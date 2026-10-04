# After go-live, before 100 hosts: WP10 to WP20

> Status: this is the original specification. The code is in `series/` and the per-WP notes in `notes/` record every deviation. Where they differ, `series/` and `notes/` win.

Do them in this order: Step 0, WP10, WP13, WP14, WP15, WP17, WP11, WP12, WP16, WP18, WP19, WP20. WP14, WP16, WP19 and WP20 are HIGH RISK.

---

## Step 0 (owner, with a small Cursor PR): staging server

- Owner: a second Lightsail instance, 1 GB bundle, Frankfurt, its own domain (for example `staging.` subdomain), its own `.env` with `UBYHOST_UBYPORT_ENV=mock`, its own S3 prefix for Litestream, no real guest data ever.
- Cursor: make the deploy workflow in `.github/workflows/` deployable to a second target (environment `staging`, separate secrets), deployed from any branch on manual trigger. Production deploy stays as today.
- From then on, every HIGH RISK WP is deployed to staging and clicked through before merge.

---

## WP10: Admin Operations page

Background: review 4.2. Read-only. No guest names or identity anywhere on the page.

Route `/admin/operations` (admin only, same guard as other admin routes). Sections, each a count plus a list of at most 50 rows with links:

- filings needing attention across all workspaces: submissions in `error`, `rejected`, `outcome_unknown` (and the retried state from PR 230), with workspace, property `internal_name`, stay id, state, age;
- iCal feeds with `last_status` not ok, or no successful sync for more than 3 hours;
- scheduler jobs: last success per job and whether it is older than twice the interval. This is not stored today (`scheduler._job_ok` only resolves the `job_failed:<id>` alert). Add `db.set_setting(f"job_last_ok:{job_id}", <UTC ISO time>)` in `_job_ok`; open `job_failed:*` alerts are shown too;
- mail outbox: failed and stuck messages (kind, age, attempts), no recipient addresses;
- open host alerts by kind.

Use aggregate SQL; no decryption; `LIMIT` everywhere. One page view = a handful of indexed queries.

Tests: admin can open it, host gets 403/redirect; it never contains a guest surname or document number from the seed (assert on rendered HTML).

Effort: M.

---

## WP13: Per-request query, DB-time and lock-time logging

Background: review 7.3.4. Turns the estimates in the review into measured numbers.

- `db.py`: a contextvar counter per request: number of queries, total time in the database, time waiting to acquire `BEGIN IMMEDIATE`.
- `main.py` `_log_access`: append `q=`, `db_ms=`, `lock_ms=` to the existing PII-free line.
- Scheduler jobs log run time and items processed (feeds, changed feeds, batches, mails).
- `App/tools/perf_report.py`: reads the last 7 days of logs (from a file path or stdin) and prints p50 and p99 per route group (host, guest, public, admin), queries per request, lock wait p99, error rate, and iCal changed ratio. Route groups by path prefix; never print full paths with tokens.

Tests: counter resets per request; the access line contains the new fields; no token or guest data in the line.

Effort: S.

---

## WP14: One database connection per thread, and remove N+1 queries. HIGH RISK

Background: review 7.3.1 items 1 to 3. Measured: a new connection plus 3 PRAGMAs per query (`db.connect()`), dashboard 73 queries and stays list 67 for 18 stays.

Part A, connection reuse:

- Reuse one connection per thread (thread-local), opened once with the PRAGMAs. FastAPI runs sync endpoints and dependencies in a thread pool, possibly in different threads, so do not bind a connection to the request; bind it to the thread.
- Read how `db.connect()` sets `isolation_level` and how `db.immediate()` commits and rolls back. Keep exactly the same transaction semantics. After every helper call and every `immediate()` block, no transaction may be left open; add a check (`conn.in_transaction` is False) in debug and tests.
- On error inside `immediate()`, roll back and keep the connection usable.
- Scheduler and worker threads use the same mechanism.
- Close connections on shutdown.

Part B, N+1:

- `reporting.dashboard_rows` and the stays list: load guests for all listed stays in one `IN (...)` query (chunked under SQLite's variable limit) and compute progress from it.
- Stay fees list: one pass over guests per period, decrypt each guest once.

Acceptance: query count per page from the WP13 log, before and after, in the PR description (target: dashboard and stays list under 20 queries for the demo seed). Output of every changed page identical for the demo seed (snapshot test of the rendered HTML, ignoring CSRF tokens).

Tests: the full suite; a concurrency test with several threads doing writes and `immediate()` blocks at once (no "database is locked", no lost update in invoice numbering and in `claim_sendable`).

Effort: M.

---

## WP15: Skip unchanged iCal feeds

Background: review 7.1.

- Store per feed: `etag`, `last_modified`, `body_sha256`, `last_checked_at` (schema change through the existing migration path).
- Send `If-None-Match` / `If-Modified-Since` when known. On 304, or when the body hash is unchanged, skip parsing and write only `last_checked_at`.
- `last_sync_at` keeps its meaning (last successful sync that read the calendar). Make sure the Operations page and alerts use the right field.
- "Sync now" always fetches, and still uses conditional headers.
- Log per run: feeds, 304s, unchanged, changed.

Tests: 304 path, unchanged-hash path, changed path writes reservations as today; a feed that returns errors still raises the existing alert.

Effort: S.

---

## WP17: Copy cleanup on guest and host pages (review 3.E)

Background: review 3.E has two tables: 17 guest items and 16 host items, each with an action (cut, shorten, keep one). Apply them exactly, EN and CS.

- Keep everything marked Keep, the GDPR Art. 13 notice and the legal notice acknowledgement untouched.
- Replace the celebration modal (`base.html`) with a small non-blocking notice, or delete it.
- Delete unused keys (`legal_notice_disclaimer`, `dashboard.reporting_modes_body`, `dashboard.minutes_saved`) after checking they are unused.
- Two rules to add to `AGENTS.md`: one explanation lives in one place (link to the guide instead of repeating it); no sentence that the button label already says.
- Expect 10 to 20 tests asserting exact strings to need updates. Update them to the new text; do not loosen them.

PR description: a before/after table of every changed string, so the owner can review the Czech text.

Effort: M (about 1.5 days).

---

## WP11: Admin funnel page and CSV export

Background: review 5.2. Every stage is read from existing rows. No new tracking.

Route `/admin/funnel`. One row per host account: created, first login, legal accepted, first legal entity, first property, first calendar connected (status ok), first guest completed, first filing, filings in each of the last 2 months, last login, last filing, stage reached and its date. Stage counts at the top. CSV export of the same table (host account e-mail and name are fine here; no guest data).

When WP20 exists, add "signed up" and "e-mail verified" before "created", and the sign-up source (UTM or Google Ads click present, yes/no).

Tests: stages computed correctly for a seeded host at each stage; host cannot access; CSV has the same rows.

Effort: M.

---

## WP12: Three lifecycle e-mails

Background: review 5.5. Lawyer must confirm the legal basis and opt-out wording first (Czech Act 480/2004). Do not enable in production before that; ship behind `UBYHOST_LIFECYCLE_MAIL=0` by default.

Through the existing outbox (`mail.py`), checked once a day by the existing mail job, each sent at most once per account:

- no property 3 days after the first login;
- no calendar 3 days after the first property;
- no completed guest 14 days after the first calendar connected.

New kinds in `mail.KINDS` and `HOST_KINDS`, EN and CS, unsubscribe link that sets a per-account flag, a "sent" marker so nothing is sent twice.

Tests: each trigger fires once; does not fire after the condition is met; respects the flag and the env switch.

Effort: M.

---

## WP16: Separate data-encryption key and more encrypted fields. HIGH RISK

Background: review 6.5. Today the Fernet key is SHA-256 of the session secret (`db.py`, around 989-1031), so rotating the session secret makes every encrypted field unreadable.

- New `UBYHOST_DATA_KEYS`: comma-separated Fernet keys, first is used for encryption, all are tried for decryption (MultiFernet). Keep the old derived key as the last decryption key until migration is complete.
- Migration tool `App/tools/reencrypt.py`: re-encrypts every encrypted column and the passport photo files with the current key, in batches, idempotent, resumable, with a dry run and a count per table. It refuses to run without a fresh backup file path given as an argument.
- Newly encrypted columns: guest birth date, guest address, UbyPort request XML. Before encrypting birth date: list every SQL statement that filters or sorts by it (age and 18th-birthday logic for stay fees). If any exist, stop and report; the logic must move to Python first.
- Guest names and nationality stay plain (search and lists).
- Runbook in the PR: backup, deploy, run dry run, run, verify counts, remove the old key on a later deploy.

Tests: old data readable after adding a new key; re-encryption leaves values equal; rotating the session secret no longer affects encrypted data; birth date, address and XML stored encrypted; stay-fee age calculation unchanged.

Effort: M.

---

## WP18: Prepare a later Postgres move

Background: review 7.2.6. Do not add Postgres. Make the later move mechanical.

- `db.insert` uses `RETURNING id` instead of `lastrowid` (3 sites).
- `INSERT OR IGNORE` and `INSERT OR REPLACE` become `INSERT ... ON CONFLICT ...` (both engines accept it). Check each `OR REPLACE` carefully: it deletes and re-inserts, which fires cascades; `ON CONFLICT DO UPDATE` does not. Keep the current behaviour where it matters and say where.
- A null-safe comparison helper for the 67 `x IS ?` sites where the value can be NULL; plain `=` where it never is.
- Numbered SQL migration files, applied in order, with a `schema_migrations` table, replacing new `PRAGMA table_info` checks. Existing databases are detected and marked as at the current version. Keep `init_db` working for tests.
- Add the rules from `00_README_for_cursor.md` rule 8 to `AGENTS.md`.

Tests: the full suite; a migration test from an empty database and from a copy of the current schema.

Effort: M.

---

## WP19: Readable guest links. HIGH RISK

Background: review 8. Owner decision: `/l/{slug}-{code}`, for example `/l/vinohrady-studio-k7m2qx`. The PIN stays.

- Table `apartment_slug` as in review 8.3. Generate a slug for every existing property in the migration.
- Slug from `internal_name`: accents folded, lower case, `a-z0-9-`, at most 40 characters cut at a word boundary, plus `-` and 6 characters from the existing token alphabet. Reserved words (every existing sub-route segment such as `pin`, `claim`, `party`) are never a slug.
- Host can edit the readable part in property settings; the code never changes. Old slugs redirect (301) to the current one forever. The old `/l/{token}` keeps working forever.
- One resolver in `routes/guest.py` for `/l/{key}` and every sub-route.
- PIN continuity: today `pin_fingerprint` HMACs the token (`auth.py`), the PIN cookie stores the token, and the lockout key uses the token (`routes/guest.py`). Key all three by the apartment's permanent token resolved from the slug, so switching between old and new URL never asks for the PIN again and never resets the lockout.
- Copy-link places (Guest links page, stay page, guest message template) use the slug form.

Tests: old token URL, current slug, old slug redirect, wrong code 404; PIN entered on one URL is valid on the other; lockout counts across both; reserved words rejected; Czech names folded correctly; guest browser e2e at 320, 360, 390 px.

Effort: M (2 to 3 days).

---

## WP20: Self sign-up page with Google Ads conversion import. HIGH RISK

Background: owner decisions 12.4. Today accounts are created only by an admin (`POST /admin/users`). Lawyer must confirm the privacy-notice wording and the legal basis for storing the Google click ID before this is enabled in production; ship behind `UBYHOST_SIGNUP_ENABLED=0`.

Owner decisions needed before coding (ask, do not guess): auto-activate after e-mail verification, or admin approval first (recommended default: auto-activate, admin is notified and can disable). Any limit on free use before the host is invoiced.

Sign-up:

- `/signup`, public layout: e-mail, password (same policy as today), workspace or company name, acceptance of terms and DPA (reuse `legal_acceptance`), Turnstile, rate limit by IP and e-mail.
- E-mail verification link through the outbox (new mail kind), valid 24 h. Unverified accounts cannot sign in and are deleted after 7 days.
- First sign-in goes through the existing mandatory TOTP setup and onboarding.
- Admin gets an e-mail on each new verified sign-up.
- No information leak: the same response whether the e-mail exists or not.

Google Ads click ID, no cookie, no Google script:

- Landing, pricing and sign-up routes read `gclid` from the query string, validate it (`[A-Za-z0-9_-]{1,200}`), and carry it server-side in the links to `/signup` and as a hidden form field. Nothing is stored in the browser.
- Store it on the account (`signup_gclid`, `signup_at`). Also store `utm_source`, `utm_medium`, `utm_campaign` the same way.
- Admin export `/admin/ads-conversions.csv`: one row per verified sign-up with a click ID, in the column format Google Ads expects for offline click conversion imports (Google Click ID, Conversion Name, Conversion Time with time zone). The owner uploads it in Google Ads by hand, or sets it as a scheduled upload later. No Google Ads API dependency in this WP.
- Delete the click ID 90 days after sign-up [ASSUMPTION: check Google's current import window and use it].
- Umami: `signup_start` and `signup_submitted` events on the sign-up page, no properties.
- Privacy page and cookie inventory: describe the click ID storage (draft for the lawyer).

Tests: sign-up, verification, expiry of unverified accounts, duplicate e-mail behaviour, rate limit, `gclid` carried and stored, invalid `gclid` dropped, CSV format, deletion after the window, nothing set in cookies except the existing session and CSRF cookies.

Effort: L (3 to 5 days).
