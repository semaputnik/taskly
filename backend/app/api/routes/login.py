from typing import Any

from fastapi import APIRouter

from app import passkeys
from app.api.deps import CurrentUser, SessionDep, UserAgent
from app.core import security
from app.models import (
    PasskeyCredential,
    RecoveryStart,
    RegistrationStart,
    Token,
    User,
    UserPublic,
)

router = APIRouter(tags=["login"])


def _session_for(user: User) -> Token:
    return Token(access_token=security.session_token(user.id, user.session_version))


@router.post("/login/registration/options")
def registration_options(session: SessionDep, body: RegistrationStart) -> Any:
    """
    Start registering an account: the options for creating its first passkey
    (FR-12.2). Open to anyone, with no invitation or approval (FR-09.4).
    """
    return passkeys.start_registration(session, email=str(body.email))


@router.post("/login/registration")
def register(
    session: SessionDep, body: PasskeyCredential, user_agent: UserAgent = None
) -> Token:
    """Finish registering: create the account and its passkey, and sign in."""
    user = passkeys.finish_registration(
        session, credential=body.credential, user_agent=user_agent
    )
    return _session_for(user)


@router.post("/login/passkey/options")
def sign_in_options(session: SessionDep) -> Any:
    """
    Start signing in. The options name no account: the browser offers the
    passkeys it holds for this installation (FR-12.3).
    """
    return passkeys.start_sign_in(session)


@router.post("/login/passkey")
def sign_in(session: SessionDep, body: PasskeyCredential) -> Token:
    """Finish signing in with a passkey and open a session (FR-12.11)."""
    user = passkeys.finish_sign_in(session, credential=body.credential)
    return _session_for(user)


@router.post("/login/recovery/options")
def recovery_options(session: SessionDep, body: RecoveryStart) -> Any:
    """
    Start recovering an account with a recovery code: the options for its
    new passkey (FR-12.17).
    """
    return passkeys.start_recovery(session, email=str(body.email), code=body.code)


@router.post("/login/recovery")
def recover(
    session: SessionDep, body: PasskeyCredential, user_agent: UserAgent = None
) -> Token:
    """
    Finish recovering: add the new passkey, spend the code, end every other
    session, and sign in (FR-12.14, FR-12.17).
    """
    user = passkeys.finish_recovery(
        session, credential=body.credential, user_agent=user_agent
    )
    return _session_for(user)


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user
