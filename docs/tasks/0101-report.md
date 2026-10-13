# 0101 report: old links removed

Record: [0101](0101-remove-legacy-links.md). Base `fdcd8da` on `claude/quirky-lamport-9svmd1`.

## Removed (404, or 405 for a POST)

- `GET /automation`, `GET/POST /invoices/settings`, `GET/POST /stay-fees/{id}/setup`, `GET /apartments/{id}/ws-request.txt`. Also `/setup` and `/setup/{step}`: `routes/setup_wizard.py`, `templates/setup/*`, `_save_address_only`, 30 `setup.*` strings and the `.wizard*` CSS.
- The app.js `HASHES` table and the `#ws-request-letter` id. `destination()` now uses only the element the hash names in the page, then `?view=&section=`.
- `GET /invoices/{invoice_id:int}`: a non-number path is now a 404 instead of a 422.

## Links changed to canonical

- Invoice settings in the sub-tabs, Search and the invoice picker now go through `access.invoice_details_url()`. With one business it opens `/entities?edit={id}&next=/invoices#entity-invoice`. Otherwise it opens `/entities`.
- These links now carry `?view=…&section=…`:
  - onboarding step URLs and `communication_url`;
  - the dashboard missing-details banner and empty state;
  - Stays empty state;
  - the stay-detail guest-link links;
  - the submission header help;
  - the `#door-code` and `#communication` return targets in `admin.py`.
- Setup banner: it linked `/setup`, now `onboarding.setup_url()`.

## Kept

- `GET /guest-links`: lifecycle tips already sent link it. The tip `lifecycle_no_guest` now links `/apartments#property-summaries`.
- The no-JS `:has(:target)` CSS. The Overview readiness links use in-page `#fragment`s, and `_property_overview.html` belongs to the parallel worker.
- `/l/` guest links and slug redirects, feeds, callbacks, auth and public pages.

## Tests

- New: `test_no_dead_internal_links.py`, which runs 27 pages plus Search, form targets, JS literal paths, a scan for the removed patterns, 404s, and the kept e-mail redirect. Checked: a reintroduced `/invoices/settings` link makes it fail.
- New: `test_setup_banner.py`, which replaces `test_setup_wizard.py`. Kept from the old file: the banner and `wizard_step` checks.
- Deleted (they tested removed adapters only):
  - the wizard tests in `test_calendar_platform_required` and `test_host_copy_corrections` (address-only save ×2);
  - the legacy GET/guard/POST tests in `test_fee_setup_compatibility` and `test_entity_editor_navigation`.
- Rewritten to the canonical routes:
  - fee save via the property, invoice details via `POST /entities/{id}/invoice`;
  - `test_invoice_settings`, `test_entity_editor_fields`, `test_ares`, `test_invoice_autofill`;
  - `/automation` tests now assert 404;
  - `test_host_ux_acceptance` (`test_removed_old_links_are_gone_and_write_nothing`; the no-JS `#ubyport` check uses the canonical URL);
  - `test_property_navigation_browser` (hash loop uses canonical URLs);
  - geometry routes;
  - the old-hash expectations in 7 page tests.
- `test_properties_table_chips`: the empty-host header check now targets the header CTA. The setup banner may itself link `/apartments/new`.
- Full suite: **3435 passed, 2 failed, 3 skipped** (19:52). The 2 failures are the known env-only ones (`test_feed_dns_pinning` concurrent, `test_posthog_snippet_browser`). The 3 skips are opt-in screenshot captures.
- `tools/smoke.py`: run as in CI, 44 pages, no failures. It now expects 404 on the 5 removed paths.
- ruff (CI selection) clean. `context_lint` clean except the existing status WARN.

## Evidence

`docs/tasks/0101-evidence/{dashboard,invoices,invoice-picker}-{390,1280}-en.png` (staging no-login, empty workspace). Continue setup → `/apartments/new`. Invoice settings → `/entities`.

## Notes

- `base.html` asset versions were not bumped, to avoid a conflict with the parallel worker. A stale cached app.js still has the old table, which is harmless.
- `docs/CLOUDFLARE.md` still lists `/automation` in a WAF path rule. It is harmless, and the owner can drop it.
- The decision line went into `ui-decisions.md`, because `decisions.md` is at its token cap.
- Order-dependent, not caused by this change: `test_ares::test_entities_fill_does_not_save` fails when run after `test_host_invoice_navigation` (an entity with the same IČO is left behind). It passes in the full-suite order.
