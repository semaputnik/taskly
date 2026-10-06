"""
Webhook delivery: the secret, the signature and the loop that drains the outbox
(F-11, ADR-0009).

Events are written by `app.webhook_events`, in the transaction of the change
that caused them. Here they are sent. There is no separate worker: every API
process runs `drain_forever` from its lifespan, and all of a delivery's state
lives in its row, so a restart loses nothing.

A process claims due rows with `SELECT ... FOR UPDATE SKIP LOCKED` and moves
their `next_attempt_at` out by a lease before it lets go of the lock. Another
process skips what is claimed or leased, so no delivery is sent twice at once;
and a process that dies mid-attempt only leaves its rows to be tried again once
the lease runs out.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.outbound import GuardedTransport, Refusal, check_url
from app.models import (
    BotUser,
    DeliveryState,
    WebhookDelivery,
    WebhookDeliveryPublic,
    WebhookEventType,
    WebhookKind,
)

logger = logging.getLogger(__name__)

# After a failed attempt n (counting from 1), the next is this long after it;
# after the last one the delivery is failed (FR-11.10). Six attempts in all:
# at once, then after 1, 5, 15, 60 and 60 minutes.
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
    timedelta(minutes=60),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
# How long the receiver has to answer with a 2xx (FR-11.10).
TIMEOUT_SECONDS = 10.0
# How long a claimed delivery is held by the process that took it. Longer than
# an attempt can take, short enough that a crash is only a short delay.
LEASE = timedelta(minutes=2)
# How many due deliveries one pass claims, and how many it sends at a time.
BATCH_SIZE = 20
WORKERS = 8

SECRET_PREFIX = "whsec_"
USER_AGENT = "Taskly-Webhooks/1"

# --- The secret --------------------------------------------------------------


def generate_secret() -> str:
    """A new webhook secret (FR-11.9): long, random, and shown only once."""
    return SECRET_PREFIX + secrets.token_urlsafe(32)


def _fernet() -> Fernet:
    return security.fernet_for(settings.WEBHOOK_SECRET_KEY, b"taskly webhook secret")


def encrypt_secret(secret: str) -> str:
    """
    The secret as it is stored: encrypted under a key derived from
    `WEBHOOK_SECRET_KEY`, never in the clear.

    It cannot be a digest like a bot token's: a token is only ever compared,
    but a webhook is signed with the secret, so Taskly has to be able to get it
    back. The key is its own setting, not `SECRET_KEY`, so rotating that does
    not touch these. Changing `WEBHOOK_SECRET_KEY` makes stored secrets
    unreadable; the owner regenerates them, and deliveries say so until then.
    """
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except InvalidToken as error:
        raise ValueError(
            "The webhook secret cannot be read, probably because "
            "WEBHOOK_SECRET_KEY changed. Regenerate the secret."
        ) from error


# --- The delivery contract ----------------------------------------------------

DELIVERY_CONTRACT = """\
## Webhook deliveries

