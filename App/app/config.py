"""Runtime configuration, read from the environment with safe local defaults.

Everything here is a plain read of the environment except the data directory
and the signing key, and those two are deliberately *not* done at import time:
importing this module is what a test run, a lint or a one-off tool does, and
none of them should create a directory on the host or write a secret to disk.
``ensure_data_dir()`` and ``secret_key()`` do that work when the application is
actually starting or actually signing something.
"""
from __future__ import annotations

import os
import secrets
from datetime import date
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = Path(os.environ.get("UBYHOST_DATA_DIR", PROJECT_DIR / "data"))

DB_PATH = Path(os.environ.get("UBYHOST_DB", DATA_DIR / "ubyhost.db"))

# The secret key signs session cookies. Until UBYHOST_DATA_KEYS is set it also
# derives the key that encrypts data at rest (see data_keys() below).
_SECRET_FILE = DATA_DIR / "secret_key"


def ensure_data_dir() -> Path:
    """Create the private data directory. Idempotent, and safe to call late.

    Called from ``db.init_db()`` and from the app lifespan rather than at
    import, so importing the module cannot write to the filesystem.
    """
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        DATA_DIR.chmod(0o700)
    except OSError:
        pass
    return DATA_DIR


def _load_secret() -> str:
    env = os.environ.get("UBYHOST_SECRET_KEY")
    if env:
        if len(env) < 32:
            raise RuntimeError("UBYHOST_SECRET_KEY must contain at least 32 characters.")
        return env
    if _SECRET_FILE.exists():
        try:
            _SECRET_FILE.chmod(0o600)
        except OSError:
            pass
        stored = _SECRET_FILE.read_text().strip()
        if len(stored) < 32:
            raise RuntimeError(f"{_SECRET_FILE} is empty or too short.")
        return stored
    generated = secrets.token_urlsafe(48)
    try:
        descriptor = os.open(_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _load_secret()
    with os.fdopen(descriptor, "w") as handle:
        handle.write(generated)
    return generated


_SECRET_KEY: Optional[str] = None


def secret_key() -> str:
    """The signing/encryption key, generated on first use.

    A function rather than a module constant because generating it writes a
    file, and because a constant loaded at import is a constant that cannot be
    absent — an empty one would sign sessions with a key anyone can guess and
    derive the database encryption key from it. This way there is no state in
    which the app runs with no key at all.
    """
    global _SECRET_KEY
    if _SECRET_KEY is None:
        _SECRET_KEY = _load_secret()
    return _SECRET_KEY


def require_secret_key() -> str:
    """The key, refusing to create one.

    ``secret_key()`` mints a key on first use, which is right for the app and
    wrong for a tool that writes encrypted data: it would encrypt under a key
    the running app has never seen, and every record it touched would be
    unreadable. Such a tool calls this instead and stops when no key is
    established yet.
    """
    if not os.environ.get("UBYHOST_SECRET_KEY") and not _SECRET_FILE.exists():
        raise RuntimeError(
            f"no UBYHOST_SECRET_KEY is set and there is no key file at {_SECRET_FILE}"
        )
    return secret_key()


def data_keys() -> List[str]:
    """The data-encryption keys from ``UBYHOST_DATA_KEYS``, newest first.

    Comma-separated Fernet keys (``Fernet.generate_key()``). The first one
    encrypts everything written from now on; every key in the list is tried
    when reading. They are separate from ``UBYHOST_SECRET_KEY`` so that the
    session-signing secret can be rotated without making stored data
    unreadable. Read on every call rather than cached, so a test or a tool can
    change the environment; the cost is a string split.
    """
    raw = os.environ.get("UBYHOST_DATA_KEYS", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def legacy_data_key_enabled() -> bool:
    """Whether the old key derived from the session secret is still tried.

    On by default, and forced on while no ``UBYHOST_DATA_KEYS`` is set, because
    then it is the only key there is. Turn it off with
    ``UBYHOST_DATA_KEY_LEGACY=0`` once ``scripts/reencrypt.py`` has moved every
    value to the new key and its ``--check`` reports nothing left.
    """
    value = os.environ.get("UBYHOST_DATA_KEY_LEGACY", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


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

# Read once at start-up. The "test connection" button reports the service's own limit but does not change this value.
UBYPORT_MAX_BATCH = int(os.environ.get("UBYHOST_MAX_BATCH", "32"))

UBYPORT_TIMEOUT = int(os.environ.get("UBYHOST_UBYPORT_TIMEOUT", "60"))

ICAL_POLL_MINUTES = int(os.environ.get("UBYHOST_ICAL_POLL_MINUTES", "60"))
SUBMIT_SWEEP_MINUTES = int(os.environ.get("UBYHOST_SUBMIT_SWEEP_MINUTES", "10"))
# Dead-man switches (for example healthchecks.io), each pinged after a
# successful run of its job: the submission sweep, the calendar sync and the
# mail job (WP07). Empty disables the ping.
HEARTBEAT_URL = os.environ.get("UBYHOST_HEARTBEAT_URL", "").strip()
HEARTBEAT_ICAL_URL = os.environ.get("UBYHOST_HEARTBEAT_ICAL_URL", "").strip()
HEARTBEAT_MAIL_URL = os.environ.get("UBYHOST_HEARTBEAT_MAIL_URL", "").strip()
# Filing watchdog (WP23). Unlike the three above, this one is pinged on every
# run of the deadline job: <url> while no stay is at risk of missing its police
# deadline, <url>/fail while at least one is (healthchecks.io semantics). The
# healthchecks.io check then notifies the owner by e-mail. That mail comes from
# healthchecks.io, not from UbyHost's own mail, so it still arrives when
# UbyHost's mail is broken, and it fires on the missing ping when the VM is
# down. Empty disables it.
HEARTBEAT_FILING_URL = os.environ.get("UBYHOST_HEARTBEAT_FILING_URL", "").strip()

# Door codes (TTLock). Off unless UBYHOST_DOOR_CODES=1; the secret is env only.
DOOR_CODES_ENABLED = os.environ.get("UBYHOST_DOOR_CODES", "0") in ("1", "true", "yes")
TTLOCK_API_BASE = os.environ.get("UBYHOST_TTLOCK_API_BASE", "https://euapi.ttlock.com").rstrip("/")
TTLOCK_CLIENT_ID = os.environ.get("UBYHOST_TTLOCK_CLIENT_ID", "").strip()
TTLOCK_CLIENT_SECRET = os.environ.get("UBYHOST_TTLOCK_CLIENT_SECRET", "").strip()
TTLOCK_MONTHLY_CALLS = int(os.environ.get("UBYHOST_TTLOCK_MONTHLY_CALLS", "30000"))
# Codes work from 1 h before check-in to 1 h after check-out: covers lock clock
# drift and any daylight-saving mismatch in the lock. Hours have no default; the host sets them.
DOOR_CODE_BUFFER_HOURS = 1
# Until this is on, only stays added by hand (reservation.source = 'manual') get a door code.
DOOR_CODES_LIVE = os.environ.get("UBYHOST_DOOR_CODES_LIVE", "0") in ("1", "true", "yes")

# Used to build the guest permalink shown to hosts for copy/paste.
PUBLIC_BASE_URL = os.environ.get("UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")

ENABLE_SCHEDULER = os.environ.get("UBYHOST_ENABLE_SCHEDULER", "1") not in ("0", "false", "no")

# WP06: what this process runs. "web" serves HTTP and never starts the
# scheduler (production runs two uvicorn workers); "worker" runs only the
# background jobs (``python -m app.worker``); "all" does both in one process,
# for local development and the single-process Render staging service.
ROLES = ("web", "worker", "all")
ROLE = os.environ.get("UBYHOST_ROLE", "web").strip().lower() or "web"
# One PII-free access line per request (OPS-3). Off in production by the
# Dockerfile's --no-access-log; this flag is the app-level switch.
ACCESS_LOG = os.environ.get("UBYHOST_ACCESS_LOG", "1") not in ("0", "false", "no")

# BE-2: the retention job computes and audits its row set but deletes nothing
# until this is set (Rule 7). The owner turns this on when they accept WP22.
RETENTION_AUTOPURGE = os.environ.get("UBYHOST_RETENTION_AUTOPURGE", "0") in (
    "1", "true", "yes",
)
# WP12: the three lifecycle tips to hosts (no property, no calendar, no guest
# yet). Off until counsel confirms the legal basis and the opt-out wording
# under Czech Act 480/2004; service mail is not affected either way.
LIFECYCLE_MAIL = os.environ.get("UBYHOST_LIFECYCLE_MAIL", "0").lower() in ("1", "true", "yes")
# How far ahead the "records reach the end of their retention period" notice looks.
RETENTION_NOTICE_DAYS = int(os.environ.get("UBYHOST_RETENTION_NOTICE_DAYS", "30"))

# G-D7 windows for the log and evidence tables.
AUDIT_RETENTION_DAYS = int(os.environ.get("UBYHOST_AUDIT_RETENTION_DAYS", "1095"))
ALERT_RETENTION_DAYS = int(os.environ.get("UBYHOST_ALERT_RETENTION_DAYS", "365"))
RATE_LIMIT_RETENTION_HOURS = int(os.environ.get("UBYHOST_RATE_LIMIT_RETENTION_HOURS", "24"))

# BE-9: whether a restricted record is withheld from police filing. Off until
# counsel decides whether the statutory duty still requires it (Rule: LEGAL-GATED).
RESTRICTED_BLOCKS_FILING = os.environ.get("UBYHOST_RESTRICTED_BLOCKS_FILING", "0") in (
    "1", "true", "yes",
)

GUEST_PIN_REQUIRED = os.environ.get("UBYHOST_GUEST_PIN", "1") not in ("0", "false", "no")

# A first administrator is created once on startup, on an empty database. They
# log in with UBYHOST_ADMIN_EMAIL (falls back to UBYHOST_OPERATOR_EMAIL). Their
# first login link is written once to DATA_DIR/initial_admin_login with
# owner-only permissions, because mail may not be set up yet on a new server.
BOOTSTRAP_ADMIN = os.environ.get("UBYHOST_BOOTSTRAP_ADMIN", "1") not in ("0", "false", "no")
ADMIN_USERNAME = os.environ.get("UBYHOST_ADMIN_USERNAME", "admin").strip().lower()
ADMIN_EMAIL = os.environ.get("UBYHOST_ADMIN_EMAIL", "").strip()
# Render staging only: shared break-glass password (console mail, no SES). Never on production.
def _staging_login_password_from_env() -> str:
    raw = os.environ.get("UBYHOST_STAGING_LOGIN_PASSWORD", "")
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


STAGING_LOGIN_PASSWORD = _staging_login_password_from_env()

# Render staging only: skip login entirely, every visitor is the first administrator.
# Ignored unless UBYHOST_DEPLOYMENT=staging. Never set this where real data lives.
STAGING_NO_LOGIN = os.environ.get("UBYHOST_STAGING_NO_LOGIN", "").strip().lower() in (
    "1", "true", "yes", "on",
)

TIMEZONE = "Europe/Prague"

# Host-admin software support (sidebar + Settings). Guest stay questions go to
# the host legal entity on the guest form, not this address.
OPERATOR_NAME = os.environ.get("UBYHOST_OPERATOR_NAME", "").strip()
OPERATOR_ICO = os.environ.get("UBYHOST_OPERATOR_ICO", "").strip()
OPERATOR_DIC = os.environ.get("UBYHOST_OPERATOR_DIC", "").strip()
OPERATOR_ADDRESS = os.environ.get("UBYHOST_OPERATOR_ADDRESS", "").strip()
OPERATOR_EMAIL = os.environ.get("UBYHOST_OPERATOR_EMAIL", "").strip() or "support@ubyhost.com"
# Gets a copy of every "door code not created" notice, so the problem is on record.
SUPPORT_EMAIL = "support@ubyhost.com"
OPERATOR_REGISTRY_URL = os.environ.get("UBYHOST_OPERATOR_REGISTRY_URL", "").strip()

# Cloudflare Turnstile. The site key is public; keep TURNSTILE_SECRET only in
# the production environment. Verification is enabled only when both are set.
TURNSTILE_SITE_KEY = os.environ.get(
    "TURNSTILE_SITE_KEY", "0x4AAAAAAE0LDM2eoIjssN00"
).strip()
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "").strip()
TURNSTILE_HOSTNAMES = {
    value.strip().lower()
    for value in os.environ.get("TURNSTILE_HOSTNAMES", "").split(",")
    if value.strip()
}
TURNSTILE_ENABLED = bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET and TURNSTILE_HOSTNAMES)

# Umami Cloud page analytics, public marketing and legal pages only (WP09).
# Both values empty by default; set them only in the production .env, copied
# from the tracking-code snippet in the Umami website settings. The tag and the
# CSP allowance appear only when both are set (see analytics.py).
UMAMI_WEBSITE_ID = os.environ.get("UMAMI_WEBSITE_ID", "").strip()
UMAMI_SCRIPT_URL = os.environ.get("UMAMI_SCRIPT_URL", "").strip()
# Optional: Umami's data-host-url, where the tracker sends its events. Empty
# means "the tracker's own default"; see analytics.py for what that is.
UMAMI_HOST_URL = os.environ.get("UMAMI_HOST_URL", "").strip().rstrip("/")
# data-domains: the hostnames the tracker may run on. Defaults to the host of
# UBYHOST_PUBLIC_BASE_URL, so a staging copy never reports into production.
UMAMI_DOMAINS = os.environ.get("UMAMI_DOMAINS", "").strip()

# Bumped when Terms of Service change materially (logged on host login).
# 1.6 (WP24): stay fee duty, filing on the host's instruction, filing by hand,
# UbyPort credentials (§ 10a), best-effort availability, liability (§ 17).
# 1.7 (Task 0005): e-mail link login replaces passwords; passkeys; mailbox duty.
TERMS_VERSION = os.environ.get("UBYHOST_TERMS_VERSION", "1.7")

# Transactional mail. Staging uses console (links appear in Settings).
# SES is refused unless deployment is production and credentials are complete.
MAIL_BACKEND = os.environ.get("UBYHOST_MAIL_BACKEND", "disabled").strip().lower()
MAIL_FROM = os.environ.get("UBYHOST_MAIL_FROM", "").strip()
SES_REGION = os.environ.get("UBYHOST_SES_REGION", "eu-central-1").strip()
AWS_ACCESS_KEY_ID = os.environ.get("UBYHOST_AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.environ.get("UBYHOST_AWS_SECRET_ACCESS_KEY", "").strip()

# WP20: self sign-up at /signup. Off by default; while off the page and its
# verification route answer 404 and the public pages link to /login as before.
# Counsel has to confirm the privacy-notice wording and the legal basis for
# keeping the Google Ads click ID before this is switched on in production.
SIGNUP_ENABLED = os.environ.get("UBYHOST_SIGNUP_ENABLED", "0").lower() in ("1", "true", "yes")
# Where the "new verified sign-up" notice goes. Defaults to the support address.
SIGNUP_NOTIFY_EMAIL = os.environ.get("UBYHOST_SIGNUP_NOTIFY_EMAIL", "").strip() or OPERATOR_EMAIL
# The conversion action name exactly as created in Google Ads (case-sensitive).
ADS_CONVERSION_NAME = os.environ.get("UBYHOST_ADS_CONVERSION_NAME", "UbyHost sign-up").strip()
# The click ID windows (export within 85 days of the click, delete 90 days
# after it or 30 days after upload) are fixed in signup.py: they come from the
# legal position, not from deployment preference.

# WP21: Meta (Facebook/Instagram) Conversions API, server-side only: no Meta
# Pixel and no cookie. Off unless both the dataset (pixel) ID and the access
# token are set; while off, the Meta consent box is not shown either.
META_DATASET_ID = os.environ.get("UBYHOST_META_DATASET_ID", "").strip()
META_ACCESS_TOKEN = os.environ.get("UBYHOST_META_ACCESS_TOKEN", "").strip()
# Events Manager > Test events. Only for trying the integration on staging;
# Meta says to remove it for production traffic.
META_TEST_EVENT_CODE = os.environ.get("UBYHOST_META_TEST_EVENT_CODE", "").strip()
# Graph API version for graph.facebook.com/<version>/<dataset>/events.
# v26.0 was the latest on 4 Oct 2026 (Graph API changelog).
META_GRAPH_VERSION = os.environ.get("UBYHOST_META_GRAPH_VERSION", "v26.0").strip()


def meta_capi_enabled() -> bool:
    return bool(META_DATASET_ID and META_ACCESS_TOKEN)


# Bumped when the public Privacy Policy changes materially. 1.6 (WP09): website
# analytics with opt-out, own retention periods and roles. A bump makes the
# policy pending again, so every host is sent to /account/accept once.
# 1.7 (Task 0005): auth data updated for e-mail link login and passkeys.
PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.7")

# Bumped when the Data Processing Agreement changes materially. 1.6 (WP24):
# § 11 names Render and Google Drive only as "only if used" subprocessors.
# 1.7 (Task 0005): § 10 updated for e-mail link login; mailbox security duty.
DPA_VERSION = os.environ.get("UBYHOST_DPA_VERSION", "1.7")

# WP24: the one effective date shown on /terms, /privacy and /dpa. Terms 1.6,
# Privacy 1.6 and DPA 1.6 take effect together, so every host accepts all
# three on one /account/accept page. Set via UBYHOST_LEGAL_EFFECTIVE_DATE in
# production .env at release (Terms § 22 allows 30 days' host notice; owner
# decides). ISO date, YYYY-MM-DD; a malformed value stops start-up rather than
# printing a wrong date on a contract.
# 1.7 effective date: set UBYHOST_LEGAL_EFFECTIVE_DATE in .env before deploy.
LEGAL_EFFECTIVE_DATE = date.fromisoformat(
    os.environ.get("UBYHOST_LEGAL_EFFECTIVE_DATE", "").strip() or "2026-10-05"
)

# BE-5: bumped whenever a legal_notice_* / privacy_* string in i18n.py changes
# materially, so a guest's acknowledgement records which notice they saw.
GUEST_NOTICE_VERSION = os.environ.get("UBYHOST_GUEST_NOTICE_VERSION", "1.0")

# Never enable in production — allows iCal fetch to private/loopback hosts (tests only).
ICAL_ALLOW_PRIVATE = os.environ.get("UBYHOST_ICAL_ALLOW_PRIVATE", "0").lower() in (
    "1",
    "true",
    "yes",
)

# Set in deploy/lightsail .env (CLOUDFLARE_PROXY=1) when Cloudflare fronts the origin.
# It no longer implies which peers are the proxy: the app cannot tell a real Caddy
# container from any other private address, so UBYHOST_TRUSTED_PROXY_CIDRS must name
# the proxy network for CF-Connecting-IP to be honoured. See docs/CLOUDFLARE.md.
CLOUDFLARE_PROXY = os.environ.get("CLOUDFLARE_PROXY", "0").lower() in ("1", "true", "yes")

# Comma-separated CIDRs for reverse proxies that may set CF-Connecting-IP.
TRUSTED_PROXY_CIDRS = os.environ.get("UBYHOST_TRUSTED_PROXY_CIDRS", "").strip()


def endpoint_for(env: str = None) -> str:
    name = (env or UBYPORT_ENV)
    if name not in UBYPORT_ENDPOINTS:
        raise ValueError(f"Unknown UbyPort environment {name!r} (use mock, test or prod).")
    return UBYPORT_ENDPOINTS[name]
