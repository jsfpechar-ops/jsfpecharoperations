# 1001: Calendar pill text, copy-link button, focus rings, guest name link

Status: todo
Depends on: 0998 (merged first: it added `calendar.no_forms` and the sheet placeholder code) | Base commit: HEAD of main after 0998 | Branch: task/1001-ux-followups
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner feedback (screenshots in the chat): a calendar pill is just a booking, so the "Booked" / "Blocked" text and the legend line go; the Properties "Copy link" button is always visible; the heavy red rings on the Properties row, the Export dialog and the date input become the calm design-system ring; the guest name on the stay page opens the guest. Change only what is listed. Do not touch the multiple-Doručenka topic.

## 2. Context

Rules: light mode only; copy rule 9; UX gate (AGENTS rule 10); copy only in `host_i18n.py` (en + cs; not `host_vi_i18n.py`); no em dashes. Read nothing else. Every anchor must be found verbatim, else STOP (§8).

**A. Pill text.** `App/app/routes/admin.py` lines 600-612 (inside `_overview_calendar_rows`):
```
            blocked = bool(re.match(r"^(?:[!⚠]\s*)?(?:closed(?:\s*[-–]\s*not available)?|not available|airbnb\s*\(not available\)|blocked|unavailable)$", raw_label, re.IGNORECASE))
            if blocked:
                css = "b-grey"  # one colour for every placeholder block, whatever the stay tone
                label = host_i18n.translate(lang, "dashboard.calendar.blocked")
            else:
                label = raw_label or _OVERVIEW_SOURCE_NAMES.get(source) or host_i18n.translate(lang, "calendar.kind_stay")
            guests = int(event.get("guests") or 0)
            if guests > 0:
                label += f" · {guests}"
            placed.append((col_start, col_end, {"css": css, "col_start": col_start, "col_end": col_end, "overdue": overdue, "label": label, "title": raw_label or label, "url": event["url"]}))
```
`_OVERVIEW_SOURCE_NAMES = {"airbnb": "Airbnb", "booking": "Booking"}` is defined at line 573.

`App/app/templates/dashboard.html` line 103 is the legend `<p class="cal-legend ov-cal-block...">...</p>` (uses `dashboard.calendar.legend.done`, `.action`, `.grey`; no other user).

`App/app/static/dashboard-calendar.js` lines 666-667 (the sheet; `labelFor` at line 212 already hides placeholders on pills and stays unchanged):
```
    const placeholder = /^(?:[!⚠]\s*)?(?:closed(?:\s*[-–]\s*not available)?|not available|airbnb\s*\(not available\)|blocked|unavailable)$/iu.test((event.label || "").trim());
    if (event.label) container.append(el("p", "cal-detail-label", placeholder ? labels.blocked : event.label));
```
`App/app/templates/_dashboard_calendar.html` line 140: `  'blocked': t('dashboard.calendar.blocked'),`
`App/app/host_i18n.py` (en lines ~9216-9219, cs ~9258-9261): `dashboard.calendar.blocked`, `dashboard.calendar.legend.done`, `.legend.action`, `.legend.grey`, each once per language.
`App/app/static/app2.css` lines 2916-2919: the `/* 0993: dashboard calendar legend and bar tooltips */` comment and three `.cal-legend` rules (find: `grep -n "cal-legend" App/app/static/app2.css | tail -30`; remove only `.cal-legend` rules, keep any other rule in that comment block).
`App/tests/test_host_i18n.py` lines 208-209 assert `dashboard.calendar.blocked` ("Booked" / "Obsazeno"). `test_dashboard_calendar_browser.py` lines 32 and 127 assert placeholder words are absent from pills; they stay valid.

**B. Copy link.** `App/app/static/app2.css` line 311 (one line, exact start):
`@media (hover:hover) and (min-width:1024px){body.v2 .props-card tbody tr .btn.sm.ghost{opacity:0;transition:opacity .15s}body.v2 .props-card tbody tr:hover .btn.sm.ghost{opacity:1}body.v2 .props-card tbody tr:focus-within .btn.sm.ghost{opacity:1;transition:none}}`
preceded by the comment line `/* 0532: copy-link button in each list row shows on hover from 1024 px (mockup); always visible on touch and below 1024 px */`. No test asserts the hidden state (`test_host_controls_browser.py` line 238 asserts opacity 1 on touch only).

