# 0976: Guide audience verification (B18 / L03)

Status: todo
Depends on: B08 (merged) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: task/0976-audience-verification
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Establish, from code and from a synthetic run, what default the Keys and getting in card editor shows under "Who can read this?" and who can really read the card through the QR/public door and the booked-guest door. This is verification only: no production behaviour changes, no access is broadened, no real code is published, and no leak is claimed unless the run reproduces one.

## 2. Context

Rules that apply (AGENTS.md, rules.md): privacy first; guest pages need the browser tests with 0 skipped; the repo is public, so never commit real codes or guest data; use only the synthetic text below.

Finding L03 (review report): the empty Keys editor showed "Everyone with the QR code" with helper text saying codes belong to booked guests. Evidence class: Opportunity, not a proven exposure.

Reading result from the orchestrator (the executor must confirm each anchor; if an anchor is not found verbatim, STOP, section 8):

| # | File | Anchor (verbatim) | Meaning |
|---|---|---|---|
| A1 | App/app/migrations/0013_guest_guide.sql:22 | `visibility    TEXT NOT NULL DEFAULT 'everyone' CHECK (visibility IN ('everyone', 'booked', 'host'))` | Stored default of every card, Keys included |
| A2 | App/app/guest_guide.py `add_kind` | `INSERT INTO guide_item (apartment_id, topic, kind, source, sort_order, "` | No visibility column given, so A1 applies. `DEFAULT_KINDS` includes `"keys"` |
| A3 | App/app/guest_guide.py:84 | `VISIBILITY = ("everyone", "booked", "host")` | Option order in the select, so `everyone` is first |
| A4 | App/app/routes/guest_guide.py `guide_card` | `return _card(request, apartment, item, item, from_leon=...)` | Editor values are the stored row, so displayed default = stored value |
| A5 | App/app/templates/guest_guide_card.html:58 | `ui_select('guide-visibility', t('guest_guide.field.visibility'), visibility_options, selected=values.visibility, name='visibility', help=t('guest_guide.field.visibility_help'))` | The select sits after photos, location, steps, watch-out, video; just above Save |
| A6 | App/app/guest_guide.py `_LEVELS` | `"everyone": ("everyone",),` and `"booked": ("everyone", "booked"),` | Authorization by level; `host` is in neither |
| A7 | App/app/guest_guide.py `for_guest` and App/app/guide_facts.py `for_guest` | `if not allowed or not guest_guide.progress(apartment_id)["live"]:` | Nothing shows until the guide is live; the facts variant also lets a not-yet-written card show its Quick answers (facts) at the card's own visibility |
| A8 | App/app/routes/guest_guide_view.py `qr_guide` | `request, lang, apartment, context, "everyone",` | QR door `/g/{token}` always uses level `everyone` |
| A9 | App/app/routes/guest_guide_view.py `booked_level` | `"booked" from the day before check-in through the checkout day, else "everyone"` | Stay door `/l/{token}/{reservation_id}/guide` gives `booked` only inside the window |
| A10 | App/app/routes/guest_guide.py:335 | `fields["visibility"] = form.get("visibility", item["visibility"])` | Save posts the select value; a form without the field keeps the stored value |
| A11 | App/app/host_i18n.py:9537 | `"guest_guide.field.visibility_help": "Codes and anything private should be for booked guests only."` | The only warning; separate text, not tied to the Keys card |

Orchestrator conclusion from reading (to be confirmed by the run): a fresh Keys card is stored as `everyone`, the editor shows `Everyone with the QR code`, and with that value the card is readable at the QR door once the guide is live. The displayed default therefore matches effective authorization. Whether any real property has a published code at `everyone` is data, not code, and is out of scope: do not look at real data.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_0976_audience_matrix.py | create | The read-only matrix test below (copy verbatim) |
| App/tests/test_0976_audience_browser.py | create | Chromium check, synthetic data only (step 5) |
| docs/tasks/0976-report.md | create | Report, 600 tokens at most |

No other file may change. No production file (App/app/) changes.

## 4. Steps

