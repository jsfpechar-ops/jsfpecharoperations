# WP28: UI bug sweep

Commit `67f14e6` on branch `wp28` (base `golive`, ae9a430). Patch: `round3/WP28-ui-sweep.patch`. Not stacked on any other round-3 WP.

## Summary

I seeded the demo workspace (mock UbyPort, demo host plus an admin account, one issued invoice) and opened every host page as host and as admin, and the whole guest flow (PIN, pick, privacy, claim, check e-mail, confirm, details, document, home, signature, review, saved, next guest). Each page was captured at 1280 px and 390 px into `round3/shots/wp28-*.png` (142 files; `-cs` files are the Czech pass at 1280 px, guest Czech at 390 px). A script then checked every page for sideways scroll, clipped boxes, words split mid-word in cells, repeated button labels in one group, destructive forms without `data-confirm`, em dashes, raw i18n keys, English text on Czech pages, the HTTP status of every same-origin link, and console errors and failed requests.

I left out the house book, the host guest detail page (`/guests/{id}`, `guest_form_admin.html`) and the police report detail page (`/submissions/{id}`), because WP25 is working on them.

Main finding: `.panel.tight` (`overflow: hidden`) has higher specificity than `.scroll-x` (`overflow-x: auto`). So every wide table inside a `panel tight scroll-x` was cut off at its right edge instead of scrolling. On the property page this hid the calendar Remove button completely. The same rule probably causes the house book table problem WP25 is fixing (see "What Cursor must verify").

## Findings

Severity: H = an action or content is unreachable or wrong, M = visibly broken or misleading, L = cosmetic or copy.

