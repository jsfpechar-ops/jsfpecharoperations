# 0993: Dashboard heading count, stale prompt, preview banner, calendar pills

Status: todo
Depends on: none | Base commit: 423d603 | Branch: task/0993-ux-dashboard-banner
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix four owner-reported UX faults on the dashboard and the preview banner: the count badge jammed onto "What needs you", the "Guests not registered" prompt still shown for a stay that has ended, the unstyled preview banner with a cramped Exit preview button, and the dashboard calendar pills ("CLOSED - No..." truncated, mixed colours, no legend). Owner said all of these are quick UX fixes: change only what is listed.

## 2. Context

Rules: light mode only; copy rule 9 (one explanation in one place, no sentence the button already says); host-page UX gate (AGENTS rule 10); every new copy key goes in `host_i18n.py` for `en` and `cs`. Read nothing else.

Root causes found by the orchestrator:

- v2 pages load `app2.css` only. The `.impersonation-bar` rules live in `App/app/static/app.css` (line 628), which v2 pages never load, so the banner is unstyled.
- `body.v2 h2.sec` is `display:flex` with no `gap`, so the badge touches the text.
- `needs_you.stay_line` in `App/app/needs_you.py` never checks the departure date.
- The 14-day grid is built in `App/app/routes/admin.py` `_overview_calendar_rows` and rendered in `App/app/templates/dashboard.html`.

Anchors (each must be found verbatim, else STOP):

`App/app/static/app2.css` line 255:
```
  body.v2 h2.sec{font-size:13px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em;margin:26px 0 12px;display:flex;justify-content:center;align-items:baseline}
```
`App/app/static/app2.css` line 70:
```
.crow .bar{grid-row:1;height:28px;border-radius:999px;font-size:12px;font-weight:600;display:flex;align-items:center;padding:0 10px;margin:0 2px;white-space:nowrap;overflow:hidden}
```
`App/app/needs_you.py` (inside `stay_line`):
```
    arrival = validation.parse_iso_date(_get(reservation, "date_from", ""))
    if status in _GUEST and arrival is not None and arrival <= today + timedelta(days=1):
```
`App/app/routes/admin.py` (inside `_overview_calendar_rows`):
```
            tone = event["tone"]
            if tone == "done":
                css = "b-ok"
            elif tone in ("action", "ready", "overdue"):
                css = "b-warn"
            else:
                css = "b-grey"
            overdue = tone == "overdue"
            source = str(event["source"] or "").lower()
            label = event["label"] or _OVERVIEW_SOURCE_NAMES.get(source) or host_i18n.translate(lang, "calendar.kind_stay")
```
and below it `placed.append((col_start, col_end, {"css": css, "col_start": col_start, "col_end": col_end, "overdue": overdue, "label": label, "url": event["url"]}))`.