A bot user may have two webhooks, set by its owner in the web interface (never
through the bot user's own token): one for tasks that become ready for it, one
for comments on tasks it is involved in. Taskly calls the URL with a POST.

**Events.** `task.ready`: a task came to be in To do with the bot user as its
assignee, by a change other than the bot user's own. `comment.added`: someone
other than the bot user added a comment to a task it is assignee or reporter
of, or has commented on. `test`: sent by the owner from the bot user's
settings.

**Body.** JSON, and nothing beyond these fields; read the rest through the
REST API with the bot user's token.

```json
{
  "event": "task.ready",
  "delivery_id": "0f0d4a3e-6f45-4a7b-9a42-5d4b1f0f8a11",
  "occurred_at": "2026-10-06T09:30:00+00:00",
  "bot_user_id": "5b0c1d52-0f5b-4c61-8d55-0d3e8f6ac1d2",
  "task_id": "8d1d6f6e-3a0b-4a7b-b4c1-2f6f0c7d9e10",
  "task_title": "Triage the inbox",
  "comment_id": null
}
```

`comment_id` is present for `comment.added` only. `task_id` and `task_title`
are null for `test`.

**Headers.** `X-Taskly-Event`, `X-Taskly-Delivery` (the delivery id),
`X-Taskly-Timestamp` (Unix seconds, fresh on every attempt) and
`X-Taskly-Signature`: `sha256=` followed by the hex HMAC-SHA256, under the
webhook secret, of the timestamp, a dot and the raw request body.

**Verifying.** Check the signature against the raw bytes received, and reject
a timestamp that is too old, so a captured request cannot be replayed:

```python
import hashlib
import hmac
import time


def verify(secret: str, headers, body: bytes, tolerance_seconds: int = 300) -> bool:
    timestamp = headers["X-Taskly-Timestamp"]
    if abs(time.time() - int(timestamp)) > tolerance_seconds:
        return False
    message = timestamp.encode() + b"." + body
    expected = "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, headers["X-Taskly-Signature"])
```

**Secret.** One per bot user, generated when its first webhook is set and shown
once, in that response. The owner can regenerate it; the new one applies from
the next delivery.

**Answering and retrying.** Answer with any 2xx within 10 seconds. Anything
else (another status, no answer, a refused connection) is a failed attempt:
Taskly tries again after 1, 5, 15, 60 and 60 minutes, and then gives up on
that delivery. Redirects are not followed. Deliveries are not ordered, and one
may arrive more than once, so treat `delivery_id` as the key.

**Addresses.** An http or https URL. One that resolves to loopback or a
private range is refused, when it is set and again on every delivery, unless
the installation sets `OUTBOUND_ALLOW_PRIVATE_ADDRESSES`.
"""


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """
    The signature header's value: HMAC-SHA256 under the secret, over the
    timestamp, a dot and the body exactly as sent (FR-11.9).
    """
    message = timestamp.encode() + b"." + body
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(
    secret: str,
    headers: Mapping[str, str],
    body: bytes,
    *,
    tolerance_seconds: int = 300,
    now: float | None = None,
) -> bool:
    """
    The reference verifier a receiver can copy: true when the request was
    signed with `secret` and its timestamp is within `tolerance_seconds` of
    now (which stops a captured request being replayed later).
    """
    try:
        timestamp = headers["X-Taskly-Timestamp"]
        received = headers["X-Taskly-Signature"]
        age = abs((time.time() if now is None else now) - int(timestamp))
    except KeyError, ValueError:
        return False
    if age > tolerance_seconds:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), received)


def body_of(delivery: WebhookDelivery) -> bytes:
    """
    The JSON a delivery sends (FR-11.8), and nothing more: the receiver reads
    the rest through the REST API, within its scope.
    """
    payload: dict[str, Any] = {
        "event": delivery.event,
        "delivery_id": str(delivery.id),
        "occurred_at": delivery.occurred_at.astimezone(UTC).isoformat(),
        "bot_user_id": str(delivery.bot_user_id),
        "task_id": str(delivery.task_id) if delivery.task_id else None,
        "task_title": delivery.task_title,
    }
    if delivery.event == WebhookEventType.COMMENT_ADDED.value:
        payload["comment_id"] = str(delivery.comment_id)
    return json.dumps(payload, separators=(",", ":")).encode()


def webhook_url(bot: BotUser, kind: str) -> str | None:
    return (
        bot.task_webhook_url
        if kind == WebhookKind.TASK.value
        else bot.comment_webhook_url
    )


# --- Sending ------------------------------------------------------------------


@dataclass(frozen=True)
class _Job:
    """Everything one attempt needs, taken out of the session so no database
    connection is held while the receiver takes its time."""

    id: uuid.UUID
    url: str
    secret: str
    body: bytes
    event: str


@dataclass(frozen=True)
class Outcome:
    status_code: int | None
    error: str | None
    duration_ms: int

    @property
    def success(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300


def make_client() -> httpx.Client:
    """
    The client deliveries go out through. A redirect is not followed: it would
    send a signed request somewhere the owner never named, past the address
    check. The environment's proxy settings are not read, for the same reason,
    and the transport connects only to the address it checked (FR-11.3).
    """
    return httpx.Client(
        transport=GuardedTransport(), follow_redirects=False, trust_env=False
    )


def _post(client: httpx.Client, job: _Job, *, now: datetime) -> Outcome:
    timestamp = str(int(now.timestamp()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-Taskly-Event": job.event,
        "X-Taskly-Delivery": str(job.id),
        "X-Taskly-Timestamp": timestamp,
        "X-Taskly-Signature": sign(job.secret, timestamp, job.body),
    }
    started = time.monotonic()

    def took() -> int:
        return int((time.monotonic() - started) * 1000)

    try:
        # Checked on every attempt, not only when the URL was set: a name can
        # come to resolve somewhere private later (FR-11.3).
        check_url(job.url)
    except Refusal as refusal:
        return Outcome(None, f"Refused: {refusal.message}"[:500], took())
    try:
        response = client.post(
            job.url, content=job.body, headers=headers, timeout=TIMEOUT_SECONDS
        )
    except httpx.TimeoutException:
        return Outcome(None, f"No answer within {TIMEOUT_SECONDS:g} seconds", took())
    except Refusal as refusal:
        # The transport's own check, made on the address it is about to use.
        return Outcome(None, f"Refused: {refusal.message}"[:500], took())
    except Exception as error:
        # Whatever went wrong with this one request, it is a failed attempt: an
        # exception that got out would leave the delivery unrecorded and
        # claimed again for ever (an invalid URL is `httpx.InvalidURL`, not an
        # `httpx.HTTPError`).
        return Outcome(None, f"{type(error).__name__}: {error}"[:500], took())
    answer_error = (
        None
        if 200 <= response.status_code < 300
        else f"The receiver answered {response.status_code}"
    )
    return Outcome(response.status_code, answer_error, took())


def _job_for(session: Session, delivery: WebhookDelivery) -> _Job | str:
    """
    What to send for a delivery, or a reason it cannot be: a string is an error
    that counts as a failed attempt.
    """
    bot = session.get(BotUser, delivery.bot_user_id)
    url = webhook_url(bot, delivery.webhook) if bot else None
    if bot is None or url is None:
        raise LookupError
    if bot.webhook_secret_encrypted is None:
        return "The bot user has no webhook secret. Regenerate it."
    try:
        secret = decrypt_secret(bot.webhook_secret_encrypted)
    except ValueError as error:
        return str(error)
    return _Job(
        id=delivery.id,
        url=url,
        secret=secret,
        body=body_of(delivery),
        event=delivery.event,
    )


def _record(
    session: Session,
    delivery: WebhookDelivery,
    outcome: Outcome,
    *,
    now: datetime,
    retry: bool,
) -> None:
    """Write down an attempt and decide what happens to the delivery next."""
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.last_status_code = outcome.status_code
    delivery.last_error = outcome.error
    delivery.last_duration_ms = outcome.duration_ms
    if outcome.success:
        delivery.state = DeliveryState.DELIVERED.value
    elif not retry or delivery.attempts >= MAX_ATTEMPTS:
        delivery.state = DeliveryState.FAILED.value
    else:
        delivery.state = DeliveryState.PENDING.value
        delivery.next_attempt_at = now + RETRY_DELAYS[delivery.attempts - 1]
    session.add(delivery)
    if delivery.state != DeliveryState.PENDING.value:
        # What the owner is shown is the last delivery of each webhook
        # (FR-11.11), and nothing is logged beyond it (FR-11.14): the finished
        # delivery this one replaces is dropped.
        session.exec(
            delete(WebhookDelivery).where(
                col(WebhookDelivery.bot_user_id) == delivery.bot_user_id,
                col(WebhookDelivery.webhook) == delivery.webhook,
                col(WebhookDelivery.id) != delivery.id,
                col(WebhookDelivery.state) != DeliveryState.PENDING.value,
                col(WebhookDelivery.last_attempt_at) <= now,
            )
        )


def _attempt(delivery_id: uuid.UUID, client: httpx.Client, now: datetime) -> None:
    """One attempt at a claimed delivery, from reading the row to recording it."""
    with Session(engine) as session:
        delivery = session.get(WebhookDelivery, delivery_id)
        if delivery is None or delivery.state != DeliveryState.PENDING.value:
            return
        try:
            job = _job_for(session, delivery)
        except LookupError:
            # The bot user is gone or the webhook was cleared since the event:
            # there is nowhere left to send it (FR-11.13).
            session.delete(delivery)
            session.commit()
            return
    if isinstance(job, str):
        outcome = Outcome(None, job, 0)
    else:
        outcome = _post(client, job, now=now)
    with Session(engine) as session:
        delivery = session.get(WebhookDelivery, delivery_id)
        if delivery is None:
            # Discarded while it was being sent: its bot user was deleted.
            return
        _record(session, delivery, outcome, now=now, retry=True)
        session.commit()


def claim_due(
    # Either outbox table: they share these columns, which no common base
    # class names.
    model: Any,
    *,
    now: datetime,
    limit: int,
) -> list[uuid.UUID]:
    """
    Claim up to `limit` pending rows of an outbox table that are due as of
    `now`: lock them (skipping what another process holds), push their
    `next_attempt_at` out by the lease and commit, so no other process sends
    them while this one does. Webhook deliveries and Paperless hand-overs wait
    in tables of the same shape and are claimed the same way.
    """
    with Session(engine) as session:
        due = session.exec(
            select(model)
            .where(
                col(model.state) == DeliveryState.PENDING.value,
                col(model.next_attempt_at) <= now,
            )
            .order_by(col(model.next_attempt_at))
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        ids = [row.id for row in due]
        for row in due:
            row.next_attempt_at = now + LEASE
            session.add(row)
        session.commit()
    return ids


def deliver_due(
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    limit: int = BATCH_SIZE,
) -> int:
    """
    Claim the deliveries that are due as of `now` and attempt each once.
    Returns how many were claimed.

    Safe to call from any number of processes at once. `client` and `now`
    exist for tests, which hand it a mock transport and step through the
    retry schedule without waiting.
    """
    now = now or datetime.now(UTC)
    ids = claim_due(WebhookDelivery, now=now, limit=limit)
    if not ids:
        return 0
    own_client = client is None
    client = client or make_client()
    try:
        if len(ids) == 1:
            _attempt(ids[0], client, now)
        else:
            with ThreadPoolExecutor(max_workers=min(WORKERS, len(ids))) as pool:
                # Consumed, so an exception in a worker is raised here.
                list(pool.map(lambda i: _attempt(i, client, now), ids))
    finally:
        if own_client:
            client.close()
    return len(ids)


def send_test(
    session: Session, bot: BotUser, kind: WebhookKind, client: httpx.Client
) -> WebhookDelivery:
    """
    Send a test event to one of the bot user's webhooks at once, without
    retries, and record it as its last delivery (FR-11.12).
    """
    now = datetime.now(UTC)
    delivery = WebhookDelivery(
        bot_user_id=bot.id,
        webhook=kind.value,
        event=WebhookEventType.TEST.value,
        occurred_at=now,
        next_attempt_at=now,
    )
    url = webhook_url(bot, kind.value)
    assert url is not None
    stored_secret = bot.webhook_secret_encrypted
    # Everything the request needs is in hand: end the transaction, so no
    # connection is held while the receiver takes up to ten seconds to answer.
    session.commit()
    if stored_secret is None:
        outcome = Outcome(None, "The bot user has no webhook secret. Regenerate it.", 0)
    else:
        try:
            secret = decrypt_secret(stored_secret)
        except ValueError as error:
            outcome = Outcome(None, str(error), 0)
        else:
            job = _Job(delivery.id, url, secret, body_of(delivery), delivery.event)
            outcome = _post(client, job, now=now)
    _record(session, delivery, outcome, now=now, retry=False)
    session.commit()
    session.refresh(delivery)
    return delivery


# --- What the owner is shown --------------------------------------------------


def delivery_public(delivery: WebhookDelivery) -> WebhookDeliveryPublic:
    state = DeliveryState(delivery.state)
    assert delivery.last_attempt_at is not None
    return WebhookDeliveryPublic(
        id=delivery.id,
        event=WebhookEventType(delivery.event),
        attempted_at=delivery.last_attempt_at,
        success=state is DeliveryState.DELIVERED,
        state=state,
        attempts=delivery.attempts,
        status_code=delivery.last_status_code,
        error=delivery.last_error,
        duration_ms=delivery.last_duration_ms,
        next_attempt_at=(
            delivery.next_attempt_at if state is DeliveryState.PENDING else None
        ),
    )


def last_deliveries(
    session: Session, bot_ids: list[uuid.UUID]
) -> dict[tuple[uuid.UUID, str], WebhookDeliveryPublic]:
    """
    The most recent attempted delivery of each (bot user, webhook), in one
    query (FR-11.11). A delivery nobody has attempted yet is not one.
    """
    if not bot_ids:
        return {}
    rows = session.exec(
        select(WebhookDelivery)
        .where(
            col(WebhookDelivery.bot_user_id).in_(bot_ids),
            col(WebhookDelivery.last_attempt_at).is_not(None),
        )
        .order_by(col(WebhookDelivery.last_attempt_at).desc())
    ).all()
    latest: dict[tuple[uuid.UUID, str], WebhookDeliveryPublic] = {}
    for row in rows:
        latest.setdefault((row.bot_user_id, row.webhook), delivery_public(row))
    return latest


# --- The loop -----------------------------------------------------------------

_loop: asyncio.AbstractEventLoop | None = None
_wakeup: asyncio.Event | None = None


def wake() -> None:
    """Tell this process's loop that a delivery is due now. Safe from any thread."""
    if _loop is not None and _wakeup is not None:
        try:
            _loop.call_soon_threadsafe(_wakeup.set)
        except RuntimeError:
            # The loop is shutting down; the change this follows is already
            # committed, and its delivery waits for the next process to run.
            pass


def _drain_once(
    client: httpx.Client | None, paperless_client: httpx.Client | None
) -> int:
    """One pass over every outbox: webhook deliveries, then Paperless
    hand-overs. Returns how many rows were claimed in all."""
    # Imported here: `app.paperless` builds on this module's claim and retry
    # rules, so it cannot be imported by it at the top.
    from app import paperless

    claimed = 0
    # One outbox failing must not starve the other.
    try:
        claimed += deliver_due(client=client)
    except Exception:
        logger.exception("Webhook delivery pass failed")
    try:
        claimed += paperless.hand_over_due(client=paperless_client)
    except Exception:
        logger.exception("Paperless hand-over pass failed")
    return claimed


async def drain_forever(
    *,
    client: httpx.Client | None = None,
    paperless_client: httpx.Client | None = None,
    poll_seconds: float | None = None,
) -> None:
    """
    Drain the outboxes until cancelled: look for due deliveries and Paperless
    hand-overs (ADR-0010 shares the loop the webhooks brought), send them, then
    wait for the next poll or for a commit in this process to wake the loop.

    A failure inside a pass is logged and the loop carries on; a pass that
    claims a full batch goes round again at once.
    """
    global _loop, _wakeup
    interval = settings.WEBHOOK_POLL_SECONDS if poll_seconds is None else poll_seconds
    wakeup = asyncio.Event()
    _loop, _wakeup = asyncio.get_running_loop(), wakeup
    try:
        while True:
            wakeup.clear()
            try:
                claimed = await asyncio.to_thread(_drain_once, client, paperless_client)
            except Exception:
                logger.exception("Outbox pass failed")
                claimed = 0
            if claimed >= BATCH_SIZE:
                continue
            try:
                await asyncio.wait_for(wakeup.wait(), timeout=interval)
            except TimeoutError:
                pass
    finally:
        _loop = _wakeup = None
