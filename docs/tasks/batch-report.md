# Batch report (PR #803 stack)

## 1000: Property page photo reorder

Status: review

Depends on 0999; committed on `task/0999-property-rules-map` (not a separate PR).

### Files changed

- `App/app/property_page.py` — `move_photo()`
- `App/app/routes/payments.py` — `POST …/page/photo-move`
- `App/app/templates/property_page_review.html` — up/down forms, Main photo marker
- `App/app/host_i18n.py` — `payments.page.photo_up|down|main` (EN + CS)
- `App/tests/test_property_page_photos.py` — reorder + edge tests

### Commands (last 5 lines each)

`pytest tests/test_property_page_photos.py -q --tb=short -x`:
```
.........                                                                [100%]
9 passed in 1.83s
```

Property bundle §6:
```
..................................                                       [100%]
34 passed in 1.80s
```

i18n (expanded `test_i18n*` → `test_go_host_i18n.py` … `test_validation_i18n.py`):
```
33 passed, 1 warning in 2.12s
```

Browser §6:
```
23 passed in 43.50s
```

`test_layout_lint_browser.py` (UBYHOST_SHOTS_DIR=/tmp/shots):
```
4 passed in 206.07s (0:03:26)
```

`python3 scripts/context_lint.py`:
```
next free: task 1000 | migration 0039
context lint: OK
```

### §7 Acceptance

- [x] Up on the first photo and down on the last are disabled; the first photo shows "Main photo".
- [x] Posting `photo-move` changes only `photos_json`; cap and files unchanged (tests).
- [x] Public page hero uses order[0] (existing `loop.first` / `_og`; not re-tested in this pass).
- [x] §6 tests green; browser/geometry 0 skipped.
- [x] UX gate: layout lint green; screenshots reviewed.

### Screenshots (`/apartments/<id>/page`, 5 photos)

390: Photos wrap in a flex row; each thumb has delete, "Main photo" on the first, compact ↑/↓ buttons; first ↑ disabled; no horizontal scroll; bottom nav visible.

768: Same photo row fits one line with five thumbs; reorder controls under each; shell lane and page card readable.

1280: Desktop sidebar; photo strip in the card with all controls aligned; no overflow in the photo row.

Evidence (local, not committed): `/tmp/shots/1000-property-page/property-page-{390,768,1280}.png`

### Design-system checklist (property page review)

- [x] Extends `host_page.html` (unchanged shell).
- [ ] Header action row — not touched this brief.
- [x] No new Save bar; no new JS; server forms only.
- [x] EN/CS keys added together; aria-labels on icon buttons (rule 9).
- [x] `test_layout_lint_browser.py` green, 0 skipped; viewports inspected.

### Deviations

- i18n step command: repo has no `tests/test_i18n*.py`; ran `test_flash_literals.py` plus the four `*i18n*.py` host/public files instead.
- Screenshot capture used synthetic `issue_session` + `acceptance.record(..., "backfill")` in a one-off script (not committed); same page as layout-lint host crawl.

### Questions

None.

### Owner steps

1. Merge the batch PR with `scripts/merge-pr-on-green.sh` after CI is green.
2. Deploy as usual (no migration).
3. On `/apartments/<id>/page`, move a photo up and confirm the public page hero updates.

## 0995 Booking site sidebar

Status: review. Files: host_i18n.py (5+1 keys cs/en), `_shell_sidebar.html`, routes/payments.py (`/booking-sites`, setup nav), new `booking_sites.html`, `booking_site_setup.html` nav, new `test_booking_site_host.py` (6 tests), `test_layout_lint_browser.py` (EXTRA_ROUTES).

### Commands
- Row "Booking site" (host, booking_site, property_page, stripe_connect): 73 passed.
- Host pages + geometry with `UBYHOST_REQUIRE_BROWSER=1`: 244 passed, 0 skipped.
- `test_layout_lint_browser.py`: 4 passed, 0 findings.
- `context_lint.py`: OK.

