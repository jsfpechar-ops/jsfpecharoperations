# 0984 report (B06, connection states)

Status: blocked

Reason: test row 3 failed (WebKit browser binary not installed in /opt/pw-browsers; not installed, per the no-install rule), row 4 failed (container has no IPv6, so the DNS-pinning IPv6 test cannot bind), row 5 failed on a real layout finding (layout lint `table-squeezed` on the feed URL cell that this branch introduced). Row 2 and row 6 passed. Rows 3 to 5 were stopped at the first failure as the brief requires; the rest of those rows was not run.

## Commits (branch codex/0964-b06-connection-states, base 7b0355c)

- 1106e97a 0984 step 1: templates, app2.css 0984 block, app2.css version key in base.html
- da7f3cf7 0984 step 2: four browser tests
- fd94de4e 0984 step 3: static_versions.json (app2.css entry only)
- 8a78b72f 0984 step 2 fix: test-only wait before an `is_visible` check in the calendar test
- 1c6648f2 0984 report (prior session)

## Files changed (vs base 7b0355c)

6 App files, all in brief section 3: app2.css (+8), _property_editor.html (+12), _property_calendars.html (+8, -1), base.html (version key), test_host_property_controls_browser.py (+164), static_versions.json (2 lines). Plus the brief and this report under docs/tasks.

## Test rows (each with UBYHOST_DB unique per row, UBYHOST_REQUIRE_BROWSER=1)

- Row 1, new tests (prior session): 4 passed, 0 skipped.
- Row 2, host (7 files): 51 passed, 0 skipped. Last line: `51 passed in 198.17s (0:03:18)`.
- Row 3, smart-lock and door code: FAIL. 115 passed before the stop. Last lines: `E   playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at /opt/pw-browsers/webkit-2359/pw_run.sh` / `1 failed, 115 passed in 68.41s (0:01:08)`. Failing test: `test_disclosure_design_and_geometry_on_every_changed_page[en-webkit]`. Only that file requires WebKit; /opt/pw-browsers has chromium only. Not deselected, not skipped.
- Row 4, calendar: FAIL. 60 passed before the stop. Last lines: `OSError: [Errno 97] Address family not supported by protocol` / `1 failed, 60 passed in 70.75s (0:01:10)`. Failing test: `test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses`. Confirmed: AF_INET6 sockets cannot be created in this container. Not a product change.
- Row 5, static and design: FAIL. 27 passed before the stop. Last lines: `AssertionError: 22 layout-lint findings {'table-squeezed': 22}` / `1 failed, 27 passed in 991.15s (0:16:31)`. Failing test: `test_layout_lint_browser.py::test_every_host_page_passes_the_layout_lint`. Findings: `td.small.feed-url "URL https://www.airbnb.com/c"` and `td.small.feed-url "URL https://ical.booking.com"` on property-bookings (and -empty) at 320, 390, 1024; "4 lines for URL Copy link" at 318 px. The cause is the new URL cell in _property_calendars.html (the `truncate` cell was replaced by details plus Copy link). This is a real layout problem, so no assertion was changed and no CSS fix was attempted.
- Row 6, context lint: PASS. `context lint: OK`, exit 0. WARN lines are pre-existing brief-reference notices.
- `git diff --check`: clean.

## Screenshots (15 viewed)

- Lock Off 390/768/1280: state "Automatic door codes: Turned off" with one explanation and "Connect my lock"; grey dot matches the "Smart lock: Off" pill. Nothing clipped. The form's own "Connect my lock" button also appears lower in the section (pre-existing). At 1280 the status tiles render as narrow cards below the form with mid-word breaks ("Calend ar", "Foreig ner"). Not attributable from these shots alone; base not compared.
- Lock On 390/768/1280: green "Automatic door codes: On" row with Turn off, unchanged. Same 1280 tile squeeze as above.
- Lock unavailable 390/768/1280: "Automatic door codes: Turned off" with "Door codes are not enabled on this deployment."; no button. Tiles correct at 1280 here.
- Calendars collapsed 390/768/1280: name, sync badge (OK green, Error red with "Synthetic feed unreachable"), URL disclosure and Remove visible; no horizontal scroll.
- Calendars open 390/768/1280: long URL wraps inside the disclosure at 390 with Copy link and Remove in view. At 768 and 1280 the URL column is narrow, so the URL wraps one token per line and the cell is tall; Copy link and Remove are still in view, but the table is cramped. This matches the layout-lint finding.

## Acceptance (section 7)

- Ticked: Lock Off, Lock unavailable, Lock On, screenshots described, only section 3 files changed.
- Not ticked: calendar rows at all widths with no horizontal scroll (layout lint fails); "4 new tests pass and all rows pass with 0 skipped" (rows 3 to 5 did not pass).
- Not verified: rows 3 to 5 beyond the first failure; design-system checklist (docs/design/design-system.md) not ticked.

## Deviations and questions

- No test or product change was made in this run; no timing race was found.
- Questions for the orchestrator: (1) install WebKit for the smart-lock row, or drop the WebKit variant by decision; (2) run the calendar row on a host with IPv6; (3) fix the feed URL cell layout on property-bookings at narrow widths (new brief); (4) confirm the 1280 status-tile layout on lock-off and lock-on against the base.

## Owner steps

None for this brief. The orchestrator decides the questions above before any PR.
