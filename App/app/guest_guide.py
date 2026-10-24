"""0341: the guest guide, one list of items per property.

The host fills small cards ("Turn on the heating"); guests read the confirmed
ones, and later the guest bot answers only from them. An item a guest may see
is ``state = 'done'``: a drafted item (``'check'``) waits for the host. Copy
for titles and prompts lives in host_i18n under ``guide.kind.<kind>.*``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import db

# Guest order. A custom item names one of these.
TOPICS = (
    "arrival",
    "wifi",
    "heating",
    "kitchen",
    "rooms",
    "bathroom",
    "rules",
    "trash",
    "checkout",
    "area",
    "emergency",
)

# Built-in cards: kind -> topic, in guest order (0354: few, rich cards; each
# prompt is a checklist of what guests ask). Never rename a kind: rows use it.
KINDS: Dict[str, str] = {
    "checkin": "arrival",
    "keys": "arrival",
    "getting_here": "arrival",
    "parking": "arrival",
    "garage": "arrival",
    "wifi": "wifi",
    "tv": "wifi",
    "heating": "heating",
    "hot_water": "heating",
    "air_conditioning": "heating",
    "kitchen_appliances": "kitchen",
    "dishwasher": "kitchen",
    "coffee_machine": "kitchen",
    "bedrooms": "rooms",
    "sofa_bed": "rooms",
    "balcony": "rooms",
    "bathroom": "bathroom",
    "washing_machine": "bathroom",
    "house_rules": "rules",
    "trash": "trash",
    "checkout": "checkout",
    "area_tips": "area",
    "emergency": "emergency",
    "something_wrong": "emergency",
}

# Every property gets these cards. The other built-in kinds are narrower cards
# kept for data that already uses them: they appear only where an import or
# earlier data created them.
DEFAULT_KINDS = (
    "checkin",
    "keys",
    "getting_here",
    "parking",
    "wifi",
    "heating",
    "hot_water",
    "kitchen_appliances",
    "bedrooms",
    "bathroom",
    "washing_machine",
    "house_rules",
    "trash",
    "checkout",
    "area_tips",
    "emergency",
    "something_wrong",
)

# The guide goes live for guests once these five are done (or skipped).
MUST_HAVE = ("checkin", "wifi", "heating", "checkout", "emergency")

VISIBILITY = ("everyone", "booked", "host")
STATES = ("missing", "check", "done", "skipped")

LIMITS = {
    "title": 120,
    "location": 500,
    "steps": 4000,
    "watch_out": 1000,
    "video_url": 500,
}

# Guest levels: what each one may read.
_LEVELS = {
    "everyone": ("everyone",),
    "booked": ("everyone", "booked"),
}


class GuideError(ValueError):
    """A field the host sent is not acceptable; ``key`` is the flash message key."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def _order(kind: str) -> int:
    kinds = list(KINDS)
    return kinds.index(kind) if kind in KINDS else len(kinds)


def add_kind(apartment_id: int, kind: str, *, source: str = "host") -> bool:
    """Create the built-in card ``kind`` if the property lacks it; True when created."""
    if kind not in KINDS:
        raise GuideError("flash.error.guide_unknown_card")
    now = db.utcnow()
    return (
        db.execute(
            "INSERT INTO guide_item (apartment_id, topic, kind, source, sort_order, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (apartment_id, KINDS[kind], kind, source, _order(kind), now, now),
        )
        == 1
    )


def ensure_defaults(apartment) -> None:
    """Give the property its default cards, once; carry over the old free-text fields.

    ``checkin_info`` / ``checkout_info`` were host text never shown anywhere,
    so they become drafts (``'check'``) the host confirms, not live items.
    """
    for kind in DEFAULT_KINDS:
        add_kind(apartment["id"], kind)
    legacy = {"checkin": apartment["checkin_info"], "checkout": apartment["checkout_info"]}
    for kind, text in legacy.items():
        text = (text or "").strip()
        if not text:
            continue
        db.execute(
            "UPDATE guide_item SET steps = ?, state = 'check', source = 'legacy', updated_at = ? "
            "WHERE apartment_id = ? AND kind = ? AND state = 'missing' AND steps = ''",
            (text[: LIMITS["steps"]], db.utcnow(), apartment["id"], kind),
        )


def items(apartment_id: int) -> List[Dict[str, Any]]:
    """Every item of the property, in guest order, each with its photo count."""
    rows = db.query(
        "SELECT i.*, (SELECT COUNT(*) FROM guide_photo p WHERE p.item_id = i.id) AS photos "
        "FROM guide_item i WHERE i.apartment_id = ? ORDER BY i.sort_order, i.id",
        (apartment_id,),
    )
    out = [dict(row) for row in rows]
    out.sort(key=lambda r: TOPICS.index(r["topic"]) if r["topic"] in TOPICS else len(TOPICS))
    return out


