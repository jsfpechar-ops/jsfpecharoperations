# 0796: Finish stay fees (/stay-fees) on v2: 0710 match, no sent/paid marks, old stay-fee test entries

Status: todo
Depends on: 0794 (in branch) | Branch: claude/project-thread-v4nqi5 (work in the main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make `/stay-fees` pass the v2 mockup-match test and the old stay-fee test entries, and remove every "Odesláno"/"Zaplaceno" (sent/paid) mark from the page (owner decision: no marks anywhere).

## 2. Context

- Read `docs/tasks/0794-report.md` (what 0794 left) and `docs/tasks/0795-report.md` item 4 only.
- `App/app/templates/stay_fees.html`: status pills at ~173-176 (desktop) and ~206-207 (phone `row_status`). Delete the `paid` and `sent` branches; the remaining branches (saved version, needs setup, in progress, ready) stay.
- 0710 failures from 0794: `.mh .big, .head h1` width at 320/390 (compare how `reservations.html` / the stays head does it; remove the BOX_OVERRIDES hack in `App/tests/v2_mockup.py` if the real fix makes it unneeded); an `<input>` 139x21 tap target at 1024-1440 (find it with Playwright `getBoundingClientRect`, give it the shared control height); 3-4 findings at 320/390/768 (print them with `-rs --tb=long`).
- Geometry rules (owner, apply here): help "?" on the same line as its title; text >= 16 px from card edges; >= 12 px between text and buttons; row buttons and "···" same height and centre; help label one word ("Otevřít"/"Open").

## 3. Files

| Path | Action |
|---|---|
| `App/app/templates/stay_fees.html` | edit |
| `App/app/static/app2.css` | edit only inside `/* 0794 stay fees v2 */` block |
| `App/tests/v2_mockup.py` | edit only the `stay_fees` entries |
| `App/tests/test_host_wide_geometry_browser.py`, `test_host_geometry.py`, `test_host_list_page_layout_browser.py` | edit only the stay-fee (`fees`, `fees-unset`, month filter) entries: update selectors to the v2 markup, or drop the page from an old-shell-only list with a one-line comment "v2, covered by 0710" |
| `App/tests/test_stay_fee*.py`, `test_fee_setup_compatibility.py` | edit only assertions on removed sent/paid marks or changed markup |
| locale files with `stay_fees.status.sent/paid` | delete those keys only if nothing else uses them (`grep -rn "status.sent\|status.paid" App/app`) |

No other file. Another executor edits other app2.css blocks and other tests at the same time: touch nothing outside this list.

## 4. Steps

1. Remove the sent/paid marks (template + now-unused strings).
2. Fix the 0710 findings one by one, rerunning `-k stay_fees`.
3. Fix the old stay-fee test entries (§3).
4. Screenshots: `UBYHOST_SHOTS...` if the test supports it, otherwise a scratchpad Playwright snippet with the rich-host fixture: `docs/tasks/screenshots-0790/stay-fees-390.png` and `stay-fees-1280.png`.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay_fees -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_fee_setup_compatibility.py tests/test_host_i18n.py -q --tb=short`
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_host_geometry.py tests/test_host_list_page_layout_browser.py -q -rs --tb=short`

## 7. Acceptance

- [ ] No "sent"/"paid" status text on /stay-fees (grep the rendered HTML).
- [ ] Command 1: 0 failed, 0 skipped. Commands 2 and 3: no failure on a stay-fee entry (report any other failure with its name; do not fix it).
- [ ] Two screenshots saved.

## 8. Stop and ask

Write the report as `blocked` if a test fails twice after a fix, a file outside §3 needs a change, or you reach 30 tool calls.

## 9. Report

`docs/tasks/0796-report.md`, 400 tokens at most: files changed, each command's last 5 lines, §7 ticked, deviations. Do not commit or push.
