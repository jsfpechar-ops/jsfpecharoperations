# WP20: Self sign-up page with Google Ads conversion import (HIGH RISK)

Commit `2443e70` on branch `wp20`, based on `wpbase`. Amended on 4 Oct 2026 to follow legal positions 2 and 3 (`04_legal_positions.md`). WP21 (`WP21-meta-capi.patch`) is stacked on top of this commit; apply WP20 first.

## Summary

Sign-up flow (unchanged by the amendment):
- New `/signup` page (public auth layout): e-mail, password (same policy as today), business or workspace name, a required Terms/DPA/Privacy checkbox (recorded through `acceptance.record` as `clickwrap`), Turnstile (action `host_signup`).
- Behind `UBYHOST_SIGNUP_ENABLED` (default `0`). While off, `/signup`, `/signup/verify` and the CSV export return 404, the landing page links to `/login`, and the privacy page is unchanged.
- Sign-up creates an inactive account and queues a `signup_verify` mail (24 hours, newest link only). Unverified accounts cannot sign in and are deleted after 7 days.
- The verification page asks for the sign-up password again. A GET does nothing. This defeats link-prefetching scanners and pre-account takeover.
- Activation signs the host in; the existing 2FA setup and onboarding follow. The operator gets a `signup_admin` mail.
- No account enumeration: a taken address gets a `signup_exists` mail (at most one per hour) and the same page.
- Rate limits: 10 per IP per hour, 3 per e-mail per hour. Login also accepts the e-mail address.

Click identifiers (legal position 3, new in the amendment):
- `gclid`, `gbraid` and `wbraid` are read on the server from the landing (`/`), pricing (`/cenik`) and sign-up page query strings and validated (`[A-Za-z0-9_-]{1,200}`).
- They are packed with the landing-page request time (ms) into one signed value, `click` (itsdangerous, salt `ubyhost-signup-click`). It travels only in the `/signup` link and a hidden form field. No cookie, no Google script, nothing in the database before submit.
- The form post accepts only the signed value. A raw `gclid` posted in the form is ignored. A tampered value, one older than 90 days, or one from the future is ignored.
- The Google consent box is shown only when the click carried a Google identifier. It is unticked, not required, placed under the terms box, and uses the legal text verbatim (EN and CS), with the "How Google uses data" link.
- Ticked: one `ad_click` row (`gclid`, `gbraid`, `wbraid`, `clicked_at`, `consented_at`, `consent_text_id`). Not ticked: nothing about the click is stored.
- `consent_texts` table: `version` (`ads-google-v1-en`, `ads-google-v1-cs`), `purpose`, `lang`, exact `text` as displayed (the link written as `[label](url)`), `text_sha256`. If the wording changes without a version bump, the new text is filed under `<version>-<hash8>`, so a consent never points at text that was not shown.
- Export (`POST /admin/ads-conversions.csv`, admin only): rows with consent, not withdrawn, e-mail verified, `gclid` present, click within 85 days, not exported before. Export sets `uploaded_at`. "Download again" (`again=1`) repeats earlier rows without changing `uploaded_at`. CSV format unchanged (see below).
- Deletion (`signup.purge`, 12-hourly `photo_sweep` job): identifiers are blanked 90 days after the click or 30 days after `uploaded_at`, whichever is first, and at once on withdrawal. The row stays as the consent record (`ids_deleted_at` set).
- Withdrawal: Settings > Privacy ("Use my sign-up to measure UbyHost's Google Ads"), a checkbox that is on; untick and save. It sets `withdrawn_at`, blanks the identifiers (uploaded or not), excludes the row from all later exports, and writes audit `ads_consent_withdrawn` (`google; uploaded=yes|no`). Admins can still withdraw from the Users menu. Re-enabling is not offered (the identifier is gone).
- Privacy page (`#signup-ads`): the legal-position-3 paragraph verbatim, EN and CS, plus a short "Self sign-up" paragraph about account data and UTM labels (`#signup`). Shown only while sign-up is on.

Setup-tips opt-out (legal position 2):
- Unticked box "Do not send me setup tips by e-mail (you can change this anytime in Settings)." (EN and CS verbatim). Stored as `user_account.onboarding_emails_opt_out` (0/1) and `onboarding_emails_opt_out_at`.
- Both columns are only in `ADDED_COLUMNS`, not in `CREATE TABLE`. `_add_missing_columns` skips an existing column, so the other WP that adds them can land before or after this one.

Access logs (checked, no change needed in the app):
- Caddy: both `deploy/lightsail/caddy/Caddyfile.acme` and `Caddyfile.cloudflare` have no `log` directive, so Caddy writes no access log. I added a comment to both saying click identifiers are one more reason, and that any future `log` needs a query-string filter.
- uvicorn: `Dockerfile` (line 39) and `render_start.sh` run with `--no-access-log`.
- App access log: `main._log_access` logs `method`, the matched route template (`_access_route`), status and ms. Never the path, query string, IP or user agent. A new test sends `gclid`, `gbraid`, `wbraid` and `fbclid` and checks none reach the log.
- Exception logging (`main.py` line 178) also uses the route template.
- Not covered: `App/run.sh` (local development only) starts uvicorn without `--no-access-log`, so a developer's terminal shows query strings.

### CSV format (Google Ads Help 7014069, opened 4 Oct 2026)

```
Parameters:TimeZone=Europe/Prague
Google Click ID,Conversion Name,Conversion Time,Ad User Data,Ad Personalization
<gclid>,UbyHost sign-up,2026-01-15 13:00:00+0100,Granted,Denied
```

- Verified in the help text: the parameters row, the column names, `Granted`/`Denied`, the time format `yyyy-MM-dd HH:mm:ss+z`.
- [UNVERIFIED] the exact header text of Google's downloadable template. Compare once and edit `CSV_HEADER` in `app/signup.py` if needed.
- Conversion Time is the e-mail verification time. Personalisation is always `Denied`.
- `gbraid`/`wbraid` are stored with consent but not exported. Google's help page names them for upgraded imports, but I found no column names for them in the legacy file. Rows with only a braid are deleted on schedule without being used.

## Files changed

- `App/app/config.py`: `SIGNUP_ENABLED`, `SIGNUP_NOTIFY_EMAIL`, `ADS_CONVERSION_NAME`. (`ADS_CLICK_WINDOW_DAYS` removed: the windows are fixed in `signup.py`.)
- `App/app/db.py`: `user_account` sign-up columns, unique index on `email`, new tables `consent_texts` and `ad_click`, opt-out columns via `ADDED_COLUMNS`.
- `App/app/auth.py`: `authenticate` accepts an e-mail as well.
- `App/app/mail.py`, `App/app/mail_notify.py`: mail kinds `signup_verify`, `signup_exists`, `signup_admin`.
- `App/app/signup.py` (new): signed click value, consent texts, register/activate, withdrawal, purge, export.
- `App/app/routes/signup.py` (new): `/signup`, `/signup/verify`, `POST /admin/ads-conversions.csv`, `/admin/users/{id}/ads-consent/withdraw`, `POST /settings/privacy/ad-consent`.
- `App/app/routes/admin.py`: includes the signup router; landing `signup_href`; Settings gets `ad_consents`.
- `App/app/routes/admin_accounts.py`: Users list selects e-mail, sign-up fields and active Google consent.
- `App/app/routes/legal.py`: pricing `signup_href`; privacy notice flag.
- `App/app/retention.py`: workspace deletion also deletes `ad_click` rows (foreign key).
- `App/app/scheduler.py`: `signup.purge()` in `_job_photo_sweep`.
- `App/app/host_i18n.py`: `_SIGNUP_STRINGS` (EN, CS), including the legal texts and Settings > Privacy strings.
- `App/app/templates/signup.html`, `signup_sent.html`, `signup_verify.html` (new).
- `App/app/templates/landing.html`, `pricing.html`, `privacy.html`, `users.html`, `settings.html`.
- `App/tests/test_claim_mail.py`: pinned mail kinds.
- `App/tests/test_signup.py` (new).
- `deploy/lightsail/.env.example`: sign-up placeholders.
- `deploy/lightsail/caddy/Caddyfile.acme`, `Caddyfile.cloudflare`: comment only.

## Tests added

`App/tests/test_signup.py`, 40 tests. New or changed in the amendment:
- landing and pricing carry a signed click with the landing time, and no raw `gclid`;
- `gbraid`/`wbraid` captured and stored;
- the sign-up page keeps the landing click time;
- tampered, unsigned, too old and future click values are ignored;
- the Google box is only shown with a click ID; the setup-tips box is always there and unticked;
- the consent texts equal the legal wording (EN, CS); the Czech form shows both;
- the stored row points at the exact `consent_texts` version and text;
- no consent stores no `ad_click` row; consent without a click stores nothing;
- opt-out stored with its time; opt-out columns added idempotently (duplicate `ADDED_COLUMNS` entry);
- changed wording without a version bump gets its own version;
- admin withdrawal and Settings > Privacy withdrawal (audit, export exclusion, page state); leaving the box on changes nothing;
- deletion at 89/91 days after click and 29/31 days after upload, consent record kept;
- unverified sign-ups take their click rows with them;
- export: 85-day window (84 in, 86 out), withdrawn excluded, `uploaded_at` set, second export empty, "download again" repeats without moving `uploaded_at`, GET never exports;
- privacy paragraph EN and CS;
- click IDs never reach the access log.

