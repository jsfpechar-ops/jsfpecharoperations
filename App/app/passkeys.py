"""Passkeys (WebAuthn): an optional, faster way to log in (task 0004).

A passkey never replaces the e-mail link. The link always works, so a host who
loses every device still gets in; a passkey only saves the trip to the inbox.

How the pieces fit:

* The relying party is the host name of ``UBYHOST_PUBLIC_BASE_URL``
  (``ubyhost.com`` in production). WebAuthn refuses IP addresses, so on a
  plain ``http://127.0.0.1`` run passkeys are simply not offered; use
  ``http://localhost:8080`` to try them locally.
* Every ceremony starts on the server: it mints a random challenge, stores
  only its SHA-256 for five minutes, and hands the options to the browser. The
  browser's answer carries the challenge back inside ``clientDataJSON``, so no
  cookie or extra field is needed to find the row again. A challenge is spent
  once, which is what stops a replayed answer.
* Passkeys are discoverable ("resident") and need user verification (Face ID,
  fingerprint, device PIN). That makes one a second factor on its own, so a
  passkey login skips the authenticator-app code.
* Phishing: the browser binds every answer to the origin it ran on, and the
  server checks that origin and the relying-party hash. A look-alike site gets
  an answer the server rejects.
* Clones: an authenticator that counts its signatures and then reports a lower
  number than last time was probably copied. The login is refused and audited.
  Synced passkeys (iCloud Keychain, Google Password Manager, 1Password) always
  report 0, which is fine.

Only the public key, the credential id, the counter, a name the host can edit
and two timestamps are stored. Removing a passkey deletes its row.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, generate_user_handle
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidCBORData,
    InvalidJSONStructure,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from . import config, db, rate_limit

REGISTER = "register"
LOGIN = "login"

RP_NAME = "UbyHost"
CHALLENGE_TTL = timedelta(minutes=5)
# The browser gives up after this long; a little shorter than the row lives.
TIMEOUT_MS = 4 * 60 * 1000
# Rows are deleted this long after they expire (retention.py).
PURGE_AFTER = timedelta(days=1)
# A host has a phone, a laptop and a spare key; ten is plenty.
MAX_PER_ACCOUNT = 10
NAME_MAX = 60

# Budgets per connection, in the same table as the other login limits.
_WINDOW = 15 * 60
OPTIONS_MAX_WINDOW = 30
FAIL_MAX_WINDOW = 20

_VERIFY_ERRORS = (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
    InvalidJSONStructure,
    InvalidCBORData,
    KeyError,
    TypeError,
    ValueError,
)


class PasskeyError(Exception):
    """The browser's answer did not prove anything. ``reason`` is for the audit."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --- relying party ---------------------------------------------------------


def _base() -> tuple:
    parts = urlsplit(config.PUBLIC_BASE_URL)
    return (parts.scheme or "").lower(), (parts.hostname or "").lower(), parts.port


def rp_id() -> str:
    return _base()[1]


def expected_origin() -> str:
    scheme, host, port = _base()
    default = {"https": 443, "http": 80}.get(scheme)
    return f"{scheme}://{host}" + (f":{port}" if port and port != default else "")


def available() -> bool:
    """Whether this deployment can offer passkeys at all.

    WebAuthn needs a host name (never an IP address) and HTTPS, except on
    ``localhost``, which browsers treat as secure for development.
    """
    scheme, host, _port = _base()
    if not host or host.replace(".", "").isdigit() or ":" in host:
        return False
    return scheme == "https" or host == "localhost"


# --- challenges --------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _hash(challenge: bytes) -> str:
    return hashlib.sha256(challenge).hexdigest()


def _store_challenge(challenge: bytes, purpose: str, user_id: Optional[int]) -> None:
    now = _now()
    db.insert(
        "webauthn_challenge",
        {
            "challenge_hash": _hash(challenge),
            "purpose": purpose,
            "user_account_id": user_id,
            "created_at": _iso(now),
            "expires_at": _iso(now + CHALLENGE_TTL),
        },
    )


