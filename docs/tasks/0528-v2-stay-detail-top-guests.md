# 0528: Stay page on the v2 shell, part 1: header, facts, guests
Status: todo
Depends on: 0524, 0525, 0718 (all on the base) | Base commit: claude/project-thread-y2e49a | Branch: task/0528-v2-stay-detail
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Move `/reservations/{id}` (`App/app/templates/reservation_detail.html`) onto the v2 shell and rebuild its top half 1:1 from the approved mockups: computer = `docs/design/mockup/ubyhost-redesign-v2.html` `<section data-v="stay">`, phone (< 1024 px) = `docs/design/mockup/ubyhost-phone-v1.html` `<section data-s="pobyt">` (and `pobyt-anna` for a failed stay). Use the mockup's class names (`.head`, `.crumb`, `.sub`, `.btn`, `.btn.ghost`, `h2`, `.card`, `table`, `.pill`, `.top`, `.round`, `.big`, `.facts`, `h2.sec`, `.list`, `.row`, `.ic.ok`, `.ic.warn`, `.t`). Do not restyle shared classes per page. Part 2 (0529) does the police, door code, payment, action bar, settings and tests.

## 2. Context and decisions (orchestrator)
- Read first: `App/app/templates/dashboard.html` lines 1-60 (v2 page pattern), the two mockup sections, and `reservation_detail.html` in ranges (`grep -n '^{# ---\|<section\|{% block' ...`).
- Filing logic is untouchable (rule 1): every form, CTA condition, menu item, banner and the `#stay-link` input keep their exact conditions, actions, names and hidden fields. You change wrappers, classes and placement only.
- **Computer header:** `<div class="head"><div><div class="crumb"><a href="{{ return_to }}">{{ t('stays.title') }}</a> › {{ lead_name or reservation.internal_name }}</div><h1>…</h1><p class="sub">` pill (`v2_status_pill(deadline_cell(progress, check_in), progress, reservation)`; grey state text when inactive) `<span style="margin-left:8px">` property link · dates `</span></p></div>` + right side: the primary `.btn` = the "Now" panel's CTA when it has one (send / fix / receipt, same forms and conditions), otherwise the copy-link button as `.btn`; the copy-link button (if not primary) and the resend-claim form as `.btn ghost`; then the existing `row_menu` (more actions, invoice link moves into it as a `row-menu-item`). Empty the old header blocks as dashboard.html does.
- **The "Now" panel** (`#now`) is removed as a box: its note text (`stay-command-note` logic) moves to 0529's police card, its buttons to the header (above). Keep the `stay_journey_panel` out (not in the mockup); note it in the report.
- **Phone top (< 1024):** `.top` with `<a class="round" href="{{ return_to }}" aria-label="{{ t('stay.detail.back') }}">` back icon and, when the copy button exists, `<button class="round" data-copy="stay-link" …>` share icon (aria-label = copy text); `.big` name; `.sub` = property · source label; the pill in `<div style="margin:0 20px">` as in the mockup. Hide `.head` below 1024 and `.top/.big/.sub-phone` from 1024 up (one rule each in app2.css).
- **Facts** (phone only, mockup `.facts`): Příjezd (`date_from` short weekday + date, `<small>` check-in time if the property has one), Odjezd, Hosté (`progress.expected`), Noci. Existing keys first (`grep -n '"calendar.arrival"\|"stays.table.arrival"' App/app/host_i18n.py`).
- **Guests, computer:** `<h2>{{ t('stay.detail.guests.title') }}</h2>` + `.card` > `table` with th Jméno / Doklad / Registrace / (menu): name (lead badge after it), doc type label (`guest-card-doc` logic from 0525, never the number), the existing state badge rendered as the matching `.pill` (`p-ok` sent/exempt, `p-warn` incomplete/not registered, `p-bad` rejected), and the guest's existing row menu. Rejection errors (`last_errors`) go as `<small>` under the name. Placeholder (not registered) guests are rows too ("Zatím neregistrován" via the existing placeholder key). The "edit count" and "add guest" buttons become `.btn ghost` links on the `h2` line. Keep the claim line (`data-stay-claim`) as a `.card` above the table, minus the resend form (now in the header).
- **Guests, phone:** `h2.sec` + `.list` of `.row`s: `.ic.ok` check icon for sent/exempt, `.ic.warn` "?" otherwise, `.t` with `<b>` name and `<small>` doc type · state text. Rows link to the guest edit page where the computer menu has it.
- The old `guest-cards` markup, its 0525 host2.css rules and the 0525 catalog entries become dead: remove them (lean rule). New CSS only where app2.css lacks a mockup rule (`.crumb`, `.facts`, phone show/hide) in one block `/* 0528 stay page */`, values copied from the mockups. Bump the app2.css key to `20261101-0528`, `--write` the manifest.

## 3. Files
`App/app/templates/reservation_detail.html`, `App/app/static/app2.css`, `App/app/static/host2.css` (remove dead 0525 rules only), `App/app/templates/base.html` (key), `App/tests/static_versions.json` (`--write`), `docs/design/catalog.json`, `App/app/host_i18n.py` / `host_vi_i18n.py` only if a key is missing, report `docs/tasks/0528-report.md`.

## 4. Steps
1. v2 switch, computer header, CTA move, phone top + facts. Commit `0528 step 1`.
2. Guests computer table and phone list; remove old guest-cards markup. Commit `0528 step 2`.
3. CSS block, dead CSS/catalog removal, key, manifest. Commit `0528 step 3`.
4. Commands, report. Commit.

## 5. Do not touch
Police reporting section, door code section, settings section, file-by-hand (all 0529); `_shell_v2.html`, `dashboard.html`, JS, routes.

## 6. Commands (from App/)
`.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_static_versions.py -q --tb=line 2>&1 | tail -20`. Repo root: `python3 scripts/design_lint.py | tail -3; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Every send, fix, receipt, resend, archive and guest-menu form is still in the page with the same action and fields (`grep -c 'action="/reservations/' ` before and after: same count or explained). Tests pass except assertions on removed old markup (`guest-card`, `stay-command`, `#now`): list them in the report, don't edit them (0529 does).

## 8. Stop and ask
Stop if a CTA condition cannot move to the header without changing its logic.

## 9. Report
`docs/tasks/0528-report.md`: status, form count before/after, test tails, departures.
