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

# Logical deployment tier shown in the UI and health checks: local | staging | production.
DEPLOYMENT = os.environ.get("UBYHOST_DEPLOYMENT", "local").lower()

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

# A first administrator is created once on startup. Set both values in a
# deployed environment; when the password is omitted a random one is written
# once to DATA_DIR/initial_admin_credentials with owner-only permissions.
BOOTSTRAP_ADMIN = os.environ.get("UBYHOST_BOOTSTRAP_ADMIN", "1") not in ("0", "false", "no")
ADMIN_USERNAME = os.environ.get("UBYHOST_ADMIN_USERNAME", "admin").strip().lower()
ADMIN_PASSWORD = os.environ.get("UBYHOST_ADMIN_PASSWORD", "")

TIMEZONE = "Europe/Prague"

# Software operator (shown in legal notices). Override via environment in production.
OPERATOR_NAME = os.environ.get("UBYHOST_OPERATOR_NAME", "Josef Pechar")
OPERATOR_ICO = os.environ.get("UBYHOST_OPERATOR_ICO", "24005169")
OPERATOR_DIC = os.environ.get("UBYHOST_OPERATOR_DIC", "CZ0101190518")
OPERATOR_ADDRESS = os.environ.get(
    "UBYHOST_OPERATOR_ADDRESS",
    "Kubelíkova 697/13, 13000 Praha 3",
)
OPERATOR_EMAIL = os.environ.get("UBYHOST_OPERATOR_EMAIL", "").strip()
OPERATOR_REGISTRY_URL = os.environ.get(
    "UBYHOST_OPERATOR_REGISTRY_URL",
    "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/24005169",
)

# Bumped when Terms of Service change materially (logged on host login).
TERMS_VERSION = os.environ.get("UBYHOST_TERMS_VERSION", "1.0")

# Bumped when the public Privacy Policy changes materially.
PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.0")


def endpoint_for(env: str = None) -> str:
    return UBYPORT_ENDPOINTS.get((env or UBYPORT_ENV), UBYPORT_ENDPOINTS["mock"])
