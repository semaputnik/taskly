import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud, passkeys
from app.api.deps import (
    AttachmentStorageDep,
    CurrentUser,
    SessionDep,
    UserAgent,
    get_current_active_superuser,
)
from app.models import (
    Confirmation,
    Message,
    PasskeyCredential,
    PasskeyPublic,
    PasskeysPublic,
    RecoveryCodeIssued,
    User,
    UserPublic,
    UsersPublic,
    UserUpdateMe,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve the registered accounts (FR-09.2).

    This list is everything a superuser can do beyond using Taskly like anyone
    else (FR-09.3). It carries account fields only: nothing about what an
    account holds or does, since a user's data stays private from the
    superuser too (FR-10.7).
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(
    session: SessionDep, current_user: CurrentUser, storage: AttachmentStorageDep
) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    # The user's attachment rows are gone the instant the account cascades;
    # their bytes only go if released here first.
    for attachment_id in crud.get_owner_attachment_ids(
        session=session, owner_id=current_user.id
    ):
        storage.delete(str(attachment_id))
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]


@router.post("/me/confirmation/options")
def confirmation_options(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Start a fresh confirmation with one of the caller's own passkeys, which
    adding or removing a passkey and issuing a recovery code each ask for
    (FR-12.7, FR-12.16).
    """
    return passkeys.start_confirmation(session, user=current_user)


@router.get("/me/passkeys", response_model=PasskeysPublic)
def read_passkeys(session: SessionDep, current_user: CurrentUser) -> Any:
    """The caller's passkeys, each with its name and when it was made and last used (FR-12.6)."""
    items = passkeys.list_passkeys(session, user=current_user)
    return PasskeysPublic(
        data=[PasskeyPublic.model_validate(item) for item in items], count=len(items)
    )


@router.post("/me/passkeys/options")
def new_passkey_options(
    session: SessionDep, current_user: CurrentUser, body: Confirmation
) -> Any:
    """
    Start adding a passkey, once the caller has confirmed with one they hold
    (FR-12.7).
    """
    return passkeys.start_new_passkey(
        session, user=current_user, confirmation=body.confirmation
    )


@router.post("/me/passkeys", response_model=PasskeyPublic)
def add_passkey(
    session: SessionDep,
    current_user: CurrentUser,
    body: PasskeyCredential,
    user_agent: UserAgent = None,
) -> Any:
    """Finish adding a passkey."""
    return passkeys.finish_new_passkey(
        session,
        user=current_user,
        credential=body.credential,
        user_agent=user_agent,
    )


@router.delete("/me/passkeys/{passkey_id}", response_model=Message)
def remove_passkey(
    session: SessionDep,
    current_user: CurrentUser,
    passkey_id: uuid.UUID,
    body: Confirmation,
) -> Any:
    """
    Remove one of the caller's passkeys, confirmed with a fresh assertion
    (FR-12.7). The last one stays (FR-12.8), and the sessions it opened are
    not ended (FR-12.9).
    """
    passkeys.remove_passkey(
        session,
        user=current_user,
        passkey_id=passkey_id,
        confirmation=body.confirmation,
    )
    return Message(message="Passkey removed")


@router.post("/me/sign-out-everywhere", response_model=Message)
def sign_out_everywhere(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    End every session of the caller's account, this one included (FR-12.13).
    No passkey confirmation is asked for.
    """
    passkeys.sign_out_everywhere(session, user=current_user)
    return Message(message="Signed out everywhere")


@router.post("/{user_id}/recovery-code", response_model=RecoveryCodeIssued)
def issue_recovery_code(
    session: SessionDep,
    current_user: CurrentSuperuser,
    user_id: uuid.UUID,
    body: Confirmation,
) -> Any:
    """
    Issue a recovery code for a user who has lost every passkey, confirmed
    with the superuser's own passkey (FR-12.16). The code is shown once. The
    superuser's own account is refused (FR-12.19).
    """
    return passkeys.issue_recovery_code_for(
        session,
        superuser=current_user,
        user_id=user_id,
        confirmation=body.confirmation,
    )
