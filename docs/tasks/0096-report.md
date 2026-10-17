# 0096 report: guided setup of a new property

Base: `3248c8d` (claude/quirky-lamport-9svmd1). Executor: Claude (owner-authorized). Brief: [0096-guided-setup](0096-guided-setup.md).

## What changed

- **After create** (`created=1` URL kept): Bookings shows only the connect form. Its button now says **Add calendar** (it said "Add and sync"), and one link-styled POST button says **Skip — I'll add stays manually**. The "What next?" box is removed. The create flash is now just "Property created." because the guide carries the instruction.
- **Guide** (`_property_setup_guide.html`, above the tabs): a progress bar, "Step N of 6 · title", one sentence, and one primary action.
  - On Calendar, Reporting, Fee, Lock and Automation, the primary is the step's own control (Add calendar / Save changes). A primary **Continue** appears only when the host is not on the step's view or section. `app.js` toggles it on in-page tab switches.
  - Guest links: a read-only box with "Guest registration: <url> · PIN: <pin>" (EN/CS), **Copy link and PIN** (normal button) and **Done, I've added it** (primary).
  - Skip is offered only on Fee and Lock. Automation offers **Keep manual sending**, or "Keep this setting" when the mode is not manual.
  - A property in setup opens on its current step when no `?view` is given. The Overview checklist is hidden while the guide runs.
  - After the last step: a redirect to Overview, a green "Setup complete." flash and the existing compact line. When the guide is finished, a skipped calendar (no stays yet) does not block that line.
- **Routes** (`admin.py`):
  - `POST /apartments/<id>/setup` (`step`, `action` = skip|done|keep) accepts only the current step and the actions that step offers. It is audited (`property_setup_step`).
  - Adding a feed redirects to the next step.
  - A Settings save carrying `setup_step` marks Fee/Lock/Automation done only when its `return_to` section is that step's section, then redirects to the next step.
  - Reporting is done only when the police details are complete.
- **Door lock group**: `PROPERTY_SETTINGS_SECTIONS` adds `lock`. The sub-nav order is Property information · Guest experience · Reporting & fees · Door lock · Automation. The group has an intro line, and the lock section inside it is unchanged (names, CSRF, return paths). `#door-code` maps to the group in JS and in the no-JS `:has(:target)` rule. The server's `#door-code` redirects and the `/smart-locks?return_to=…%23door-code` links are unchanged. The Overview card links to `section=lock`. Without door codes on the deployment there is no group and no step (the guide has 5 steps).
- **Guest link name**: the "Readable part of the link" field and its POST branch are removed. When a save changes `internal_name`, `guest_slug.follow_name()` calls `rename()` with the name's readable part. Old slugs redirect (301). A clash keeps the current link.

## Step state (no schema change)

The state is stored in the existing `settings` key/value table, through `db.get_setting`/`set_setting`. Key `property_setup:<id>` holds `{"steps": {"calendar": "skipped", "guest_links": "done", …}, "finished": bool}`. It holds no personal data, so no retention line is needed. The key is written by `POST /apartments`.

- A property without the key (made before 0096) never shows the guide.
- A finished guide never returns.
- Calendar, Fee and Lock can also finish from real data: a feed exists, a fee rate is set, a TTLock lock is chosen.
- Note: the key is not removed when an account is erased (`retention.py` was not touched). It is an orphan flag with no personal data.

## Tests (App/, staging/mock env, pinned Chromium, `UBYHOST_REQUIRE_BROWSER=1`)

- New `test_property_setup_guide_browser.py`, 11 passed:
  - the full journey EN/CS × 360/1280 (EN adds a calendar and saves Automation; CS skips the calendar and keeps manual sending), with one visible primary and the right skip on each step and no horizontal overflow;
  - the no-JS CS journey;
  - Continue follows tab switches;
  - refusals (wrong step or action, no Reporting skip, a save from another section, another host);
  - pre-0096 and finished properties show no guide;
  - the Door lock group, its order and the no-door-codes case;
  - a rename in the browser, after which the old `/l/<slug>` lands on the new one.
- Updated for the intentional changes, each with a replacement assertion:
  - test_guest_slugs: the name-follows-link tests, plus "an unchanged name or a posted link name never renames" and a reserved-word fallback;
  - test_property_navigation_browser: Door lock group/hash, the guide after create;
  - test_host_ux_acceptance: the control set; keyboard focus on `door_codes` in the lock group;
  - test_host_unsaved_changes_browser: switch to the lock group before toggling;
  - test_property_create_browser: the guide replaces first-use.
- Listed files: guide 11 ✓, navigation 11 ✓, smart_locks_page 14 ✓, guest_slugs 26 ✓, ux_acceptance 12 ✓, unsaved 15 ✓.
- Remaining failures exist identically at `3248c8d`, run from an untouched copy. Cause: fixtures without an address (parallel worker):
  - host_property_controls 2;
  - lock_navigation 1;
  - property_create 7. My edited asserts there cannot run until those fixtures post an address.
- Wider run of 79 files that touch `/apartments`, slugs, locks or setup: 980 passed, 1 skipped (the existing capture gate), 52 failed/errored. That is the same set as baseline, test by test.
- `ruff` (E9,F63,F7,F82,F401,F841): clean. `context_lint`: run at commit.

## Evidence

`docs/tasks/0096-evidence/` (`UBYHOST_CAPTURE_GUIDE=1`): `{1-calendar,2-guest-links,3-reporting,4-fee,5-lock,6-automation,7-complete}-{360,1280}-{en,cs}.png` plus `-1280-cs-nojs`. Synthetic data only.

## Open points for the owner

1. Police reporting has no Skip (as briefed). A host waiting for Ubyport credentials stays on step 3 until they arrive. Steps 4–6 wait for it, though they stay reachable by tab.
2. The Door lock intro and the existing "connect first" line both mention TTLock with a gateway. The intro is the briefed text, and the lock section was kept unchanged, so the overlap remains.
3. Existing incomplete properties do not get the guide (no stored key). Say if they should.
