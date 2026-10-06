"""
Doubles and readers for webhook tests.

Nothing here reaches a network: a delivery is sent through an `httpx` mock
transport, and the outbox is read straight from the table.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from sqlmodel import Session, col, select

from app.models import DeliveryState, WebhookDelivery


@dataclass
class Receiver:
    """
    A webhook receiver that records every request it is sent and answers as it
    is told to: a status, or an exception such as `httpx.ReadTimeout`.
    """

    status: int = 200
    fail_with: Exception | None = None
    requests: list[httpx.Request] = field(default_factory=list)
    on_request: Callable[[httpx.Request], None] | None = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.on_request is not None:
            self.on_request(request)
        if self.fail_with is not None:
            raise self.fail_with
        return httpx.Response(self.status)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))


def outbox(db: Session, bot_user_id: str | uuid.UUID) -> list[WebhookDelivery]:
    """Every delivery row of a bot user, oldest first."""
    db.expire_all()
    return list(
        db.exec(
            select(WebhookDelivery)
            .where(WebhookDelivery.bot_user_id == uuid.UUID(str(bot_user_id)))
            .order_by(col(WebhookDelivery.occurred_at))
        )
    )


def pending(db: Session, bot_user_id: str | uuid.UUID) -> list[WebhookDelivery]:
    """What is waiting to be delivered to a bot user."""
    return [
        row
        for row in outbox(db, bot_user_id)
        if row.state == DeliveryState.PENDING.value
    ]