`App/app/templates/dashboard.html` (the grid):
```
    <div class="cgrid"><div></div>{% for d in cal_days %}<div class="cd{{ ' today' if loop.first }}">{{ wd[d.weekday()] }} {{ d.day }}</div>{% endfor %}</div>
```
```
<a class="bar {{ bar.css }}" data-c1="{{ bar.col_start }}" data-c2="{{ bar.col_end }}" data-row="{{ bar.row }}"{% if bar.overdue %} data-overdue{% endif %} href="{{ bar.url }}">{{ bar.label }}</a>
```
```
  <p class="ov-cal-more ov-cal-block{{ ' ph-hide cal-hide' if cal_view }}"><a href="/?cal_view=calendar" class="ov-cal-link">{{ t('dashboard.calendar.full') }}</a></p>
```
`App/app/host_i18n.py`: `"dashboard.calendar.full": "Full calendar →",` (en, about line 9211) and `"dashboard.calendar.full": "Celý kalendář →",` (cs, about line 9249).
`App/app/templates/base.html` line 22: `<link rel="stylesheet" data-turbo-track="reload" href="/static/app2.css?v=...">` (value changes between briefs; match only up to `/static/app2.css?v=`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | h2.sec gap; impersonation bar styles; bar title/legend styles |
| App/app/templates/base.html | edit | bump app2.css cache key |
| App/app/needs_you.py | edit | no "forms" prompt once the stay has ended |
| App/app/routes/admin.py | edit | blocked placeholder: short label, grey, full text in title |
| App/app/templates/dashboard.html | edit | bar title, header month hint, legend line |
| App/app/host_i18n.py | edit | 3 keys, en + cs |
| App/tests/test_needs_you*.py or the existing file that tests `stay_line` | edit | one test (find with grep) |

No other file may change.

## 4. Steps

1. `app2.css` line 255: add `;gap:8px` before the closing brace, so the rule ends `display:flex;justify-content:center;align-items:baseline;gap:8px}`. Check: `grep -n "align-items:baseline;gap:8px" App/app/static/app2.css | tail -30` shows one line.
2. `app2.css`: append at the end of the file (v2 never loads app.css):
```
/* 0993: preview banner, v2 pages do not load app.css */
body.v2 .impersonation-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 16px;margin:0 0 20px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
body.v2 .impersonation-copy{flex:1 1 240px;min-width:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;font-size:14px}
body.v2 .impersonation-eyebrow{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--acc-text)}
body.v2 .impersonation-handle{font-size:13px;color:var(--ink3)}
body.v2 .impersonation-bar form{margin:0;flex:0 0 auto}
body.v2 .impersonation-bar .btn{white-space:nowrap}
/* 0993: dashboard calendar legend and bar tooltips */
.cal-legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:8px 0 0;font-size:13px;color:var(--ink3)}
.cal-legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:baseline}
.cal-legend .l-ok i{background:var(--ok)}.cal-legend .l-warn i{background:var(--warn)}.cal-legend .l-grey i{background:#c9c9c3}
.cd small{display:block;font-size:10px;font-weight:400;color:var(--ink3)}
```
Check each token exists: `grep -c -e "--acc-text" -e "--ok:" -e "--warn:" App/app/static/tokens.css App/app/static/app2.css | tail -30`; if one is missing use `var(--ink)`.
3. `base.html` line 22: replace the version value after `/static/app2.css?v=` with `20261107-0993`. Check: `grep -n "app2.css?v=" App/app/templates/base.html | tail -30`.
4. `needs_you.py`: directly after the line `arrival = validation.parse_iso_date(_get(reservation, "date_from", ""))` insert:
```
    departure = validation.parse_iso_date(_get(reservation, "date_to", ""))
    if departure is not None and departure <= today:
        return None  # the guests have left or leave today: asking them to register is stale
```
Add one test next to the existing `stay_line` tests (find: `grep -rln "stay_line" App/tests | tail -30`): a stay with `date_to == today`, status in `_GUEST`, `urgency` not overdue, expects `None`; and the same stay with `date_to == today + 1 day` still returns a line. Copy the fixture style of the neighbouring test; do not invent helpers.
5. `routes/admin.py`: replace the single line `label = event["label"] or _OVERVIEW_SOURCE_NAMES.get(source) or host_i18n.translate(lang, "calendar.kind_stay")` with:
```
            raw_label = (event["label"] or "").strip()
            blocked = bool(re.match(r"^(?:[!⚠]\s*)?(?:closed(?:\s*[-–]\s*not available)?|not available|airbnb\s*\(not available\)|blocked|unavailable)$", raw_label, re.IGNORECASE))
            if blocked:
                css = "b-grey"  # one colour for every placeholder block, whatever the stay tone
                label = host_i18n.translate(lang, "dashboard.calendar.blocked")
            else:
                label = raw_label or _OVERVIEW_SOURCE_NAMES.get(source) or host_i18n.translate(lang, "calendar.kind_stay")
```
Make sure `import re` exists at the top of the file (`grep -n "^import re" App/app/routes/admin.py | tail -30`); add it in the import block if absent. In the `placed.append(...)` dict add `"title": raw_label or label,` (full text for the tooltip).
6. `dashboard.html`: in the `<a class="bar ...` anchor add `title="{{ bar.title }}"` right after `data-row="{{ bar.row }}"`. In the `.cgrid` header line replace `{{ wd[d.weekday()] }} {{ d.day }}</div>` with `{{ wd[d.weekday()] }} {{ d.day }}{% if loop.first or d.day == 1 %}<small>{{ d.day }}.{{ d.month }}.</small>{% endif %}</div>`. After the closing `</div>` of `<div class="scroll-x ov-cal-block...">` (just before the `<p class="ov-cal-more` line) insert:
```
  <p class="cal-legend ov-cal-block{{ ' ph-hide cal-hide' if cal_view }}"><span class="l-ok"><i></i>{{ t('dashboard.calendar.legend.done') }}</span><span class="l-warn"><i></i>{{ t('dashboard.calendar.legend.action') }}</span><span class="l-grey"><i></i>{{ t('dashboard.calendar.legend.grey') }}</span></p>
```
7. `host_i18n.py`: directly after each `dashboard.calendar.full` line add, en:
```
        "dashboard.calendar.blocked": "Blocked",
        "dashboard.calendar.legend.done": "Reported",
        "dashboard.calendar.legend.action": "Needs you",
        "dashboard.calendar.legend.grey": "Blocked or waiting",
```
cs (same indentation):
```
        "dashboard.calendar.blocked": "Blokováno",
        "dashboard.calendar.legend.done": "Nahlášeno",
        "dashboard.calendar.legend.action": "Čeká na vás",
        "dashboard.calendar.legend.grey": "Blokováno nebo čeká",
```
Use no em dashes. Do not touch `host_vi_i18n.py`.

## 5. Do not touch

`App/app/static/app.css`, `dashboard-calendar.*` (a different widget), `needs_you` copy keys, any other brief's files. No new dependency, no new outbound request, no new personal-data field.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_needs_you*.py tests/test_host_*.py tests/test_host_geometry.py tests/test_dashboard_calendar*.py -q --tb=short -x 2>&1 | tail -30` (browser files: 0 skipped; set `UBYHOST_REQUIRE_BROWSER=1`).
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_*_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`; open `/tmp/shots/layout-lint/<dashboard page>-{390,768,1280}.png`.
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Heading reads "What needs you" with a visible gap before the badge (screenshot).
- [ ] New test: stay with `date_to == today` gives no "Guests not registered" line.
- [ ] Preview banner at 390/768/1280: one bordered strip, text wraps, "Exit preview" never touches the text.
- [ ] Blocked bars read "Blocked", are all grey, have a tooltip with the original text; legend line shown; first day and each 1st show "7.11." under the weekday.
- [ ] Layout lint: zero findings, 0 skipped. 390 px screenshot of the dashboard in the report, and per page "390: ...; 768: ...; 1280: ..." in the PR. Design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found; a test fails twice; 25 tool calls; a file outside section 3 needs a change; the layout lint reports a finding you cannot fix inside section 3 (never silence it).

## 9. Report

Write `docs/tasks/0993-report.md` (600 tokens at most), set `Status: review`: files changed, last 5 lines of each command, section 7 ticked, deviations. Hand merge and deploy to the owner.
