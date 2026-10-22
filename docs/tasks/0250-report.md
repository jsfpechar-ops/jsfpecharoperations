# 0250 report

Status: blocked
Branch: claude/project-thread-cjz5cc | Base: c1ebb74 | Steps 1 to 4 done.

## Files changed
- App/app/templates/_property_overview.html (Open pill on 6 cards, Guest links title stretched)
- App/app/static/host.css (card, pill, stretched link, touch, facility example styles)
- App/app/templates/base.html (host.css key 20261022-0250)
- App/tests/static_versions.json (regenerated with --write)
- App/app/templates/_property_editor.html and App/app/templates/setup_wizard/police.html (facility help example)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (name_hint changed, name_example added)
- App/tests/test_0250_property_cards.py (new, 3 tests)

## Commands (last lines)
- cmd 1 (0250, reporting help, static versions): `10 passed, 1 warning`
- cmd 2 (navigation + onboarding wizard browser): `3 failed, 79 passed`, 0 skipped. Failures: test_three_views_four_groups_one_editor_and_unique_ids, test_create_offers_the_calendar_first_and_works_without_js, test_property_views_fit_every_width_and_sidebar.
- cmd 3 (design guardrails + host-wide geometry browser): `16 passed`, 0 skipped.

## Section 7
- [x] 7 cards carry the Open pill (text at 640 px and up, chevron circle below). Not screenshot-checked.
- [x] Guest links card opens settings through the stretched link; Copy link is its own button (z-index 1).
- [x] Facility help shows the example with the highlighted first line (EN, CS, VI strings).
- [x] host.css key bumped, manifest regenerated.
- [ ] All section 6 commands green: 3 failures in cmd 2.

## Deviations
Done: steps 1 to 4. Stopped after cmd 2 showed 3 failures.
The same 3 tests fail on the base commit c1ebb74 (checked in a temporary worktree, now removed), so they predate this branch. They are not caused by 0250. Not fixed: the brief does not name them.
Step 3 i18n: host_i18n.py has two name_hint lines (EN and CS); both were edited.

## Questions
- Do the 3 failing navigation tests stay out of scope for 0250, or should they be fixed in a separate task?
- No screenshots taken (orchestrator task per section 7).

## Owner steps left
- Decide on the 3 pre-existing failures, then re-run cmd 2 before merge.
