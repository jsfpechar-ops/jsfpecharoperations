"""Security incident register and the controller-notification draft (BE-13/LD-5).

Platform-admin only. The register is the record Art 33(5) GDPR requires. The
draft is rendered as text to copy; nothing is sent automatically.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import alerts, db

# A burst of rate-limited guest links suggests a link may have been shared or
# attacked; it raises a review suggestion, never an incident by itself.
REVIEW_THRESHOLD = 5
REVIEW_WINDOW_HOURS = 24

TIMESTAMP_FIELDS = (
    "contained_at",
    "controllers_notified_at",
    "authority_notified_at",
    "subjects_notified_at",
    "closed_at",
)


def list_all() -> List[Any]:
    return db.query(
        "SELECT * FROM security_incident ORDER BY detected_at DESC, id DESC"
    )


def get(incident_id: int):
    return db.query_one("SELECT * FROM security_incident WHERE id = ?", (incident_id,))


def affected_owner_ids(incident) -> List[int]:
    try:
        return [int(value) for value in json.loads(incident["affected_owner_ids"] or "[]")]
    except (TypeError, ValueError):
        return []


def create(
    *,
    detected_at: str,
    summary: str,
    reported_by: str = "",
    data_categories: str = "",
    owner_ids: Optional[List[int]] = None,
    approx_subjects: Optional[int] = None,
    risk_level: str = "",
    notes: str = "",
) -> int:
    now = db.utcnow()
    return db.insert(
        "security_incident",
        {
            "detected_at": detected_at,
            "reported_by": reported_by,
            "summary": summary,
            "data_categories": data_categories,
            "affected_owner_ids": json.dumps([int(v) for v in (owner_ids or [])]),
            "approx_subjects": approx_subjects,
            "risk_level": risk_level or None,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        },
    )


def update(incident_id: int, values: Dict[str, Any]) -> None:
    db.update("security_incident", incident_id, {**values, "updated_at": db.utcnow()})


def mark_timestamp(incident_id: int, field: str, when: Optional[str] = None) -> None:
    if field not in TIMESTAMP_FIELDS:
        raise ValueError("unknown incident timestamp")
    update(incident_id, {field: when or db.utcnow()})


def controller_notification_draft(incident) -> str:
    """The pre-filled notice the operator sends to each affected controller.

    Shown as text to copy — the plan is explicit that it must not auto-send.
    """
    contacts: List[str] = []
    for owner_id in affected_owner_ids(incident):
        for entity in db.query(
            "SELECT name, contact_email FROM legal_entity "
            "WHERE owner_user_id = ? AND contact_email IS NOT NULL",
            (owner_id,),
        ):
            contacts.append(f"{entity['name']} <{entity['contact_email']}>")
    return "\n".join(
        [
            "Subject: Notification of a personal-data incident (Art 33(2) GDPR)",
            "",
            f"Detected: {incident['detected_at']}",
            f"Summary: {incident['summary']}",
            f"Data categories: {incident['data_categories'] or '-'}",
            "Approximate data subjects: "
            f"{incident['approx_subjects'] if incident['approx_subjects'] is not None else '-'}",
            f"Risk: {incident['risk_level'] or '-'}",
            "",
            "To: " + ("; ".join(contacts) if contacts else "(no controller contact on file)"),
            "",
            "We are notifying you without undue delay as your processor. As controller you must",
            "assess the incident and, where required, notify the supervisory authority (UOOU)",
            "within 72 hours of becoming aware. Please confirm receipt and tell us what you need.",
        ]
    )


def open_review_alerts() -> List[Any]:
    """Unresolved incident-review suggestions, for the admin incidents page."""
    return db.query(
        "SELECT * FROM alert WHERE kind = 'incident_review' AND resolved_at IS NULL "
        "ORDER BY id DESC"
    )


def suggest_review_if_frequent() -> bool:
    """Raise a review suggestion when guest links are rate-limited often enough."""
    since = (
        datetime.now(timezone.utc) - timedelta(hours=REVIEW_WINDOW_HOURS)
    ).replace(microsecond=0).isoformat()
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM audit "
        "WHERE action = 'guest_pin_rate_limited' AND at > ?",
        (since,),
    )
    if not row or row["n"] < REVIEW_THRESHOLD:
        return False
    alerts.raise_alert(
        "warning",
        "incident_review",
        "Repeated guest PIN failures may warrant an incident review.",
        f"{row['n']} guest links were rate-limited in the last {REVIEW_WINDOW_HOURS} hours.",
        dedupe_key=(
            "incident_review:"
            + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ),
        params={"count": row["n"], "hours": REVIEW_WINDOW_HOURS},
    )
    return True
