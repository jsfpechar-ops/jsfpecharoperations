# 0089 report: calendar needs a platform and a link

Base: `1d6ff14` (0088 at review). Result: `c7ea030`. Executor: Claude (owner-authorized).

## What changed

- `admin.py`:
  - New shared allowlist `CALENDAR_PLATFORMS`: Booking.com, Airbnb, Vrbo, Agoda, e-chalupy, Other.
  - New `_calendar_platform(platform, other, own_name)`. It turns the choice into a readable `label` and checks it. Other needs a trimmed name of at most 80 characters with no control characters. `own_name` is optional, at most 100 characters, and defaults to the label. Unknown or blank choices are refused, and nothing is inferred from the URL.
  - New `_feed_display` for showing feeds. Name: own_name, then label, then the platform recognised from the URL, then "Calendar / Kalendář". Portal: label, then the recognised platform, then "Other / Jiný". It never shows a dash and never rewrites the database.
  - `add_feed` now checks the platform first. It then refuses a blank URL with no network call. Only after that does it run the unchanged `validate_calendar_url` and the duplicate check, then insert and run `sync_all` as before.
  - Any refusal renders the property page again with status 400. It passes `feed_draft` (platform, Other name, custom name and URL only, never in a query string) and translated per-field errors. The first invalid field gets `autofocus`.
  - Success and partial-sync results redirect to `/apartments/{id}#calendars`. When a sync fails, the new feed is kept, as in the ordinary add flow.
- `_render_property_detail(apartment_id, request, *, extra=None, status_code=200)` was added with the brief's signature. It loads the property and calls the shared render body, `_render_apartment_detail`, which 0088 already extracted. That body now merges `**(extra or {})` after the copy context.
  - **Deviation:** the GET route calls `_render_apartment_detail` directly, so `?copy_from=` keeps working.
- `apartment_form.html`:
  - The calendar form now opens with a required platform select ("Choose platform" is disabled).
  - Next comes the Other-name field, shown only when Other is picked. This is a CSS `:has()` rule, so it needs no JS. If a browser lacks `:has()`, the field just stays visible.
  - Then the URL, then an ordinary optional name. The More options fold is gone.
  - Field names `label`, `own_name` and `url` are kept, plus `label_other`.
  - The feed table uses the readable fallbacks.
- `setup_wizard.py` / `setup/bookings.html`:
  - The platform buttons come from the same allowlist plus "I take bookings myself". `myself` still goes to a manual stay and never creates a calendar row.
  - A hidden `chosen_source` carries the picked platform to Continue (`action=add`). Other asks for a name.
  - The URL and Other name are kept when the form is refused. The label is stored readable (it was a raw key like "airbnb" before).
- `host_i18n.py`: a `# 0089` block with 10 EN/CS keys.

## Anchors (old → new)

The `add_feed`, `label` and `own_name` anchors matched. The detail render body had already moved: 0088 extracted it as `_render_apartment_detail(request, apartment, copy_ctx, …)`. I reused it and added the brief's wrapper.

## Commands (from App/, staging/mock env, pinned Chromium)

```
pytest tests/test_calendar_platform_required.py tests/test_calendar_sync_ui.py tests/test_feed_url_ssrf.py tests/test_feed_no_duplicate_per_user.py tests/test_host_property_controls_browser.py -q -rs
  60 passed, 1 warning in 22.30s   (0 skipped)
per-file run of all property/setup/feed test files (73 files): all pass except the known baseline
  (test_host_wide_geometry_browser 3, test_security first test when run alone).
  test_endtoend 28 passed alone.
ruff check app tests tools --select E9,F63,F7,F82,F401,F841  ->  All checks passed!
python3 scripts/context_lint.py  ->  context lint: OK
```

## §7 checklist

- [x] Platform and URL are both required on the server, for the property form and the wizard. Tests cover a missing, blank, whitespace-only, unknown or readable-but-not-a-key platform, and an Other name that is empty, too long or has a control character. They also cover an empty or whitespace URL with no validation call, an unsafe URL, a foreign property and a duplicate.
- [x] Each refusal writes nothing and runs no sync. The draft is kept and the error field gets focus.
- [x] Default and custom names are stored as typed. Old unlabeled Booking/Airbnb/unknown feeds read in EN and CS without a DB rewrite. A real sync error stays visible, and results return to `#calendars`.
- [x] Browser checks, EN/CS at 360/390/1280:
  - The platform select comes before the URL, with no fold.
  - The Other field shows only after Other is picked.
  - The layout fits with no overflow.
  - With browser validation bypassed, the server still refuses and focuses the platform field.
- [x] No schema, dependency or live feed. `validate_calendar_url` and `sync_all` are mocked in route tests. The SSRF route test uses a literal loopback address with no DNS.
- [ ] CI on the task head: not run here (no push).

## Evidence

`docs/tasks/0089-evidence/`: `calendar-add-*`, `calendar-other-*` (360/390/1280 × en/cs), `calendar-error-1280-en`. Captured with `UBYHOST_CAPTURE_0089=1`.

## Deviations / files outside §3

- `App/app/static/host.css`: added a `/* 0089 */` block (the `:has` toggle, plus a select `width:100%` / `min-width:0` rule). The new select widened the side panel by 3 px and broke `test_wp28_geometry::test_calendar_remove_button_is_visible_without_scrolling`. That test is fixed without changing it.
- `App/tests/test_endtoend.py`: the feed post now sends `label=airbnb` (a platform key) instead of free text.
- The URL safety check, which resolves DNS, runs only once the platform is valid. A form that is wrong in both places therefore shows the platform error first.

## Owner steps

1. Review the screenshots in `docs/tasks/0089-evidence/`.
2. Let the coordinator run the full suite and CI.
3. On staging, add a synthetic calendar with and without "Other".
