"""
The Paperless connection: set, test, change and disconnect, owner only, with a
token that is kept and never shown (FR-04.4, FR-04.8, FR-04.12).
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import paperless
from app.core import outbound
from app.core.config import settings
from app.models import PaperlessConnection
from tests.paperless.support import API, connect, connected_user, drain, settle, upload
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_project,
    create_task_record,
    create_user_headers,
    error_code,
    issue_bot_headers,
)
from tests.utils.paperless import BASE_URL, TOKEN, StubPaperless, pdf
from tests.utils.storage import InMemoryAttachmentStorage


def _stored(
    db: Session, headers: dict[str, str], client: TestClient
) -> PaperlessConnection:
    db.expire_all()
    me = client.get(f"{API}/users/me", headers=headers).json()["id"]
    return db.exec(
        select(PaperlessConnection).where(PaperlessConnection.user_id == me)
    ).one()


def test_there_is_no_connection_until_one_is_set(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)

    r = client.get(f"{API}/paperless/", headers=headers)

    assert r.status_code == 200
    assert r.json() == {"connected": False, "url": None, "documents_kept": 0}


def test_connecting_stores_the_address_and_never_shows_the_token(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)

    r = connect(client, headers, url=f"{BASE_URL}/")

    assert r.status_code == 200, r.text
    assert r.json() == {"connected": True, "url": BASE_URL, "documents_kept": 0}
    assert TOKEN not in r.text
    assert TOKEN not in client.get(f"{API}/paperless/", headers=headers).text
    row = _stored(db, headers, client)
    # Kept encrypted: not the token, and not recoverable without the key.
    assert TOKEN not in row.token_encrypted
    assert paperless.decrypt_token(row.token_encrypted) == TOKEN


def test_the_token_is_encrypted_under_its_own_key(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = create_user_headers(client, db)
    connect(client, headers)
    stored = _stored(db, headers, client).token_encrypted

    # Neither SECRET_KEY nor WEBHOOK_SECRET_KEY is what it is encrypted under.
    monkeypatch.setattr(settings, "SECRET_KEY", "something-else")
    monkeypatch.setattr(settings, "WEBHOOK_SECRET_KEY", "something-else-again")
    assert paperless.decrypt_token(stored) == TOKEN

    monkeypatch.setattr(settings, "PAPERLESS_TOKEN_KEY", "rotated")
    with pytest.raises(paperless.PaperlessError, match="PAPERLESS_TOKEN_KEY"):
        paperless.decrypt_token(stored)


def test_a_rotated_key_makes_the_connection_test_say_to_enter_the_token_again(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = connected_user(client, db)
    monkeypatch.setattr(settings, "PAPERLESS_TOKEN_KEY", "rotated")

    r = client.post(f"{API}/paperless/test", headers=headers)

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "Enter the token again" in r.json()["error"]
    assert stub.requests == []


def test_a_connection_needs_a_token(client: TestClient, db: Session) -> None:
    headers = create_user_headers(client, db)

    r = connect(client, headers, token=None)

    assert r.status_code == 422
    assert error_code(r) == "paperless_token_required"
    assert client.get(f"{API}/paperless/", headers=headers).json()["connected"] is False


@pytest.mark.parametrize("url", ["ftp://paperless.example.com", "not a url", "http://"])
def test_an_address_that_is_not_http_is_refused(
    client: TestClient, db: Session, url: str
) -> None:
    headers = create_user_headers(client, db)

    r = connect(client, headers, url=url)

    assert r.status_code == 422
    assert str(error_code(r)).startswith("paperless_url_")


def test_a_private_address_is_refused_naming_the_rule(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)

    r = connect(client, headers, url="http://192.168.1.20:8000")

    assert r.status_code == 422
    assert error_code(r) == "paperless_url_private_address"
    message = r.json()["detail"]["message"]
    assert "private" in message
    assert outbound.ALLOW_SETTING in message


def test_a_private_address_is_allowed_when_the_installation_allows_it(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "OUTBOUND_ALLOW_PRIVATE_ADDRESSES", True)
    headers = create_user_headers(client, db)

    r = connect(client, headers, url="http://localhost:8000")

    assert r.status_code == 200, r.text


def test_the_token_can_be_replaced_without_naming_the_address_again(
    client: TestClient, db: Session
) -> None:
    headers = connected_user(client, db)

    r = connect(client, headers, token="a-new-token")

    assert r.status_code == 200
    assert paperless.decrypt_token(_stored(db, headers, client).token_encrypted) == (
        "a-new-token"
    )


def test_the_token_can_be_left_out_while_the_address_stays(
    client: TestClient, db: Session
) -> None:
    headers = connected_user(client, db)

    r = connect(client, headers, token=None)

    assert r.status_code == 200
    assert paperless.decrypt_token(_stored(db, headers, client).token_encrypted) == (
        TOKEN
    )


def test_a_new_address_needs_its_token_so_the_old_one_is_never_sent_there(
    client: TestClient, db: Session
) -> None:
    headers = connected_user(client, db)

    r = connect(client, headers, url="https://elsewhere.example.com", token=None)

    assert r.status_code == 422
    assert error_code(r) == "paperless_token_required"
    assert client.get(f"{API}/paperless/", headers=headers).json()["url"] == BASE_URL

    r = connect(client, headers, url="https://elsewhere.example.com", token="theirs")
    assert r.status_code == 200
    assert r.json()["url"] == "https://elsewhere.example.com"


def test_every_user_has_a_connection_of_their_own(
    client: TestClient, db: Session
) -> None:
    mine = connected_user(client, db)
    theirs = create_user_headers(client, db)

    assert client.get(f"{API}/paperless/", headers=theirs).json()["connected"] is False
    assert client.get(f"{API}/paperless/", headers=mine).json()["connected"] is True


# --- Owner only -----------------------------------------------------------------


def test_a_bot_user_cannot_touch_the_connection(
    client: TestClient, db: Session
) -> None:
    owner = connected_user(client, db)
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    for method, path, body in [
        ("GET", "/paperless/", None),
        ("PUT", "/paperless/", {"url": BASE_URL, "token": "x"}),
        ("POST", "/paperless/test", None),
        ("DELETE", "/paperless/", None),
    ]:
        r = client.request(method, f"{API}{path}", headers=bot, json=body)
        assert r.status_code == 403, (method, path, r.text)
        assert error_code(r) == "human_only"

    assert client.get(f"{API}/paperless/", headers=owner).json()["url"] == BASE_URL


def test_the_connection_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.get(f"{API}/paperless/").status_code in (401, 403)


# --- Testing --------------------------------------------------------------------


def test_the_saved_connection_can_be_tested(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = connected_user(client, db)

    r = client.post(f"{API}/paperless/test", headers=headers)

    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None}
    [request] = stub.requests
    assert request.headers["authorization"] == f"Token {TOKEN}"
    assert request.url.host == "paperless.example.com"


def test_a_refused_token_fails_the_test_saying_so(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = connected_user(client, db)
    stub.token = "changed-in-paperless"

    r = client.post(f"{API}/paperless/test", headers=headers)

    assert r.json()["ok"] is False
    assert "refused the token" in r.json()["error"]


def test_an_unreachable_paperless_fails_the_test_saying_so(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = connected_user(client, db)
    stub.down = True

    r = client.post(f"{API}/paperless/test", headers=headers)

    assert r.json()["ok"] is False
    assert "could not be reached" in r.json()["error"]


def test_values_typed_but_not_saved_can_be_tested(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = create_user_headers(client, db)

    r = client.post(
        f"{API}/paperless/test",
        headers=headers,
        json={"url": "https://typed.example.com/", "token": TOKEN},
    )

    assert r.json() == {"ok": True, "error": None}
    assert stub.requests[0].url.host == "typed.example.com"
    assert client.get(f"{API}/paperless/", headers=headers).json()["connected"] is False


def test_the_saved_token_is_not_tried_against_an_address_typed_for_the_test(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = connected_user(client, db)

    r = client.post(
        f"{API}/paperless/test",
        headers=headers,
        json={"url": "https://typed.example.com"},
    )

    assert r.status_code == 422
    assert error_code(r) == "paperless_token_required"
    assert stub.requests == []


def test_testing_with_nothing_saved_and_nothing_typed_is_not_found(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)

    r = client.post(f"{API}/paperless/test", headers=headers)

    assert r.status_code == 404
    assert error_code(r) == "paperless_not_connected"


def test_a_private_address_fails_the_test_naming_the_rule(
    client: TestClient, db: Session, stub: StubPaperless
) -> None:
    headers = create_user_headers(client, db)

    r = client.post(
        f"{API}/paperless/test",
        headers=headers,
        json={"url": "http://10.0.0.5", "token": TOKEN},
    )

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert outbound.ALLOW_SETTING in r.json()["error"]
    assert stub.requests == []


# --- Disconnecting and connecting moving nothing ------------------------------------


def test_disconnecting_reports_how_many_documents_become_unreachable_and_deletes_nothing(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task = create_task_record(client, headers, "Taxes")
    first = upload(client, headers, task["id"], pdf("a"))
    second = upload(client, headers, task["id"], pdf("b"))
    upload(client, headers, task["id"], b"plain text", "n.txt", "text/plain")
    settle(stub, storage)
    assert (
        client.get(f"{API}/paperless/", headers=headers).json()["documents_kept"] == 2
    )

    r = client.delete(f"{API}/paperless/", headers=headers)

    assert r.status_code == 200, r.text
    assert r.json() == {"connected": False, "unreachable_documents": 2}
    assert client.get(f"{API}/paperless/", headers=headers).json() == {
        "connected": False,
        "url": None,
        "documents_kept": 2,
    }
    assert stub.deletes == []
    assert len(stub.documents) == 2
    # The attachments are still there, still kept in Paperless, out of reach.
    shown = client.get(f"{API}/tasks/{task['id']}/attachments/", headers=headers)
    kept = {a["id"]: a for a in shown.json()["data"] if a["kept_in"] == "paperless"}
    assert set(kept) == {first["id"], second["id"]}
    assert all(a["paperless_url"] is None for a in kept.values())


def test_disconnecting_when_not_connected_is_not_found(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)

    r = client.delete(f"{API}/paperless/", headers=headers)

    assert r.status_code == 404
    assert error_code(r) == "paperless_not_connected"


def test_documents_are_reachable_again_when_the_connection_is_set_again(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = connected_user(client, db)
    task = create_task_record(client, headers, "Taxes")
    attached = upload(client, headers, task["id"], pdf("a"))
    settle(stub, storage)
    client.delete(f"{API}/paperless/", headers=headers)
    out_of_reach = client.get(f"{API}/attachments/{attached['id']}", headers=headers)
    assert out_of_reach.status_code == 409
    assert error_code(out_of_reach) == "paperless_not_connected"

    connect(client, headers)

    back = client.get(f"{API}/attachments/{attached['id']}", headers=headers)
    assert back.status_code == 200
    assert back.content == pdf("a")


def test_connecting_moves_nothing(
    client: TestClient,
    db: Session,
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
) -> None:
    headers = create_user_headers(client, db)
    task = create_task_record(client, headers, "Taxes")
    before = upload(client, headers, task["id"], pdf("old"))

    connect(client, headers)

    assert drain(stub, storage) == 0
    assert stub.requests == []
    assert storage.files[before["id"]] == pdf("old")
    shown = client.get(f"{API}/tasks/{task['id']}/attachments/", headers=headers)
    [attachment] = shown.json()["data"]
    assert attachment["kept_in"] == "taskly"
    assert attachment["paperless_handover"] is None
