from collections.abc import Generator

import pytest
from sqlmodel import Session, delete

from app.api.deps import get_webhook_client
from app.main import app
from app.models import WebhookDelivery
from tests.utils.webhooks import Receiver


@pytest.fixture(autouse=True)
def empty_outbox(db: Session) -> None:
    """
    The outbox is shared by every test in the session, and a delivery pass
    takes whatever is due, so each test starts from nothing waiting.
    """
    db.execute(delete(WebhookDelivery))
    db.commit()


@pytest.fixture
def receiver() -> Generator[Receiver]:
    """A receiver every webhook test endpoint sends to, instead of a network."""
    fake = Receiver()
    app.dependency_overrides[get_webhook_client] = fake.client
    yield fake
    app.dependency_overrides.pop(get_webhook_client, None)
