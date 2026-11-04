# 0914: Settings, House book, Reports, Cleaning, Havel and dashboard labels

Status: todo. Source: UX review 2026-11-04 (finding 11; Settings pages, House book, Reports, Cleaning, Havel, Dashboard/Cleaning rows; finding 10 as a check only). Executor: Haiku 5.5, one run. Run after 0913 is merged. If you reach 25 tool calls, stop after the current part (A to F) and hand over as executor.md says.
Read first: AGENTS.md, docs/context/executor.md, this brief.

## 0. Before you start
PR #772 must be merged. This brief does not edit `dashboard.html`, `_components.html` or `base.html`. No guest, public or Payments file.

## 1. Objective
- Settings stops repeating headings and keeps every "?" inline.
- House book keeps its key columns visible, and Export looks like a button.
- The Reports page has the same name as its tab, with readable stamps.
- Cleaning pluralises correctly and its toolbar wraps.
- Havel shows its text box from the start and keeps "All topics" as the back link.
- Calendar labels get tooltips.
- The dashboard nights figure is checked and reported, with no change.

## 2. Context (verified 2026-11-04)
- `templates/settings.html`: the Security group opens `{% call settings_group('security', t('settings.group.security')) %}` (line 104) and then `{{ settings_heading('security', t('settings.nav.security'), t('settings.security.lede')) }}` (line 106), which shows "Security" twice. Passkeys row: 107-112 (`<strong>{{ t('passkeys.title') }}</strong>` + `help_tip`). 2FA: ~147-153, a value card `settings.account.2fa`, then `<div class="settings-action-row">{{ help_tip('settings-2fa-help', ...) }}<a ...>{{ t('settings.account.setup') }}</a></div>` (orphan "?" with no label).
- House book: `templates/housebook.html` line 40, `{{ housebook_csv_menu(...) }}` (macro in `_components.html`, don't edit it). CSS scope `body.v2 .housebook-page` (`app2.css` ~1063).
- Reports: `templates/submissions.html:18` `<h1 class="big">{{ t('reports.title') }}</h1>`. `reports.title` is "Reports" in en (`host_i18n.py:373`) and "Hlášení" in cs (`:2442`). The tab is `tabs.stays.reports` "Police reports" in en (`:8284`). The nav label is `nav.reports` (en `:47`, cs `:2114`).
- Cleaning plural: `static/dashboard-calendar.js:429` builds `String(moreBookings) + " " + cleaningLabels.overflow_bookings`. Strings: `cleaning_i18n.py:216` `"overflow_bookings": ["more bookings", "další rezervace"]`.
- Havel: `routes/havel.py:121` `"havel_locked": len(exchanges) == 0 and not ask`. `templates/_havel_form.html:4` hides the composer with `{% if havel_locked %} hidden data-havel-locked{% endif %}`.

## 3. Files
`templates/settings.html`, `templates/submissions.html`, `static/app2.css`, `static/cleaning.css`, `static/dashboard-calendar.js`, `static/dashboard-calendar.css`, `cleaning_i18n.py`, `routes/havel.py`, `templates/_havel_form.html`, `static/havel.js`, the Havel back-link template (step E2), `host_i18n.py`, `host_vi_i18n.py`, cache keys, tests.

## 4. Steps
### A. Settings
1. Delete line 106 (`settings_heading('security', ...)`). Keep `settings.security.lede` by passing it as the help of the group title, if `settings_group` accepts a help argument (`grep -n "macro settings_group" App/app/templates/settings.html App/app/templates/_account_parts.html`). If it does not, drop the lede.
2. `grep -n "passkeys.title\|settings_heading('passkeys" App/app/templates/settings.html`: if Passkeys has its own heading and also the row `<strong>`, keep only the row.
3. 2FA row: change it to `<div><strong>{{ t('settings.account.2fa') }}</strong>{{ help_tip('settings-2fa-help', t('settings.account.2fa_off')) }}</div>` + the Setup link. Wrap the value card include above it in `{% if current_user.totp_enabled %}...{% endif %}` so "Two-factor" is not said twice.
4. "?" stays inline: append to `app2.css` `body.v2 .settings-action-row > div:first-child{display:inline-flex;align-items:center;gap:4px;flex-wrap:nowrap}`.
### B. House book
5. Append `body.v2 .housebook-page table :is(th,td):first-child{position:sticky;left:0;background:var(--surface);z-index:1}`. Give the export control the secondary-button look: `grep -n "macro housebook_csv_menu" -A12 App/app/templates/_components.html` (read only) gives its summary or button class. Style that class under `body.v2 .housebook-page` with the same tokens as `.ui-btn-secondary` (copy them from `app2.css`, `grep -n "\.ui-btn-secondary{" App/app/static/*.css`).
### C. Reports
6. `reports.title` takes the tab text: en "Police reports"; cs and vi copy their `tabs.stays.reports` value (grep it). Leave `nav.reports`.
7. Stamps: `grep -n "stamp\|receipt\|doruc" App/app/templates/submissions.html` finds the stamp cell. Give it `class="stamp-cell"` and `title="{{ <full value> }}"`. CSS: `body.v2 .stamp-cell{font-family:var(--font-mono, ui-monospace, monospace);white-space:nowrap;max-width:22ch;overflow:hidden;text-overflow:ellipsis}`.
### D. Cleaning
8. Plural: in `cleaning_i18n.py`, add `"overflow_booking_one": ["more booking", "další rezervace"]` and `"overflow_bookings_many": ["more bookings", "dalších rezervací"]`, keeping `overflow_bookings` (cs 2 to 4). First check how the list is turned into `cleaningLabels` and whether vi exists (`grep -n "overflow_bookings\|def .*labels" App/app/cleaning_i18n.py App/app/routes/*.py App/app/templates/*.html | head`). At `dashboard-calendar.js:429`, pick `overflow_booking_one` when n is 1; for cs (`document.documentElement.lang` starts with "cs") pick `overflow_bookings` for 2 to 4 and `overflow_bookings_many` for 5 or more; English uses `overflow_bookings` for anything not 1.
9. Toolbar: `grep -n "toolbar" App/app/static/cleaning.css | head -5`. Give the toolbar `flex-wrap:wrap; gap:12px`, and its selects `min-width:8rem`.
10. Bar span check: seed a stay that started 3 days ago and ends in 2 days, open the month view (Chromium 1280). Its bar's left edge must align with its check-in day cell within 2 px, and greyed past days before check-in must have no bar. If it is off, report the measured numbers and the function in `dashboard-calendar.js` that positions bars (`grep -n "left\b\|style.left\|gridColumn" App/app/static/dashboard-calendar.js | head`), but do not rewrite it.
11. Truncated labels: where `dashboard-calendar.js` writes a bar or cell label (`textContent =`), also set `title` to the full text. In `dashboard-calendar.css`, give bar labels `min-width:2ch`.
### E. Havel
12. Show the text box from the start: in `routes/havel.py:121`, set `"havel_locked": False`. `grep -n "havel-locked\|havelLocked\|Didn" App/app/static/havel.js App/app/templates/_havel_*.html` finds the "Didn't help? Ask Havel" unlock button: hide it when the form is not locked (render it only `{% if havel_locked %}`). Card height: `grep -n "havel-card\|min-height" App/app/static/*.css | grep -i havel`. Replace a fixed `height`/`min-height` on the card with `height:auto`.
13. Back link: `grep -rn "all_topics" App/app/templates/_havel_*.html App/app/static/havel.js`. Where JS or a template swaps the back-link text to the topic name, keep `t('havel.all_topics')` (or the existing key).
### F. Dashboard nights (finding 10, confirm and report, no code)
14. Read only: `grep -n "def month_summary" App/app/reporting.py`, and the function. Answer in the report:
   - Does "This month" nights come from the same reservation rows as the calendar (status, archived filter, date clipping to the month)?
   - Does it count stays still being imported by a calendar sync, which would explain 15 then 19?
   - Give the owner one SQL to compare.
   Change no file in this part (PR #772 also edits `reporting.py`).

## 5. Do not touch
`_components.html`, `dashboard.html`, `reporting.py`, `base.html`, guest/public templates, Payments.

## 6. Commands (from `App/`, `2>&1 | tail -30`)
- `.venv/bin/python -m pytest tests/test_cleaning*.py tests/test_havel*.py tests/test_ai*.py tests/test_guide*.py tests/test_dashboard_calendar*.py tests/test_login_*.py tests/test_passkeys.py tests/test_two_factor_*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=short -x -rs`, 0 skipped. If a Havel test pins the locked composer, update it to the new rule (composer visible at start). Do not delete it.
- Copy row: `test_*_i18n.py test_no_em_dashes.py test_flash_literals.py`.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped. Open the 390/768/1280 shots for Settings → Security, House book, Reports, Cleaning (week and month) and Havel. PR body: per page "390: ...; 768: ...; 1280: ...".
- `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] "Security" shows once, the 2FA "?" has a label, and every "?" sits inline next to its label.
- [ ] House book keeps the first column in view while scrolling, and Export looks like a button.
- [ ] The Reports page title equals the tab, and stamps are one line with the full value on hover.
- [ ] "1 more booking", "3 další rezervace", "5 dalších rezervací".
- [ ] The Havel text box is visible on first open, and the back link always says "All topics".
- [ ] Finding 10 has a written answer, with no code change.

## 8. Stop and ask
An anchor is missing; the cleaning labels have no vi column and the format is unclear; the Havel lock is required by a documented decision (`grep -n "havel" docs/context/decisions.md | head`): if a decision line says the composer stays locked, STOP.

## 9. Report
`docs/tasks/0914-report.md`: the 390 px shots, the step 10 measurements and the finding 10 answer.
