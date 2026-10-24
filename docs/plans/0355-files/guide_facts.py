"""0355: Quick answers, the yes/no facts of a property's guest guide.

The host answers short questions in five steps (routes/guest_guide.py, the
quick pages). Each answer becomes one short line inside the card it belongs to,
for guests (guest page) and for Leon (leon.guide_block), so Leon can cite that
card. "Not sure" stores nothing. Facts are about the property, never a person.
Host copy: host_i18n ``guest_guide.quick.*``; guest lines: i18n ``guide_fact_*``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

from . import db, guest_guide, i18n

# One topic per step, in screen order.
STEPS = ("times", "rules", "access", "kitchen", "comfort")

# fact -> (step, answer type, card kind it shows in). Types: "yesno" ('yes' or
# 'no'), "time" ('HH:MM'), "range" ('HH:MM-HH:MM'). Every card is a default card.
FACTS: Dict[str, tuple] = {
    "checkin_from": ("times", "time", "checkin"),
    "checkout_by": ("times", "time", "checkout"),
    "late_checkout": ("times", "yesno", "checkout"),
    "luggage": ("times", "yesno", "checkin"),
    "pets": ("rules", "yesno", "house_rules"),
    "smoking": ("rules", "yesno", "house_rules"),
    "parties": ("rules", "yesno", "house_rules"),
    "quiet_hours": ("rules", "range", "house_rules"),
    "parking": ("access", "yesno", "parking"),
    "lift": ("access", "yesno", "getting_here"),
    "step_free": ("access", "yesno", "getting_here"),
    "dishwasher": ("kitchen", "yesno", "kitchen_appliances"),
    "coffee_machine": ("kitchen", "yesno", "kitchen_appliances"),
    "washing_machine": ("kitchen", "yesno", "washing_machine"),
    "dryer": ("kitchen", "yesno", "washing_machine"),
    "iron": ("kitchen", "yesno", "bedrooms"),
    "air_conditioning": ("comfort", "yesno", "heating"),
    "balcony": ("comfort", "yesno", "bedrooms"),
    "safe": ("comfort", "yesno", "bedrooms"),
    "cot": ("comfort", "yesno", "bedrooms"),
    "high_chair": ("comfort", "yesno", "bedrooms"),
    "hair_dryer": ("comfort", "yesno", "bathroom"),
}

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_SEEN = "step."  # a row "step.<step>" = "seen" remembers a saved or skipped step


def answers(apartment_id: int) -> Dict[str, str]:
    rows = db.query("SELECT fact, value FROM guide_fact WHERE apartment_id = ?", (apartment_id,))
    return {r["fact"]: r["value"] for r in rows}


def _put(apartment_id: int, fact: str, value: str) -> None:
    db.execute(
        "INSERT INTO guide_fact (apartment_id, fact, value, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (apartment_id, fact) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (apartment_id, fact, value, db.utcnow()),
    )


def _clean(kind: str, raw: str) -> str:
    """The stored value, or "" for not sure / not valid."""
    raw = (raw or "").strip()
    if kind == "yesno":
        return raw if raw in ("yes", "no") else ""
    if kind == "time":
        return raw if _TIME.match(raw) else ""
    start, _, end = raw.partition("-")
    return raw if _TIME.match(start) and _TIME.match(end) else ""


def mark_seen(apartment_id: int, step: str) -> None:
    _put(apartment_id, _SEEN + step, "seen")


def save_step(apartment_id: int, step: str, form: Mapping[str, Any]) -> None:
    """Store one step's answers; a blank or invalid answer removes the fact."""
    if step not in STEPS:
        raise guest_guide.GuideError("flash.error.guide_unknown_card")
    for fact, (fact_step, kind, _card) in FACTS.items():
        if fact_step != step:
            continue
        if kind == "range":
            raw = f"{str(form.get(fact + '_from') or '').strip()}-{str(form.get(fact + '_to') or '').strip()}"
        else:
            raw = str(form.get(fact) or "")
        value = _clean(kind, raw)
        if value:
            _put(apartment_id, fact, value)
        else:
            db.execute("DELETE FROM guide_fact WHERE apartment_id = ? AND fact = ?", (apartment_id, fact))
    mark_seen(apartment_id, step)


def next_step(apartment_id: int) -> str:
    """The first step the host has neither saved nor skipped; "" when all are done."""
    seen = answers(apartment_id)
    return next((s for s in STEPS if _SEEN + s not in seen), "")


def step_fields(apartment_id: int, step: str) -> List[Dict[str, str]]:
    """What the step page shows: one entry per question with the stored answer."""
    values = answers(apartment_id)
    out = []
    for fact, (fact_step, kind, _card) in FACTS.items():
        if fact_step != step:
            continue
        value = values.get(fact, "")
        start, _, end = value.partition("-") if kind == "range" else ("", "", "")
        out.append({"key": fact, "type": kind, "value": value, "start": start, "end": end})
    return out


def lines(apartment_id: int, lang: str) -> Dict[str, List[str]]:
    """card kind -> the guest lines of its answered facts, in ``lang`` (guest languages)."""
    t = i18n.translator(lang)
    values = answers(apartment_id)
    out: Dict[str, List[str]] = {}
    for fact, (_step, kind, card) in FACTS.items():
        value = values.get(fact)
        if not value:
            continue
        if kind == "yesno":
            text = t(f"guide_fact_{fact}_{value}")
        elif kind == "time":
            text = t(f"guide_fact_{fact}", time=value)
        else:
            start, _, end = value.partition("-")
            text = t(f"guide_fact_{fact}", start=start, end=end)
        out.setdefault(card, []).append(text)
    return out


def for_guest(apartment_id: int, level: str, lang: str) -> List[Dict[str, Any]]:
    """``guest_guide.for_guest`` plus Quick answers: every card gets ``facts`` (lines in
    ``lang``). A built-in card the host has not written yet still reaches guests when
    it has facts, with its own text left out (a draft is never shown)."""
    allowed = guest_guide._LEVELS.get(level)
    if not allowed or not guest_guide.progress(apartment_id)["live"]:
        return []
    facts = lines(apartment_id, lang)
    out = []
    for row in guest_guide.items(apartment_id):
        if row["visibility"] not in allowed:
            continue
        mine = facts.get(row["kind"], []) if row["kind"] != "custom" else []
        if row["state"] == "done":
            out.append({**row, "facts": mine})
        elif mine and row["state"] in ("missing", "check"):
            out.append({**row, "location": "", "steps": "", "watch_out": "", "video_url": "", "facts": mine})
    return out
