# 1124: property page Calendars table, copy link button beside the URL, same look as the other buttons

Status: review
Depends on: none | Base commit: origin/main | Branch: task/1124-calendar-copy-link-button
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (3 steps of at most 6 calls)
Brief by Sonnet 5.5, 2026-11-11. Owner Josef: "the copy link button is ugly, make it better".

## 1. Objective

In the property page Calendars section, each feed row shows the URL as plain text (cut at 240 px) with a grey `btn sm ghost` "Copy link" pill stacked below it. Put the URL field and the copy button on one row: URL flexible and ellipsised, button to its right, same weight as the other pills in that table (Remove is `ui-btn-danger`, Add calendar is `ui-btn-secondary`, both `ui-btn-compact`). No new copy.

## 2. Context

Rules: AGENTS rule 6 (light mode), 7 (browser and geometry tests, 0 skipped, one 390 px screenshot per changed page), 9 (copy), 10 (UX gate). No new dependency, no new i18n key (label stays `common.copy_link`, "Copied" feedback stays `common.copied`).

Template `App/app/templates/_property_calendars.html`, lines 48-51:
```
<td class="small feed-url" data-label="{{ t('apartment.form.feed.url') }}">
  <span class="mono feed-url-value" id="feed-url-{{ feed.id }}" title="{{ feed.url }}">{{ feed.url }}</span>
  {{ copy_button('feed-url-' ~ feed.id, t('common.copy_link')) }}
</td>
```
`copy_button` (`_components.html` line 323) renders, under `body.v2`, `<button class="btn sm ghost copy-btn" data-copy=ID>` with a `.copy-label-default` span and a `[data-copy-label-slot]` span; CSS at `app2.css` 418-422 swaps them on `.copied`, and `app.js` line 400 `bindHostNodes("[data-copy]")` does the copy. Do not change the macro or the markup inside the button: that keeps the "Copied" feedback working. The target stays the `<span id="feed-url-N">` (existing tests need that id visible).

CSS today (all `body.v2`, `App/app/static/app2.css`):
- 2482-2490: below 1024 px `.feed-table` becomes stacked label cards (`td{display:block;width:100%}`). The URL cell hides its `::before` label (2857).
- 2974: `.feed-table .feed-url-value{display:block;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}`; 2975: `max-width:100%` below 1024 px.
- 2861 and 2872 (`.feed-url-value` break-all, bordered box, `var(--s)` background, padding `var(--space-3)`) are older rules for a `<details>` that no longer exists in the template; the later rule 2974 wins on `max-width`/`white-space`/`overflow`, the border and padding of 2872 still apply. Reuse that bordered look as the "field".
- 206 and 308: `.btn.sm` already gets `min-height:44px` below 1024 px (below 640 px inside `tbody`).
Reference pattern (Guest links section, do not edit): `app2.css` 2700-2707 (`.guest-copy-row`: flex, nowrap, gap 12, input `flex:1 1 auto;min-width:0;height:40px`, button `flex:none;height:40px;padding:0 12px;white-space:nowrap`, 44 px below 1024 px).

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/_property_calendars.html` | wrap span and button in one div (lines 48-51) |
| `App/app/static/app2.css` | edit line 2974-2975, add rules after 2975 |
| `App/app/templates/base.html` | bump `app2.css?v=` (line 23, now `20261111-1103a`) to `20261111-1124a` |
| `App/tests/test_host_property_controls_browser.py` | add one browser test |
| `App/tests/test_calendar_sync_ui.py` | add one template test |

No other file. No i18n change.

## 4. Steps

### Step 1: template and CSS (at most 6 calls)
1. Template: replace the span and the `copy_button` line with
```
<div class="feed-url-row"><span class="mono feed-url-value" id="feed-url-{{ feed.id }}" title="{{ feed.url }}">{{ feed.url }}</span>{{ copy_button('feed-url-' ~ feed.id, t('common.copy_link')) }}</div>
```
(keep the `<td>` line and `</td>`).
2. CSS: replace lines 2974-2975 with the block below. First check the real `ui-btn-secondary` look: `grep -n 'ui-btn-secondary' App/app/static/app2.css | head -6` and copy its border, background, colour and radius into the `.copy-btn` rule instead of the guesses in brackets.
```
body.v2 .feed-table .feed-url-row{display:flex;flex-wrap:nowrap;align-items:center;gap:12px;min-width:0;max-width:100%}
body.v2 .feed-table .feed-url-row .feed-url-value{flex:1 1 auto;min-width:0;max-width:none;margin:0;padding:0 12px;height:40px;display:flex;align-items:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:normal;overflow-wrap:normal}
body.v2 .feed-table .feed-url-row .copy-btn{flex:none;width:auto;height:40px;min-height:40px;padding:0 14px;margin:0;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:var(--radius-md,8px)}
@media (max-width:1023px){body.v2 .feed-table .feed-url-row .feed-url-value,body.v2 .feed-table .feed-url-row .copy-btn{height:44px;min-height:44px}}
```
Use the copied `ui-btn-secondary` values for the last property group of the `.copy-btn` rule (white outlined pill like Add calendar, never the grey `#efefeb`). Keep `display:inline-flex` only for the not-copied state; do not touch the `.copied` rules at 418-422. Bump `base.html` `?v=`.
3. Run `grep -n 'feed-url-row' App/app/static/app2.css | wc -l` (expect 4).

