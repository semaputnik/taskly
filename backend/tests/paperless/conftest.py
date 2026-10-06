from collections.abc import Generator

import pytest
from sqlmodel import Session, delete

from app.api.deps import get_paperless_client
from app.main import app
from app.models import PaperlessHandover
from tests.utils.paperless import StubPaperless


@pytest.fixture(autouse=True)
def empty_handovers(db: Session) -> Generator[None]:
    """
    The outbox is shared by every test in the session, and a pass takes whatever
    is due: each test starts from nothing waiting and leaves nothing behind, so
    no other test's loop ever picks up a hand-over and goes looking for Paperless.
    """
    db.execute(delete(PaperlessHandover))
    db.commit()
    yield
    db.execute(delete(PaperlessHandover))
    db.commit()


@pytest.fixture(autouse=True)
def stub() -> Generator[StubPaperless]:
    """
    A Paperless every endpoint of the API talks to, instead of a network. It is
    in place for every test here, so none can reach a real one by forgetting it.
    """
    fake = StubPaperless()
    app.dependency_overrides[get_paperless_client] = fake.client
    yield fake
    app.dependency_overrides.pop(get_paperless_client, None)
