# 0840: Stays list: one-tap guest-link copy icon on the phone row

Status: todo
Depends on: 0841 (baseline first); runs after 0837 (both edit `reservations.html`) | Base commit: b8c87df | Branch: task/0840-stay-row-copy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On a phone, each active stay row on `/reservations` gets a copy icon next to its row menu that copies the guest-form link in one tap. Today it takes two (open the row menu, then "Copy guest form link"). Target: 2 to 1 tap.

## 2. Context

Verified on b8c87df, `App/app/templates/reservations.html`:
- Line 234: `        <td class="row-actions" data-card="actions" data-label="">`, next line `          {{ row_menu_begin() }}`.
- Lines 238-242: the row menu already renders `copy_inline('stay-link-' ~ reservation.id, …)`, which writes a hidden input `id="stay-link-<id>"` plus a button with `data-copy="stay-link-<id>"` (macro `copy_inline` in `App/app/templates/_components.html` line 316). The new icon reuses that input; no new URL logic.
- Rows are `tr.clickable-row[data-href]` (`App/app/static/app.js` line 10 `ROW_SELECTOR`). Tapping the icon must not open the stay.
- `icon('copy', …)` is already used in `_components.html`.
- Label key already exists: `host.copy_guest_form_link` (EN "Copy guest form link", CS "Kopírovat odkaz na formulář hosta"). No new copy.
- 12 px neighbour rule (MASTER `--space-3:12px`): the icon must be 12 px or more from the row-menu trigger. No new CSS file in scope.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservations.html` | edit | Icon button in the actions cell |
| `App/tests/test_host_stay_row_copy_browser.py` | new | Browser test at 390 px |
| `docs/tasks/0840-report.md` | new | Report |

No other file may change.

## 4. Steps

1. Check the copy handler first: `grep -n 'data-copied-label\|data-copy-label\|textContent' app/static/app.js | head -20`. If the handler replaces the button's text with the copied label (which would erase the icon) and offers no way to keep it, STOP and report: the fix belongs in `app.js` and needs a new brief.
2. `reservations.html`: directly after line 234 (the `row-actions` `<td>`), before `{{ row_menu_begin() }}`, insert:
```html
          {% if reservation.permalink_token and not show_archive and reservation.status == 'active' %}<button class="ui-btn ui-btn-quiet ui-btn-compact ph-only stay-row-copy" type="button" data-copy="stay-link-{{ reservation.id }}" data-copied-label="{{ t('common.copied') }}" aria-label="{{ t('host.copy_guest_form_link') }}" title="{{ t('host.copy_guest_form_link') }}">{{ icon('copy', 18) }}</button>{% endif %}
```
   Commit.
3. New test `test_host_stay_row_copy_browser.py`: copy the server, login and seed setup from `App/tests/test_host_stay_actions_browser.py` (read its first 80 lines only). One active stay with a permalink. At 390×844: assert `.stay-row-copy` is visible; click it; assert the page URL did not change and the clipboard (or the button's copied state, whichever the handler gives) shows the link ending in `/<reservation id>`; assert the horizontal gap between `.stay-row-copy` and the row-menu trigger is 12 px or more (bounding boxes); at 1280 px assert `.stay-row-copy` is hidden. Save a 390 px screenshot to `docs/tasks/screenshots-0840/stays-390.png`. Grant `clipboard-read`/`clipboard-write` on the context if needed. Commit.
4. Run §6. If the click opens the stay (row navigation), STOP and report: the row guard in `app.js` is out of scope.

## 5. Do not touch

`app.js`, CSS files, `_components.html`, `reservation_detail.html`, filing and send buttons. Wizard, onboarding and property-editor files. No new share API (would need a decision line).

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_host_stay_row_copy_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
2. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`

Expected: all pass, 0 skipped.

## 7. Acceptance

- [ ] At 390 px one tap on the row icon copies the guest link and stays on the list.
- [ ] Hidden on desktop, absent for archived or inactive stays and stays without a link.
- [ ] Gap to the menu trigger is 12 px or more.
- [ ] Commands 1-2 pass, 0 skipped; one 390 px screenshot of `/reservations`.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0840-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/reservations.html` (condition matches the menu copy; no duplicate ids).

## Owner steps

1. Check the screenshot, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
