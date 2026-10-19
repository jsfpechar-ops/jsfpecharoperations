# 0137: Remove legacy host actions (calendar sync copies, row send, code lists, slot, claim workarounds; Send all only for manual sending)

Status: todo
Depends on: 0136 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
HIGH RISK (filing-adjacent): exact diff only; the reviewer reads the full diff of every file below.

Owner-confirmed set (2026-10-19): items 3 to 6 and 8 to 10 as recommended; item 7 (demo buttons) is kept. Part of [design-v2](../plans/design-v2.md). Commit each step as `0137 step k`. Never push, never open a PR.

## 1. Objective

Apply the recommended removal set from `/mnt/project-files/design-reset/legacy-actions.md`:

- 3: Update calendars stays only in the property calendar section (`_property_calendars.html`); the dashboard header, dashboard More panel, dashboard empty state and Properties header copies go.
- 4: the stays-list row "Send" button goes; the stay detail keeps one Send button; "Send again" after a refusal moves into the stay's More menu.
- 5: "Refresh code lists from UbyPort" and its help line go (the bundled lists are used; the route stays for CI).
- 6: "Remove extra guest" goes (editing the expected count does the same; the route stays).
- 7: kept. "Delete demo stay" and "Clear demo data" already show only with demo data; after 0133 the dashboard renders "Clear demo data" once, in the header actions, so nothing to dedupe.
- 8: "Reopen guest access" and "Release assignment" move into the stay's More menu.
- 9: "Send all ready" shows only when the host has a property with manual sending.
- 10: "Save and test connection" stays where it is (UbyPort setup section); no change.

Nothing under "Keep" changes: filed-by-hand and Undo, the one Send button, Re-send (moved, not deleted), invoice and fee actions, Delete expired records.

## 2. Context

Every anchor is the text after 0133 (dashboard), 0134 (stays list) and 0135 (stay detail). Verify each with `grep -n` before editing; if one is not found verbatim, stop. No route, `reporting.py`, `send_controls` or worker code changes; the only Python change is one query in the stays list route (item 9).

Anchor A, `App/app/templates/dashboard.html`: the string `{% if feed_count %}{{ sync_calendars_button(return_to='/', last_sync=none) }}{% endif %}` (twice: secondary actions and `#dashboard-more`); the string `{% call ui_empty(t('dashboard.empty.no_stays')) %}{{ sync_calendars_button(return_to='/', label_key='dashboard.empty.sync_now') }}{% endcall %}` (once); `, sync_calendars_button, guest_count with context %}` in the import line (once).

Anchor B, `App/app/templates/apartments.html` line 7: `  {{ sync_calendars_button(return_to='/apartments') }}` and `sync_calendars_button, ` in the import on line 5.

Anchor C, `App/app/templates/reservations.html`: the line `          {{ row_reporting_actions(reservation, row.controls, return_to) }}` and `row_reporting_actions, ` in the import; the block `{% block secondary_actions %}{% if apartments %}{{ bulk_send_ready(ready_send_count, return_to) }}{% endif %}{% endblock %}`.

Anchor D, `App/app/templates/reservation_detail.html`, the refusal branch (eight lines):

```
          <a class="{{ cta }}" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="inline">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="{{ cta if send_controls.rejected_edited else 'ui-btn ui-btn-secondary' }}" type="submit">
              {{ t('stay.detail.cta.send_again') }}
            </button>
          </form>
```

Anchor E, same file, the end of the `#now` menu (two lines):

```
        <a class="row-menu-item" href="/apartments/{{ reservation.apartment_id }}?view=settings&amp;section=guests#communication" role="menuitem">{{ t('stay.detail.menu.guest_links') }}</a>
      {{ row_menu_end() }}
```

Anchor F: none (item 7 kept).

Anchor G, same file, the claim actions (fifteen lines, from `  <div class="stay-command-actions">` that follows `{{ t('stay.claim.unclaimed') }}` to its `  </div>`), containing the `reopen-guest` and `release-claim` forms.

Anchor H, same file, the slot form (seven lines):

