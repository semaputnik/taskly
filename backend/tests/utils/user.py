from fastapi.testclient import TestClient
from fido2 import cbor
from fido2.cose import ES256
from sqlmodel import Session

from app import crud, passkeys
from app.core.config import settings
from app.models import Passkey, User, UserCreate
from tests.utils.passkey import Authenticator, b64
from tests.utils.utils import random_email

API = settings.API_V1_STR


def create_random_user(db: Session, **fields: object) -> User:
    user_in = UserCreate.model_validate({"email": random_email(), **fields})
    return crud.create_user(session=db, user_create=user_in)


def give_passkey(db: Session, user: User) -> Authenticator:
    """
    A passkey for `user`, held by a fresh software authenticator, stored as if
    the user had registered it. For tests about something other than the
    registration ceremony itself.
    """
    authenticator = Authenticator()
    authenticator.cred_init(passkeys.rp_id(), b64(user.id.bytes))
    db.add(
        Passkey(
            user_id=user.id,
            credential_id=authenticator.credential_id,
            public_key=cbor.encode(
                ES256.from_cryptography_key(authenticator.private_key.public_key())
            ),
            name="Test passkey",
        )
    )
    db.commit()
    return authenticator


def sign_in(client: TestClient, authenticator: Authenticator) -> dict[str, str]:
    """Sign in through the API with the authenticator's passkey."""
    options = client.post(f"{API}/login/passkey/options").json()
    r = client.post(
        f"{API}/login/passkey", json={"credential": authenticator.get_json(options)}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def new_user_headers(client: TestClient, db: Session) -> dict[str, str]:
    """A new user of the test's own, signed in with a passkey."""
    return sign_in(client, give_passkey(db, create_random_user(db)))


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session, is_superuser: bool = False
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        user = crud.create_user(
            session=db,
            user_create=UserCreate(email=email, is_superuser=is_superuser),
        )
    return sign_in(client, give_passkey(db, user))