| Page | Width | Defect | Sev | Fixed |
|---|---|---|---|---|
| Property edit (calendars table) | 1280 | `panel tight` overflow hid the last column: the feed's Remove button could not be seen or reached | H | yes (CSS `.panel.tight.scroll-x`, URL cell capped at 200 px) |
| All `panel tight scroll-x` tables (properties, entities, admin users, invoices, stays, archive) | 1280 | Same clipping rule; any table wider than its panel lost its right edge | H | yes |
| Property edit, entities | 1280 | Words split mid-word in cells ("Airbn b", "controller@example.co m") because `td { overflow-wrap: anywhere }` lets columns shrink below the longest word | M | yes (`break-word`) |
| Guest links | 390 | Suggested portal message (`pre`) widened the page to 420 px (long URL) | M | yes |
| Guest privacy notice `/l/{token}/privacy` | 390 | Cookie table widened the guest page to 501 px (guest.css has no `.scroll-x`) | M | yes (guest.css, cache key bumped) |
| Stay detail, cancelled stay | all | Reporting pill said "Waiting for guest" (teal) under the "This stay is cancelled" banner | M | yes (grey "Cancelled" / "Archived" pill) |
| Invoice detail | all | "Cancel / correct" issues an irreversible correcting document with no confirmation | M | yes (`data-confirm`, new `confirm.cancel_invoice` EN/CS) |
| Stay detail | all | "I filed this stay by hand in UbyPort" panel had zero padding (`panel tight`), the summary touched the border and the open form ran to the edges | M | yes |
| Stay detail | all | "Mark ID checked" button hung over the card's bottom edge (`form.inline` ignores vertical margin) | M | yes |
| Stay detail | all | Unregistered-guest placeholder cards: buttons sat on the bottom border (padding-bottom 0) | M | yes |
| Stay detail, overdue | 1280 | "overdue by N days" rendered as a full-width red bar instead of a pill | L | yes |
| Stay detail | all | Document fact showed a lone "—" before the number when no document type is stored ("— YA1122334") | L | yes |
| Onboarding (finished) | all | "Skip setup guidance" twice on one page (header meter and finish card) | M | yes (finish card drops its toggle on /onboarding only; dashboard unchanged) |
| Onboarding (finished) | all | "share the link below" while the link is above | L | yes (EN/CS) |
| Settings | all | "Data protection" card contained a second card with the same "Data protection" heading; "0 record(s) — open house book" | L | yes ("Retention status" h3, plural-safe counts) |
| Property edit | all | "1 calendars" / "1 kalendáře" | L | yes (plural keys one/few/many) |
| Property edit | all | Sticky save bar said "Back to apartments" (UI says Properties everywhere) | L | yes |
| Automation | all | Button label "full property setup" in lower case (sentence fragment reused as a label) | L | yes (`automation.full_setup_button`) |
| Invoice settings | all | h1/title "Invoice details — Demo Controller s.r.o." (em dash) | L | yes (colon) |
| Entities | 1280 | Operator signature block was an unstyled browser fieldset (grey groove border); Clear and Upload image not level | L | yes |
| Invoices list | all | Search box unstyled (no padding, browser border): `input[type=search]` missing from field styles; same for `tel` and `datetime-local` (hand-filing time field) | L | yes (command palette input excluded) |
| Stays list, dashboard (row menu "Open guest form") | all | Links to `/l/{token}/{id}` for stays whose guest access is closed (outside the window, cancelled, complete) return the guest "stay gone" 404 page | M | no (needs per-row access state from the route) |
| Stays list, default view | all | "Upcoming & current" hides past stays, so the two overdue stays that lead the dashboard are not in the default Stays list | M | no (filter semantics; product decision) |
| Stay detail, cancelled | all | Still offers "+ Add a guest", "Edit count", "Generate invoice"; next step says "Demo stays are never sent" instead of "cancelled" | L | no (wants a decision on what a cancelled stay may still do) |
| Stay detail | all | Two "Edit count" actions (next-step card and Guests heading) | L | no |
| Host add-guest form `/reservations/{id}/guests/new` (CS) | all | Country list in English on the Czech page (the guest form uses Czech names) | M | no (template is `guest_form_admin.html`, owned by WP25) |
| Stay fees filter | all | `input[type=month]` unstyled (monospace, browser border) | L | no (styling it clipped the month control in test_host_geometry; needs a dedicated rule) |
| Data requests | all | "Received" is a free-text field with an ISO timestamp placeholder; "Guest id" asks for an internal id | L | no |
| Guest privacy notice | all | The cookie table lists host-only items (sidebar, command palette, saved views, `umami.disabled`) to guests | L | no (legal copy, cookie_inventory owner) |
| Admin users | 1280 | "Copy" wraps under the password field | L | no |
| Top bar | 390 | "MOCK · NOTHIN…" environment badge truncated | L | no |
| All host pages | 390 | Two overdue alert toasts cover about 200 px of content in the middle of the screen until dismissed | L | no (by design of the alert stack; worth a look) |
| Many pages | all | Em dashes in user-visible copy: about 197 in host_i18n.py, 30 in i18n.py, 4 in validation_i18n.py, 37 in templates; several tests pin the exact text | L | partly (only strings this WP touched) |
| Settings, properties (mail preview) | all | Logo blocked by CSP in the sweep only, because the preview uses `PUBLIC_BASE_URL` (port 8080) while the sweep ran on another port; not a production defect while PUBLIC_BASE_URL matches the origin | L | no (environment artefact) |

No raw `host.foo.bar` keys, no CS catalogue gaps (every EN key exists in CS), no console errors and no broken links apart from the guest-link rows above. Status pill colours were otherwise consistent (red rejected, amber incomplete or ID not checked, blue ready, teal waiting or unpaid, green reported or done, grey neutral).

## Files changed

- `App/app/static/app.css`: `.panel.tight.scroll-x` scrolls; field styles cover `tel`, `datetime-local`, `search` (not the command palette); portal message wraps; overdue metric is inline; feed URL cell 200 px on desktop.
- `App/app/static/host.css`: table cells use `break-word`; placeholder guest card bottom padding; signature fieldset styling.
- `App/app/static/guest.css`: `.scroll-x` and cookie table cell styles for the guest privacy notice.
- `App/app/templates/base.html`, `auth_base.html`, `public_legal_base.html`, `guest/base.html`: cache keys bumped to `20261004w`.
- `App/app/templates/reservation_detail.html`: hand-filing panels lose `tight`; verify form loses `inline`; no lone dash for a missing document type; inactive stays show their state pill.
- `App/app/templates/apartment_form.html`: plural calendar count; `feed-table` class.
- `App/app/templates/automation.html`: capitalised button label key.
- `App/app/templates/invoice_detail.html`: confirm on cancel / correct.
- `App/app/templates/settings.html`: inner card heading is an h3.
- `App/app/templates/_components.html`: `onboarding_finish(..., show_toggle=True)`; /onboarding passes False.
- `App/app/host_i18n.py`: new keys `confirm.cancel_invoice`, `automation.full_setup_button`, `apartment.form.calendars_count(.one/.few)` in EN and CS; reworded `invoice.cancel_help`, `invoice.settings.title`, `onboarding.finish_line_done`, `apartment.form.back_list` (EN), `settings.data.title`, `settings.data.due_count`, `settings.data.dsr_count`.
- `App/tests/test_wp28_ui_sweep.py`: new, rendered-markup and CSS assertions.
- `App/tests/test_wp28_geometry.py`: new, Chromium geometry checks on the seeded demo.