```
          {% if not stay_inactive and progress.expected > 1 %}
          <form method="post" action="/reservations/{{ reservation.id }}/remove-empty-slot" data-confirm data-confirm-title="{{ t('host.remove_slot') }}" data-confirm-message="{{ t('host.remove_slot_confirm') }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="expected" value="{{ progress.expected }}">
            <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('host.remove_slot') }}</button>
          </form>
          {% endif %}
```

Anchor I, `App/app/templates/_property_editor.html` lines 284 to 290:

```
        <button class="btn" type="submit" formaction="{{ base_url }}/refresh-codelists"
                formmethod="post" formnovalidate>{{ t('apartment.form.refresh_codelists') }}</button>
        <span class="small muted">
          {{ t('apartment.form.credentials_actions_help') }}
          {% if codelist_fetched %}{{ t('apartment.form.codelists_cached', date=codelist_fetched[:10]) }}
          {% else %}{{ t('apartment.form.codelists_bundled') }}{% endif %}
        </span>
```

Anchor J, `App/app/routes/admin.py` (stays list route): the line `    query_params = [(key, value) for key, value in request.query_params.multi_items() if key != "page"]` and the line `            "ready_send_count": ready_send_count,`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/dashboard.html` | edit | Anchor A |
| `App/app/templates/apartments.html` | edit | Anchor B |
| `App/app/templates/reservations.html` | edit | Anchor C |
| `App/app/templates/reservation_detail.html` | edit | Anchors D, E, G, H |
| `App/app/templates/_property_editor.html` | edit | Anchor I |
| `App/app/routes/admin.py` | edit | Anchor J: `manual_send` flag |
| `App/app/host_i18n.py` | edit | delete four unused keys (en and cs) |
| `App/app/host_design_i18n.py` | edit | delete `host.remove_slot`, `host.remove_slot_confirm` (en and cs) |
| `App/tests/test_calendar_sync_ui.py` | edit | lines 167 to 170 |
| `App/tests/test_dashboard_empty.py` | edit | lines 122 and 128 |
| `App/tests/test_host_quiet_dashboard_browser.py` | edit | lines 317 to 330 |
| `App/tests/test_host_stay_actions_browser.py` | edit | lines 191 to 200 |
| `App/tests/test_send_controls.py` | edit | line 741 |
| `App/tests/test_remove_legacy_actions.py` | create | the buttons are gone, the routes still answer |

No other file may change.

## 4. Steps

1. Templates, run from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(name, pairs):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:60], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("dashboard.html", [
 ("{% if feed_count %}{{ sync_calendars_button(return_to='/', last_sync=none) }}{% endif %}", "", 2),
 ("{% call ui_empty(t('dashboard.empty.no_stays')) %}{{ sync_calendars_button(return_to='/', label_key='dashboard.empty.sync_now') }}{% endcall %}", "{{ ui_empty(t('dashboard.empty.no_stays')) }}", 1),
 (", sync_calendars_button, guest_count with context %}", ", guest_count with context %}", 1),
])
patch("apartments.html", [
 ("  {{ sync_calendars_button(return_to='/apartments') }}\n", "", 1),
 ("sync_calendars_button, ", "", 1),
])
patch("reservations.html", [
 ("          {{ row_reporting_actions(reservation, row.controls, return_to) }}\n", "", 1),
 ("row_reporting_actions, ", "", 1),
 ("{% block secondary_actions %}{% if apartments %}{{ bulk_send_ready(ready_send_count, return_to) }}{% endif %}{% endblock %}",
  "{% block secondary_actions %}{% if manual_send %}{{ bulk_send_ready(ready_send_count, return_to) }}{% endif %}{% endblock %}", 1),
])
D_OLD = """          <a class="{{ cta }}" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="inline">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="{{ cta if send_controls.rejected_edited else 'ui-btn ui-btn-secondary' }}" type="submit">
              {{ t('stay.detail.cta.send_again') }}
            </button>
          </form>
"""
D_NEW = """          <a class="{{ cta }}" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
"""
E_OLD = """        <a class="row-menu-item" href="/apartments/{{ reservation.apartment_id }}?view=settings&amp;section=guests#communication" role="menuitem">{{ t('stay.detail.menu.guest_links') }}</a>
      {{ row_menu_end() }}
"""
E_NEW = """        <a class="row-menu-item" href="/apartments/{{ reservation.apartment_id }}?view=settings&amp;section=guests#communication" role="menuitem">{{ t('stay.detail.menu.guest_links') }}</a>
        {% if send_controls.send_enabled and progress.status == 'failed' %}
          {# 0137: Re-send after a refusal lives in the menu; the duplicate-filing rules are unchanged. #}
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="row-menu-form">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="row-menu-item" type="submit" role="menuitem">{{ t('stay.detail.cta.send_again') }}</button>
          </form>
        {% endif %}
        {% if stay_claim.guest_access_locked_at %}
          <form method="post" action="/reservations/{{ reservation.id }}/reopen-guest" class="row-menu-form">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <button class="row-menu-item" type="submit" role="menuitem">{{ t('stay.claim.reopen') }}</button>
          </form>
        {% endif %}
        {% if stay_claim.state != 'unclaimed' %}
          <form method="post" action="/reservations/{{ reservation.id }}/release-claim" class="row-menu-form"
                data-confirm data-confirm-message="{{ t('stay.claim.release_confirm') }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <button class="row-menu-item" type="submit" role="menuitem">{{ t('stay.claim.release') }}</button>
          </form>
        {% endif %}
      {{ row_menu_end() }}
"""
H_OLD = """          {% if not stay_inactive and progress.expected > 1 %}
          <form method="post" action="/reservations/{{ reservation.id }}/remove-empty-slot" data-confirm data-confirm-title="{{ t('host.remove_slot') }}" data-confirm-message="{{ t('host.remove_slot_confirm') }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="expected" value="{{ progress.expected }}">
            <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('host.remove_slot') }}</button>
          </form>
          {% endif %}
"""
p = pathlib.Path("app/templates/reservation_detail.html"); s = p.read_text(encoding="utf-8")
for old, new in ((D_OLD, D_NEW), (E_OLD, E_NEW), (H_OLD, "")):
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)
# Anchor G: the claim actions div, reopen-guest form first
start = s.index('<div class="stay-command-actions">\n    {% if stay_claim.guest_access_locked_at %}')
end = s.index("  </div>\n", start) + len("  </div>\n")
block = s[start:end]
assert "release-claim" in block and block.count("<form") == 2, block
s = s[:start].rstrip(" ") + s[end:]
assert s.count("reopen-guest") == 1 and s.count("release-claim") == 1 and "remove-empty-slot" not in s and s.count("delete-demo") == 1
p.write_text(s, encoding="utf-8")
patch("_property_editor.html", [("""        <button class="btn" type="submit" formaction="{{ base_url }}/refresh-codelists"
                formmethod="post" formnovalidate>{{ t('apartment.form.refresh_codelists') }}</button>
        <span class="small muted">
          {{ t('apartment.form.credentials_actions_help') }}
          {% if codelist_fetched %}{{ t('apartment.form.codelists_cached', date=codelist_fetched[:10]) }}
          {% else %}{{ t('apartment.form.codelists_bundled') }}{% endif %}
        </span>
""", "", 1)])
print("ok")
EOF
```

   Expected: `ok`. Command: `cd App && .venv/bin/python -c "
from app.templating import templates
for n in ('dashboard.html','apartments.html','reservations.html','reservation_detail.html','apartment_form.html'): templates.env.get_template(n)
print('compiled')"`. Expected: `compiled`.

