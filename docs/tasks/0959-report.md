# 0959 report

Status: blocked. Reason: the regression test fails on the first name's letter case. `/relang` re-draws the answers through `validation.normalise_guest`, and `normalise_name` (App/app/validation.py:279) uppercases names by design. The typed first name comes back upper-cased, but the brief's test asserts the typed case.

Branch: codex/0959-guest-draft-language, base 7b0355c. Worktree HEAD: afe7e133 (brief commit).

Changed, NOT committed (step 1 withheld because the test does not pass): App/app/routes/guest.py, App/app/templates/guest/base.html, App/app/templates/guest/form.html, App/app/templates/_signature_script.html, App/app/static/guest.css, App/app/static/signature.js, App/app/i18n.py, App/app/guest_uk_i18n.py, App/tests/test_guest_browser_e2e.py (test appended), App/tests/static_versions.json. All are in the brief's section 3 list. App/.venv is a symlink to the 0958 venv and is not committed.

Commands:
- `.venv/bin/python -c "import app.routes.guest"`: no output, pass.
- `node --check app/static/signature.js`: no output, pass.
- `tests/test_static_versions.py --write`: wrote 49 files, pass.
- `tests/test_static_versions.py` (brief's check run): prints usage, because the script has no check mode. Brief command is wrong; not verified.
- `pytest tests/test_guest_browser_e2e.py -k 0959`: 1 failed, 0 passed, 23 deselected, 0 skipped. Last lines: `E   AssertionError: assert 'SYNTHETICA' == 'Synthetica'` (test line 791), `1 failed, 23 deselected in 7.15s`.
- Guest test-map rows: not run (stopped at the failing test).
- `python3 scripts/context_lint.py`: "context lint: OK", exit 0.
- `git diff --check`: no output, exit 0.

Acceptance:
1. New test passes: NOT MET (fails on name case before the step check).
2. Czech 3 steps / German longer list: NOT VERIFIED (test stopped first).
3. Test-map guest rows, cache tests: NOT VERIFIED.
4. Screenshots 390/768/1280 and open-menu shot: NOT MET (folder /tmp/ubyhost-b01 empty).
5. `git diff --stat` only section 3 files: MET.

Screenshots: none taken, nothing seen.

Deviations:
- Brief static-version check command is invalid (see above).
- Commit trailers: the session attribution rule requires Claude trailers; I used those instead of the brief's Codex trailer and no-model-name rule for the report and status commits.
- Anchors, helpers and CSRF: all verified. The router-level `protect_guest_post` covers the new POST, and the form includes `_csrf`. `_guest_form_raw` and `_stay_dates_from_form` are aliases in routes/guest.py.

Done: edits applied, import and JS syntax checks pass, static manifest regenerated, lint and diff check pass.

Left (owner decision needed, or orchestrator decision):
A. Keep typed name case on `/relang` (re-draw raw values for names, normalise only on save), or
B. Make the test compare names case-insensitively.
Then run the guest rows, take the three screenshots and the open-menu shot, and commit step 1.

Owner actions: none.