## Tests added

- `test_wp28_ui_sweep.py` (12): table scroll rule and `break-word`; field styles for tel, datetime-local and search; guest `.scroll-x`; invoice cancel confirm and copy; "1 calendar" / "1 kalendář" and no "Back to apartments"; `feed-table`; automation button label; one "Skip setup guidance" and "link above"; settings headings and no "record(s)"; hand-filing panel class, verify form class, no lone dash; cancelled stay pill; new keys in both languages and translated.
- `test_wp28_geometry.py` (7): guest links has no sideways scroll at 390 and 1280; the calendar Remove button is inside the visible panel and the feed name is on one line; placeholder and verify buttons sit at least 8 px inside their cards and the hand-filing panel has padding; the overdue deadline is narrower than its cell; the signature fieldset has a solid rounded border and level buttons; the guest privacy notice has no sideways scroll at 390.
- Checked against the base: with the code changes stashed, all 12 markup tests and 6 of the 7 geometry tests fail. The one that passes is guest links at 1280, which was never broken.

## Test commands and results

All commands run from `/tmp/wp/wp28/App` with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu`.
- `pytest -q tests/test_wp28_ui_sweep.py`: 12 passed.
- `UBYHOST_REQUIRE_BROWSER=1 pytest -q -rs tests/test_wp28_geometry.py tests/test_host_geometry.py tests/test_wp28_ui_sweep.py`: 21 passed.
- `UBYHOST_REQUIRE_BROWSER=1 pytest -q -rs tests/test_guest_browser_e2e.py`: 4 passed, 0 skipped.
- Full suite in chunks (guest e2e and the geometry files ran separately above): a-c 298 passed, 2 skipped; d-f 378 passed; g-h 365 passed; i-o 417 passed; p-r 330 passed; s 362 passed; t-z 231 passed. 0 failures.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.

## Deviations from the spec and why

- I did not run a full em-dash cleanup. There are about 270 em dashes across the catalogues and templates, and existing tests pin the exact wording (for example `test_dashboard_order.py` and `test_dashboard_queue_copy.py`). That makes it a copy package of its own, not a local fix. I only removed em dashes from strings I was already editing.
- I tried and then dropped field styling for `input[type=month]`, because it clipped the month stepper in `test_host_geometry.py`. It is listed as an open defect.
- Some fixes are global CSS (`.panel.tight.scroll-x`, `td` overflow-wrap). They also affect the house book page. I did not edit that page's template.

## What Cursor must verify or adapt when applying on the real main

- Overlap with WP25: the `.panel.tight.scroll-x` rule and the `break-word` change probably fix the house book "table does not fit" bug on their own. If WP25 adds its own house book rule, check that the two agree. If WP25 also bumps the `app.css`, `host.css` or `guest.css` `?v=` keys, keep one new value.
- `test_wp28_geometry.py` and `test_wp28_ui_sweep.py` seed the built-in demo for a fresh host, so they rely on `UBYHOST_UBYPORT_ENV=mock` (the conftest default) and on demo stay dates relative to today. The overdue test skips if no seeded stay is overdue on the day it runs.
- Tables that used to be silently clipped now scroll inside their panel at desktop widths whenever they are wider than the panel. Check the stays and entities tables against real data with long names.
- `onboarding_finish` has a new optional argument. Any caller added on main keeps the old behaviour by default.

## Manual steps for the owner

- None to deploy. To review, open `round3/shots/wp28-*.png`. Then decide on the open items: guest-form links for closed stays, overdue stays missing from the default Stays view, which actions a cancelled stay should still offer, and a dedicated em-dash copy pass.
