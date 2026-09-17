import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api import access
from app.api.deps import Caller, CurrentUser, SessionDep
from app.models import (
    BotPermissions,
    BotScope,
    BotTokenIssue,
    BotTokenIssued,
    BotUser,
    BotUserCreate,
    BotUserPublic,
    BotUsersPublic,
    BotUserUpdate,
    Message,
)

# Every endpoint here takes a human caller: creating, scoping, issuing tokens
# for and deleting bot users is the user's to do, and a bot user cannot do it for
# another bot user or for itself (FR-07.3).
router = APIRouter(prefix="/bot-users", tags=["bots"])

# A bot user holds one token (FR-08.12). Replacing it is a revoke and then a
# fresh issue, never an overwrite, so an old token is never quietly left
# working or quietly cut off.
TOKEN_ALREADY_ISSUED_STATUS = 409
TOKEN_ALREADY_ISSUED_CODE = "token_already_issued"


def _public(bot: BotUser, project_ids: list[uuid.UUID]) -> BotUserPublic:
    return BotUserPublic(
        id=bot.id,
        name=bot.name,
        deleted=bot.deleted_at is not None,
        scope=BotScope(
            project_ids=project_ids,
            permissions=BotPermissions.model_validate(bot, from_attributes=True),
        ),
        has_token=bot.token_hash is not None,
        token_issued_at=bot.token_issued_at,
        token_expires_at=bot.token_expires_at,
        token_last_used_at=bot.token_last_used_at,
        token_revoked_at=bot.token_revoked_at,
        created_at=bot.created_at,
    )


def _get_owned_bot_user(
    session: SessionDep,
    current_user: CurrentUser,
    bot_user_id: uuid.UUID,
    deleted: bool = False,
) -> BotUser:
    """
    One of the user's bot users. Deleted ones are out of reach unless the
    caller is reading rather than changing: nothing can be done to a deleted
    bot user, but its record still opens (FR-08.19).
    """
    bot = session.get(BotUser, bot_user_id)
    if not bot or bot.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Bot user not found")
    if bot.deleted_at is not None and not deleted:
        raise HTTPException(status_code=404, detail="Bot user not found")
    return bot


@router.get("/", response_model=BotUsersPublic)
def read_bot_users(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's bot users, with their scopes, oldest first.
    Deleted bot users are not among them.
    """
    count = session.exec(
        select(func.count())
        .select_from(BotUser)
        .where(BotUser.owner_id == current_user.id, col(BotUser.deleted_at).is_(None))
    ).one()
    bots = session.exec(
        select(BotUser)
        .where(BotUser.owner_id == current_user.id, col(BotUser.deleted_at).is_(None))
        .order_by(col(BotUser.created_at))
        .offset(skip)
        .limit(limit)
    ).all()
    project_ids = crud.get_bot_user_project_ids(
        session=session, bot_ids=[bot.id for bot in bots]
    )
    return BotUsersPublic(
        data=[_public(bot, project_ids[bot.id]) for bot in bots], count=count
    )


@router.get("/{bot_user_id}", response_model=BotUserPublic)
def read_bot_user(
    *, session: SessionDep, current_user: CurrentUser, bot_user_id: uuid.UUID
) -> Any:
    """
    Retrieve one bot user by its id, with its scope: what the bot user's panel
    is addressed by.

    A deleted bot user reads here too, marked deleted. It is kept rather than
    removed precisely so that what it did still names it (FR-08.19), and a
    reader following one of those references has to land on a record that
    says what it now is — while every endpoint that would change it still
    refuses, and the list still leaves it out.
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id, deleted=True)
    return _public(
        bot, crud.get_bot_user_project_ids(session=session, bot_ids=[bot.id])[bot.id]
    )


