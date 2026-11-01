#!/usr/bin/env python3
"""Write the Python oracle for the Go crypto port (go/internal/secure).

Dev tool, never run in production. Test keys only: it never reads .env,
config or the database. Usage: crypto_fixtures.py [--out PATH]
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
from unittest import mock

from cryptography.fernet import Fernet, MultiFernet
from itsdangerous import URLSafeTimedSerializer

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "go" / "internal" / "secure" / "testdata" / "fixtures.json"
SECRET = "fixture-secret-0123456789abcdef0123456789"
KEY1 = "1GkCuCTOyJg0vS3EsxyKXGfPZJQvqujz1WOzmU6CStg="
KEY2 = "qsnhqPggFPSaXh-V1-LUo5feZLRFywanTE8-4az-oxc="
NOW = 1767225600
IV = bytes(range(16))
SALTS = [
    "ubyhost-session",
    "ubyhost-2fa-pending",
    "ubyhost-guest-pin",
    "ubyhost-invoice-download",
]
PLAINTEXTS = [
    ("empty", b""),
    ("unicode", "Jana Nováková".encode("utf-8")),
    ("x1000", b"x" * 1000),
    ("bytes256", bytes(range(256))),
]
SIGNER_VALUES = {
    "small": {"uid": 7, "rm": 1},
    "long": [i % 7 for i in range(200)],
    "unicode": {"name": "Jana Nováková"},
}


def legacy_key() -> str:
    digest = hashlib.sha256(SECRET.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def fernet_token(key: str, data: bytes) -> str:
    token = Fernet(key.encode("ascii"))._encrypt_from_parts(data, NOW, IV)
    return token.decode("ascii")


def signer_token(salt: str, value: object) -> str:
    with mock.patch("time.time", return_value=float(NOW)):
        return URLSafeTimedSerializer(SECRET, salt=salt).dumps(value)


def recovery_hash(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hmac.new(SECRET.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def pin_hash(token: str, pin: str) -> str:
    message = f"{token}\0{pin}".encode()
    return hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()


def build() -> tuple[dict, int]:
    keys = {"key1": KEY1, "key2": KEY2, "legacy": legacy_key()}

    fernet = []
    for name, data in PLAINTEXTS:
        tokens = {label: fernet_token(key, data) for label, key in keys.items()}
        fernet.append({"name": name, "plaintext_hex": data.hex(), "tokens": tokens})

    mf_plain = "Jana Nováková".encode("utf-8")
    mf_keys = [keys["key1"], keys["key2"], keys["legacy"]]
    mf_tokens = {label: fernet_token(key, mf_plain) for label, key in keys.items()}
    for token in mf_tokens.values():
        assert MultiFernet([Fernet(k.encode("ascii")) for k in mf_keys]).decrypt(
            token.encode("ascii"), ttl=None
        ) == mf_plain
    multifernet = {
        "plaintext_hex": mf_plain.hex(),
        "keys": mf_keys,
        "tokens": mf_tokens,
    }

    signer = []
    for salt in SALTS:
        for name, value in SIGNER_VALUES.items():
            token = signer_token(salt, value)
            loaded = URLSafeTimedSerializer(SECRET, salt=salt).loads(token)
            assert loaded == value
            signer.append({"salt": salt, "name": name, "value": value, "token": token})

    digest = {
        "recovery_code_hash": {"input": "abcd-ef12", "hex": recovery_hash("abcd-ef12")},
        "pin_fingerprint": {
            "token": "tok123",
            "pin": "4821",
            "hex": pin_hash("tok123", "4821"),
        },
    }

    data = {
        "secret": SECRET,
        "now": NOW,
        "iv_hex": IV.hex(),
        "keys": keys,
        "fernet": fernet,
        "multifernet": multifernet,
        "signer": signer,
        "digest": digest,
    }
    count = len(fernet) + 1 + len(signer) + len(digest)
    return data, count


def main() -> None:
    out = DEFAULT_OUT
    if sys.argv[1:2] == ["--out"]:
        out = Path(sys.argv[2])
    data, count = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"fixtures written: {count}")


if __name__ == "__main__":
    main()
