# 0432/0433 report: OTA photos + page meta (sitemap, noindex, OG, preview)

Status: review

## Files (0432 photos)

- `App/app/property_page.py`: `store_photo` (re-encode + shrink via the 0343
  pipeline — EXIF stripped, one clean JPG), `download_listing_photos`
  (https-only, max 10, never hotlink), `delete_photo`, `photos_dir`.
- `App/app/routes/property_page.py`: public `GET /photos/property/<hex>.jpg`
  (regex-gated, 404 on traversal, long cache).
- `App/app/guest_guide_import.py`: `_photo_urls` (Booking/Airbnb shapes); the
  worker's success path feeds the page prefill + photos in the same run — a
  photo failure never fails the import (text stands).
- Review screen: photo grid with delete + the rights notice (en/cs).

## Files (0433 meta)

- `App/app/migrations/0029_property_page.sql`: `hide_from_search` default 1
  (noindex unless the host opts in — owner decision).
- `App/app/property_page.py`: `published_pages()` (published + search-visible).
- `App/app/routes/property_page.py`: `/sitemap.xml` (rate-limited, correct
  content type); `noindex` meta default-on; OG/Twitter tags with the first
  photo; guest preview = the real public URL from the review screen.
- `App/app/templates/base.html`: `{% block head_extra %}`.
- Review screen: "Hide from search engines" toggle + preview link.

## Commands (last lines)

- `pytest tests/test_property_page_photos.py` → 6 passed
- `pytest tests/test_property_page_meta.py` → 4 passed
- full branch row → all payments/pages/mail tests green
- Browser/geometry + 390 px: CI shard (sandbox has no Chromium).

## Findings

- The stored photo file is pixels-only (reencode drops every metadata block,
  including GPS); max 10 per property, per-file cap from 0343.
- The page references only our re-hosted copies — an OTA CDN URL appears
  nowhere in the page (tested).
- Sitemap excludes hidden + unpublished pages; noindex is the default state.

## Owner steps

1. CI browser shard check (review screen + public page at 390 px).
2. Merge when green. 0434 (booking widget) follows on this branch.
