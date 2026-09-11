"""Verify guest PIN gate in a fresh process (config loads at import time)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("UBYHOST_DATA_DIR", tempfile.mkdtemp(prefix="ubyhost-pin-"))
os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ["UBYHOST_BOOTSTRAP_ADMIN"] = "0"
os.environ["UBYHOST_GUEST_PIN"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402

db.init_db()
now = db.utcnow()
entity_id = db.insert(
    "legal_entity",
    {"name": "PIN Test", "seat": "Praha", "ico": "99999999", "created_at": now},
)
db.insert(
    "apartment",
    {
        "legal_entity_id": entity_id,
        "internal_name": "PIN flat",
        "city_en": "Prague",
        "permalink_token": "pintoken",
        "permalink_window_days": 14,
        "default_purpose": "10",
        "automation_mode": "manual",
        "active": 1,
        "created_at": now,
    },
)
response = TestClient(app).get("/l/pintoken")
if response.status_code == 200 and "PIN" in response.text:
    print("OK")
else:
    print(f"FAIL {response.status_code}")
