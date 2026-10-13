# 0094 report: property tabs, one editor, early calendars

Base: `272a03f` (0092 at review). Result: `675adf0` (code), report commit after it. Executor: Claude (owner-authorized). Scope: the property part of the host navigation (property preview), not full-host completion.

## What changed

- `apartment_form.html`: the edit branch is now a header, a local tab bar (Overview · Bookings & calendars · Settings; CS Přehled · Rezervace a kalendáře · Nastavení) and three views, each included once:
  - `_property_overview.html`: shortcut cards with real summaries (calendar count and errors, guest link, "Ready to report"/"N details missing", operator, fee, address, door codes Enabled/Off) and the Setup checklist as a visible section (no `<details>`). No form or field. The business card opens `/entities?edit=<id>`.
  - `_property_calendars.html`: the feed list (status, last check, error, Remove), Add calendar, Add stay manually, Update calendars, and the one calendar form (sibling, never nested). With feeds, the form waits behind **Add calendar** (`?add_calendar=1#calendar-connect`). It is open when there are no feeds, on the first-use path and on a refused draft. The first-use choice after create (Connect a calendar · Add stay manually · Continue to overview) sits here.
  - `_property_editor.html`: the existing full form, moved once, with the same names, endpoint, hidden guards and credential-test/code-list actions. It is grouped under visible headers: **Property information** (basics, address, notes, Archive/Restore at the bottom on a dashed card above the Save bar), **Guest experience** (Guest links with URL+Copy+Preview, PIN+Copy and New PIN / New link at the top, then name, message, windows, photo policy; Digital door lock), **Reporting & fees** (police details, the request letter as a visible sub-section, stay fee), **Automation**. Header bars replace `<summary>`. Routine hints moved to the shared `?`.
  - The Suggested portal message block and its copy buttons are removed. Door codes use a `role="switch"` named **Automatic door codes** with a saved Enabled/Off status that reads "Not saved yet" when toggled. The help tip carries lede, margin and manual-change text, with one Guide link.
- `admin.py`: `PROPERTY_VIEWS`/`PROPERTY_SETTINGS_SECTIONS` and `_property_view_state` (allowlisted `view`, `section`, `add_calendar`, GET presentation only). Refused saves render settings/property, refused feeds render bookings. Return targets: create → `?view=bookings&created=1#calendar-connect`; add/remove feed → `?view=bookings#calendars`; `/guest-links` and `/automation` → their Settings group. The save `return_to` carries the active view/section.
- `setup_wizard.py`: legacy targets carry `?view=` (address → settings/property, bookings → bookings).
- `app.js` `initPropertyViews` (one function): it switches views/groups in place, without a reload, for unmodified same-property links. History follows with back/forward. The fixed hash map, plus any id inside a view, reveals its view and group, and an unknown hash does nothing. It keeps `return_to` in step. A refused native field in a hidden group shows that group first, so the browser focuses it. `beforeunload` asks before leaving with unsaved settings. It also runs the switch status.
- `host.css` `/* 0094 */`: wrapping tab/section chips; a section rail beside the form at ≥860 px of *lane* width (container query); list+form side by side at ≥900 px. Without JS, `:has(:target)` opens the view/group of an old `#hash`.
- `_csrf` hidden fields on the settings, calendar and feed-remove forms, so they work without JS.
- `host_i18n.py`: `# 0094` block, 20 EN/CS keys.

## Control inventory (before → after)

The one `POST /apartments/<id>` form submits the same 47 names as before 0094, plus an explicit `_csrf` (csrf.js already added it). `fee-copy-source` stays unnamed. `test_three_views_four_groups_one_editor_and_unique_ids` pins the exact set, checks there are no duplicate names or ids and no nested forms, that there is one calendar form, and that Overview has no inputs. `test_unrelated_save_keeps_every_stored_value` posts the page's own values (credentials, controller, fee, PIN, lock, mode) and only `notes` changes.

## Tests (from App/, staging/mock env, pinned Chromium)

```
pytest tests/test_property_navigation_browser.py tests/test_host_property_controls_browser.py tests/test_setup_wizard.py tests/test_calendar_platform_required.py -q -rs
  → 50 passed, 0 skipped
per-file run of 87 files (all property/setup/onboarding/lock/door-code/help/geometry files)
ruff → All checks passed!   context_lint → OK
```

Per-file run: 1089 passed. Remaining failures:
- test_host_quiet_dashboard_browser (1) and test_security (1, alone): both are baseline failures at `34bffcb`.
- test_host_i18n (1): order-only, fails only when it runs first; passes after another file.
- test_dashboard_missing_banner: 1 skip, its pre-existing capture gate.

Flake found and fixed: the Overview-card click checked visibility before the switch had painted. The test now waits and also checks that the page did not reload. It then passed 6 times in a row.

## §7 checklist

- [x] Three tabs and four Settings groups, header bars, one editor and one field per setting.
- [x] The calendar comes first after create and is always under its own tab. After connection the form sits behind Add calendar, and errors keep the draft open.
- [x] Old hashes and return paths, operator defaults, PIN/link actions at the top, Archive at the bottom of Property information, the switch, and `?` help.
- [x] Drafts survive tab and group switches and back/forward. A dirty page asks before leaving. Save and test-connection return to their group. Invalid hidden fields are revealed. No-JS hashes, tabs and save work with the same markup.
- [x] EN/CS 360/390/1280 screenshots. Widths 760–2048 measured with the sidebar expanded and collapsed. 0 skipped. Synthetic data only.
- [ ] CI on the task head: not run (no push).

## Evidence

`docs/tasks/0094-evidence/`: `{overview,bookings,settings}-{360,390,1280}-{en,cs}`, `settings-{guests,reporting}-1280-{en,cs}`, `settings-{760,1024,1440,1920}-cs-{expanded,collapsed}`, `created-bookings-1280-en`, `settings-nojs-1280-cs` (`UBYHOST_CAPTURE_0094=1`).

## Files outside §3 / deviations

- Tests rewritten for intentional changes (suggested message removed, folds removed, tabbed URLs), each with a replacement assertion: test_guest_links_bilingual (page tests → "message is gone, link/PIN/Preview present"; helper tests kept), test_guest_links_preview, test_overhaul, test_calmer_forms, test_copy_cleanup, test_property_form_nav, test_property_hub, test_automation_missing, test_ubyport_sample_pdf, test_ws_request_letter (with a saved login only the download link remains; no fold), test_stay_fee_property_panel, test_host_help_browser, test_lock_navigation_browser, test_wp28_geometry, test_host_wide_geometry_browser (guest-links/automation routes use their Settings URL and lane).
- Not done (outside §3): `_stay_fee_fields.html` still folds the council details in `<details class="fee-setup-section">`. It is shared with `stay_fee_setup.html` (0077/0093).
- `_components.html` was not edited: the existing `help_tip`/`field_label`/`sync_calendars_button` were enough.

## Hand-off to 0075–0083

Property-local ownership: the Overview cards (read-only), Bookings (`/apartments/<id>/feeds`, `/feeds/<id>/delete`) and Settings (one `POST /apartments/<id>`) groups as above. Business/legal details stay in `/entities?edit=<id>`. Those briefs stay blocked until rebased on this; this is a property preview, not full-host acceptance.

## Owner steps

1. Look at `overview-1280-en.png`, `settings-guests-1280-en.png`, `bookings-390-en.png` and `created-bookings-1280-en.png`.
2. On staging: create a property and connect a calendar from the first screen. Then switch tabs with unsaved text and try the browser Back button.
