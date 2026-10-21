# 0204: Push engine (keys, encryption, device list, queue, delivery, retention)

Status: todo
Depends on: 0203 | Base commit: after 0203 on claude/project-thread-w35ftw | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the server side of urgent alerts on the host's phone: the server's signing key, storage of each device's push subscription, a queue with retries, delivery through the browser's push service with end-to-end encryption, and retention. No screen and no event uses it yet (0205 adds Settings, 0206 the four alerts).

## 2. Context

- Owner decisions 2026-10-21: push is for **critical alerts only**: police report not accepted, police deadline at risk, door code missing, cancelled stay with registered guests. `push.KINDS` holds exactly those four; nothing else may be queued.
- **No new dependency.** Web Push is built on `cryptography` and `requests`, which are already in `requirements.txt`. The orchestrator checked the encryption code against the RFC 8291 example byte for byte; `tests/test_webpush.py` keeps that check.
- **Outbound requests** go only to the four browser push services (`PUSH_HOST_SUFFIXES`). Any other subscription address is refused, so nobody can make the server call an address they chose (SSRF).
- **Privacy:** the push address and keys are stored encrypted (`db.encrypt_secret`). A queued alert holds a property name and dates, never a guest name. Queue rows are deleted after 30 days, and devices not seen for 180 days. Deleting a workspace deletes both. Never log an endpoint; log ids and status codes only.
- **Database:** new tables only through `App/app/migrations/0011_web_push.sql`, Postgres-portable SQL, `ON CONFLICT ... DO NOTHING`, never `INSERT OR IGNORE`.
- **Key:** the VAPID key pair is made by the app on first use and stored encrypted in `settings` (`web_push_vapid_private`). No env var is needed. `UBYHOST_WEB_PUSH=0` switches everything off.
- `db.execute` returns the row count. `db.utcnow()` returns `YYYY-MM-DDTHH:MM:SS+00:00`; every time string here uses the same format so string comparison works.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/webpush.py` | new | VAPID + RFC 8291 encryption + POST |
| `App/app/push.py` | new | key, subscriptions, queue, delivery, purge |
| `App/app/migrations/0011_web_push.sql` | new | two tables |
| `App/app/config.py` | edit | `WEB_PUSH` flag |
| `App/app/retention.py` | edit | purge step, workspace deletion |
| `App/app/scheduler.py` | edit | `push` job every minute |
| `App/app/host_i18n.py` | edit | alert texts EN/CS, job name |
| `App/app/host_vi_i18n.py` | edit | alert texts VI, job name |
| `docs/ENVIRONMENT.md` | edit | `UBYHOST_WEB_PUSH` |
| `App/tests/test_webpush.py` | new | RFC vector, VAPID, send |
| `App/tests/test_push.py` | new | storage, queue, delivery, retention |

No other file may change.

## 4. Steps

**Step 1.** Create `App/app/webpush.py` with exactly:

```python
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
```

**Step 2.** Create `App/tests/test_webpush.py` with exactly:

```python
"""Brief 0204: Web Push encryption and VAPID, checked against the RFCs."""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app import webpush

# RFC 8291, section 5 and appendix A.
RFC_PLAINTEXT = b"When I grow up, I want to be a watermelon"
RFC_UA_PUBLIC = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
RFC_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RFC_AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
RFC_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
RFC_BODY = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
    "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
    "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def test_encryption_reproduces_the_rfc_8291_example_byte_for_byte():
    body = webpush.encrypt(
        RFC_PLAINTEXT,
        webpush.unb64url(RFC_UA_PUBLIC),
        webpush.unb64url(RFC_AUTH),
        as_private=webpush.private_from_raw(webpush.unb64url(RFC_AS_PRIVATE)),
        salt=webpush.unb64url(RFC_SALT),
    )
    assert webpush.b64url(body) == RFC_BODY


def test_every_message_gets_a_fresh_key_and_salt():
    ua = webpush.public_raw(webpush.new_private_key())
    first = webpush.encrypt(b"x", ua, b"0" * 16)
    second = webpush.encrypt(b"x", ua, b"0" * 16)
    assert first[:16] != second[:16]
    assert first[21:86] != second[21:86]


def test_the_vapid_token_is_signed_by_the_servers_key():
    key = webpush.new_private_key()
    header = webpush.vapid_header(
        key, "https://fcm.googleapis.com", "mailto:support@ubyhost.com", now=1000
    )
    token, public = header.removeprefix("vapid t=").split(", k=")
    assert webpush.unb64url(public) == webpush.public_raw(key)
    head, claims, signature = token.split(".")
    assert json.loads(webpush.unb64url(head)) == {"typ": "JWT", "alg": "ES256"}
    assert json.loads(webpush.unb64url(claims)) == {
        "aud": "https://fcm.googleapis.com",
        "exp": 1000 + 12 * 3600,
        "sub": "mailto:support@ubyhost.com",
    }
    raw = webpush.unb64url(signature)
    key.public_key().verify(
        encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
        f"{head}.{claims}".encode("ascii"),
        ec.ECDSA(hashes.SHA256()),
    )


def test_a_key_round_trips_through_its_raw_form():
    key = webpush.new_private_key()
    again = webpush.private_from_raw(webpush.private_raw(key))
    assert webpush.public_raw(again) == webpush.public_raw(key)


@pytest.mark.parametrize(
    "raw", [b"", b"\x04" + b"\x00" * 64, b"\x02" + b"\x01" * 64, b"\x04" * 10]
)
def test_a_browser_key_that_is_not_a_p256_point_is_refused(raw):
    with pytest.raises(ValueError):
        webpush.check_public_key(raw)


