# Before go-live: WP01 to WP09

> Status: this is the original specification. The code is in `series/` and the per-WP notes in `notes/` record every deviation. Where they differ, `series/` and `notes/` win.

Line numbers are from the PR 230 head and may have moved. Find the code by name.

---

## WP01: Deadline shows the filing time once a stay is reported

Background: review 2. Display only. Risk: low.

Problem: the deadline badge is computed from the arrival date only (`deadlines.urgency`, `deadlines.describe_time_left`) and ignores the stay status. The stays list (`templates/reservations.html`) and the stay page (`templates/reservation_detail.html`) show a reported stay as "overdue by 42 h" forever. The dashboard (`templates/dashboard.html`) does the same until it drops the stay 3 days after arrival.

Required behaviour:

| Stay status | Deadline cell | Level (tokens.css) |
|---|---|---|
| Not finished (waiting, incomplete, ready, failed) | Countdown, unchanged | unchanged |
| Reported, on time | "Reported 12.05. 14:32" | done (muted text in tables) |
| Reported after the deadline | "Reported 6 h late", or "Reported 2 days late" from 48 h | neutral |
| Not required (Czech guests only) | nothing | none |
| Cancelled or inactive | dash, unchanged | neutral |

"Reported" means `FINISHED_STATUSES` as used by `queue_groups` in `reporting.py`. The filing time is the latest `submitted_at` of the reportable guests. Late = filing time after `deadlines.reporting_deadline(check_in)`. Times in Europe/Prague, format as elsewhere in the host app.

Changes:

- `reporting.py`: helper `filed_at(progress)`; per row `deadline_state` (`countdown`, `filed_on_time`, `filed_late`, `none`), `filed_at`, `late_hours`. Compute once per row.
- `templating.py`: one global `deadline_cell(progress, check_in)` returning that state, so templates never call `urgency()` directly.
- `templates/_components.html`: macro `deadline_badge(...)`. Use it in the three templates, replacing the raw `<span class="deadline ...">`.
- `host_i18n.py`: `deadline.filed_at`, `deadline.filed_late_hours`, `deadline.filed_late_days`, EN and CS.
- `guide_i18n.py`: one sentence in the reporting section: after a stay is reported, its deadline shows when it was filed.

Tests:

- a reported stay past its deadline shows no "overdue" on the dashboard, stays list or stay page;
- a stay filed after its deadline shows "late" with the right hours or days;
- an unreported stay past its deadline is still critical (red);
- a Czech-only stay shows no deadline.

Effort: S.

---

## WP02: Property names in guest e-mails match the guest pages

Background: review 3.F. Risk: none for filing (`uby_name` still goes to UbyPort).

Problem: `mail_notify.property_label()` returns `uby_name` (the police-register name, often a code such as "č1") before `internal_name`. Guest pages use `internal_name` first (`routes/guest.py`, around 618-628). Guests see one name on the page and another in the e-mail.

Changes:

- `property_label()` prefers `internal_name`, falls back to `uby_name`.
- `invoice_issued` mail (`routes/invoices.py`): when the invoice is linked to a stay, add the property's `internal_name` to subject and body.
- Check `cancelled_with_guests` (PR 230 fix item 5) uses `property_label()` too.

Tests: one per guest mail kind (claim, claim_resend, reminder_guest, completion) asserting the subject contains `internal_name` and not `uby_name` when the two differ; one for the invoice subject with and without a stay.

Effort: S.

---

## WP03: Guide second pass for the owner decisions

Background: review 3.D. Text only. Risk: low.

Changes in `guide_i18n.py`, EN and CS:

- `guide.reporting.failure`: when a send gets no answer, the app retries once on its own in the next sweep; if that is still unclear, it holds the stay and alerts the host.
- New text: scheduled account deletion (the banner, sign-in kept until the deletion date, the ZIP download, what the ZIP contains including stay-fee filings).
- New text: calendar date changes. Guests do not sign again; the app fits their dates to the new booking.
- Check every other guide statement against the merged PR 230 behaviour and list any further mismatch in the PR description (fix it if it is text only).

Tests: the existing guide key-parity test (EN and CS have the same keys) passes; add one if it does not exist.

Effort: S.

---

## WP04: Admin access to guest data. HIGH RISK

Background: review 4.3. Owner decision: the owner is the only admin for now; no separate support role.

Today: impersonation (`routes/admin_accounts.py`, `/admin/users/{id}/impersonate`) gives the admin the host's full view, including document numbers, visa numbers, signatures and passport photos, with no reason and no time limit. `impersonation_stopped` is written to the admin's own workspace, so the host never sees the end of a session.

Required behaviour:

