"""Write the Web Push golden file for the Go port (brief 0683).

Run from App/: ``.venv/bin/python scripts/webpush_golden.py``. It loads
``app/webpush.py`` by path (no package import) and writes
``go/internal/webpush/testdata/golden.json`` with fixed keys, salt and time,
so the Go tests can check that their bytes equal Python's.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "App" / "app" / "webpush.py"
OUT = ROOT / "go" / "internal" / "webpush" / "testdata" / "golden.json"

spec = importlib.util.spec_from_file_location("webpush_src", SOURCE)
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)

UA_PRIVATE = bytes(range(1, 33))
AS_PRIVATE = bytes(range(101, 133))
AUTH_SECRET = bytes(range(200, 216))
SALT = bytes(range(50, 66))
VAPID_PRIVATE = bytes(range(7, 39))
PAYLOAD = '{"message": "Čau é", "url": "/x", "tag": "t", "lang": "cs"}'.encode("utf-8")
ENDPOINT = "https://push.example.net/send/abc123"
SUBJECT = "mailto:ops@example.org"
NOW = 1767225600

ua_key = wp.private_from_raw(UA_PRIVATE)
ua_public = wp.public_raw(ua_key)
as_key = wp.private_from_raw(AS_PRIVATE)
vapid_key = wp.private_from_raw(VAPID_PRIVATE)
body = wp.encrypt(PAYLOAD, ua_public, AUTH_SECRET, as_private=as_key, salt=SALT)
audience = "https://push.example.net"
header = wp.vapid_header(vapid_key, audience, SUBJECT, now=NOW)

golden = {
    "ua_private": UA_PRIVATE.hex(),
    "ua_public": ua_public.hex(),
    "auth_secret": AUTH_SECRET.hex(),
    "as_private": AS_PRIVATE.hex(),
    "salt": SALT.hex(),
    "vapid_private": VAPID_PRIVATE.hex(),
    "payload": PAYLOAD.decode("utf-8"),
    "endpoint": ENDPOINT,
    "subject": SUBJECT,
    "now": NOW,
    "body": body.hex(),
    "vapid_authorization": header,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(golden, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", OUT, "body bytes", len(body))