**C. Focus rings.** `App/app/static/app2.css` lines 189-193:
```
/* 0709 focus: one visible ring for every control */
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible,tr:focus-visible{outline:2px solid #d0452d;outline-offset:2px}
body.v2 .btn.copy-btn:focus-visible{outline:2px solid #d0452d;outline-offset:2px}
body.v2 .ui-btn.copy-btn:focus-visible{outline:2px solid #d0452d;outline-offset:2px}
.clickable-row:focus-within{outline:2px solid #d0452d;outline-offset:-2px}
```
Causes: line 193 outlines the whole Properties row whenever anything inside has focus (including a mouse click on Copy link); the `csv-export-dialog` (`App/app/static/app2.css` line 907, opened by `dialog.showModal()` in `app.js` line 671-685) gets the browser's default dialog focus outline; inputs use the 2px red outline. The shared token is `--focus-ring-2` (tokens.css line 142: `0 0 0 1px var(--sand-0), 0 0 0 4px rgba(200, 90, 82, 0.32)`), already used by `.havel-*` and `.cal-close` focus rules.

**D. Guest name.** `App/app/templates/reservation_detail.html` line 203 (inside `{% for row in guest_rows %}`):
```
        <b>{{ guest.first_name or '' }} {{ guest.surname or '—' }}</b>{% if guest.is_lead %} <span class="pill">{{ t('stay.detail.guests.lead') }}</span>{% endif %}
```
and the menu item (line ~221, stays as is): `<a class="row-menu-item" href="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}" role="menuitem">{{ t('stay.detail.guests.edit') }}</a>`

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | placeholder pill label |
| App/app/templates/dashboard.html | edit | remove legend line |
| App/app/static/dashboard-calendar.js | edit | sheet label |
| App/app/templates/_dashboard_calendar.html | edit | drop `blocked` label; bump js `?v=` |
| App/app/host_i18n.py | edit | remove 4 keys x 2 languages |
| App/tests/test_host_i18n.py | edit | remove the 2 asserts |
| App/app/static/app2.css | edit | copy-link rule, legend rules, focus rules |
| App/app/templates/base.html | edit | bump `app2.css?v=` |
| App/app/templates/reservation_detail.html | edit | guest name link |

No other file may change.

## 4. Steps

