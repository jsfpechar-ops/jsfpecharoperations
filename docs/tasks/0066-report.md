# 0066 report: property hub

## Files changed

- `App/app/templates/_host_navigation.html` — removed Properties / Guest links / Automation / Smart locks sub-bar.
- `App/app/templates/apartment_form.html` — editable `#automation` timing; guest-link copy/preview on `#communication`; communication open when editing.
- `App/app/templates/settings.html` — Business & legal details card → `/entities`.
- `App/app/routes/admin.py` — `/guest-links` and `/automation` 303 redirects; removed standalone automation POST/helpers; property save updates automation only when `automation_mode` is posted; `_save_address_only` for setup wizard; regenerate return_to → property `#communication`.
- `App/app/routes/setup_wizard.py` — address step uses `_save_address_only` (no full-form wipe).
- `App/app/templates/setup/address.html` — wizard validation error line.
- `App/app/routes/api.py` — command palette entries → `/apartments`.
- `App/app/templates/reservation_detail.html` — guest-link menu → property `#communication`.
- Deleted `App/app/templates/automation.html`, `App/app/templates/guest_links.html`.
- `App/tests/test_property_hub.py` (new) and updates across tests that referenced removed pages.
- `docs/tasks/0066-property-is-the-hub.md` (brief).

## Step 1: guest_links.html capabilities vs property `#communication`

| guest_links.html | On property `#communication` |
|---|---|
| Copy permalink | Yes (`#permalink` + copy button) |
| Copy PIN | Yes (`#permalink_pin`) |
| Bilingual suggested message | Yes (`message-{{ id }}`) |
| Copy full message | Yes (added primary copy button) |
| Copy English only | Yes (added button + hidden `message-en-{{ id }}`) |
| Preview guest picker (`/l/…`) | Yes (added ghost link) |
| Regenerate link / PIN | Yes (formaction buttons) |
| Setup status pill (ready / N setup items) | Replaced by property readiness checklist (same signals) |
| Link to property setup | N/A (already on property page) |
| Per-stay guest URLs | Not on guest_links page; stays use `/reservations/{id}` copy link (unchanged) |

Nothing on `/guest-links` required a redesign beyond moving copy/preview controls onto the property page.

## Follow-up fixes (same PR)

1. **Automation regression:** `_save_apartment_form` pops `automation_mode` / `submit_after_hours` / `default_purpose` when those fields are absent from the POST (partial saves no longer reset timing to manual/24/10).
2. **Setup wizard address (0054):** `_save_address_only` updates only `addr_*` fields; validates merged row and rejects on address issues only. Tests in `test_setup_wizard.py`.

## Tests

```
6 failed, 3138 passed, 4 skipped, 7 warnings in ~464s
```

Failures (all browser geometry / copy-feedback on stays row at 1280px width):  
`test_host_feedback_browser`, `test_host_quiet_dashboard_browser`, `test_host_stay_actions_browser`, three in `test_host_wide_geometry_browser`. These assert stays-table row action clipping, not the removed sub-bar; they also fail on this VM without the bar change. Worth a separate layout pass if CI shows the same.

Context lint: OK.

## Screenshots (demo host, 360 / 390 / 1280 px)

Saved under `docs/tasks/screenshots-0066/`:

- `apartments-{360,390,1280}.png` — list without `host-local-nav`.
- `property-{360,390,1280}.png` — property page with `#automation` timing fields and `#communication` guest link block.
