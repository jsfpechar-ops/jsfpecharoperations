# 0098 report: Properties — inline guest link, PIN and reporting timing

Status: review. Executor: Claude (owner-authorized). Base `3248c8d` (claude/quirky-lamport-9svmd1). No push.

## What changed

- **Summary rows** (`apartments.html` `#property-summaries`) now use the Properties table design: `panel tight scroll-x list-cards lc-properties`, `row-primary-link` + `property_identity` (avatar + bold name), same header band. The labelled cards below 800 px panel width are the same as the table above. The heading is a plain `h2` plus `?` (`heading-with-tip`); the pink band rules were removed from the 0078 CSS.
- **Columns:** Property | Guest link | Access PIN | When to send to UbyPort.
  - Guest link: the full `PUBLIC_BASE_URL/l/<key>`, the same value Settings shows. Monospace, it wraps inside the cell. Icon-only Copy link and Preview as a guest (new tab).
  - PIN: the value, with icon-only Copy PIN and New PIN.
  - Icons have an `aria-label` plus `sr-only` text and are 44×44.
- **New PIN** posts to the existing `POST /apartments/{id}/regenerate-pin`, with the same handler and CSRF. It sits behind `data-confirm` with a new message: "…The old PIN stops working for guests at once…". The handler now maps `return_to=/apartments` (the fragment is stripped by `safe_local_path`) to `/apartments#property-summaries`. There is no regenerate-link here.
- **Inline timing:**
  - The select has the Automation section's options and labels. The 1–48 hours box shows only for "after a delay", via CSS `:has()`, so this works without JS too.
  - With JS (`initInlineTiming` in app.js): it saves on change, debounces the hours box (700 ms), and shows "Saved" or the server's error in an `aria-live="polite"` status. Without JS there is a visible Save button.
- **Save path:** `POST /apartments/{id}/automation-timing` is a thin route. `_automation_timing_values(form)` was extracted from `_apartment_payload`, so the Settings → Automation save and the inline control use **one normaliser** with two entry points.
  - The route writes only `automation_mode` and `submit_after_hours`. Default purpose is untouched.
  - It refuses an unknown mode, and for the delay mode any hours outside 1–48 (where the Automation form would silently clamp or default). Nothing is stored on a refusal.
  - It has the same login guard, CSRF middleware and `access.apartment` ownership check. A foreign id gets 404 (JSON) or a redirect with `err`.
  - It returns JSON when `Accept: application/json`, otherwise a 303 to `/apartments#property-summaries`. It writes the `apartment_updated` audit row.
- **Properties table:** the `addr_obec` and `uby_name` sublines under the name were removed (owner). No IDUB, mark or login is on the list.
- **i18n:** `_PROPERTIES_0098_STRINGS` (EN/CS); the 0078 help text was updated.
- **Decision:** one line added in `docs/context/ui-decisions.md`.

## Filing

The stored values are identical to a Settings → Automation save. This is tested row-for-row for scheduled 7/48, immediate and manual, using the real settings form fields parsed from the page. The reporting/worker code is unchanged.

## Tests (App/, staging/mock/REQUIRE_BROWSER, pinned Chromium)

- New `tests/test_properties_inline_controls_browser.py`: **12 passed**. It covers:
  - the URL, the icons and the confirm text
  - an identical DB row against the Automation page (×4)
  - JSON/no-JS refusals that store nothing
  - foreign-id refusal
  - no-JS New PIN
  - browser: copy URL/PIN, New PIN confirm, PIN changed, old PIN refused and new PIN accepted on the guest page
  - save-on-change, the hours box following the mode, an invalid-hours error with nothing stored
  - the no-JS Save button
  - geometry at 360/390/760/1024/1280/1440, EN/CS, rail expanded and collapsed: no overflow, 44 px targets, aligned with the table above, same cards/table switch
- Updated intentionally: `test_host_properties_navigation.py` (the summary is no longer read-only; no police values on the list), `test_host_ux_acceptance.py` (Properties may edit only `automation_mode`/`submit_after_hours`, and only via the two routes), `test_property_hub.py` (the "/automation" check no longer matches `/automation-timing`).
- Run: every `automation_mode` test file, plus list-cards, ux-acceptance, guest_slugs, host_i18n, help: **1462 passed, 2 skipped** (evidence-capture gates, not browser), 28 failed. Three of those were mine (the old read-only and one-editor assertions above); after the update their files re-ran green: ux_acceptance 12/12; hub, list-cards, navigation, inline, guest_slugs, pin_rotation and table_chips all pass.
- **25 failures not mine**, in fee_setup_compatibility, new_property_defaults, property_create_browser, property_navigation_browser `test_create_offers…` and property_operator_defaults. They fail identically on base `3248c8d` app code (mandatory address, 400 on create/save without address; a parallel worker owns these).
- ruff (E9,F63,F7,F82,F401,F841) clean. `context_lint` OK.

## Evidence

`docs/tasks/0098-evidence/properties-inline-{360,1280}-{en,cs}.png` (`UBYHOST_CAPTURE_0098=1`, synthetic properties).

## Notes

- `base.html` asset `?v=` was not bumped (outside scope). Staging may need a hard refresh until the next version bump.
- At narrow widths a long mode label can truncate inside the closed select; the open list shows it in full. The font is kept at 16 px to avoid iOS zoom.

## Owner steps

1. Open Properties on staging. Each row shows the full link. Press the copy icon and paste it somewhere.
2. Change "When to send to UbyPort" on one row. "Saved" appears. Open that property's Settings → Automation and check that the same value is shown.