def get(apartment_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    """One item, only when it belongs to this property."""
    row = db.query_one(
        "SELECT * FROM guide_item WHERE id = ? AND apartment_id = ?", (item_id, apartment_id)
    )
    return dict(row) if row else None


def _clean(fields: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, limit in LIMITS.items():
        if name not in fields:
            continue
        value = str(fields.get(name) or "").replace("\r\n", "\n").strip()
        if len(value) > limit:
            raise GuideError("flash.error.guide_too_long")
        out[name] = value
    url = out.get("video_url")
    if url and not url.startswith("https://"):
        raise GuideError("flash.error.guide_video_url")
    if "visibility" in fields:
        if fields["visibility"] not in VISIBILITY:
            raise GuideError("flash.error.guide_visibility")
        out["visibility"] = fields["visibility"]
    return out


def save(apartment_id: int, item_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Save the host's edit; the item is done when it says where or how, else missing."""
    item = get(apartment_id, item_id)
    if not item:
        raise GuideError("flash.error.guide_no_such_item")
    values = _clean(fields)
    if item["kind"] == "custom" and "title" in values and not values["title"]:
        raise GuideError("flash.error.guide_title_required")
    merged = {**item, **values}
    values["state"] = "done" if (merged["steps"] or merged["location"]) else "missing"
    if item["source"] != "host":
        values["source"] = "host"
    values["updated_at"] = db.utcnow()
    db.update("guide_item", item_id, values)
    return get(apartment_id, item_id)


def skip(apartment_id: int, item_id: int, skipped: bool = True) -> None:
    """Mark a card as not applying to this property (or bring it back)."""
    item = get(apartment_id, item_id)
    if not item:
        raise GuideError("flash.error.guide_no_such_item")
    has_text = bool(item["steps"] or item["location"])
    if skipped:
        state = "skipped"
    elif has_text and item["source"] == "host":
        state = "done"
    else:
        # Imported or legacy text the host never saved goes back to "Check this",
        # never straight to guests.
        state = "check" if has_text else "missing"
    db.update("guide_item", item_id, {"state": state, "updated_at": db.utcnow()})


def add_custom(apartment_id: int, topic: str, title: str) -> int:
    """A card the host names themself, under one of the topics."""
    if topic not in TOPICS:
        raise GuideError("flash.error.guide_unknown_card")
    title = (title or "").strip()
    if not title:
        raise GuideError("flash.error.guide_title_required")
    if len(title) > LIMITS["title"]:
        raise GuideError("flash.error.guide_too_long")
    now = db.utcnow()
    return db.insert(
        "guide_item",
        {
            "apartment_id": apartment_id,
            "topic": topic,
            "kind": "custom",
            "title": title,
            "sort_order": len(KINDS) + 1,
            "created_at": now,
            "updated_at": now,
        },
    )


def delete_custom(apartment_id: int, item_id: int) -> bool:
    """Delete a custom card; built-in cards are skipped instead. True when deleted."""
    return (
        db.execute(
            "DELETE FROM guide_item WHERE id = ? AND apartment_id = ? AND kind = 'custom'",
            (item_id, apartment_id),
        )
        == 1
    )


def progress(apartment_id: int) -> Dict[str, Any]:
    """Counts for the progress ring and whether guests can see the guide yet."""
    rows = items(apartment_id)
    counted = [r for r in rows if r["state"] != "skipped"]
    done = sum(1 for r in counted if r["state"] == "done")
    must = {r["kind"]: r["state"] for r in rows if r["kind"] in MUST_HAVE}
    must_done = sum(1 for kind in MUST_HAVE if must.get(kind) in ("done", "skipped"))
    return {
        "done": done,
        "total": len(counted),
        "check": sum(1 for r in counted if r["state"] == "check"),
        "must_have_done": must_done,
        "must_have_total": len(MUST_HAVE),
        "live": must_done == len(MUST_HAVE),
    }


def for_guest(apartment_id: int, level: str) -> List[Dict[str, Any]]:
    """The items a guest at ``level`` may read: confirmed, visible to them, never host-only.

    Empty until the guide is live, so a half-written guide never reaches guests.
    """
    allowed = _LEVELS.get(level)
    if not allowed or not progress(apartment_id)["live"]:
        return []
    return [r for r in items(apartment_id) if r["state"] == "done" and r["visibility"] in allowed]
