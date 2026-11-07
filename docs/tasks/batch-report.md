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