def test_send_posts_an_encrypted_body_with_the_standard_headers(monkeypatch):
    seen = {}

    class _Answer:
        status_code = 201

    def fake_post(url, data, headers, timeout, allow_redirects):
        seen.update(url=url, data=data, headers=headers, timeout=timeout, redirects=allow_redirects)
        return _Answer()

    monkeypatch.setattr(webpush.requests, "post", fake_post)
    ua = webpush.new_private_key()
    status = webpush.send(
        "https://fcm.googleapis.com/fcm/send/abc",
        webpush.public_raw(ua),
        b"1" * 16,
        b'{"title":"x"}',
        private_key=webpush.new_private_key(),
        subject="mailto:support@ubyhost.com",
        ttl=86400,
    )
    assert status == 201
    assert seen["url"] == "https://fcm.googleapis.com/fcm/send/abc"
    assert seen["headers"]["Content-Encoding"] == "aes128gcm"
    assert seen["headers"]["TTL"] == "86400"
    assert seen["headers"]["Urgency"] == "high"
    assert seen["headers"]["Authorization"].startswith("vapid t=")
    assert seen["redirects"] is False and seen["timeout"] == 10.0
    assert b"title" not in seen["data"]


def test_an_unreachable_push_service_is_a_transport_error(monkeypatch):
    def down(*args, **kwargs):
        raise webpush.requests.ConnectionError("down")

    monkeypatch.setattr(webpush.requests, "post", down)
    ua = webpush.new_private_key()
    with pytest.raises(webpush.TransportError):
        webpush.send(
            "https://fcm.googleapis.com/x", webpush.public_raw(ua), b"1" * 16, b"{}",
            private_key=ua, subject="mailto:a@example.test", ttl=60,
        )
```

Run: `cd App && .venv/bin/python -m pytest tests/test_webpush.py -q --tb=short -x 2>&1 | tail -5`. Expected: 10 passed.

**Step 3.** Create `App/app/migrations/0011_web_push.sql` with exactly:

```sql
-- Brief 0204: urgent alerts on the host's phone (Web Push).
--
-- push_subscription: one row per browser that turned alerts on. The endpoint is
-- the push service address the browser gave; with the two keys it is enough to
-- message that device, so all three are stored encrypted. endpoint_hash
-- (sha256) finds a row without decrypting. device is a coarse family name
-- ("iPhone"); lang is the interface language the alerts are written in.
CREATE TABLE IF NOT EXISTS push_subscription (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    endpoint_hash    TEXT NOT NULL UNIQUE,
    endpoint_enc     TEXT NOT NULL,
    p256dh_enc       TEXT NOT NULL,
    auth_enc         TEXT NOT NULL,
    lang             TEXT NOT NULL DEFAULT 'en',
    device           TEXT NOT NULL DEFAULT '',
    failures         INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    last_sent_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_subscription_user ON push_subscription (user_account_id);

-- push_outbox: one row per alert per device. params holds a property name and
-- dates for the text, never a guest's name. Rows are deleted 30 days after they
-- were queued (retention.py). The idempotency key stops a retried event from
-- buzzing the same phone twice.
CREATE TABLE IF NOT EXISTS push_outbox (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key  TEXT NOT NULL UNIQUE,
    subscription_id  INTEGER NOT NULL REFERENCES push_subscription(id) ON DELETE CASCADE,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,
    params           TEXT NOT NULL DEFAULT '{}',
    url              TEXT NOT NULL DEFAULT '/',
    state            TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'sent', 'failed')),
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TEXT NOT NULL,
    last_status      INTEGER,
    created_at       TEXT NOT NULL,
    sent_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_outbox_due ON push_outbox (state, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_push_outbox_device ON push_outbox (subscription_id, state, sent_at);
```

Run: `cd App && .venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -5`. Expected: all pass.

**Step 4.** `App/app/config.py`. Anchor: `TTLOCK_MONTHLY_CALLS = int(os.environ.get("UBYHOST_TTLOCK_MONTHLY_CALLS", "30000"))`. Insert after it:

```python

# Web push (briefs 0204-0206): urgent alerts on the host's phone. On unless
# UBYHOST_WEB_PUSH=0. The signing key is made by the app and kept encrypted.
WEB_PUSH = os.environ.get("UBYHOST_WEB_PUSH", "1").strip().lower() not in ("0", "false", "no")
```

**Step 5.** Create `App/app/push.py` with exactly:

```python
"""Urgent alerts on the host's phone (Web Push, briefs 0204-0206).

Only problems that need the host now become a push (owner decision
2026-10-21): a police report UbyPort did not accept, a police deadline at
risk, a door code that could not be made, and a cancelled stay whose guests
had registered. Each of them already sends an e-mail; the push only gets the
news to the host sooner. Nothing else may become a push without a new owner
decision, and DAILY_CAP stops a bug from ever flooding a phone.

What is kept, per device that turned alerts on: the browser's push address and
its two keys (encrypted), a coarse device name and the interface language. A
queued alert carries a property name and dates, never a guest's name, and is
deleted 30 days later. The message itself is end-to-end encrypted (RFC 8291):
Apple, Google, Mozilla or Microsoft carry it but cannot read it.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from . import config, db, host_i18n, webpush

log = logging.getLogger("ubyhost.push")

KINDS = ("filing_problem", "deadline_at_risk", "door_code", "cancelled_with_guests")
TEST_KIND = "test"

# The push services browsers use. Any other address is refused, or a visitor
# could make the server send requests wherever they like.
PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",  # Chrome, Edge on Android, Samsung Internet, Opera
    "push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari and iPhone home-screen apps (web.push.apple.com)
    "notify.windows.com",  # Edge on Windows
)
MAX_DEVICES = 10
DAILY_CAP = 12  # per device and 24 hours; the e-mail still carries anything past it
TTL_SECONDS = 24 * 3600
RETRY_MINUTES = (1, 5, 15, 60)
CLAIM_MINUTES = 10
MAX_FAILURES = 5
OUTBOX_KEEP_DAYS = 30
UNSEEN_DAYS = 180
VAPID_SETTING = "web_push_vapid_private"
_PARAM_MAX = 120


class SubscriptionError(ValueError):
    """A subscription this server will not store."""


def enabled() -> bool:
    return bool(config.WEB_PUSH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


# --- the server's key pair (VAPID) ---------------------------------------------


def vapid_key():
    """The server's signing key: made on first use, kept encrypted in settings."""
    stored = db.get_setting(VAPID_SETTING)
    raw = db.decrypt_secret(stored) if stored else ""
    if raw:
        return webpush.private_from_raw(webpush.unb64url(raw))
    if stored:
        # The app's secret key changed, so this key is lost. Every subscription
        # was made for it; each browser subscribes again from Settings.
        log.warning("web push key unreadable; making a new one and dropping all devices")
        db.execute("DELETE FROM push_outbox")
        db.execute("DELETE FROM push_subscription")
        db.execute("DELETE FROM settings WHERE key = ?", (VAPID_SETTING,))
    fresh = webpush.b64url(webpush.private_raw(webpush.new_private_key()))
    # Two processes may get here at once: the first row wins and both use it.
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
        (VAPID_SETTING, db.encrypt_secret(fresh)),
    )
    kept = db.decrypt_secret(db.get_setting(VAPID_SETTING))
    return webpush.private_from_raw(webpush.unb64url(kept))