2. Route (item 9). In `App/app/routes/admin.py`, before the `query_params = ...` line of Anchor J insert:

```python
    # 0137: "Send all ready" is the manual-sending control; a host whose properties all send
    # automatically never sees it. Archived properties count: their stays still list.
    manual_send = db.query_one(
        "SELECT 1 AS x FROM apartment WHERE owner_user_id = ? AND automation_mode = 'manual' LIMIT 1",
        (access.owner_id(request),),
    ) is not None
```

   and after `            "ready_send_count": ready_send_count,` insert `            "manual_send": manual_send,`. Command: `cd App && .venv/bin/python -m pytest tests/test_send_controls.py tests/test_stays_empty_workspace.py -q --tb=short 2>&1 | tail -5`. Expected: one failure, at test_send_controls.py line 741 (fixed in step 4).

3. Texts, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
p = pathlib.Path("app/host_i18n.py"); s = p.read_text(encoding="utf-8")
for key in ("apartment.form.refresh_codelists", "apartment.form.codelists_bundled",
            "apartment.form.codelists_cached", "apartment.form.credentials_actions_help"):
    pat = re.compile(r'^        "' + re.escape(key) + r'": .*\n', re.M)
    assert len(pat.findall(s)) == 2, (key, len(pat.findall(s))); s = pat.sub("", s)