1. Starting impersonation requires a reason (free text, 5 to 300 characters). Store it in the `impersonation_started` audit detail.
2. Impersonation ends automatically 60 minutes after it started. Store the start time in the session payload; check it in the same place the session is read. On expiry, return to the admin's own view with a notice, and write `impersonation_stopped` with detail `expired`.
3. `impersonation_stopped` is written to the host's workspace (owner id of the impersonated account) as well as the admin's.
4. While impersonating, guest identity is masked by default:
   - document number, visa number: show only the last 3 characters;
   - signatures and passport photos: not shown, replaced by a "Hidden while supporting" placeholder with a Reveal button;
   - guest register PDF and CSV exports, and the workspace ZIP: blocked with a clear message.
   Names, nationality, dates and statuses stay visible (needed for support).
5. Reveal is per guest: asks for a reason, writes `guest_identity_revealed` (guest id, reason) to the host's workspace audit, and shows that guest's identity for the rest of the impersonation session.
6. One helper, `access.identity_visible(request, guest_id)`, used by every route and template that outputs the fields above. False when impersonating and the guest was not revealed.
7. Keep the existing impersonation bar in `templates/base.html`; add the remaining minutes.
8. Host Settings audit list: show reason and support sessions (start, stop or expiry, reveals). Add a "Support sessions" filter.

Steps for Cursor: first list every route and template that outputs document numbers, visa numbers, signatures, passport photos, or builds the register exports or the ZIP. Put the list in the PR description. Then apply the helper to all of them.

Tests:

- impersonation without a reason is refused;
- after 60 minutes (freeze time) the next request ends impersonation and writes the expiry row in the host's audit;
- every route from the list above returns masked data or is blocked while impersonating, and full data when the host is signed in;
- reveal writes the audit row and unmasks only that guest;
- the host sees start, stop and reveal rows in Settings.

Effort: M (1 to 1.5 days).

---

## WP05: Litestream continuous backup to S3

Background: review 6.2, 6.10. Owner decision: SQLite plus Litestream, no Turso. Today RPO is up to 24 h (nightly backup).

Changes (repo):

- `deploy/lightsail/docker-compose.yml`: a `litestream` service from the official Litestream image, pinned to a version tag, sharing the `/data` volume, `restart: unless-stopped`, small `mem_limit` (for example 128m).
- `deploy/lightsail/litestream.yml`: replicate the database at `UBYHOST_DB` (default `DATA_DIR/ubyhost.db`, see `config.py`) to `s3://<bucket>/<prefix>` in `eu-central-1`. Bucket and credentials come from `.env` (`LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY`, bucket and path variables). Add them to `.env.example` with placeholder values only.
- Follow Litestream's "tips and caveats" for the app's PRAGMAs (WAL is already on, `busy_timeout` via `timeout=30`). If a PRAGMA change is needed, explain it in the PR.
- If the pinned Litestream version supports client-side encryption of replicas, enable it and say so; if not, rely on S3 server-side encryption and say so.
- `deploy/lightsail/scripts/restore_test.sh`: restores the latest replica to a temp file, runs `PRAGMA integrity_check`, prints row counts of the main tables, compares them with the live database, deletes the temp file. Exit code non-zero on mismatch.
- Keep the nightly age-encrypted backup unchanged (second independent copy).
- Docs: a short runbook in `deploy/lightsail/README` (or the existing ops doc): how to restore after losing the VM.

Manual steps for the owner (list them in the PR):

1. Create a private S3 bucket in `eu-central-1`: Block Public Access on, default encryption on, versioning on, lifecycle rule to expire non-current versions after 30 days.
2. Create an IAM user with only `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` on that bucket and prefix. Put its keys in the server `.env`.
3. Deploy, then run `restore_test.sh` once and once per quarter.

Tests: none in the app suite. The PR includes the output of a local run against MinIO or a test bucket, if possible.

Effort: S.

---

## WP06: Scheduler in its own process, 2 web workers. HIGH RISK

Background: review 6.2, 7.2.1. Today: one uvicorn worker (`Dockerfile` CMD `--workers 1`), APScheduler started in the FastAPI lifespan (`main.py`, `scheduler.start()`), guarded by an `fcntl` lock on `DATA_DIR/scheduler.lock`.

Owner manual step FIRST: move the server from the 1 GB Lightsail bundle to the 2 GB bundle (snapshot, create a new instance from it with the larger bundle in Frankfurt, move the static IP, check, delete the old instance). The current `mem_limit: 768m` is too tight for three processes.

Changes:

- New env var `UBYHOST_ROLE` with values `web` (default) and `worker`.
  - `web`: the lifespan does not start the scheduler.
  - `worker`: a small entry point (for example `python -m app.worker`) that runs `init_db`-safe startup checks, takes the existing scheduler lock, starts the scheduler, and blocks until SIGTERM. No HTTP server, or only a tiny health endpoint if the compose health check needs one.
