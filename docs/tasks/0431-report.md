# 0431 report: property page — scrape prefill, review screen, public template

Status: review

## Files

- `App/app/migrations/0029_property_page.sql` (new): the page content row
  (description, photos_json, amenities_json, times, publish flag).
- `App/app/property_page.py`: `page_for`, `prefill_from_import`
  (deterministic field mapping, empty-fields-only), `save_page`,
  `publish_page`.
- `App/app/routes/property_page.py`: the public template render (was 0430's
  stub) — name, district, times, description with a no-JS `<details>`
  collapse, amenities list, "everyone"-and-done guide cards.
- `App/app/routes/payments.py`: host review screen
  `GET/POST /apartments/{id}/page` (edit + publish toggle).
- `App/app/templates/property_page.html` (new): Airbnb-pattern layout
  (hero grid slot, 65ch description, sections), light mode, no third-party
  scripts, no-JS.
- `App/app/templates/property_page_review.html` (new): review screen.
- `App/app/host_i18n.py`: page/pp strings (en/cs).
- `App/tests/test_property_page.py` (new): 7 tests.

## Commands (last lines)

- `pytest tests/test_property_page.py` → 7 passed
- full branch row (payments + pages + mail contract) → 138 passed
- `migration_guard.py <base>` → OK; `context_lint.py` → OK
- Browser/geometry + 390 px screenshots: CI browser shard (sandbox cannot
  launch Chromium); check the shard before merging (rule 7).

## Findings

- Prefill maps verbatim (0347-trimmed) fields; a re-import never overwrites
  a host edit (tested).
- The public page renders from confirmed data only: guide cards must be
  `visibility='everyone'` AND `state='done'` (drafts/missing never publish,
  tested).
- A page can publish without a `property_page` content row (0430 semantics:
  the slug row's publish flag is the gate); content is optional.

## Deviations

- The review screen lives under the payments router's host-CSRF router
  (`/apartments/{id}/page`) rather than a new router — same guard, one
  include. If the design review wants it under Properties' routes file,
  it is a two-file move.
- Photo download (brief 0432) is not in this commit; `photos_json` renders
  when present.

## Owner steps

1. Check the CI browser shard for the two new pages at 390 px.
2. Merge when green; brief 0432 (OTA photos) follows on the same branch.
