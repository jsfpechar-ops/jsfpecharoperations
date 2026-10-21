# 0204: Push engine (keys, encryption, device list, queue, delivery, retention)

Status: done
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
# Compacted after review: the committed App/app/push.py (5588290) is the source of truth.
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
# Compacted after review: the committed App/tests/test_push.py (aed2955) is the source of truth.
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