@router.post("/", response_model=BotUserPublic)
def create_bot_user(
    *, session: SessionDep, current_user: CurrentUser, bot_user_in: BotUserCreate
) -> Any:
    """
    Create a bot user with its scope: the projects it may act in, each named
    explicitly (FR-08.6), and what it may do there (FR-08.9, FR-08.10).

    It has no token yet; issuing one is a step of its own.
    """
    for project_id in bot_user_in.scope.project_ids:
        access.get_project(
            session, Caller(owner_id=current_user.id), project_id, action=None
        )
    bot = crud.create_bot_user(
        session=session, bot_user_create=bot_user_in, owner_id=current_user.id
    )
    return _public(
        bot, crud.get_bot_user_project_ids(session=session, bot_ids=[bot.id])[bot.id]
    )


@router.patch("/{bot_user_id}", response_model=BotUserPublic)
def update_bot_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    bot_user_id: uuid.UUID,
    bot_user_in: BotUserUpdate,
) -> Any:
    """
    Rename a bot user, or replace its scope, or both. The bot user's next
    request is authorized against the new scope; its token is untouched.

    As on creation, every project has to be one of the user's own.
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id)
    if bot_user_in.scope is not None:
        for project_id in bot_user_in.scope.project_ids:
            access.get_project(
                session, Caller(owner_id=current_user.id), project_id, action=None
            )
    bot = crud.update_bot_user(session=session, bot=bot, bot_user_update=bot_user_in)
    return _public(
        bot, crud.get_bot_user_project_ids(session=session, bot_ids=[bot.id])[bot.id]
    )


@router.delete("/{bot_user_id}")
def delete_bot_user(
    *, session: SessionDep, current_user: CurrentUser, bot_user_id: uuid.UUID
) -> Message:
    """
    Delete a bot user (FR-08.18). It is marked deleted rather than removed, so
    what it did and what it was assigned still name it (FR-08.19, FR-08.21),
    and its token is refused from the next request on (FR-08.20).

    There is no undoing it, and nothing here acts on it again: every endpoint
    that would change a bot user refuses a deleted one, and the list leaves it
    out. Reading it by its id still works, so what it did can still be read
    back to the bot user that did it.
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id)
    crud.delete_bot_user(session=session, bot=bot)
    return Message(message="Bot user deleted successfully")


@router.post("/{bot_user_id}/token", response_model=BotTokenIssued)
def issue_bot_user_token(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    bot_user_id: uuid.UUID,
    token_in: BotTokenIssue | None = None,
) -> Any:
    """
    Issue the bot user's token, optionally with an expiry (FR-08.14).

    This response is the only place the token appears: only its digest is
    stored, and no endpoint returns it again (FR-08.13). A bot user that
    already holds a token — even an expired one — is refused another until
    that one is revoked (FR-08.16).
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id)
    if bot.token_hash is not None:
        raise HTTPException(
            status_code=TOKEN_ALREADY_ISSUED_STATUS,
            detail={
                "code": TOKEN_ALREADY_ISSUED_CODE,
                "message": (
                    f"“{bot.name}” already has a token. A bot user holds one "
                    "token at a time: revoke it before issuing a new one."
                ),
            },
        )
    expires_at = token_in.expires_at if token_in else None
    token = crud.issue_bot_token(session=session, bot=bot, expires_at=expires_at)
    return BotTokenIssued(bot_user_id=bot.id, token=token, expires_at=expires_at)


@router.delete("/{bot_user_id}/token", response_model=BotUserPublic)
def revoke_bot_user_token(
    *, session: SessionDep, current_user: CurrentUser, bot_user_id: uuid.UUID
) -> Any:
    """
    Revoke the bot user's token: the next request with it is refused
    (FR-08.15). The bot user keeps its name and scope, and stays without a
    token until one is issued again.

    Revoking a bot user that holds no token changes nothing.
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id)
    if bot.token_hash is not None:
        bot = crud.revoke_bot_token(session=session, bot=bot)
    return _public(
        bot, crud.get_bot_user_project_ids(session=session, bot_ids=[bot.id])[bot.id]
    )
