# 0751 brief: phone v2 stay page (Airbnb reservation style)

Status: review
Executor: Haiku 5.5, alone, on branch `claude/project-thread-rub7xm` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push, do not commit).
Another Haiku works on brief 0750 (stays list) in the same folder at the same time: edit only the lines this brief names; never revert changes you did not make.

## 1. Objective

Below 1024 px, `/reservations/{id}` looks like screen `pobyt` of `docs/design/mockup/ubyhost-phone-v2.html`:
top row with round soft back button left and the existing "···" stay menu right (no copy button in the top row; "Copy guest link" becomes an item of that menu);
centred 30 px name (h1.big) with the centred "property · source" line under it; the status pill line is hidden on phone;
one white card with Check-in | Check-out (weekday + date bold, check-in/out time under it when the property has one) and a full-width bottom line "N guests · N nights";
guest rows without dividers with a round 36 px state icon; police card and door-code card in v2 card style; one sticky coral button (the existing phone CTA).
"Request payment" moves from the page bottom link into the "···" menu on phone. Desktop (>= 1024 px) must not change at all.

## 2. Context

- Design: read the `/* stays list + stay page (0750` CSS block and the `data-s="pobyt"` section of `docs/design/mockup/ubyhost-phone-v2.html`. Do not edit the mockup.
- Template: `App/app/templates/reservation_detail.html`: lines ~28-40 (`.top.stay-top`, `.sub.sub-phone`, `.stay-pill-line`, `.facts`), ~65 `h1.big`, the head actions row menu (grep `row_menu_begin` / `stay-head-actions`), ~171 guests header, the phone guest list (grep `guest-list`), ~286 police card, ~357 door code, ~363 Request payment link.
- CSS: `App/app/static/app2.css` lines ~532-602 (`.host-stay-detail` rules; line ~596 positions the phone row menu at `right:64px`, line ~600 the fixed phone CTA `.stay-head-cta`). Shared phone v2 classes exist (search `0718`, `0729`, `0735`): reuse, do not copy.
- Check-in/out times: grep how the desktop page or the property gives `checkin_time`/`check_in_time` (`grep -n "check.\?in_time\|checkin" App/app/templates/reservation_detail.html App/app/*.py | head`). If the stay page has no time in its context, leave the time line out (no new query).
- `.ph-hide` / `.ph-only` as in app2.css.
- Standing rule for tests: you may change assertions that only check the phone stay page below 1024 px (stay-top buttons, facts cells, the phone request-payment link, pill line) in `App/tests/test_*stay*browser*`, `test_*reservation_detail*`, `test_design_guardrails_browser.py`, `test_host_wide_geometry_browser.py` and the `stay` entry of `App/tests/v2_mockup.py`. Keep the filing-forms count (`grep -c 'action="/reservations/'` = 12 decision) unless a test proves otherwise. Change no desktop assertion.

## 3. Files

The template, `app2.css`, i18n files, `App/tests/v2_mockup.py` and the tests in section 2.

## 4. Steps

1. Template: remove the copy round button from `.stay-top` (keep the desktop copy button); add "Copy guest link" (same `data-copy="stay-link"` attributes) and "Request payment" (`/payments?reservation_id=…#new-request`) as phone-only items of the stay "···" menu (`ph-only` on the items if the menu is shared with desktop); hide the bottom Request payment `.list` on phone (`ph-hide`). Move the "···" menu to the top row's right edge on phone (change `right:64px` to the gutter so it sits where the copy button was). Rewrite `.facts` as `<div class="card facts stay-dates">` with two cells (small label, b weekday+date, span time when known) and `<div class="tot">{{ guests }} · {{ nights }}</div>`; use existing i18n keys for labels and counts (grep `tp(` plural helpers for guests/nights; add keys only if none exist, in en/cs/vi). Add `ph-hide` to `.stay-pill-line` content on phone or hide it in CSS. Guest rows: make the phone guest list markup `.list.guests .row` with `.ic.ok|.ic.warn` and `.t b/small` like the mockup (keep its data and links). Door card: keep `.stay-door-card`, icon in `.ic.acc`.
2. `app2.css`: one `@media (max-width:1023px){…}` set in the `.host-stay-detail` area with values copied from the mockup (`.stay-top`, `h1.big`, `.sub-phone`, `.stay-dates` and children, `.guests .row`, `.guests .ic…`, `.police-card b/small`, `.stay-door-card`, `.code`, `.ic.acc`), prefixed `body.v2 .host-stay-detail`. Restyle the existing fixed phone CTA bar to match the mockup `.actbar` (white, top line, 12px 20px padding, full-width coral `.btn` 50 px high, radius 12). Delete phone rules made dead by the change (grep first). No `!important`.
3. `App/tests/v2_mockup.py`, `stay` entry: add `"phone_mockup": PHONE_MOCKUP_V2,`; set `"phone_selectors"` to
   `[".tabs", ".stay-top .round", ".host-stay-detail h1.big", ".sub-phone", ".stay-dates", ".stay-dates small", ".stay-dates b", ".stay-dates .tot", "h2.sec", ".guests .row", ".guests .ic", ".guests .row b", ".guests .row small", ".police-card", ".police-card b", ".stay-door-card", ".code"]`
   (drop a selector only if it cannot exist in one of the two pages, and say why in the report). Keep `missing_ok` for `.code` (no code issued in the fixture) and add `.stay-door-card` with the same reason. Replace old `stay:` BOX_OVERRIDES that name removed selectors; add new ones only for text/data-dependent sizes, under `# text-dependent: app copy vs phone v2 mockup demo copy (0751)`, keyed `"stay:selector@width"`.
4. Tests, from `App/` (do NOT reinstall playwright; the venv pins 1.63.0):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -k stay 2>&1 | tail -30` (collect first with `--collect-only -q | grep -i stay | head` and run the stay-page ids). Style failures mean wrong CSS: fix the CSS, never override a style.
   Then the stay-page tests: `ls tests | grep -i -E 'stay|reservation_detail'`, run the ones with `browser` in the name plus `test_design_guardrails_browser.py test_host_wide_geometry_browser.py`, same env, `-q --tb=short 2>&1 | tail -30`, and the non-browser `test_*stay_detail*`/`test_*reservation_detail*` files.
5. Take a 390 px full-page screenshot of the stay page used by the 0710 test to `docs/tasks/screenshots-0751/stay-390.png`.

## 5. Do not touch

Desktop (>= 1024 px) markup and rules, filing forms and their actions, `docs/design/mockup/`, `reservations.html` (0750), `base.html`, `static_versions.json`, `catalog.json`.

## 6. Commands

The test commands in step 4, from `App/`.

## 7. Acceptance

The 0710 stay test and the listed tests pass with 0 skipped (test_static_versions and design_lint may fail until the orchestrator bumps them; say so).

## 8. Stop and ask

A test outside the standing rule fails, or the 30-call cap comes near: write the report with what is left.

## 9. Report

`docs/tasks/0751-report.md`: changed files, command tails, overrides added, new CSS classes and i18n keys, deviations.
