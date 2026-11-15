"""Write the Python-side passkey golden fixture for the Go tests.

A software authenticator (ES256, attestation "none") makes up one passkey for
rpId ``ubyhost.example.test``. The registration and a login are verified with
py_webauthn the way app/passkeys.py calls it, then written to
go/internal/web/auth/testdata/passkeys_python.json. Everything is made-up data.

Run from App/:

    .venv/bin/python scripts/go_passkeys_golden.py

Challenges and the credential id are random per run, so the output is not
byte-reproducible, but every run writes content that verifies.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any, Dict

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn import verify_authentication_response, verify_registration_response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

RP_ID = "ubyhost.example.test"
ORIGIN = "https://ubyhost.example.test"
OUT = Path(__file__).resolve().parents[2] / "go/internal/web/auth/testdata/passkeys_python.json"

FLAGS_REGISTER = 0x01 | 0x04 | 0x40  # UP | UV | AT (attested credential data)
FLAGS_LOGIN = 0x01 | 0x04  # UP | UV
REGISTER_COUNTER = 0
LOGIN_COUNTER = 7
AAGUID = bytes(16)  # no real authenticator model; all zeros
# A fixed 64-byte made-up user handle.
USER_HANDLE = hashlib.sha512(b"ubyhost go golden fixture user handle").digest()


def _b64(data: bytes) -> str:
    return bytes_to_base64url(data)


def _client_data(kind: str, challenge: bytes) -> bytes:
    return json.dumps(
        {"type": kind, "challenge": _b64(challenge), "origin": ORIGIN, "crossOrigin": False},
        separators=(",", ":"),
    ).encode("utf-8")


def _rp_hash() -> bytes:
    return hashlib.sha256(RP_ID.encode("ascii")).digest()


def _register(key: ec.EllipticCurvePrivateKey, cred_id: bytes, challenge: bytes) -> Dict[str, Any]:
    numbers = key.public_key().public_numbers()
    cose = cbor2.dumps(
        {
            1: 2,  # kty: EC2
            3: -7,  # alg: ES256
            -1: 1,  # crv: P-256
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
    )
    auth_data = (
        _rp_hash()
        + bytes([FLAGS_REGISTER])
        + REGISTER_COUNTER.to_bytes(4, "big")
        + AAGUID
        + len(cred_id).to_bytes(2, "big")
        + cred_id
        + cose
    )
    attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
    return {
        "id": _b64(cred_id),
        "rawId": _b64(cred_id),
        "type": "public-key",
        "authenticatorAttachment": "platform",
        "response": {
            "clientDataJSON": _b64(_client_data("webauthn.create", challenge)),
            "attestationObject": _b64(attestation),
            "transports": ["internal"],
        },
        "clientExtensionResults": {},
    }


def _login(key: ec.EllipticCurvePrivateKey, cred_id: bytes, challenge: bytes) -> Dict[str, Any]:
    auth_data = _rp_hash() + bytes([FLAGS_LOGIN]) + LOGIN_COUNTER.to_bytes(4, "big")
    client_data = _client_data("webauthn.get", challenge)
    signed = auth_data + hashlib.sha256(client_data).digest()
    signature = key.sign(signed, ec.ECDSA(hashes.SHA256()))
    return {
        "id": _b64(cred_id),
        "rawId": _b64(cred_id),
        "type": "public-key",
        "authenticatorAttachment": "platform",
        "response": {
            "clientDataJSON": _b64(client_data),
            "authenticatorData": _b64(auth_data),
            "signature": _b64(signature),
            "userHandle": _b64(USER_HANDLE),
        },
        "clientExtensionResults": {},
    }


def build() -> Dict[str, Any]:
    key = ec.generate_private_key(ec.SECP256R1())
    cred_id = secrets.token_bytes(32)
    reg_challenge = secrets.token_bytes(32)
    login_challenge = secrets.token_bytes(32)

    reg_credential = _register(key, cred_id, reg_challenge)
    numbers = key.public_key().public_numbers()
    cose = cbor2.dumps(
        {
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
    )

    # Verify exactly as app/passkeys.py does.
    verified_reg = verify_registration_response(
        credential=reg_credential,
        expected_challenge=reg_challenge,
        expected_rp_id=RP_ID,
        expected_origin=[ORIGIN],
        require_user_verification=True,
    )
    assert verified_reg.credential_public_key == cose, "registered COSE key mismatch"

    stored_public_key = _b64(verified_reg.credential_public_key)
    login_credential = _login(key, cred_id, login_challenge)
    verified_login = verify_authentication_response(
        credential=login_credential,
        expected_challenge=login_challenge,
        expected_rp_id=RP_ID,
        expected_origin=[ORIGIN],
        credential_public_key=base64url_to_bytes(stored_public_key),
        credential_current_sign_count=REGISTER_COUNTER,
        require_user_verification=True,
    )
    assert verified_login.new_sign_count == LOGIN_COUNTER

    return {
        "rp_id": RP_ID,
        "origin": ORIGIN,
        "user_handle": _b64(USER_HANDLE),
        "credential_id": _b64(verified_reg.credential_id),
        "public_key": stored_public_key,
        "sign_count": REGISTER_COUNTER,
        "registration": {"challenge": _b64(reg_challenge), "credential": reg_credential},
        "login": {"challenge": _b64(login_challenge), "credential": login_credential},
    }


def main() -> None:
    fixture = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
