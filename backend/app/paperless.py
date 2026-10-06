"""
Paperless-ngx: the connection, the API calls Taskly makes, and the hand-over of
a PDF (F-04, ADR-0010).

A PDF attached by a user with a connection is accepted at once and kept in
Taskly's storage. A row in `paperlesshandover` (the sibling of the webhook
outbox, drained by the same loop on the same retry schedule) takes it through
three stages: SEND (look for the document by checksum, otherwise post the file),
POLL (wait for Paperless to consume it, by the task id it gave back) and
FINISH (tag the document, note the task on it, link the attachment and release
Taskly's copy). All of the state is in the row, so a restart only delays it.

Taskly never deletes from Paperless, and nothing here does.
"""

import hashlib
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from app import webhooks
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.outbound import Refusal, check_url
from app.core.storage import AttachmentStorage, default_storage
from app.models import (
    Attachment,
    AttachmentLocation,
    AttachmentPublic,
    DeliveryState,
    PaperlessConnection,
    PaperlessHandover,
    PaperlessHandoverPublic,
    PaperlessHandoverStage,
    Task,
)

logger = logging.getLogger(__name__)

# What a PDF starts with. A file is a PDF by this, not by its name or declared
# type (FR-04.5).
PDF_MAGIC = b"%PDF-"
# The tag every document Taskly hands over carries, created on first use
# (FR-04.9).
TAG_NAME = "Taskly"
# One request to Paperless. Longer than a webhook's ten seconds: a post carries
# the whole file.
REQUEST_TIMEOUT = 30.0
# How often Paperless is asked whether it has consumed a file, and how long it
# gets before the wait counts as a failed attempt (which is retried on the
# webhook schedule, FR-04.6).
POLL_INTERVAL = timedelta(seconds=10)
POLL_DEADLINE = timedelta(minutes=15)

NOT_CONNECTED_CODE = "paperless_not_connected"
UNREACHABLE_CODE = "paperless_unreachable"
MISSING_CODE = "paperless_document_missing"


def is_pdf(data: bytes) -> bool:
    return data.startswith(PDF_MAGIC)


# --- The token ------------------------------------------------------------------


def _fernet() -> Fernet:
    return security.fernet_for(settings.PAPERLESS_TOKEN_KEY, b"taskly paperless token")


def encrypt_token(token: str) -> str:
    """
    The token as it is stored: encrypted under a key derived from
    `PAPERLESS_TOKEN_KEY`, never in the clear. Taskly has to send it back to
    Paperless, so it cannot be a digest; it is never returned by the API.
    """
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except InvalidToken as error:
        raise PaperlessError(
            "The Paperless token cannot be read, probably because "
            "PAPERLESS_TOKEN_KEY changed. Enter the token again in Settings."
        ) from error


# --- Talking to Paperless -------------------------------------------------------


class PaperlessError(Exception):
    """
    Something Paperless did, or did not do. The message is for the person who
    attached the file or is downloading it; `code` and `status` are what the
    REST API answers with.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = UNREACHABLE_CODE,
        status: int = 502,
        missing: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        # Paperless answered 404: what was asked for is not there.
        self.missing = missing


def normalise_url(url: str) -> str:
    return url.strip().rstrip("/")


def document_url(base_url: str, document_id: int) -> str:
    """Where a person opens the document in Paperless's own interface."""
    return f"{normalise_url(base_url)}/documents/{document_id}/details"


def task_url(task_id: uuid.UUID) -> str:
    """Where a person opens the task in Taskly, as the note on the document says."""
    return f"{settings.FRONTEND_HOST.rstrip('/')}/tasks?task={task_id}"


def note_text(title: str, task_id: uuid.UUID) -> str:
    return f"Attached to the Taskly task “{title}”: {task_url(task_id)}"


@dataclass(frozen=True)
class ConsumptionTask:
    """What Paperless says about the consumption of a file it was sent."""

    status: str
    result: str | None
    document_id: int | None