## Test commands and results (exact counts)

From `/tmp/wp/wp20/App` at commit `2443e70`, `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_signup.py`: 40 passed.
- Related set (`test_signup`, `test_claim_mail`, `test_guest_mail`, `test_accounts`, `test_login_*`, `test_no_tracking`, `test_cookie_inventory`, `test_host_i18n`, `test_db_upgrade`, `test_scheduler`, `test_admin_route_split`, `test_users_disable_confirm`, `test_access_log`, `test_retention*`): 308 passed.
- `test_[a-c]*`: 284 passed, 2 skipped.
- `test_[d-g]*` without the browser e2e: 615 passed.
- `test_[h-o]*`: 481 passed, 1 skipped, 1 failed (`test_host_geometry::test_the_month_filter_shares_its_page_edges`, Playwright launch failure in this sandbox, same on `wpbase`).
- `test_[p-s]*`: 677 passed, 1 failed (`test_stale_submission::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`, order-dependent, same on `wpbase`, passes alone).
- `test_[t-z]*`: 152 passed.
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.
- The full suite was not run in one process (170 s limit per call).

## Deviations from the spec and why

- Click IDs live in a new `ad_click` table instead of `user_account` columns. One row per platform holds the consent record, the identifiers, and the upload state; WP21 reuses it for Meta.
- The click value in links is a signed token (`click=`), not the raw `gclid=`. The legal text asks for the value in the link and the time in a signed field; one signed value does both and stops a client from choosing the click time.
- Withdrawal deletes the identifier even if it was already uploaded. The legal text requires it only for un-uploaded IDs. Nothing uses an uploaded one, and conversion retraction is not implemented.
- The export is now a POST (it marks rows exported). `uploaded_at` means "downloaded by the operator for upload": the upload itself happens in Google Ads by hand.
- `gbraid`/`wbraid` are not exported (column names unverified).
- The old hint under the ads box ("Optional. Your account works the same without it.") was removed, so the box shows exactly the recorded text.
- The Settings toggle for setup tips (legal position 2) is not part of this WP. Only the sign-up box and the two columns are. The onboarding-mail WP should add the toggle and the privacy paragraph from legal position 2.
- Earlier deviations still stand: password step on verification, login by e-mail, two extra mail kinds, Umami attributes inert.

## What Cursor must verify or adapt when applying on the real main

- `db.py`: keep `consent_texts` and `ad_click` in `SCHEMA` and the new `ADDED_COLUMNS` entries. If another WP added `onboarding_emails_opt_out*` first, keep one pair of entries (duplicates are harmless).
- Any code that deletes `user_account` rows must delete `ad_click` rows first (foreign key). This patch covers `retention._delete_workspace` and `signup.purge`.
- WP18 (Postgres): `INSERT ... ON CONFLICT (version) DO NOTHING` is used in `signup.consent_text_id`; it is valid in both databases.
- WP11 (funnel): stages from `user_account.signup_at` / `email_verified_at`; source from `signup_source` (WP21) or `ad_click`.
- WP12 or the onboarding-mail WP: honour `onboarding_emails_opt_out` before sending setup tips.
- Mail kinds: merge `KINDS`/`HOST_KINDS` and the pinned set in `test_claim_mail.py`.
- Landing/pricing CTA changes from other WPs: keep the `{% if signup_href %}` switch.
- A future Umami or analytics WP must not send query strings with click IDs (Umami `data-exclude-search` already covers this on marketing pages).
- Hand-review: `signup.read_click`/`attribution`, `signup.register`, `signup.withdraw_consent`, `signup.purge`, `signup.export_conversions`, `routes/signup.py` (`signup_verify_submit`, `ad_consent_settings`).
- Run the full suite in one process.

## Manual steps for the owner

1. Counsel: approve the texts now taken from `04_legal_positions.md` sections 2 and 3 (checkboxes, privacy paragraph). If any wording changes, bump `signup.CONSENT_VERSIONS["google"]`.
2. Google Ads: create the offline conversion action ("Import > Conversions from clicks"), set `UBYHOST_ADS_CONVERSION_NAME` to its exact name, turn on auto-tagging, accept the customer data terms. Keep enhanced conversions for leads off for this action.
3. Download Google's click-conversion template once; compare headers with `CSV_HEADER`; check whether it has GBRAID/WBRAID columns.
4. SES mail must be live; without it nobody can verify.
5. Enable on staging first (`UBYHOST_SIGNUP_ENABLED=1`), run a sign-up with `?gclid=TEST123`, tick the box, verify, check Settings > Privacy and the CSV.
6. Upload the CSV in Google Ads straight after downloading it (the download marks rows as uploaded). Use "Download again" if an upload failed.
7. After the first upload, check that rows with `Ad Personalization=Denied` are counted.