1. Branch `task/0976-audience-verification` from the base commit. Symlink the venv: `ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv` (ignored by git; never `git add` it).
2. Confirm A1 to A11 with one grep each (`grep -n '<anchor fragment>' <file> | head`). Record found / not found.
3. Create App/tests/test_0976_audience_matrix.py with exactly this content (it reuses the fixtures of test_guest_guide_view.py; synthetic text only):

```python
"""0976: read-only audience matrix for the Keys card. Asserts today's behaviour; changes none."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import guest_guide
from app.main import app
from tests.conftest import login_as
from tests.test_guest_guide_view import TOKEN, _cards, _go_live, _qr, _stay, ws  # noqa: F401

SYNTHETIC = "SYNTHETIC-0976 key box instruction"


def _selected(html: str) -> str:
    select = re.search(r'<select[^>]*name="visibility".*?</select>', html, re.S)
    assert select, "visibility select not found"
    chosen = re.search(r'<option[^>]*value="(\w+)"[^>]*selected', select.group(0)) or re.search(
        r'<option[^>]*selected[^>]*value="(\w+)"', select.group(0))
    return chosen.group(1) if chosen else "first-option"


def _levels(ws, visibility):
    """(editor default, QR sees it, booked-window stay sees it, outside-window stay sees it)."""
    cards = _go_live(ws["home"], keys={"steps": SYNTHETIC, "visibility": visibility})
    qr = ws["client"].get(f"/g/{_qr(ws)}?lang=en").text
    inside = ws["client"].get(f"/l/{TOKEN}/{_stay(ws['home'], 0)}/guide?lang=en").text
    outside = ws["client"].get(f"/l/{TOKEN}/{_stay(ws['home'], 30)}/guide?lang=en").text
    return SYNTHETIC in qr, SYNTHETIC in inside, SYNTHETIC in outside


def test_fresh_keys_card_default_is_stored_everyone_and_shown_selected(ws):
    keys = _cards(ws["home"])["keys"]
    assert keys["visibility"] == "everyone"  # migration 0013 column default; no code overrides it
    host = TestClient(app)
    assert login_as(host, "view-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    html = host.get(f"/apartments/{ws['home']}/guide/{keys['id']}?lang=en").text
    print("EDITOR_DEFAULT", _selected(html))
    assert _selected(html) in ("everyone", "first-option")  # record which in the report


@pytest.mark.parametrize("visibility,qr,inside,outside", [
    ("everyone", True, True, True),
    ("booked", False, True, False),
    ("host", False, False, False),
])
def test_keys_card_matrix(ws, visibility, qr, inside, outside):
    assert _levels(ws, visibility) == (qr, inside, outside)
```

4. Run it (section 6, command 1). Expected: 4 passed. The test prints `EDITOR_DEFAULT everyone` with `-s`. If any assertion fails, do not edit it: that is a finding, go to section 8.
5. Chromium check (decide pass or fail). In App/tests/test_0976_audience_browser.py reuse `live_server`, `browser`, `LAYOUT_JS` from tests/test_guest_browser_e2e.py, and the host-login approach found with `grep -n 'login' tests/test_host_geometry.py | head`. Seed as `_seed()` in tests/test_guest_guide_browser.py does (own apartment name `Audience 0976`, token `audience0976tok`, clean up in `finally`), then:
   a. Host, 390 px: open the Keys card editor of a fresh property. Record the selected option text of `#guide-visibility`. Screenshot `/tmp/ubyhost-b18/0976-editor-keys-default-390.png`.
   b. Save the Keys card with steps `SYNTHETIC-0976 key box instruction` and the select left untouched (this is the default path a host would take). Open `/g/audience0976tok?lang=en`: record whether the text is present. Screenshot `/tmp/ubyhost-b18/0976-qr-default-390.png`.
   c. Change the select to `Booked guests during their stay`, save. Open the QR door again: text absent. Open `/l/<token>/<reservation_id>/guide?lang=en` with a synthetic reservation whose dates include today: text present. Screenshots `0976-qr-booked-390.png` and `0976-stay-booked-390.png`.
   d. Pass = every observation equals the matrix in section 7; the layout checker reports no problems on both guest pages. Anything else = fail, report it, do not fix.