class PaperlessApi:
    """
    The few calls Taskly makes to one user's Paperless-ngx, over a client whose
    transport only connects to addresses the installation allows (FR-04.4).
    Every failure is a `PaperlessError` with a message that says what happened.
    """

    def __init__(self, client: httpx.Client, url: str, token: str) -> None:
        self._client = client
        self.url = normalise_url(url)
        self._headers = {
            "Authorization": f"Token {token}",
            "Accept": "application/json",
        }
        self._checked = False

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self._checked:
            # The readable refusal, once per use: a name can come to resolve
            # somewhere private after the address was set. The transport holds
            # the line on every connection.
            try:
                check_url(
                    self.url, what="Paperless address", code_prefix="paperless_url"
                )
            except Refusal as refusal:
                raise PaperlessError(f"Refused: {refusal.message}") from refusal
            self._checked = True
        try:
            response = self._client.request(
                method,
                f"{self.url}{path}",
                headers=self._headers,
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )
        except httpx.TimeoutException as error:
            raise PaperlessError(
                f"Paperless did not answer within {REQUEST_TIMEOUT:g} seconds"
            ) from error
        except Refusal as refusal:
            raise PaperlessError(f"Refused: {refusal.message}") from refusal
        except Exception as error:
            # Whatever went wrong with this one request is a failed attempt, an
            # invalid address (`httpx.InvalidURL`) included.
            raise PaperlessError(
                f"Paperless could not be reached ({type(error).__name__}: {error})"[
                    :500
                ]
            ) from error
        if response.is_success:
            return response
        if response.status_code in (401, 403):
            raise PaperlessError(
                f"Paperless refused the token (it answered {response.status_code})"
            )
        raise PaperlessError(
            f"Paperless answered {response.status_code}{_detail(response)}",
            missing=response.status_code == 404,
        )

    def check(self) -> None:
        """Raise unless the address answers and the token is accepted."""
        self._request("GET", "/api/documents/", params={"page_size": 1})

    def find_by_checksum(self, checksum: str) -> int | None:
        """The document Paperless holds for a file with this MD5, if any. It is
        the checksum of the original file, which is what Taskly sends."""
        answer = self._request(
            "GET", "/api/documents/", params={"checksum__iexact": checksum}
        ).json()
        results = answer.get("results", []) if isinstance(answer, dict) else answer
        return int(results[0]["id"]) if results else None

    def ensure_tag(self) -> int:
        """The id of the `Taskly` tag, creating it when Paperless has none."""
        found = self._find_tag()
        if found is not None:
            return found
        try:
            created = self._request("POST", "/api/tags/", json={"name": TAG_NAME})
        except PaperlessError:
            # Someone made it between the look and the post (names are unique).
            found = self._find_tag()
            if found is None:
                raise
            return found
        return int(created.json()["id"])

    def _find_tag(self) -> int | None:
        answer = self._request(
            "GET", "/api/tags/", params={"name__iexact": TAG_NAME}
        ).json()
        results = answer.get("results", []) if isinstance(answer, dict) else answer
        return int(results[0]["id"]) if results else None

    def post_document(self, filename: str, data: bytes, tag_id: int) -> str:
        """Send a file to be consumed, titled with its name and tagged; the
        answer is the id of the consumption task."""
        answer = self._request(
            "POST",
            "/api/documents/post_document/",
            files={"document": (filename, data, "application/pdf")},
            data={"title": filename, "tags": [str(tag_id)]},
        ).json()
        if not isinstance(answer, str) or not answer:
            raise PaperlessError("Paperless did not say how it would process the file")
        return answer

    def consumption(self, task_id: str) -> ConsumptionTask | None:
        """How the consumption of a file is going; None while Paperless has not
        registered the task."""
        answer = self._request("GET", "/api/tasks/", params={"task_id": task_id}).json()
        rows = answer.get("results", []) if isinstance(answer, dict) else answer
        if not rows:
            return None
        row = rows[0]
        result = row.get("result")
        related = row.get("related_document")
        if related is None and isinstance(result, str):
            # Older Paperless puts it in the message only.
            match = re.search(r"document id (\d+)", result)
            related = match.group(1) if match else None
        return ConsumptionTask(
            status=str(row.get("status", "")).upper(),
            result=result if isinstance(result, str) else None,
            document_id=int(related) if related is not None else None,
        )

    def ensure_document_tag(self, document_id: int, tag_id: int) -> None:
        document = self._request("GET", f"/api/documents/{document_id}/").json()
        tags = [int(tag) for tag in document.get("tags", [])]
        if tag_id not in tags:
            self._request(
                "PATCH",
                f"/api/documents/{document_id}/",
                json={"tags": [*tags, tag_id]},
            )

    def ensure_note(self, document_id: int, note: str, *, link: str) -> None:
        """Add the note unless the document already has one for this task, so a
        retry or a second attachment of the same task adds nothing."""
        answer = self._request("GET", f"/api/documents/{document_id}/notes/").json()
        notes = answer.get("results", []) if isinstance(answer, dict) else answer
        if any(link in str(entry.get("note", "")) for entry in notes):
            return
        self._request(
            "POST", f"/api/documents/{document_id}/notes/", json={"note": note}
        )

    def download_original(self, document_id: int) -> bytes:
        """The file as it was attached, not Paperless's archived copy
        (FR-04.10)."""
        return self._request(
            "GET",
            f"/api/documents/{document_id}/download/",
            params={"original": "true"},
        ).content


