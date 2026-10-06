"""
Signing in with passkeys (F-12, ADR-0007).

Every way a human user proves who they are runs through here: registering an
account with its first passkey, signing in, confirming a sensitive change with
a fresh assertion, adding and removing passkeys, signing out everywhere, and
recovering an account with a code the superuser issued.

A ceremony has two halves. The first hands the browser its options and keeps a
challenge; the second takes that challenge back exactly once, whatever the
outcome, and checks the browser's answer against it (FR-12.10). The challenge
travels inside the answer itself, so the client never has to carry anything
but the credential back.
"""

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlmodel import Session, col, delete, func, select
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidCBORData,
    InvalidJSONStructure,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app import crud
from app.core.config import settings
from app.models import (
    ChallengeKind,
    Passkey,
    RecoveryCode,
    RecoveryCodeIssued,
    User,
    UserCreate,
    WebAuthnChallenge,
)
from app.passkey_names import passkey_name

# How long either half of a ceremony waits for the other (FR-12.10). Also the
# timeout the browser is given, so it stops asking when the server stops
# listening.
CHALLENGE_LIFETIME = timedelta(minutes=5)

RECOVERY_CODE_LIFETIME = timedelta(hours=24)
RECOVERY_CODE_MAX_ATTEMPTS = 5
# Crockford's base32: no I, L, O or U, so a code read out over the phone is
# not mistaken for another. Sixteen characters carry 80 random bits.
_RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_RECOVERY_CODE_LENGTH = 16


class PasskeyError(Exception):
    """A ceremony or a change the caller is refused. The message is safe to show."""


class EmailTaken(PasskeyError):
    def __init__(self) -> None:
        super().__init__("An account with this email already exists.")


class SignInRefused(PasskeyError):
    # One message for every reason, so a refusal says nothing about which
    # passkeys or accounts exist (FR-12.3).
    def __init__(self) -> None:
        super().__init__("This passkey could not sign you in. Try again.")


class ConfirmationRefused(PasskeyError):
    def __init__(self) -> None:
        super().__init__(
            "The passkey confirmation did not go through. Confirm again with "
            "one of this account's passkeys."
        )


class CeremonyFailed(PasskeyError):
    def __init__(self) -> None:
        super().__init__("The passkey could not be created. Try again.")


class RecoveryRefused(PasskeyError):
    # A wrong code, a spent one and an expired one read the same (FR-12.18),
    # and so does an email with no account behind it.
    def __init__(self) -> None:
        super().__init__("This email and recovery code do not match a live code.")


class LastPasskey(PasskeyError):
    def __init__(self) -> None:
        super().__init__(
            "This is the account's only passkey. Add another before removing it."
        )


class PasskeyNotFound(PasskeyError):
    def __init__(self) -> None:
        super().__init__("Passkey not found.")


class UserNotFound(PasskeyError):
    def __init__(self) -> None:
        super().__init__("User not found")


class OwnRecoveryCode(PasskeyError):
    def __init__(self) -> None:
        super().__init__(
            "You cannot issue a recovery code for your own account. Run the "
            "recovery command on the server instead."
        )


# --- The relying party ------------------------------------------------------


def expected_origin() -> str:
    """
    The origin a passkey ceremony must come from: the installation's public
    address and nothing else (FR-12.4).
    """
    parts = urlsplit(settings.FRONTEND_HOST)
    return f"{parts.scheme}://{parts.netloc}"


def rp_id() -> str:
    """The hostname every passkey is bound to (FR-12.4)."""
    return urlsplit(settings.FRONTEND_HOST).hostname or "localhost"


# --- Registering ------------------------------------------------------------


def start_registration(session: Session, *, email: str) -> dict[str, Any]:
    """The options for creating a new account's first passkey (FR-12.2)."""
    if crud.get_user_by_email(session=session, email=email):
        raise EmailTaken()
    user_handle = uuid.uuid4()
    challenge = _issue(
        session,
        ChallengeKind.REGISTRATION,
        email=email,
        user_handle=user_handle,
    )
    return _registration_options(
        challenge=challenge, user_handle=user_handle, email=email, exclude=[]
    )


