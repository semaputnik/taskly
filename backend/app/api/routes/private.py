from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel

from app import crud, passkeys
from app.api.deps import SessionDep
from app.core import security
from app.models import RecoveryCodeIssued, UserCreate, UserPublic

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    full_name: str | None = None
    is_superuser: bool = False


class PrivateSession(SQLModel):
    user: UserPublic
    access_token: str


@router.post("/users/", response_model=PrivateSession)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    A user and a session for them, without a passkey ceremony: for the
    end-to-end tests, which set a scene this way rather than through the
    sign-in screen. An existing user is signed in as they are. Only mounted in
    development.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user is None:
        user = crud.create_user(
            session=session,
            user_create=UserCreate(
                email=user_in.email,
                full_name=user_in.full_name,
                is_superuser=user_in.is_superuser,
            ),
        )
    return PrivateSession(
        user=UserPublic.model_validate(user),
        access_token=security.session_token(user.id, user.session_version),
    )


class PrivateRecoveryCode(BaseModel):
    email: str


@router.post("/recovery-code", response_model=RecoveryCodeIssued)
def issue_recovery_code(body: PrivateRecoveryCode, session: SessionDep) -> Any:
    """
    A recovery code for any user, superuser included, the way the server's
    recovery command gives one (FR-12.19): for the end-to-end tests of
    recovering an account. Only mounted in development.
    """
    user = crud.get_user_by_email(session=session, email=body.email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return passkeys.issue_recovery_code(session, user=user)