def _detail(response: httpx.Response) -> str:
    """What Paperless said, when it said it in the usual `detail` field."""
    try:
        detail = response.json().get("detail")
    except Exception:
        return ""
    return f": {detail}"[:200] if isinstance(detail, str) and detail else ""


# --- The connection -------------------------------------------------------------


def get_connection(session: Session, user_id: uuid.UUID) -> PaperlessConnection | None:
    return session.get(PaperlessConnection, user_id)


def api_for(connection: PaperlessConnection, client: httpx.Client) -> PaperlessApi:
    return PaperlessApi(
        client, connection.url, decrypt_token(connection.token_encrypted)
    )


def documents_kept(session: Session, user_id: uuid.UUID) -> int:
    """How many of the user's attachments are kept in Paperless."""
    return (
        session.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.owner_id == user_id,
                col(Attachment.paperless_document_id).is_not(None),
            )
        )
        or 0
    )


def disconnect(session: Session, user_id: uuid.UUID) -> int:
    """
    End the user's connection and return how many attachments are now out of
    reach (FR-04.8). Nothing in Paperless is touched, and attachments kept there
    stay as they are. Hand-overs still waiting are dropped: those files are
    still in Taskly and stay there.
    """
    kept = documents_kept(session, user_id)
    mine = select(col(Attachment.id)).where(Attachment.owner_id == user_id)
    session.exec(
        delete(PaperlessHandover).where(col(PaperlessHandover.attachment_id).in_(mine))
    )
    connection = session.get(PaperlessConnection, user_id)
    if connection is not None:
        session.delete(connection)
    session.commit()
    return kept


def restart_handovers(session: Session, user_id: uuid.UUID) -> None:
    """
    The connection was changed: a hand-over still waiting starts again from the
    top, because the consumption it was waiting for happened (if at all) on
    whatever the connection pointed at before. Failed ones are left for the
    owner to send again.
    """
    mine = select(col(Attachment.id)).where(Attachment.owner_id == user_id)
    handovers = session.exec(
        select(PaperlessHandover).where(
            col(PaperlessHandover.attachment_id).in_(mine),
            col(PaperlessHandover.state) == DeliveryState.PENDING.value,
        )
    ).all()
    for handover in handovers:
        handover.stage = PaperlessHandoverStage.SEND.value
        handover.paperless_task_id = None
        handover.paperless_document_id = None
        handover.sent_at = None
        handover.next_attempt_at = datetime.now(UTC)
        session.add(handover)


# --- What the REST API shows ----------------------------------------------------


