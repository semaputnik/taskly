"""Setting, changing and clearing a bot user's webhooks and its secret (FR-11.1 to FR-11.3, FR-11.9)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import webhooks
from app.core import outbound
from app.core.config import settings
from app.models import BotUser
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_bot_user,
    create_project,
    create_user_headers,
    create_webhook_bot,
    error_code,
    set_webhook,
    token_headers,
)
from tests.utils.webhooks import Receiver

API = settings.API_V1_STR


def _bot(client: TestClient, headers: dict[str, str]) -> dict:
    return create_bot_user(
        client,
        headers,
        project_ids=[create_project(client, headers)],
        permissions=ALL_PERMISSIONS,
    )


def test_a_new_bot_user_has_no_webhooks_and_no_secret(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    assert bot["webhooks"] == {
        "task": {"url": None, "last_delivery": None},
        "comment": {"url": None, "last_delivery": None},
        "has_secret": False,
    }


def test_each_webhook_is_set_changed_and_cleared_on_its_own(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    result = set_webhook(client, headers, bot["id"], "task", "https://a.example.com/x")
    assert result["bot_user"]["webhooks"]["task"]["url"] == "https://a.example.com/x"
    assert result["bot_user"]["webhooks"]["comment"]["url"] is None

    set_webhook(client, headers, bot["id"], "comment", "http://b.example.com/y")
    result = set_webhook(client, headers, bot["id"], "task", "https://c.example.com/z")
    shown = result["bot_user"]["webhooks"]
    assert shown["task"]["url"] == "https://c.example.com/z"
    assert shown["comment"]["url"] == "http://b.example.com/y"

    r = client.delete(f"{API}/bot-users/{bot['id']}/webhooks/task", headers=headers)
    assert r.status_code == 200
    assert r.json()["webhooks"]["task"]["url"] is None
    assert r.json()["webhooks"]["comment"]["url"] == "http://b.example.com/y"

    listed = client.get(f"{API}/bot-users/{bot['id']}", headers=headers).json()
    assert listed["webhooks"]["comment"]["url"] == "http://b.example.com/y"


def test_the_secret_is_shown_once_when_the_first_webhook_is_set(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    first = set_webhook(client, headers, bot["id"], "task")
    assert first["secret"].startswith("whsec_")
    assert first["bot_user"]["webhooks"]["has_secret"] is True

    second = set_webhook(client, headers, bot["id"], "comment")
    assert second["secret"] is None
    again = set_webhook(client, headers, bot["id"], "task", "https://other.example.com")
    assert again["secret"] is None
    shown = client.get(f"{API}/bot-users/{bot['id']}", headers=headers).text
    assert first["secret"] not in shown


def test_the_secret_is_stored_encrypted_and_can_be_read_back_to_sign(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = create_webhook_bot(client, headers, project_ids=[])
    stored = db.get_one(BotUser, uuid.UUID(bot["id"])).webhook_secret_encrypted

    assert stored is not None
    assert bot["secret"] not in stored
    assert webhooks.decrypt_secret(stored) == bot["secret"]


def test_an_unreadable_secret_says_so_instead_of_signing() -> None:
    with pytest.raises(ValueError, match="Regenerate the secret"):
        webhooks.decrypt_secret("not-a-token-this-key-made")


def test_a_secret_stored_under_another_webhook_secret_key_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WEBHOOK_SECRET_KEY", "the-key-it-was-stored-under")
    stored = webhooks.encrypt_secret("whsec_example")
    assert webhooks.decrypt_secret(stored) == "whsec_example"

    monkeypatch.setattr(settings, "WEBHOOK_SECRET_KEY", "a-different-key")
    with pytest.raises(ValueError, match="Regenerate the secret") as raised:
        webhooks.decrypt_secret(stored)
    assert "WEBHOOK_SECRET_KEY" in str(raised.value)


def test_rotating_the_secret_key_leaves_stored_secrets_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = webhooks.encrypt_secret("whsec_example")

    monkeypatch.setattr(settings, "SECRET_KEY", "a-rotated-secret-key")

    assert webhooks.decrypt_secret(stored) == "whsec_example"


def test_the_secret_can_be_regenerated_and_the_old_one_stops_applying(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = create_webhook_bot(client, headers, project_ids=[])

    r = client.post(f"{API}/bot-users/{bot['id']}/webhook-secret", headers=headers)
    assert r.status_code == 200
    new_secret = r.json()["secret"]
    assert new_secret.startswith("whsec_")
    assert new_secret != bot["secret"]
    stored = db.get_one(BotUser, uuid.UUID(bot["id"]))
    db.refresh(stored)
    assert stored.webhook_secret_encrypted is not None
    assert webhooks.decrypt_secret(stored.webhook_secret_encrypted) == new_secret


def test_a_bot_user_with_no_webhook_has_no_secret_to_regenerate(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    r = client.post(f"{API}/bot-users/{bot['id']}/webhook-secret", headers=headers)
    assert r.status_code == 409
    assert error_code(r) == "webhook_not_set"


def test_clearing_the_last_webhook_drops_the_secret_and_the_next_one_makes_a_new_one(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = create_webhook_bot(client, headers, project_ids=[])

    client.delete(f"{API}/bot-users/{bot['id']}/webhooks/task", headers=headers)
    r = client.delete(f"{API}/bot-users/{bot['id']}/webhooks/comment", headers=headers)
    assert r.json()["webhooks"]["has_secret"] is False

    result = set_webhook(client, headers, bot["id"], "task")
    assert result["secret"] is not None
    assert result["secret"] != bot["secret"]


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("http://127.0.0.1:8000/hook", "loopback"),
        ("http://localhost/hook", "loopback"),
        ("http://[::1]/hook", "loopback"),
        ("http://10.1.2.3/hook", "private"),
        ("https://192.168.0.7/hook", "private"),
        ("http://172.16.0.1/hook", "private"),
        ("http://169.254.169.254/latest/meta-data", "link-local"),
        ("http://[::ffff:10.0.0.1]/hook", "private"),
        ("http://100.64.0.1/hook", "non-public"),
    ],
)
def test_a_private_address_is_refused_with_the_rule_it_breaks(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    kind: str,
) -> None:
    def resolve(host: str) -> list[str]:
        return ["127.0.0.1"] if host == "localhost" else [host]

    monkeypatch.setattr(outbound, "resolve_host", resolve)
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    r = client.put(
        f"{API}/bot-users/{bot['id']}/webhooks/task", headers=headers, json={"url": url}
    )

    assert r.status_code == 422, r.text
    assert error_code(r) == "webhook_url_private_address"
    message = r.json()["detail"]["message"]
    assert f"a {kind} address" in message
    assert outbound.ALLOW_SETTING in message
    shown = client.get(f"{API}/bot-users/{bot['id']}", headers=headers).json()
    assert shown["webhooks"]["task"]["url"] is None
    assert shown["webhooks"]["has_secret"] is False


def test_a_name_that_resolves_to_a_private_address_is_refused(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(outbound, "resolve_host", lambda _host: ["10.0.0.5"])
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    r = client.put(
        f"{API}/bot-users/{bot['id']}/webhooks/task",
        headers=headers,
        json={"url": "https://agent.internal.example.com/hook"},
    )

    assert r.status_code == 422
    assert (
        "agent.internal.example.com resolves to 10.0.0.5"
        in r.json()["detail"]["message"]
    )


def test_the_installation_setting_allows_private_addresses(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "OUTBOUND_ALLOW_PRIVATE_ADDRESSES", True)
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    result = set_webhook(
        client, headers, bot["id"], "task", "http://127.0.0.1:9000/hook"
    )

    assert result["bot_user"]["webhooks"]["task"]["url"] == "http://127.0.0.1:9000/hook"


@pytest.mark.parametrize(
    "url", ["ftp://example.com/hook", "example.com/hook", "http:///x"]
)
def test_only_http_and_https_addresses_naming_a_host_are_accepted(
    client: TestClient, db: Session, url: str
) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    r = client.put(
        f"{API}/bot-users/{bot['id']}/webhooks/task", headers=headers, json={"url": url}
    )

    assert r.status_code == 422, r.text


def test_an_unknown_webhook_is_not_found(client: TestClient, db: Session) -> None:
    headers = create_user_headers(client, db)
    bot = _bot(client, headers)

    r = client.put(
        f"{API}/bot-users/{bot['id']}/webhooks/status",
        headers=headers,
        json={"url": "https://example.com"},
    )

    assert r.status_code == 422


def test_only_the_owner_reaches_a_bot_users_webhooks(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    stranger = create_user_headers(client, db)
    bot = create_webhook_bot(client, owner, project_ids=[])
    base = f"{API}/bot-users/{bot['id']}"

    assert (
        client.put(
            f"{base}/webhooks/task",
            headers=stranger,
            json={"url": "https://x.example.com"},
        ).status_code
        == 404
    )
    assert client.delete(f"{base}/webhooks/task", headers=stranger).status_code == 404
    assert client.post(f"{base}/webhook-secret", headers=stranger).status_code == 404
    assert (
        client.post(f"{base}/webhooks/task/test", headers=stranger).status_code == 404
    )
    assert client.get(base, headers=stranger).status_code == 404


def test_a_bot_user_cannot_read_or_change_its_own_webhooks(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    bot_headers = token_headers(client, owner, bot["id"])
    base = f"{API}/bot-users/{bot['id']}"

    for r in (
        client.get(base, headers=bot_headers),
        client.put(
            f"{base}/webhooks/task",
            headers=bot_headers,
            json={"url": "https://evil.example.com"},
        ),
        client.delete(f"{base}/webhooks/task", headers=bot_headers),
        client.post(f"{base}/webhook-secret", headers=bot_headers),
        client.post(f"{base}/webhooks/task/test", headers=bot_headers),
    ):
        assert r.status_code == 403, r.text
        assert error_code(r) == "human_only"


def test_a_deleted_bot_user_is_out_of_reach_and_has_no_webhooks(
    client: TestClient, db: Session
) -> None:
    headers = create_user_headers(client, db)
    bot = create_webhook_bot(client, headers, project_ids=[])
    client.delete(f"{API}/bot-users/{bot['id']}", headers=headers)

    r = client.put(
        f"{API}/bot-users/{bot['id']}/webhooks/task",
        headers=headers,
        json={"url": "https://x.example.com"},
    )
    assert r.status_code == 404
    shown = client.get(f"{API}/bot-users/{bot['id']}", headers=headers).json()
    assert shown["webhooks"]["task"]["url"] is None
    assert shown["webhooks"]["has_secret"] is False


def test_a_test_event_needs_a_webhook_to_send_to(
    client: TestClient, db: Session, receiver: Receiver
) -> None:
    headers = create_user_headers(client, db)
    bot = create_webhook_bot(client, headers, project_ids=[], comment=False)

    r = client.post(
        f"{API}/bot-users/{bot['id']}/webhooks/comment/test", headers=headers
    )

    assert r.status_code == 409
    assert error_code(r) == "webhook_not_set"
    assert receiver.requests == []