### Step 2: tests (at most 6 calls)
1. `test_calendar_sync_ui.py`: grep how an existing test renders the property bookings page with a feed (`grep -n 'feed-table\|feed-url' App/tests/test_calendar_sync_ui.py | head`), follow it, add `test_feed_url_and_copy_button_share_one_row`: assert the HTML contains `class="feed-url-row"`, that `id="feed-url-<id>"` and `data-copy="feed-url-<id>"` both appear inside that div, and that the label `Copy link` still appears once per feed.
2. `test_host_property_controls_browser.py`: the existing test at lines ~839-857 (rows `.feed-table tbody tr`, `_IN_VIEW_0984`) shows the fixture with two feeds; read lines 825-860 only and add a sibling test using the same setup. At 1280 and 768: for each row, `#feed-url-N` and `.copy-btn[data-copy='feed-url-N']` bounding boxes have vertical centres within 4 px of each other, button `left >= url right - 1` (same row, button on the right), URL width >= 120, button height >= 44 at 768 and >= 36 at 1280. At 390: `document.documentElement.scrollWidth <= innerWidth`, the row's `.feed-url-row` right edge <= its `td` right edge + 1, both children in view (`_IN_VIEW_0984`), URL width >= 100. At all three widths click the button (grant clipboard permission as other tests in the file do, or skip the clipboard read) and assert the button text becomes `Copied` (`common.copied`) then use the existing wait pattern; if no such pattern exists, only assert the `copied` class is set.
3. Existing assertions at lines 845-857 and in `test_wp28_geometry.py`, `test_wp28_ui_sweep.py` must still pass unchanged; if one fails, report it, do not weaken it.

## 5. Do not touch (same macro, different markup or place)

`copy_button` and `copy_inline` stay unchanged. Other users, left alone:
- `_property_editor.html` lines 258, 266 (Guest link and PIN `.guest-copy-row`, the reference pattern) and 78 (Guest link tile, brief 1103).
- `reservations.html` 239 and `dashboard.html` 141 (`copy_inline`, stay link in a row menu or table cell), `stay_fees.html`.
- `apartments.html` 46 (`copy_button` in the properties list), `booking_site_setup.html` 77/87, `payments_share.html` 20, `stay_fee_detail.html`, `submission_detail.html` 100, `_havel_card.html` 14, `_smart_lock_share.html` 6, `_smart_locks_panel.html`, `setup_wizard/*`, `_components.html` onboarding finish (358, 363).
Only the feed table uses `.feed-url-row`; the grey `btn.sm.ghost` look elsewhere is out of scope. If the owner wants a global change, that is a new brief.

## 6. Commands (run from `App/`, each ends with `| tail -30`)

```
.venv/bin/python -m pytest tests/test_calendar_sync_ui.py tests/test_calendar_platform_required.py tests/test_feed_*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_layout_lint_browser.py tests/test_wp28_geometry.py tests/test_wp28_ui_sweep.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_host_i18n*.py -q --tb=short -x 2>&1 | tail -30
```
Browser files must report 0 skipped (`-rs`; any skip is a fail, report it). Rows used: test-map "Calendar, iCal feeds", host templates, host CSS. No full suite.

## 7. Acceptance

UX gate (AGENTS rule 10, you do it, never ask the owner)

Property page, Calendars section (`/apartments/<id>?view=bookings`), property with two feeds, screenshots at 390, 768, 1280. Open them and write per width in the PR: URL field and white outlined "Copy link" pill on one row, button right of the field, same height as Remove and Add calendar, URL ellipsised not wrapped, no horizontal scroll, "Copied" shown after a click. At 390 the table stacks into cards (below 1024 px): the URL row fills the card width. Tick the [design-system checklist](../design/design-system.md) in the PR body. Never silence a finding; if `test_layout_lint_browser.py` flags the button (44 px target, overflow), fix it and rerun.


- Section 6 tests green, 0 skipped; screenshots attached; draft PR until UX notes are written; merge only with `scripts/merge-pr-on-green.sh`, never push to `main`.
- Report: files changed, test tail lines, three screenshot descriptions. Do not edit status, decisions or known-issues.

## 8. Stop and ask

Stop and report if: `ui-btn-secondary` has no CSS to copy; a feed test outside section 6 fails; the layout lint flags something the CSS above cannot fix in 2 tries; more than 30 tool calls.

## 9. Report

Files changed, test tail lines, the three screenshot descriptions, any deviation from this brief.