def finish_registration(
    session: Session, *, credential: dict[str, Any], user_agent: str | None
) -> User:
    """
    Create the account the registration was started for, together with its
    first passkey. The person who registers the installation's first
    superuser address while no superuser exists becomes it (FR-09.6).
    """
    row = _take(session, ChallengeKind.REGISTRATION, credential)
    if row is None or row.email is None or row.user_handle is None:
        raise CeremonyFailed()
    verified = _verify_registration(credential, row.challenge)
    if crud.get_user_by_email(session=session, email=row.email):
        raise EmailTaken()
    is_superuser = (
        row.email == settings.FIRST_SUPERUSER and find_superuser(session) is None
    )
    user = crud.create_user(
        session=session,
        user_create=UserCreate(email=row.email, is_superuser=is_superuser),
        user_id=row.user_handle,
        commit=False,
    )
    # Registering signs in with the new passkey: that is its first use.
    session.add(_new_passkey(user.id, credential, verified, user_agent, used=True))
    session.commit()
    session.refresh(user)
    return user


def find_superuser(session: Session) -> User | None:
    """The installation's superuser, if one has registered yet (FR-09.6)."""
    return session.exec(
        select(User).where(User.is_superuser == True)  # noqa: E712
    ).first()


# --- Signing in -------------------------------------------------------------


def start_sign_in(session: Session) -> dict[str, Any]:
    """
    The options for signing in. They name no account and no passkey: the
    browser offers whatever it holds for this hostname (FR-12.3).
    """
    challenge = _issue(session, ChallengeKind.SIGN_IN)
    return _authentication_options(challenge=challenge, allow=[])


def finish_sign_in(session: Session, *, credential: dict[str, Any]) -> User:
    row = _take(session, ChallengeKind.SIGN_IN, credential)
    if row is None:
        raise SignInRefused()
    passkey = _passkey_for(session, credential)
    if passkey is None:
        raise SignInRefused()
    user = session.get(User, passkey.user_id)
    if user is None or not user.is_active:
        raise SignInRefused()
    if not _verify_assertion(credential, row.challenge, passkey):
        raise SignInRefused()
    session.commit()
    return user


# --- Confirming with a fresh assertion --------------------------------------


def start_confirmation(session: Session, *, user: User) -> dict[str, Any]:
    """
    The options for confirming a change with one of the user's own passkeys,
    at this moment (FR-12.7, FR-12.16).
    """
    challenge = _issue(session, ChallengeKind.CONFIRMATION, user_id=user.id)
    return _authentication_options(
        challenge=challenge, allow=_passkeys_of(session, user.id)
    )


def confirm(session: Session, *, user: User, credential: dict[str, Any]) -> None:
    """
    Check a fresh assertion made by one of the user's passkeys against a
    confirmation challenge issued to them. The session that sent it is not
    enough on its own (FR-12.7).
    """
    row = _take(session, ChallengeKind.CONFIRMATION, credential)
    if row is None or row.user_id != user.id:
        raise ConfirmationRefused()
    passkey = _passkey_for(session, credential)
    if passkey is None or passkey.user_id != user.id:
        raise ConfirmationRefused()
    if not _verify_assertion(credential, row.challenge, passkey):
        raise ConfirmationRefused()
    session.commit()


# --- Managing passkeys ------------------------------------------------------


def list_passkeys(session: Session, *, user: User) -> list[Passkey]:
    return _passkeys_of(session, user.id)


def start_new_passkey(
    session: Session, *, user: User, confirmation: dict[str, Any]
) -> dict[str, Any]:
    """
    The options for adding a passkey to a signed-in account, once the user has
    confirmed with one they already hold (FR-12.7).
    """
    confirm(session, user=user, credential=confirmation)
    challenge = _issue(session, ChallengeKind.NEW_PASSKEY, user_id=user.id)
    return _registration_options(
        challenge=challenge,
        user_handle=user.id,
        email=user.email,
        exclude=_passkeys_of(session, user.id),
    )