- `docker-compose.yml`: a second service `worker` from the same image with `UBYHOST_ROLE=worker`, same `/data` volume and env file. Set `mem_limit` for web and worker so the total fits 2 GB with Caddy and Litestream.
- `Dockerfile`: `--workers 2`. Update the comment that explains one worker.
- Before raising workers, audit module-level mutable state that would break with 2 processes (in-memory counters or caches, for example in `turnstile.py`). List what you found in the PR. Rate limits are already in the database (`rate_limit.py`).
- Database migrations (`init_db`) must be safe when two web workers and the worker start at the same time. If they are not, run them only in one place (for example the worker or the entrypoint before uvicorn starts) and explain.
- Immediate-mode sending during a guest save stays in the web process; the claim already prevents double sends across processes. Do not change it.
- Job-failure alerts and the submit heartbeat must still work from the worker.

Tests:

- with `UBYHOST_ROLE=web` the lifespan does not start the scheduler;
- the worker entry point starts the scheduler and refuses to start a second one while the lock is held;
- existing scheduler tests pass.

PR description: the exact compose diff and the deploy order (deploy worker and web together; check logs show exactly one scheduler).

Effort: S to M.

---

## WP07: Job heartbeats, static caching, compression

Background: review 6.4, 6.8, 7.3.1 items 5, 6, 8. Risk: low.

Changes:

- Heartbeats: `UBYHOST_HEARTBEAT_URL` exists for the submit sweep (`scheduler.py` `_heartbeat`). Add optional `UBYHOST_HEARTBEAT_ICAL_URL` and `UBYHOST_HEARTBEAT_MAIL_URL`, pinged after a successful iCal sync and mail run. Same timeout and logging. Document all three plus `UBYHOST_BACKUP_PING_URL` in `.env.example`.
- Static files: `/static` responses get `Cache-Control: public, max-age=31536000, immutable`. First check that every static URL in templates carries a `?v=` version; list any that do not and add it. The `no-store, private` default for other responses stays.
- Caddy: `encode zstd gzip` in all three Caddyfiles.
- Guest pages: load `signature.js` only on the signature step (`guest/base.html`). Check every guest step still works in the browser e2e.

Owner manual step: create the check-ins in the cron monitor (for example healthchecks.io free tier) with the right periods (submit 10 min, iCal 60 min, mail 5 min, backup daily) and an uptime check on `/healthz` every minute.

Tests: cache header on a static file and absence on an HTML page; heartbeat functions call the URL when set and do nothing when unset.

Effort: S.

---

## WP08: Passport upload hardening

Background: review 6.6. Today (`passport_photos.py`): JPEG, PNG, WebP up to 5 MB and PDF up to 15 MB, checked by magic bytes, stored as-is, encrypted. PDFs are a real use case (a registration form with up to 11 guests), so they stay.

Changes:

- Images: decode with Pillow and re-encode before encryption (JPEG quality 90, keep resolution, apply EXIF orientation, strip all metadata). Reject files Pillow cannot decode. Set `Image.MAX_IMAGE_PIXELS` to a sane bound to avoid decompression bombs.
- PDFs: unchanged (magic bytes, size). Make sure every download response for an attachment sends `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`, so a PDF or image is never rendered inline from the app's origin. If the host UI shows an inline preview today, keep it only for re-encoded images.
- Keep the stored file extension consistent with the re-encoded type.

Tests: EXIF (GPS) is removed; orientation is applied; a truncated image is rejected; a pixel bomb is rejected; PDF still accepted; download headers present.

Effort: S.

---

## WP09: Umami on public pages only

Background: review 5, owner decision section 12.3: Umami Cloud free Hobby plan, EU servers. Replaces the Plausible plan in the review.

Changes:

- `config.py`: `UMAMI_WEBSITE_ID` and `UMAMI_SCRIPT_URL`, both empty by default. Set only in production `.env`.
- The script tag (`defer`, with `data-website-id`, and `data-domains` set to the production domain) is rendered only in `templates/public_legal_base.html` and `templates/landing.html`, and only when both values are set. Use the exact snippet from the Umami website settings.
- Events with Umami's `data-umami-event` attributes, no extra JS: `contact_click` on `mailto:` links, `login_click` on landing CTAs to `/login`. No properties that could contain personal data.
- `main.py`: a CSP variant for those public pages that adds the Umami origin to `script-src` and `connect-src`. Host, guest and auth pages keep the current CSP.
- `cookie_inventory.py`, `/privacy`, `/subprocessors`: add Umami (processor for marketing pages only, no cookies, EU). State that app and guest pages are not measured. Wording for the owner's lawyer to review.
- Guard test: render every template; fail if the Umami host or `data-website-id` appears in any template other than the two above, or in any response under `/l/`, `/login`, `/reservations`, `/admin`.

Owner manual steps: create the Umami Cloud account in the EU region, add the site, copy the ID into `.env`, accept Umami's DPA. Lawyer check that cookieless analytics without a banner is fine in Czechia (review 5.6).

Effort: S.
