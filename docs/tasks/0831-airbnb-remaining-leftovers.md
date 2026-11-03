# 0831 brief: leftovers of 0830 and Josef's Properties/Stays shots (16:39)

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-3a2ocu` (contains all of 0830), in the main checkout. Do not commit; the orchestrator commits. Each run does ONE group (G, H or I) named in its prompt; G, H and I may run at the same time, so edit only the files of your group and write CSS only between your own markers at the end of `App/app/static/app2.css` (`/* 0831G page help */`, `/* 0831H details+cleanup */`; group I writes no CSS). Report to `docs/tasks/0831<G|H|I>-report.md`.

Context: brief `docs/tasks/0830-airbnb-remaining-pages.md` section 1 (rules 1 to 7) still applies. Read it, not the 0830 reports.

## Group G: page help "?" next to the title (Josef's screenshots)

Josef sees on Properties and Stays: a grey line of fine print under the h1, a bordered "How does this work?" pill with two chevrons, an open bordered box, and "Police reports / Guest register / Export stays (CSV)" as loose bold text. Wanted: Airbnb/Wolt look, a small help "?" on the h1 line.

1. In `App/app/templates/_components.html` add one macro `page_help(how)` that renders the same content as today's `<details class="ui-how">` blocks (the 3 steps `how.<how>.1..3` and the `how.more` link to `/guide#<anchor>`; move the anchor map from `host_page.html` into the macro) but as:
   `<details class="page-help" data-how="{{ how }}"><summary class="page-help-btn" aria-label="{{ t('how.toggle') }}">?</summary><div class="page-help-body">...</div></details>`.
   No icon, no chevron, no visible "How does this work?" text.
2. Replace every `<details class="ui-how ...">` block with `{{ page_help(<key>) }}` placed INSIDE the h1, right after the title text: `host_page.html` (h1 at line ~21; only when `how_key` is set), `dashboard.html` (inside the desktop `span.ph-hide` title), `apartments.html`, `apartment_form.html`, `reservation_detail.html`. Keep `data-how` values.
3. `apartments.html`: delete the `<p class="sub ...">{{ t('apartments.sub') }}</p>` line (fine print). Leave the i18n key.
4. CSS in your block: `.page-help` inline, vertical-align middle, margin-left 8px; `.page-help-btn` 18 px round, 1.5 px border #717171, font 12 px bold, colour #222, list-style none, no native marker (`::-webkit-details-marker{display:none}` and `list-style:none`), invisible 44 px hit area via `::before`. `.page-help-body`: hidden unless `[open]`; when open it is a popover under the "?" (position absolute, z-index 30, width min(320px, calc(100vw - 32px)), white, 1 px #ddd border, radius 12, padding 16, shadow 0 6px 20px rgba(0,0,0,.12), font 15 px normal weight, line-height 1.4, text colour #222). The h1 needs `position:relative` only if required. Must not push other content down.
5. Stays (`reservations.html`, the `.stays-links` block at line ~294 only): render the three links with `partials/settings_index_row.html` (icons: `shield` or the existing police icon, `book`, `download`; pick names that exist in `_icons.html`), inside one bordered card (1 px #ddd, radius 12), rows 64 px with 1 px dividers, chevron right, 24 px above the card. Make sure the `0830D` rules for `.stays-links` do not fight yours (override in your block).
6. Tests to update to the new markup: `App/tests/test_page_help_0277.py`, `App/tests/test_motion_browser.py`, `App/tests/test_property_create_browser.py`, and the `ui-how` checks in `App/tests/test_0830_airbnb_pages_browser.py` (`test_0830C_properties_regressions`). Add one test there, `test_0831G_page_help`: on `/apartments` and `/reservations` at 390 and 1280, the "?" is visible, 16 to 20 px wide, its centre within 8 px of the h1 text's vertical centre and left edge 6 to 12 px after the title text's right edge; the help body is hidden; after a click it is visible, inside the viewport, and does not move the next element after the header; no `.ui-how` anywhere on the page.
7. Run: those 4 test files plus `-k "partB or partC or partD"` of the 0830 test. 0 skipped.

## Group H: details and cleanup

1. `submission_detail.html`: the outcome note ("UbyPort accepted this report ..." and its failed/pending variants) becomes one `partials/settings_value_card.html` (label = status label, value = short state word already used for the status badge). The full sentence stays available under a `help_tip` next to the label (UbyPort rule 1: the host must still be able to read what happened; do not drop it).
2. Invoice items overflow 34 px at 360 px (`App/tests/test_host_invoice_items_browser.py`): fix in the `0831H` block (wrap or stack the item row at <= 480 px). That test passes.
3. In the `0830B overview+menu` block of `app2.css`, delete the rules for the calendar day grid and stay bars (selectors with `cal-`, `dashboard-calendar`, `stay-bar` or `day-`); the calendar PR owns them. Delete only those rules.
4. `App/tests/test_host_geometry.py::test_dashboard_actions_share_height_and_gap` (40 vs 37 px): make the overview action buttons share one height in the `0831H` block (do not edit the 0830B block for this). It passes.
5. Run: `test_host_invoice_items_browser.py`, `test_host_geometry.py`, `-k "partE or partB"` of `test_0830_airbnb_pages_browser.py`, and the submission detail tests that `grep -l submission_detail App/tests/*.py` finds. 0 skipped.

## Group I: tests and lint (no template or CSS change except item 2)

1. `App/tests/test_payments_consent.py`: failures since `/payments` changed: monkeypatch `STRIPE_MODE` (look how other payments tests set it) so the test reaches the page; fix assertions only where they check the old markup.
2. `billing_plan.html` reads `apartments` that the route no longer passes as such: use the value the route passes (`apartment_count`); check with `grep -n "billing_plan.html" -A15 App/app/*.py`. No Python change.
3. Old-shell tests that used `/payments` as their old-shell page (`grep -ln "/payments" App/tests/test_design_shell*.py App/tests/test_*sidebar*.py App/tests/test_*guardrail*.py`): point them at a page that still uses the old shell (find one: a host template without `set v2 = true`), or, if none is left, say so in the report and stop on that item.
4. `python3 scripts/design_lint.py` (repo root): add the new classes from 0830 parts and 0831 to `docs/design/catalog.json` the way existing entries look (e.g. `stays-title-row`, `stays-pills`, `police-deadline-row`, `e-page`, `f1-*`, `page-help*`). Lint passes, or list what is left.
5. Run: the files you changed plus `App/tests/test_billing*.py`. 0 skipped.

## Commands

From `App/`: `.venv/bin/python -m pytest <files> -q --tb=short -x 2>&1 | tail -30`. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30`.

## Do not touch

Settings area templates and their CSS blocks, `_dashboard_calendar.html`, `cleaning.html`, `base.html` cache key (orchestrator bumps it), `docs/tasks/screenshots-*` and evidence folders, any other group's files or CSS block. No commit, no push.

## Stop and ask

If a fix needs a Python route change, a new dependency, or another group's file: stop and write it in your report.

## 1. Objective

Groups G, H, I and J above (0830 leftovers).

## 2. Context

See the group sections above.

## 3. Files

Named per group above.

## 4. Steps

Per group above.

## 5. Do not touch

See "Do not touch" above.

## 6. Commands

See "Commands" above.

## 7. Acceptance

Each group's run line passes with 0 skipped.

## 8. Stop and ask

See "Stop and ask" above.

## 9. Report

See the 0831G, 0831H, 0831I and 0831J reports.