def public_key() -> str:
    """The applicationServerKey a browser subscribes with (base64url)."""
    return webpush.b64url(webpush.public_raw(vapid_key()))


def _subject() -> str:
    return f"mailto:{config.SUPPORT_EMAIL}"


# --- devices ------------------------------------------------------------------


def _hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def clean_subscription(data: Any) -> Dict[str, str]:
    """Check a browser's PushSubscription.toJSON() and return its three parts."""
    if not isinstance(data, dict):
        raise SubscriptionError("not an object")
    keys = data.get("keys")
    keys = keys if isinstance(keys, dict) else {}
    endpoint = str(data.get("endpoint") or "")
    p256dh = str(keys.get("p256dh") or "")
    auth_secret = str(keys.get("auth") or "")
    if not endpoint or len(endpoint) > 1024:
        raise SubscriptionError("bad endpoint")
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError as exc:
        raise SubscriptionError("bad endpoint") from exc
    if parts.scheme != "https" or port not in (None, 443) or parts.username or parts.password:
        raise SubscriptionError("endpoint must be plain https")
    if not any(host == suffix or host.endswith("." + suffix) for suffix in PUSH_HOST_SUFFIXES):
        raise SubscriptionError("unknown push service")
    try:
        webpush.check_public_key(webpush.unb64url(p256dh))
        secret = webpush.unb64url(auth_secret)
    except ValueError as exc:
        raise SubscriptionError("bad keys") from exc
    if len(secret) != 16:
        raise SubscriptionError("bad auth secret")
    return {"endpoint": endpoint, "p256dh": p256dh, "auth": auth_secret}


def count_for(account_id: int) -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM push_subscription WHERE user_account_id = ?", (account_id,)
    )
    return int(row["n"]) if row else 0


def devices_for(account_id: int):
    """The account's devices for Settings: id, device name, added, last alert."""
    return db.query(
        "SELECT id, device, created_at, last_sent_at FROM push_subscription "
        "WHERE user_account_id = ? ORDER BY created_at, id",
        (account_id,),
    )


def save_subscription(account_id: int, data: Any, *, lang: str, device: str) -> int:
    """Store or refresh this browser's subscription for the account. Returns its id."""
    sub = clean_subscription(data)
    digest = _hash(sub["endpoint"])
    now = db.utcnow()
    lang = host_i18n.normalise_language(lang)
    device = (device or "")[:40]
    existing = db.query_one(
        "SELECT id, user_account_id FROM push_subscription WHERE endpoint_hash = ?", (digest,)
    )
    if existing:
        if int(existing["user_account_id"]) != int(account_id):
            # One browser, one row: signed in as someone else now, it follows
            # them, and nothing queued for the previous account reaches them.
            db.execute("DELETE FROM push_outbox WHERE subscription_id = ?", (existing["id"],))
        db.execute(
            "UPDATE push_subscription SET user_account_id = ?, p256dh_enc = ?, auth_enc = ?, "
            "lang = ?, device = ?, failures = 0, last_seen_at = ? WHERE id = ?",
            (
                account_id,
                db.encrypt_secret(sub["p256dh"]),
                db.encrypt_secret(sub["auth"]),
                lang,
                device,
                now,
                existing["id"],
            ),
        )
        return int(existing["id"])
    if count_for(account_id) >= MAX_DEVICES:
        raise SubscriptionError("too many devices")
    return int(db.insert("push_subscription", {
        "user_account_id": account_id,
        "endpoint_hash": digest,
        "endpoint_enc": db.encrypt_secret(sub["endpoint"]),
        "p256dh_enc": db.encrypt_secret(sub["p256dh"]),
        "auth_enc": db.encrypt_secret(sub["auth"]),
        "lang": lang,
        "device": device,
        "failures": 0,
        "created_at": now,
        "last_seen_at": now,
    }))


def _drop(subscription_id: int) -> None:
    db.execute("DELETE FROM push_outbox WHERE subscription_id = ?", (subscription_id,))
    db.execute("DELETE FROM push_subscription WHERE id = ?", (subscription_id,))


def remove(account_id: int, subscription_id: int) -> bool:
    """Forget one of the account's devices (Settings > Remove)."""
    row = db.query_one(
        "SELECT id FROM push_subscription WHERE id = ? AND user_account_id = ?",
        (subscription_id, account_id),
    )
    if not row:
        return False
    _drop(int(row["id"]))
    return True


def remove_endpoint(account_id: int, endpoint: str) -> bool:
    """Forget the device with this push address (Settings > Turn off)."""
    row = db.query_one(
        "SELECT id FROM push_subscription WHERE endpoint_hash = ? AND user_account_id = ?",
        (_hash(str(endpoint or "")), account_id),
    )
    if not row:
        return False
    _drop(int(row["id"]))
    return True


# --- queue ----------------------------------------------------------------------


def _clean_params(params: Optional[Dict[str, Any]]) -> Dict[str, str]:
    return {str(key): str(value)[:_PARAM_MAX] for key, value in (params or {}).items()}


