import ipaddress
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.api.deps import get_attachment_storage
from app.core import outbound
from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models import User
from tests.utils.storage import InMemoryAttachmentStorage
from tests.utils.user import authentication_token_from_email


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    # This fixture deletes every user when the session ends, and a user takes
    # their projects, tasks, tags and bot users with them. `scripts/test.sh`
    # is what points the engine at the test database; run without it, the
    # suite empties the development one instead. The check is here rather than
    # in the script because the script is the thing that gets skipped.
    if engine.url.database != settings.TEST_DB_NAME:
        pytest.exit(
            f"Refusing to run: the tests delete every user, and this session "
            f"is pointed at “{engine.url.database}” rather than at "
            f"“{settings.TEST_DB_NAME}”. Run `bash scripts/test.sh`.",
            returncode=1,
        )
    with Session(engine) as session:
        yield session
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.FIRST_SUPERUSER, db=db, is_superuser=True
    )


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


@pytest.fixture(autouse=True)
def public_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Every host name resolves to one public address, so no test needs a network
    to set a webhook. An address given as a number is its own answer, and a
    test that needs a name to resolve elsewhere patches `resolve_host` again.
    """

    def resolve(host: str) -> list[str]:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return ["93.184.216.34"]
        return [host]

    monkeypatch.setattr(outbound, "resolve_host", resolve)


@pytest.fixture(autouse=True)
def storage() -> Generator[InMemoryAttachmentStorage]:
    """Attachments go to memory, never to a disk; the test can look inside."""
    fake_storage = InMemoryAttachmentStorage()
    app.dependency_overrides[get_attachment_storage] = lambda: fake_storage
    yield fake_storage
    app.dependency_overrides.pop(get_attachment_storage, None)
