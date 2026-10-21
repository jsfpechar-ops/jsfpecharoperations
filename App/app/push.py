"""Urgent alerts on the host's phone (Web Push, briefs 0225-0227).

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
import secrets
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


def refresh(account_id: int, endpoint: str, *, lang: str) -> bool:
    """A visit from a device that has alerts on: keep its language and last visit.

    Never creates a row: a device removed in Settings stays removed until its
    owner turns alerts on again on it. False when this account has no such device.
    """
    row = db.query_one(
        "SELECT id FROM push_subscription WHERE endpoint_hash = ? AND user_account_id = ?",
        (_hash(str(endpoint or "")), account_id),
    )
    if not row:
        return False
    db.execute(
        "UPDATE push_subscription SET lang = ?, last_seen_at = ? WHERE id = ?",
        (host_i18n.normalise_language(lang), db.utcnow(), row["id"]),
    )
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
        "idempotency_key": f"{TEST_KIND}:{secrets.token_hex(8)}:{row['id']}",
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


# --- the four urgent events (brief 0228) ----------------------------------------
# Each runs next to the e-mail for the same event and never raises: an alert
# that cannot be queued must never be the reason a filing, a calendar sync or a
# door-code run fails.


def _day(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except ValueError:
        return str(value or "")


def filing_problem(apartment: Any, submission_id: Optional[int]) -> int:
    """UbyPort did not accept a report. One push per property and local day."""
    try:
        from . import deadlines, mail_notify

        stays = mail_notify.stays_for_submission(submission_id)
        return notify(
            apartment["owner_user_id"],
            "filing_problem",
            key=f"{apartment['id']}:{deadlines.local_now().date().isoformat()}",
            url=f"/reservations/{stays[0]['id']}" if len(stays) == 1 else "/reservations",
            params={"property": apartment["internal_name"] or ""},
        )
    except Exception:
        log.exception("push_filing_problem_failed submission_id=%s", submission_id)
        return 0


def deadline_at_risk(stay: Dict[str, Any]) -> int:
    """A stay is about to miss the police deadline (filing_watchdog). Once per stay."""
    try:
        deadline = stay["deadline"]
        return notify(
            stay["owner_user_id"],
            "deadline_at_risk",
            key=str(stay["reservation_id"]),
            url=f"/reservations/{stay['reservation_id']}",
            params={
                "property": stay["property"],
                "date": stay["arrival"].strftime("%d.%m.%Y"),
                "deadline": f"{deadline.strftime('%d.%m.%Y')} {deadline.strftime('%H:%M')}",
            },
        )
    except Exception:
        log.exception("push_deadline_failed reservation_id=%s", stay.get("reservation_id"))
        return 0


def door_code_missing(reservation_id: int) -> int:
    """Registered guests still have no door code. Once per stay."""
    try:
        row = db.query_one(
            "SELECT r.id, r.date_from, a.owner_user_id, a.internal_name "
            "FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
            (reservation_id,),
        )
        if not row:
            return 0
        return notify(
            row["owner_user_id"],
            "door_code",
            key=str(row["id"]),
            url=f"/reservations/{row['id']}",
            params={"property": row["internal_name"] or "", "date": _day(row["date_from"])},
        )
    except Exception:
        log.exception("push_door_code_failed reservation_id=%s", reservation_id)
        return 0


def cancelled_with_guests(apartment_id: int, reservation_id: int) -> int:
    """The calendar cancelled a stay whose guests had registered. Once per stay."""
    try:
        row = db.query_one(
            "SELECT r.id, r.date_from, a.owner_user_id, a.internal_name "
            "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
            "WHERE r.id = ? AND a.id = ?",
            (reservation_id, apartment_id),
        )
        if not row:
            return 0
        return notify(
            row["owner_user_id"],
            "cancelled_with_guests",
            key=str(row["id"]),
            url=f"/reservations/{row['id']}",
            params={"property": row["internal_name"] or "", "date": _day(row["date_from"])},
        )
    except Exception:
        log.exception("push_cancelled_failed reservation_id=%s", reservation_id)
        return 0


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