def finish_new_passkey(
    session: Session,
    *,
    user: User,
    credential: dict[str, Any],
    user_agent: str | None,
) -> Passkey:
    row = _take(session, ChallengeKind.NEW_PASSKEY, credential)
    if row is None or row.user_id != user.id:
        raise CeremonyFailed()
    verified = _verify_registration(credential, row.challenge)
    passkey = _new_passkey(user.id, credential, verified, user_agent)
    session.add(passkey)
    session.commit()
    session.refresh(passkey)
    return passkey


def rename_passkey(
    session: Session, *, user: User, passkey_id: uuid.UUID, name: str
) -> Passkey:
    """
    Give one of the user's passkeys a name they recognise (FR-12.6). Naming is
    a label and opens nothing, so the session alone is enough.
    """
    passkey = session.get(Passkey, passkey_id)
    if passkey is None or passkey.user_id != user.id:
        raise PasskeyNotFound()
    passkey.name = name
    session.add(passkey)
    session.commit()
    session.refresh(passkey)
    return passkey


def remove_passkey(
    session: Session,
    *,
    user: User,
    passkey_id: uuid.UUID,
    confirmation: dict[str, Any],
) -> None:
    """
    Remove one of the user's passkeys, never the last (FR-12.8). The sessions
    it opened stay open (FR-12.9).
    """
    passkey = session.get(Passkey, passkey_id)
    if passkey is None or passkey.user_id != user.id:
        raise PasskeyNotFound()
    confirm(session, user=user, credential=confirmation)
    # Hold the account while counting, so two removals at once cannot each
    # see a passkey left and take the last one between them.
    _lock_user(session, user.id)
    if len(_passkeys_of(session, user.id)) <= 1:
        session.rollback()
        raise LastPasskey()
    session.delete(passkey)
    session.commit()


def passkey_summaries(
    session: Session, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, datetime | None]]:
    """
    For each of the accounts: how many passkeys it holds and when one last
    signed it in, in one query. An account with none is absent.
    """
    rows = session.exec(
        select(
            Passkey.user_id,
            func.count(),
            func.max(col(Passkey.last_used_at)),
        )
        .where(col(Passkey.user_id).in_(user_ids))  # type: ignore[attr-defined]
        .group_by(Passkey.user_id)
    ).all()
    return {user_id: (count, last) for user_id, count, last in rows}


def sign_out_everywhere(session: Session, *, user: User) -> None:
    """
    End every session of the account at once (FR-12.13). Each is refused from
    its next request on, because its token carries the version this replaces.
    """
    _end_every_session(session, user)
    session.commit()


def _end_every_session(session: Session, user: User) -> None:
    user.session_version += 1
    session.add(user)


# --- Recovery ---------------------------------------------------------------


def issue_recovery_code(session: Session, *, user: User) -> RecoveryCodeIssued:
    """
    Give the user a new recovery code, replacing any live one (FR-12.16). The
    code is returned here and nowhere else; only its digest is kept.
    """
    code = "".join(
        secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_CODE_LENGTH)
    )
    expires_at = datetime.now(UTC) + RECOVERY_CODE_LIFETIME
    existing = session.get(RecoveryCode, user.id)
    if existing is not None:
        session.delete(existing)
        session.flush()
    session.add(
        RecoveryCode(
            user_id=user.id, digest=_recovery_digest(code), expires_at=expires_at
        )
    )
    session.commit()
    return RecoveryCodeIssued(code=format_recovery_code(code), expires_at=expires_at)


def issue_recovery_code_for(
    session: Session,
    *,
    superuser: User,
    user_id: uuid.UUID,
    confirmation: dict[str, Any],
) -> RecoveryCodeIssued:
    """
    The superuser issuing a code for someone else, confirmed with their own
    passkey (FR-12.16). Their own account is refused (FR-12.19).
    """
    if user_id == superuser.id:
        raise OwnRecoveryCode()
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFound()
    confirm(session, user=superuser, credential=confirmation)
    return issue_recovery_code(session, user=user)


