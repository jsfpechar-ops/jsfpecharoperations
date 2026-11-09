# qa-fix-host-ui report

Status: review
Branch: claude/qa-fix-host-ui (rebuilt from main; the booking commits that belong to PR #832 were removed)

Done: steps 1 to 3 (A overflow, B phone fix line, C security prompt modal).

Files changed: `_pp_booking_css.html`, `app.js`, `passkeys.js`, `base.html` (no `open`, `?v=20261109-qa1` on app.js and passkeys.js), `templating.py`, `routes/passkeys.py` (new `POST /account/security-prompt/seen`), `static_versions.json`, tests (overflow, fix line, security prompt delay, passkeys, and `mark_security_prompt_seen` in nine browser fixtures).

Findings and fixes:
- Fix-line test failed because of the test, not app.js: the first visible submit was "Archive property" (the Save bar only shows once the form is dirty). It now dirties the fields with an `input` event and clicks `.savebar` Save. Checked it fails against main's app.js and passes with the fix.
- Description assert restored: the template shows the first 400 characters, the rest sits in `<details>`, so the test asserts a 400 run and a 2600 run. Amenity `<li>` asserted whole.
- The modal covers clicks in browser fixtures that never dismissed the old below-the-fold box; those fixtures call `mark_security_prompt_seen`. Tests of the prompt itself do not.

Deviation from PR #824: without JavaScript the dialog is no longer an open box (the brief asks for closed and unmarked). Passkey row and "Not now" (`method=dialog`) are untouched.

Commands (all with `UBYHOST_REQUIRE_BROWSER=1`): cmd 1 47 passed; cmd 2 36 passed; cmd 3 258 passed except `test_host_flash_outcomes::test_browser_renders_saved_warning_as_sticky_amber`, which also fails on main (not ours); cmd 4 4 passed, 0 skipped.

Screenshots: `docs/tasks/screenshots-qa-host-ui/` (390 px, en and cs; 768 and 1280 viewed, not committed).

Owner steps left: merge when CI is green.
