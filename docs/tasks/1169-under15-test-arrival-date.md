# 1169: under-15 birth-date test reads the seeded arrival date, not import-time today

Status: todo
Depends on: none | Base commit: claude/zealous-maxwell-a7ub54 HEAD | Branch: task/1169-under15-arrival
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

In `test_typing_and_changing_the_birth_date`, take the arrival date from the seeded booking in the database instead of the module constant `ARRIVAL`. CI on PR #950 failed (`browser shard 2`, `test_under15_signature_1090_browser.py:294`, "14 on arrival keeps the pad", `(False, True) == (True, False)`) because the shard crossed Prague midnight. Test-only change; no `App/app` file changes.

## 2. Context

Root cause. `App/tests/test_under15_signature_1090_browser.py:103`:

```python
ARRIVAL = claim.prague_today()  # the seeded booking starts today
```

is computed once at import. The shard ran 23 minutes and ended 23:09 UTC (00:09 Prague). `_stay` calls `_fee_seed` -> `_seed` (`App/tests/test_guest_browser_e2e.py:189-221`), which sets `date_from = claim.prague_today().isoformat()` at seed time, so the booking got the next day. The page compares the birth date against the stay's own arrival (`App/app/static/signature.js` ~251-275, "The rule is the arrival day, never today"), so the test's `ARRIVAL` was one day off and the "day before the 15th birthday" case landed on the 15th.

Other uses of `ARRIVAL` in the file (checked):
- Line 104 `CHILD` = 10 years before, line 105 `TEEN` = 16 years before: a one-day shift cannot change under/over 15 for these. Not boundary-sensitive. Leave them.
- Only `test_typing_and_changing_the_birth_date` (lines 286, 288, 291) uses `ARRIVAL` directly. No other test in the file does.

Follow-ups, NOT in this brief (do not fix): other browser tests call `claim.prague_today()` but only inside functions (no module-level constant), so the midnight gap there is seed-to-assert, not import-to-seed. Files: `test_0765_phone_today_window_browser.py:43`, `test_0766_phone_stays_browser.py:19`, `test_0890_speed_pages_browser.py:201`, `test_0976_audience_browser.py:49`, `test_host_alert_stack_browser.py:116`, `test_host_controls_browser.py:60,282-283`, `test_host_quiet_dashboard_browser.py:46,99`, `test_host_stay_actions_browser.py:54`, `test_host_wide_geometry_browser.py:106`. The only module-level `= claim.prague_today()` in `App/tests/*browser*.py` is the one fixed here. Orchestrator logs the in-function list in known-issues.

Existing imports in the file already cover this: `from datetime import date`, `from app import claim, db, ...`. `claim` stays used (line 103 stays).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_under15_signature_1090_browser.py | edit | read `arrival` from the DB in one test |

No other file may change.

## 4. Steps

1. Edit `App/tests/test_under15_signature_1090_browser.py`. Find this anchor verbatim (STOP if absent):

```python
def test_typing_and_changing_the_birth_date(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "typing")
    page, guest = _open(browser, live_server, token, stay)
```

Replace with:

```python
def test_typing_and_changing_the_birth_date(live_server, browser, monkeypatch):
    token, stay = _stay(monkeypatch, "typing")
    # The page's rule is the stay's own arrival day. Read it from the seeded booking: a
    # clock taken at import can be a day behind when the shard crosses Prague midnight.
    arrival = date.fromisoformat(db.query_one("SELECT date_from FROM reservation WHERE id = ?", (stay,))["date_from"][:10])
    page, guest = _open(browser, live_server, token, stay)
```

2. In the same test, replace these three lines (each verbatim, each once):

```diff
-        retype(f"0000{ARRIVAL.year - 14}", (False, True))
+        retype(f"0000{arrival.year - 14}", (False, True))
```
```diff
-        retype(f"0000{ARRIVAL.year - 15}", (True, False))
+        retype(f"0000{arrival.year - 15}", (True, False))
```
```diff
-        fifteen = _years_before(ARRIVAL, 15)
+        fifteen = _years_before(arrival, 15)
```

3. Confirm only the module constants remain: `grep -n "ARRIVAL" App/tests/test_under15_signature_1090_browser.py | tail -30` shows exactly lines 103, 104, 105.

## 5. Do not touch

`App/app/**`, `signature.js`, `test_guest_browser_e2e.py`, `CHILD`/`TEEN`/`ADULT`, any other test. Do not install playwright. Hard rule 7 (screenshots) does not apply: no template, CSS or guest-page change.

## 6. Commands

From the repo root:

```
cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 tests/test_under15_signature_1090_browser.py 2>&1 | tail -30
```
Expected: `All checks passed!`

```
cd App && .venv/bin/python -m py_compile tests/test_under15_signature_1090_browser.py 2>&1 | tail -30
```
Expected: no output.

```
cd App && .venv/bin/python -m pytest tests/test_under15_signature_1090_browser.py -q --tb=short -x 2>&1 | tail -30
```
Playwright is NOT installed in `App/.venv` here: if it errors on the playwright import or skips, do not install it; write "run by CI" in the report. Bite: not reproducible locally (needs playwright and a clock at Prague midnight); state "bite proven by CI failure on 864dfb0c".

```
python3 scripts/context_lint.py | tail -3
```
Expected: OK.

## 7. Acceptance

- [ ] `git diff --stat` shows only `App/tests/test_under15_signature_1090_browser.py`, 4 changed lines of logic (1 added block of 3 lines, 3 replaced).
- [ ] ruff and py_compile clean.
- [ ] `grep -n "ARRIVAL"` in the file shows only lines 103-105.
- [ ] context_lint OK.
- [ ] Report says the browser test runs in CI (shard 2), not locally.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed (including playwright);
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1169-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/tests/test_under15_signature_1090_browser.py`, the `test_typing_and_changing_the_birth_date` hunk only.

## Owner steps

None. The orchestrator opens the PR and merges with `scripts/merge-pr-on-green.sh` when CI is green.
