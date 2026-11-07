# 0998: Calendar "Booked" label and mobile calendar polish

Status: todo
Depends on: 0993 (merged first; it created the `dashboard.calendar.blocked` keys) | Base commit: HEAD of the 0993 branch | Branch: task/0998-ux-mobile-calendar
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner feedback from phone screenshots of `/?cal_view=calendar`: imported placeholder blocks read "CLOSED - Not available" and must read "Booked" (cs "Obsazeno"); and the mobile calendar has a stray blue side border, a heavy red ring on the sheet close button, floating buttons covering the last row, and an unclear "0 / Not specified" guest line. Change only what is listed.

## 2. Context

Rules: light mode only; copy rule 9; host UX gate (AGENTS rule 10); copy only via `host_i18n.py` (en + cs; do not touch `host_vi_i18n.py`); no em dashes. Read nothing else.

Root causes found by the orchestrator:

- The sheet prints the raw iCal label (`event.label`), so "CLOSED - Not available" shows. `labelFor` in the JS already hides such placeholders on pills (regex `generic`), but the sheet does not.
- The blue side border is the browser focus outline on `.cal-body` (`tabindex="-1"`, focused by script).
- The close button is auto-focused when a sheet opens and shows a heavy red outline.
- Pills already carry a `title` tooltip with the full label, so truncation stays (ellipsis); no change.

Anchors (each must be found verbatim, else STOP):

