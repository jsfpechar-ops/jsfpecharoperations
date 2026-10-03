"""Self sign-up and its Google Ads click attribution (WP20).

Off unless ``UBYHOST_SIGNUP_ENABLED`` is set. The flow:

1. ``/signup`` creates an *inactive* account with the e-mail, the password hash
   and the workspace name, records the Terms/DPA acceptance, and queues a
   verification link. The page answers the same whether or not the address is
   already taken, so it cannot be used to find out who has an account.
2. The link opens ``/signup/verify``, which asks for the sign-up password once
   more. That stops a mail scanner that pre-fetches links from activating the
   account, and it stops anyone who signed up with somebody else's address
   from taking the account over when the owner clicks the link: only the
   person who knows the password can finish.
3. Activation logs the host in. ``auth.require_login`` then sends them through
   the existing mandatory 2FA setup and onboarding.

Ad click identifiers (legal position 3), without a cookie or an ad script:

- A ``gclid``/``gbraid``/``wbraid`` arriving on the landing, pricing or sign-up
  page is read on the server, validated, and packed with the time it was first
  seen into one signed value (``click``). That value travels only in the
  ``/signup`` link and a hidden form field, never in a cookie, the database or
  analytics, until the visitor submits the form.
- The optional consent box is shown only when such an identifier is present.
  Only when it is ticked is the identifier stored, in ``ad_click``, together
  with the time of the click, the time of consent, and a pointer to the exact
  wording shown (``consent_texts``).
- The operator exports consented, verified rows within 85 days of the click
  and uploads them to Google Ads by hand; the export records ``uploaded_at``.
- The identifier is blanked 90 days after the click or 30 days after upload,
  whichever comes first, or at once when consent is withdrawn (Settings >
  Privacy, or an admin on request). The consent record itself stays.
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer

from . import acceptance, auth, config, db, mail_notify, rate_limit

log = logging.getLogger("ubyhost.signup")

VERIFY_MAX_AGE = 24 * 60 * 60
UNVERIFIED_TTL_DAYS = 7
WORKSPACE_MAX = 120

# Budgets per hour. The IP budget allows a shared office connection a few
# honest attempts; the e-mail budget caps how many messages one address can be
# sent through this form, whoever is typing it in.
_HOUR = 60 * 60
SIGNUP_IP_MAX = 10
SIGNUP_EMAIL_MAX = 3

_UTM_RE = re.compile(r"^[A-Za-z0-9._+ -]{1,100}$")
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign")

# --- ad platforms -------------------------------------------------------------
#
# Each URL parameter belongs to one ad platform, and each platform has its own
# optional consent box, its own consent wording and its own retention rule.

GOOGLE = "google"
PLATFORMS = (GOOGLE,)

# URL parameter -> (platform, validation pattern).
CLICK_PARAMS: Dict[str, tuple] = {
    "gclid": (GOOGLE, re.compile(r"^[A-Za-z0-9_-]{1,200}$")),
    "gbraid": (GOOGLE, re.compile(r"^[A-Za-z0-9_-]{1,200}$")),
    "wbraid": (GOOGLE, re.compile(r"^[A-Za-z0-9_-]{1,200}$")),
}
# The ad_click columns that hold a platform's identifiers. Blanked on schedule.
ID_COLUMNS: Dict[str, tuple] = {GOOGLE: ("gclid", "gbraid", "wbraid")}
# Name of the platform's checkbox on the sign-up form.
CONSENT_FIELDS: Dict[str, str] = {GOOGLE: "ads_consent"}
# Bump when the wording of the box changes; the language is appended.
CONSENT_VERSIONS: Dict[str, str] = {GOOGLE: "ads-google-v1"}
# (days after the click, days after a successful upload) before the
# identifiers are blanked, whichever comes first (legal position 3).
ID_RETENTION_DAYS: Dict[str, tuple] = {GOOGLE: (90, 30)}

GOOGLE_PRIVACY_URL = "https://business.safety.google/privacy/"
# Rows older than this are not exported: a safety margin inside Google's
# 90-day import window.
GOOGLE_EXPORT_DAYS = 85

# A signed click value older than the longest retention is refused outright.
CLICK_MAX_AGE_DAYS = 90
_CLICK_FUTURE_SLACK_MS = 5 * 60 * 1000

# Google Ads offline click-conversion file (Google Ads Help 7014069). The two
# consent columns are the EU user consent fields; personalisation is never
# asked for, so it is always Denied. gbraid/wbraid are stored with consent but
# not exported: the legacy file's column names for them are unverified.
CSV_HEADER = (
    "Google Click ID",
    "Conversion Name",
    "Conversion Time",
    "Ad User Data",
    "Ad Personalization",
)
CONSENT_GRANTED = "Granted"
CONSENT_DENIED = "Denied"


def enabled() -> bool:
    return bool(config.SIGNUP_ENABLED)


# --- attribution ------------------------------------------------------------


def clean_click_id(param: str, value: Any) -> str:
    spec = CLICK_PARAMS.get(param)
    text = str(value or "").strip()
    return text if spec and spec[1].fullmatch(text) else ""


def clean_gclid(value: Any) -> str:
    return clean_click_id("gclid", value)


def clean_utm(value: Any) -> str:
    text = str(value or "").strip()
    return text if _UTM_RE.fullmatch(text) else ""


def click_ids(params: Any) -> Dict[str, str]:
    """The valid ad click identifiers in a query string. Invalid ones are dropped."""
    found = {param: clean_click_id(param, params.get(param)) for param in CLICK_PARAMS}
    return {param: value for param, value in found.items() if value}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _click_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.secret_key(), salt="ubyhost-signup-click")


def issue_click(ids: Dict[str, str], seen_ms: Optional[int] = None) -> str:
    """Sign the identifiers together with the moment they were first seen."""
    return _click_serializer().dumps({"i": ids, "t": int(seen_ms or _now_ms())})


def read_click(token: Any, now_ms: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """``{"ids": {...}, "seen_ms": int}`` from a signed click value, or None.

    The signature stops a visitor from backdating or forward-dating the click
    time, which decides when the identifier has to be deleted.
    """
    if not token:
        return None
    try:
        payload = _click_serializer().loads(str(token))
    except BadSignature:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("i"), dict):
        return None
    try:
        seen_ms = int(payload.get("t"))
    except (TypeError, ValueError):
        return None
    now_ms = now_ms or _now_ms()
    if seen_ms > now_ms + _CLICK_FUTURE_SLACK_MS:
        return None
    if seen_ms < now_ms - CLICK_MAX_AGE_DAYS * 86400 * 1000:
        return None
    ids = click_ids(payload["i"])
    if not ids or len(ids) != len(payload["i"]):
        return None
    return {"ids": ids, "seen_ms": seen_ms}


def click_platforms(click: Optional[Dict[str, Any]]) -> List[str]:
    """The platforms a click value has identifiers for, in display order."""
    if not click:
        return []
    present = {CLICK_PARAMS[param][0] for param in click["ids"]}
    return [platform for platform in PLATFORMS if platform in present]


def attribution(params: Any, *, mint: bool = False) -> Dict[str, str]:
    """The campaign labels and the signed click value for a page or a form.

    ``mint`` is for pages a visitor lands on (GET): raw identifiers in the
    query string are signed with the current time. A form post (``mint`` off)
    only accepts the signed value, so the click time cannot be chosen by the
    client. Anything that fails validation is dropped, not repaired.
    """
    found = {key: clean_utm(params.get(key)) for key in UTM_KEYS}
    token = str(params.get("click") or "")
    click = read_click(token)
    if not click:
        token = ""
    if mint:
        raw = click_ids(params)
        if raw and (not click or click["ids"] != raw):
            token = issue_click(raw)
    found["click"] = token
    return {key: value for key, value in found.items() if value}


def signup_href(lang: str, params: Any) -> str:
    """The ``/signup`` link with the visitor's attribution carried along."""
    query = {"lang": lang, **attribution(params, mint=True)}
    return "/signup?" + urlencode(query)


