# 0219 (was 0203) report: installable phone app

Status: review

## Files changed
All §3 files, 17 commits (steps 1 to 17), each `0203 step k`. Icons, script, sw.js, pwa.js, offline.html, main.py (import json, routes), base.html, auth_base.html, login.html, settings.html, host_i18n.py, host_vi_i18n.py, test_pwa.py, test_pwa_browser.py, static_versions.json.
Screenshots: /mnt/project-files/pwa/0203/settings-phone-390-{en,cs,vi}.png and offline-390-{en,cs,vi}.png.

## Commands (last lines)
- Step 1: `badge-96.png (96, 96)` ... `icon-maskable-512.png (512, 512)`
- Steps 2, 3: `node --check` no output
- Step 6: `import app.main` no output
- Step 12: `design lint: OK`
- §6.1 (pytest, 8 files): `56 passed, 2 warnings`
- §6.2 (login and passkey tests): `76 passed, 1 warning`
- §6.3 (browser, UBYHOST_REQUIRE_BROWSER=1): `16 passed, 1 warning`, no skips
- §6.4 `python3 scripts/context_lint.py`: `context lint: OK`
- Step 17 `tests/test_static_versions.py --write`: `wrote ... (33 files)`

## §7
- [x] §6 commands 1 to 4 pass, 0 skipped
- [x] Screenshots exist and were looked at: offline pages centred, coral button, nothing cut off. Settings > Phone app group checked in the English screenshot.
- [x] `git diff --stat` lists only §3 files (the brief itself is in the stat from 2f043c8 because it was committed on this branch before step 1)

## Deviations
1. Step 14: the closing-brace anchor `\n}` is not unique in host_vi_i18n.py (4 matches). The first attempt stopped before writing. The strings went before the final `}` at the end of the file, verified.
2. Step 15: `login.html` puts the hint inside `{% if passkeys_enabled() %}`, which is off in the test environment. The test asserts the hint only when the passkey button renders. Step 15 commit was amended.
3. `test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects` fails when run alone (`no such table: apartment`, empty test DB, middleware query). It passes in the §6.1 run, where test_pwa.py initialises the DB first. Not checked against the base commit.
4. Context lint warns that main.py, base.html and host_i18n.py are also named by open briefs 0130 to 0137. Warnings only.

## Questions
- Should test_host_i18n.py initialise the DB itself? (Deviation 3.)

## Owner steps left
None for this brief. After deploy: on iPhone open the app in Safari, Share, Add to Home Screen. On Android Chrome, Settings > Phone app > Install app.