def message(kind: str, lang: str, params: Dict[str, Any]) -> Dict[str, str]:
    """The alert's title and body in the device's language."""
    lang = host_i18n.normalise_language(lang)
    return {
        "title": host_i18n.translate(lang, f"push.msg.{kind}.title", **params),
        "body": host_i18n.translate(lang, f"push.msg.{kind}.body", **params),
    }


def notify(
    owner_user_id: Optional[int],
    kind: str,
    *,
    key: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
) -> int:
    """Queue one urgent alert for every device of the account. Never raises.

    ``key`` names the event (one stay, or one property and day): the same kind
    and key never reach the same device twice. Returns how many were queued.
    """
    try:
        if kind not in KINDS:
            log.error("push_unknown_kind kind=%s", kind)
            return 0
        if not enabled() or not owner_user_id:
            return 0
        if not str(url).startswith("/") or str(url).startswith("//"):
            url = "/"
        stored = json.dumps(_clean_params(params), ensure_ascii=False)
        now = db.utcnow()
        queued = 0
        devices = db.query(
            "SELECT id FROM push_subscription WHERE user_account_id = ?", (owner_user_id,)
        )
        for device in devices:
            queued += db.execute(
                "INSERT INTO push_outbox (idempotency_key, subscription_id, user_account_id, "
                "kind, params, url, state, attempts, next_attempt_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?) "
                "ON CONFLICT(idempotency_key) DO NOTHING",
                (f"{kind}:{key}:{device['id']}", device["id"], owner_user_id, kind, stored, url, now, now),
            )
        return queued
    except Exception:
        log.exception("push_notify_failed kind=%s owner_user_id=%s", kind, owner_user_id)
        return 0


# --- delivery -------------------------------------------------------------------


def drain(limit: int = 50, now: Optional[datetime] = None) -> Dict[str, int]:
    """Send the alerts that are due. The scheduler runs this every minute."""
    if not enabled():
        return {}
    moment = now or _now()
    due = db.query(
        "SELECT id, next_attempt_at FROM push_outbox WHERE state = 'queued' "
        "AND next_attempt_at <= ? ORDER BY id LIMIT ?",
        (_stamp(moment), limit),
    )
    counts: Dict[str, int] = {}
    for row in due:
        # Claim the row first, so a second process cannot send it as well.
        claimed = db.execute(
            "UPDATE push_outbox SET attempts = attempts + 1, next_attempt_at = ? "
            "WHERE id = ? AND state = 'queued' AND next_attempt_at = ?",
            (_stamp(moment + timedelta(minutes=CLAIM_MINUTES)), row["id"], row["next_attempt_at"]),
        )
        if not claimed:
            continue
        outcome = _deliver(int(row["id"]), moment)
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def send_test(account_id: int, endpoint: str) -> str:
    """Send the test alert to this one device now. Returns the outcome."""
    row = db.query_one(
        "SELECT id FROM push_subscription WHERE endpoint_hash = ? AND user_account_id = ?",
        (_hash(str(endpoint or "")), account_id),
    )
    if not row:
        return "gone"
    moment = _now()
    outbox_id = db.insert("push_outbox", {
        "idempotency_key": f"{TEST_KIND}:{_stamp(moment)}:{row['id']}",
        "subscription_id": row["id"],
        "user_account_id": account_id,
        "kind": TEST_KIND,
        "params": "{}",
        "url": "/settings#settings-group-phone",
        "state": "queued",
        "attempts": 1,
        "next_attempt_at": _stamp(moment + timedelta(minutes=CLAIM_MINUTES)),
        "created_at": _stamp(moment),
    })
    return _deliver(int(outbox_id), moment)


def _deliver(outbox_id: int, moment: datetime) -> str:
    row = db.query_one(
        "SELECT o.*, s.endpoint_enc, s.p256dh_enc, s.auth_enc, s.lang, s.failures "
        "FROM push_outbox o JOIN push_subscription s ON s.id = o.subscription_id "
        "WHERE o.id = ?",
        (outbox_id,),
    )
    if not row:
        return "gone"
    sent_today = db.query_one(
        "SELECT COUNT(*) AS n FROM push_outbox WHERE subscription_id = ? "
        "AND state = 'sent' AND sent_at >= ?",
        (row["subscription_id"], _stamp(moment - timedelta(hours=24))),
    )["n"]
    if sent_today >= DAILY_CAP:
        log.warning("push_capped subscription=%s kind=%s", row["subscription_id"], row["kind"])
        _finish(outbox_id, "failed", None, moment)
        return "capped"
    try:
        params = json.loads(row["params"] or "{}")
    except ValueError:
        params = {}
    payload = json.dumps({
        **message(row["kind"], row["lang"], params),
        "url": row["url"],
        # One notification per event: a repeat replaces it instead of stacking.
        "tag": row["idempotency_key"].rsplit(":", 1)[0],
        "lang": row["lang"],
    }, ensure_ascii=False).encode("utf-8")
    try:
        status = webpush.send(
            db.decrypt_secret(row["endpoint_enc"]),
            webpush.unb64url(db.decrypt_secret(row["p256dh_enc"])),
            webpush.unb64url(db.decrypt_secret(row["auth_enc"])),
            payload,
            private_key=vapid_key(),
            subject=_subject(),
            ttl=TTL_SECONDS,
        )
    except webpush.TransportError as exc:
        log.warning("push_transport_error subscription=%s error=%s", row["subscription_id"], exc)
        return _retry(row, None, moment)
    except ValueError:
        # Stored keys that no longer decrypt (the app key changed): unusable.
        log.warning("push_unreadable_device subscription=%s", row["subscription_id"])
        _drop(int(row["subscription_id"]))
        return "gone"
    return _settle(row, status, moment)


