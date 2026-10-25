# 0403 report

Status: review (reviewer installed the CI Playwright pin 1.63.0 in the venv; browser tests then ran with 0 skipped)

## Files changed

- App/app/guest_guide_import.py: `request_imports`, `request_import` delegates, `sources_left`
- App/app/routes/guest_guide.py: POST `guide_import` reads `booking_url`, `airbnb_url`, legacy `url`; `next=leon` target; `import_sources`, `import_first`
- App/app/templates/guest_guide.html: import section as `import_section()` macro, rendered first or last; two optional fields
- App/app/guest_guide_merge.py: rule 6 wording ("Combine both")
- App/app/host_i18n.py: en and cs copy (help, booking_url, airbnb_url, guide_import_empty, guide_import_same)
- App/tests/test_guest_guide_import.py: new 0403 tests; two assertions updated to the new field names
- App/tests/test_guest_guide_merge.py: one assertion for "Combine both"

## Commits (branch claude/0403-leon-setup-wizard, not pushed)

- 029d578 0403 step 1 (and steps 2 to 7 follow in order)

## Commands

- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `pytest tests/test_guest_guide_import.py tests/test_guest_guide_merge.py tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_design_*.py -q`: 201 passed, 3 skipped
  - SKIPPED tests/test_design_guardrails_browser.py, test_design_setup_wizard_browser.py, test_design_shell_browser.py: "No module named 'playwright'"
- `python3 scripts/design_lint.py`: design lint: OK

## Acceptance (§7)

- [x] One post with both links queues both; refusals queue nothing (tested)
- [x] Only unused platforms get a field; empty, duplicate, used and over-budget are refused with their own message (tested)
- [x] Import section first while it has work, last otherwise (tested)
- [x] Merge rule 6 combines both listings (tested by string check only)
- [ ] §6 passes with 0 skipped: 3 browser tests skipped

## Deviations

- Kept `guest_guide.import.url` in host_i18n.py. It is now unused in app/ (grep), so it can be removed in a later brief.
- No 390 px screenshot was taken (rule 7 asks for one per changed page). Not done in this session.

## Questions

- App/.venv has no playwright, so the three browser design tests skipped. Install is a dependency decision (rule 4), so I did not install it. Owner: confirm CI runs them, or decide on the install.

## Owner steps left

- Decide on playwright for the browser tests (or confirm CI covers them).
- Review and open the PR when ready. Nothing pushed.
