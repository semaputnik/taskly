"""
Sending: the request, its signature, the retry schedule, the loop and what the
owner is shown (FR-11.8 to FR-11.14).

Nothing here reaches a network. A delivery pass is called directly, with a mock
transport and a clock the test moves; the loop itself is started only by the
test that is about it.
"""

import asyncio
import json
import re
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session, col

from app import webhooks
from app.core import outbound
from app.core.config import settings
from app.main import app
from app.models import BotUser, DeliveryState, WebhookDelivery
from tests.utils.accounts import (
    create_project,
    create_task_record,
    create_user_headers,
    create_webhook_bot,
    set_webhook,
)
from tests.utils.webhooks import Receiver, outbox, pending

API = settings.API_V1_STR
Headers = dict[str, str]


def _ready(
    client: TestClient, db: Session, **bot_options: Any
) -> tuple[Headers, dict[str, Any], dict[str, Any]]:
    """An owner and a bot user with its webhooks set, and one task ready for it."""
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_webhook_bot(client, owner, project_ids=[project_id], **bot_options)
    task = create_task_record(
        client,
        owner,
        "Triage the inbox",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    return owner, bot, task


def _last(db: Session, bot: dict[str, Any]) -> WebhookDelivery:
    [row] = outbox(db, bot["id"])
    return row


def _now() -> datetime:
    return datetime.now(UTC)


# --- The request ----------------------------------------------------------------


def test_a_delivery_is_a_signed_post_with_the_thin_body(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, task = _ready(client, db)
    row = _last(db, bot)
    now = _now()

    assert webhooks.deliver_due(client=receiver.client(), now=now) == 1

    [request] = receiver.requests
    assert request.method == "POST"
    assert str(request.url) == "https://hooks.example.com/task"
    body = json.loads(request.content)
    assert body == {
        "event": "task.ready",
        "delivery_id": str(row.id),
        "occurred_at": row.occurred_at.astimezone(UTC).isoformat(),
        "bot_user_id": bot["id"],
        "task_id": task["id"],
        "task_title": "Triage the inbox",
    }
    assert request.headers["content-type"] == "application/json"
    assert request.headers["x-taskly-event"] == "task.ready"
    assert request.headers["x-taskly-delivery"] == str(row.id)
    assert request.headers["x-taskly-timestamp"] == str(int(now.timestamp()))
    assert request.headers["x-taskly-signature"].startswith("sha256=")
    assert request.extensions["timeout"]["read"] == 10.0


def test_a_comment_delivery_adds_the_comment_id(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, task = _ready(client, db)
    r = client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=owner, json={"body": "Hi"}
    )
    comment_id = r.json()["id"]

    webhooks.deliver_due(client=receiver.client())

    by_event = {json.loads(q.content)["event"]: q for q in receiver.requests}
    assert str(by_event["comment.added"].url) == "https://hooks.example.com/comment"
    assert json.loads(by_event["comment.added"].content)["comment_id"] == comment_id
    assert "comment_id" not in json.loads(by_event["task.ready"].content)


def test_the_signature_verifies_with_the_reference_verifier_in_the_docs(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    webhooks.deliver_due(client=receiver.client())
    [request] = receiver.requests
    headers = dict(request.headers)
    # The verifier in the API docs, exactly as a reader would paste it.
    snippet = re.search(r"```python\n(.*?)```", webhooks.DELIVERY_CONTRACT, re.DOTALL)
    assert snippet
    namespace: dict[str, Any] = {}
    exec(snippet.group(1), namespace)  # noqa: S102
    verify = namespace["verify"]
    # Header names are case-insensitive on the wire; the snippet reads them as
    # the docs spell them.
    spelled = {
        "X-Taskly-Timestamp": headers["x-taskly-timestamp"],
        "X-Taskly-Signature": headers["x-taskly-signature"],
    }

    assert verify(bot["secret"], spelled, request.content) is True
    assert verify("whsec_not_it", spelled, request.content) is False
    assert verify(bot["secret"], spelled, request.content + b" ") is False
    stale = {**spelled, "X-Taskly-Timestamp": str(int(time.time()) - 3600)}
    assert verify(bot["secret"], stale, request.content) is False
    # And the module's own copy agrees.
    assert webhooks.verify_signature(bot["secret"], spelled, request.content)


def test_a_regenerated_secret_signs_the_next_delivery(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    receiver.status = 500
    webhooks.deliver_due(client=receiver.client())
    new = client.post(f"{API}/bot-users/{bot['id']}/webhook-secret", headers=owner)
    new_secret = new.json()["secret"]
    receiver.status = 200

    webhooks.deliver_due(client=receiver.client(), now=_now() + timedelta(minutes=1))

    request = receiver.requests[-1]
    headers = {
        "X-Taskly-Timestamp": request.headers["x-taskly-timestamp"],
        "X-Taskly-Signature": request.headers["x-taskly-signature"],
    }
    assert webhooks.verify_signature(new_secret, headers, request.content)
    assert not webhooks.verify_signature(bot["secret"], headers, request.content)


# --- Success, failure and the schedule (FR-11.10) --------------------------------


def test_a_2xx_answer_delivers_it_and_nothing_is_sent_again(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    receiver.status = 204

    webhooks.deliver_due(client=receiver.client())
    assert (
        webhooks.deliver_due(client=receiver.client(), now=_now() + timedelta(days=1))
        == 0
    )

    row = _last(db, bot)
    assert (row.state, row.attempts, row.last_status_code) == ("delivered", 1, 204)
    assert len(receiver.requests) == 1


def test_a_failed_delivery_is_retried_after_1_5_15_60_and_60_minutes_then_failed(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    receiver.status = 503
    start = _now()

    clock = start
    waits = [1, 5, 15, 60, 60]
    assert webhooks.deliver_due(client=receiver.client(), now=clock) == 1
    for attempt, minutes in enumerate(waits, start=1):
        row = _last(db, bot)
        assert (row.state, row.attempts) == ("pending", attempt)
        assert row.next_attempt_at == clock + timedelta(minutes=minutes)
        # Not due a moment before.
        early = clock + timedelta(minutes=minutes) - timedelta(seconds=1)
        assert webhooks.deliver_due(client=receiver.client(), now=early) == 0
        clock += timedelta(minutes=minutes)
        assert webhooks.deliver_due(client=receiver.client(), now=clock) == 1

    row = _last(db, bot)
    assert (row.state, row.attempts) == ("failed", 6)
    assert len(receiver.requests) == 6
    # After the last attempt it is not tried again, however long it waits.
    assert (
        webhooks.deliver_due(client=receiver.client(), now=clock + timedelta(days=9))
        == 0
    )
    assert len(receiver.requests) == 6
    # Each attempt carries its own timestamp, so a replay window still works.
    stamps = {r.headers["x-taskly-timestamp"] for r in receiver.requests}
    assert len(stamps) == 6
    assert clock - start == timedelta(minutes=141)


def test_a_retry_that_succeeds_ends_the_delivery(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    receiver.status = 500
    start = _now()
    webhooks.deliver_due(client=receiver.client(), now=start)
    receiver.status = 200

    webhooks.deliver_due(client=receiver.client(), now=start + timedelta(minutes=1))

    row = _last(db, bot)
    assert (row.state, row.attempts, row.last_status_code) == ("delivered", 2, 200)
    assert (
        webhooks.deliver_due(client=receiver.client(), now=start + timedelta(days=1))
        == 0
    )


def test_a_timeout_is_a_failed_attempt_that_says_so(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    receiver.fail_with = httpx.ReadTimeout("slow")

    webhooks.deliver_due(client=receiver.client())

    row = _last(db, bot)
    assert row.state == "pending"
    assert row.last_status_code is None
    assert row.last_error == "No answer within 10 seconds"


def test_a_refused_connection_is_a_failed_attempt_that_says_so(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    receiver.fail_with = httpx.ConnectError("Connection refused")

    webhooks.deliver_due(client=receiver.client())

    row = _last(db, bot)
    assert row.last_error == "ConnectError: Connection refused"


def test_any_exception_while_sending_is_a_failed_attempt_not_a_lost_one(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db)
    # Not an `httpx.HTTPError`: had it escaped, the delivery would never be
    # recorded and would be claimed again for ever.
    receiver.fail_with = RuntimeError("boom")

    assert webhooks.deliver_due(client=receiver.client()) == 1

    row = _last(db, bot)
    assert (row.state, row.attempts) == ("pending", 1)
    assert row.last_error == "RuntimeError: boom"


def test_a_redirect_is_a_failure_and_is_not_followed(
    client: TestClient, db: Session
) -> None:
    _owner, bot, _task = _ready(client, db)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://10.0.0.1/steal"})

    # The client `webhooks.make_client` makes, with the network swapped out.
    real = webhooks.make_client()
    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=real.follow_redirects,
    )

    webhooks.deliver_due(client=http)

    assert seen == ["https://hooks.example.com/task"]
    row = _last(db, bot)
    assert row.last_status_code == 302
    assert row.last_error == "The receiver answered 302"


def test_the_event_is_sent_with_the_title_it_was_about(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, _bot, task = _ready(client, db)
    client.patch(f"{API}/tasks/{task['id']}", headers=owner, json={"title": "Renamed"})

    webhooks.deliver_due(client=receiver.client())

    assert json.loads(receiver.requests[0].content)["task_title"] == "Triage the inbox"


# --- Addresses at delivery (FR-11.3) ---------------------------------------------


def test_a_name_that_comes_to_resolve_somewhere_private_is_refused_at_delivery(
    client: TestClient, db: Session, receiver: Receiver, monkeypatch: pytest.MonkeyPatch
) -> None:
    _owner, bot, _task = _ready(client, db)
    monkeypatch.setattr(outbound, "resolve_host", lambda _host: ["10.9.8.7"])

    webhooks.deliver_due(client=receiver.client())

    assert receiver.requests == []
    row = _last(db, bot)
    assert row.state == "pending"
    assert row.last_status_code is None
    assert row.last_error is not None
    assert row.last_error.startswith("Refused: hooks.example.com resolves to 10.9.8.7")
    assert outbound.ALLOW_SETTING in row.last_error


def test_the_installation_setting_lets_a_private_address_be_delivered_to(
    client: TestClient, db: Session, receiver: Receiver, monkeypatch: pytest.MonkeyPatch
) -> None:
    _owner, bot, _task = _ready(client, db)
    monkeypatch.setattr(outbound, "resolve_host", lambda _host: ["10.9.8.7"])
    monkeypatch.setattr(settings, "OUTBOUND_ALLOW_PRIVATE_ADDRESSES", True)

    webhooks.deliver_due(client=receiver.client())

    assert len(receiver.requests) == 1
    assert _last(db, bot).state == "delivered"


# --- What is dropped instead of sent (FR-11.13) -----------------------------------


def test_a_deleted_bot_users_events_are_not_sent(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    assert webhooks.deliver_due(client=receiver.client()) == 0

    assert receiver.requests == []


def test_an_event_whose_webhook_has_no_address_any_more_is_dropped_not_sent(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    _owner, bot, _task = _ready(client, db, comment=False)
    # Clearing the webhook through the API discards what waits for it; this is
    # the same state reached by a delivery that was already claimed.
    db.execute(
        update(BotUser)
        .where(col(BotUser.id) == uuid.UUID(bot["id"]))
        .values(task_webhook_url=None)
    )
    db.commit()

    assert webhooks.deliver_due(client=receiver.client()) == 1

    assert receiver.requests == []
    assert outbox(db, bot["id"]) == []


def test_a_deleted_bot_user_mid_flight_discards_the_attempt_it_was_sent(
    client: TestClient, db: Session
) -> None:
    owner, bot, _task = _ready(client, db)

    def delete_it(_request: httpx.Request) -> None:
        client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)

    receiver = Receiver(on_request=delete_it)
    webhooks.deliver_due(client=receiver.client())

    assert len(receiver.requests) == 1
    assert outbox(db, bot["id"]) == []


# --- Two processes, a crash, a restart (ADR-0009) ---------------------------------


def _stage_many(db: Session, bot: dict[str, Any], count: int) -> list[uuid.UUID]:
    now = _now()
    rows = [
        WebhookDelivery(
            bot_user_id=uuid.UUID(bot["id"]),
            webhook="task",
            event="task.ready",
            occurred_at=now,
            next_attempt_at=now,
            task_id=uuid.uuid4(),
            task_title=f"Task {n}",
        )
        for n in range(count)
    ]
    db.add_all(rows)
    db.commit()
    return [row.id for row in rows]


def test_two_processes_never_send_the_same_delivery(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    ids = _stage_many(db, bot, 6)
    seen: list[str] = []
    gate = threading.Barrier(2)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["x-taskly-delivery"])
        time.sleep(0.2)
        return httpx.Response(200)

    def process() -> None:
        http = httpx.Client(transport=httpx.MockTransport(handler))
        gate.wait()
        # Each takes a few at a time, as two API processes would.
        while webhooks.deliver_due(client=http, limit=2):
            pass

    threads = [threading.Thread(target=process) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(seen) == sorted(str(i) for i in ids)
    assert all(row.state == "delivered" for row in outbox(db, bot["id"]))


def test_a_claimed_delivery_is_left_alone_until_its_lease_runs_out(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    [delivery_id] = _stage_many(db, bot, 1)
    start = _now()
    # A process claims it and dies before it can send: only the lease is left.
    with Session(db.get_bind()) as session:
        row = session.get_one(WebhookDelivery, delivery_id)
        row.next_attempt_at = start + webhooks.LEASE
        session.add(row)
        session.commit()

    assert (
        webhooks.deliver_due(client=receiver.client(), now=start + timedelta(minutes=1))
        == 0
    )
    assert receiver.requests == []
    assert (
        webhooks.deliver_due(client=receiver.client(), now=start + webhooks.LEASE) == 1
    )
    assert len(receiver.requests) == 1
    # The interrupted attempt was never counted.
    assert _last(db, bot).attempts == 1


def test_the_schedule_resumes_in_a_new_process_from_what_the_table_holds(
    client: TestClient, db: Session
) -> None:
    _owner, bot, _task = _ready(client, db)
    start = _now()
    first = Receiver(status=500)
    webhooks.deliver_due(client=first.client(), now=start)

    # A restart keeps nothing in memory: a new process, with a new client, is
    # handed the same table and carries on where the old one stopped.
    second = Receiver(status=200)
    webhooks.deliver_due(client=second.client(), now=start + timedelta(minutes=1))

    assert len(first.requests) == 1
    assert len(second.requests) == 1
    assert (_last(db, bot).state, _last(db, bot).attempts) == ("delivered", 2)
    assert (
        first.requests[0].headers["x-taskly-delivery"]
        == second.requests[0].headers["x-taskly-delivery"]
    )


def test_the_loop_sends_what_a_commit_leaves_without_waiting_for_the_next_poll(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_webhook_bot(client, owner, project_ids=[project_id])
    receiver = Receiver()
    http = receiver.client()

    async def run() -> None:
        # A poll interval far longer than the test: only the wake-up on commit
        # can explain a prompt delivery.
        loop = asyncio.create_task(
            webhooks.drain_forever(client=http, poll_seconds=3600)
        )
        try:
            await asyncio.sleep(0.2)
            await asyncio.to_thread(
                create_task_record,
                client,
                owner,
                "Now",
                project_id=project_id,
                status="todo",
                assignee_id=bot["id"],
            )
            for _ in range(100):
                if receiver.requests:
                    break
                await asyncio.sleep(0.05)
        finally:
            loop.cancel()
            await asyncio.gather(loop, return_exceptions=True)

    asyncio.run(run())

    assert len(receiver.requests) == 1
    assert json.loads(receiver.requests[0].content)["task_title"] == "Now"
    assert _last(db, bot).state == "delivered"


def test_the_loop_finds_events_that_were_waiting_when_it_started(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    _stage_many(db, bot, 3)
    receiver = Receiver()
    http = receiver.client()

    async def run() -> None:
        loop = asyncio.create_task(
            webhooks.drain_forever(client=http, poll_seconds=0.05)
        )
        try:
            for _ in range(100):
                if len(receiver.requests) == 3:
                    break
                await asyncio.sleep(0.05)
        finally:
            loop.cancel()
            await asyncio.gather(loop, return_exceptions=True)

    asyncio.run(run())

    assert len(receiver.requests) == 3


def test_the_loop_does_not_run_in_the_test_suite_unless_a_test_starts_it() -> None:
    assert settings.WEBHOOK_DELIVERY_LOOP is False


def test_the_app_starts_the_loop_with_the_server_and_stops_it_with_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[str] = []

    async def drain() -> None:
        started.append("started")
        try:
            await asyncio.sleep(3600)
        finally:
            started.append("stopped")

    monkeypatch.setattr(settings, "WEBHOOK_DELIVERY_LOOP", True)
    monkeypatch.setattr(webhooks, "drain_forever", drain)

    with TestClient(app):
        time.sleep(0.2)
        assert started == ["started"]

    assert started == ["started", "stopped"]


# --- Test events (FR-11.12) -------------------------------------------------------


def test_a_test_event_is_sent_at_once_and_its_result_returned(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])

    r = client.post(f"{API}/bot-users/{bot['id']}/webhooks/task/test", headers=owner)

    assert r.status_code == 200, r.text
    result = r.json()
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["error"] is None
    assert result["event"] == "test"
    assert result["state"] == "delivered"
    assert isinstance(result["duration_ms"], int)
    [request] = receiver.requests
    body = json.loads(request.content)
    assert body["event"] == "test"
    assert body["task_id"] is None
    assert body["task_title"] is None
    assert body["bot_user_id"] == bot["id"]
    assert body["delivery_id"] == result["id"]
    headers = {
        "X-Taskly-Timestamp": request.headers["x-taskly-timestamp"],
        "X-Taskly-Signature": request.headers["x-taskly-signature"],
    }
    assert webhooks.verify_signature(bot["secret"], headers, request.content)


def test_a_failing_test_event_is_not_retried_and_still_answers_200(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    receiver.status = 500

    r = client.post(f"{API}/bot-users/{bot['id']}/webhooks/comment/test", headers=owner)

    assert r.status_code == 200
    result = r.json()
    assert (result["success"], result["status_code"], result["state"]) == (
        False,
        500,
        "failed",
    )
    assert result["error"] == "The receiver answered 500"
    assert result["next_attempt_at"] is None
    assert (
        webhooks.deliver_due(client=receiver.client(), now=_now() + timedelta(days=1))
        == 0
    )
    assert len(receiver.requests) == 1
    assert str(receiver.requests[0].url) == "https://hooks.example.com/comment"


def test_a_test_event_that_cannot_connect_returns_the_error(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    receiver.fail_with = httpx.ConnectError("Connection refused")

    result = client.post(
        f"{API}/bot-users/{bot['id']}/webhooks/task/test", headers=owner
    ).json()

    assert result["success"] is False
    assert result["status_code"] is None
    assert result["error"] == "ConnectError: Connection refused"


def test_a_test_event_to_a_name_that_resolves_privately_is_refused(
    client: TestClient, db: Session, receiver: Receiver, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    monkeypatch.setattr(outbound, "resolve_host", lambda _host: ["192.168.1.9"])

    result = client.post(
        f"{API}/bot-users/{bot['id']}/webhooks/task/test", headers=owner
    ).json()

    assert result["success"] is False
    assert "192.168.1.9" in result["error"]
    assert receiver.requests == []


# --- The last delivery of each webhook (FR-11.11, FR-11.14) -----------------------


def _bot_record(client: TestClient, owner: Headers, bot_id: str) -> dict[str, Any]:
    record: dict[str, Any] = client.get(
        f"{API}/bot-users/{bot_id}", headers=owner
    ).json()
    return record


def test_each_webhook_reports_its_last_delivery(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, task = _ready(client, db)
    assert (
        _bot_record(client, owner, bot["id"])["webhooks"]["task"]["last_delivery"]
        is None
    )
    client.post(
        f"{API}/tasks/{task['id']}/comments/", headers=owner, json={"body": "Hi"}
    )
    receiver.status = 500

    webhooks.deliver_due(client=receiver.client())

    shown = _bot_record(client, owner, bot["id"])["webhooks"]
    task_delivery = shown["task"]["last_delivery"]
    assert task_delivery["success"] is False
    assert task_delivery["status_code"] == 500
    assert task_delivery["error"] == "The receiver answered 500"
    assert task_delivery["event"] == "task.ready"
    assert task_delivery["state"] == "pending"
    assert task_delivery["attempts"] == 1
    assert task_delivery["next_attempt_at"] is not None
    assert task_delivery["attempted_at"] is not None
    assert task_delivery["duration_ms"] >= 0
    assert shown["comment"]["last_delivery"]["event"] == "comment.added"

    receiver.status = 200
    webhooks.deliver_due(client=receiver.client(), now=_now() + timedelta(minutes=1))

    shown = _bot_record(client, owner, bot["id"])["webhooks"]
    assert shown["task"]["last_delivery"]["success"] is True
    assert shown["task"]["last_delivery"]["status_code"] == 200
    assert shown["task"]["last_delivery"]["state"] == "delivered"
    assert shown["task"]["last_delivery"]["next_attempt_at"] is None
    assert shown["task"]["last_delivery"]["attempts"] == 2


def test_the_list_of_bot_users_carries_each_ones_last_deliveries(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    quiet = create_webhook_bot(client, owner, project_ids=[], name="Quiet")
    webhooks.deliver_due(client=receiver.client())

    listed = client.get(f"{API}/bot-users/", headers=owner).json()["data"]

    by_id = {b["id"]: b for b in listed}
    assert by_id[bot["id"]]["webhooks"]["task"]["last_delivery"]["success"] is True
    assert by_id[quiet["id"]]["webhooks"]["task"]["last_delivery"] is None


def test_a_webhook_is_never_disabled_however_many_deliveries_fail(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    receiver.status = 500
    clock = _now()
    for _ in range(7):
        webhooks.deliver_due(client=receiver.client(), now=clock)
        clock += timedelta(hours=2)
    assert _last(db, bot).state == "failed"

    shown = _bot_record(client, owner, bot["id"])["webhooks"]["task"]
    assert shown["url"] == "https://hooks.example.com/task"
    # A new event is sent as usual.
    receiver.status = 200
    set_webhook(client, owner, bot["id"], "task", "https://hooks.example.com/task")
    create_task_record(
        client,
        owner,
        "Next",
        project_id=create_project(client, owner),
        status="todo",
        assignee_id=bot["id"],
    )
    webhooks.deliver_due(client=receiver.client(), now=clock)
    assert receiver.requests[-1].content != b""
    assert json.loads(receiver.requests[-1].content)["task_title"] == "Next"


def test_only_the_last_finished_delivery_of_a_webhook_is_kept(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    project_id = create_project(client, owner)
    webhooks.deliver_due(client=receiver.client())
    for n in range(3):
        create_task_record(
            client,
            owner,
            f"More {n}",
            project_id=project_id,
            status="todo",
            assignee_id=bot["id"],
        )
        webhooks.deliver_due(client=receiver.client())

    rows = outbox(db, bot["id"])
    assert len(rows) == 1
    assert rows[0].task_title == "More 2"
    assert rows[0].state == DeliveryState.DELIVERED.value
    assert not pending(db, bot["id"])


def test_deliveries_are_not_in_the_activity_log(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db)
    before = client.get(f"{API}/activity-log/", headers=owner).json()["count"]

    webhooks.deliver_due(client=receiver.client())
    client.post(f"{API}/bot-users/{bot['id']}/webhooks/task/test", headers=owner)

    assert client.get(f"{API}/activity-log/", headers=owner).json()["count"] == before


def test_a_test_events_result_replaces_an_older_failure_as_the_last_delivery(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    owner, bot, _task = _ready(client, db, comment=False)
    receiver.status = 500
    webhooks.deliver_due(client=receiver.client())
    receiver.status = 200

    client.post(f"{API}/bot-users/{bot['id']}/webhooks/task/test", headers=owner)

    last = _bot_record(client, owner, bot["id"])["webhooks"]["task"]["last_delivery"]
    assert last["event"] == "test"
    assert last["success"] is True
    # The task event is still waiting for its retry, and is still sent.
    assert len(pending(db, bot["id"])) == 1


def test_permissions_play_no_part_in_a_delivery(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    # Deliveries continue whether or not the bot user holds a valid token
    # (FR-11.13): it has none here, and the event still goes out.
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_webhook_bot(client, owner, project_ids=[project_id], permissions={})
    create_task_record(
        client,
        owner,
        "T",
        project_id=project_id,
        status="todo",
        assignee_id=bot["id"],
    )
    webhooks.deliver_due(client=receiver.client())

    assert len(receiver.requests) == 1
