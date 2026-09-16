from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


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
        init_db(session)
        yield session
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
