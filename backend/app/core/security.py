import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(
    subject: str | Any, expires_delta: timedelta, session_version: int
) -> str:
    """
    A session token for a user. It carries their session version, so signing
    out everywhere ends it (FR-12.13).
    """
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject), "sv": session_version}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def session_token(user_id: Any, session_version: int) -> str:
    """A session token with the lifetime every sign-in gets (FR-12.11)."""
    return create_access_token(
        user_id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        session_version=session_version,
    )


# Bot user tokens are opaque random strings, not JWTs: the prefix is how a
# request is told apart as a bot's before anything is decoded, and it makes a
# leaked token recognisable for what it is.
BOT_TOKEN_PREFIX = "taskly_bot_"


def generate_bot_token() -> str:
    return BOT_TOKEN_PREFIX + secrets.token_urlsafe(32)


def is_bot_token(token: str) -> bool:
    return token.startswith(BOT_TOKEN_PREFIX)


def hash_bot_token(token: str) -> str:
    """
    The form a bot token is stored and looked up in. The token carries 256
    random bits, so a fast digest is as safe to store as a slow password hash
    would be, and it can be indexed.
    """
    return hashlib.sha256(token.encode()).hexdigest()
