"""Steps shared by the Paperless tests: connecting, attaching and running the
hand-over loop's pass against the stub."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import paperless
from app.core.config import settings
from app.models import PaperlessHandover
from tests.utils.accounts import create_user_headers
from tests.utils.paperless import BASE_URL, TOKEN, StubPaperless
from tests.utils.storage import InMemoryAttachmentStorage

API = settings.API_V1_STR
Headers = dict[str, str]


def connect(
    client: TestClient,
    headers: Headers,
    *,
    url: str = BASE_URL,
    token: str | None = TOKEN,
) -> httpx.Response:
    response: httpx.Response = client.put(
        f"{API}/paperless/", headers=headers, json={"url": url, "token": token}
    )
    return response


def connected_user(client: TestClient, db: Session) -> Headers:
    headers = create_user_headers(client, db)
    r = connect(client, headers)
    assert r.status_code == 200, r.text
    return headers


def upload(
    client: TestClient,
    headers: Headers,
    task_id: str,
    data: bytes,
    filename: str = "invoice.pdf",
    content_type: str = "application/pdf",
) -> dict[str, Any]:
    r = client.post(
        f"{API}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": (filename, data, content_type)},
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def read_attachment(
    client: TestClient, headers: Headers, task_id: str, attachment_id: str
) -> dict[str, Any]:
    r = client.get(f"{API}/tasks/{task_id}/attachments/", headers=headers)
    assert r.status_code == 200, r.text
    return next(a for a in r.json()["data"] if a["id"] == attachment_id)


def drain(
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
    *,
    now: datetime | None = None,
) -> int:
    """One pass of the loop over the hand-over outbox, as of `now`."""
    return paperless.hand_over_due(
        client=stub.client(), storage=storage, now=now or datetime.now(UTC)
    )


def settle(
    stub: StubPaperless,
    storage: InMemoryAttachmentStorage,
    *,
    start: datetime | None = None,
    step: timedelta = timedelta(minutes=1),
) -> datetime:
    """
    Run passes of the loop, a step of the clock apart, until one finds nothing
    due. Returns the time of the last pass. For flows that go well: a wait for
    Paperless to consume a file only ever takes a pass or two.
    """
    now = start or datetime.now(UTC)
    for _ in range(20):
        if drain(stub, storage, now=now) == 0:
            return now
        now += step
    raise AssertionError("the hand-over never settled")


def handover(db: Session, attachment_id: str) -> PaperlessHandover | None:
    """The attachment's hand-over row, read fresh; None once it is finished."""
    db.expire_all()
    return db.exec(
        select(PaperlessHandover).where(
            PaperlessHandover.attachment_id == uuid.UUID(attachment_id)
        )
    ).first()
