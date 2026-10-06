"""
Managing passkeys, signing out everywhere, and recovering an account
(FR-12.6–FR-12.19).
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session, col, select

from app import superuser_recovery_code
from app.core.config import settings
from app.models import Passkey, RecoveryCode, User
from app.passkeys import RECOVERY_CODE_MAX_ATTEMPTS
from tests.utils.passkey import Authenticator, b64
from tests.utils.user import create_random_user, give_passkey, sign_in

API = settings.API_V1_STR
Headers = dict[str, str]


def _confirm(client: TestClient, headers: Headers, authenticator: Authenticator) -> Any:
    """A fresh assertion with `authenticator`, answering a confirmation challenge."""
    r = client.post(f"{API}/users/me/confirmation/options", headers=headers)
    assert r.status_code == 200, r.text
    return authenticator.get_json(r.json())


def _signed_in(client: TestClient, db: Session) -> tuple[User, Authenticator, Headers]:
    user = create_random_user(db)
    authenticator = give_passkey(db, user)
    return user, authenticator, sign_in(client, authenticator)


def _add_passkey(
    client: TestClient,
    headers: Headers,
    current: Authenticator,
    user_agent: str = "testclient",
) -> tuple[Authenticator, Any]:
    new = Authenticator()
    options = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": _confirm(client, headers, current)},
    ).json()
    r = client.post(
        f"{API}/users/me/passkeys",
        headers={**headers, "User-Agent": user_agent},
        json={"credential": new.create_json(options)},
    )
    return new, r


def _passkey_ids(client: TestClient, headers: Headers) -> list[str]:
    r = client.get(f"{API}/users/me/passkeys", headers=headers)
    return [passkey["id"] for passkey in r.json()["data"]]


# --- Listing ----------------------------------------------------------------


def test_settings_lists_the_users_own_passkeys(client: TestClient, db: Session) -> None:
    user, _, headers = _signed_in(client, db)
    _signed_in(client, db)

    r = client.get(f"{API}/users/me/passkeys", headers=headers)

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    [passkey] = body["data"]
    assert set(passkey) == {"id", "name", "created_at", "last_used_at"}
    assert passkey["name"] == "Test passkey"
    assert passkey["last_used_at"] is not None
    stored = db.exec(select(Passkey).where(Passkey.user_id == user.id)).one()
    assert passkey["id"] == str(stored.id)


# --- Confirming -------------------------------------------------------------


def test_confirmation_asks_for_the_users_own_passkeys(
    client: TestClient, db: Session
) -> None:
    _, authenticator, headers = _signed_in(client, db)

    r = client.post(f"{API}/users/me/confirmation/options", headers=headers)

    allowed = [item["id"] for item in r.json()["allowCredentials"]]
    assert allowed == [b64(authenticator.credential_id)]
    assert r.json()["userVerification"] == "required"


# --- Adding -----------------------------------------------------------------


def test_adding_a_passkey_after_confirming(client: TestClient, db: Session) -> None:
    _, current, headers = _signed_in(client, db)

    new, r = _add_passkey(
        client,
        headers,
        current,
        user_agent="Mozilla/5.0 (iPad; CPU OS 18_0) Version/18.0 Safari/604.1",
    )

    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Safari on iPad"
    # Added, not yet signed in with.
    assert r.json()["last_used_at"] is None
    assert len(_passkey_ids(client, headers)) == 2
    # The new one signs in too.
    sign_in(client, new)


def test_adding_a_passkey_without_a_fresh_confirmation_is_refused(
    client: TestClient, db: Session
) -> None:
    _, current, headers = _signed_in(client, db)
    confirmation = _confirm(client, headers, current)
    r = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": confirmation},
    )
    assert r.status_code == 200

    # The same confirmation a second time: the session alone is not enough.
    r = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": confirmation},
    )

    assert r.status_code == 400
    assert "confirm" in r.json()["detail"].lower()


def test_a_confirmation_with_someone_elses_passkey_is_refused(
    client: TestClient, db: Session
) -> None:
    _, _, headers = _signed_in(client, db)
    _, theirs, _ = _signed_in(client, db)
    r = client.post(f"{API}/users/me/confirmation/options", headers=headers)
    # Their authenticator answers our challenge.
    confirmation = theirs.get_json(r.json())

    r = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": confirmation},
    )

    assert r.status_code == 400


def test_a_confirmation_issued_to_someone_else_is_refused(
    client: TestClient, db: Session
) -> None:
    _, _, headers = _signed_in(client, db)
    _, theirs, their_headers = _signed_in(client, db)
    confirmation = _confirm(client, their_headers, theirs)

    r = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": confirmation},
    )

    assert r.status_code == 400


def test_a_confirmation_without_user_verification_is_refused(
    client: TestClient, db: Session
) -> None:
    _, current, headers = _signed_in(client, db)
    current.user_verified = False

    r = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": _confirm(client, headers, current)},
    )

    assert r.status_code == 400


def test_a_new_passkey_answer_must_come_from_the_same_account(
    client: TestClient, db: Session
) -> None:
    _, current, headers = _signed_in(client, db)
    _, _, other_headers = _signed_in(client, db)
    options = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": _confirm(client, headers, current)},
    ).json()

    r = client.post(
        f"{API}/users/me/passkeys",
        headers=other_headers,
        json={"credential": Authenticator().create_json(options)},
    )

    assert r.status_code == 400
    assert len(_passkey_ids(client, other_headers)) == 1


def test_adding_a_passkey_the_account_already_holds_is_excluded(
    client: TestClient, db: Session
) -> None:
    _, current, headers = _signed_in(client, db)

    options = client.post(
        f"{API}/users/me/passkeys/options",
        headers=headers,
        json={"confirmation": _confirm(client, headers, current)},
    ).json()

    excluded = [item["id"] for item in options["excludeCredentials"]]
    assert excluded == [b64(current.credential_id)]


# --- Renaming ---------------------------------------------------------------


def test_renaming_a_passkey_needs_only_the_session(
    client: TestClient, db: Session
) -> None:
    _, _, headers = _signed_in(client, db)
    [passkey_id] = _passkey_ids(client, headers)

    r = client.patch(
        f"{API}/users/me/passkeys/{passkey_id}",
        headers=headers,
        json={"name": "  Work laptop "},
    )

    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Work laptop"
    [listed] = client.get(f"{API}/users/me/passkeys", headers=headers).json()["data"]
    assert listed["name"] == "Work laptop"


def test_a_blank_passkey_name_is_refused(client: TestClient, db: Session) -> None:
    _, _, headers = _signed_in(client, db)
    [passkey_id] = _passkey_ids(client, headers)

    r = client.patch(
        f"{API}/users/me/passkeys/{passkey_id}", headers=headers, json={"name": "  "}
    )

    assert r.status_code == 422
    [listed] = client.get(f"{API}/users/me/passkeys", headers=headers).json()["data"]
    assert listed["name"] == "Test passkey"


def test_someone_elses_passkey_cannot_be_renamed(
    client: TestClient, db: Session
) -> None:
    _, _, headers = _signed_in(client, db)
    _, _, their_headers = _signed_in(client, db)
    [their_id] = _passkey_ids(client, their_headers)

    r = client.patch(
        f"{API}/users/me/passkeys/{their_id}", headers=headers, json={"name": "Mine"}
    )

    assert r.status_code == 404
    [listed] = client.get(f"{API}/users/me/passkeys", headers=their_headers).json()[
        "data"
    ]
    assert listed["name"] == "Test passkey"


# --- Removing ---------------------------------------------------------------


def test_removing_a_passkey_after_confirming(client: TestClient, db: Session) -> None:
    _, first, headers = _signed_in(client, db)
    second, _ = _add_passkey(client, headers, first)
    first_id, _ = _passkey_ids(client, headers)

    r = client.request(
        "DELETE",
        f"{API}/users/me/passkeys/{first_id}",
        headers=headers,
        json={"confirmation": _confirm(client, headers, second)},
    )

    assert r.status_code == 200, r.text
    assert first_id not in _passkey_ids(client, headers)
    # The session it opened goes on (FR-12.9).
    assert client.get(f"{API}/users/me", headers=headers).status_code == 200


def test_removing_a_passkey_without_confirming_is_refused(
    client: TestClient, db: Session
) -> None:
    _, first, headers = _signed_in(client, db)
    _add_passkey(client, headers, first)
    first_id, _ = _passkey_ids(client, headers)

    r = client.request(
        "DELETE",
        f"{API}/users/me/passkeys/{first_id}",
        headers=headers,
        json={"confirmation": {}},
    )

    assert r.status_code == 400
    assert first_id in _passkey_ids(client, headers)


def test_the_last_passkey_cannot_be_removed(client: TestClient, db: Session) -> None:
    _, only, headers = _signed_in(client, db)
    [only_id] = _passkey_ids(client, headers)

    r = client.request(
        "DELETE",
        f"{API}/users/me/passkeys/{only_id}",
        headers=headers,
        json={"confirmation": _confirm(client, headers, only)},
    )

    assert r.status_code == 400
    assert "only passkey" in r.json()["detail"]
    assert _passkey_ids(client, headers) == [only_id]


def test_someone_elses_passkey_is_not_found(client: TestClient, db: Session) -> None:
    _, mine, headers = _signed_in(client, db)
    _, _, their_headers = _signed_in(client, db)
    [their_id] = _passkey_ids(client, their_headers)

    r = client.request(
        "DELETE",
        f"{API}/users/me/passkeys/{their_id}",
        headers=headers,
        json={"confirmation": _confirm(client, headers, mine)},
    )

    assert r.status_code == 404
    assert _passkey_ids(client, their_headers) == [their_id]


# --- Signing out everywhere -------------------------------------------------


def test_signing_out_everywhere_ends_every_session(
    client: TestClient, db: Session
) -> None:
    _, authenticator, headers = _signed_in(client, db)
    other_device = sign_in(client, authenticator)

    r = client.post(f"{API}/users/me/sign-out-everywhere", headers=headers)

    assert r.status_code == 200
    for session in (headers, other_device):
        assert client.get(f"{API}/users/me", headers=session).status_code == 401
    # Signing in again opens a session that works.
    fresh = sign_in(client, authenticator)
    assert client.get(f"{API}/users/me", headers=fresh).status_code == 200


# --- Issuing recovery codes -------------------------------------------------


@pytest.fixture
def superuser(client: TestClient, db: Session) -> tuple[Authenticator, Headers]:
    user = create_random_user(db, is_superuser=True)
    authenticator = give_passkey(db, user)
    return authenticator, sign_in(client, authenticator)


def _issue(
    client: TestClient,
    superuser: tuple[Authenticator, Headers],
    user_id: Any,
) -> Any:
    authenticator, headers = superuser
    return client.post(
        f"{API}/users/{user_id}/recovery-code",
        headers=headers,
        json={"confirmation": _confirm(client, headers, authenticator)},
    )


def test_the_superuser_issues_a_recovery_code(
    client: TestClient, db: Session, superuser: tuple[Authenticator, Headers]
) -> None:
    user = create_random_user(db)

    r = _issue(client, superuser, user.id)

    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert len(code) == 19 and code.count("-") == 3
    expires_at = datetime.fromisoformat(r.json()["expires_at"])
    assert (
        timedelta(hours=23, minutes=59)
        < expires_at - datetime.now(UTC)
        <= timedelta(hours=24)
    )
    stored = db.get(RecoveryCode, user.id)
    assert stored is not None
    # Kept as a digest only.
    assert code.replace("-", "") not in stored.digest


def test_a_new_code_replaces_the_live_one(
    client: TestClient, db: Session, superuser: tuple[Authenticator, Headers]
) -> None:
    user = create_random_user(db)
    give_passkey(db, user)
    first = _issue(client, superuser, user.id).json()["code"]
    _issue(client, superuser, user.id)

    r = client.post(
        f"{API}/login/recovery/options", json={"email": user.email, "code": first}
    )

    assert r.status_code == 400
    assert (
        len(db.exec(select(RecoveryCode).where(RecoveryCode.user_id == user.id)).all())
        == 1
    )


def test_issuing_a_code_takes_a_fresh_confirmation(
    client: TestClient, db: Session, superuser: tuple[Authenticator, Headers]
) -> None:
    user = create_random_user(db)
    _, headers = superuser

    r = client.post(
        f"{API}/users/{user.id}/recovery-code",
        headers=headers,
        json={"confirmation": {}},
    )

    assert r.status_code == 400
    assert db.get(RecoveryCode, user.id) is None


def test_the_superuser_cannot_issue_their_own_code(
    client: TestClient, superuser: tuple[Authenticator, Headers]
) -> None:
    _, headers = superuser
    me = client.get(f"{API}/users/me", headers=headers).json()

    r = _issue(client, superuser, me["id"])

    assert r.status_code == 400
    assert "your own account" in r.json()["detail"]


def test_a_code_for_nobody_is_not_found(
    client: TestClient, superuser: tuple[Authenticator, Headers]
) -> None:
    r = _issue(client, superuser, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_only_the_superuser_issues_codes(client: TestClient, db: Session) -> None:
    _, authenticator, headers = _signed_in(client, db)
    user = create_random_user(db)

    r = client.post(
        f"{API}/users/{user.id}/recovery-code",
        headers=headers,
        json={"confirmation": _confirm(client, headers, authenticator)},
    )

    assert r.status_code == 403


# --- Spending a recovery code -----------------------------------------------


@pytest.fixture
def locked_out(
    client: TestClient, db: Session, superuser: tuple[Authenticator, Headers]
) -> tuple[User, Authenticator, str]:
    """A user with a passkey they no longer have, and a code to get back in."""
    user = create_random_user(db)
    lost = give_passkey(db, user)
    code = _issue(client, superuser, user.id).json()["code"]
    return user, lost, code


RECOVERY_REFUSED = "This email and recovery code do not match a live code."


def _recover(
    client: TestClient, email: str, code: str, authenticator: Authenticator
) -> Any:
    r = client.post(
        f"{API}/login/recovery/options", json={"email": email, "code": code}
    )
    if r.status_code != 200:
        return r
    return client.post(
        f"{API}/login/recovery",
        json={"credential": authenticator.create_json(r.json())},
    )


def test_spending_a_code_adds_a_passkey_and_signs_in(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, lost, code = locked_out
    old_session = sign_in(client, lost)
    new = Authenticator()

    r = _recover(client, user.email, code.lower().replace("-", " "), new)

    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"{API}/users/me", headers=headers).json()["id"] == str(user.id)
    # The passkeys the account had stay, beside the new one.
    assert len(_passkey_ids(client, headers)) == 2
    sign_in(client, new)
    # The code is spent and every earlier session is over (FR-12.14).
    assert db.get(RecoveryCode, user.id) is None
    assert client.get(f"{API}/users/me", headers=old_session).status_code == 401


def test_a_spent_code_is_refused(
    client: TestClient, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    assert _recover(client, user.email, code, Authenticator()).status_code == 200

    r = _recover(client, user.email, code, Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_an_expired_code_is_refused_in_the_same_words(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    db.exec(
        update(RecoveryCode)
        .where(col(RecoveryCode.user_id) == user.id)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()

    r = _recover(client, user.email, code, Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED
    db.expire_all()
    assert db.get(RecoveryCode, user.id) is None


def test_a_code_expiring_during_the_ceremony_is_refused(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    options = client.post(
        f"{API}/login/recovery/options", json={"email": user.email, "code": code}
    ).json()
    db.exec(
        update(RecoveryCode)
        .where(col(RecoveryCode.user_id) == user.id)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()

    r = client.post(
        f"{API}/login/recovery",
        json={"credential": Authenticator().create_json(options)},
    )

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_an_unknown_email_is_refused_in_the_same_words(client: TestClient) -> None:
    r = _recover(client, "nobody@example.com", "AAAA-AAAA-AAAA-AAAA", Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_an_account_without_a_code_is_refused_in_the_same_words(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)

    r = _recover(client, user.email, "AAAA-AAAA-AAAA-AAAA", Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_five_wrong_tries_burn_the_code(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    for _ in range(RECOVERY_CODE_MAX_ATTEMPTS - 1):
        r = _recover(client, user.email, "WRNG-WRNG-WRNG-WRNG", Authenticator())
        assert r.json()["detail"] == RECOVERY_REFUSED
    stored = db.get(RecoveryCode, user.id)
    assert stored is not None
    db.refresh(stored)
    assert stored.failed_attempts == RECOVERY_CODE_MAX_ATTEMPTS - 1

    _recover(client, user.email, "WRNG-WRNG-WRNG-WRNG", Authenticator())
    r = _recover(client, user.email, code, Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_a_recovery_answer_is_accepted_once(
    client: TestClient, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    options = client.post(
        f"{API}/login/recovery/options", json={"email": user.email, "code": code}
    ).json()
    credential = Authenticator().create_json(options)
    assert (
        client.post(
            f"{API}/login/recovery", json={"credential": credential}
        ).status_code
        == 200
    )

    r = client.post(f"{API}/login/recovery", json={"credential": credential})

    assert r.status_code == 400


# --- The superuser's own code -----------------------------------------------


@pytest.fixture
def only_superuser(db: Session) -> Generator[User]:
    """One superuser on the installation, the rest set aside for the test."""
    others = db.exec(select(User).where(User.is_superuser == True)).all()  # noqa: E712
    ids = [user.id for user in others]
    db.exec(update(User).where(col(User.id).in_(ids)).values(is_superuser=False))
    db.commit()
    superuser = create_random_user(db, is_superuser=True)
    yield superuser
    db.delete(superuser)
    db.exec(update(User).where(col(User.id).in_(ids)).values(is_superuser=True))
    db.commit()


def test_the_command_prints_the_superusers_code(
    client: TestClient,
    db: Session,
    only_superuser: User,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert superuser_recovery_code.main() == 0

    printed = capsys.readouterr().out
    assert only_superuser.email in printed
    code = printed.split(": ", 1)[1].split()[0]
    r = _recover(client, only_superuser.email, code, Authenticator())
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(RecoveryCode, only_superuser.id) is None


def test_the_command_says_when_there_is_no_superuser(
    db: Session, only_superuser: User, capsys: pytest.CaptureFixture[str]
) -> None:
    only_superuser.is_superuser = False
    db.add(only_superuser)
    db.commit()

    assert superuser_recovery_code.main() == 1

    assert settings.FIRST_SUPERUSER in capsys.readouterr().err


def test_an_inactive_account_cannot_spend_a_code(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    user.is_active = False
    db.add(user)
    db.commit()

    r = _recover(client, user.email, code, Authenticator())

    assert r.status_code == 400
    assert r.json()["detail"] == RECOVERY_REFUSED


def test_an_account_made_inactive_during_the_ceremony_is_refused(
    client: TestClient, db: Session, locked_out: tuple[User, Authenticator, str]
) -> None:
    user, _, code = locked_out
    options = client.post(
        f"{API}/login/recovery/options", json={"email": user.email, "code": code}
    ).json()
    user.is_active = False
    db.add(user)
    db.commit()

    r = client.post(
        f"{API}/login/recovery",
        json={"credential": Authenticator().create_json(options)},
    )

    assert r.status_code == 400
    db.expire_all()
    # Refused before anything was spent.
    assert db.get(RecoveryCode, user.id) is not None
