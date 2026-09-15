"""
A bot user's token over its life: issued, perhaps expiring, used, revoked and
issued again (FR-08.12–FR-08.17).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import BotUser
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_user_headers,
    error_code,
)

API = settings.API_V1_STR

Headers = dict[str, str]


def _issue(
    client: TestClient,
    owner: Headers,
    bot_id: str,
    expires_at: datetime | None = None,
) -> Any:
    body = {"expires_at": expires_at.isoformat()} if expires_at else None
    return client.post(f"{API}/bot-users/{bot_id}/token", headers=owner, json=body)


def _as_bot(token: str) -> Headers:
    return {"Authorization": f"Bearer {token}"}


def _listed(client: TestClient, owner: Headers, bot_id: str) -> dict[str, Any]:
    bots = client.get(f"{API}/bot-users/", headers=owner).json()["data"]
    bot: dict[str, Any] = next(b for b in bots if b["id"] == bot_id)
    return bot


def _set(db: Session, bot_id: str, **values: Any) -> None:
    # For what only time can do through the API — a token running past its
    # expiry, or a last use going stale — the row is moved directly.
    bot = db.get(BotUser, uuid.UUID(bot_id))
    assert bot is not None
    db.refresh(bot)
    for name, value in values.items():
        setattr(bot, name, value)
    db.add(bot)
    db.commit()


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


@pytest.fixture
def bot_id(client: TestClient, owner: Headers) -> str:
    project_id = create_project(client, owner)
    bot: dict[str, Any] = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    return str(bot["id"])


# --- Expiry -------------------------------------------------------------------


def test_a_token_can_be_issued_with_an_expiry(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=30)

    r = _issue(client, owner, bot_id, expires_at)
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["expires_at"]) == expires_at
    assert (
        client.get(f"{API}/tasks/", headers=_as_bot(r.json()["token"])).status_code
        == 200
    )

    listed = _listed(client, owner, bot_id)
    assert datetime.fromisoformat(listed["token_expires_at"]) == expires_at


def test_a_token_without_an_expiry_never_expires(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    r = _issue(client, owner, bot_id)
    assert r.status_code == 200
    assert r.json()["expires_at"] is None
    assert _listed(client, owner, bot_id)["token_expires_at"] is None


@pytest.mark.parametrize(
    "expires_at",
    [
        (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        (datetime.now() + timedelta(days=1)).isoformat(),  # noqa: DTZ005
    ],
    ids=["in the past", "without a timezone"],
)
def test_an_expiry_has_to_be_a_moment_in_the_future(
    client: TestClient, owner: Headers, bot_id: str, expires_at: str
) -> None:
    r = client.post(
        f"{API}/bot-users/{bot_id}/token",
        headers=owner,
        json={"expires_at": expires_at},
    )
    assert r.status_code == 422
    assert _listed(client, owner, bot_id)["has_token"] is False


def test_an_expired_token_is_refused(
    client: TestClient, db: Session, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id, datetime.now(UTC) + timedelta(days=1)).json()[
        "token"
    ]
    _set(db, bot_id, token_expires_at=datetime.now(UTC) - timedelta(seconds=1))

    r = client.get(f"{API}/tasks/", headers=_as_bot(token))
    assert r.status_code == 401


def test_an_expired_token_still_has_to_be_revoked_before_another_is_issued(
    client: TestClient, db: Session, owner: Headers, bot_id: str
) -> None:
    _issue(client, owner, bot_id, datetime.now(UTC) + timedelta(days=1))
    _set(db, bot_id, token_expires_at=datetime.now(UTC) - timedelta(seconds=1))

    r = _issue(client, owner, bot_id)
    assert r.status_code == 409
    assert error_code(r) == "token_already_issued"


# --- Revoking and issuing again -----------------------------------------------


def test_revoking_refuses_the_very_next_request(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]
    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 200

    r = client.delete(f"{API}/bot-users/{bot_id}/token", headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["has_token"] is False
    assert r.json()["token_revoked_at"] is not None

    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 401


def test_a_token_issued_again_works_and_the_revoked_one_stays_refused(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    scope_before = _listed(client, owner, bot_id)["scope"]
    old = _issue(client, owner, bot_id).json()["token"]
    client.delete(f"{API}/bot-users/{bot_id}/token", headers=owner)

    r = _issue(client, owner, bot_id)
    assert r.status_code == 200, r.text
    new = r.json()["token"]
    assert new != old

    assert client.get(f"{API}/tasks/", headers=_as_bot(new)).status_code == 200
    assert client.get(f"{API}/tasks/", headers=_as_bot(old)).status_code == 401

    listed = _listed(client, owner, bot_id)
    assert listed["scope"] == scope_before
    assert listed["has_token"] is True
    assert listed["token_revoked_at"] is None


def test_a_bot_user_never_holds_two_working_tokens(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]

    r = _issue(client, owner, bot_id)
    assert r.status_code == 409
    assert error_code(r) == "token_already_issued"
    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 200


def test_revoking_a_bot_user_without_a_token_changes_nothing(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    r = client.delete(f"{API}/bot-users/{bot_id}/token", headers=owner)
    assert r.status_code == 200
    assert r.json()["has_token"] is False
    assert r.json()["token_revoked_at"] is None


def test_only_the_owner_revokes_and_a_bot_cannot_revoke_or_reissue(
    client: TestClient, db: Session, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]
    other = create_user_headers(client, db)

    r = client.delete(f"{API}/bot-users/{bot_id}/token", headers=other)
    assert r.status_code == 404
    for method in ("delete", "post"):
        r = client.request(
            method, f"{API}/bot-users/{bot_id}/token", headers=_as_bot(token)
        )
        assert r.status_code == 403
        assert error_code(r) == "human_only"

    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 200


# --- Refusals look alike ------------------------------------------------------


def test_revoked_expired_and_malformed_tokens_get_the_same_refusal(
    client: TestClient, db: Session, owner: Headers
) -> None:
    project_id = create_project(client, owner)

    def token_for(state: str) -> str:
        bot = create_bot_user(
            client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
        )
        token: str = _issue(client, owner, bot["id"]).json()["token"]
        if state == "revoked":
            client.delete(f"{API}/bot-users/{bot['id']}/token", headers=owner)
        elif state == "expired":
            _set(
                db,
                bot["id"],
                token_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        return token

    responses = [
        client.get(f"{API}/tasks/", headers=_as_bot(token))
        for token in (
            token_for("revoked"),
            token_for("expired"),
            "taskly_bot_" + "x" * 43,
        )
    ]
    assert {(r.status_code, r.text) for r in responses} == {
        (401, '{"detail":"Could not validate credentials"}')
    }


# --- Last used ----------------------------------------------------------------


def test_last_used_is_recorded_on_a_successful_request(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]
    assert _listed(client, owner, bot_id)["token_last_used_at"] is None

    before = datetime.now(UTC)
    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 200

    last_used = _listed(client, owner, bot_id)["token_last_used_at"]
    assert last_used is not None
    assert datetime.fromisoformat(last_used) >= before


def test_last_used_is_not_recorded_on_a_refused_request(
    client: TestClient, db: Session, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]
    _set(db, bot_id, token_expires_at=datetime.now(UTC) - timedelta(seconds=1))

    assert client.get(f"{API}/tasks/", headers=_as_bot(token)).status_code == 401
    assert _listed(client, owner, bot_id)["token_last_used_at"] is None


def test_last_used_is_coarse(
    client: TestClient, db: Session, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id).json()["token"]
    client.get(f"{API}/tasks/", headers=_as_bot(token))
    first = _listed(client, owner, bot_id)["token_last_used_at"]

    # A request moments later leaves it be.
    client.get(f"{API}/tasks/", headers=_as_bot(token))
    assert _listed(client, owner, bot_id)["token_last_used_at"] == first

    # One after the last note has gone stale records the new use.
    stale = datetime.now(UTC) - timedelta(minutes=5)
    _set(db, bot_id, token_last_used_at=stale)
    client.get(f"{API}/tasks/", headers=_as_bot(token))
    assert datetime.fromisoformat(
        _listed(client, owner, bot_id)["token_last_used_at"]
    ) > stale + timedelta(minutes=4)


def test_a_token_issued_again_starts_unused(
    client: TestClient, owner: Headers, bot_id: str
) -> None:
    token = _issue(client, owner, bot_id, datetime.now(UTC) + timedelta(days=1)).json()[
        "token"
    ]
    client.get(f"{API}/tasks/", headers=_as_bot(token))
    client.delete(f"{API}/bot-users/{bot_id}/token", headers=owner)

    _issue(client, owner, bot_id)

    listed = _listed(client, owner, bot_id)
    assert listed["token_last_used_at"] is None
    assert listed["token_expires_at"] is None
