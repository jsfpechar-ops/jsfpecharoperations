"""A small software authenticator for the passkey tests (task 0004).

It does what a phone or a password manager does, with a P-256 key held in
memory: answers ``navigator.credentials.create`` with a "none" attestation and
``navigator.credentials.get`` with a real ECDSA signature. The server's checks
run unmodified against it, so the tests prove the real verification, not a
mock of it.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
from base64 import urlsafe_b64decode, urlsafe_b64encode

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_BE = 0x08
FLAG_BS = 0x10
FLAG_AT = 0x40


def b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64url(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SoftAuthenticator:
    def __init__(self, *, origin: str, rp_id: str, counting: bool = False, synced: bool = True):
        self.origin = origin
        self.rp_id = rp_id
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.user_handle = b""
        # Synced passkeys report 0 for ever; a security key counts up.
        self.counting = counting
        self.count = 0
        self.synced = synced

    def _client_data(self, kind: str, challenge: str, origin: str | None = None) -> bytes:
        return json.dumps(
            {
                "type": kind,
                "challenge": challenge,
                "origin": origin or self.origin,
                "crossOrigin": False,
            }
        ).encode("utf-8")

    def _flags(self, extra: int = 0, *, uv: bool = True) -> int:
        flags = FLAG_UP | extra
        if uv:
            flags |= FLAG_UV
        if self.synced:
            flags |= FLAG_BE | FLAG_BS
        return flags

    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}
        )

    def _rp_hash(self, rp_id: str | None = None) -> bytes:
        return hashlib.sha256((rp_id or self.rp_id).encode("utf-8")).digest()

    def create(self, options: dict, *, origin: str | None = None, uv: bool = True) -> dict:
        """The browser's answer to ``navigator.credentials.create``."""
        self.user_handle = unb64url(options["user"]["id"])
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        auth_data = (
            self._rp_hash(options.get("rp", {}).get("id"))
            + bytes([self._flags(FLAG_AT, uv=uv)])
            + struct.pack(">I", self.count)
            + bytes(16)  # AAGUID: none
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = b64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "attestationObject": b64url(attestation),
                "transports": ["internal", "hybrid"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def get(
        self, options: dict, *, origin: str | None = None, rp_id: str | None = None,
        uv: bool = True, count: int | None = None,
    ) -> dict:
        """The browser's answer to ``navigator.credentials.get``."""
        if count is not None:
            self.count = count
        elif self.counting:
            self.count += 1
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        auth_data = (
            self._rp_hash(rp_id) + bytes([self._flags(uv=uv)]) + struct.pack(">I", self.count)
        )
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        cid = b64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(signature),
                "userHandle": b64url(self.user_handle) if self.user_handle else None,
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }
