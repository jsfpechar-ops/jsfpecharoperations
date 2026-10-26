# 0405 report: try Leon at the end of the setup wizard

Status: review

## Commits (branch claude/0403-leon-setup-wizard, not pushed)

- cd0683f step 1: `leon.try_reply`, `try_left`, `TRY_MAX = 5` per property per 24 h
- 3930c4e step 2: POST `/apartments/{id}/leon/setup/try` (JSON or page), try context on GET
- 9f140bb step 3: the chat in `leon_setup/try.html` (no JS: form posts the page)
- 2b589d6 step 4: `leon-setup.js` fetch and bubbles; `?v=20261026-0405`
- 78d4446 step 5: en and cs copy in `host_i18n.py`
- 380f50f step 6: `tests/test_0405_leon_try.py` (8 tests)
- c71421f step 7: browser test settles before each screenshot; `try-390.png`, `try-cap-390.png`
- (this commit) 0405 report

## Test tails

- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `pytest test_0405 test_0404 test_leon test_guest_leon_chat test_privacy_first test_design_*`: `209 passed in 121.07s`
- `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium pytest tests/test_0404_leon_setup_browser.py -rs`: `1 passed in 10.25s` (0 skipped)
- `python3 scripts/design_lint.py`: design lint: OK

## Screenshots (390 px)

- docs/tasks/screenshots-0404/cards-390.png (retaken, checked once: one settled page, no overlap)
- docs/tasks/screenshots-0404/try-390.png (empty chat, composer enabled)
- docs/tasks/screenshots-0404/try-cap-390.png (cap reached: composer disabled, cap line)
- Also retaken: switch-on, import, import-waiting, import-1280, done.

## Deviations

- Vietnamese copy not added: the brief names `host_vi_i18n.py` but gives no text. `host_i18n` falls back to English for vi. Owner to supply or confirm.
- Brief template used `havel-bubbles`, `visually-hidden` and `ui_button()`, which are not in the catalog or templates. Used a plain `<ol data-leon-try-log>`, a visible label and `ui-btn ui-btn-secondary`.
- `setup_step_page` body moved to `_step_page(...)` so the POST can render the same page with the question and answer. The GET still uses the same URL and guards.
- Cap copy appears on reload, not in the JS path: when the last message is used, the input disables without showing the cap line until the page is reloaded.
- No foreign-property 404 test; used an unknown id (999999) instead.
- Test file also patches `leon.host_state` to "on" (terms version is not set in the fixture).
- No PR opened and nothing pushed (brief says commit only, never push).
- Commit trailer: the Opus line from the executor instruction was kept, as instructed.

## Questions

- Vietnamese copy for the six `leon_setup.try.*` keys.

## Owner steps left

- Review the branch, then merge with `scripts/merge-pr-on-green.sh` once a PR is opened.
