"""
The address rule for what Taskly sends to on a user's say-so (FR-11.3), at the
transport that makes it hold. No test here touches a network: the transport
underneath is a mock, and a host name resolves to what the test says.
"""

import asyncio
import ipaddress

import httpx
import pytest

from app import webhooks
from app.core import outbound
from app.core.config import settings
from app.core.outbound import resolve_host as real_resolve_host

PUBLIC = "93.184.216.34"


def _guarded(
    monkeypatch: pytest.MonkeyPatch, *answers: list[str]
) -> tuple[httpx.Client, list[httpx.Request], list[str]]:
    """A client through the guard, whose resolver answers in turn, and what it saw."""
    seen: list[httpx.Request] = []
    asked: list[str] = []
    remaining = list(answers)

    def resolve(host: str) -> list[str]:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return [host]
        asked.append(host)
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(outbound, "resolve_host", resolve)
    transport = outbound.GuardedTransport(httpx.MockTransport(handler))
    return httpx.Client(transport=transport), seen, asked


def test_a_request_goes_to_the_address_that_was_checked_under_its_own_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, seen, _asked = _guarded(monkeypatch, [PUBLIC])

    client.post("https://hooks.example.com/taskly?x=1", content=b"{}")

    [request] = seen
    assert request.url.host == PUBLIC
    assert request.url.path == "/taskly"
    assert request.url.query == b"x=1"
    # The name is still what the receiver sees, and what its certificate is
    # checked against.
    assert request.headers["host"] == "hooks.example.com"
    assert request.extensions["sni_hostname"] == "hooks.example.com"


def test_a_name_is_resolved_once_so_a_second_answer_cannot_be_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An attacker's name server: public for the first look, loopback for the
    # next. The connection is made to what the first look found.
    client, seen, asked = _guarded(monkeypatch, [PUBLIC], ["127.0.0.1"])

    client.post("https://rebind.example.com/")

    assert asked == ["rebind.example.com"]
    assert seen[0].url.host == PUBLIC


@pytest.mark.parametrize(
    "answer",
    [
        ["127.0.0.1"],
        ["10.0.0.5"],
        ["169.254.169.254"],
        [PUBLIC, "192.168.1.1"],
        ["::1"],
    ],
)
def test_a_name_with_any_private_answer_is_refused_before_a_connection(
    monkeypatch: pytest.MonkeyPatch, answer: list[str]
) -> None:
    client, seen, _asked = _guarded(monkeypatch, answer)

    with pytest.raises(outbound.Refusal) as refusal:
        client.post("https://sneaky.example.com/")

    assert refusal.value.code == "webhook_url_private_address"
    assert outbound.ALLOW_SETTING in refusal.value.message
    assert seen == []


def test_an_address_given_as_a_number_is_checked_and_left_as_it_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, seen, _asked = _guarded(monkeypatch, [PUBLIC])
    client.post(f"http://{PUBLIC}:8080/x")
    assert seen[0].url.host == PUBLIC
    assert seen[0].url.port == 8080
    assert "sni_hostname" not in seen[0].extensions

    with pytest.raises(outbound.Refusal):
        client.post("http://10.1.1.1/x")


def test_the_installation_setting_lets_the_transport_connect_privately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OUTBOUND_ALLOW_PRIVATE_ADDRESSES", True)
    client, seen, _asked = _guarded(monkeypatch, ["10.0.0.5"])

    client.post("http://agent.lan/hook")

    assert seen[0].url.host == "10.0.0.5"


def test_the_client_deliveries_use_has_the_guard_and_ignores_the_proxy_environment() -> (
    None
):
    client = webhooks.make_client()

    assert client.trust_env is False
    assert client.follow_redirects is False
    with pytest.raises(outbound.Refusal):
        client.post("http://127.0.0.1:1/never-connected")


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1/hook",
        "http://example.com:notaport/hook",
        "https://[nope]/hook",
        "http://exa mple.com/hook",
        "http://ex\x00ample.com/hook",
        "http://example.com/ho\nok",
    ],
)
def test_a_url_that_does_not_parse_is_refused_not_an_error(url: str) -> None:
    with pytest.raises(outbound.Refusal) as refusal:
        outbound.check_url(url)

    assert refusal.value.code == "webhook_url_invalid"


def test_a_host_name_the_resolver_cannot_encode_resolves_to_nothing() -> None:
    with pytest.raises(OSError):
        real_resolve_host("a" * 70 + ".example")


def test_a_wake_up_after_the_loop_has_closed_is_harmless(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = asyncio.new_event_loop()
    event = asyncio.Event()
    loop.close()
    monkeypatch.setattr(webhooks, "_loop", loop)
    monkeypatch.setattr(webhooks, "_wakeup", event)

    webhooks.wake()