def _settle(row, status: int, moment: datetime) -> str:
    device = int(row["subscription_id"])
    if 200 <= status < 300:
        _finish(int(row["id"]), "sent", status, moment)
        db.execute(
            "UPDATE push_subscription SET failures = 0, last_sent_at = ? WHERE id = ?",
            (_stamp(moment), device),
        )
        return "sent"
    if status in (404, 410):
        # The browser unsubscribed or the app was removed: forget the device.
        log.info("push_gone subscription=%s status=%s", device, status)
        _drop(device)
        return "gone"
    if status == 429 or status >= 500:
        return _retry(row, status, moment)
    log.warning("push_refused subscription=%s status=%s kind=%s", device, status, row["kind"])
    _finish(int(row["id"]), "failed", status, moment)
    failures = int(row["failures"] or 0) + 1
    if failures >= MAX_FAILURES:
        _drop(device)
    else:
        db.execute("UPDATE push_subscription SET failures = ? WHERE id = ?", (failures, device))
    return "failed"


def _retry(row, status: Optional[int], moment: datetime) -> str:
    attempts = int(row["attempts"])  # already counts this try
    if attempts > len(RETRY_MINUTES):
        _finish(int(row["id"]), "failed", status, moment)
        return "failed"
    db.execute(
        "UPDATE push_outbox SET next_attempt_at = ?, last_status = ? WHERE id = ?",
        (_stamp(moment + timedelta(minutes=RETRY_MINUTES[attempts - 1])), status, row["id"]),
    )
    return "retry"


def _finish(outbox_id: int, state: str, status: Optional[int], moment: datetime) -> None:
    db.execute(
        "UPDATE push_outbox SET state = ?, last_status = ?, sent_at = ? WHERE id = ?",
        (state, status, _stamp(moment) if state == "sent" else None, outbox_id),
    )


# --- retention ------------------------------------------------------------------


def purge(
    now: Optional[datetime] = None, dry_run: bool = False, owner_user_id: Optional[int] = None
) -> int:
    """Alerts queued more than 30 days ago, and devices unseen for 180 days."""
    moment = now or _now()
    old = _stamp(moment - timedelta(days=OUTBOX_KEEP_DAYS))
    unseen = _stamp(moment - timedelta(days=UNSEEN_DAYS))
    scope = "" if owner_user_id is None else " AND user_account_id = ?"
    extra = () if owner_user_id is None else (owner_user_id,)
    alerts = db.query_one(
        f"SELECT COUNT(*) AS n FROM push_outbox WHERE created_at < ?{scope}", (old, *extra)
    )["n"]
    devices = db.query(
        f"SELECT id FROM push_subscription WHERE last_seen_at < ?{scope}", (unseen, *extra)
    )
    if not dry_run:
        db.execute(f"DELETE FROM push_outbox WHERE created_at < ?{scope}", (old, *extra))
        for device in devices:
            _drop(int(device["id"]))
    return int(alerts) + len(devices)
```

Run: `cd App && .venv/bin/python -c "import app.push" 2>&1 | tail -3`. Expected: no error.

**Step 6.** `App/app/retention.py`. Anchor: `        cur.execute("DELETE FROM webauthn_challenge WHERE user_account_id = ?", (owner_id,))`. Insert after it:

```python
        # Brief 0204: urgent-alert devices and their queue (also cascade).
        cur.execute("DELETE FROM push_outbox WHERE user_account_id = ?", (owner_id,))
        cur.execute("DELETE FROM push_subscription WHERE user_account_id = ?", (owner_id,))
```

**Step 7.** `App/app/retention.py`. Anchor: `# Each step takes (today, dry_run, owner_user_id) and returns the affected count.`. Insert before it:

```python
def _push_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Brief 0204: alerts 30 days after they were queued; devices unseen 180 days."""
    from . import push
    return push.purge(dry_run=dry_run, owner_user_id=owner_user_id)


```

Then in `STEPS`, replace `    ("cleaning", _cleaning_step),` with:

```python
    ("cleaning", _cleaning_step),
    ("push", _push_step),
```

Then in `_cutoffs`, anchor `        "cleaning": f"event or link expiry before {(today - timedelta(days=30)).isoformat()}",` and insert after it:

```python
        "push": "alert queued over 30 days ago, or device unseen for 180 days",
```

**Step 8.** `App/app/scheduler.py`, four edits:

a. In the `from . import (` list, replace `    passport_photos,` with `    passport_photos,` + newline + `    push,`.

b. In `_JOB_LEVELS`, replace `    "door_codes": "warning",` with `    "door_codes": "warning",` + newline + `    "push": "warning",`.

c. In `job_intervals`, replace `        "posthog": 15,` with `        "posthog": 15,` + newline + `        "push": 1,`.

d. Anchor `def _job_retention() -> None:`. Insert before it:

```python
def _job_push() -> None:
    """Brief 0204: send the urgent alerts that are due."""
    started = time.perf_counter()
    try:
        summary = push.drain()
        if summary:
            log.info("push: %s", summary)
    except Exception:
        log.exception("push job failed")
        _job_failed("push")
        _log_run("push", started, False)
        return
    _job_ok("push")
    _log_run("push", started, True, summary)


```

e. Anchor (the posthog job):

```python
    _scheduler.add_job(
        _job_posthog, "interval", minutes=minutes["posthog"],
        id="posthog", max_instances=1, coalesce=True,
    )
```

Insert after it:

```python
    _scheduler.add_job(
        _job_push, "interval", minutes=minutes["push"],
        id="push", max_instances=1, coalesce=True,
    )
```

Run: `cd App && .venv/bin/python -c "import app.scheduler" 2>&1 | tail -3`. Expected: no error.

**Step 9.** `App/app/host_i18n.py`. Anchor (added by 0203):

```python
for _lang, _strings in _PWA_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert after it:

```python

