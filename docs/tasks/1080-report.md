# 1080 report

Status: blocked
Branch: claude/ecstatic-feynman-6iy30u (brief's branch name ignored, per owner). Local commits only, no push, no PR.

## Done
- Steps 1 to 3 (earlier commits 525ffa3, 017e519, aa57764): unchanged.
- Step 4 (commit "1080 step 4"): 4 tests in App/tests/test_login_session_persistence.py. The failing test is fixed: it now patches the template global `turnstile_site_key` with monkeypatch.setitem (the import-time global in templating.py is not changed). The three other widget tests got the same patch, so the hide test is meaningful. `templating` added to the test file's import.
- Step 5 (commit "1080 step 5"): decisions.md line appended, text from the brief, dated 2026-11-10.
- Owner steps (Cloudflare) not done, per instruction.

## Files changed
- App/tests/test_login_session_persistence.py
- docs/context/decisions.md
- docs/tasks/1080-report.md

## Test results (section 6)
1. `tests/test_login_session_persistence.py tests/test_login_*.py ...` (-x): last lines
   `........`, `....`, `212 passed in 22.33s`. 0 skipped.
2. `tests/test_host_*.py tests/test_host_geometry.py`: `82 passed, 26 skipped, 1 warning in 12.91s`.
   FAIL against "0 skipped": every skip is `could not import 'playwright.sync_api': No module named 'playwright'`. App/.venv has no Playwright.
3. `tests/test_layout_lint_browser.py` (UX gate): not run. Collection error `ModuleNotFoundError: No module named 'playwright'`.
4. `python3 scripts/context_lint.py`: `context lint: OK` (only WARN lines, none from this change except the decisions.md note about open briefs).

## §7 acceptance
- [x] Valid device cookie: no widget (0 elements). No cookie: widget (1 element). Confirmed in the browser and by the tests.
- [x] Forged or stale cookie shows the widget (test passes).
- [x] Device cookie for another e-mail, POST, gives 403 and the widget (test passes).
- [x] Existing server-skip tests pass unchanged.
- [x] Staging password path unchanged (not touched).
- [ ] Commands 2 and 3 green with 0 skipped: NOT met (Playwright missing from App/.venv).
- [x] Context lint passes.
- [ ] Design-system checklist in the PR: no PR opened.

## Screenshots (Node Playwright, /opt/node-tools, Chromium /opt/pw-browsers; not in the repo)
Served by uvicorn on 127.0.0.1:8765 from a throwaway script. Challenges host blocked, so the widget is an empty container.
- With valid device cookie (no widget): 
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-cookie-390.png
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-cookie-768.png
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-cookie-1280.png
- Without cookie (widget shown):
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-nocookie-390.png
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-nocookie-768.png
  /tmp/claude-0/-home-user-jsfpecharoperations/f88325f1-e840-5acd-a6a1-0c73b2c75083/scratchpad/shots/login-nocookie-1280.png
390 px, what I saw: with the cookie, the e-mail form is directly under the passkey error, with the Send button right after the field and no widget gap. Without the cookie, a widget gap sits between the field and the button. The spacing looks right in both. Not yet reviewed against the design system.
Observation (not from this change, not investigated): both shots show the passkey error "That passkey did not log you in" on a plain GET /login.

## Deviations
- Done: steps 1 to 5. Left: §7 browser items, the PR, and owner steps.
- UBYHOST_SHOTS_DIR set to the scratchpad, not /tmp/shots.
- Screenshots taken with Node Playwright and a seed script (scratchpad/shots_seed.py), not through pytest. The seed script wrote a test host row to the configured database.
- Commit attribution uses Claude Sonnet 5.5 as the brief's owner message asked.

## Questions for the reviewer
1. Playwright is not importable from App/.venv. Install it there (owner decision, a dependency) or run the browser tests from another environment? Without it, 26 host tests and the UX gate are skipped or not run.
2. The security hook noted the Turnstile api.js script tag has no SRI. Not changed; Cloudflare's versioned api.js cannot be pinned by hash. Reviewer decides.
3. The passkey error on a plain GET /login: is that expected for this state, or a stale flash?

## Owner steps left
- Cloudflare dashboard steps in the brief (not done).