1. `admin.py`: replace the block in §2A (from `if blocked:` through the `placed.append(...)` line) with:
```
            if blocked:
                css = "b-grey"  # one colour for every placeholder block, whatever the stay tone
                label = _OVERVIEW_SOURCE_NAMES.get(source, "")  # a placeholder has no name: platform if known, else an empty pill
            else:
                label = raw_label or _OVERVIEW_SOURCE_NAMES.get(source) or host_i18n.translate(lang, "calendar.kind_stay")
            guests = int(event.get("guests") or 0)
            if guests > 0:
                label = f"{label} · {guests}" if label else f"· {guests}"
            placed.append((col_start, col_end, {"css": css, "col_start": col_start, "col_end": col_end, "overdue": overdue, "label": label, "title": label or host_i18n.translate(lang, "calendar.kind_stay"), "url": event["url"]}))
```
Check: `grep -n "dashboard.calendar.blocked" App/app/routes/admin.py | tail -30` prints nothing.
2. `dashboard.html`: delete line 103 entirely (the whole `<p class="cal-legend ...">...</p>`). Check: `grep -n "cal-legend\|calendar.legend" App/app/templates/dashboard.html | tail -30` prints nothing.
3. `dashboard-calendar.js`: replace lines 666-667 with:
```
    const placeholder = /^(?:[!⚠]\s*)?(?:closed(?:\s*[-–]\s*not available)?|not available|airbnb\s*\(not available\)|blocked|unavailable)$/iu.test((event.label || "").trim());
    if (event.label && !placeholder) container.append(el("p", "cal-detail-label", event.label));
```
Check: `grep -n "labels.blocked" App/app/static/dashboard-calendar.js | tail -30` prints nothing.
4. `_dashboard_calendar.html`: delete line 140 (`  'blocked': t('dashboard.calendar.blocked'),`). Then bump the cache key of `dashboard-calendar.js`: `grep -n "dashboard-calendar.js?v=" App/app/templates/*.html | tail -30`, replace the value after `?v=` with `20261107-1001` in each file found (match only up to `?v=`). Check the grep again.
5. `host_i18n.py`: delete the 4 lines per language (`dashboard.calendar.blocked`, `dashboard.calendar.legend.done`, `dashboard.calendar.legend.action`, `dashboard.calendar.legend.grey`; 8 lines total). Check: `grep -rn "dashboard.calendar.blocked\|dashboard.calendar.legend" App/app | tail -30` prints nothing.
6. `test_host_i18n.py`: delete lines 208-209. If that leaves a test function without an assert or with a dangling blank body, delete the whole function instead. Check: `grep -n "calendar.blocked" App/tests/test_host_i18n.py | tail -30` prints nothing.
7. `app2.css` copy link: delete the comment line and the line-311 `@media` rule from §2B (two lines). Replace them with the single line:
```
/* 1001: the copy-link button in each list row is always visible */
```
8. `app2.css` legend: delete the three `.cal-legend` rules (find with the grep in §2A). Keep the `/* 0993 ... */` comment only if another rule remains under it; otherwise delete it too.
9. `app2.css` focus: replace the line-193 rule `.clickable-row:focus-within{outline:2px solid #d0452d;outline-offset:-2px}` with:
```
/* 1001: a clickable row shows a ring only when a link or control inside is keyboard-focused, never on mouse focus or hover */
.clickable-row:focus-within{outline:0}
.clickable-row:has(:focus-visible){outline:2px solid var(--acc);outline-offset:-2px;border-radius:8px}
```
Then append at the very end of `app2.css` (after step 7 and 8 edits; last line must stay a complete rule):
```
/* 1001: calm focus. Dialogs are focused by script (no ring on the dialog itself); fields and buttons get the 2px accent ring on keyboard focus only. */
body.v2 dialog:focus,body.v2 dialog:focus-visible{outline:0}
body.v2 .csv-export-dialog input:focus,body.v2 .csv-export-dialog select:focus{outline:0}
body.v2 .csv-export-dialog input:focus-visible,body.v2 .csv-export-dialog select:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-color:var(--acc)}
body.v2 .csv-export-dialog .ui-btn:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
```
Also change line 190 only by removing `,tr:focus-visible` from its selector list (rows are not tab stops; `<tr tabindex>` rows keep the `:has` rule above). Keep the rest of line 190. Check: `grep -n "tr:focus-visible\|clickable-row:focus-within\|clickable-row:has" App/app/static/app2.css | tail -30` shows the two new rows only. `--acc` is defined in app2.css (used at line 1397); if `grep -n "\-\-acc:" App/app/static/*.css | tail -30` finds nothing, use `#d0452d` instead.
10. `base.html` line 22: change `app2.css?v=20261107-1002` to `app2.css?v=20261107-1010`. Check: `grep -n "app2.css?v=" App/app/templates/base.html | tail -30`.
11. `reservation_detail.html` line 203: replace the `<b>...</b>` with:
```
        <b><a href="/guests/{{ guest.id }}?return_to=/reservations/{{ reservation.id }}">{{ guest.first_name or '' }} {{ guest.surname or '—' }}</a></b>{% if guest.is_lead %} <span class="pill">{{ t('stay.detail.guests.lead') }}</span>{% endif %}
```
Leave the ⋮ menu untouched. Check: `grep -n "return_to=/reservations" App/app/templates/reservation_detail.html | tail -30` shows the new link and the menu item.

## 5. Do not touch

`host_vi_i18n.py`, `labelFor` in the JS, pill grid and lane logic, `dashboard-calendar.css`, `calendar.no_forms` and `calendar.unknown` keys, the menu markup, any other template. No new dependency, outbound request or personal-data field.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_dashboard_calendar.py tests/test_dashboard_calendar_browser.py tests/test_host_stay_actions_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_0525_stay_detail.py tests/test_0912_stay_detail.py tests/test_host_controls_browser.py tests/test_host_list_cards_browser.py tests/test_design_guardrails_browser.py tests/test_static_versions.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30` with `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped. If a file does not exist, drop it from the list.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`; open `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` for the dashboard, calendar, properties (apartments), stay detail (reservation) and housebook pages (the Export dialog if a shot exists; else say so).
- Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] No "Booked", "Blocked", "CLOSED", "Not available" or legend line on the dashboard bars, the sheet or the calendar page; a placeholder pill reads the platform name (Airbnb, Booking), `· N`, or is empty with a `title`.
- [ ] Copy link is visible in every Properties row at 1280 px without hover.
- [ ] Properties row, Export dialog and date input show no heavy outline on mouse use; keyboard Tab shows a 2px accent ring on the focused control only.
- [ ] The guest name on the stay page is a link to the same URL as the menu item "Edit details"; the menu still works.
- [ ] Layout lint zero findings, 0 skipped. PR body: per page "390: ...; 768: ...; 1280: ..."; design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found (0998 not on your branch: stop); a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change; a lint finding you cannot fix inside §3 (never silence it); a test other than the ones named asserts the removed text.

## 9. Report

Write `docs/tasks/1001-report.md` (600 tokens at most), set `Status: review`: files changed, last 5 lines of each command, §7 ticked, deviations, anything you still see in the screenshots. Hand merge and deploy to the owner.