def _spend_challenge(credential: Dict[str, Any], purpose: str, user_id: Optional[int]) -> bytes:
    """Find and spend the challenge the browser signed. Raises if none is live."""
    try:
        client_data = json.loads(
            base64url_to_bytes(credential["response"]["clientDataJSON"]).decode("utf-8")
        )
        challenge = base64url_to_bytes(client_data["challenge"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise PasskeyError("malformed") from exc
    now = _iso(_now())
    row = db.query_one(
        "SELECT * FROM webauthn_challenge WHERE challenge_hash = ? AND used_at IS NULL "
        "AND expires_at > ?",
        (_hash(challenge), now),
    )
    if not row or row["purpose"] != purpose:
        raise PasskeyError("challenge")
    if purpose == REGISTER and row["user_account_id"] != user_id:
        raise PasskeyError("challenge")
    if not db.update_if(
        "webauthn_challenge", row["id"], {"used_at": now}, {"used_at": None},
        extra_where="expires_at > ?", extra_params=(now,),
    ):
        raise PasskeyError("challenge")
    return challenge


def options_blocked(ip_key: str) -> bool:
    return rate_limit.blocked("passkey_options", ip_key, OPTIONS_MAX_WINDOW, _WINDOW)


def record_options(ip_key: str) -> None:
    rate_limit.record("passkey_options", ip_key)


def failures_blocked(ip_key: str) -> bool:
    return rate_limit.blocked("passkey_fail", ip_key, FAIL_MAX_WINDOW, _WINDOW)


def record_failure(ip_key: str) -> None:
    rate_limit.record("passkey_fail", ip_key)


# --- reading -----------------------------------------------------------------


def for_account(user_id: int) -> List[Any]:
    return db.query(
        "SELECT id, name, created_at, last_used_at, backed_up FROM passkey "
        "WHERE user_account_id = ? ORDER BY id",
        (int(user_id),),
    )


def count_for(user_id: int) -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM passkey WHERE user_account_id = ?", (int(user_id),)
    )
    return int(row["n"]) if row else 0


def _user_handle(account: Any) -> bytes:
    """The account's opaque WebAuthn handle, made on first use."""
    current = account["webauthn_user_handle"]
    if current:
        return base64url_to_bytes(current)
    handle = generate_user_handle()
    encoded = bytes_to_base64url(handle)
    if not db.update_if(
        "user_account", int(account["id"]), {"webauthn_user_handle": encoded},
        {"webauthn_user_handle": None},
    ):
        # Another tab won the race; use what it stored.
        row = db.query_one(
            "SELECT webauthn_user_handle FROM user_account WHERE id = ?", (int(account["id"]),)
        )
        return base64url_to_bytes(row["webauthn_user_handle"])
    return handle


# --- registration ------------------------------------------------------------


def registration_options(account: Any) -> str:
    """Options JSON for adding a passkey to ``account``."""
    existing = db.query(
        "SELECT credential_id, transports FROM passkey WHERE user_account_id = ?",
        (int(account["id"]),),
    )
    options = generate_registration_options(
        rp_id=rp_id(),
        rp_name=RP_NAME,
        user_id=_user_handle(account),
        user_name=account["email"] or account["username"],
        user_display_name=account["display_name"] or account["email"] or account["username"],
        timeout=TIMEOUT_MS,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(row["credential_id"]),
                transports=_transports(row["transports"]),
            )
            for row in existing
        ],
    )
    _store_challenge(options.challenge, REGISTER, int(account["id"]))
    return options_to_json(options)


def _transports(raw: Optional[str]) -> Optional[List[AuthenticatorTransport]]:
    values = []
    for item in (raw or "").split(","):
        try:
            values.append(AuthenticatorTransport(item))
        except ValueError:
            continue
    return values or None


def clean_name(name: str, fallback: str) -> str:
    text = " ".join(str(name or "").split())[:NAME_MAX]
    return text or fallback