# Brief 0204: the urgent alerts. Short: a lock screen shows about two lines.
_PUSH_MESSAGE_STRINGS = {
    "en": {
        "push.msg.filing_problem.title": "Police report not accepted",
        "push.msg.filing_problem.body": "%(property)s: UbyPort did not accept the report. Open UbyHost to see why and send it again.",
        "push.msg.deadline_at_risk.title": "Police deadline at risk",
        "push.msg.deadline_at_risk.body": "%(property)s, arrival %(date)s: guests are not reported yet. Deadline %(deadline)s.",
        "push.msg.door_code.title": "Door code missing",
        "push.msg.door_code.body": "%(property)s, arrival %(date)s: the guests have no door code yet. See the e-mail we sent you.",
        "push.msg.cancelled_with_guests.title": "Cancelled stay had registered guests",
        "push.msg.cancelled_with_guests.body": "%(property)s, %(date)s: nothing will be reported for it. If the booking only moved, set the stay back to Active.",
        "push.msg.test.title": "Alerts are on",
        "push.msg.test.body": "This device will get urgent UbyHost alerts.",
        "notification.job_name.push": "urgent alerts",
    },
    "cs": {
        "push.msg.filing_problem.title": "Hlášení policii nepřijato",
        "push.msg.filing_problem.body": "%(property)s: UbyPort hlášení nepřijal. Otevřete UbyHost, zjistěte proč a odešlete ho znovu.",
        "push.msg.deadline_at_risk.title": "Hrozí zmeškání lhůty pro policii",
        "push.msg.deadline_at_risk.body": "%(property)s, příjezd %(date)s: hosté zatím nejsou nahlášeni. Termín %(deadline)s.",
        "push.msg.door_code.title": "Chybí kód ke dveřím",
        "push.msg.door_code.body": "%(property)s, příjezd %(date)s: hosté zatím nemají kód ke dveřím. Podívejte se do e-mailu, který jsme vám poslali.",
        "push.msg.cancelled_with_guests.title": "Zrušený pobyt měl registrované hosty",
        "push.msg.cancelled_with_guests.body": "%(property)s, %(date)s: nic se za něj nenahlásí. Pokud se rezervace jen přesunula, nastavte pobyt zpět na Aktivní.",
        "push.msg.test.title": "Upozornění jsou zapnutá",
        "push.msg.test.body": "Toto zařízení bude dostávat naléhavá upozornění UbyHost.",
        "notification.job_name.push": "naléhavá upozornění",
    },
}
for _lang, _strings in _PUSH_MESSAGE_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

**Step 10.** `App/app/host_vi_i18n.py`. Anchor (added by 0203): `    "offline.retry": "Thử lại",`. Insert after it:

```python
    # Brief 0204: urgent alerts.
    "push.msg.filing_problem.title": "Báo cáo cho cảnh sát không được chấp nhận",
    "push.msg.filing_problem.body": "%(property)s: UbyPort không chấp nhận báo cáo. Mở UbyHost để xem lý do và gửi lại.",
    "push.msg.deadline_at_risk.title": "Sắp trễ hạn khai báo cảnh sát",
    "push.msg.deadline_at_risk.body": "%(property)s, ngày đến %(date)s: khách chưa được khai báo. Hạn chót %(deadline)s.",
    "push.msg.door_code.title": "Thiếu mã cửa",
    "push.msg.door_code.body": "%(property)s, ngày đến %(date)s: khách chưa có mã cửa. Hãy xem email chúng tôi đã gửi cho bạn.",
    "push.msg.cancelled_with_guests.title": "Lượt lưu trú bị hủy đã có khách đăng ký",
    "push.msg.cancelled_with_guests.body": "%(property)s, %(date)s: sẽ không có gì được khai báo. Nếu đặt phòng chỉ bị dời, hãy đặt lượt lưu trú về Đang hoạt động.",
    "push.msg.test.title": "Đã bật cảnh báo",
    "push.msg.test.body": "Thiết bị này sẽ nhận cảnh báo khẩn từ UbyHost.",
    "notification.job_name.push": "cảnh báo khẩn",
```

**Step 11.** `docs/ENVIRONMENT.md`. Anchor: the line `## Accounts`. Insert before it:

```markdown
## Urgent alerts (web push)

| Variable | Default | Notes |
| --- | --- | --- |
| `UBYHOST_WEB_PUSH` | `1` | `0`, `false` or `no` switches phone alerts off: nothing is queued or sent, and Settings hides the switch. |

No key to set: the app makes its push signing key (VAPID) on first use and keeps it encrypted with `UBYHOST_SECRET_KEY` in the `settings` table. Rotating the secret key makes a new push key, and every host turns alerts on again in Settings. Outbound: HTTPS POST to the browser's push service only (`fcm.googleapis.com`, `*.push.services.mozilla.com`, `web.push.apple.com`, `*.notify.windows.com`), body end-to-end encrypted.

```

**Step 12.** Create `App/tests/test_push.py` with exactly:

