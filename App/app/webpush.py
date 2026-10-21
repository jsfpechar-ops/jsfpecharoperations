"""Web Push with no library beyond ``cryptography`` and ``requests`` (brief 0204).

Two small standards:

* VAPID (RFC 8292): every request carries a short ES256-signed token that
  proves it comes from this server. ``push.vapid_key`` makes and keeps the key.
* Message encryption (RFC 8291, the "aes128gcm" coding of RFC 8188): the alert
  is encrypted for the one browser that subscribed, so the push service that
  carries it (Apple, Google, Mozilla, Microsoft) cannot read it.

``tests/test_webpush.py`` checks ``encrypt`` against the RFC 8291 example byte
for byte.
"""
from __future__ import annotations

import base64
import json
import os
import struct
import time
from typing import Optional
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096
# A push service takes at least 4096 bytes; the header and the tag use 103.
MAX_PAYLOAD = 3800
TOKEN_HOURS = 12


class TransportError(RuntimeError):
    """The push service could not be reached."""


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64url(text: str) -> bytes:
    text = "".join(str(text).split())
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def new_private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def private_from_raw(raw: bytes) -> ec.EllipticCurvePrivateKey:
    if len(raw) != 32:
        raise ValueError("a P-256 private key is 32 bytes")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def private_raw(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_numbers().private_value.to_bytes(32, "big")


def public_raw(key: ec.EllipticCurvePrivateKey) -> bytes:
    """The uncompressed public point (65 bytes), the form browsers use."""
    return key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def check_public_key(raw: bytes) -> ec.EllipticCurvePublicKey:
    """A browser's p256dh key, or ValueError when it is not a P-256 point."""
    if len(raw) != 65 or raw[0] != 4:
        raise ValueError("not an uncompressed P-256 point")
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(
    plaintext: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    as_private: Optional[ec.EllipticCurvePrivateKey] = None,
    salt: Optional[bytes] = None,
) -> bytes:
    """RFC 8291 section 3.4: one aes128gcm record for one browser.

    ``as_private`` and ``salt`` are fresh for every message; the tests pass the
    RFC's values to reproduce its example.
    """
    if len(plaintext) > MAX_PAYLOAD:
        raise ValueError("push payload too large")
    as_private = as_private or new_private_key()
    salt = salt or os.urandom(16)
    as_public = public_raw(as_private)
    ecdh_secret = as_private.exchange(ec.ECDH(), check_public_key(ua_public))
    key_info = b"WebPush: info\x00" + ua_public + as_public
    ikm = _hkdf(auth_secret, ecdh_secret, key_info, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # 0x02 marks the last (here: the only) record; no further padding.
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public
    return header + ciphertext


def vapid_header(private_key, audience: str, subject: str, now: Optional[int] = None) -> str:
    """RFC 8292: the Authorization header for one push service origin."""
    issued = int(time.time() if now is None else now)
    head = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode("utf-8"))
    claims = b64url(json.dumps(
        {"aud": audience, "exp": issued + TOKEN_HOURS * 3600, "sub": subject},
        separators=(",", ":"),
    ).encode("utf-8"))
    signing_input = f"{head}.{claims}".encode("ascii")
    r, s = decode_dss_signature(private_key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    signature = b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{claims}.{signature}, k={b64url(public_raw(private_key))}"


def send(
    endpoint: str,
    ua_public: bytes,
    auth_secret: bytes,
    payload: bytes,
    *,
    private_key,
    subject: str,
    ttl: int,
    urgency: str = "high",
    timeout: float = 10.0,
) -> int:
    """Encrypt ``payload`` and POST it to the push service. Returns the HTTP status."""
    parts = urlsplit(endpoint)
    headers = {
        "Authorization": vapid_header(private_key, f"{parts.scheme}://{parts.netloc}", subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(int(ttl)),
        "Urgency": urgency,
    }
    body = encrypt(payload, ua_public, auth_secret)
    try:
        response = requests.post(
            endpoint, data=body, headers=headers, timeout=timeout, allow_redirects=False
        )
    except requests.RequestException as exc:
        raise TransportError(type(exc).__name__) from exc
    return int(response.status_code)