def public_context(request: Any, lang: Optional[str] = None) -> Dict[str, str]:
    """Template context for the landing and pricing pages.

    Empty while sign-up is off, so the pages keep linking to /login.
    """
    if not enabled():
        return {}
    from . import host_i18n

    lang = lang or host_i18n.resolve_language(
        request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE
    )
    return {"signup_href": signup_href(lang, request.query_params)}


# --- tokens -----------------------------------------------------------------


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="ubyhost-signup-verify")


def issue_token(user_id: int, nonce: str) -> str:
    return _serializer().dumps({"uid": int(user_id), "n": nonce})


def pending_account(token: str):
    """The unverified account a link points at, or None.

    Only the newest link works: every sign-up for the address mints a new
    nonce, so an older mail stops working once a newer one is sent.
    """
    try:
        payload = _serializer().loads(token or "", max_age=VERIFY_MAX_AGE)
    except BadSignature:
        return None
    if not isinstance(payload, dict) or not payload.get("uid") or not payload.get("n"):
        return None
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND email_verified_at IS NULL "
        "AND signup_at IS NOT NULL AND active = 0",
        (int(payload["uid"]),),
    )
    if not account or not account["signup_verify_nonce"]:
        return None
    if not secrets.compare_digest(str(account["signup_verify_nonce"]), str(payload["n"])):
        return None
    return account


