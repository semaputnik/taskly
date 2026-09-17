import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy import or_, update
from sqlmodel import Session, col, select

from app import activity
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.storage import AttachmentStorage, LocalAttachmentStorage
from app.models import BotUser, BotUserProject, TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


# A bot user reaching an endpoint only a human may call. Refused for what the
# caller is rather than for a permission it lacks: no scope a user could set
# would let it through (FR-07.3).
HUMAN_ONLY_STATUS = 403
HUMAN_ONLY_CODE = "human_only"


# How fine-grained "last used" is. Recording every request would be a write on
# every bot call; at most one per bot user per interval tells the user just as
# much about whether an integration is alive (FR-08.17).
BOT_TOKEN_USE_RESOLUTION = timedelta(minutes=1)


def _authenticate_bot(session: Session, token: str) -> BotUser:
    """
    The bot user a token belongs to. A token that matches nothing — unknown,
    revoked — one that has expired, and one of a deleted bot user are all
    refused the same way, before anything else about the request is looked
    at, so the refusal says nothing about why (FR-08.14, FR-08.15, FR-08.20).
    """
    bot = session.exec(
        select(BotUser).where(BotUser.token_hash == security.hash_bot_token(token))
    ).first()
    now = datetime.now(UTC)
    if (
        not bot
        or bot.deleted_at is not None
        or (bot.token_expires_at is not None and bot.token_expires_at <= now)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _record_bot_token_use(bot, now)
    return bot


def _record_bot_token_use(bot: BotUser, now: datetime) -> None:
    """
    Note that the bot user's token was just used, if the last note is older
    than `BOT_TOKEN_USE_RESOLUTION`.

    Written on its own connection and committed at once, rather than in the
    request's transaction: the note is true whatever the request goes on to do,
    and a bot's requests do not queue up behind each other's row lock.
    """
    last_used = bot.token_last_used_at
    if last_used is not None and now - last_used < BOT_TOKEN_USE_RESOLUTION:
        return
    with engine.begin() as connection:
        connection.execute(
            update(BotUser)
            .where(
                col(BotUser.id) == bot.id,
                or_(
                    col(BotUser.token_last_used_at).is_(None),
                    col(BotUser.token_last_used_at) < now - BOT_TOKEN_USE_RESOLUTION,
                ),
            )
            .values(token_last_used_at=now)
        )


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """
    The human user making the request. A bot user's token is refused here,
    which is what keeps every endpoint that depends on this out of a bot's
    reach.
    """
    if security.is_bot_token(token):
        _authenticate_bot(session, token)
        raise HTTPException(
            status_code=HUMAN_ONLY_STATUS,
            detail={
                "code": HUMAN_ONLY_CODE,
                "message": "Bot users cannot use this endpoint.",
            },
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        # A token can outlive the account it names — the user was recreated
        # with a new id, or removed. That is a credentials problem, not a
        # missing resource: 401 lets the frontend's existing "clear the token
        # and go to /login" handling recover on its own, rather than getting
        # stuck replaying a 404 against every authenticated request.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    # The request's session is shared with the route it authenticates, so
    # whatever the route changes is logged as this user's doing (FR-10.2).
    activity.set_actor(session, user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(frozen=True)
class Caller:
    """
    Whoever is making a request to an endpoint that humans and bot users may
    both call.

    `owner_id` is whose data the request reaches: the user's own, or the
    owning user's for a bot, which never reaches anyone else's. For a bot,
    `bot` and the projects of its scope come along, so Task access
    (`app.api.access`) can narrow what it reaches.
    """

    owner_id: uuid.UUID
    bot: BotUser | None = None
    project_ids: frozenset[uuid.UUID] = frozenset()


def get_caller(session: SessionDep, token: TokenDep) -> Caller:
    if not security.is_bot_token(token):
        return Caller(owner_id=get_current_user(session, token).id)

    bot = _authenticate_bot(session, token)
    # Whatever a bot's request changes is logged as the bot's doing, never as
    # its owner's (FR-10.2).
    activity.set_bot_actor(session, bot.id)
    project_ids = session.exec(
        select(BotUserProject.project_id).where(BotUserProject.bot_user_id == bot.id)
    ).all()
    return Caller(owner_id=bot.owner_id, bot=bot, project_ids=frozenset(project_ids))


CallerDep = Annotated[Caller, Depends(get_caller)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


@lru_cache
def _local_attachment_storage() -> LocalAttachmentStorage:
    return LocalAttachmentStorage(Path(settings.ATTACHMENTS_DIR))


def get_attachment_storage() -> AttachmentStorage:
    return _local_attachment_storage()


AttachmentStorageDep = Annotated[AttachmentStorage, Depends(get_attachment_storage)]
