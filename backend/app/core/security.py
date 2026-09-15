import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


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
