"""Havel's quick-help layer (plan 17c): five topics, each with two to four questions.

An answer is the guide strings named by its keys, in order, shown as paragraphs.
No model call, no cost, no count. When the host presses "Still need help? Ask
Havel", the topic and the keys they have just read travel with the message as
``topic`` and ``read_keys`` in the host context, so Havel does not repeat them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import host_i18n

TOPICS: List[Dict[str, Any]] = [
    {"id": "stays", "icon": "calendar-days", "label": "havel.topic.stays", "questions": [
        {"id": "add", "label": "havel.q.stays.add", "keys": ["guide.stays.body"], "page": "add_stay"},
        {"id": "change", "label": "havel.q.stays.change", "keys": ["guide.stays.detail"], "page": "stays"},
        {"id": "cancelled", "label": "havel.q.stays.cancelled",
         "keys": ["guide.stays.cancelled", "guide.stays.dates_changed"], "page": "stays"},
    ]},
    {"id": "guest_link", "icon": "external-link", "label": "havel.topic.guest_link", "questions": [
        {"id": "how", "label": "havel.q.guest_link.how",
         "keys": ["guide.guests.body", "guide.guests.step_pin", "guide.guests.step_pick", "guide.guests.step_claim",
                  "guide.guests.step_form"], "page": "property_guests"},
        {"id": "where", "label": "havel.q.guest_link.where", "keys": ["guide.setup.step3"], "page": "property_guests"},
        {"id": "broken", "label": "havel.q.guest_link.broken", "keys": ["guide.faq.link_a"], "page": "property_guests"},
    ]},
    {"id": "reporting", "icon": "send", "label": "havel.topic.reporting", "questions": [
        {"id": "when", "label": "havel.q.reporting.when",
         "keys": ["guide.reporting.body", "guide.reporting.immediate", "guide.reporting.scheduled",
                  "guide.reporting.manual"], "page": "reports"},
        {"id": "colours", "label": "havel.q.reporting.colours",
         "keys": ["guide.statuses.lede", "guide.statuses.ready", "guide.statuses.waiting", "guide.statuses.reported",
                  "guide.statuses.failed"], "page": "guide_statuses"},
        {"id": "czech", "label": "havel.q.reporting.czech", "keys": ["guide.faq.czech_a"], "page": "reports"},
    ]},
    {"id": "calendars", "icon": "refresh-cw", "label": "havel.topic.calendars", "questions": [
        {"id": "connect", "label": "havel.q.calendars.connect", "keys": ["guide.setup.step2"], "page": "property_calendars"},
        {"id": "stale", "label": "havel.q.calendars.stale", "keys": ["guide.stays.body"], "page": "property_calendars"},
    ]},
    {"id": "wrong", "icon": "triangle-alert", "label": "havel.topic.wrong", "questions": [
        {"id": "report", "label": "havel.q.wrong.report", "keys": ["guide.reporting.failure"], "page": "reports"},
        {"id": "error", "label": "havel.q.wrong.error", "keys": ["havel.topic.support_body"], "page": None,
         "support": True},
    ]},
]
TOPIC_IDS = [t["id"] for t in TOPICS]

# The hosting page's nav key -> the topic shown first (plan 17c).
FIRST_FOR_NAV = {"cleaning": "stays", "reservations": "stays", "submissions": "reporting", "housebook": "reporting",
                 "apartments": "guest_link", "dashboard": "reporting"}


def ordered(nav: str = "") -> List[Dict[str, Any]]:
    first = FIRST_FOR_NAV.get(nav or "")
    return sorted(TOPICS, key=lambda t: 0 if t["id"] == first else 1)


def topic(topic_id: str) -> Optional[Dict[str, Any]]:
    return next((t for t in TOPICS if t["id"] == topic_id), None)


def question(topic_id: str, q_id: str) -> Optional[Dict[str, Any]]:
    t = topic(topic_id)
    if not t:
        return None
    return next((q for q in t["questions"] if q["id"] == q_id), None)


def read_keys(topic_id: str, q_id: str) -> List[str]:
    q = question(topic_id, q_id)
    return [k for k in (q["keys"] if q else []) if k.startswith("guide.")]


def answer(lang: str, topic_id: str, q_id: str) -> Optional[Dict[str, Any]]:
    """Paragraphs for one question, in the interface language, or None."""
    q = question(topic_id, q_id)
    if not q:
        return None
    texts = [host_i18n.translate(lang, k) for k in q["keys"]]
    return {"topic": topic_id, "question": q, "paragraphs": [t for t in texts if t and t != "?"],
            "page": q.get("page"), "support": bool(q.get("support"))}
