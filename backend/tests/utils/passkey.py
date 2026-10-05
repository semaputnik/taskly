"""
A software authenticator for driving passkey ceremonies in tests.

Built on soft-webauthn's `SoftWebauthnDevice`, which holds one credential and
signs with it, but answers the way a browser's `PublicKeyCredential.toJSON()`
does — base64url strings, not bytes — and sets the user-verified flag, since
Taskly refuses any passkey that was not verified on the device (FR-12.5).
`user_verified=False` makes one that skips verification, to see it refused.
"""

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from struct import pack
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor
from fido2.cose import ES256
from fido2.utils import sha256
from soft_webauthn import SoftWebauthnDevice  # type: ignore[import-untyped]

from app import passkeys

_USER_PRESENT = 0x01
_USER_VERIFIED = 0x04
_ATTESTED_DATA = 0x40


def b64(data: bytes) -> str:
    return urlsafe_b64encode(data).decode().rstrip("=")


def unb64(data: str) -> bytes:
    return urlsafe_b64decode(data + "=" * (-len(data) % 4))


class Authenticator(SoftWebauthnDevice):  # type: ignore[misc]
    def __init__(self, *, user_verified: bool = True, origin: str | None = None):
        super().__init__()
        self.user_verified = user_verified
        self.origin = origin or passkeys.expected_origin()

    def _flags(self, *extra: int) -> bytes:
        flags = _USER_PRESENT | (_USER_VERIFIED if self.user_verified else 0)
        for flag in extra:
            flags |= flag
        return bytes([flags])

    def _client_data(self, kind: str, options: dict[str, Any]) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": options["challenge"], "origin": self.origin}
        ).encode()

    def create_json(self, options: dict[str, Any]) -> dict[str, Any]:
        """Answer `navigator.credentials.create()` with the given options."""
        self.cred_init(options["rp"]["id"], options["user"]["id"])
        client_data = self._client_data("webauthn.create", options)
        public_key = cbor.encode(
            ES256.from_cryptography_key(self.private_key.public_key())
        )
        auth_data = (
            sha256(self.rp_id.encode())
            + self._flags(_ATTESTED_DATA)
            + pack(">I", self.sign_count)
            + self.aaguid
            + pack(">H", len(self.credential_id))
            + self.credential_id
            + public_key
        )
        attestation = cbor.encode({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def get_json(self, options: dict[str, Any]) -> dict[str, Any]:
        """Answer `navigator.credentials.get()` with the given options."""
        if self.rp_id != options["rpId"]:
            raise ValueError(
                "This authenticator holds no passkey for that relying party"
            )
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", options)
        auth_data = (
            sha256(self.rp_id.encode()) + self._flags() + pack(">I", self.sign_count)
        )
        signature = self.private_key.sign(
            auth_data + sha256(client_data), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": self.user_handle,
            },
            "clientExtensionResults": {},
        }
