# 0954 report: TTLock setup

Status: review (branch claude/friendly-albattani-ndmdji, not pushed). Commits: 247da152, a37b40f0, d96c8c5f, 27b17ea7, ca235c44, 6e31881a, 69de95a9, 69d7fe14, f87e490a, c0725e6d, 88784ee6.

## Files changed
- App/app/host_i18n.py, App/app/host_vi_i18n.py: step 1 and 2 copy (eAdmin first), state headlines and reasons, health keys.
- App/app/routes/admin.py: `door_code.state` and `first_lock`; `POST /apartments/{id}/door-codes` (Turn on / Turn off); first-connection default-on in `smart_locks_refresh`.
- App/app/property_health.py: door row reads `state`.
- App/app/templates/_property_editor.html: status block, state line, warning line (off only), stars, switch removed.
- App/app/static/app2.css (block `/* 0954 ttlock */`), App/app/templates/base.html (`?v=20261104-0954a`), App/tests/static_versions.json.
- Tests: test_ttlock_setup_0954.py (21), test_ttlock_setup_0954_browser.py (12), updated test_smart_locks_page.py, test_door_code_one_lock_one_property.py, test_property_navigation_browser.py, test_0541_property_page_phone_browser.py.
- Screenshots: docs/tasks/screenshots-0954/ (12 PNG, state x width).

## Tests (last runs, chromium)
- test_ttlock_setup_0954.py + test_smart_locks_page.py: 37 passed.
- 0954 browser + test_layout_lint_browser.py: 16 passed, 0 skipped (chromium only).
- test_0541 phone: 5 passed. Navigation browser: 12 passed.
- Not re-run after the final copy change: test_host_i18n (3 known failures on a clean tree).
- Webkit: not installed here; all new browser tests are chromium-only and untested on webkit.

## Per-width notes (viewed)
- 390: on (green, Turn off, Lock online) looks right; offline (amber, "lock offline", reconnect sentence, Turn off) is clear; off (grey, Turn on) seen at 768.
- 768: off (grey, red Turn on, full width) fits; offline viewed.
- 1280: times (amber, waiting for times, reason, Turn off) and offline viewed; button and block sit on one row.
- Not viewed: on-768/1280, off-390/1280, times-390/768. Screenshots exist.

## Deviations
- Copy keys added in step 4; step 6 reused them. Warning line shown only in off state (avoids a second copy of the times reason).
- `health.door.fix` key added (not in the brief).
- Offline reason shows only the reconnect sentence (no "Lock offline" repeat of the headline). The existing reconnect notice under the lock select still repeats it: pre-existing copy, left alone.
- Step 5: default-on also skips a lock already used by another property.
- No main check-in/out labels exist in the templates, so no extra stars there.
- host.js still has dead code for the removed switch (not touched).

## Checklist (design-system, honest)
- [x] Page extends host page; no inline style in the new block.
- [x] One Save per form; the lock buttons are their own forms.
- [x] 390/768/1280: no sideways scroll (browser test).
- [x] test_layout_lint_browser green, 0 skipped (chromium only).
- [x] CS and EN keys added together; VI too; no em dash.
- [ ] Header action row: not touched.
- [ ] Fine print and "?" placement: not reviewed.
- [ ] Spacing 12 px / 6 px: not measured beyond lint.
- [ ] CI watched to the end: pending.

## Owner questions
1. The TTLock name is one per host, not a fixed UbyHost account. Is the copy button enough?
2. "Lock online" means the connection is accepted and the lock is listed (no live ping). Enough?

## Owner steps left
Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Deploy is manual.
