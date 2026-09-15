import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_project_of
from app.models import (
    BotPermissions,
    BotScope,
    BotTokenIssued,
    BotUser,
    BotUserCreate,
    BotUserPublic,
    BotUsersPublic,
)

# Every endpoint here takes a human caller: creating, scoping and issuing
# tokens for bot users is the user's to do, and a bot user cannot do it for
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
        scope=BotScope(
            project_ids=project_ids,
            permissions=BotPermissions.model_validate(bot, from_attributes=True),
        ),
        has_token=bot.token_hash is not None,
        token_issued_at=bot.token_issued_at,
        created_at=bot.created_at,
    )


def _get_owned_bot_user(
    session: SessionDep, current_user: CurrentUser, bot_user_id: uuid.UUID
) -> BotUser:
    bot = session.get(BotUser, bot_user_id)
    if not bot or bot.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Bot user not found")
    return bot


@router.get("/", response_model=BotUsersPublic)
def read_bot_users(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the current user's bot users, with their scopes, oldest first.
    """
    count = session.exec(
        select(func.count())
        .select_from(BotUser)
        .where(BotUser.owner_id == current_user.id)
    ).one()
    bots = session.exec(
        select(BotUser)
        .where(BotUser.owner_id == current_user.id)
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
        get_project_of(session, current_user.id, project_id)
    bot = crud.create_bot_user(
        session=session, bot_user_create=bot_user_in, owner_id=current_user.id
    )
    return _public(
        bot, crud.get_bot_user_project_ids(session=session, bot_ids=[bot.id])[bot.id]
    )


@router.post("/{bot_user_id}/token", response_model=BotTokenIssued)
def issue_bot_user_token(
    *, session: SessionDep, current_user: CurrentUser, bot_user_id: uuid.UUID
) -> Any:
    """
    Issue the bot user's token.

    This response is the only place the token appears: only its digest is
    stored, and no endpoint returns it again (FR-08.13). A bot user that
    already holds a token is refused another.
    """
    bot = _get_owned_bot_user(session, current_user, bot_user_id)
    if bot.token_hash is not None:
        raise HTTPException(
            status_code=TOKEN_ALREADY_ISSUED_STATUS,
            detail={
                "code": TOKEN_ALREADY_ISSUED_CODE,
                "message": (
                    f"“{bot.name}” already has a token. A bot user holds one "
                    "token at a time."
                ),
            },
        )
    token = crud.issue_bot_token(session=session, bot=bot)
    return BotTokenIssued(bot_user_id=bot.id, token=token)