6. Describe each screenshot in the report in one line (what the page shows, which option is selected, whether the synthetic text is visible). Never use real instructions, codes or guest data.
7. Write the report. Commit only the three files in section 3 with message `0976 verification` and the trailer from section 9.

## 5. Do not touch

- Anything under App/app/ (templates, routes, guest_guide.py, migrations, i18n). The proposed default change is NOT in this brief.
- Existing tests. Real data, real tokens, production, any server. Push and merge (owner only).
- Do not broaden access, do not change any stored visibility, do not run the full suite.

## 6. Commands

From App/:

1. `.venv/bin/python -m pytest tests/test_0976_audience_matrix.py -q --tb=short -x 2>&1 | tail -30`
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b18 .venv/bin/python -m pytest tests/test_0976_audience_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
3. Test-map row "Guest guide": `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b18 .venv/bin/python -m pytest tests/test_guest_guide*.py tests/test_guide_qr.py tests/test_0976_audience_matrix.py -q --tb=short -x -rs 2>&1 | tail -30`
4. Test-map row "Guest pages": `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b18 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
5. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`
6. Before commit: `git status --short`, `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'` (only the synthetic test token strings may match).

## 7. Acceptance (matrix to copy into the report)

Expected rows for the Keys card, guide live, synthetic text. "Editor shows" is the selected option when the card is opened with that stored value; the first row is a brand-new card.

| Stored audience | Editor shows | QR/public door `/g/...` | Stay door inside window | Stay door outside window |
|---|---|---|---|---|
| everyone (fresh-card default) | Everyone with the QR code | readable | readable | readable |
| booked | Booked guests during their stay | hidden | readable | hidden |
| host | Only you | hidden | hidden | hidden |

- [ ] Command 1: 4 passed; EDITOR_DEFAULT recorded.
- [ ] Browser check passes with 0 skipped; four screenshots exist under /tmp/ubyhost-b18, each described.
- [ ] Commands 3 and 4 green with 0 skipped; lint green.
- [ ] Report states in one line: "displayed default matches effective authorization: yes/no", and "leak reproduced: yes/no". "Yes" to a leak only when a real third party path was shown to read a `host` or `booked` card without a booking (none is expected). A card stored as `everyone` readable at the QR door is the documented rule, not a leak.
- [ ] `git diff --stat main` shows only the three files; nothing under App/app/.

## 8. Stop and ask

Stop and write the report as `blocked` if: an anchor A1 to A11 is not found verbatim; a matrix cell differs from section 7 (report the cell, do not fix); a test fails twice; Chromium is missing (0-skipped rule); a file outside section 3 needs a change; you need real data, push, merge, secrets or deploy; 25 tool calls or about 50k tokens.

## 9. Report

Write `docs/tasks/0976-report.md` (600 tokens at most), set `Status: review`. Contents: files changed; anchors found (A1 to A11 as one line); the filled matrix; editor default recorded; screenshot descriptions; command outputs (last 5 lines each); deviations; questions. Commit trailer: `Co-authored-by: Codex <noreply@openai.com>`.

## Owner decision (separate from this brief; implement only after the verification report)

Proposed policy, NOT implemented here: private access cards (Keys and getting in first, then any card meant for codes) default to booked guests; the audience selector moves beside the content it protects (above the steps field, not below the video field); the choice is explicit at Save. Decisions the owner must make after reading the report:

1. Default for new access cards: `booked`. Which kinds count as access cards (keys, garage, checkin, wifi?).
2. Existing cards: leave untouched (recommended; a data change would silently narrow what QR guests see today) or offer a one-time host prompt. No silent change to published audiences.
3. "Explicit at Save": a required choice with no preselected option for new access cards, or a preselected `booked` with the choice visible beside the content.
4. Whether a single code-like pattern in the text should warn when `everyone` is chosen (privacy note: the text is processed on save only; no new dependency).
Then a new brief (0977) covers the change, with the public/booked authorization tests in this brief kept green.

## Risk list (for the reviewer)

App/tests/test_0976_audience_matrix.py (reuses private test helpers of test_guest_guide_view.py), App/tests/test_0976_audience_browser.py (synthetic seed cleanup).

## Owner steps

None for this brief. After review: read the report, answer the four decisions above.