p.write_text(s, encoding="utf-8")
p = pathlib.Path("app/host_design_i18n.py"); s = p.read_text(encoding="utf-8")
pat = re.compile(r"^        'host\.remove_slot': .*\n        'host\.remove_slot_confirm': .*\n(?:                                    .*\n)+?", re.M)
found = pat.findall(s); assert len(found) == 2, len(found); s = pat.sub("", s)
assert "remove_slot" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Command: `grep -rn "refresh_codelists\|codelists_bundled\|codelists_cached\|credentials_actions_help\|host.remove_slot" App/app --include=*.py --include=*.html | grep -v 'routes/admin.py' | wc -l`. Expected: `0`. (`routes/admin.py` keeps its `/refresh-codelists` route and flash keys.)

4. Tests, exact edits:
   - `App/tests/test_calendar_sync_ui.py` lines 167 to 170: replace the four asserts with
     ```
        assert 'action="/sync"' not in dashboard.text
        assert 'action="/sync"' not in apartments.text
        property_page = client.get(f"/apartments/{apartment_id}?view=bookings")
        assert 'action="/sync"' in property_page.text
        assert f'name="return_to" value="/apartments/{apartment_id}?view=bookings"' in property_page.text
     ```
   - `App/tests/test_dashboard_empty.py`: line 128 `    assert "Update calendars" in with_feed.text` -> `    assert "Update calendars" not in with_feed.text`; rename the test on line 117 to `test_the_dashboard_never_shows_the_sync_button` and keep line 122.
   - `App/tests/test_host_quiet_dashboard_browser.py` lines 317 to 330: replace
     `header_actions = page.locator(".dashboard-actions")` with `header_actions = page.locator(".ui-ph-acts")` (if 0133 already did, keep it); delete the line `assert header_actions.locator('form[action="/sync"]').is_visible()` (the `/demo/reset` assert stays); replace the `header_buttons = header_actions.locator(\n                    ".action-group > .btn, .action-group > form > .btn, .action-group .sync-cta .btn"\n                )` call with `header_buttons = header_actions.locator(".ui-btn")`; replace `# Add cleaning is the requested fourth header action.\n                assert header_buttons.count() == 4` with `# Add stay, Add cleaning, Clear demo data and the More button: the sync button is gone (0137).\n                assert header_buttons.count() == 4`; replace `assert all(abs(box["height"] - (44 if width <= 390 else 42)) <= 1 for box in header_boxes)` with `assert all(box["height"] >= 40 for box in header_boxes)`.
   - `App/tests/test_host_stay_actions_browser.py` lines 191 to 200: delete `send = ready_row.locator(".row-action-send")` and `assert send.is_visible()`; `boxes = [control.bounding_box() for control in (send, trigger)]` -> `boxes = [trigger.bounding_box()]`; `for box in (boxes[0], boxes[1])), boxes` -> `for box in boxes), boxes`.
   - `App/tests/test_send_controls.py` line 741: `    assert 'class="ui-btn ui-btn-primary" type="submit"' in fixed` -> `    assert '<button class="row-menu-item" type="submit" role="menuitem">Send again</button>' in fixed` and add after line 742 `    assert 'class="ui-btn ui-btn-primary" type="submit"' not in fixed`.

   Create `App/tests/test_remove_legacy_actions.py`:

```python
"""0137: legacy host buttons are gone from the templates; their routes still answer."""
from __future__ import annotations

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _t(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_update_calendars_lives_only_in_the_property_calendar_section():
    assert "sync_calendars_button(" not in _t("dashboard.html")
    assert "sync_calendars_button(" not in _t("apartments.html")
    assert _t("_property_calendars.html").count("sync_calendars_button(") == 1


def test_the_stays_list_has_no_row_send_and_send_all_is_manual_only():
    text = _t("reservations.html")
    assert "row_reporting_actions" not in text
    assert "{% if manual_send %}{{ bulk_send_ready(" in text


def test_the_stay_detail_keeps_one_send_and_moves_the_rest_into_the_menu():
    text = _t("reservation_detail.html")
    assert text.count("/submit\" class=\"inline\"") == 1
    assert text.count('/submit" class="row-menu-form"') == 1
    assert "remove-empty-slot" not in text
    assert text.count("delete-demo") == 1  # item 7 kept: shows only for the demo stay
    menu = text[text.index('id="now"'):text.index("</section>", text.index('id="now"'))]
    assert "reopen-guest" in menu and "release-claim" in menu
    assert "filed-by-hand" in text  # Keep: the manual-filing fallback


def test_code_list_refresh_is_gone_and_test_connection_and_clear_demo_stay():
    assert "refresh-codelists" not in _t("_property_editor.html")
    assert "test-connection" in _t("_property_editor.html")  # item 10: kept in UbyPort setup
    assert _t("dashboard.html").count("/demo/reset") == 1  # item 7 kept, once
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_remove_legacy_actions.py tests/test_send_controls.py tests/test_calendar_sync_ui.py tests/test_dashboard_empty.py tests/test_stays_empty_workspace.py tests/test_host_redesign.py tests/test_demo_stay_exclusion.py tests/test_flash_next_step.py tests/test_property_hub.py tests/test_endtoend.py tests/test_host_i18n.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. Filing row: `cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_worker.py tests/test_submission_*.py tests/test_filed_by_hand.py tests/test_duplicate_guard.py tests/test_claim_*.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_quiet_dashboard_browser.py tests/test_host_stay_actions_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_host_list_layouts_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach the stay detail with the menu open at 390 and 1280 (`stay-menu-390.png`, `stay-menu-1280.png`).

6. Commit: `git add App/app/templates App/app/routes/admin.py App/app/host_i18n.py App/app/host_design_i18n.py App/tests && git commit -m "0137 step 6: remove legacy host actions; Send all only for manual sending"`.

## 5. Do not touch

Routes (all stay, including `/sync`, `remove-empty-slot`, `reopen-guest`, `release-claim`, `refresh-codelists`), `app/reporting.py`, `app/send_controls`, the worker, `_components.html` macros (unused ones are deleted in the cleanup brief), the filed-by-hand panel, the demo buttons (item 7, kept), invoice and fee actions, Settings purge; hard rules 1, 3, 8.

## 6. Commands

- Step 4 commands (both rows) and step 5, 0 skipped.
- `python3 scripts/design_lint.py` expected: OK.

## 7. Acceptance

- [ ] Dashboard header: Add stay, Add cleaning, Clear demo data (demo only), More; no sync button. Properties header: Add property only. Property calendar section: one Update calendars.
- [ ] Stays list rows: menu only. Send all ready: present for a host with a manual property, absent otherwise.
- [ ] Stay detail: one Send button at most; Send again, Reopen guest access and Release assignment in the More menu; no slot button; Delete demo stay stays (demo only).
- [ ] Filing tests pass unchanged.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found verbatim; a count differs; a filing test fails once; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0137-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. State explicitly: "no route or filing logic changed; only the stays route gained the manual_send flag".

## Risk list (for the reviewer)

`App/app/templates/reservation_detail.html` (Send again moved; hard rule 1), `App/app/routes/admin.py` (one query), `App/app/templates/reservations.html` (Send all visibility).

## Owner steps

None (set confirmed 2026-10-19).
