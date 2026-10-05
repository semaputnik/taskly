"""Registering and signing in with a passkey (F-12, FR-09.4, FR-09.6)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session, col, select

from app import crud, passkeys
from app.core import security
from app.core.config import settings
from app.main import app
from app.models import Passkey, User, WebAuthnChallenge
from tests.utils.passkey import Authenticator, b64
from tests.utils.user import create_random_user, give_passkey, sign_in
from tests.utils.utils import random_email

API = settings.API_V1_STR


def _registration_options(client: TestClient, email: str) -> dict[str, Any]:
    r = client.post(f"{API}/login/registration/options", json={"email": email})
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()
    return result


def _register(
    client: TestClient, email: str, authenticator: Authenticator
) -> dict[str, Any]:
    options = _registration_options(client, email)
    r = client.post(
        f"{API}/login/registration",
        json={"credential": authenticator.create_json(options)},
    )
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()
    return result


def _sign_in_options(client: TestClient) -> dict[str, Any]:
    result: dict[str, Any] = client.post(f"{API}/login/passkey/options").json()
    return result


def _me(client: TestClient, token: str) -> Any:
    return client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {token}"})


# --- Registering ------------------------------------------------------------


def test_registering_creates_the_account_with_its_passkey_and_signs_in(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    authenticator = Authenticator()

    token = _register(client, email, authenticator)["access_token"]

    r = _me(client, token)
    assert r.status_code == 200
    assert r.json()["email"] == email
    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None and user.is_superuser is False
    keys = db.exec(select(Passkey).where(Passkey.user_id == user.id)).all()
    assert [key.credential_id for key in keys] == [authenticator.credential_id]
    # The new passkey is made under the id the account was given.
    assert authenticator.user_handle == b64(user.id.bytes)


def test_registration_asks_for_a_discoverable_verified_passkey(
    client: TestClient,
) -> None:
    options = _registration_options(client, random_email())

    assert options["rp"]["id"] == passkeys.rp_id()
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["timeout"] == 5 * 60 * 1000


def test_registering_a_taken_email_is_refused(client: TestClient, db: Session) -> None:
    user = create_random_user(db)

    r = client.post(f"{API}/login/registration/options", json={"email": user.email})

    assert r.status_code == 400
    assert r.json()["detail"] == "An account with this email already exists."


def test_an_email_taken_while_registering_is_refused_at_the_end(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    options = _registration_options(client, email)
    create_random_user(db, email=email)

    r = client.post(
        f"{API}/login/registration",
        json={"credential": Authenticator().create_json(options)},
    )

    assert r.status_code == 400
    assert r.json()["detail"] == "An account with this email already exists."


def test_a_passkey_made_without_user_verification_is_refused(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    options = _registration_options(client, email)

    r = client.post(
        f"{API}/login/registration",
        json={"credential": Authenticator(user_verified=False).create_json(options)},
    )

    assert r.status_code == 400
    assert crud.get_user_by_email(session=db, email=email) is None


def test_a_registration_answer_is_accepted_once(client: TestClient) -> None:
    options = _registration_options(client, random_email())
    credential = Authenticator().create_json(options)
    r = client.post(f"{API}/login/registration", json={"credential": credential})
    assert r.status_code == 200

    r = client.post(f"{API}/login/registration", json={"credential": credential})

    assert r.status_code == 400
    assert r.json()["detail"] == "The passkey could not be created. Try again."


def test_an_expired_challenge_is_refused(client: TestClient, db: Session) -> None:
    email = random_email()
    options = _registration_options(client, email)
    db.exec(
        update(WebAuthnChallenge)
        .where(col(WebAuthnChallenge.email) == email)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()

    r = client.post(
        f"{API}/login/registration",
        json={"credential": Authenticator().create_json(options)},
    )

    assert r.status_code == 400
    assert crud.get_user_by_email(session=db, email=email) is None


def test_an_answer_from_another_origin_is_refused(client: TestClient) -> None:
    options = _registration_options(client, random_email())
    authenticator = Authenticator(origin="https://evil.example.com")

    r = client.post(
        f"{API}/login/registration",
        json={"credential": authenticator.create_json(options)},
    )

    assert r.status_code == 400


def test_a_challenge_answers_only_its_own_kind_of_ceremony(client: TestClient) -> None:
    sign_in_options = _sign_in_options(client)
    # A registration answer built around a sign-in challenge.
    registration_options = _registration_options(client, random_email())
    registration_options["challenge"] = sign_in_options["challenge"]

    r = client.post(
        f"{API}/login/registration",
        json={"credential": Authenticator().create_json(registration_options)},
    )

    assert r.status_code == 400


def test_a_malformed_answer_is_refused(client: TestClient) -> None:
    r = client.post(f"{API}/login/registration", json={"credential": {"id": "x"}})
    assert r.status_code == 400

    r = client.post(f"{API}/login/passkey", json={"credential": {"response": "x"}})
    assert r.status_code == 400


@pytest.fixture
def no_superuser(db: Session) -> Generator[str]:
    """
    An installation with no superuser yet, whose first-superuser address is a
    fresh one. The superusers the rest of the suite relies on come back after.
    """
    superusers = db.exec(select(User).where(User.is_superuser == True)).all()  # noqa: E712
    ids = [user.id for user in superusers]
    db.exec(update(User).where(col(User.id).in_(ids)).values(is_superuser=False))
    db.commit()
    email = random_email()
    with patch.object(settings, "FIRST_SUPERUSER", email):
        yield email
    db.exec(update(User).where(col(User.id).in_(ids)).values(is_superuser=True))
    db.commit()


def test_registering_the_first_superuser_address_makes_the_superuser(
    client: TestClient, db: Session, no_superuser: str
) -> None:
    _register(client, no_superuser, Authenticator())

    user = crud.get_user_by_email(session=db, email=no_superuser)
    assert user is not None and user.is_superuser is True


def test_once_a_superuser_exists_their_address_is_an_ordinary_one(
    client: TestClient, db: Session, no_superuser: str
) -> None:
    create_random_user(db, is_superuser=True)

    _register(client, no_superuser, Authenticator())

    user = crud.get_user_by_email(session=db, email=no_superuser)
    assert user is not None and user.is_superuser is False


# --- Signing in -------------------------------------------------------------


def test_signing_in_names_no_account_and_requires_verification(
    client: TestClient,
) -> None:
    options = _sign_in_options(client)

    assert options["rpId"] == passkeys.rp_id()
    assert options["allowCredentials"] == []
    assert options["userVerification"] == "required"


def test_signing_in_with_a_passkey_opens_a_session(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    authenticator = give_passkey(db, user)

    headers = sign_in(client, authenticator)

    r = client.get(f"{API}/users/me", headers=headers)
    assert r.json()["id"] == str(user.id)
    passkey = db.exec(select(Passkey).where(Passkey.user_id == user.id)).one()
    db.refresh(passkey)
    assert passkey.last_used_at is not None
    assert passkey.sign_count == authenticator.sign_count


def test_the_session_has_the_usual_lifetime(client: TestClient, db: Session) -> None:
    headers = sign_in(client, give_passkey(db, create_random_user(db)))

    token = headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
    lifetime = datetime.fromtimestamp(claims["exp"], UTC) - datetime.now(UTC)
    expected = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    assert expected - timedelta(minutes=1) < lifetime <= expected


SIGN_IN_REFUSED = "This passkey could not sign you in. Try again."


def test_an_unknown_passkey_is_refused_without_saying_why(client: TestClient) -> None:
    authenticator = Authenticator()
    authenticator.cred_init(passkeys.rp_id(), "unknown")

    r = client.post(
        f"{API}/login/passkey",
        json={"credential": authenticator.get_json(_sign_in_options(client))},
    )

    assert r.status_code == 400
    assert r.json()["detail"] == SIGN_IN_REFUSED


def test_signing_in_without_user_verification_is_refused(
    client: TestClient, db: Session
) -> None:
    authenticator = give_passkey(db, create_random_user(db))
    authenticator.user_verified = False

    r = client.post(
        f"{API}/login/passkey",
        json={"credential": authenticator.get_json(_sign_in_options(client))},
    )

    assert r.status_code == 400
    assert r.json()["detail"] == SIGN_IN_REFUSED


def test_an_inactive_account_cannot_sign_in(client: TestClient, db: Session) -> None:
    authenticator = give_passkey(db, create_random_user(db, is_active=False))

    r = client.post(
        f"{API}/login/passkey",
        json={"credential": authenticator.get_json(_sign_in_options(client))},
    )

    assert r.status_code == 400
    assert r.json()["detail"] == SIGN_IN_REFUSED


def test_a_sign_in_answer_is_accepted_once(client: TestClient, db: Session) -> None:
    authenticator = give_passkey(db, create_random_user(db))
    credential = authenticator.get_json(_sign_in_options(client))
    assert (
        client.post(f"{API}/login/passkey", json={"credential": credential}).status_code
        == 200
    )

    r = client.post(f"{API}/login/passkey", json={"credential": credential})

    assert r.status_code == 400
    assert r.json()["detail"] == SIGN_IN_REFUSED


def test_unanswered_challenges_do_not_pile_up(client: TestClient, db: Session) -> None:
    _sign_in_options(client)
    db.exec(
        update(WebAuthnChallenge).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
    )
    db.commit()

    _sign_in_options(client)

    live = db.exec(select(WebAuthnChallenge)).all()
    assert len(live) == 1


def test_a_token_from_before_the_session_version_is_refused(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    token = security.session_token(user.id, user.session_version)
    unversioned = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(hours=1), "sub": str(user.id)},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    user.session_version += 1
    db.add(user)
    db.commit()

    for stale in (token, unversioned):
        r = _me(client, stale)
        assert r.status_code == 401


def test_test_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(f"{API}/login/test-token", headers=superuser_token_headers)
    assert r.status_code == 200
    assert "email" in r.json()


def test_password_sign_in_is_gone() -> None:
    paths = set(app.openapi()["paths"])
    for path in (
        "/login/access-token",
        "/password-recovery/{email}",
        "/reset-password/",
        "/users/signup",
        "/users/me/password",
    ):
        assert f"{API}{path}" not in paths


# --- The relying party and names --------------------------------------------


def test_passkeys_are_bound_to_the_public_hostname() -> None:
    with patch.object(settings, "FRONTEND_HOST", "https://tasks.example.com:8443/app"):
        assert passkeys.rp_id() == "tasks.example.com"
        assert passkeys.expected_origin() == "https://tasks.example.com:8443"


@pytest.mark.parametrize(
    ("user_agent", "name"),
    [
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Chrome on macOS",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "Safari on iPhone",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
            "like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
            "Edge on Windows",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Firefox on Linux",
        ),
        ("Mozilla/5.0 (Linux; Android 15) Firefox/140.0", "Firefox on Android"),
        ("testclient", "Passkey"),
        (None, "Passkey"),
    ],
)
def test_a_passkey_is_named_after_the_browser_and_device(
    user_agent: str | None, name: str
) -> None:
    assert passkeys.passkey_name(user_agent) == name


def test_registering_names_the_passkey_from_the_browser(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    options = _registration_options(client, email)
    r = client.post(
        f"{API}/login/registration",
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"},
        json={"credential": Authenticator().create_json(options)},
    )
    assert r.status_code == 200

    user = crud.get_user_by_email(session=db, email=email)
    assert user is not None
    passkey = db.exec(select(Passkey).where(Passkey.user_id == user.id)).one()
    assert passkey.name == "Firefox on Linux"
    assert passkey.transports == ["internal"]
    # Registering signed in with it, so it has been used.
    assert passkey.last_used_at is not None