def register(account: Any, credential: Dict[str, Any], name: str) -> int:
    """Verify the browser's answer and store the new passkey. Returns its id."""
    if count_for(int(account["id"])) >= MAX_PER_ACCOUNT:
        raise PasskeyError("too_many")
    challenge = _spend_challenge(credential, REGISTER, int(account["id"]))
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
            require_user_verification=True,
        )
    except _VERIFY_ERRORS as exc:
        raise PasskeyError("invalid") from exc
    credential_id = bytes_to_base64url(verified.credential_id)
    if db.query_one("SELECT id FROM passkey WHERE credential_id = ?", (credential_id,)):
        raise PasskeyError("duplicate")
    transports = (credential.get("response") or {}).get("transports") or []
    return db.insert(
        "passkey",
        {
            "user_account_id": int(account["id"]),
            "credential_id": credential_id,
            "public_key": bytes_to_base64url(verified.credential_public_key),
            "sign_count": int(verified.sign_count or 0),
            "transports": ",".join(t for t in transports if isinstance(t, str))[:200],
            "name": name,
            "backed_up": 1 if verified.credential_backed_up else 0,
            "created_at": db.utcnow(),
        },
    )


def rename(user_id: int, passkey_id: int, name: str) -> bool:
    return db.execute_rowcount(
        "UPDATE passkey SET name = ? WHERE id = ? AND user_account_id = ?",
        (name, int(passkey_id), int(user_id)),
    ) == 1


def remove(user_id: int, passkey_id: int) -> Optional[str]:
    """Delete one of the account's passkeys. Returns its name, or None."""
    row = db.query_one(
        "SELECT name FROM passkey WHERE id = ? AND user_account_id = ?",
        (int(passkey_id), int(user_id)),
    )
    if not row:
        return None
    db.execute(
        "DELETE FROM passkey WHERE id = ? AND user_account_id = ?",
        (int(passkey_id), int(user_id)),
    )
    return row["name"]


# --- login -------------------------------------------------------------------


def authentication_options() -> str:
    """Options JSON for logging in with any passkey this site knows."""
    options = generate_authentication_options(
        rp_id=rp_id(),
        timeout=TIMEOUT_MS,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _store_challenge(options.challenge, LOGIN, None)
    return options_to_json(options)


def normalise_credential_id(raw_id: Any) -> str:
    """The stored form of a credential id, or "" when it is not valid base64url."""
    if not isinstance(raw_id, str):
        return ""
    try:
        return bytes_to_base64url(base64url_to_bytes(raw_id))
    except (TypeError, ValueError):
        return ""


def authenticate(credential: Dict[str, Any]):
    """Verify a login answer. Returns ``(account, passkey_row)`` or raises.

    The account must be active and the passkey's user handle must match it.
    """
    try:
        credential_id = bytes_to_base64url(base64url_to_bytes(credential["rawId"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise PasskeyError("malformed") from exc
    challenge = _spend_challenge(credential, LOGIN, None)
    row = db.query_one("SELECT * FROM passkey WHERE credential_id = ?", (credential_id,))
    if not row:
        raise PasskeyError("unknown")
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (row["user_account_id"],)
    )
    if not account:
        raise PasskeyError("inactive")
    handle = (credential.get("response") or {}).get("userHandle")
    if handle and account["webauthn_user_handle"]:
        try:
            same = base64url_to_bytes(handle) == base64url_to_bytes(account["webauthn_user_handle"])
        except (TypeError, ValueError) as exc:
            raise PasskeyError("handle") from exc
        if not same:
            raise PasskeyError("handle")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id(),
            expected_origin=expected_origin(),
            credential_public_key=base64url_to_bytes(row["public_key"]),
            credential_current_sign_count=int(row["sign_count"] or 0),
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        if "sign count" in str(exc).lower():
            raise PasskeyError("sign_count") from exc
        raise PasskeyError("invalid") from exc
    except _VERIFY_ERRORS as exc:
        raise PasskeyError("invalid") from exc
    db.execute(
        "UPDATE passkey SET sign_count = ?, last_used_at = ?, backed_up = ? WHERE id = ?",
        (
            int(verified.new_sign_count or 0),
            db.utcnow(),
            1 if verified.credential_backed_up else 0,
            row["id"],
        ),
    )
    return account, row


# --- retention -----------------------------------------------------------------


def purge(now: Optional[datetime] = None, dry_run: bool = False) -> int:
    """Delete ceremonies that expired more than a day ago."""
    cutoff = _iso((now or _now()) - PURGE_AFTER)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM webauthn_challenge WHERE expires_at < ?", (cutoff,)
    )
    count = int(row["n"]) if row else 0
    if count and not dry_run:
        db.execute("DELETE FROM webauthn_challenge WHERE expires_at < ?", (cutoff,))
    return count
