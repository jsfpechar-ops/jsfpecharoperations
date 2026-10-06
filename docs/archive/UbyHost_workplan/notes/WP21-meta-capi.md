# WP21: Meta Conversions API sign-up conversion (server-side, consent-gated)

Commit `a56eaf2` on branch `wp20`, **stacked on WP20** (`2443e70`). Apply `WP20-signup-google-ads.patch` first, then `WP21-meta-capi.patch`. Both patches were checked to apply in order on `wpbase` and reproduce the branch exactly. Legal basis: new section 6 of `04_legal_positions.md`.

## Summary

- `fbclid` is captured like `gclid`. It is read on the server on the landing, pricing and sign-up pages, validated (`[A-Za-z0-9_-]{1,500}`, case kept), and carried with its first-seen time only in the signed `click` value (link and hidden field). No cookie, no Meta Pixel, no Meta script.
- A separate optional, unticked Meta box is shown only when the click carried `fbclid` **and** the Conversions API is configured. Its wording says "came from Facebook or Instagram", because Facebook adds `fbclid` to group and post links as well as ads. EN and CS text are verbatim from legal section 6, with a "How Meta uses data" link. Consent text versions: `ads-meta-v1-en`, `ads-meta-v1-cs` in `consent_texts`.
- Ticked: an `ad_click` row with platform `meta` and `fbc = fb.1.<first-seen ms>.<fbclid>`. This is Meta's format for a value built on the server. Not ticked: nothing about the click is stored.
- `signup.activate` (e-mail verified) calls `meta_capi.enqueue`, which only writes the database. It sets `send_state = pending` and a random 32-hex `event_id`.
- New scheduler job `meta_capi` (every 10 minutes) runs `meta_capi.send_pending`. It works outbox-style:
  - claims the row with a compare-and-set;
  - makes the HTTP call with no transaction open (a test checks that another connection can take the write lock during the call);
  - writes the result afterwards.
- Retries: network errors, HTTP 5xx, 429, `is_transient`, and Graph codes 1, 2, 4, 17, 32, 341, 613 and 80004 are retried with backoff (2, 4, 8 min and so on, up to 6 h), at most 8 attempts. Code 100 and other client errors fail at once. Token or dataset errors (codes 10, 190, 200, 803) raise an admin alert and are retried. A claimed row stuck in `sending` for 10 minutes is handed back.
- Meta rejects an `event_time` more than 7 days old, so events not sent within 7 days minus 1 hour are marked `expired` and never sent. This also runs while the API is off.
- Request: `POST https://graph.facebook.com/<UBYHOST_META_GRAPH_VERSION>/<UBYHOST_META_DATASET_ID>/events`, form fields `data` (JSON) and `access_token`, plus `test_event_code` only when configured. The token is never in the URL. Timeout 10 s. Uses `requests`.
- Event, exactly:
  `{"event_name": "CompleteRegistration", "event_time": <verification time, s>, "event_id": "<random>", "action_source": "website", "event_source_url": "<UBYHOST_PUBLIC_BASE_URL>/signup", "opt_out": true, "user_data": {"fbc": "<fbc>"}}`.
  No e-mail, phone, name, IP address or user agent.
- Deletion: `fbc` is blanked 7 days after a successful send (`uploaded_at`), at once when the send failed or expired, on withdrawal, and at the latest 90 days after the click. The row stays as the consent record.
- Withdrawal: Settings > Privacy shows "Use my sign-up to measure UbyHost's Facebook and Instagram campaigns". Unticking it blanks `fbc`, sets `send_state = withdrawn` (an unsent event is never sent), and logs `ads_consent_withdrawn` (`meta; uploaded=no|yes`). Admins can withdraw from the Users menu.
- Source flag: `user_account.signup_source` is `google`, `meta` or `none`. A consented click decides first; otherwise the `utm_source` label (`google`/`adwords`/... or `facebook`/`fb`/`instagram`/`ig`/`meta`). An unconsented click never counts. The Users list shows "Source: ...". The admin sign-up mail gains a "Facebook/Instagram click (with consent)" line.
- Privacy page: a "Facebook and Instagram measurement" paragraph (`#signup-meta`, EN and CS verbatim from legal section 6), shown while sign-up is on and Meta is configured. There is also a "Recipients for ad measurement" line: Google Ireland Ltd. always, Meta Platforms Ireland Ltd. when configured.
- `/subprocessors`: a "Recipients that are not subprocessors" panel while sign-up is on, with the Meta sentence when configured.
- Config: `UBYHOST_META_DATASET_ID`, `UBYHOST_META_ACCESS_TOKEN`, `UBYHOST_META_TEST_EVENT_CODE`, `UBYHOST_META_GRAPH_VERSION` (default `v26.0`, the latest version on 4 Oct 2026). Everything is off while the dataset ID or the token is empty.

