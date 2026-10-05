from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
from tests.utils.utils import random_email

API = settings.API_V1_STR


def test_create_user(client: TestClient, db: Session) -> None:
    email = random_email()
    r = client.post(
        f"{API}/private/users/", json={"email": email, "full_name": "Pollo Listo"}
    )

    assert r.status_code == 200
    data = r.json()
    user = db.exec(select(User).where(User.id == data["user"]["id"])).first()
    assert user
    assert user.email == email
    assert user.full_name == "Pollo Listo"

    # The session it hands back is a real one.
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    r = client.get(f"{API}/users/me", headers=headers)
    assert r.json()["email"] == email


def test_an_existing_user_is_signed_in_as_they_are(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    first = client.post(f"{API}/private/users/", json={"email": email}).json()
    again = client.post(
        f"{API}/private/users/", json={"email": email, "is_superuser": True}
    ).json()

    assert again["user"]["id"] == first["user"]["id"]
    user = db.exec(select(User).where(User.email == email)).one()
    assert user.is_superuser is False


def test_a_recovery_code_for_anyone(client: TestClient, db: Session) -> None:
    email = random_email()
    client.post(f"{API}/private/users/", json={"email": email, "is_superuser": True})

    r = client.post(f"{API}/private/recovery-code", json={"email": email})

    assert r.status_code == 200
    options = client.post(
        f"{API}/login/recovery/options", json={"email": email, "code": r.json()["code"]}
    )
    assert options.status_code == 200
    user = db.exec(select(User).where(User.email == email)).one()
    assert user.is_superuser is True


def test_a_recovery_code_for_nobody(client: TestClient) -> None:
    r = client.post(f"{API}/private/recovery-code", json={"email": random_email()})
    assert r.status_code == 404
