# 0078 report: Properties list and read-only cross-property summaries

Status: review. Executor: Claude (owner-authorized), combined staging lane §2 mode.

- Start: `f49e3de` (0076 at review). Code commit: `7831cdc` (14 files, +445/−19 including 6 PNGs).

## Anchors

- `admin.py` `@router.get("/apartments")` is unchanged.
- `return _property_hub_redirect(request, "communication")` is unchanged. The multi-property branch of `_property_hub_redirect` was already a 0094 Settings redirect for one property; it now targets `/apartments#property-summaries`.

## What changed

- **List (`apartments.html`)**: each row shows the name, location (`addr_obec`), IDUB name, legal operator, calendar count, stays and the setup pill. A visible **Open** button sits before the row menu. In the menu:
  - Edit now goes to Settings → Property information `#basics`.
  - Guest links / Automation now use canonical `?view=settings&section=…` URLs. The old `#ubyport` "Automation" hash pointed at Reporting, not Automation.
  - A property without a business gets **Choose business**, which opens its own Settings `#operator-picker`.
  - Add property, Update calendars, Delete (archive), the archived list with Restore, and the empty states are unchanged.
- **Shared records, linked once** (`.properties-shared`):
  - **Business & legal details** opens `/entities?edit={id}&next=/apartments` when there is one business, else `/entities`. With no business there is no link; the empty state already says "Add operator".
  - **Door lock account** (`/smart-locks`) appears only when TTLock is enabled and an account is connected. It is not shown as an onboarding nag.
- **Summary** (`#property-summaries`, "Guest links and reporting timing"): a visible section with a header bar and a `?` tip, not a `<details>`. Each row has the property, its guest link `/l/<key>` and its reporting timing (mode label, plus hours when scheduled). Each value links to that property's Settings group (Guest experience `#communication` / Automation `#automation`). It has no form, input or name attribute (tested). Archived properties are excluded. The link key is read with `guest_slug.current` or the permalink token, so a GET never creates a slug (tested).
- **Legacy and Search**:
  - `/guest-links` and `/automation`: one property → its Settings group (unchanged); none or several → `/apartments#property-summaries`.
  - In `api.py`, the command-palette Guest links/Automation entries follow the same rule. A Door lock account entry appears only when a lock account is connected.
  - `/apartments`, `/entities` and `/invoices/settings` entries are kept.
- `host_i18n.py` `_PROPERTIES_0078_STRINGS` (7 keys, EN+CS). `host.css` `/* 0078 */` block. The 0076 section-head title now uses `flex: 1 1 0; min-width: 0`, so the `?` stays on the title line on mobile.
- `_components.html` was not edited; the existing `help_tip`/`nav_icon` were enough.

## Deviations

- The brief says "optional native disclosure". Plan §4 rule 2 (binding) makes it a visible section instead.
- There is no list filter today, so there is no separate "no-match" state. Empty (no business), empty (business, no property) and archived stay distinct (tested).
- Copied-property navigation lives on the create/settings pages (`copy_from`). It is untouched, so there is no list action for it.
- Files outside §3: `tests/test_property_hub.py`. Its two multi-property redirect assertions are now `/apartments#property-summaries`, an intentional change with a replacement assertion.

## Commands (from App/, staging/mock/REQUIRE_BROWSER, pinned Chromium)

```
pytest tests/test_host_properties_navigation.py -q -rs          → 8 passed
pytest <58 entity/invoice/properties/settings/search files> tests/test_host_properties_navigation.py
       tests/test_property_readiness.py tests/test_property_navigation_browser.py -q -rfEs
       (UBYHOST_SHOTS_DIR set)                                  → 836 passed, 0 failed, 1 skipped
   skip: test_dashboard_missing_banner.py:174 evidence-capture gate (pre-existing, not browser/geometry)
pytest tests/test_endtoend.py -q                                → 28 passed
ruff (E9,F63,F7,F82,F401,F841) → All checks passed   context_lint → OK
```

These include the brief §6 set: test_property_hub, test_host_redesign, test_host_property_controls_browser, test_host_wide_geometry_browser, test_property_readiness. The full suite with coverage was not run (coordinator: focused tests only).

## §7 evidence

- [x] One/many/none/archived: `test_no_business_and_no_property_states_stay_distinct`, `test_list_rows_show_location_setup_calendars_and_an_aligned_open`, `test_summary_is_visible_read_only_and_links_to_each_editor`.
- [x] Read-only summary with correct property/section links; no GET mutation (`test_listing_never_creates_a_guest_link_slug`).
- [x] Search, legacy redirects and shared entity/lock routes reachable: `test_hub_redirects_for_none_one_and_many`, `test_lock_account_link_only_when_connected`.
- [x] Browser: no overflow and nothing clipped at 360/390/768/1024/1280/1440/2048 EN/CS, with the rail expanded and collapsed at ≥1024.
  - Open sits at one right edge on every row (≥1024).
  - The summary panel shares the list lane.
  - The summary has no `<details>`.
  - `/guest-links` lands on the summary in view.
- [ ] CI on the task head: not run (no push).

## Evidence

`docs/tasks/0078-evidence/properties-{360,390,1280}-{en,cs}.png` (`UBYHOST_CAPTURE_0078=1`; synthetic properties "Byt Alfa", "Chata Beta…", "Studio Gama", archived "Starý byt").

## Owner steps

1. Look at `properties-1280-en.png` and `properties-360-cs.png`.
2. On staging with two properties: open Search → "Guest links"; you land on the summary. Click a timing value; that property's Automation settings open.
