"""Server-side PostHog funnel sync for host accounts (posthog-analytics plan).

Sends stage events and person properties from existing funnel rows. Never
touches guest tables or ad_click. Failures are logged with account id and HTTP
status only; they do not propagate to callers.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import admin_funnel, analytics, config, db

log = logging.getLogger("ubyhost.posthog_sync")

_TIMEOUT = 3
_ALLOWED_SIGNUP_SOURCES = frozenset({"google", "meta", "none"})
_UTM_FIELDS = (
    ("signup_utm_source", "utm_source"),
    ("signup_utm_medium", "utm_medium"),
    ("signup_utm_campaign", "utm_campaign"),
)


def _click_id_in(value: str) -> bool:
    lower = value.lower()
    return "gclid" in lower or "fbclid" in lower


def _stage_keys() -> List[str]:
    return [key for key, _column in admin_funnel.stages()]


def _stages_to_send(previous: Optional[str], current: str) -> List[str]:
    keys = _stage_keys()
    if not current or current not in keys:
        return []
    end = keys.index(current)
    if not previous:
        return keys[: end + 1]
    if previous not in keys:
        return keys[: end + 1]
    start = keys.index(previous)
    if start >= end:
        return []
    return keys[start + 1 : end + 1]


def _person_set(account: Dict[str, Any], funnel_stage: str) -> Dict[str, Any]:
    props: Dict[str, Any] = {"funnel_stage": funnel_stage}
    email = account.get("email")
    if not email:
        username = account.get("username") or ""
        if "@" in username:
            email = username
    if email:
        props["email"] = email
    display_name = account.get("display_name")
    if display_name:
        props["workspace_name"] = display_name
    signup_source = account.get("signup_source")
    if signup_source in _ALLOWED_SIGNUP_SOURCES:
        props["signup_source"] = signup_source
    for column, key in _UTM_FIELDS:
        value = account.get(column)
        if value and not _click_id_in(str(value)):
            props[key] = value
    return props


def _capture(
    api_key: str,
    api_host: str,
    event: str,
    distinct_id: str,
    properties: Dict[str, Any],
    timestamp: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "api_key": api_key,
        "event": event,
        "distinct_id": distinct_id,
        "properties": properties,
    }
    if timestamp:
        payload["timestamp"] = timestamp
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{api_host.rstrip('/')}/capture/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(
                request.full_url, response.status, response.reason, response.headers, None
            )


def _stage_timestamp(row: Dict[str, Any], stage_key: str) -> Optional[str]:
    columns = {key: column for key, column in admin_funnel.stages()}
    column = columns.get(stage_key)
    if not column:
        return None
    value = row.get(column)
    return value if value else None


def sync() -> Dict[str, int]:
    """Send pending funnel stage events. Returns sent, skipped and failed counts."""
    counts = {"sent": 0, "skipped": 0, "failed": 0}
    if not analytics.enabled():
        return counts

    api_key = config.POSTHOG_PROJECT_API_KEY
    api_host = analytics.tag()["api_host"] if analytics.tag() else ""
    if not api_host:
        return counts

    funnel_rows = {row["id"]: row for row in admin_funnel.rows()["rows"]}
    accounts = db.query(
        "SELECT id, email, username, display_name, signup_utm_source, signup_utm_medium, "
        "signup_utm_campaign, signup_source, posthog_stage FROM user_account WHERE role = 'host'"
    )
    for raw_account in accounts:
        account = dict(raw_account)
        row = funnel_rows.get(account["id"])
        if not row:
            counts["skipped"] += 1
            continue
        current = row.get("stage") or ""
        pending = _stages_to_send(account.get("posthog_stage"), current)
        if not pending:
            counts["skipped"] += 1
            continue

        distinct_id = str(account["id"])
        person_base = {
            "email": account.get("email"),
            "username": account.get("username"),
            "display_name": account.get("display_name"),
            "signup_source": account.get("signup_source"),
            "signup_utm_source": account.get("signup_utm_source"),
            "signup_utm_medium": account.get("signup_utm_medium"),
            "signup_utm_campaign": account.get("signup_utm_campaign"),
        }
        try:
            for stage_key in pending:
                properties: Dict[str, Any] = {
                    "$ip": None,
                    "$set": _person_set(person_base, stage_key),
                }
                _capture(
                    api_key,
                    api_host,
                    stage_key,
                    distinct_id,
                    properties,
                    _stage_timestamp(row, stage_key),
                )
                counts["sent"] += 1
            db.execute(
                "UPDATE user_account SET posthog_stage = ? WHERE id = ?",
                (current, account["id"]),
            )
        except urllib.error.HTTPError as exc:
            log.warning("posthog capture failed for account %s: %s", account["id"], exc.code)
            counts["failed"] += 1
        except Exception:
            log.warning("posthog capture failed for account %s", account["id"], exc_info=True)
            counts["failed"] += 1

    return counts