def format_recovery_code(code: str) -> str:
    """The code in groups of four, the way it is shown and read out."""
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def start_recovery(session: Session, *, email: str, code: str) -> dict[str, Any]:
    """
    The options for creating a new passkey with a recovery code (FR-12.17).
    A wrong code counts as a miss, and the fifth miss burns it (FR-12.18).
    """
    user = crud.get_user_by_email(session=session, email=email)
    if user is None or not user.is_active:
        raise RecoveryRefused()
    # Locked until the miss is counted, so tries made at once are each
    # counted and the fifth still burns the code.
    recovery = _locked_recovery_code(session, user.id)
    if recovery is None:
        session.rollback()
        raise RecoveryRefused()
    if recovery.expires_at <= datetime.now(UTC):
        session.delete(recovery)
        session.commit()
        raise RecoveryRefused()
    if not hmac.compare_digest(recovery.digest, _recovery_digest(code)):
        recovery.failed_attempts += 1
        if recovery.failed_attempts >= RECOVERY_CODE_MAX_ATTEMPTS:
            session.delete(recovery)
        else:
            session.add(recovery)
        session.commit()
        raise RecoveryRefused()
    challenge = _issue(session, ChallengeKind.RECOVERY, user_id=user.id)
    return _registration_options(
        challenge=challenge,
        user_handle=user.id,
        email=user.email,
        exclude=_passkeys_of(session, user.id),
    )


def finish_recovery(
    session: Session, *, credential: dict[str, Any], user_agent: str | None
) -> User:
    """
    Add the new passkey, spend the code and sign the account out everywhere
    (FR-12.14, FR-12.17). The passkeys the account already had stay.
    """
    row = _take(session, ChallengeKind.RECOVERY, credential)
    if row is None or row.user_id is None:
        raise RecoveryRefused()
    user = session.get(User, row.user_id)
    recovery = _locked_recovery_code(session, row.user_id)
    if (
        user is None
        or not user.is_active
        or recovery is None
        or recovery.expires_at <= datetime.now(UTC)
    ):
        session.rollback()
        raise RecoveryRefused()
    verified = _verify_registration(credential, row.challenge)
    session.add(_new_passkey(user.id, credential, verified, user_agent, used=True))
    session.delete(recovery)
    _end_every_session(session, user)
    session.commit()
    session.refresh(user)
    return user


def _recovery_digest(code: str) -> str:
    """
    The form a code is stored and compared in. Read leniently: case, spaces
    and the dashes it is shown with do not matter. Eighty random bits make a
    fast digest enough, as for bot tokens.
    """
    normalised = "".join(ch for ch in code.upper() if ch.isalnum())
    return hashlib.sha256(normalised.encode()).hexdigest()


# --- Challenges -------------------------------------------------------------


def _issue(
    session: Session,
    kind: ChallengeKind,
    *,
    user_id: uuid.UUID | None = None,
    email: str | None = None,
    user_handle: uuid.UUID | None = None,
) -> bytes:
    now = datetime.now(UTC)
    # Ceremonies that were started and never finished leave their challenge
    # behind; clearing the expired ones here keeps the table to the few that
    # can still be answered.
    session.exec(
        delete(WebAuthnChallenge).where(col(WebAuthnChallenge.expires_at) <= now)
    )
    challenge = secrets.token_bytes(32)
    session.add(
        WebAuthnChallenge(
            kind=kind,
            challenge=challenge,
            user_id=user_id,
            email=email,
            user_handle=user_handle,
            expires_at=now + CHALLENGE_LIFETIME,
        )
    )
    session.commit()
    return challenge


def _take(
    session: Session, kind: ChallengeKind, credential: dict[str, Any]
) -> WebAuthnChallenge | None:
    """
    The challenge a browser's answer was made for, removed so it cannot be
    answered twice (FR-12.10). None if the answer names no live challenge of
    this kind. The removal is committed before anything is verified, so a
    failed answer spends the challenge too.
    """
    challenge = _challenge_in(credential)
    if challenge is None:
        return None
    # One statement that both finds and removes the row, so of two requests
    # answering with the same challenge at once only one gets it back.
    row: WebAuthnChallenge | None = session.exec(
        delete(WebAuthnChallenge)
        .where(col(WebAuthnChallenge.challenge) == challenge)
        .returning(WebAuthnChallenge)
    ).scalar_one_or_none()
    if row is not None:
        # Gone from the table, so kept apart from the session: the commit
        # would otherwise expire it, and there is no row to reload it from.
        session.expunge(row)
    session.commit()
    if row is None:
        return None
    if row.kind != kind or row.expires_at <= datetime.now(UTC):
        return None
    return row


