"""
Accounts and passkeys: sign-in, registration, recovery and the WebAuthn ceremony
state behind them (FR-09, FR-12).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import EmailStr, StringConstraints
from sqlalchemy import DateTime, LargeBinary
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from .shared import get_datetime_utc


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to create a user with. There is no password: an account's only
# credentials are its passkeys (FR-12.1), made in the same step (FR-12.2).
class UserCreate(UserBase):
    pass


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Carried in every session token this user is issued and compared on every
    # request: raising it ends every session at once (FR-12.13, FR-12.14).
    session_version: int = 0
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UserListed(UserPublic):
    """
    An account as the superuser's list shows it: the account fields, how many
    passkeys it holds, and when one of them last signed it in (FR-09.2). Nothing
    about what the account holds or does (FR-10.7).
    """

    passkey_count: int
    last_sign_in_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserListed]
    count: int


class Passkey(SQLModel, table=True):
    """
    A WebAuthn credential a user signs in with (FR-12.1). Taskly holds only
    its public half; the private key stays on the user's device or in their
    password manager.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    credential_id: bytes = Field(sa_type=LargeBinary, unique=True, index=True)
    public_key: bytes = Field(sa_type=LargeBinary)
    sign_count: int = 0
    # What the browser reported it can reach the authenticator over, handed
    # back when the same passkey is asked for, so the browser offers it the
    # right way.
    transports: list[str] = Field(default_factory=list, sa_type=JSONB)
    # Given from the browser and device that made it, never typed (FR-12.6).
    name: str = Field(max_length=255)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class PasskeyPublic(SQLModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None


# A passkey's name is given from the browser and device that made it, and the
# owner may replace it with words they recognise (FR-12.6). Blank is refused.
PasskeyName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class PasskeyRename(SQLModel):
    name: PasskeyName


class PasskeysPublic(SQLModel):
    data: list[PasskeyPublic]
    count: int


class ChallengeKind(StrEnum):
    """What the ceremony a challenge belongs to is for."""

    # Creating an account with its first passkey (FR-12.2).
    REGISTRATION = "registration"
    # Signing in (FR-12.3).
    SIGN_IN = "sign_in"
    # A fresh confirmation with one of the user's passkeys (FR-12.7, FR-12.16).
    CONFIRMATION = "confirmation"
    # Adding a passkey to an account that is already signed in (FR-12.7).
    NEW_PASSKEY = "new_passkey"
    # Creating a passkey with a recovery code (FR-12.17).
    RECOVERY = "recovery"


class WebAuthnChallenge(SQLModel, table=True):
    """
    The server's half of one passkey ceremony: issued with the options the
    browser is handed, taken once when the browser answers, and refused
    after five minutes (FR-12.10).
    """

    __tablename__ = "webauthn_challenge"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    kind: ChallengeKind = Field(
        sa_type=SAEnum(  # type: ignore
            ChallengeKind,
            name="challengekind",
            values_callable=lambda kinds: [kind.value for kind in kinds],
        )
    )
    challenge: bytes = Field(sa_type=LargeBinary, unique=True, index=True)
    # Whose ceremony it is. Empty for signing in, where nobody is known yet,
    # and for registering, where the account does not exist yet.
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="CASCADE"
    )
    # Registering only: the email asked for and the id the account will be
    # given, which the new passkey is made under.
    email: str | None = Field(default=None, max_length=255)
    user_handle: uuid.UUID | None = None
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore


class RecoveryCode(SQLModel, table=True):
    """
    The one live recovery code a user may hold (FR-12.16). Kept as a digest
    only; the code itself is shown once, when it is issued.
    """

    __tablename__ = "recovery_code"

    user_id: uuid.UUID = Field(
        foreign_key="user.id", primary_key=True, ondelete="CASCADE"
    )
    digest: str = Field(max_length=64)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    failed_attempts: int = 0


class RecoveryCodeIssued(SQLModel):
    code: str
    expires_at: datetime


class RegistrationStart(SQLModel):
    email: EmailStr = Field(max_length=255)


class RecoveryStart(SQLModel):
    email: EmailStr = Field(max_length=255)
    code: str = Field(max_length=64)


class PasskeyCredential(SQLModel):
    """
    The browser's answer to a passkey ceremony, as WebAuthn's
    `PublicKeyCredential.toJSON()` gives it.
    """

    credential: dict[str, Any]


class Confirmation(SQLModel):
    """
    A fresh assertion with one of the caller's own passkeys, answering a
    confirmation challenge (FR-12.7, FR-12.16).
    """

    confirmation: dict[str, Any]
