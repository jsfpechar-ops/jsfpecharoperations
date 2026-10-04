"""Meta Conversions API: the sign-up event, sent from the server (WP21).

No Meta Pixel and no cookie. A visitor who arrived with ``fbclid`` and ticked
the optional Meta box at sign-up has an ``ad_click`` row with ``fbc`` (see
``signup``). Once the e-mail address is confirmed, ``enqueue`` marks that row
``pending``; ``send_pending`` (scheduler job ``meta_capi``) posts one
``CompleteRegistration`` event per row to
``graph.facebook.com/<version>/<dataset>/events``, outbox style:

- the row is claimed with a compare-and-set, the HTTP call happens with no
  database transaction open, and the answer is written afterwards;
- network errors, 5xx, 429 and errors Meta marks transient are retried with
  backoff; anything else, or too many attempts, ends as ``failed``;
- Meta refuses an ``event_time`` more than 7 days old, so an event that could
  not be sent by then is ``expired`` instead of retried forever.

The event carries ``fbc``, ``client_user_agent`` (the browser type string of
the sign-up submit; Meta requires it for website events), ``event_time``,
``event_id`` (random, for Meta's deduplication), ``action_source``,
``event_source_url`` (the sign-up page, no query string) and ``opt_out``
(measurement only). No e-mail, phone, name or IP address.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import requests

from . import alerts, config, db

log = logging.getLogger("ubyhost.meta_capi")

EVENT_NAME = "CompleteRegistration"
ACTION_SOURCE = "website"
GRAPH_HOST = "https://graph.facebook.com"
TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 8
# Meta rejects the whole request if an event_time is older than 7 days.
# Stop an hour early so a slow retry cannot land just past the edge.
SEND_WINDOW = timedelta(days=7) - timedelta(hours=1)
# A claimed row whose worker died is handed back after this long.
STALE_SENDING = timedelta(minutes=10)
# Graph API error codes that mean "try again later": unknown/service errors,
# rate limits, temporarily unavailable.
_TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613, 80004}
# The token or the dataset is wrong: a configuration problem the owner can fix,
# so keep retrying (until the window closes) and raise an alert.
_CONFIG_CODES = {10, 190, 200, 803}

PENDING, SENDING, SENT, FAILED, EXPIRED = "pending", "sending", "sent", "failed", "expired"


class _Retry(Exception):
    """A send that may succeed later."""


class _Fatal(Exception):
    """A send that will never succeed as it is."""


def enabled() -> bool:
    return config.meta_capi_enabled()


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse(stored: str) -> datetime:
    parsed = datetime.fromisoformat(str(stored).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def enqueue(user_id: int) -> bool:
    """Queue the sign-up event for a just-verified account, if it consented.

    Called from ``signup.activate``. Only writes the database.
    """
    row = db.query_one(
        "SELECT id FROM ad_click WHERE user_account_id = ? AND platform = 'meta' "
        "AND withdrawn_at IS NULL AND fbc IS NOT NULL AND send_state IS NULL",
        (user_id,),
    )
    if not row:
        return False
    return db.update_if(
        "ad_click",
        row["id"],
        {
            "send_state": PENDING,
            "event_id": secrets.token_hex(16),
            "next_attempt_at": db.utcnow(),
        },
        {"send_state": None},
    )


def event_source_url() -> str:
    """The page the conversion happened on, without any query string."""
    return f"{config.PUBLIC_BASE_URL}/signup"


def _user_data(row: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"fbc": row["fbc"]}
    # Meta requires client_user_agent for website events. Stored with the
    # Meta consent; a browser that sent none simply leaves it out.
    if row["client_user_agent"]:
        data["client_user_agent"] = row["client_user_agent"]
    return data


def build_payload(row: Any) -> Dict[str, Any]:
    """The exact request body (before form encoding) for one row."""
    event = {
        "event_name": EVENT_NAME,
        "event_time": int(_parse(row["email_verified_at"]).timestamp()),
        "event_id": row["event_id"],
        "action_source": ACTION_SOURCE,
        "event_source_url": event_source_url(),
        # Meta: "we only use the event for attribution", not for ad delivery
        # optimisation. The consent is for measuring campaigns.
        "opt_out": True,
        "user_data": _user_data(row),
    }
    body: Dict[str, Any] = {"data": [event]}
    if config.META_TEST_EVENT_CODE:
        body["test_event_code"] = config.META_TEST_EVENT_CODE
    return body


def endpoint() -> str:
    return f"{GRAPH_HOST}/{config.META_GRAPH_VERSION}/{config.META_DATASET_ID}/events"


def _post(body: Dict[str, Any]) -> None:
    """One HTTP call. Raises _Retry or _Fatal; returns on success.

    Form-encoded like Meta's own curl example, with the token in the body so
    it never appears in a URL that a proxy might log.
    """
    form = {"data": json.dumps(body["data"], separators=(",", ":")),
            "access_token": config.META_ACCESS_TOKEN}
    if "test_event_code" in body:
        form["test_event_code"] = body["test_event_code"]
    try:
        response = requests.post(endpoint(), data=form, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise _Retry(f"network: {type(exc).__name__}") from None
    try:
        answer = response.json()
    except ValueError:
        answer = {}
    if response.status_code == 200 and int(answer.get("events_received") or 0) >= 1:
        return
    error = answer.get("error") if isinstance(answer, dict) else None
    error = error if isinstance(error, dict) else {}
    code = error.get("code")
    summary = f"HTTP {response.status_code}" + (f", code {code}" if code is not None else "")
    message = str(error.get("message") or "")[:200]
    detail = f"{summary}: {message}" if message else summary
    if (
        response.status_code >= 500
        or response.status_code == 429
        or error.get("is_transient")
        or code in _TRANSIENT_CODES
    ):
        raise _Retry(detail)
    if code in _CONFIG_CODES:
        alerts.raise_alert(
            "warning",
            "meta_capi_config",
            "Meta Conversions API refused the access token or dataset.",
            detail,
            dedupe_key="meta_capi_config",
            params={"error": detail},
        )
        raise _Retry(detail)
    raise _Fatal(detail)


def _delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(6 * 60 * 60, 60 * (2 ** min(attempts, 8))))


def expire_unsendable(now: Optional[datetime] = None) -> int:
    """Mark events Meta would refuse as too old. Runs with the API off too."""
    now = now or datetime.now(timezone.utc)
    cutoff = _iso(now - SEND_WINDOW)
    with db.immediate() as cur:
        cur.execute(
            "UPDATE ad_click SET send_state = ?, last_error = ? "
            "WHERE platform = 'meta' AND send_state = ? AND user_account_id IN ("
            "SELECT id FROM user_account WHERE email_verified_at < ?)",
            (EXPIRED, "older than Meta's 7-day event window", PENDING, cutoff),
        )
        return max(cur.rowcount, 0)


def send_pending(now: Optional[datetime] = None, limit: int = 20) -> Dict[str, int]:
    """Send the due sign-up events. The scheduler's ``meta_capi`` job."""
    summary = {"sent": 0, "retry": 0, "failed": 0, "expired": 0}
    if not enabled():
        return summary
    now = now or datetime.now(timezone.utc)
    db.execute(
        "UPDATE ad_click SET send_state = ? WHERE send_state = ? AND next_attempt_at < ?",
        (PENDING, SENDING, _iso(now - STALE_SENDING)),
    )
    summary["expired"] = expire_unsendable(now)
    rows = db.query(
        "SELECT c.id FROM ad_click c WHERE c.platform = 'meta' AND c.send_state = ? "
        "AND c.next_attempt_at <= ? ORDER BY c.id LIMIT ?",
        (PENDING, _iso(now), limit),
    )
    for candidate in rows:
        # Claim, then read what we claimed: a withdrawal that landed in
        # between leaves nothing to send.
        if not db.update_if(
            "ad_click",
            candidate["id"],
            {"send_state": SENDING, "next_attempt_at": _iso(now)},
            {"send_state": PENDING},
            extra_where="withdrawn_at IS NULL AND fbc IS NOT NULL",
        ):
            continue
        row = db.query_one(
            "SELECT c.*, u.email_verified_at FROM ad_click c "
            "JOIN user_account u ON u.id = c.user_account_id WHERE c.id = ?",
            (candidate["id"],),
        )
        attempts = int(row["attempts"] or 0) + 1
        try:
            _post(build_payload(row))
        except _Retry as exc:
            terminal = attempts >= MAX_ATTEMPTS
            db.update_if(
                "ad_click",
                row["id"],
                {
                    "send_state": FAILED if terminal else PENDING,
                    "attempts": attempts,
                    "last_error": str(exc)[:400],
                    "next_attempt_at": _iso(now + _delay(attempts)),
                },
                {"send_state": SENDING},
            )
            summary["failed" if terminal else "retry"] += 1
            log.warning("meta event %s not sent (attempt %s): %s", row["id"], attempts, exc)
            continue
        except _Fatal as exc:
            db.update_if(
                "ad_click",
                row["id"],
                {"send_state": FAILED, "attempts": attempts, "last_error": str(exc)[:400]},
                {"send_state": SENDING},
            )
            summary["failed"] += 1
            log.warning("meta event %s refused: %s", row["id"], exc)
            continue
        db.update_if(
            "ad_click",
            row["id"],
            {
                "send_state": SENT,
                "attempts": attempts,
                "last_error": None,
                # Retention counts from here: fbc is deleted 7 days later.
                "uploaded_at": db.utcnow(),
            },
            {"send_state": SENDING},
        )
        summary["sent"] += 1
    return summary
