# 0299: Review drafted cards (source line, discard)

Status: todo
Depends on: 0298 merged | Base commit: after 0298 | Branch: task/0299-guide-drafts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On a drafted card ("Check this"), tell the host where the text came from (Booking.com, Airbnb, their old notes) and let them throw the draft away with one button, so they write the card themselves. Saving a draft already confirms it (0292). After the one import per listing, the host fills the rest by hand (owner, 2026-10-24); this brief makes that hand-over clear ([plan](../plans/guest-guide.md)).

## 2. Context

- A draft is `guide_item.state = 'check'` with `source` `booking`, `airbnb` (0298) or `legacy` (0291). Guests never see it.
- Discard clears the text fields, sets `state = 'missing'` and `source = 'host'`. A later import of the other listing may fill a `missing` card again (0298 rule); that is intended.
- `ui_banner` prints its text unescaped, so it only ever gets translated copy, never card text.
- No paste box: dropped from the plan to keep AI cost down (owner prefers the form after the import).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/guest_guide.py` | edit | `discard_draft` |
| `App/app/routes/guest_guide.py` | edit | `POST .../discard` |
| `App/app/templates/guest_guide_card.html` | edit | Source line, discard button |
| `App/app/host_i18n.py` | edit | `_GUIDE_DRAFT_STRINGS` |
| `App/tests/test_guide_drafts.py` | create | Tests |

No other file may change.

## 4. Steps

1. In `App/app/guest_guide.py`, directly before the line `def add_custom(apartment_id: int, topic: str, title: str) -> int:`, insert (followed by two blank lines):

```python
def discard_draft(apartment_id: int, item_id: int) -> bool:
    """Throw away text the host did not write (an import or the old notes); the card
    goes back to "Missing". Only for drafts; True when something was discarded."""
    item = get(apartment_id, item_id)
    if not item or item["state"] != "check":
        return False
    db.update("guide_item", item_id, {
        "location": "", "steps": "", "watch_out": "", "video_url": "",
        "state": "missing", "source": "host", "updated_at": db.utcnow(),
    })
    return True