`App/app/static/dashboard-calendar.js` line 667:
```
    if (event.label) container.append(el("p", "cal-detail-label", event.label));
```
line 668:
```
    const guestCount = event.expected === null ? String(event.complete) + " / " + labels.unknown : String(event.complete) + " / " + String(event.expected);
```
`App/app/templates/_dashboard_calendar.html` line 138:
```
  'unknown': t('calendar.unknown'),
```
`App/app/host_i18n.py` (en and cs, each once): `"dashboard.calendar.blocked": "Blocked",` / `"dashboard.calendar.blocked": "Blokováno",`; `"dashboard.calendar.legend.grey": "Blocked or waiting",` / `"dashboard.calendar.legend.grey": "Blokováno nebo čeká",`; `"calendar.unknown": "Not specified",` / `"calendar.unknown": "Neuvedeno",`.
Last line of `App/app/static/dashboard-calendar.css` is free (append only).
`App/app/templates/base.html` line 22 and the `dashboard-calendar.css?v=` link (find: `grep -n "dashboard-calendar.css?v=" App/app/templates/*.html | tail -30`); match only up to `?v=`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_i18n.py | edit | "Booked"/"Obsazeno" wording, 1 new key |
| App/app/static/dashboard-calendar.js | edit | sheet label and guest-forms line |
| App/app/templates/_dashboard_calendar.html | edit | pass 2 new labels |
| App/app/static/dashboard-calendar.css | edit | focus, bottom padding |
| App/app/templates/*.html carrying `dashboard-calendar.css?v=` | edit | bump cache key |
| App/tests/test_dashboard_calendar.py (or the file that asserts the i18n labels; find with grep) | edit | one assertion |

No other file may change.

## 4. Steps

1. `host_i18n.py`: change en `"dashboard.calendar.blocked": "Blocked",` to `"Booked",`; en `"dashboard.calendar.legend.grey": "Blocked or waiting",` to `"Booked or waiting",`. cs: `"Blokováno",` to `"Obsazeno",`; `"Blokováno nebo čeká"` to `"Obsazeno nebo čeká"`. After en `"calendar.unknown": "Not specified",` add:
```
        "calendar.no_forms": "No guest forms yet",
```
after cs `"calendar.unknown": "Neuvedeno",` add:
```
        "calendar.no_forms": "Zatím žádné formuláře hostů",
```
Check: `grep -n "calendar.no_forms\|Booked or waiting\|Obsazeno" App/app/host_i18n.py | tail -30` shows 6 lines or more.
2. `_dashboard_calendar.html`: after the line `  'unknown': t('calendar.unknown'),` add `  'no_forms': t('calendar.no_forms'),` and `  'blocked': t('dashboard.calendar.blocked'),`. Check: `grep -n "no_forms\|'blocked'" App/app/templates/_dashboard_calendar.html | tail -30` (2 lines).
3. `dashboard-calendar.js`: replace line 667 with:
```
    const placeholder = /^(?:[!⚠]\s*)?(?:closed(?:\s*[-–]\s*not available)?|not available|airbnb\s*\(not available\)|blocked|unavailable)$/iu.test((event.label || "").trim());
    if (event.label) container.append(el("p", "cal-detail-label", placeholder ? labels.blocked : event.label));
```
Replace line 668 (now 669) with:
```
    const guestCount = event.complete === 0 ? labels.no_forms : (event.expected === null ? String(event.complete) : String(event.complete) + " / " + String(event.expected));
```
(`labels.unknown` stays defined for other users; do not remove it.) Check: `grep -n "no_forms\|placeholder ?" App/app/static/dashboard-calendar.js | tail -30`.
4. `dashboard-calendar.css`: append at the end:
```
/* 0998: mobile polish. No UA focus box on the scripted-focus body, calm close-button focus, room under the last row for the floating buttons. */
.dashboard-calendar .cal-body:focus{outline:0}
.dashboard-calendar .cal-dialog button.cal-close:focus:not(:focus-visible){outline:0;box-shadow:none}
.dashboard-calendar .cal-dialog button.cal-close:focus-visible{outline:0;box-shadow:var(--focus-ring-2)}
@media (max-width:767px){.dashboard-calendar .cal-body{padding-bottom:140px}}
```
Check: `tail -5 App/app/static/dashboard-calendar.css | cut -c1-120`. `--focus-ring-2` is defined in tokens.css; if the close button still shows a heavy ring in the 390 screenshot, report it, do not add more rules.
5. Bump the `dashboard-calendar.css?v=` value to `20261107-0998` where it is linked (grep from section 2; one file). Check the grep again.
6. Test: `grep -rln "calendar.unknown\|dashboard.calendar.blocked" App/tests | tail -30`; in the file found (else `test_dashboard_calendar.py`) add one test that `host_i18n.translate("en", "dashboard.calendar.blocked") == "Booked"` and `translate("cs", ...) == "Obsazeno"`. Copy the import style of a neighbouring test.

## 5. Do not touch

`app.css`, `app2.css`, `admin.py`, `.havel-fab` and `.cal-to-top` rules, pill grid or span logic, `host_vi_i18n.py`. No new dependency, outbound request or personal-data field.

Out of scope, state in the report as "not attempted": pills spilling past the day cell edge (week-grid span logic), shorter or two-line pill labels (full text is already in the `title` tooltip), hiding the floating help and scroll-up buttons (padding only). Report anything from the screenshots you still see.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_dashboard_calendar.py tests/test_dashboard_calendar_browser.py tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30` (`UBYHOST_REQUIRE_BROWSER=1`, 0 skipped).
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`; open the calendar page screenshots `/tmp/shots/layout-lint/<page>-{390,768,1280}.png`.
- Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] No "Not available" or "CLOSED" text reaches the sheet or the dashboard bars; en "Booked", cs "Obsazeno"; the 0993 legend says "Booked or waiting".
- [ ] Sheet shows "No guest forms yet" when 0 forms, else "N / M" or "N".
- [ ] 390 px screenshot of the calendar page: no blue side border, last month row clear of the floating buttons; sheet close button shows no heavy red ring when opened by tap.
- [ ] Layout lint zero findings, 0 skipped. Per page "390: ...; 768: ...; 1280: ..." in the PR; design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found (0993 not on your branch: stop); a test fails twice; 25 tool calls; a file outside section 3 needs a change; a lint finding you cannot fix inside section 3 (never silence it).

## 9. Report

Write `docs/tasks/0998-report.md` (600 tokens at most), set `Status: review`: files changed, last 5 lines of each command, section 7 ticked, the "not attempted" items, deviations. Hand merge and deploy to the owner.