## Files changed

- `App/app/meta_capi.py` (new): enqueue, payload, HTTP call, retries, expiry.
- `App/app/signup.py`: platform `meta` (`fbclid`, `fbc`, consent field `meta_consent`, version `ads-meta-v1`, retention 90/7 days), `platform_active`, `signup_source`, enqueue on activation, withdrawal stops unsent events, purge expires and blanks.
- `App/app/config.py`: the four `META_*` settings and `meta_capi_enabled()`.
- `App/app/db.py`: `ad_click.fbc`, `event_id`, `send_state`, `attempts`, `next_attempt_at`, `last_error`; `user_account.signup_source` (schema and `ADDED_COLUMNS`); index on `(send_state, next_attempt_at)`.
- `App/app/scheduler.py`: `_job_meta_capi`, job level `meta_capi`.
- `App/app/mail_notify.py`: `meta_click` line in the admin sign-up mail.
- `App/app/routes/admin_accounts.py`: Users list selects `signup_source` and active Meta consent.
- `App/app/routes/legal.py`: `signup_meta_notice`, `signup_recipients_notice`.
- `App/app/host_i18n.py`: `_META_STRINGS` (EN, CS).
- `App/app/templates/privacy.html`, `subprocessors.html`, `users.html`.
- `App/tests/test_meta_capi.py` (new).
- `deploy/lightsail/.env.example`: Meta placeholders.

## Tests added

`App/tests/test_meta_capi.py`, 26 tests, HTTP mocked (any unmocked call fails the test):
- capture: `fbclid` signed with its time, no raw value in the page, the box unticked and not required;
- the box needs both `fbclid` and a configured API (a ticked box posted while off stores nothing);
- wording: "Facebook or Instagram", no "ad"; both languages exactly as in legal section 6;
- consent on: `fbc` format, consent version and text, nothing sent before verification, source `meta`;
- consent off: no row, source from UTM; the source-flag rules;
- verification queues the event and makes no HTTP call;
- exact payload, URL, form fields and token placement; `test_event_code` added only when set;
- retries: network error, then 503, then success (attempts 3), backoff respected; transient flag and code 17 retried; code 100 fails at once and `fbc` is purged; 8 attempts end as failed; code 190 raises an alert and retries;
- 7-day window expiry, also with the API off;
- no database transaction is open during the HTTP call; a stale claim is handed back;
- deletion 7 days after sending (6 kept, 8 deleted) and 90 days after the click, consent record kept;
- withdrawal in Settings before sending: never sent, audit written; Settings page shows the toggle; admin withdrawal;
- no cookies beyond session, CSRF and language along the whole flow, no `_fb*` cookie, no Meta script;
- privacy and `/subprocessors` text when configured, hidden when not;
- the scheduler job calls `send_pending`.

## Test commands and results (exact counts)