def attachments_public(
    session: Session, attachments: list[Attachment]
) -> list[AttachmentPublic]:
    """
    Attachments as the REST API shows them: where each is kept, the document
    link for one kept in Paperless, and the state of a hand-over still under way
    or failed (FR-04.11).
    """
    ids = [attachment.id for attachment in attachments]
    handovers = {
        handover.attachment_id: handover
        for handover in session.exec(
            select(PaperlessHandover).where(
                col(PaperlessHandover.attachment_id).in_(ids)
            )
        )
    }
    owners = {attachment.owner_id for attachment in attachments}
    urls = {
        connection.user_id: connection.url
        for connection in session.exec(
            select(PaperlessConnection).where(
                col(PaperlessConnection.user_id).in_(owners)
            )
        )
    }
    shown: list[AttachmentPublic] = []
    for attachment in attachments:
        public = AttachmentPublic.model_validate(attachment)
        document_id = attachment.paperless_document_id
        if document_id is not None:
            public.kept_in = AttachmentLocation.PAPERLESS
            base = urls.get(attachment.owner_id)
            public.paperless_url = document_url(base, document_id) if base else None
        handover = handovers.get(attachment.id)
        if handover is not None:
            public.paperless_handover = PaperlessHandoverPublic(
                state=handover.state,
                error=handover.last_error,
                attempts=handover.attempts,
                next_attempt_at=(
                    handover.next_attempt_at
                    if handover.state == DeliveryState.PENDING.value
                    else None
                ),
            )
        shown.append(public)
    return shown


def queue_handover(session: Session, attachment: Attachment) -> None:
    """
    Record that a PDF is to go to Paperless, and wake the loop (FR-04.6). The
    file is already in storage and downloadable from there.
    """
    session.add(PaperlessHandover(attachment_id=attachment.id))
    session.commit()
    webhooks.wake()


def resend(session: Session, handover: PaperlessHandover) -> None:
    """The owner asks for a failed hand-over to be tried again from the top."""
    handover.state = DeliveryState.PENDING.value
    handover.stage = PaperlessHandoverStage.SEND.value
    handover.paperless_task_id = None
    handover.paperless_document_id = None
    handover.sent_at = None
    handover.attempts = 0
    handover.last_error = None
    handover.next_attempt_at = datetime.now(UTC)
    session.add(handover)
    session.commit()
    webhooks.wake()


def fetch_original(
    session: Session, attachment: Attachment, client: httpx.Client
) -> bytes:
    """
    The bytes of an attachment kept in Paperless, as they were attached
    (FR-04.10). Raises `PaperlessError` saying why when they cannot be had.
    """
    document_id = attachment.paperless_document_id
    assert document_id is not None
    connection = get_connection(session, attachment.owner_id)
    if connection is None:
        raise PaperlessError(
            "This file is kept in Paperless, and Paperless is not connected. "
            "Connect it again in Settings to reach the file.",
            code=NOT_CONNECTED_CODE,
            status=409,
        )
    api = api_for(connection, client)
    # No connection is held while Paperless takes its time to answer.
    session.commit()
    try:
        return api.download_original(document_id)
    except PaperlessError as error:
        if error.missing:
            raise PaperlessError(
                "Paperless no longer has this document.",
                code=MISSING_CODE,
                status=404,
            ) from error
        raise PaperlessError(
            f"This file is kept in Paperless, which could not be reached: "
            f"{error.message}",
            code=error.code,
            status=error.status,
        ) from error


def test_connection(client: httpx.Client, url: str, token: str) -> str | None:
    """None when the address answers and the token works, otherwise why not."""
    try:
        PaperlessApi(client, url, token).check()
    except PaperlessError as error:
        return error.message
    return None


# --- Handing a file over --------------------------------------------------------


@dataclass(frozen=True)
class _Work:
    """Everything one attempt needs, taken out of the session so no database
    connection is held while Paperless takes its time."""

    handover_id: uuid.UUID
    attachment_id: uuid.UUID
    filename: str
    task_id: uuid.UUID
    task_title: str
    connection: PaperlessConnection
    stage: str
    paperless_task_id: str | None
    document_id: int | None
    sent_at: datetime | None


@dataclass
class _Step:
    """What an attempt came to. An `error` is a failed attempt; otherwise it
    moved on, or is waiting, or is done."""

    stage: str
    paperless_task_id: str | None = None
    document_id: int | None = None
    sent_at: datetime | None = None
    error: str | None = None
    # A failure that retrying cannot mend.
    final: bool = False
    # When the next look is due, for a step that is waiting on Paperless.
    wait: timedelta | None = None
    done: bool = False


