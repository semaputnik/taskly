"""
Which addresses Taskly will send a request to on a user's say-so.

A webhook URL is typed by a user, and registration is open, so without a rule
any visitor could make the server probe its own network (ADR-0009). Loopback
and private ranges are refused unless the operator allows them with
`OUTBOUND_ALLOW_PRIVATE_ADDRESSES`. The same rule covers a user's Paperless
address (FR-04.4).

The rule is applied twice. `check_url` is the readable refusal, given when a
URL is set and before every delivery. `GuardedTransport` is the one that
holds: it resolves the host name once, checks the answer and connects to that
very address, so a name that answers differently the second time cannot get
past the check.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

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
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except UnicodeError as error:
        # A name the resolver cannot even encode resolves to nothing.
        raise OSError(str(error)) from error
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


def allowed_addresses(
    host: str, *, code: str = "webhook_url_private_address"
) -> list[str]:
    """
    What `host` resolves to, if the installation may send to all of it: raises
    `Refusal` naming the rule if any address is loopback or private, unless the
    installation allows those, and `OSError` if the name does not resolve.
    """
    addresses = resolve_host(host)
    if not settings.OUTBOUND_ALLOW_PRIVATE_ADDRESSES:
        for text in addresses:
            kind = _kind(ipaddress.ip_address(text))
            if kind is not None:
                raise Refusal(
                    code,
                    f"{host} resolves to {text}, a {kind} address. Loopback and "
                    "private ranges are refused unless the installation allows "
                    f"them with {ALLOW_SETTING}.",
                )
    return addresses


def check_url(
    url: str, *, what: str = "webhook URL", code_prefix: str = "webhook_url"
) -> None:
    """
    Raise `Refusal` unless `url` is an http or https address Taskly may send
    to: its host must not resolve to loopback or a private range, unless the
    installation allows those (FR-11.3, FR-04.4). `what` names the address in
    the refusal and `code_prefix` starts its code: a webhook URL by default, a
    Paperless address for the other user of this rule.

    A host that does not resolve passes: whether it exists is not this rule's
    question, and a delivery to it fails with the resolver's own error.
    """
    if any(char.isspace() or not char.isprintable() for char in url):
        raise Refusal(
            f"{code_prefix}_invalid",
            f"A {what} cannot contain spaces or control characters.",
        )
    try:
        parts = urlsplit(url)
        host = parts.hostname
        # Reading the port is what validates it.
        _ = parts.port
    except ValueError as error:
        raise Refusal(
            f"{code_prefix}_invalid", f"That is not a valid URL: {error}."
        ) from error
    if parts.scheme not in ("http", "https"):
        raise Refusal(
            f"{code_prefix}_scheme",
            f"A {what} has to start with http:// or https://.",
        )
    if not host:
        raise Refusal(f"{code_prefix}_host", f"A {what} has to name a host.")
    try:
        allowed_addresses(host, code=f"{code_prefix}_private_address")
    except OSError:
        return


class GuardedTransport(httpx.BaseTransport):
    """
    A transport that only connects to addresses the installation allows, and
    connects to the address it checked.

    The host name is resolved here, once, checked, and the request is sent to
    that address with the original name kept for the `Host` header and for
    verifying the certificate. A second lookup by the connection itself, which
    an attacker's name server could answer differently, never happens.
    """

    def __init__(self, inner: httpx.BaseTransport | None = None) -> None:
        self._inner = inner or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        try:
            ipaddress.ip_address(host)
        except ValueError:
            address = allowed_addresses(host)[0]
            request.url = request.url.copy_with(host=address)
            request.extensions = {**request.extensions, "sni_hostname": host}
        else:
            allowed_addresses(host)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()