```python
"""Brief 0204: urgent alerts on the host's phone: devices, queue and delivery."""
from __future__ import annotations

import json
import os
import secrets
import struct
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import auth, config, db, host_vi_i18n, push, retention, scheduler, webpush

FCM = "https://fcm.googleapis.com/fcm/send/"


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "WEB_PUSH", True)
    yield


def _new_account() -> int:
    username = f"push{secrets.token_hex(4)}"
    return auth.create_account(f"{username}@example.test", "Push Host", role="host", username=username)


def _forget(owner: int) -> None:
    db.execute("DELETE FROM push_outbox WHERE user_account_id = ?", (owner,))
    db.execute("DELETE FROM push_subscription WHERE user_account_id = ?", (owner,))


@pytest.fixture
def account():
    owner = _new_account()
    yield owner
    _forget(owner)


class Browser:
    """A stand-in browser: its own key pair and auth secret, as pushManager makes them."""

    def __init__(self, endpoint=None):
        self.key = webpush.new_private_key()
        self.auth = os.urandom(16)
        self.endpoint = FCM + secrets.token_hex(8) if endpoint is None else endpoint

    def subscription(self):
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": webpush.b64url(webpush.public_raw(self.key)),
                "auth": webpush.b64url(self.auth),
            },
        }

    def read(self, body: bytes) -> dict:
        """Decrypt a push the way the browser does (RFC 8291)."""
        salt = body[:16]
        record_size, key_len = struct.unpack("!IB", body[16:21])
        as_public = body[21:21 + key_len]
        ua_public = webpush.public_raw(self.key)
        ecdh = self.key.exchange(ec.ECDH(), webpush.check_public_key(as_public))
        ikm = webpush._hkdf(self.auth, ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
        cek = webpush._hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = webpush._hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        plain = AESGCM(cek).decrypt(nonce, body[21 + key_len:], None)
        assert record_size == 4096 and plain.endswith(b"\x02")
        return json.loads(plain[:-1])


class PushService:
    """Records what would have gone to Apple or Google and answers ``status``."""

    def __init__(self, monkeypatch, status=201):
        self.status = status
        self.sent = []
        monkeypatch.setattr(webpush.requests, "post", self._post)

    def _post(self, url, data, headers, timeout, allow_redirects):
        self.sent.append({"url": url, "data": data, "headers": headers})
        if isinstance(self.status, Exception):
            raise self.status
        answer = type("Answer", (), {})()
        answer.status_code = self.status
        return answer


def _subscribe(account, browser=None, lang="en"):
    browser = browser or Browser()
    push.save_subscription(account, browser.subscription(), lang=lang, device="iPhone")
    return browser


def _later(minutes):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@pytest.mark.parametrize("endpoint", [
    "https://169.254.169.254/latest/meta-data",
    "http://fcm.googleapis.com/fcm/send/x",
    "https://evil.example/fcm.googleapis.com/x",
    "https://fcm.googleapis.com.evil.example/x",
    "https://user:pw@fcm.googleapis.com/x",
    "https://fcm.googleapis.com:8443/x",
    "file:///etc/passwd",
    "",
])
def test_only_real_push_services_are_accepted(account, endpoint):
    with pytest.raises(push.SubscriptionError):
        push.save_subscription(account, Browser(endpoint).subscription(), lang="en", device="")


@pytest.mark.parametrize("endpoint", [
    "https://fcm.googleapis.com/fcm/send/abc",
    "https://web.push.apple.com/QGxabc",
    "https://updates.push.services.mozilla.com/wpush/v2/abc",
    "https://wns2-par02p.notify.windows.com/w/?token=abc",
])
def test_the_four_browser_push_services_are_accepted(account, endpoint):
    assert push.save_subscription(account, Browser(endpoint).subscription(), lang="en", device="Mac")


def test_bad_keys_are_refused(account):
    bad_point = Browser().subscription()
    bad_point["keys"]["p256dh"] = "not-a-key"
    short_secret = Browser().subscription()
    short_secret["keys"]["auth"] = webpush.b64url(b"short")
    for subscription in (bad_point, short_secret, "nonsense", {"endpoint": FCM + "x"}):
        with pytest.raises(push.SubscriptionError):
            push.save_subscription(account, subscription, lang="en", device="")


def test_the_push_address_and_keys_are_stored_encrypted(account):
    browser = _subscribe(account)
    row = db.query_one("SELECT * FROM push_subscription WHERE user_account_id = ?", (account,))
    stored = " ".join(str(value) for value in dict(row).values())
    assert browser.endpoint not in stored
    assert browser.subscription()["keys"]["p256dh"] not in stored
    assert browser.subscription()["keys"]["auth"] not in stored
    assert row["device"] == "iPhone" and row["lang"] == "en"


def test_one_browser_is_one_row_and_follows_the_account_signed_in(account):
    browser = _subscribe(account)
    _subscribe(account, browser, lang="cs")
    assert push.count_for(account) == 1
    other = _new_account()
    try:
        push.notify(account, "door_code", key="stay1", url="/reservations/1", params={})
        _subscribe(other, browser)
        assert push.count_for(account) == 0 and push.count_for(other) == 1
        # An alert queued for the first account never reaches the next person.
        assert not db.query_one("SELECT 1 AS x FROM push_outbox WHERE user_account_id = ?", (account,))
    finally:
        _forget(other)


def test_an_account_has_at_most_ten_devices(account):
    for _ in range(push.MAX_DEVICES):
        _subscribe(account)
    with pytest.raises(push.SubscriptionError):
        _subscribe(account)


def test_notify_queues_once_per_device_and_never_twice_for_one_event(account):
    _subscribe(account)
    _subscribe(account)
    args = dict(key="7:2026-10-21", url="/apartments/7", params={"property": "Flat"})
    assert push.notify(account, "filing_problem", **args) == 2
    assert push.notify(account, "filing_problem", **args) == 0


def test_only_the_four_urgent_kinds_can_be_queued_and_notify_never_raises(account):
    _subscribe(account)
    assert push.KINDS == ("filing_problem", "deadline_at_risk", "door_code", "cancelled_with_guests")
    assert push.notify(account, "guests_registered", key="1", url="/", params={}) == 0
    assert push.notify(account, "test", key="1", url="/", params={}) == 0
    assert push.notify(None, "door_code", key="1", url="/", params={}) == 0


def test_notify_does_nothing_when_push_is_switched_off(account, monkeypatch):
    _subscribe(account)
    monkeypatch.setattr(config, "WEB_PUSH", False)
    assert push.notify(account, "door_code", key="1", url="/", params={}) == 0
    assert push.drain() == {}


def test_a_delivered_alert_is_encrypted_for_the_device_in_its_language(account, monkeypatch):
    browser = _subscribe(account, lang="cs")
    service = PushService(monkeypatch)
    push.notify(
        account, "deadline_at_risk", key="stay9", url="/reservations/9",
        params={"property": "Byt 1", "date": "21.10.2026", "deadline": "23.10.2026 14:00"},
    )
    assert push.drain() == {"sent": 1}
    [request] = service.sent
    assert request["url"] == browser.endpoint
    message = browser.read(request["data"])
    assert message["title"] == "Hrozí zmeškání lhůty pro policii"
    assert "Byt 1" in message["body"] and "23.10.2026 14:00" in message["body"]
    assert message["url"] == "/reservations/9"
    assert message["tag"] == "deadline_at_risk:stay9"
    assert push.drain() == {}


def test_an_outside_address_never_becomes_the_click_target(account, monkeypatch):
    browser = _subscribe(account)
    service = PushService(monkeypatch)
    push.notify(account, "door_code", key="x", url="https://evil.example/", params={})
    push.drain()
    assert browser.read(service.sent[0]["data"])["url"] == "/"


def test_a_gone_device_is_forgotten(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=410)
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"gone": 1}
    assert push.count_for(account) == 0


def test_a_busy_push_service_is_retried_then_given_up_after_five_tries(account, monkeypatch):
    _subscribe(account)
    service = PushService(monkeypatch, status=503)
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"retry": 1}
    assert push.drain() == {}
    for minutes in (2, 8, 25, 90):
        push.drain(now=_later(minutes))
    row = db.query_one(
        "SELECT state, attempts, last_status FROM push_outbox WHERE user_account_id = ?", (account,)
    )
    assert (row["state"], row["attempts"], row["last_status"]) == ("failed", 5, 503)
    assert len(service.sent) == 5


def test_an_unreachable_push_service_is_retried(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=webpush.requests.ConnectionError("down"))
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"retry": 1}


def test_a_refusing_push_service_drops_the_device_after_five_refusals(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=400)
    for n in range(push.MAX_FAILURES):
        push.notify(account, "door_code", key=f"x{n}", url="/", params={})
        assert push.drain() == {"failed": 1}
    assert push.count_for(account) == 0


def test_one_device_gets_at_most_the_daily_cap(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch)
    for n in range(push.DAILY_CAP + 2):
        push.notify(account, "door_code", key=f"s{n}", url="/", params={})
    assert push.drain() == {"sent": push.DAILY_CAP, "capped": 2}


def test_the_test_alert_goes_to_this_device_only_and_now(account, monkeypatch):
    first = _subscribe(account)
    _subscribe(account)
    service = PushService(monkeypatch)
    assert push.send_test(account, first.endpoint) == "sent"
    assert len(service.sent) == 1
    assert first.read(service.sent[0]["data"])["title"] == "Alerts are on"
    assert push.send_test(account, FCM + "unknown") == "gone"


def test_the_server_key_is_made_once_and_kept():
    assert push.public_key() == push.public_key()
    assert len(webpush.unb64url(push.public_key())) == 65


def test_an_unreadable_server_key_is_replaced_and_its_devices_dropped(account):
    _subscribe(account)
    before = push.public_key()
    db.set_setting(push.VAPID_SETTING, "not-a-fernet-token")
    assert push.public_key() != before
    assert push.count_for(account) == 0


def test_retention_deletes_old_alerts_and_unseen_devices(account):
    _subscribe(account)
    push.notify(account, "door_code", key="old", url="/", params={})
    long_ago = (datetime.now(timezone.utc) - timedelta(days=200)).replace(microsecond=0).isoformat()
    db.execute("UPDATE push_outbox SET created_at = ? WHERE user_account_id = ?", (long_ago, account))
    assert push.purge(dry_run=True, owner_user_id=account) == 1
    db.execute("UPDATE push_subscription SET last_seen_at = ? WHERE user_account_id = ?", (long_ago, account))
    assert push.purge(owner_user_id=account) == 2
    assert push.count_for(account) == 0
    assert "push" in dict(retention.STEPS)


def test_deleting_a_workspace_deletes_its_devices_and_alerts():
    owner = _new_account()
    _subscribe(owner)
    push.notify(owner, "door_code", key="w", url="/", params={})
    retention._delete_workspace(owner)
    assert not db.query_one("SELECT 1 AS x FROM push_subscription WHERE user_account_id = ?", (owner,))
    assert not db.query_one("SELECT 1 AS x FROM push_outbox WHERE user_account_id = ?", (owner,))


def test_the_scheduler_sends_alerts_every_minute(monkeypatch):
    called = []
    monkeypatch.setattr(push, "drain", lambda: called.append(1) or {})
    scheduler._job_push()
    assert called and scheduler.job_intervals()["push"] == 1
    assert scheduler._JOB_LEVELS["push"] == "warning"


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_every_alert_has_its_own_title_and_body_in_every_host_language(lang):
    params = {"property": "P", "date": "D", "deadline": "X"}
    for kind in push.KINDS + (push.TEST_KIND,):
        text = push.message(kind, lang, params)
        assert text["title"] != f"push.msg.{kind}.title"
        assert text["body"] != f"push.msg.{kind}.body"
        if lang == "vi":
            assert f"push.msg.{kind}.title" in host_vi_i18n.STRINGS
            assert f"push.msg.{kind}.body" in host_vi_i18n.STRINGS
```

