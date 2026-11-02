# 0892 report

Status: review

Not committed, staged or pushed (orchestrator commits). No PR opened.

## Files (App/ paths, from git)

- New: `app/static/auth2.css`, `tests/test_0892_auth_airbnb_browser.py`, `docs/tasks/screenshots-0892/` (12 PNGs: login, login_sent, login_link_expired, two_factor_login, two_factor_setup, two_factor_recovery at 390 and 1280)
- Edited: `app/templates/auth_base.html` (link to auth2.css, version key `20261102-0892c`), `login.html`, `login_link.html` (invite branch only), `two_factor_login.html`, `two_factor_setup.html`, `two_factor_recovery.html`, `tests/static_versions.json` (`--write`)
- Not touched: app.css, components.css, signup*, guest and public pages, routes, Python, i18n.

## Commands

1. `pytest tests/test_0892_auth_airbnb_browser.py -q -rs`: `37 passed, 1 warning in 13.50s` (0 skipped; 6 pages x 6 widths + no-JS login test)
2. Regression set (`test_login_*`, `test_auth_*`, `test_two_factor_*`, signup, copy, logo, static_versions): `2 failed, 158 passed in 8.05s`. Both failures are `test_static_versions.py` (`test_a_changed_static_file_has_a_new_key`, `test_the_manifest_is_current`) and come from `app/static/admin2.css` (brief 0893, another executor): it changed without a bump to `?v=20261102-0893`. Not my file; not touched. Fix: the 0893 executor bumps its key, then `.venv/bin/python tests/test_static_versions.py --write`.
3. `UBYHOST_SHOTS_0892=1 pytest ... -k "390 or 1280"`: `12 passed, 25 deselected in 9.67s`. The screenshots were not opened for review (tool budget).
4. `python3 scripts/context_lint.py`: `context lint: OK`

## §7 acceptance

- [x] Command 1, 0 skipped, widths 320 to 1440
- [ ] Command 2: passes except the two 0893 static-manifest tests (see above)
- [x] `git diff --stat` lists only §3 files plus the new CSS and test (static_versions.json included)
- [x] Screenshots saved (390 and 1280); not visually reviewed by the executor
- [ ] Tap counts: not measured. Expected unchanged (same taps); the keyboard Go/Done key now submits.

## Deviations

- CSS added beyond §4, to meet the brief's own checks: `.auth-card>.auth-title` (expired-link h1 has no title row); lang buttons, `.auth-notice`, `.auth-card .btn` at 16 px; footer and footer links at 14 px; `.auth-card code` at 16 px; `.auth-card .btn` min-height 44 px; the environment banner (`_env_banner.html`, included by auth_base, outside §3) styled through `body.auth-page .env-banner`.
- Test checks: the "?" glyph (12 px) is exempt from the 14 px rule; content of closed `<details>` is not counted as visible (Chromium lays it out); when the h1's last line is short, the "?" gap may be measured from the h1 box edge (8 px flex gap).
- Login form found with `form[action='/login']` (the first form on the page is the language switch, action `/language`).
- Recovery page reached by POST `/account/2fa/setup` as in `test_two_factor_setup_page.py`; not skipped.
- Test uses local copies of helpers (no import of private test helpers).

## Owner decision applied

- Owner: no fine text anywhere. Hero text removed from the desktop illustration (domain label, flow step numbers and labels, the ready float, the body paragraph). Shapes, logo and the h2 stay; the aside stays aria-hidden. The test no longer exempts aria-hidden content.
- Rerun: command 1 `37 passed in 13.81s` (0 skipped). Screenshots at 390 and 1280 refreshed (`12 passed`).
- `static_versions.json --write` still refused: `admin2.css` (0893) changed without its key bump. Rerun once 0893 bumps its key.
## Owner steps left

1. After 0893 merges or bumps `admin2.css`: run `App/.venv/bin/python tests/test_static_versions.py --write` and confirm command 2 is green.
2. Open the PR, check the 390 px screenshots of login and 2FA.
3. On staging, log in once with the magic link and once with 2FA on a phone.
