# 1163 report (executor, cont-1)

Status: review

Done: steps 4 to 9 of docs/tasks/1163-ttlock-error-code-map.md (step 4 revert-bite, step 5 docs, §6 commands, §7 acceptance, §8 stop check, §9 report). Steps 1 to 3 were committed earlier (147d2061, 82475a8c).

Commits: 4ebd1c34 (1163 step 5), this report commit (1163 report). Step 4 changed no files, so no commit.

Files changed since base 4d64e168: App/app/ttlock.py, App/app/door_codes.py, App/app/cleaning_codes.py, App/tests/test_ttlock_error_map.py, docs/TTLOCK.md, docs/plans/ttlock-door-codes.md, docs/tasks/1163-report.md, docs/tasks/1163-ttlock-error-code-map.md (Status), docs/tasks/1163-cont-1.md (Status).

Commands (last lines):
- Step 4 revert-bite (script run from repo root): 9 lines `BITES`: already_gone 3 failed, retry_kinds 2, map_1007 4, map_offline 2, list_1007 2, new_pin 2, clean_retry 1, clean_gone 1, audit_via 1. No NO BITE. `git diff --stat` empty afterwards.
- Step 5 plan and docs scripts: no output. `git diff --stat` on docs: 2 files, 46 insertions, 3 deletions. `grep -n "^### 3.1" docs/plans/ttlock-door-codes.md` -> one line (line 37).
- §6.1 `tests/test_ttlock_error_map.py`: `37 passed in 5.49s`.
- §6.2 test-map row set (door_code, ttlock, smart_locks_page, cleaning, -x): `389 passed, 4 skipped in 103.96s`.
- §6.3 ruff E9,F63,F7,F82,F401,F841 on app tests tools: `All checks passed!`.
- §6.4 `tests/test_no_em_dashes.py`: `4 passed in 1.05s`.

Acceptance (§7):
- [x] Nine BITES lines (step 4).
- [x] Tests 37 passed, parametrized kind test included.
- [x] Commands 2 to 4 pass (see above).
- [x] git diff --stat shows only files of §3 (plus the two brief Status lines and this report).
- [ ] `grep -c '"code_missing"' App/app/ttlock.py` printed 2, not 1 (map line 75 `-1007: "code_missing"` and constant line 98 `CODE_MISSING = "code_missing"`). Not changed; the check's expected count looks wrong, the bite and mapping tests cover the behavior.
- Behavior checkboxes covered by the 37 tests and the bites (not re-verified by hand).

Deviations:
- The brief says steps 6 to 9 exist in §4. §4 of the map has only steps 1 to 5. I read steps 6 to 9 as §6 (commands), §7 (acceptance), §8 (stop check), §9 (report), which is how the brief's own text labels them.
- Scripts were run from the scratchpad copies (extracted from the map), not /tmp, per executor rules.
- The 4 skipped tests: 3 browser files (test_property_navigation_browser.py, test_ttlock_setup_0954_browser.py, test_cleaning_browser.py) skip because `playwright` is not installed in App/.venv. Not installed (new dependency needs an owner decision). 1 sqlite_only skip (test_door_codes_schema.py:105). The browser tests did not run, so their 0-skip rule is not met; this change touches no template or CSS.
- Postgres ran fine (no schema error), no schema apply needed.

Questions: whether the 3 browser files should run in CI (CI has playwright) or needs an owner decision to add playwright locally.

Owner steps left: open the PR (not done here; executor does not push) and decide the open question in the map §2 (TTLock support on type-3 codes) per the map's owner steps.