```

2. In `App/app/routes/guest_guide.py`, directly before the line `@router.post("/apartments/{apartment_id}/guide/{item_id}/skip")`, insert (followed by two blank lines):

```python
@router.post("/apartments/{apartment_id}/guide/{item_id}/discard")
def guide_card_discard(request: Request, apartment_id: int, item_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _home(request, apartment_id)
    if not guest_guide.discard_draft(apartment_id, item_id):
        raise HTTPException(404)
    return back(f"{_base(apartment_id)}/{item_id}", msg=flash(request, "flash.guest_guide.discarded"))
```

3. In `App/app/templates/guest_guide_card.html`, replace the line

```html
{% if item.state == 'check' %}{{ ui_banner('attention', t('guest_guide.check_banner')) }}{% endif %}
```

with

```html
{% if item.state == 'check' %}{{ ui_banner('attention', t('guest_guide.draft_from.' ~ (item.source if item.source in ('booking', 'airbnb', 'legacy') else 'other')) ~ ' ' ~ t('guest_guide.check_banner')) }}{% endif %}
```

4. In the same file, inside the `card-more` section, directly before the line `{% if custom %}` that opens the delete form, insert:

```html
{% if item.state == 'check' %}
<form method="post" action="{{ base_url }}/{{ item.id }}/discard" data-confirm data-confirm-message="{{ t('guest_guide.discard_confirm') }}">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{{ ui_button(t('guest_guide.discard'), 'secondary', type='submit') }}
</form>
{% endif %}
```

5. In `App/app/host_i18n.py`, find (once):

```python
for _lang, _strings in _GUIDE_IMPORT_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Directly after them, insert one blank line and:

```python
# 0299: reviewing drafts on the card editor.
_GUIDE_DRAFT_STRINGS = {
    "en": {
        "guest_guide.draft_from.booking": "From your Booking.com listing.",
        "guest_guide.draft_from.airbnb": "From your Airbnb listing.",
        "guest_guide.draft_from.legacy": "From your old check-in notes in UbyHost.",
        "guest_guide.draft_from.other": "Drafted by UbyHost.",
        "guest_guide.discard": "Discard this draft",
        "guest_guide.discard_confirm": "Discard the drafted text? The card goes back to Missing and you can write it yourself.",
        "flash.guest_guide.discarded": "Draft discarded. Write the card in your own words.",
    },
    "cs": {
        "guest_guide.draft_from.booking": "Z vaší nabídky na Booking.com.",
        "guest_guide.draft_from.airbnb": "Z vaší nabídky na Airbnb.",
        "guest_guide.draft_from.legacy": "Z vašich starších poznámek k příjezdu v UbyHost.",
        "guest_guide.draft_from.other": "Připravil UbyHost.",
        "guest_guide.discard": "Zahodit tento návrh",
        "guest_guide.discard_confirm": "Zahodit navržený text? Karta se vrátí mezi chybějící a napíšete ji sami.",
        "flash.guest_guide.discarded": "Návrh zahozen. Napište kartu vlastními slovy.",
    },
}

for _lang, _strings in _GUIDE_DRAFT_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

6. Create `App/tests/test_guide_drafts.py`:

```python
"""0299: reviewing drafted cards on the card editor."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, guest_guide
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "drafts.sqlite3")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("draft-owner@example.test", "Draft owner", username="draft-owner", role="host")
    other = auth.create_account("draft-other@example.test", "Other owner", username="draft-other", role="host")
    now = db.utcnow()

    def home(name, user):
        apt_id = db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        return apt_id
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "draft-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"home": mine, "foreign": foreign, "client": client}


def _draft(apt_id, kind="wifi", source="airbnb"):
    item = {r["kind"]: r for r in guest_guide.items(apt_id)}[kind]
    db.execute(
        "UPDATE guide_item SET steps = 'Network Vivus, password on the router', state = 'check', source = ? "
        "WHERE id = ?", (source, item["id"]),
    )
    return item["id"]


def test_draft_shows_where_it_came_from_and_can_be_discarded(ws):
    item_id = _draft(ws["home"])
    client = ws["client"]
    page = client.get(f"/apartments/{ws['home']}/guide/{item_id}").text
    assert "From your Airbnb listing." in page and "Discard this draft" in page
    response = client.post(f"/apartments/{ws['home']}/guide/{item_id}/discard", follow_redirects=False)
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    item = guest_guide.get(ws["home"], item_id)
    assert (item["state"], item["steps"], item["source"]) == ("missing", "", "host")


def test_saving_a_draft_confirms_it(ws):
    item_id = _draft(ws["home"], source="booking")
    ws["client"].post(
        f"/apartments/{ws['home']}/guide/{item_id}",
        data={"steps": "Network Vivus, password on the router", "visibility": "booked"},
    )
    item = guest_guide.get(ws["home"], item_id)
    assert (item["state"], item["source"]) == ("done", "host")


def test_only_drafts_can_be_discarded(ws):
    client = ws["client"]
    wifi = {r["kind"]: r for r in guest_guide.items(ws["home"])}["wifi"]
    guest_guide.save(ws["home"], wifi["id"], {"steps": "Host wrote this"})
    assert client.post(f"/apartments/{ws['home']}/guide/{wifi['id']}/discard").status_code == 404
    assert guest_guide.get(ws["home"], wifi["id"])["steps"] == "Host wrote this"
    assert "Discard this draft" not in client.get(f"/apartments/{ws['home']}/guide/{wifi['id']}").text


def test_another_hosts_draft_is_out_of_reach(ws):
    theirs = _draft(ws["foreign"])
    client = ws["client"]
    assert client.post(f"/apartments/{ws['foreign']}/guide/{theirs}/discard").status_code == 404
    assert client.post(f"/apartments/{ws['home']}/guide/{theirs}/discard").status_code == 404
    assert guest_guide.get(ws["foreign"], theirs)["state"] == "check"


def test_czech_draft_line(ws):
    item_id = _draft(ws["home"], source="legacy")
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{item_id}?lang=cs").text
    assert "Z vašich starších poznámek k příjezdu v UbyHost." in page and "Zahodit tento návrh" in page
```

## 5. Do not touch

Everything else, including `guest_guide_merge.py`, `guest_guide_import.py` and CSS. No new class.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guide_drafts.py tests/test_guest_guide*.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.
- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30`. Expected: 0 failed.

From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: both OK.

## 7. Acceptance

- [ ] Only the five files of §3 change (plus the report).
- [ ] `test_guide_drafts.py`: 5 passed; the other rows pass.
- [ ] Both lints OK.

## 8. Stop and ask

Stop, and write the report, if: 0298 is not merged; an anchor is not found exactly once; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0299-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `discard_draft` refuses anything but `check`, so host-written text can never be wiped by it; ownership through `_home` and `get`.

## Owner steps

1. Review and merge once CI is green.