# --- sign-up ----------------------------------------------------------------


def rate_limited(ip_key: str, email: str) -> bool:
    return rate_limit.blocked("signup_ip", ip_key, SIGNUP_IP_MAX, _HOUR) or (
        bool(email) and rate_limit.blocked("signup_email", email, SIGNUP_EMAIL_MAX, _HOUR)
    )


def record_attempt(ip_key: str, email: str) -> None:
    rate_limit.record("signup_ip", ip_key)
    if email:
        rate_limit.record("signup_email", email)


def _username_base(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    local = re.sub(r"[^a-z0-9._-]", "", local)
    local = re.sub(r"^[^a-z0-9]+", "", local)[:20]
    return local or "host"


def _new_username(email: str) -> str:
    base = _username_base(email)
    for _ in range(20):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if auth.username_is_valid(candidate) and not db.query_one(
            "SELECT id FROM user_account WHERE username = ?", (candidate,)
        ):
            return candidate
    return f"host-{secrets.token_hex(6)}"


# --- consent records ---------------------------------------------------------


def consent_label(platform: str, lang: str) -> Dict[str, str]:
    """The pieces of a platform's consent box as the form shows them."""
    from . import host_i18n

    if platform == GOOGLE:
        return {
            "text": host_i18n.translate(lang, "signup.ads_consent"),
            "link_label": host_i18n.translate(lang, "signup.ads_consent_link"),
            "link_url": GOOGLE_PRIVACY_URL,
        }
    raise ValueError(f"unknown ad platform {platform!r}")


def consent_text(platform: str, lang: str) -> str:
    """The exact wording of the box, written the way the legal text has it."""
    label = consent_label(platform, lang)
    return f"{label['text']} [{label['link_label']}]({label['link_url']})"


def consent_text_id(platform: str, lang: str) -> int:
    """The ``consent_texts`` row for the wording shown now, created on first use.

    The version is ``<CONSENT_VERSIONS[platform]>-<lang>``. If somebody edits
    the wording without bumping the version, the stored text no longer
    matches; the new wording is then filed under a version with its hash
    appended, so no consent ever points at text that was not shown.
    """
    text = consent_text(platform, lang)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    version = f"{CONSENT_VERSIONS[platform]}-{lang}"
    row = db.query_one(
        "SELECT id, text_sha256 FROM consent_texts WHERE version = ?", (version,)
    )
    if row and row["text_sha256"] == digest:
        return int(row["id"])
    if row:
        log.warning("consent wording for %s changed without a version bump", version)
        version = f"{version}-{digest[:8]}"
        row = db.query_one("SELECT id FROM consent_texts WHERE version = ?", (version,))
        if row:
            return int(row["id"])
    db.execute(
        "INSERT INTO consent_texts (version, purpose, lang, text, text_sha256, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (version) DO NOTHING",
        (version, f"ads_{platform}", lang, text, digest, db.utcnow()),
    )
    return int(db.query_one("SELECT id FROM consent_texts WHERE version = ?", (version,))["id"])


def _iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()


def _click_values(platform: str, click: Dict[str, Any]) -> Dict[str, Any]:
    """The ad_click columns for one platform's identifiers."""
    ids = {param: value for param, value in click["ids"].items()
           if CLICK_PARAMS[param][0] == platform}
    return {column: ids.get(column) for column in ID_COLUMNS[platform]}


def _store_clicks(
    user_id: int, click: Optional[Dict[str, Any]], consents: Dict[str, bool], lang: str
) -> List[str]:
    """Replace the account's click rows with the consented ones. Returns platforms stored.

    Without a ticked box nothing about the click is written, not even that
    there was one.
    """
    db.execute("DELETE FROM ad_click WHERE user_account_id = ?", (user_id,))
    stored = []
    now = db.utcnow()
    for platform in click_platforms(click):
        if not consents.get(platform):
            continue
        db.insert(
            "ad_click",
            {
                "user_account_id": user_id,
                "platform": platform,
                **_click_values(platform, click),
                "clicked_at": _iso_from_ms(click["seen_ms"]),
                "consent_text_id": consent_text_id(platform, lang),
                "consented_at": now,
                "created_at": now,
            },
        )
        stored.append(platform)
    return stored


def has_click(user_id: int, platform: str) -> bool:
    return bool(db.query_one(
        "SELECT id FROM ad_click WHERE user_account_id = ? AND platform = ? "
        "AND withdrawn_at IS NULL AND ids_deleted_at IS NULL",
        (user_id, platform),
    ))


def consents_for(user_id: int) -> List[Dict[str, Any]]:
    """The account's ad consents for Settings > Privacy, oldest platform first."""
    rows = {
        row["platform"]: dict(row)
        for row in db.query(
            "SELECT c.platform, c.consented_at, c.withdrawn_at, c.uploaded_at, "
            "c.ids_deleted_at, t.version FROM ad_click c "
            "JOIN consent_texts t ON t.id = c.consent_text_id WHERE c.user_account_id = ?",
            (user_id,),
        )
    }
    return [rows[platform] for platform in PLATFORMS if platform in rows]


# --- sign-up ------------------------------------------------------------------


def register(
    *,
    email: str,
    password: str,
    workspace: str,
    attr: Dict[str, str],
    consents: Optional[Dict[str, bool]] = None,
    onboarding_opt_out: bool = False,
    lang: str,
    request: Any = None,
) -> str:
    """Create or refresh a pending account and queue the right e-mail.

    Returns ``"created"``, ``"refreshed"`` or ``"exists"`` for the caller's
    audit and tests only. The page shown to the visitor must not depend on it.
    Inputs are already validated by the route.
    """
    now = db.utcnow()
    nonce = secrets.token_urlsafe(16)
    password_hash = auth.hash_password(password)
    existing = db.query_one("SELECT * FROM user_account WHERE email = ?", (email,))
    if existing and not (
        existing["email_verified_at"] is None
        and existing["signup_at"] is not None
        and not existing["active"]
    ):
        # One mail per account per hour at most, on top of the e-mail budget.
        # Nothing from this form is stored against the existing account.
        bucket = now[:13]
        mail_notify.signup_exists(
            user_id=existing["id"], to_email=email, lang=lang, bucket=bucket
        )
        db.audit("signup_repeated", actor="anonymous", owner_user_id=existing["id"])
        return "exists"
    values = {
        "display_name": workspace,
        "password_hash": password_hash,
        "signup_at": now,
        "signup_verify_nonce": nonce,
        "signup_utm_source": attr.get("utm_source"),
        "signup_utm_medium": attr.get("utm_medium"),
        "signup_utm_campaign": attr.get("utm_campaign"),
        # Legal position 2: the sign-up refusal of setup-tip e-mails.
        "onboarding_emails_opt_out": 1 if onboarding_opt_out else 0,
        "onboarding_emails_opt_out_at": now if onboarding_opt_out else None,
    }
    if existing:
        # Signing up again before confirming replaces the password and retires
        # the older link: whoever confirms has to know the newest password.
        db.update("user_account", existing["id"], values)
        user_id = int(existing["id"])
        username = existing["username"]
        outcome = "refreshed"
    else:
        username = _new_username(email)
        try:
            user_id = db.insert(
                "user_account",
                {
                    "username": username,
                    "email": email,
                    "role": "host",
                    "active": 0,
                    "must_change_password": 0,
                    "session_version": 1,
                    "created_at": now,
                    **values,
                },
            )
        except Exception as exc:
            if "UNIQUE constraint failed" not in str(exc):
                raise
            # A second submit raced this one for the same address.
            log.info("signup race on one address; treated as repeated")
            return "exists"
        outcome = "created"
    _store_clicks(user_id, read_click(attr.get("click")), consents or {}, lang)
    # The sign-up checkbox is a clickwrap; the table only knows that method.
    acceptance.record(user_id, ("terms", "dpa", "privacy"), "clickwrap", request)
    db.audit("signup_" + outcome, actor="anonymous", owner_user_id=user_id)
    mail_notify.signup_verify(
        user_id=user_id,
        to_email=email,
        lang=lang,
        workspace=workspace,
        username=username,
        token=issue_token(user_id, nonce),
        nonce=nonce,
    )
    return outcome


def activate(account) -> bool:
    """Mark the account verified and active. False if someone else won the race."""
    now = db.utcnow()
    done = db.update_if(
        "user_account",
        account["id"],
        {
            "active": 1,
            "email_verified_at": now,
            "signup_verify_nonce": None,
            "must_change_password": 0,
        },
        {"signup_verify_nonce": account["signup_verify_nonce"]},
        extra_where="email_verified_at IS NULL",
    )
    if not done:
        return False
    db.audit("signup_verified", actor=account["username"], owner_user_id=account["id"])
    mail_notify.signup_admin(
        user_id=account["id"],
        workspace=account["display_name"] or "",
        email=account["email"] or "",
        username=account["username"],
        campaign=" / ".join(
            value for value in (
                account["signup_utm_source"],
                account["signup_utm_medium"],
                account["signup_utm_campaign"],
            ) if value
        ),
        ads_click=has_click(int(account["id"]), GOOGLE),
    )
    return True


def withdraw_consent(user_id: int, platform: str, actor: str) -> bool:
    """Withdraw one platform's consent: blank the identifiers, keep the record.

    Legal position 3 requires deleting an identifier that was not uploaded
    yet. An uploaded one is deleted too: nothing here uses it afterwards. The
    row is excluded from every later export because ``withdrawn_at`` is set.
    Returns False when there was no active consent to withdraw.
    """
    row = db.query_one(
        "SELECT * FROM ad_click WHERE user_account_id = ? AND platform = ? "
        "AND withdrawn_at IS NULL",
        (user_id, platform),
    )
    if not row:
        return False
    now = db.utcnow()
    blank = {column: None for column in ID_COLUMNS[platform]}
    if not db.update_if(
        "ad_click",
        row["id"],
        {**blank, "withdrawn_at": now, "ids_deleted_at": row["ids_deleted_at"] or now},
        {"withdrawn_at": None},
    ):
        return False
    db.audit(
        "ads_consent_withdrawn",
        detail=f"{platform}; uploaded={'yes' if row['uploaded_at'] else 'no'}",
        actor=actor,
        owner_user_id=user_id,
    )
    return True


# --- housekeeping -------------------------------------------------------------


def _iso_days_ago(days: int, now: Optional[datetime] = None) -> str:
    moment = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    return moment.replace(microsecond=0).isoformat()


def purge(now: Optional[datetime] = None) -> Dict[str, int]:
    """Delete unconfirmed sign-ups and click identifiers past their time.

    Runs whether or not sign-up is switched on, so turning it off never leaves
    a stored click ID behind.
    """
    unverified_cutoff = _iso_days_ago(UNVERIFIED_TTL_DAYS, now)
    stale = [
        int(row["id"])
        for row in db.query(
            "SELECT id FROM user_account WHERE email_verified_at IS NULL "
            "AND signup_at IS NOT NULL AND active = 0 AND signup_at < ?",
            (unverified_cutoff,),
        )
    ]
    for user_id in stale:
        with db.immediate() as cur:
            cur.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
            cur.execute("DELETE FROM ad_click WHERE user_account_id = ?", (user_id,))
            cur.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
            cur.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
            cur.execute(
                "DELETE FROM user_account WHERE id = ? AND email_verified_at IS NULL "
                "AND active = 0",
                (user_id,),
            )
    cleared = 0
    stamp = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    for platform in PLATFORMS:
        after_click, after_upload = ID_RETENTION_DAYS[platform]
        blank = ", ".join(f"{column} = NULL" for column in ID_COLUMNS[platform])
        with db.immediate() as cur:
            cur.execute(
                f"UPDATE ad_click SET {blank}, ids_deleted_at = ? "
                "WHERE platform = ? AND ids_deleted_at IS NULL AND ("
                "clicked_at < ? OR uploaded_at < ? OR withdrawn_at IS NOT NULL)",
                (
                    stamp,
                    platform,
                    _iso_days_ago(after_click, now),
                    _iso_days_ago(after_upload, now),
                ),
            )
            cleared += max(cur.rowcount, 0)
    return {"unverified_deleted": len(stale), "click_ids_cleared": cleared}


# --- Google Ads export --------------------------------------------------------


def conversion_time(stored: str) -> str:
    """A stored UTC timestamp as Prague time with its offset.

    ``yyyy-MM-dd HH:mm:ss+z`` is one of the formats Google Ads lists; the
    explicit offset keeps the daylight-saving switch unambiguous.
    """
    parsed = datetime.fromisoformat(stored)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S%z")


def export_rows(now: Optional[datetime] = None, *, again: bool = False) -> List[Dict[str, Any]]:
    """Consented, verified, not withdrawn Google clicks from the last 85 days.

    By default only rows not exported before. ``again`` re-includes rows that
    were already exported, for a file that has to be uploaded once more.
    """
    window_cutoff = _iso_days_ago(GOOGLE_EXPORT_DAYS, now)
    sql = (
        "SELECT c.id, c.gclid, u.email_verified_at FROM ad_click c "
        "JOIN user_account u ON u.id = c.user_account_id "
        "WHERE c.platform = ? AND c.gclid IS NOT NULL AND c.withdrawn_at IS NULL "
        "AND c.ids_deleted_at IS NULL AND u.email_verified_at IS NOT NULL "
        "AND c.clicked_at >= ?"
    )
    if not again:
        sql += " AND c.uploaded_at IS NULL"
    sql += " ORDER BY u.email_verified_at, c.id"
    return [
        dict(row)
        for row in db.query(sql, (GOOGLE, window_cutoff))
        if clean_gclid(row["gclid"])
    ]


def conversions_csv(rows: List[Dict[str, Any]]) -> str:
    out = io.StringIO()
    out.write(f"Parameters:TimeZone={config.TIMEZONE}\r\n")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow(
            (
                row["gclid"],
                config.ADS_CONVERSION_NAME,
                conversion_time(row["email_verified_at"]),
                CONSENT_GRANTED,
                CONSENT_DENIED,
            )
        )
    return out.getvalue()


def export_conversions(now: Optional[datetime] = None, *, again: bool = False) -> tuple:
    """The CSV body and its row count; marks new rows ``uploaded_at``.

    ``uploaded_at`` means "handed to the operator for upload": the file goes
    to Google by hand, so this is the last moment the app can know about.
    """
    rows = export_rows(now, again=again)
    body = conversions_csv(rows)
    if rows and not again:
        stamp = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
        marks = ", ".join("?" for _ in rows)
        db.execute(
            f"UPDATE ad_click SET uploaded_at = ? WHERE uploaded_at IS NULL AND id IN ({marks})",
            [stamp] + [row["id"] for row in rows],
        )
    return body, len(rows)