From `/tmp/wp/wp20/App` at commit `a56eaf2`, `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_meta_capi.py`: 26 passed.
- Related set (`test_meta_capi`, `test_signup`, `test_scheduler`, `test_host_i18n`, `test_access_log`, `test_cookie_inventory`, `test_no_tracking`, `test_claim_mail`): 170 passed.
- `test_[a-c]*`: 284 passed, 2 skipped.
- `test_[d-g]*` without the browser e2e: 615 passed.
- `test_[h-o]*` (run before the 26th test was added, so with 25 Meta tests): 506 passed, 1 skipped, 1 failed (`test_host_geometry`, Playwright launch in this sandbox, same on `wpbase`).
- `test_[p-s]*`: 677 passed, 1 failed (`test_stale_submission`, order-dependent, same on `wpbase`).
- `test_[t-z]*`: 152 passed.
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why

- `opt_out: true` is added to the event. It is a flag, not personal data. Meta documents that with it "we only use the event for attribution", which matches a consent "to measure our campaigns". If the owner wants Meta to optimise delivery on sign-ups, remove it, change the consent and privacy wording, and bump `CONSENT_VERSIONS["meta"]`.
- `event_name` is sent (required by Meta). `data_processing_options` is omitted: Meta only offers US Limited Data Use, nothing for the EU.
- **`client_user_agent` is not sent, as the brief requires, but Meta's docs say website events "require" it.** [UNVERIFIED] whether Meta rejects such an event or only flags it. If the staging test with `UBYHOST_META_TEST_EVENT_CODE` is rejected (Graph code 100), the event ends as `failed` with the error in `ad_click.last_error`. The fix then needs a decision: store and send the user agent (new consent text) or drop the integration.
- The Meta box is hidden while the API is not configured, so consent is never collected for something the app would not do.
- The "sent" time reuses `ad_click.uploaded_at` (the Google export time), so one retention rule covers both platforms.
- Retention after sending: 7 days, the owner's default. No Meta source requires keeping it at all.
- A withdrawal that lands while a send is in flight cannot stop that one request. The row ends as withdrawn, and its `fbc` is already blanked.
- No admin funnel page exists on `wpbase` (WP11 not applied here). The source is shown on the Users list and stored for WP11.

## What Cursor must verify or adapt when applying on the real main

- Apply after WP20. `db.py` conflicts as for WP20: keep the WP21 columns in both `SCHEMA` and `ADDED_COLUMNS`.
- If WP06 (worker process) has landed, register `_job_meta_capi` wherever the scheduler jobs now live. Keep it out of the web process.
- If WP07 (heartbeats) or another WP lists job IDs, add `meta_capi` and its `notification.job_name.meta_capi` label.
- If WP11 has landed, use `user_account.signup_source` for the source column.
- If WP09 (Umami) has landed, make sure no Umami or other script reaches `/signup` and that marketing-page tracking excludes query strings (`fbclid`).
- `config.PUBLIC_BASE_URL` must be the production origin and a domain verified in Meta Business Manager; `event_source_url` is built from it.
- Hand-review `meta_capi.send_pending` (claim, stale reset, result writes) and `signup.withdraw_consent` (`send_state` handling).
- Run the full suite in one process.

## Manual steps for the owner

1. In Meta Events Manager, create or choose a dataset (pixel) and generate a Conversions API access token (Settings > Conversions API > Generate access token). Do not install the Pixel.
2. Verify the site's domain in Meta Business Manager.
3. On staging, set `UBYHOST_META_DATASET_ID`, `UBYHOST_META_ACCESS_TOKEN` and `UBYHOST_META_TEST_EVENT_CODE` (from Events Manager > Test events). Run a sign-up from a link with `?fbclid=...`, tick the Meta box, verify the e-mail, wait up to 10 minutes, and check the Test events tab. Check `ad_click.send_state` and `last_error` if nothing arrives. Meta says test events are not dropped, so use a test dataset if you have one.
4. Remove `UBYHOST_META_TEST_EVENT_CODE` in production.
5. Have counsel approve the Meta box and privacy paragraph (legal section 6). Any wording change needs a new `CONSENT_VERSIONS["meta"]`.
6. Requests from people about Meta data: forward them to Meta within 7 days using Meta's form, as the Controller Addendum requires.
7. Put `utm_source=facebook` (or `instagram`) in your ad and group links, so sign-ups without consent still count in the source column.
