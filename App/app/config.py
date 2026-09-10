"""Runtime configuration, read from the environment with safe local defaults."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = Path(os.environ.get("UBYHOST_DATA_DIR", PROJECT_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("UBYHOST_DB", DATA_DIR / "ubyhost.db"))

# The secret key signs session cookies and derives the key that encrypts
# UbyPort passwords at rest. Losing it means re-entering those passwords.
_SECRET_FILE = DATA_DIR / "secret_key"


def _load_secret() -> str:
    env = os.environ.get("UBYHOST_SECRET_KEY")
    if env:
        return env
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    generated = secrets.token_urlsafe(48)
    _SECRET_FILE.write_text(generated)
    try:
        _SECRET_FILE.chmod(0o600)
    except OSError:
        pass
    return generated


SECRET_KEY = _load_secret()

# "mock" | "test" | "prod".  Controls which UbyPort endpoint submissions go to.
UBYPORT_ENV = os.environ.get("UBYHOST_UBYPORT_ENV", "mock").lower()

UBYPORT_ENDPOINTS = {
    "test": "https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc",
    "prod": "https://ubyport.pcr.cz/ws_uby/ws_uby.svc",
    "mock": os.environ.get("UBYHOST_MOCK_URL", "http://127.0.0.1:8081/ws_uby/ws_uby.svc"),
}

# NTLM domain the police authenticate web-service accounts against.
UBYPORT_DOMAIN = os.environ.get("UBYHOST_UBYPORT_DOMAIN", "EXRESORTMV")

# Hard ceiling from the spec; refreshed at runtime via MaximalniDelkaSeznamu.
UBYPORT_MAX_BATCH = int(os.environ.get("UBYHOST_MAX_BATCH", "32"))

UBYPORT_TIMEOUT = int(os.environ.get("UBYHOST_UBYPORT_TIMEOUT", "60"))

ICAL_POLL_MINUTES = int(os.environ.get("UBYHOST_ICAL_POLL_MINUTES", "60"))
SUBMIT_SWEEP_MINUTES = int(os.environ.get("UBYHOST_SUBMIT_SWEEP_MINUTES", "10"))

# Used to build the guest permalink shown to hosts for copy/paste.
PUBLIC_BASE_URL = os.environ.get("UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")

ENABLE_SCHEDULER = os.environ.get("UBYHOST_ENABLE_SCHEDULER", "1") not in ("0", "false", "no")

GUEST_PIN_REQUIRED = os.environ.get("UBYHOST_GUEST_PIN", "1") not in ("0", "false", "no")

TIMEZONE = "Europe/Prague"


def endpoint_for(env: str = None) -> str:
    return UBYPORT_ENDPOINTS.get((env or UBYPORT_ENV), UBYPORT_ENDPOINTS["mock"])
