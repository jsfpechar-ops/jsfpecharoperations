# 0231 report: guest link window

Status: review

## Files changed (App/ diff since 93a23be)

```
 App/app/routes/guest.py                        | 26 ++++++++++++-
 App/app/static/guest.css                       |  3 ++
 App/app/templates/_property_editor.html        |  4 ++
 App/app/templates/guest/base.html              |  2 +-
 App/app/templates/guest/unavailable.html       |  1 +
 App/app/templates/reservation_detail.html      |  3 ++
 App/app/templates/reservations.html            |  4 ++
 App/app/templates/setup_wizard/guest_link.html |  5 +++
 App/tests/test_guest_link_window_0231.py       | 51 ++++++++++++++++++++++++++
 9 files changed, 96 insertions(+), 3 deletions(-)
```

## Commands (last 5 lines)

- Step 1, `test_guest_links_preview.py`: `6 passed`
- Step 2, `test_onboarding_wizard_survival.py`: `24 passed`
- Step 3, `test_host_list_cards_browser.py -rs`: **error, not run**. `BrowserType.launch: Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1243/...`. Chromium is not installed in this container. Not a skip, and the template change is not verified in a browser.
- Step 9, `test_guest_navigation.py`: `31 passed`
- Step 13 and §6 (5 files): `70 passed`

## §7 acceptance

- [x] The 4 new tests pass (`test_guest_link_window_0231.py`, 4 passed). The named older tests still pass (70 passed in §6).
- [x] The guest page shows the note only to the owner (`test_the_owner_sees_why...` passes, `test_a_guest_never_sees_the_host_note` passes).

## Deviations

- Step 3 browser test could not run (Chromium missing). Not installed, because the brief names no install step. Orchestrator or owner must run `tests/test_host_list_cards_browser.py` with 0 skipped.
- No 390 px screenshots were taken (no browser). Required by AGENTS rule 7 for the changed pages (reservations, reservation detail, property editor, setup guest link, guest unavailable).
- Steps 4 and 5 both edit `reservation_detail.html`; committed as separate `0231 step 4` and `0231 step 5` commits.
- Step 12 grep: `App/app/templates/guest/archive/ticket-wallet/base.html` still uses an older `guest.css?v=20261002a` key. Not in brief §3, not changed. No test pins the old key.
- Untracked `docs/tasks/0235-round1-verification.md` was already in the tree before this session. Not committed.

## Questions

- None blocking. Please confirm the browser run and screenshots (above) before merge.

## Owner steps left

- None for the code. Run the browser test and screenshots in an environment with Chromium.
