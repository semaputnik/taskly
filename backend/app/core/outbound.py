"""
Which addresses Taskly will send a request to on a user's say-so.

A webhook URL is typed by a user, and registration is open, so without a rule
any visitor could make the server probe its own network (ADR-0009). Loopback
and private ranges are refused unless the operator allows them with
`OUTBOUND_ALLOW_PRIVATE_ADDRESSES`. The same rule covers a user's Paperless
address (FR-04.4).
"""

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import settings

ALLOW_SETTING = "OUTBOUND_ALLOW_PRIVATE_ADDRESSES"

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class Refusal(Exception):
    """A URL Taskly will not send to, with the rule that says so."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_host(host: str) -> list[str]:
    """
    The addresses a host name resolves to. An address given as a number is its
    own answer. Raises `OSError` when the name does not resolve.
    """
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def _kind(address: IPAddress) -> str | None:
    """What makes an address one Taskly refuses, or None for a public one."""
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link-local"
    if address.is_private:
        return "private"
    if not address.is_global:
        return "non-public"
    return None


def check_url(url: str) -> None:
    """
    Raise `Refusal` unless `url` is an http or https address Taskly may send
    to: its host must not resolve to loopback or a private range, unless the
    installation allows those (FR-11.3).

    A host that does not resolve passes: whether it exists is not this rule's
    question, and a delivery to it fails with the resolver's own error.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise Refusal(
            "webhook_url_scheme",
            "A webhook URL has to start with http:// or https://.",
        )
    host = parts.hostname
    if not host:
        raise Refusal("webhook_url_host", "A webhook URL has to name a host.")
    if settings.OUTBOUND_ALLOW_PRIVATE_ADDRESSES:
        return
    try:
        addresses = resolve_host(host)
    except OSError:
        return
    for text in addresses:
        kind = _kind(ipaddress.ip_address(text))
        if kind is not None:
            raise Refusal(
                "webhook_url_private_address",
                f"{host} resolves to {text}, a {kind} address. Loopback and "
                "private ranges are refused unless the installation allows "
                f"them with {ALLOW_SETTING}.",
            )