def _challenge_in(credential: dict[str, Any]) -> bytes | None:
    try:
        client_data = json.loads(
            base64url_to_bytes(credential["response"]["clientDataJSON"])
        )
        return base64url_to_bytes(client_data["challenge"])
    except KeyError, TypeError, ValueError:
        return None


# --- WebAuthn ---------------------------------------------------------------


def _registration_options(
    *,
    challenge: bytes,
    user_handle: uuid.UUID,
    email: str,
    exclude: list[Passkey],
) -> dict[str, Any]:
    options = generate_registration_options(
        rp_id=rp_id(),
        rp_name=settings.PROJECT_NAME,
        user_name=email,
        user_id=user_handle.bytes,
        user_display_name=email,
        challenge=challenge,
        timeout=int(CHALLENGE_LIFETIME.total_seconds() * 1000),
        # Discoverable, so signing in asks for nothing (FR-12.3), and verified
        # on the device every time (FR-12.5).
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[_descriptor(passkey) for passkey in exclude],
    )
    result: dict[str, Any] = json.loads(options_to_json(options))
    return result


def _authentication_options(
    *, challenge: bytes, allow: list[Passkey]
) -> dict[str, Any]:
    options = generate_authentication_options(
        rp_id=rp_id(),
        challenge=challenge,
        timeout=int(CHALLENGE_LIFETIME.total_seconds() * 1000),
        allow_credentials=[_descriptor(passkey) for passkey in allow],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    result: dict[str, Any] = json.loads(options_to_json(options))
    return result


def _descriptor(passkey: Passkey) -> PublicKeyCredentialDescriptor:
    transports = []
    for transport in passkey.transports:
        try:
            transports.append(AuthenticatorTransport(transport))
        except ValueError:
            continue
    return PublicKeyCredentialDescriptor(
        id=passkey.credential_id, transports=transports or None
    )


@dataclass(frozen=True)
class _Registration:
    credential_id: bytes
    public_key: bytes
    sign_count: int


def _verify_registration(credential: dict[str, Any], challenge: bytes) -> _Registration:
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse, InvalidJSONStructure, InvalidCBORData:
        raise CeremonyFailed()
    return _Registration(
        verified.credential_id, verified.credential_public_key, verified.sign_count
    )


def _verify_assertion(
    credential: dict[str, Any], challenge: bytes, passkey: Passkey
) -> bool:
    """
    Check an assertion made by `passkey`, and note that it was used. The
    caller commits.
    """
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse, InvalidJSONStructure, InvalidCBORData:
        return False
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(UTC)
    return True


def _passkey_for(session: Session, credential: dict[str, Any]) -> Passkey | None:
    try:
        credential_id = base64url_to_bytes(credential["rawId"])
    except KeyError, TypeError, ValueError:
        return None
    return session.exec(
        select(Passkey).where(Passkey.credential_id == credential_id)
    ).first()


def _lock_user(session: Session, user_id: uuid.UUID) -> None:
    session.exec(select(User.id).where(User.id == user_id).with_for_update()).one()


def _locked_recovery_code(session: Session, user_id: uuid.UUID) -> RecoveryCode | None:
    return session.exec(
        select(RecoveryCode).where(RecoveryCode.user_id == user_id).with_for_update()
    ).first()


def _passkeys_of(session: Session, user_id: uuid.UUID) -> list[Passkey]:
    return list(
        session.exec(
            select(Passkey)
            .where(Passkey.user_id == user_id)
            .order_by(col(Passkey.created_at))
        ).all()
    )


def _new_passkey(
    user_id: uuid.UUID,
    credential: dict[str, Any],
    verified: _Registration,
    user_agent: str | None,
    *,
    used: bool = False,
) -> Passkey:
    transports = credential.get("response", {}).get("transports") or []
    return Passkey(
        user_id=user_id,
        credential_id=verified.credential_id,
        public_key=verified.public_key,
        sign_count=verified.sign_count,
        transports=[str(transport) for transport in transports],
        name=passkey_name(user_agent),
        last_used_at=datetime.now(UTC) if used else None,
    )
