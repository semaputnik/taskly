"""
A PDF's way to Paperless: accepted at once, handed over in the background,
linked when Paperless already holds it, retried on the webhook schedule, and
served from Paperless once Taskly has let go of its own copy (FR-04.5 to
FR-04.12, ADR-0010).

Paperless is a stub behind a mock transport; nothing here reaches a network.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import paperless, webhooks
from app.core.config import settings
from app.models import DeliveryState, PaperlessHandover
from tests.paperless.support import (
    API,
    Headers,
    connect,
    connected_user,
    drain,
    handover,
    read_attachment,
    settle,
    upload,
)
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_project,
    create_task_record,
    create_user_headers,
    error_code,
    issue_bot_headers,
)
from tests.utils.paperless import BASE_URL, StubPaperless, parse_multipart, pdf
from tests.utils.storage import InMemoryAttachmentStorage


def _task(client: TestClient, headers: Headers, title: str = "File the taxes") -> str:
    task_id: str = create_task_record(client, headers, title)["id"]
    return task_id


# --- Which files go (FR-04.5) -----------------------------------------------------


def test_a_pdf_of_a_connected_user_is_accepted_at_once_and_downloadable(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)

    attached = upload(client, headers, task_id, pdf())

    # Nothing has been sent yet: the answer did not wait for Paperless.
    assert stub.requests == []
    assert attached["kept_in"] == "taskly"
    assert attached["paperless_document_id"] is None
    assert attached["paperless_url"] is None
    assert attached["paperless_handover"]["state"] == "pending"
    downloaded = client.get(f"{API}/attachments/{attached['id']}", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == pdf()
    assert storage.files[attached["id"]] == pdf()


def test_a_pdf_is_known_by_its_content_not_by_its_name_or_type(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)

    disguised = upload(client, headers, task_id, pdf("x"), "scan.dat", "text/plain")
    not_a_pdf = upload(
        client, headers, task_id, b"just words", "invoice.pdf", "application/pdf"
    )

    assert handover(db, disguised["id"]) is not None
    assert handover(db, not_a_pdf["id"]) is None
    settle(stub, storage)
    assert [p.url.path for p in stub.posted] == ["/api/documents/post_document/"]
    _fields, files = parse_multipart(stub.posted[0])
    assert files["document"][1] == pdf("x")
    shown = read_attachment(client, headers, task_id, not_a_pdf["id"])
    assert shown["kept_in"] == "taskly"
    assert storage.files[not_a_pdf["id"]] == b"just words"


def test_other_files_and_users_without_a_connection_are_kept_in_taskly_as_before(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    connected = connected_user(client, db)
    plain = create_user_headers(client, db)
    mine = _task(client, connected)
    theirs = _task(client, plain)

    text = upload(client, connected, mine, b"words", "n.txt", "text/plain")
    pdf_without_connection = upload(client, plain, theirs, pdf())

    assert handover(db, text["id"]) is None
    assert handover(db, pdf_without_connection["id"]) is None
    assert drain(stub, storage) == 0
    assert stub.requests == []
    for headers, task_id, attached in [
        (connected, mine, text),
        (plain, theirs, pdf_without_connection),
    ]:
        shown = read_attachment(client, headers, task_id, attached["id"])
        assert shown["kept_in"] == "taskly"
        assert shown["paperless_document_id"] is None
        assert shown["paperless_handover"] is None
    assert storage.files[pdf_without_connection["id"]] == pdf()


def test_a_pdf_a_bot_user_attaches_goes_to_its_owners_paperless(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    owner = connected_user(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task = create_task_record(client, owner, "Receipts", project_id=project_id)

    attached = upload(client, bot, task["id"], pdf("bot"))
    settle(stub, storage)

    shown = read_attachment(client, owner, task["id"], attached["id"])
    assert shown["kept_in"] == "paperless"
    assert attached["id"] not in storage.files


def test_the_size_limit_applies_before_anything_is_sent(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ATTACHMENT_MAX_SIZE_BYTES", 20)
    headers = connected_user(client, db)
    task_id = _task(client, headers)

    r = client.post(
        f"{API}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": ("big.pdf", pdf() + b"x" * 100, "application/pdf")},
    )

    assert r.status_code == 413
    assert drain(stub, storage) == 0
    assert stub.requests == []
    assert storage.files == {}


# --- The hand-over (FR-04.6, FR-04.9) ----------------------------------------------


def test_a_pdf_is_handed_over_tagged_titled_and_noted_and_then_released(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers, "File the taxes")
    attached = upload(client, headers, task_id, pdf(), "Tax return 2025.pdf")

    settle(stub, storage)

    # The file went once, with its original name as the title and the tag.
    [post] = stub.posted
    fields, files = parse_multipart(post)
    assert files["document"] == ("Tax return 2025.pdf", pdf())
    assert fields["title"] == ["Tax return 2025.pdf"]
    [tag_id] = [i for i, name in stub.tags.items() if name == "Taskly"]
    assert fields["tags"] == [str(tag_id)]
    assert post.headers["authorization"] == "Token stub-token"
    [document] = stub.documents.values()
    assert document.title == "Tax return 2025.pdf"
    assert document.tags == [tag_id]
    # One note, naming the task and linking to it in Taskly.
    [note] = document.notes
    assert "File the taxes" in note
    assert f"{settings.FRONTEND_HOST}/tasks?task={task_id}" in note
    # Taskly let go of its copy and keeps the document's id.
    assert attached["id"] not in storage.files
    assert handover(db, attached["id"]) is None
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["kept_in"] == "paperless"
    assert shown["paperless_document_id"] == document.id
    assert shown["paperless_url"] == f"{BASE_URL}/documents/{document.id}/details"
    assert shown["paperless_handover"] is None
    assert stub.deletes == []


def test_the_tag_is_created_on_first_use_and_found_after_that(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    upload(client, headers, task_id, pdf("1"))
    settle(stub, storage)
    upload(client, headers, task_id, pdf("2"))
    settle(stub, storage)

    assert list(stub.tags.values()) == ["Taskly"]
    assert len(stub.calls("POST", "/api/tags/")) == 1


def test_an_existing_taskly_tag_is_used(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    tag_id = stub.has_tag("taskly")
    headers = connected_user(client, db)
    upload(client, headers, _task(client, headers), pdf())

    settle(stub, storage)

    assert stub.calls("POST", "/api/tags/") == []
    [document] = stub.documents.values()
    assert document.tags == [tag_id]


def test_the_file_stays_downloadable_from_taskly_until_paperless_has_consumed_it(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.polls_to_consume = 2
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    start = datetime.now(UTC)

    drain(stub, storage, now=start)
    assert len(stub.posted) == 1
    assert stub.documents == {}
    # Sent, not consumed: still Taskly's, still downloadable, still pending.
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["kept_in"] == "taskly"
    assert shown["paperless_handover"]["state"] == "pending"
    assert client.get(
        f"{API}/attachments/{attached['id']}", headers=headers
    ).content == (pdf())

    # Not asked again before the poll interval is up.
    assert drain(stub, storage, now=start + timedelta(seconds=2)) == 0

    drain(stub, storage, now=start + timedelta(seconds=15))
    drain(stub, storage, now=start + timedelta(seconds=30))
    assert attached["id"] in storage.files
    assert handover(db, attached["id"]) is not None
    drain(stub, storage, now=start + timedelta(seconds=45))

    assert attached["id"] not in storage.files
    assert len(stub.posted) == 1
    assert read_attachment(client, headers, task_id, attached["id"])["kept_in"] == (
        "paperless"
    )


def test_the_document_id_is_found_by_checksum_when_paperless_does_not_report_it(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.hold_document_id = False
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())

    settle(stub, storage)

    [document] = stub.documents.values()
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["paperless_document_id"] == document.id


# --- A document Paperless already holds (FR-04.7, FR-04.9) ----------------------------


def test_a_pdf_paperless_already_holds_is_linked_and_not_sent_again(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    existing = stub.has_document(pdf("known"), "Filed by hand")
    headers = connected_user(client, db)
    task_id = _task(client, headers, "Renew the passport")
    attached = upload(client, headers, task_id, pdf("known"), "copy.pdf")

    settle(stub, storage)

    assert stub.posted == []
    assert list(stub.documents) == [existing.id]
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["kept_in"] == "paperless"
    assert shown["paperless_document_id"] == existing.id
    assert attached["id"] not in storage.files
    # It gets the tag and a note too.
    [tag_id] = [i for i, name in stub.tags.items() if name == "Taskly"]
    assert existing.tags == [tag_id]
    [note] = existing.notes
    assert "Renew the passport" in note


def test_one_document_may_stand_behind_several_attachments_with_a_note_per_task(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    first_task = _task(client, headers, "First task")
    second_task = _task(client, headers, "Second task")
    one = upload(client, headers, first_task, pdf("same"))
    again = upload(client, headers, first_task, pdf("same"), "again.pdf")
    other = upload(client, headers, second_task, pdf("same"))

    settle(stub, storage)

    [document] = stub.documents.values()
    ids = {
        read_attachment(client, headers, task_id, a["id"])["paperless_document_id"]
        for task_id, a in [(first_task, one), (first_task, again), (second_task, other)]
    }
    assert ids == {document.id}
    # One note for each task it is attached to, not for each attachment.
    assert len(document.notes) == 2
    assert sum("First task" in n for n in document.notes) == 1
    assert sum("Second task" in n for n in document.notes) == 1
    assert document.tags.count(next(iter(stub.tags))) == 1


def test_a_duplicate_paperless_rejects_after_the_check_is_linked_too(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf("race"))
    # The document appears in Paperless between the check and the consumption.
    original_handle = stub.handle

    def handle(request: httpx.Request) -> httpx.Response:
        response = original_handle(request)
        if request.url.path == "/api/documents/post_document/":
            stub.has_document(pdf("race"), "Filed meanwhile")
        return response

    stub.handle = handle  # type: ignore[method-assign]

    settle(stub, storage)

    [filed] = stub.documents.values()
    assert filed.title == "Filed meanwhile"
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["paperless_document_id"] == filed.id
    assert attached["id"] not in storage.files


# --- Failing, retrying, sending again (FR-04.6) ------------------------------------------


def test_a_failed_attempt_is_retried_on_the_webhook_schedule_and_then_fails(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.status = 500
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    now = datetime.now(UTC)

    delays = []
    for delay in webhooks.RETRY_DELAYS:
        assert drain(stub, storage, now=now) == 1
        row = handover(db, attached["id"])
        assert row is not None
        assert row.state == DeliveryState.PENDING.value
        assert row.next_attempt_at == now + delay
        delays.append(delay)
        # Not before it is due.
        assert drain(stub, storage, now=now + delay - timedelta(seconds=1)) == 0
        now += delay
    assert delays == [timedelta(minutes=m) for m in (1, 5, 15, 60, 60)]
    assert drain(stub, storage, now=now) == 1

    row = handover(db, attached["id"])
    assert row is not None
    assert row.state == DeliveryState.FAILED.value
    assert row.attempts == webhooks.MAX_ATTEMPTS == 6
    assert drain(stub, storage, now=now + timedelta(days=1)) == 0
    # The file stays kept in Taskly, with the reason shown.
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["kept_in"] == "taskly"
    failure = shown["paperless_handover"]
    assert failure["state"] == "failed"
    assert failure["attempts"] == 6
    assert failure["next_attempt_at"] is None
    assert "Paperless answered 500" in failure["error"]
    assert client.get(
        f"{API}/attachments/{attached['id']}", headers=headers
    ).content == (pdf())


def test_a_failed_hand_over_can_be_sent_again_by_its_owner(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.down = True
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    now = datetime.now(UTC)
    for delay in (timedelta(0), *webhooks.RETRY_DELAYS):
        now += delay
        drain(stub, storage, now=now)
    failed = read_attachment(client, headers, task_id, attached["id"])
    assert failed["paperless_handover"]["state"] == "failed"
    assert "could not be reached" in failed["paperless_handover"]["error"]

    stub.down = False
    r = client.post(f"{API}/attachments/{attached['id']}/resend", headers=headers)

    assert r.status_code == 200, r.text
    assert r.json()["paperless_handover"]["state"] == "pending"
    assert r.json()["paperless_handover"]["error"] is None
    settle(stub, storage, start=now)
    assert read_attachment(client, headers, task_id, attached["id"])["kept_in"] == (
        "paperless"
    )


def test_only_a_failed_hand_over_can_be_sent_again(
    client: TestClient, db: Session
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    waiting = upload(client, headers, task_id, pdf())
    plain = upload(client, headers, task_id, b"words", "n.txt", "text/plain")

    for attached in (waiting, plain):
        r = client.post(f"{API}/attachments/{attached['id']}/resend", headers=headers)
        assert r.status_code == 409
        assert error_code(r) == "attachment_not_failed"


def test_sending_again_is_for_the_owner_only(client: TestClient, db: Session) -> None:
    owner = connected_user(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    stranger = create_user_headers(client, db)
    task = create_task_record(client, owner, "Receipts", project_id=project_id)
    attached = upload(client, owner, task["id"], pdf())
    row = handover(db, attached["id"])
    assert row is not None
    row.state = DeliveryState.FAILED.value
    db.add(row)
    db.commit()

    by_bot = client.post(f"{API}/attachments/{attached['id']}/resend", headers=bot)
    by_stranger = client.post(
        f"{API}/attachments/{attached['id']}/resend", headers=stranger
    )

    assert by_bot.status_code == 403
    assert error_code(by_bot) == "human_only"
    assert by_stranger.status_code == 404
    unchanged = handover(db, attached["id"])
    assert unchanged is not None
    assert unchanged.state == DeliveryState.FAILED.value


def test_a_token_paperless_refuses_is_the_reason_given(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    stub.token = "rotated-in-paperless"

    drain(stub, storage)

    row = handover(db, attached["id"])
    assert row is not None
    assert row.last_error is not None
    assert "refused the token" in row.last_error
    assert row.attempts == 1


def test_a_file_paperless_cannot_process_is_a_failed_attempt_with_its_reason(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.consume = "failure"
    stub.failure_result = "broken.pdf: Not consuming: the file is corrupt"
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    now = datetime.now(UTC)

    drain(stub, storage, now=now)
    drain(stub, storage, now=now + timedelta(seconds=30))

    row = handover(db, attached["id"])
    assert row is not None
    assert row.state == DeliveryState.PENDING.value
    assert row.attempts == 1
    assert row.last_error is not None
    assert "the file is corrupt" in row.last_error
    # The next attempt starts again from the top, after the first delay.
    assert row.stage == "send"
    assert row.next_attempt_at == now + timedelta(seconds=30) + timedelta(minutes=1)
    assert attached["id"] in storage.files


def test_waiting_too_long_for_paperless_to_consume_a_file_is_a_failed_attempt(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.consume = "pending"
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    start = datetime.now(UTC)

    drain(stub, storage, now=start)
    drain(stub, storage, now=start + paperless.POLL_DEADLINE - timedelta(minutes=1))
    row = handover(db, attached["id"])
    assert row is not None
    assert row.attempts == 0

    drain(stub, storage, now=start + paperless.POLL_DEADLINE + timedelta(minutes=1))

    row = handover(db, attached["id"])
    assert row is not None
    assert row.attempts == 1
    assert row.last_error is not None
    assert "had not processed the file" in row.last_error
    assert row.stage == "send"


def test_a_missing_local_copy_fails_the_hand_over_at_once(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    del storage.files[attached["id"]]

    drain(stub, storage)

    row = handover(db, attached["id"])
    assert row is not None
    assert row.state == DeliveryState.FAILED.value
    assert row.last_error is not None
    assert "copy of the file is missing" in row.last_error
    assert stub.requests == []


# --- Never deleting (FR-04.8) ------------------------------------------------------------


def test_removing_an_attachment_kept_in_paperless_drops_the_link_and_nothing_else(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())
    settle(stub, storage)
    requests_before = len(stub.requests)

    r = client.delete(f"{API}/attachments/{attached['id']}", headers=headers)

    assert r.status_code == 200
    assert len(stub.documents) == 1
    assert len(stub.requests) == requests_before
    assert stub.deletes == []
    listed = client.get(f"{API}/tasks/{task_id}/attachments/", headers=headers)
    assert listed.json()["count"] == 0


def test_deleting_and_restoring_a_task_and_deleting_the_account_change_nothing_in_paperless(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    upload(client, headers, task_id, pdf())
    settle(stub, storage)
    requests_before = len(stub.requests)

    assert client.delete(f"{API}/tasks/{task_id}", headers=headers).status_code == 200
    assert client.delete(f"{API}/users/me", headers=headers).status_code == 200

    assert len(stub.requests) == requests_before
    assert stub.deletes == []
    assert len(stub.documents) == 1


def test_disconnecting_leaves_a_pdf_still_waiting_in_taskly(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf())

    client.delete(f"{API}/paperless/", headers=headers)

    assert handover(db, attached["id"]) is None
    assert drain(stub, storage) == 0
    assert stub.requests == []
    shown = read_attachment(client, headers, task_id, attached["id"])
    assert shown["kept_in"] == "taskly"
    assert shown["paperless_handover"] is None
    assert storage.files[attached["id"]] == pdf()


def test_a_hand_over_waiting_when_the_connection_is_changed_starts_again(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    stub.consume = "pending"
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    drain(stub, storage)
    row = handover(db, attached["id"])
    assert row is not None
    assert row.stage == "poll"
    assert row.paperless_task_id is not None

    connect(client, headers, url="https://other.example.com", token="theirs")

    row = handover(db, attached["id"])
    assert row is not None
    assert row.stage == "send"
    assert row.paperless_task_id is None


# --- Downloading (FR-04.10) ---------------------------------------------------------------------


def test_a_download_after_release_is_the_original_from_paperless(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    attached = upload(client, headers, task_id, pdf("orig"), "Tax return.pdf")
    settle(stub, storage)
    assert attached["id"] not in storage.files

    r = client.get(f"{API}/attachments/{attached['id']}", headers=headers)

    assert r.status_code == 200
    # The original bytes, not the archived copy Paperless would give by default.
    assert r.content == pdf("orig")
    assert r.headers["content-type"] == "application/pdf"
    assert "Tax%20return.pdf" in r.headers["content-disposition"]
    [download] = stub.calls(
        "GET", f"/api/documents/{next(iter(stub.documents))}/download/"
    )
    assert download.url.params["original"] == "true"


def test_a_bot_user_downloads_a_file_kept_in_paperless_wherever_it_can_read_the_task(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    owner = connected_user(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    task = create_task_record(client, owner, "Receipts", project_id=project_id)
    attached = upload(client, owner, task["id"], pdf("bot"))
    settle(stub, storage)

    r = client.get(f"{API}/attachments/{attached['id']}", headers=bot)

    assert r.status_code == 200
    assert r.content == pdf("bot")


def test_a_download_says_so_when_paperless_cannot_be_reached(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    settle(stub, storage)
    stub.down = True

    r = client.get(f"{API}/attachments/{attached['id']}", headers=headers)

    assert r.status_code == 502
    assert error_code(r) == "paperless_unreachable"
    assert (
        "kept in Paperless, which could not be reached" in r.json()["detail"]["message"]
    )


def test_a_download_says_so_when_the_document_is_gone_from_paperless(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    settle(stub, storage)
    stub.documents.clear()

    r = client.get(f"{API}/attachments/{attached['id']}", headers=headers)

    assert r.status_code == 404
    assert error_code(r) == "paperless_document_missing"


def test_a_file_kept_in_paperless_stays_out_of_reach_of_other_users(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    settle(stub, storage)
    stranger = connected_user(client, db)

    r = client.get(f"{API}/attachments/{attached['id']}", headers=stranger)

    assert r.status_code == 404


# --- The shared loop (ADR-0010) -----------------------------------------------------------------


def test_one_pass_of_the_loop_drains_webhooks_and_hand_overs_together(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    monkeypatch.setattr(paperless, "default_storage", lambda: storage)

    claimed = webhooks._drain_once(None, stub.client())

    assert claimed == 1
    assert len(stub.posted) == 1
    assert handover(db, attached["id"]) is not None


def test_the_loop_hands_a_pdf_over_as_soon_as_it_is_attached(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = connected_user(client, db)
    task_id = _task(client, headers)
    monkeypatch.setattr(paperless, "default_storage", lambda: storage)

    async def run() -> None:
        # A poll interval far longer than the test: only the wake-up on commit
        # can explain a prompt hand-over.
        loop = asyncio.create_task(
            webhooks.drain_forever(paperless_client=stub.client(), poll_seconds=3600)
        )
        try:
            await asyncio.sleep(0.2)
            await asyncio.to_thread(upload, client, headers, task_id, pdf())
            for _ in range(100):
                if stub.posted:
                    break
                await asyncio.sleep(0.05)
        finally:
            loop.cancel()
            await asyncio.gather(loop, return_exceptions=True)

    asyncio.run(run())

    assert len(stub.posted) == 1


def test_two_passes_never_claim_the_same_hand_over(
    client: TestClient, db: Session
) -> None:
    headers = connected_user(client, db)
    upload(client, headers, _task(client, headers), pdf())
    now = datetime.now(UTC)

    first = webhooks.claim_due(PaperlessHandover, now=now, limit=10)
    second = webhooks.claim_due(PaperlessHandover, now=now, limit=10)

    assert len(first) == 1
    assert second == []


def test_a_crash_mid_attempt_only_delays_the_retry_until_the_lease_runs_out(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    now = datetime.now(UTC)
    webhooks.claim_due(PaperlessHandover, now=now, limit=10)

    assert drain(stub, storage, now=now + timedelta(seconds=30)) == 0
    assert (
        drain(stub, storage, now=now + paperless.HANDOVER_LEASE + timedelta(seconds=1))
        == 1
    )
    assert handover(db, attached["id"]) is not None


def test_the_post_carries_nothing_but_the_file_its_title_and_the_tag(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    upload(client, headers, _task(client, headers), pdf(), "a.pdf")

    drain(stub, storage)

    fields, files = parse_multipart(stub.posted[0])
    assert set(fields) == {"title", "tags"}
    assert set(files) == {"document"}
    # Whatever a note says, it is never in the post: it follows the document.
    assert json.dumps(fields).count("Taskly") == 0


def test_what_an_attempt_came_to_is_dropped_when_the_connection_changed_meanwhile(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    attached = upload(client, headers, _task(client, headers), pdf())
    original_handle = stub.handle

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/documents/post_document/":
            # The owner points Paperless somewhere else while the file is sent.
            connect(client, headers, url="https://other.example.com", token="theirs")
        return original_handle(request)

    stub.handle = handle  # type: ignore[method-assign]

    drain(stub, storage)

    row = handover(db, attached["id"])
    assert row is not None
    # The restart stands: the stale task id of the old instance was not written.
    assert row.stage == "send"
    assert row.paperless_task_id is None
