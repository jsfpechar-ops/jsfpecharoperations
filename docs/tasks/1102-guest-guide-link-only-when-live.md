# 1102: guest stay page, show the guide link only when the guide is live, and below registration

Status: blocked
Depends on: none | Base commit: origin/main | Branch: task/1102-guide-link-when-live
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Owner Josef agreed to this fix. Brief by Sonnet 5.5, 2026-11-11.

## 1. Objective

On the guest stay page the "Your guide" link shows even when the host's guide is not live, and it opens a dead end ("This guide is not ready yet"). It also sits above the one task the guest must do (add a person). Show the link only when the guide is live, and move it below the registration block.

## 2. Context

Rules: guest pages ([rules](../context/rules.md#guest-pages)): browser and geometry tests with 0 skipped; UX gate (AGENTS rule 10); no copy change, no new dependency, no CSS change unless spacing breaks.

`guest_guide.progress(apartment_id)["live"]` is True only when the five `MUST_HAVE` cards in `App/app/guest_guide.py` are done or skipped. `App/app/routes/guest_guide_view.py` line 109 computes it the same way: `live = guest_guide.progress(apartment["id"])["live"]`.

Excerpt A, `App/app/templates/guest/stay.html` lines 14 to 18:

```
<a class="g-card g-guide-link" href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}" data-guide-link>{{ t('guide_title') }}</a>

{# Fixed vertical order: (1) status, (2) the one next action, (3) money —
   the invoice link, when there is one — (4) your records, (5) the host
   footer. #}
```

Excerpt B, the end of the same file (lines 155 to 160):

```
  {% for person in people if not person.mine %}
    <div class="g-card g-summary g-summary-row">{{ t('person') }} {{ person.index }} &middot; {% if person.complete %}{{ t('summary_fold_saved') }} <span aria-hidden="true">{{ icon('check', 14) }}</span>{% else %}{{ t('not_filled') }}{% endif %}</div>
  {% endfor %}
{% endif %}

{% endblock %}
```

Excerpt C, `App/app/routes/guest.py` line 31 (the import line, one long line; its middle reads `... guest_slug, guest_uk_i18n, guest_draft, headcount, ...`) and lines 1553 to 1556:

```
            "door_code": door_codes.view(reservation, apartment),
        }
    )
    context["fee_panel"] = (
```

Excerpt D, `App/tests/test_guest_guide_view.py` lines 219 to 222 (stays valid; do not change it):

```
def test_the_stay_page_links_to_the_guide():
    stay = (TEMPLATES / "stay.html").read_text(encoding="utf-8")
    assert 'href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}"' in stay
    assert "t('guide_title')" in stay
```

That is the only test that mentions the guide link on the stay page (`grep -rn "data-guide-link\|g-guide-link" App/tests` finds nothing else). The new link markup keeps the same href text, so it keeps passing.

Helpers already in `App/tests/test_guest_guide_view.py`: fixture `ws` (apartment `ws["home"]` with token `TOKEN`, mail off, PIN off), `_go_live(apt_id)` (fills the five must-have cards, asserts live), `_stay(apt_id, start_in_days)` (returns a reservation id). The guide-not-live state is the fixture default.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | import `guest_guide`; add `guide_live` to the stay context |
| `App/app/templates/guest/stay.html` | edit | remove link from the top; add it, guarded, at the end; update the order comment |
| `App/tests/test_guest_guide_view.py` | edit | add three tests after Excerpt D |

No other file may change. No CSS change, no `?v=` bump (no CSS or JS file changes).

## 4. Steps

1. `App/app/routes/guest.py`, import line 31: insert `guest_guide, ` right after `guest_draft, `. Command: `grep -n "guest_draft, guest_guide, headcount" App/app/routes/guest.py | cut -c1-40`. Expect one hit.

2. `App/app/routes/guest.py`, directly above the `def` that holds Excerpt C's `context = _shared(...)` (the stay hub route function ending at line 1577 with `render_guest(request, "guest/stay.html", context)`), add this helper at module level, one blank line pair before the `@router.get` decorator of that route. Find the decorator with `grep -n 'render_guest(request, "guest/stay.html"' App/app/routes/guest.py` then read 60 lines above it for the `@router.get(` line. Helper:

```python
def _guide_is_live(apartment_id: int) -> bool:
    """1102: the guide link is shown only once the host's guide is live; never break the stay page over it."""
    try:
        return bool(guest_guide.progress(apartment_id)["live"])
    except Exception:  # noqa: BLE001 - a guide hiccup hides the link, nothing more
        return False
```

3. Same file, Excerpt C: add one key to the context dict.

```diff
             "door_code": door_codes.view(reservation, apartment),
+            "guide_live": _guide_is_live(apartment["id"]),
         }
     )
```

Command: `grep -n "guide_live\|_guide_is_live" App/app/routes/guest.py | tail -30`. Expect 3 lines (helper def, dict key, and none else). If `import guest_guide` raises a circular import in step 8, stop (section 8).

4. `App/app/templates/guest/stay.html`: delete Excerpt A's link line and the blank line after it, and rewrite the comment so lines 14 to 16 become:

```diff
-<a class="g-card g-guide-link" href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}" data-guide-link>{{ t('guide_title') }}</a>
-
 {# Fixed vertical order: (1) status, (2) the one next action, (3) money —
-   the invoice link, when there is one — (4) your records, (5) the host
-   footer. #}
+   the invoice link, when there is one — (4) your records, (5) the guide
+   link, only while the guide is live, (6) the host footer. #}
```

5. Same file, Excerpt B: insert the guarded link after the closing `{% endif %}` of the people block and before `{% endblock %}`.

```diff
   {% endfor %}
 {% endif %}
 
+{% if guide_live %}
+  <a class="g-card g-guide-link" href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}" data-guide-link>{{ t('guide_title') }}</a>
+{% endif %}
+
 {% endblock %}
```

Command: `grep -n "data-guide-link\|guide_live" App/app/templates/guest/stay.html`. Expect exactly 2 lines, both near the end of the file.

6. `App/tests/test_guest_guide_view.py`: after Excerpt D (before the `# --- photos` rule line) add:

```python
def _hub_html(ws, lang="en"):
    """The stay page with one guest on it (a stay with no guest redirects to the form)."""
    reservation_id = _stay(ws["home"], 0)
    now = db.utcnow()
    db.insert("guest", {
        "reservation_id": reservation_id, "is_lead": 1, "first_name": "Ada", "surname": "Guest",
        "created_at": now, "updated_at": now,
    })
    response = ws["client"].get(f"/l/{TOKEN}/{reservation_id}?lang={lang}")
    assert response.status_code == 200
    return response.text


def test_the_stay_page_hides_the_guide_link_until_live(ws):
    html = _hub_html(ws)
    assert "data-guide-link" not in html
    assert "/guide?lang=" not in html


def test_the_stay_page_shows_the_guide_link_once_live(ws):
    _go_live(ws["home"])
    html = _hub_html(ws)
    assert html.count("data-guide-link") == 1
    assert "/guide?lang=en" in html


def test_the_guide_link_comes_after_the_registration_block(ws):
    _go_live(ws["home"])
    html = _hub_html(ws)
    # g-summary-row is the guest line of the registration block; the link follows it.
    assert "g-summary-row" in html
    assert html.index("g-summary-row") < html.index("data-guide-link")
    stay = (TEMPLATES / "stay.html").read_text(encoding="utf-8")
    assert "{% if guide_live %}" in stay
    assert stay.index("{% if guide_live %}") > stay.index("{{ t('add_person') }}")
```

Command: `cd App && .venv/bin/python -m pytest tests/test_guest_guide_view.py -q --tb=short -x 2>&1 | tail -30`. Expect all pass. If `/l/{TOKEN}/{id}` redirects or the guest row is rejected (status not 200, or `g-summary-row` missing), read the response for the reason ONCE and adjust only the test helper (for example add `"submit_state": "pending"` or `"birth_date": "1990-02-03"` as `test_0520_overview_today.py::_guest` does); a second failure means stop (section 8).

7. Guest and layout tests, from `App/`, one command each (test-map row "Guest pages, guest templates" and "Guest guide"):

```
.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short 2>&1 | tail -30
```

Expected: green, and the second run shows 0 skipped (`-rs` lists none). A skip means Playwright is missing: run `.cursor/install.sh`, then repeat.

8. Screenshots. Start the app the way `docs/context/workflow.md#ux-gate` says (grep that heading, read at most 40 lines). Open the stay page of a stay that has one guest, once with the guide not live and once with it live (fill the five must-have cards via `guest_guide.save`, as `_go_live` does). Take the live-state screenshot at 390, 768 and 1280 px. Take the not-live screenshot at 390 px. Save them under `docs/tasks/screenshots-1102/`. Look at each. Expected: live state shows the link card under the guest rows with normal card spacing; not-live state shows no link and no empty gap. If the card touches the previous card (no gap), reuse the existing spacing of `.g-summary-row` cards, do not add a new class: stop and report instead of editing CSS (CSS is not in section 3).

9. Open the PR as a draft, body: per page (stay page) what you saw at 390, 768 and 1280, the ticked [design-system checklist](../design/design-system.md), and the reason line "no new outbound request". End the body with the attribution lines the session gives.

## 5. Do not touch

`App/app/static/*.css`, `base.html`, `guest_guide.py`, `guest_guide_view.py`, i18n strings (no copy change), `App/app/routes/` files other than `guest.py`, any host template. Hard rules: light mode only; no new dependency; never push to `main`; never merge (owner uses `scripts/merge-pr-on-green.sh`).

## 6. Commands

All from `App/`, each ends `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_guest_guide_view.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs` (0 skipped)
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] `grep -n "data-guide-link" App/app/templates/guest/stay.html` shows one line, inside `{% if guide_live %}`, after the people block.
- [ ] The three new tests and the old `test_the_stay_page_links_to_the_guide` pass.
- [ ] Guest-page tests, browser e2e and geometry tests green with 0 skipped; `test_layout_lint_browser.py` green.
- [ ] 390 px screenshots (live and not live) and 768 and 1280 px screenshots (live) of the stay page exist and were looked at; the PR body says per page what was seen.
- [ ] `git diff --stat` lists only the three files in section 3 (plus the screenshots and the report).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found verbatim;
- `import guest_guide` in `guest.py` raises a circular import;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- spacing breaks after the move (CSS is outside section 3);
- a file outside section 3 needs a change.

## 9. Report

Write `docs/tasks/1102-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of output, section 7 ticked, deviations, questions.

## Risk list (for the reviewer)

`App/app/routes/guest.py` (the helper and context key), `App/app/templates/guest/stay.html` (guard and position).

## Owner steps

1. Open the pull request when it is marked ready.
2. Merge it with `scripts/merge-pr-on-green.sh`. Nothing else.
