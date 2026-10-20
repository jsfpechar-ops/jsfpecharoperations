# 0179: guest cards on the stay page use one grid and show repeated facts once

Status: todo
Depends on: 0178 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Owner: "how the guests info is all over the place". On the stay page, each guest card shows two rows of facts on different column lines: row 1 (Date of birth, Citizenship, Document, Purpose of stay) uses four columns, row 2 (Staying, Signature, Entered by) uses three, and Residence abroad sits alone between them with a dashed line. "Staying" repeats the stay's own dates for every guest. Make the card read as one tidy block:

- One fact grid with four equal columns for the whole card. Row 1: Date of birth, Citizenship, Document, Purpose of stay. Row 2: Residence abroad (spans columns 1 and 2), Signature (column 3), Entered by (column 4). Every label and value starts on the same four column lines in both rows.
- "Staying" is shown only when the guest's own stay dates differ from the reservation's dates; in that case it takes column 1 and 2 of a third row. When equal, it is omitted.
- No dashed divider between the rows; one thin line under the header only, as today.

## 2. Context

`App/app/templates/reservation_detail.html` lines 194-290: `<li class="guest-card">` with `<dl class="guest-facts guest-facts-identity">` (4 cells) and `<dl class="guest-facts guest-facts-stay">` (Residence as `.fact-wide`, Staying, Signature, Entered by). Find the CSS with `grep -n "guest-facts\|fact-wide\|fact-extra" App/app/static/*.css | cut -c1-220` and read only those lines. `host2.css` loads last; S1 forbids raw colours, S2 forbids bare px in margin, padding, gap and font-size. Phone (below 640 px): two columns; Residence spans both.

## 3. Files

`App/app/templates/reservation_detail.html`, `App/app/static/host2.css` (append `/* 0179 */`), `App/app/templates/base.html` (host2.css key ending `-0179`), `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (one new test), tests that assert the removed "Staying" text for equal dates (`grep -rln "guests.staying\|Staying" App/tests | head`; change only that expectation), `docs/tasks/0179-*`.

## 4. Steps

1. In the template, merge the two `<dl>` into one `<dl class="guest-facts">` (keep the ids and classes other code or tests rely on; check with grep before renaming anything). Order: Born, Nationality, Document, Purpose, Residence (`.fact-wide`), Signature, Entered by, then Staying only when `(guest.stay_from or reservation.date_from) != reservation.date_from or (guest.stay_to or reservation.date_to) != reservation.date_to` (compare the raw values as the template already does for display).
2. Append CSS: `.host-workspace .guest-card .guest-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3) var(--space-4); }`, `.fact-wide { grid-column: span 2; }`, remove the dashed border between the rows (`border: 0`), and below 640 px `grid-template-columns: repeat(2, minmax(0, 1fr))`. Keep value text wrapping (`overflow-wrap: anywhere`) so long document numbers or addresses never widen a column. Run `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
3. Bump the host2.css key (`-0179`) and run from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Add `test_guest_card_facts_share_four_column_lines` to `test_design_guardrails_browser.py`: use the `wide_host` fixtures like the other tests; open `/reservations/{reservation_id}` for a stay that has guests (`wide_host["reservations"][0]`; if none of the seeded stays has guest cards, find one with `grep -n "guest" App/tests/test_host_wide_geometry_browser.py | head` and use the same one) at 1280 px; for the first `.guest-card`, collect the left `x` of every `dt` and assert that the set of distinct x values (rounded to the nearest 2 px) has at most 4 entries.
5. From `App/` (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_wide_geometry_browser.py -q -rs 2>&1 | tail -8`. Run the unit tests of the files you edited. Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped.
6. Screenshots (390 and 1280) of a stay with guests: use a short Playwright script outside the repo, or `shots.py` if it supports a stay page (`--pages "/reservations/<id>"`); save under `docs/tasks/0179-screenshots/`.
7. Commit: `git add App docs/tasks/0179-* && git commit` with message "0179: guest cards on one four-column grid" and the two trailers given by the orchestrator.

## 5. Do not touch

Header (name, badges, Edit, menu), the guests section title, any other page; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Both rows of facts share four column lines; Staying shown only when it differs; test passes; guards pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0179-report.md`, short; `Status: review`.