def _md5(data: bytes) -> str:
    # Paperless identifies the original file by its MD5: not a security use.
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def _run(
    work: _Work, api: PaperlessApi, storage: AttachmentStorage, now: datetime
) -> _Step:
    """Take a hand-over as far as one attempt goes."""
    key = str(work.attachment_id)
    stage = work.stage
    step = _Step(
        stage=stage,
        paperless_task_id=work.paperless_task_id,
        document_id=work.document_id,
        sent_at=work.sent_at,
    )
    if stage == PaperlessHandoverStage.SEND.value:
        try:
            data = storage.get(key)
        except FileNotFoundError:
            step.error = "Taskly's copy of the file is missing, so it cannot be sent."
            step.final = True
            return step
        existing = api.find_by_checksum(_md5(data))
        if existing is not None:
            # Paperless already holds it: link, do not send (FR-04.7).
            step.document_id = existing
            stage = step.stage = PaperlessHandoverStage.FINISH.value
        else:
            tag_id = api.ensure_tag()
            step.paperless_task_id = api.post_document(work.filename, data, tag_id)
            step.sent_at = now
            step.stage = PaperlessHandoverStage.POLL.value
            step.wait = POLL_INTERVAL
            return step
    elif stage == PaperlessHandoverStage.POLL.value:
        assert work.paperless_task_id is not None
        consumed = api.consumption(work.paperless_task_id)
        status = consumed.status if consumed else ""
        if consumed is not None and status == "SUCCESS":
            document_id = consumed.document_id
            if document_id is None:
                document_id = _find_sent(api, storage, key)
            if document_id is None:
                return _restart(step, "Paperless did not say which document it made")
            step.document_id = document_id
            stage = step.stage = PaperlessHandoverStage.FINISH.value
        elif consumed is not None and status in ("FAILURE", "REVOKED"):
            # A file Paperless already holds fails to be consumed as a
            # duplicate: that is a link, not a failure.
            document_id = _find_sent(api, storage, key)
            if document_id is None:
                reason = (consumed.result or status).strip()
                return _restart(step, f"Paperless could not process the file: {reason}")
            step.document_id = document_id
            stage = step.stage = PaperlessHandoverStage.FINISH.value
        else:
            started = work.sent_at or now
            if now - started > POLL_DEADLINE:
                minutes = int(POLL_DEADLINE.total_seconds() // 60)
                return _restart(
                    step,
                    f"Paperless had not processed the file after {minutes} minutes",
                )
            step.wait = POLL_INTERVAL
            return step
    assert stage == PaperlessHandoverStage.FINISH.value
    assert step.document_id is not None
    tag_id = api.ensure_tag()
    api.ensure_document_tag(step.document_id, tag_id)
    api.ensure_note(
        step.document_id,
        note_text(work.task_title, work.task_id),
        link=task_url(work.task_id),
    )
    step.done = True
    return step


def _find_sent(api: PaperlessApi, storage: AttachmentStorage, key: str) -> int | None:
    try:
        return api.find_by_checksum(_md5(storage.get(key)))
    except FileNotFoundError:
        return None


def _restart(step: _Step, error: str) -> _Step:
    """A failed attempt after the file was sent: the next one starts from the
    top, and finds the document by checksum if Paperless has it after all."""
    step.stage = PaperlessHandoverStage.SEND.value
    step.paperless_task_id = None
    step.sent_at = None
    step.error = error
    return step


def _work_for(session: Session, handover_id: uuid.UUID) -> _Work | None:
    """What to attempt for a claimed hand-over, or None when there is nothing
    left to do (and the row has been cleared away)."""
    handover = session.get(PaperlessHandover, handover_id)
    if handover is None or handover.state != DeliveryState.PENDING.value:
        return None
    attachment = session.get(Attachment, handover.attachment_id)
    connection = (
        session.get(PaperlessConnection, attachment.owner_id) if attachment else None
    )
    task = session.get(Task, attachment.task_id) if attachment else None
    if attachment is None or connection is None or task is None:
        # The attachment is gone, or the owner disconnected since: the file is
        # still in Taskly and stays there.
        session.delete(handover)
        session.commit()
        return None
    return _Work(
        handover_id=handover.id,
        attachment_id=attachment.id,
        filename=attachment.filename,
        task_id=task.id,
        task_title=task.title,
        connection=connection,
        stage=handover.stage,
        paperless_task_id=handover.paperless_task_id,
        document_id=handover.paperless_document_id,
        sent_at=handover.sent_at,
    )


def _apply(session: Session, work: _Work, step: _Step, now: datetime) -> bool:
    """Write down what an attempt came to. True when the hand-over is finished
    and Taskly's copy can be released."""
    handover = session.get(PaperlessHandover, work.handover_id)
    if handover is None:
        return False
    if step.done:
        attachment = session.get(Attachment, work.attachment_id)
        session.delete(handover)
        if attachment is None:
            session.commit()
            return False
        attachment.paperless_document_id = step.document_id
        session.add(attachment)
        session.commit()
        return True
    handover.stage = step.stage
    handover.paperless_task_id = step.paperless_task_id
    handover.paperless_document_id = step.document_id
    handover.sent_at = step.sent_at
    handover.last_attempt_at = now
    if step.error is None:
        # Moved on, or waiting on Paperless: not a failed attempt.
        handover.last_error = None
        handover.next_attempt_at = now + (step.wait or timedelta())
    else:
        handover.attempts += 1
        handover.last_error = step.error[:500]
        if step.final or handover.attempts >= webhooks.MAX_ATTEMPTS:
            handover.state = DeliveryState.FAILED.value
        else:
            handover.next_attempt_at = (
                now + webhooks.RETRY_DELAYS[handover.attempts - 1]
            )
    session.add(handover)
    session.commit()
    return False


def _attempt(
    handover_id: uuid.UUID,
    client: httpx.Client,
    storage: AttachmentStorage,
    now: datetime,
) -> None:
    """One attempt at a claimed hand-over, from reading the row to recording it."""
    with Session(engine) as session:
        work = _work_for(session, handover_id)
    if work is None:
        return
    try:
        api = api_for(work.connection, client)
        step = _run(work, api, storage, now)
    except PaperlessError as error:
        step = _Step(
            stage=work.stage,
            paperless_task_id=work.paperless_task_id,
            document_id=work.document_id,
            sent_at=work.sent_at,
            error=error.message,
        )
    except Exception as error:
        # Whatever else went wrong is a failed attempt too: an exception that
        # got out would leave the row claimed and silent until the lease ends.
        logger.exception("Paperless hand-over failed")
        step = _Step(
            stage=work.stage,
            paperless_task_id=work.paperless_task_id,
            document_id=work.document_id,
            sent_at=work.sent_at,
            error=f"{type(error).__name__}: {error}",
        )
    with Session(engine) as session:
        finished = _apply(session, work, step, now)
    if finished:
        # The attachment points at Paperless now: release Taskly's copy
        # (FR-04.6). If this fails the bytes are only orphaned, and nothing
        # reads them.
        try:
            storage.delete(str(work.attachment_id))
        except Exception:
            logger.exception("Could not release the local copy of an attachment")


def hand_over_due(
    *,
    client: httpx.Client | None = None,
    storage: AttachmentStorage | None = None,
    now: datetime | None = None,
    limit: int = webhooks.BATCH_SIZE,
) -> int:
    """
    Claim the hand-overs that are due as of `now` and attempt each once.
    Returns how many were claimed. Safe from any number of processes at once;
    `client`, `storage` and `now` exist for tests.
    """
    now = now or datetime.now(UTC)
    ids = webhooks.claim_due(PaperlessHandover, now=now, limit=limit)
    if not ids:
        return 0
    own_client = client is None
    client = client or webhooks.make_client()
    storage = storage or default_storage()
    try:
        if len(ids) == 1:
            _attempt(ids[0], client, storage, now)
        else:
            with ThreadPoolExecutor(
                max_workers=min(webhooks.WORKERS, len(ids))
            ) as pool:
                list(pool.map(lambda i: _attempt(i, client, storage, now), ids))
    finally:
        if own_client:
            client.close()
    return len(ids)
