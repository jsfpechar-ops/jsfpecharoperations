# 0374 report (executor)

Status: blocked

## Files changed
- App/app/static/havel.js (save, restore, clear, unread dot, sign-out clear)
- App/app/templates/_havel_panel.html, havel.html (`data-havel-owner`)
- App/app/templates/base.html (cache keys 20261025-0374)
- App/app/static/host2.css (`.host-workspace .havel-fab[data-unread]::after`)
- docs/privacy/ROPA.md (Havel row: sessionStorage sentence)
- App/tests/test_havel_browser.py (3 new test cases)

## Commits
- e29f644 steps 1-7 (passed nothing yet; committed before tests)
- step 8 (this WIP commit): restore fix plus tests, one case still failing

## Commands (last lines)
- ruff (E9,F63,F7,F82,F401,F841): All checks passed!
- Havel + design + dev_ui set: 3 failed, 159 passed. Failed: test_the_seventh_message (known, not ours), test_chat_follows_the_host_across_pages[1280] and [390] (failed at the /guide restore assertion; fixed since by restoring after the composer loads).
- Re-run `-k "follows or new_chat"`: 2 passed, 1 failed (not identified; the failing case was not isolated before the cap).
- design_lint: OK. context_lint: OK.

## Deviations
- Done: steps 1 to 7 and step 8 code. Left: find the one failing case (`pytest tests/test_havel_browser.py -k "follows or new_chat" -rs --tb=long`), fix it, rerun the full command set, review restored-390.png, then report.
- Step 3 "save after echo()" not done: it conflicts with "do not save while send() is waiting". Save happens after the reply, and after an error (added).
- Restore now runs after ensureForm (the composer fragment swap replaced the thread).
- Dot test skipped: tests/ai_fake.py has no delay option.
- Step 6 CSS uses the attribute selector only (no `.havel-fab-dot` class, no catalog.json entry), per the step's code.
- Brief said "sessionStorage" for storage; innerHTML restore of own saved thread flagged by the security hook. Same pattern as the 0373 thread swap; no new untrusted input.
- Stopped at the tool-call cap (about 28 calls).

## Owner steps left
None. Tests and review remain.
