import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

ALGORITHM = "HS256"


def fernet_for(key: str, info: bytes) -> Fernet:
    """
    A Fernet cipher for an installation key, which can be any string: it is run
    through HKDF, with `info` naming what it protects so two keys that happen
    to be equal still give unrelated ciphers.
    """
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        key.encode()
    )
    return Fernet(base64.urlsafe_b64encode(derived))


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


def session_token(user_id: uuid.UUID, session_version: int) -> str:
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