Run: `cd App && .venv/bin/python -m pytest tests/test_push.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass. If a test fails, fix the code once (never the test's expectation), rerun; fails again: STOP.

## 5. Do not touch

Anything that calls `push.notify` (0206 wires the events), any template, any static file, `requirements*.txt`. Hard rules: no new dependency; SQL through `db` helpers and Postgres-portable; never log an endpoint, a key or a guest field; no em dashes in copy.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_webpush.py tests/test_push.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x`
2. `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py tests/test_no_tracking.py tests/test_cookie_inventory.py tests/test_pii_encryption.py tests/test_dsr_audit.py tests/test_data_keys.py -q --tb=short -x`
3. `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_meta_capi.py -q --tb=short -x`
4. From the repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] §6 commands pass.
- [ ] `test_encryption_reproduces_the_rfc_8291_example_byte_for_byte` passes.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE §8. Also stop if a retention or privacy test outside §3 needs a change (report which assertion).

## 9. Report

`docs/tasks/0204-report.md` per TEMPLATE §9; set `Status: review`.

## Risk list (for the reviewer)

`App/app/webpush.py`, `App/app/push.py` (SSRF allowlist, claim, retry, cap), `App/app/migrations/0011_web_push.sql`, `App/app/retention.py`.

## Owner steps

None: no key or env var to set. `UBYHOST_WEB_PUSH=0` in `.env` is the off switch.