### UX gate (booking-sites)
390: one card per property, name wraps, badge and "Set up" side by side, sidebar absent (tab bar). 768: same cards, no overlap. 1280: sidebar shows "Booking site" highlighted, Properties not; cards full width, badge and button compact.
Design-system checklist: reused tokens/components, no CSS, light mode, no JS.

### Deviations
- Icon: `globe` not in `_icons.html`, used `external-link`.
- Brief's single `ui-facts` list failed layout lint (duplicate-heading with the page title, tight-stack of stacked "Set up" buttons at 768). Fixed inside the template: no wrapping section, one `ui_section` per property with badge and button in `ui-btn-group`. No CSS or ALLOW change.
- First host-pages run showed 1 unexplained failure (not reproduced twice; later full run 244 passed).

### Questions
None. Owner steps: after merge and deploy, check the sidebar item on a Free and a Max account. 390 px shot: /opt/cursor/artifacts/0995-booking-sites-390.png (not committed).

## 0996: Booking site direct pay setup

Status: review

### Summary
- Migrations `0039_site_booking_direct.sql` / `00010_site_booking_direct.sql` (branch had 0038/00009 taken; PG schema version **39**; `test_db_postgres.py` + `test_migrations.py` bumped).
- `booking_rails.py`, setup step `pay`, `#pay` form, `create_pending` supports `requested` + `pay_method`.
- **Rails share stay-fee columns** (`stay_fee_guest_*` on `apartment`); owner pre-approved in brief 0996 risk list.

### Commands (last lines)
- `test_booking_site.py test_booking_direct_0996.py test_property_page.py test_stripe_connect.py test_host_i18n.py`: 100 passed.
- `test_migrations.py`: green after LATEST 39.
- `test_layout_lint_browser.py` + `test_host_geometry.py`: 6 passed, 0 skipped.
- `context_lint.py`: OK (compacted duplicate 0986 decision line + test-map row).

### UX (`/apartments/<id>/booking-site`, #pay)
390/768/1280 (layout-lint host crawl + HTML verified "How guests pay"): cash/iban/revolut checkboxes stack; Save primary; step list shows "How guests pay"; no horizontal scroll; bottom nav on phone.

### Deviations
- `test_booking_setup.py` `stripe`→`pay` (brief §3 listed only `test_booking_site.py`; needed for green setup tests).

## 0997: Guest request flow

Status: review

### Commands
- `test_booking_direct_0997.py` + 0996 bundle + property_page + booking_widget + stripe + host_i18n: 102 passed.

### Guest pages
- `/p/<slug>` book form: pay-mode radios when Stripe+direct; hidden field when one mode.
- `property_page_requested.html`: IBAN/QR/VS, Revolut link, cash note, 24h hold copy once.
- `expire_requests` scheduler job added.

### Screenshots (report-only)
390: narrow book form, pay-mode fieldset above submit. Request page: stacked rail cards, QR 200px. 768/1280: same structure, comfortable width.

## 0998: Host confirm / decline

Status: review

### Commands
- Full direct stack + property_page + stripe + host_i18n: **102 passed**.
- UX gate: `test_layout_lint_browser.py` + `test_host_geometry.py` + `test_design_guardrails_browser.py`: **17 passed**, 0 skipped, 0 findings.

### UX (`/apartments/<id>/booking-site`, bookings list with `requested`)
390: status "Waiting for payment"; compact Mark paid / Decline buttons beside badge; three actions wrap without overlap. 768: buttons inline in row. 1280: sidebar + list readable; direct cancel confirm uses no-auto-refund copy.

### Deviations
- `App/app/mail.py`: added `site_booking_request_host` to `KINDS` (brief mail kind not in allowlist; required for `notify_request`).

### Stop-and-ask (coordinator)
1. **Rails columns**: shared with stay-fee guest pay (brief 0996); not separate `booking_pay_*` unless owner wants a follow-up migration.
2. **Layout lint**: no unfixable findings; booking-site not in default EXTRA_ROUTES (pre-existing); host lint green.
3. **Deploy**: owner applies PG migration **39** / goose **00010** (not brief's 0038/00009 numbers on this branch).
