# 0341: Guest guide data layer

Status: review
Depends on: none | Base commit: 92646d3 | Branch: task/0291-guest-guide-data
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the tables and the module that hold a property's guest guide: one row per card ("Turn on the heating"), with visibility levels and states. This is the base for the host guide page (0342), the card editor (0343), the guest guide tab (0344), and later the imports and the guest bot ([plan](../plans/guest-guide.md)).

## 2. Context

- Rules (AGENTS.md, rules.md#database): all SQL through `App/app/db.py` helpers, parameterised, Postgres-portable. No `INSERT OR IGNORE`, no `lastrowid`. A schema change is a new `App/app/migrations/NNNN_name.sql` file; `db.SCHEMA` and `db.ADDED_COLUMNS` must not change. The lint says the next free migration is 0013.
- `ON CONFLICT DO NOTHING` without a target is valid in SQLite and Postgres; the partial unique index makes a second built-in card of the same kind a conflict.
- The `apartment` table already has `checkin_info` and `checkout_info` text columns that no template shows. `ensure_defaults` turns them into drafts the host must confirm.
- Guide items are host-written. They hold no guest personal data, so no `retention.py` line is needed in this brief.
- Anchor for the test fixture pattern, `App/tests/test_door_code_one_lock_one_property.py`:

```python
    for n, name in enumerate(("Flat A", "Flat B")):
```

All files in this brief are new except the test-map row, which the orchestrator already added.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0013_guest_guide.sql` | create | `guide_item` and `guide_photo` tables |
| `App/app/guest_guide.py` | create | Topics, built-in cards, save/skip/custom, progress, guest filter |
| `App/tests/test_guest_guide.py` | create | Tests for the module |

No other file may change.

## 4. Steps

1. Check that the migration number is still free: `ls App/app/migrations/ | tail -3 2>&1 | tail -30`. Expected: the last file is `0012_web_push.sql`. If a `0013_*` file exists, STOP (§8).

2. Create `App/app/migrations/0013_guest_guide.sql` with exactly this content:

```sql
-- Brief 0341: the guest guide (plan: docs/plans/guest-guide.md).
--
-- guide_item: one thing a guest may need to know or do at a property ("Turn
-- on the heating"). The host writes it; guests read it on the guide page and
-- the guest bot answers from it. kind names a built-in card ('checkin',
-- 'wifi', ...) or 'custom'; a property has at most one row per built-in kind.
-- visibility: 'everyone' (QR page), 'booked' (stay link during the stay only),
-- 'host' (never shown to guests). state: 'missing' (empty card), 'check'
-- (drafted for the host, not confirmed: never shown to guests), 'done',
-- 'skipped' (does not apply, e.g. no air conditioning). Host-written content,
-- no guest personal data.
CREATE TABLE IF NOT EXISTS guide_item (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'custom',
    title         TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    steps         TEXT NOT NULL DEFAULT '',
    watch_out     TEXT NOT NULL DEFAULT '',
    video_url     TEXT NOT NULL DEFAULT '',
    visibility    TEXT NOT NULL DEFAULT 'everyone' CHECK (visibility IN ('everyone', 'booked', 'host')),
    state         TEXT NOT NULL DEFAULT 'missing' CHECK (state IN ('missing', 'check', 'done', 'skipped')),
    source        TEXT NOT NULL DEFAULT 'host' CHECK (source IN ('host', 'legacy', 'booking', 'airbnb', 'paste', 'ai', 'guest_question')),
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guide_item_apartment ON guide_item (apartment_id, topic, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS uq_guide_item_kind ON guide_item (apartment_id, kind) WHERE kind != 'custom';

-- guide_photo: photos on a guide item, stored under DATA_DIR/guide_photos by
-- brief 0343. Kept while the item exists; the files go with the item.
CREATE TABLE IF NOT EXISTS guide_photo (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id       INTEGER NOT NULL REFERENCES guide_item(id) ON DELETE CASCADE,
    file_name     TEXT NOT NULL UNIQUE,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guide_photo_item ON guide_photo (item_id, sort_order);
```

Command: `cd App && .venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

3. Create `App/app/guest_guide.py` with exactly this content:

```python
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

# Built-in cards: kind -> topic. Order within a topic is the order here.
KINDS: Dict[str, str] = {
    "checkin": "arrival",
    "keys": "arrival",
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
    "sofa_bed": "rooms",
    "balcony": "rooms",
    "washing_machine": "bathroom",
    "house_rules": "rules",
    "trash": "trash",
    "checkout": "checkout",
    "area_tips": "area",
    "emergency": "emergency",
}

# Every property gets these cards; the others come from imports or the host.
DEFAULT_KINDS = (
    "checkin",
    "keys",
    "wifi",
    "heating",
    "hot_water",
    "house_rules",
    "trash",
    "checkout",
    "emergency",
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
```

Command: `cd App && .venv/bin/python -c "import app.guest_guide" 2>&1 | tail -30`. Expected: no output.

4. Create `App/tests/test_guest_guide.py` with exactly this content:

```python
"""0341: the guest guide data layer."""
from __future__ import annotations

import pytest

from app import db, guest_guide

PREFIX = "guide-0291-"


def _cleanup() -> None:
    db.execute(
        "DELETE FROM apartment WHERE permalink_token LIKE ?", (PREFIX + "%",)
    )


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Guide flat",
            "permalink_token": PREFIX + "tok",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "checkin_info": "Key box left of the door, code from your host.",
            "created_at": now,
        },
    )
    yield db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))
    _cleanup()


def _by_kind(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def test_defaults_are_created_once(apartment):
    guest_guide.ensure_defaults(apartment)
    guest_guide.ensure_defaults(apartment)
    kinds = [r["kind"] for r in guest_guide.items(apartment["id"])]
    assert sorted(kinds) == sorted(guest_guide.DEFAULT_KINDS)
    assert len(kinds) == len(set(kinds))


def test_old_checkin_text_becomes_a_draft(apartment):
    guest_guide.ensure_defaults(apartment)
    checkin = _by_kind(apartment["id"])["checkin"]
    assert checkin["state"] == "check"
    assert checkin["source"] == "legacy"
    assert checkin["steps"].startswith("Key box")


def test_items_come_in_guest_order(apartment):
    guest_guide.ensure_defaults(apartment)
    guest_guide.add_kind(apartment["id"], "garage", source="booking")
    topics = [r["topic"] for r in guest_guide.items(apartment["id"])]
    order = [guest_guide.TOPICS.index(t) for t in topics]
    assert order == sorted(order)


def test_save_marks_done_and_validates(apartment):
    guest_guide.ensure_defaults(apartment)
    wifi = _by_kind(apartment["id"])["wifi"]
    saved = guest_guide.save(
        apartment["id"], wifi["id"], {"steps": "Network Vivus, password on the router", "visibility": "booked"}
    )
    assert saved["state"] == "done"
    assert saved["visibility"] == "booked"
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"video_url": "http://example.test/v"})
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"steps": "x" * 4001})
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"], wifi["id"], {"visibility": "public"})
    cleared = guest_guide.save(apartment["id"], wifi["id"], {"steps": ""})
    assert cleared["state"] == "missing"


def test_another_property_cannot_edit_the_item(apartment):
    guest_guide.ensure_defaults(apartment)
    wifi = _by_kind(apartment["id"])["wifi"]
    with pytest.raises(guest_guide.GuideError):
        guest_guide.save(apartment["id"] + 100000, wifi["id"], {"steps": "x"})


def test_custom_cards_can_be_added_and_deleted_built_in_cannot(apartment):
    guest_guide.ensure_defaults(apartment)
    item_id = guest_guide.add_custom(apartment["id"], "kitchen", "Induction hob")
    assert guest_guide.get(apartment["id"], item_id)["kind"] == "custom"
    assert guest_guide.delete_custom(apartment["id"], item_id) is True
    wifi = _by_kind(apartment["id"])["wifi"]
    assert guest_guide.delete_custom(apartment["id"], wifi["id"]) is False
    with pytest.raises(guest_guide.GuideError):
        guest_guide.add_custom(apartment["id"], "nowhere", "Hob")


def _finish_must_haves(apt_id):
    for kind in guest_guide.MUST_HAVE:
        item = _by_kind(apt_id)[kind]
        guest_guide.save(apt_id, item["id"], {"steps": f"How to {kind}"})


def test_guests_see_nothing_until_the_five_are_done(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    assert guest_guide.progress(apt)["live"] is False
    assert guest_guide.for_guest(apt, "everyone") == []
    _finish_must_haves(apt)
    assert guest_guide.progress(apt)["live"] is True
    assert guest_guide.for_guest(apt, "everyone")


def test_visibility_levels(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    _finish_must_haves(apt)
    items = _by_kind(apt)
    guest_guide.save(apt, items["wifi"]["id"], {"visibility": "booked"})
    guest_guide.save(apt, items["keys"]["id"], {"steps": "Spare key with cleaner", "visibility": "host"})
    public = {r["kind"] for r in guest_guide.for_guest(apt, "everyone")}
    booked = {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    assert "wifi" not in public and "wifi" in booked
    assert "keys" not in public and "keys" not in booked
    assert guest_guide.for_guest(apt, "host") == []


def test_drafts_and_skipped_cards_never_reach_guests(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    _finish_must_haves(apt)
    kinds = {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    assert "checkin" in kinds  # saved by the host, so confirmed
    guest_guide.add_kind(apt, "garage", source="booking")
    garage = _by_kind(apt)["garage"]
    db.execute("UPDATE guide_item SET steps = 'Remote in drawer', state = 'check' WHERE id = ?", (garage["id"],))
    assert "garage" not in {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    guest_guide.skip(apt, garage["id"])
    guest_guide.skip(apt, garage["id"], skipped=False)
    assert _by_kind(apt)["garage"]["state"] == "check"
    assert "garage" not in {r["kind"] for r in guest_guide.for_guest(apt, "booked")}
    guest_guide.skip(apt, _by_kind(apt)["trash"]["id"])
    progress = guest_guide.progress(apt)
    assert progress["check"] == 1
    assert progress["total"] == len(_by_kind(apt)) - 1
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_guide.py -q --tb=short -x 2>&1 | tail -30`. Expected: 9 passed.

## 5. Do not touch

`App/app/db.py` (`SCHEMA`, `ADDED_COLUMNS`), every existing migration, every template, route and i18n file. Hard rules 2, 3 and 5 of AGENTS.md apply. No new dependency.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_guide.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 failed.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: `context lint: OK`.

## 7. Acceptance

- [ ] The three files exist with the content above, and `git diff --stat main` lists only them (plus the report).
- [ ] `tests/test_guest_guide.py`: 9 passed.
- [ ] `tests/test_migrations.py` and `tests/test_db_*.py` pass.
- [ ] Context lint OK.

## 8. Stop and ask

Stop, and write the report, if:

- `0013_*` already exists in `App/app/migrations/`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0341-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/migrations/0013_guest_guide.sql` (HIGH RISK: migration; read the full diff).
- `App/app/guest_guide.py`: `for_guest` is the only gate between host-only or draft text and guests. `skip(..., skipped=False)` must not turn imported text into `done` (Fable review 2026-10-24).

## Owner steps

1. Review and merge the PR once CI is green.
2. No deploy step is needed on its own. The tables are created on the next normal deploy, and nothing uses them until 0342.
