# WP07: Job heartbeats, static caching, compression

## Summary
- Optional `UBYHOST_HEARTBEAT_ICAL_URL` and `UBYHOST_HEARTBEAT_MAIL_URL` are pinged after a successful calendar sync and after a mail run in which every step succeeded. They use the same 5 s timeout and warning log as the submit heartbeat, through one shared `_ping` helper.
- Versioned `/static` responses get `Cache-Control: public, max-age=31536000, immutable`. HTML keeps `no-store, private`.
- Every `src`/`href` static URL in the templates now carries `?v=`.
- `encode zstd gzip` in both Caddyfiles.
- `signature.js` loads only on the guest form page (which holds the signature step) and on the PIN page.

Stacked on WP05 and WP06.

## Files changed
- `App/app/config.py`: two new heartbeat URLs.
- `App/app/scheduler.py`: `_ping(url, job_id)`; ical and mail pings; `_heartbeat()` kept for submit.
- `App/app/main.py`: static Cache-Control in the existing middleware (200 and 304 only).
- `App/app/templates/guest/base.html`: `signature.js` behind `load_signature_js`; `guest/form.html` and `guest/pin.html` set it.
- 14 templates: `?v=20261004a` on images and the sample PDF that had no version.
- `App/tests/test_logo_placements.py`: exact-string asserts now expect `?v=`.
- `deploy/lightsail/caddy/Caddyfile.acme`, `Caddyfile.cloudflare`: `encode zstd gzip`.
- `deploy/lightsail/.env.example`, `docs/ENVIRONMENT.md`: all four dead-man URLs documented.
- `App/tests/test_wp07_cache_heartbeats.py`: new.

## Tests added
- A versioned static file has the immutable header. An unversioned one gets one day. A 404 under /static is not cached. `/login` keeps `no-store, private`.
- Guard test: every `src`/`href` `/static/...` URL in all templates has `?v=`.
- The ical and mail heartbeats ping on success, not on failure, and not when unset. A failing ping is logged, not raised.
- `signature.js` is absent on the stay page and present on the form page (order skeleton, then signature, then ticket kept) and on the PIN page.

## Test commands and results
- `pytest tests/test_wp07_cache_heartbeats.py tests/test_logo_placements.py tests/test_ubyport_sample_pdf.py tests/test_skeleton_loaders.py tests/test_security.py tests/test_scheduler.py tests/test_public_seo.py tests/test_error_pages.py`: 104 passed.
- Whole suite in chunks (WP07 tree): a-c 284 passed 2 skipped; d-f 316; g 299 passed 4 skipped; h 62 passed 1 skipped 1 failed; i-m 267; n-r 422; s 366; t-z 173. Total 2189 passed, 7 skipped, 1 failed. The failure is `test_host_geometry.py::test_the_month_filter_shares_its_page_edges` (Chromium cannot launch in this sandbox; it also fails on the unmodified base). The skips are browser tests, for the same reason.
- ruff (CI selection): all checks passed.

## Deviations from the spec and why
- Static files requested without `?v=` get `public, max-age=86400`, not the one-year immutable header. Those requests still exist after the template pass: the `/favicon.ico` redirect, the logo in e-mails, and absolute `og:image` / JSON-LD URLs for crawlers. A year-long immutable cache on them would pin an old file. Every template URL is versioned, so browsers get the year for all page assets.
- `og:image` and JSON-LD logo URLs (absolute, `{{ public_base_url }}/static/...`) were left without `?v=`. A test asserts the JSON-LD string, and crawlers do not benefit.
- The spec says "all three Caddyfiles". The repo has two (`Caddyfile.acme`, `Caddyfile.cloudflare`). `Caddyfile.active` is a copy that `deploy.sh` makes, and it is gitignored.
- `signature.js` is not used only by the signature pad. It also runs the form wizard, the date of birth input, the review step, the error-summary links and the PIN-page claim-secret carry-over. So it is loaded on `form.html` (all form steps, including the signature, are one page) and `pin.html`. Pages without them (pick, stay, claim, confirm, assigned, privacy, unavailable) no longer load it. On those pages it did nothing.

## What Cursor must verify or adapt when applying on the real main
- Guest page change: run `pytest tests/test_guest_browser_e2e.py -q -rs` with `UBYHOST_REQUIRE_BROWSER=1` (must say 0 skipped), including 320, 360 and 390 px. Walk the PIN page with a `#c=` claim link. This could not run here.
- `signature.js` itself did not change, so its `?v=` stays.
- WP09 (Umami on public pages) and WP17 (copy cleanup) also edit `landing.html`, `pricing.html`, `product.html` and the public chrome. Expect small textual conflicts on the `?v=` hunks. Keep both sides.
- From now on, bump `?v=` whenever a static file changes (the new guard test only checks that a version is present).

## Manual steps for the owner
In healthchecks.io (free tier), create one check per job. Put the ping URLs in the server `.env`, then redeploy.

| Check | `.env` key | Period | Grace |
|---|---|---|---|
| UbyPort submit sweep | `UBYHOST_HEARTBEAT_URL` | 10 min | 10 min |
| Calendar sync | `UBYHOST_HEARTBEAT_ICAL_URL` | 60 min | 30 min |
| Mail outbox | `UBYHOST_HEARTBEAT_MAIL_URL` | 5 min | 10 min |
| Nightly backup | `UBYHOST_BACKUP_PING_URL` | 1 day | 2 h |
| Litestream (WP05) | `LITESTREAM_HEARTBEAT_URL` | 5 min | 10 min |

Add an uptime check on `https://ubyhost.com/healthz` every minute (healthchecks.io does not do HTTP probes; use a free uptime monitor such as UptimeRobot or Better Stack). Send alerts to the owner's e-mail or phone. If the sweep period was changed with `UBYHOST_SUBMIT_SWEEP_MINUTES` or `UBYHOST_ICAL_POLL_MINUTES`, match the check period to it.
