# UbyHost — GDPR / ePrivacy remediation plan (for Cursor)

Companion to `docs/GDPR_COMPLIANCE_REVIEW_2026-09-27.md`. The review says what
is missing and why; this plan says what to build, where, in what order, and how
to know each item is finished. It is written to be handed to a Cursor agent with
repo access, in the same style as `CURSOR_REMEDIATION_PLAN.md`.

Gap IDs in brackets — e.g. `[A-6]`, `[B-1]` — refer to the review's Phase 2
tables. Backlog IDs: `OPS-*` / `BE-*` (App Backend), `FE-*` (App Frontend),
`MK-*` (Marketing Site), `LD-*` (Legal Docs & Policies).

**Where to put these files:** copy this file to the repo root as
`GDPR_REMEDIATION_PLAN.md` and the review to
`docs/GDPR_COMPLIANCE_REVIEW_2026-09-27.md`.

---

## Rules for the executing agent

Read these before touching anything. They extend — not replace — the rules in
`CURSOR_REMEDIATION_PLAN.md`.

1. **Read `AGENTS.md`, `docs/DESIGN.md`, `docs/SECURITY.md` and
   `docs/OPERATIONS.md` first.** Light mode only. Run tests from `App/` with
   `.venv/bin/python -m pytest tests -q`. Never set `PYTHONPATH=App`.
2. **One work item per branch, one branch per PR** unless an item says it may be
   grouped. Branch names are given per item.
3. **Every work item ships with its test.** No test that would have failed on the
   old behaviour = not finished.
4. **EN/CS parity.** Every new string goes into both languages in the same
   commit: host copy in `App/app/host_i18n.py`, guest copy in `App/app/i18n.py`,
   public legal copy in `privacy_policy_i18n.py` / `dpa_i18n.py` /
   `terms_i18n.py` / `subprocessors_i18n.py`.
5. **Schema changes are append-only.** New tables: append a
   `CREATE TABLE IF NOT EXISTS` block to the `SCHEMA` literal in
   `App/app/db.py`. New columns: add to the table's `CREATE TABLE` in `SCHEMA`
   **and** append a tuple at the end of `ADDED_COLUMNS` (`db.py:482`). `NOT NULL`
   needs a `DEFAULT`. No renames, no drops, no reordering.
6. **Legal wording is gated.** Where an item says **LEGAL-GATED COPY**, implement
   the mechanism and put the wording in the i18n catalog exactly as given here,
   marked with a `# LEGAL-REVIEW` comment on the line above the key. Do **not**
   invent statements of law, statute citations, retention periods, or promises.
   Anything not given verbatim here is a `TODO(counsel)` placeholder string that
   a test asserts is not shown in production (`config.DEPLOYMENT == "production"`
   renders the previous approved text instead).
7. **Destructive jobs ship disabled.** Every new deletion path runs in dry-run
   mode unless its env flag is set (see BE-2). Dry-run must compute exactly the
   same row set it would delete, audit the counts, and delete nothing.
8. **Never log personal data.** New log lines carry ids and counts only — no
   names, e-mails, document numbers, IPs, tokens, or raw URLs.
9. **Stop and ask before implementing anything in "Decisions needed".** Use the
   recommended default *only* if the owner has written "use defaults" in the PR.
10. **Out-of-scope findings go to `FOLLOWUPS.md`** under a new heading
    `## From the GDPR plan`.

---

## Decisions needed from the owner before coding starts

| # | Question | Blocks | Recommended default (owner must confirm) |
|---|---|---|---|
| G-D1 | Backup encryption key custody: who holds the `age` private identity and where? | OPS-1 | One `age` identity generated offline; public recipient in `.env` as `UBYHOST_BACKUP_AGE_RECIPIENT`; private identity in the owner's password manager + one offline copy. Never on the server. |
| G-D2 | Off-site backup target | OPS-2 | AWS S3 bucket in `eu-central-1`, lifecycle expiry = backup retention. Retire Google Drive unless it is a Google Workspace account with the Cloud Data Processing Addendum accepted. |
| G-D3 | Backup retention window (local and off-site) | OPS-1/2, LD-3 | 35 days local, 35 days off-site. Counsel to confirm (deleted records survive in backups until expiry). |
| G-D4 | Retention anchor for guest records | BE-2 | Keep current per-guest anchor (stay end + 6 years) — **counsel must confirm** vs "6 years from last house-book entry". Job ships in dry-run until confirmed. |
| G-D5 | Retention of claim e-mail / `reservation.guest_email` / `phone_last4` after the stay | BE-3 | Null them 30 days after `date_to` once the stay is complete or past. |
| G-D6 | Retention of `guest.filled_ip` | BE-3 | Null 90 days after the guest's stay end (evidence window for disputes), counsel to confirm. |
| G-D7 | Audit / security-log retention | BE-4 | `audit`: 3 years. `rate_limit_event`: 24 h. Resolved `alert`: 12 months. `legal_acceptance`: life of account + 3 years. |
| G-D8 | Clickwrap acceptance for Terms/DPA/Privacy | BE-1, FE-1 | Yes: explicit checkbox + button on first login and whenever any version changes. |
| G-D9 | Missing controller identity: block the guest form, or only warn? | BE-7 | Block *new* claims/forms with a guest-safe "not available yet" page; keep already-started forms working; raise a critical host alert. |
| G-D10 | Log sensitive **reads** of which kinds | BE-6 | Passport image views and every export/download. Not ordinary page views. |
| G-D11 | Workspace termination: return format and deletion timing | BE-10 | ZIP (house-book CSV + per-guest PDFs + receipts) on request; deletion 30 days after account termination, after the host confirms they have their six-year copy. **Counsel.** |

---

## Sequencing (what is legally urgent vs lower risk)

| Order | Item | Area | Priority | Why this order |
|---|---|---|---|---|
| 1 | OPS-1 Encrypt backups, separate key, time-based retention | Backend/infra | **P0** | Off-site copies currently hold plaintext DB **and** the decryption key; register claims they are encrypted. Highest breach exposure. |
| 2 | OPS-2 Off-site target with a DPA; purge old plaintext copies | Backend/infra | **P0** | Personal-account Drive has no processor DPA. |
| 3 | LD-4 Correct the subprocessor register | Legal docs | **P0** | Published statement is currently false. Ship the same day as OPS-1/2. |
| 4 | BE-1 + FE-1 Acceptance evidence + clickwrap | Backend + Frontend | **P0** | Production (2FA path) records no acceptance at all. |
| 5 | OPS-3 Access-log minimisation + rotation | Backend/infra | **P1** | Unbounded logs with guest tokens. |
| 6 | BE-11 Run the doc-number backfill on deploy | Backend | **P1** | Plaintext doc numbers may still sit in production rows. |
| 7 | BE-2 Scheduled retention job (dry-run first) | Backend | **P1** | Storage limitation depends on a human pressing a button. |
| 8 | BE-3 Reservation / claim e-mail / IP minimisation | Backend | **P1** | Data kept with no end date. |
| 9 | BE-4 Audit, rate-limit, alert retention | Backend | **P1** | Same. |
| 10 | BE-5 + FE-2 Persist guest notice acknowledgement | Backend + Frontend | **P1** | Accountability (Art 5(2)). |
| 11 | BE-6 Audit sensitive reads + real actor | Backend | **P1** | Needed for breach investigation and DPA audit promises. |
| 12 | BE-7 + FE-6 Controller identity gate | Backend + Frontend | **P1** | Art 13 identity must be shown to guests. |
| 13 | BE-13 + LD-5 Incident register + runbook | Backend + Legal | **P1** | Art 33(2)/(5). |
| 14 | LD-1 RoPA, LD-2 DPIA, LD-3 retention schedule | Legal docs | **P1** | Documentation duties; inputs for counsel. |
| 15 | MK-1 No-tracking guardrail test | Marketing | **P1** | Cheap; prevents the most-fined failure mode. |
| 16 | MK-2, MK-3, FE-4 Cookie/storage inventory + Cloudflare verification | Marketing + Frontend | **P2** | Transparency; ÚOOU lists missing cookie detail as a deficiency. |
| 17 | BE-8 + FE-5 DSR register + per-guest export | Backend + Frontend | **P2** | Rights currently handled ad hoc. |
| 18 | BE-9 Restriction flag | Backend | **P2 / LEGAL-GATED** | Interaction with reporting duty needs counsel. |
| 19 | BE-10 Workspace export + termination deletion | Backend | **P2 / LEGAL-GATED** | Art 28(3)(g). |
| 20 | FE-3 Settings "Data protection" panel | Frontend | **P2** | Makes retention/backup status visible; fixes an INCONSISTENT copy claim. |
| 21 | BE-12 Encrypt passport files and signatures at rest | Backend | **P2** | Art 32 hardening. |
| 22 | MK-4, MK-5 Language-cookie lifetime; CMP spec if analytics added | Marketing | **P3** | Only matters if tracking is introduced. |
| 23 | LD-6..LD-10 | Legal docs | P1–P2 | See each item. |

---

# A. App Backend

## A1. Infrastructure

### OPS-1 — Encrypt backups, keep the key out of plaintext copies, retain by time `[B-1] [B-3] [B-4]` — P0

**Branch:** `fix/gdpr-encrypted-backups` · **Depends on:** G-D1, G-D3

**Files:** `Dockerfile`, `App/scripts/backup_data.sh`, `deploy/lightsail/scripts/backup.sh`,
`deploy/lightsail/scripts/restore.sh`, `deploy/lightsail/.env.example`,
`App/tests/test_backup_data.py`, `docs/OPERATIONS.md` (§ Backup and restore),
`deploy/lightsail/README.md`.

**Steps**

1. `Dockerfile`: add `age` to the existing `apt-get install -y --no-install-recommends ca-certificates sqlite3` line (Debian `python:3.12-slim` ships it in apt).
2. New env vars (document in `deploy/lightsail/.env.example` and `docs/ENVIRONMENT.md`):
   - `UBYHOST_BACKUP_AGE_RECIPIENT` — public `age1…` recipient. Required when `UBYHOST_DEPLOYMENT=production`.
   - `UBYHOST_BACKUP_RETENTION_DAYS` — default from G-D3 (35).
3. `App/scripts/backup_data.sh`:
   - Keep the `sqlite3 .backup` snapshot step.
   - Build a tarball in the snapshot dir containing `ubyhost.db` and the key (the existing `secret_key` / `UBYHOST_SECRET_KEY` logic at lines 33–45 stays, but only writes *into the tarball staging dir*).
   - If `UBYHOST_BACKUP_AGE_RECIPIENT` is set: `age -r "$UBYHOST_BACKUP_AGE_RECIPIENT" -o "$DEST/ubyhost-backup.tar.age" "$DEST/ubyhost-backup.tar"`, then remove the plaintext tar, `ubyhost.db`, `secret_key` and `initial_admin_credentials` from `$DEST`. Use `rm -f` after `umask 077` (already set); do not rely on `shred` on overlay filesystems.
   - If the recipient is **unset** and `UBYHOST_DEPLOYMENT=production`: print an error and `exit 1` (fail closed). Outside production keep today's plaintext behaviour so local dev still works, but print a warning.
   - Replace count-based pruning (`tail -n +11`, line 54) with time-based: delete snapshot dirs older than `UBYHOST_BACKUP_RETENTION_DAYS`, **always keeping the newest one**.
   - On success write `$BACKUP_ROOT/.last_success.json`:
     `{"at": "<UTC ISO>", "encrypted": true|false, "bytes": <int>, "retention_days": <int>}` (mode 0600). FE-3 reads this.
4. `deploy/lightsail/scripts/restore.sh`: accept a stamp whose dir contains `ubyhost-backup.tar.age`. Require `AGE_IDENTITY_FILE=/path/on/host` (never inside the volume); `docker cp` the encrypted file out, decrypt on the host with `age -d -i "$AGE_IDENTITY_FILE"`, copy `ubyhost.db` (and `secret_key` if present) into the volume with the existing uid 10001 ownership handling, then delete the host-side plaintext. Keep the legacy plaintext path working for old stamps.
5. `docs/OPERATIONS.md` § "Backup and restore": replace "Backups are not encrypted by the supplied scripts" with the new procedure, key custody (G-D1), retention (G-D3), and a quarterly restore-test step.

**Tests** (`App/tests/test_backup_data.py`; skip with `pytest.skip` if `age`/`age-keygen` are not on PATH):
- With a generated test keypair and `UBYHOST_DEPLOYMENT=production`: after running the script, `$DEST` contains `ubyhost-backup.tar.age` and **no** `ubyhost.db`, `secret_key` or `.tar`. Decrypting with the test identity yields a DB with the seeded row and the key.
- Production with no recipient → non-zero exit, no snapshot left behind.
- Snapshots older than retention are removed; the newest is kept even if older than retention.
- `.last_success.json` exists, mode `0600`, `encrypted` true.
- Existing `test_backup_uses_sqlite_snapshot_and_keeps_last_ten` is updated (count → days) — do not delete the sqlite-snapshot assertion.

**Done when:** no production backup on disk or off-site can be read without the offline `age` identity, and backups older than the retention window do not exist.

### OPS-2 — Off-site backup provider with a DPA, bounded retention, purge legacy copies `[B-2]` — P0

**Branch:** `fix/gdpr-offsite-backups` · **Depends on:** OPS-1, G-D2, G-D3

**Files:** `deploy/lightsail/scripts/backup-s3.sh`, `deploy/lightsail/scripts/backup-gdrive.sh`,
`deploy/lightsail/scripts/setup-server.sh` (cron lines 73–76), `deploy/lightsail/README.md`, `docs/OPERATIONS.md`.

**Steps**
1. `backup-s3.sh`: copy only `*.age` files (`rclone copy --include "*.age" …`). Refuse to run (exit 1) if the newest snapshot has no `.age` file.
2. Document in `deploy/lightsail/README.md` the one-time bucket setup: region `eu-central-1`; Block Public Access on; default encryption SSE-S3; **lifecycle rule expiring objects after `UBYHOST_BACKUP_RETENTION_DAYS`**; an IAM user limited to `s3:PutObject`, `s3:ListBucket`, `s3:GetObject` on that bucket only.
3. `backup-gdrive.sh`: if G-D2 retires Drive, replace the body with an error message pointing to `backup-s3.sh` and exit 1; remove its cron line from `setup-server.sh`. If G-D2 keeps Drive (Workspace only), restrict to `*.age` and add `rclone delete --min-age "${UBYHOST_BACKUP_RETENTION_DAYS}d" "${REMOTE}:${DRIVE_DIR}"` after the copy.
4. **Operator runbook step (manual, do not automate):** add to `docs/OPERATIONS.md` a checklist to find and delete every pre-OPS-1 plaintext snapshot already on Google Drive / S3 / laptops, and to record the date done in `docs/vendors/README.md` (LD-9).

**Tests:** shell-level test in `App/tests/test_backup_data.py` (or a new `test_backup_offsite.py`) that runs `backup-s3.sh` with a fake `rclone` on PATH and asserts it is invoked with `--include "*.age"` and refuses when no `.age` exists.

**Done when:** the only off-site copies are encrypted, in an EU region, under a provider DPA, and expire automatically.

### OPS-3 — Access-log minimisation and log rotation `[B-5]` — P1

**Branch:** `fix/gdpr-access-logs`

**Files:** `Dockerfile` (CMD line 34), `App/app/main.py` (middleware `cloudflare_connecting_ip`, lines 136–159), `App/app/config.py`, `deploy/lightsail/docker-compose.yml`, `docs/OPERATIONS.md`, `App/app/privacy_policy_i18n.py` (§8, LEGAL-GATED COPY).

**Steps**
1. `Dockerfile` CMD: add `"--no-access-log"` to the uvicorn args. (Render/local `run.sh` may keep the default.)
2. `config.py`: `ACCESS_LOG = os.environ.get("UBYHOST_ACCESS_LOG", "1") not in ("0","false","no")`.
3. `main.py`: add a logger `log_access = logging.getLogger("ubyhost.access")`. In the existing `cloudflare_connecting_ip` middleware, time the call and, when `config.ACCESS_LOG`, log **one** line after `call_next`:
   `method=%s route=%s status=%s ms=%d` where `route` is `request.scope.get("route").path` if a route matched (FastAPI puts the template, e.g. `/l/{token}/{reservation_id}`), else the literal `"<unmatched>"`. **Never** log `request.url`, query string, client IP, user agent or headers. Skip `/static/*` and `/healthz`.
4. `docker-compose.yml`: add to **both** services:
   ```yaml
   logging:
     driver: json-file
     options:
       max-size: "10m"
       max-file: "5"
   ```
   Keep Caddy without a `log` directive (it currently has none — add a comment in `Caddyfile.cloudflare` / `Caddyfile.acme` saying access logging is intentionally off).
5. `docs/OPERATIONS.md`: new § "Logs" — what is logged, rotation (≈50 MB per service), that rotated logs are gone for good, and how to capture logs during an incident.

**Tests:** new `App/tests/test_access_log.py` using `caplog` and `TestClient`:
- `GET /l/<real-looking-token>` logs `route=/l/{token}` and the token string does **not** appear in any captured record.
- `GET /?lang=cs&email=x@y.z` — no `x@y.z` and no `lang=` in logs.
- `UBYHOST_ACCESS_LOG=0` → no `ubyhost.access` records.

**Done when:** no log line anywhere contains a guest token, query string, or IP, and container logs are bounded.

## A2. Application

### BE-1 — Record Terms/DPA/Privacy acceptance per version, on every login path `[A-6] [A-7]` — P0

**Branch:** `feat/gdpr-acceptance-evidence` · **Depends on:** G-D8 · **Pairs with:** FE-1 (may share one PR)

**Files:** `App/app/db.py`, NEW `App/app/acceptance.py`, `App/app/auth.py` (`require_login`, line 288),
`App/app/routes/admin_accounts.py` (login `:106-114`, 2FA `:168`), `App/app/config.py` (versions at `:169`, `:180`, `:183`).

**Schema** (append to `SCHEMA` in `db.py`):
```sql
CREATE TABLE IF NOT EXISTS legal_acceptance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id INTEGER NOT NULL REFERENCES user_account(id),
    document        TEXT NOT NULL CHECK (document IN ('terms','privacy','dpa')),
    version         TEXT NOT NULL,
    accepted_at     TEXT NOT NULL,
    method          TEXT NOT NULL CHECK (method IN ('clickwrap','login_notice','backfill')),
    ip              TEXT,
    user_agent      TEXT,
    UNIQUE (user_account_id, document, version)
);
CREATE INDEX IF NOT EXISTS idx_acceptance_user ON legal_acceptance (user_account_id, document);
```

**`acceptance.py` API**
- `CURRENT = {"terms": config.TERMS_VERSION, "privacy": config.PRIVACY_VERSION, "dpa": config.DPA_VERSION}`
- `pending(user_id) -> list[str]` — documents whose current version has no row for this user.
- `record(user_id, docs, method, request)` — `INSERT OR IGNORE` one row per doc; `ip` from `request.client.host` (already the visitor IP via `client_ip.apply_visitor_client`), `user_agent` truncated to 300 chars; one `db.audit("legal_accepted", "terms_v… privacy_v… dpa_v… method=…", actor=username, owner_user_id=user_id)`.
- `backfill_from_audit()` — one-shot: parse existing `audit` rows `action='login'` with detail `terms_vX privacy_vY dpa_vZ accepted` into rows with `method='backfill'`, `accepted_at = audit.at`. Call from a new script `App/scripts/backfill_legal_acceptance.py` (idempotent via the UNIQUE constraint), and run it from `deploy/lightsail/scripts/deploy.sh` after the health check.

**Flow**
1. In `auth.require_login`, after the TOTP redirect block and before `workspace_user`: if `acceptance.pending(account["id"])` is non-empty and the path is not in (`/account/accept`, `/account/password`, `/account/2fa/setup`, `/logout`, `/terms`, `/privacy`, `/dpa`, `/legal`, `/subprocessors`), redirect 303 to `/account/accept?next=<safe local path>` (use `security.safe_local_path`). **Do not** redirect while an admin is impersonating — acceptance is for the real account (`current_user`), never the workspace target.
2. Remove the free-text `terms_v… accepted` detail from the `login` audit in `admin_accounts.py:106-114` (acceptance is now its own event) and leave `two_factor_login` as is.
3. Routes `GET/POST /account/accept` live in `routes/admin_accounts.py` (FE-1 renders the page). POST requires the checkbox `accept=1`; otherwise re-render with an error. On success `acceptance.record(..., method="clickwrap")` and redirect to `next`.

**Tests:** new `App/tests/test_legal_acceptance.py`
- Fresh account, non-2FA login → redirected to `/account/accept`; after POST, three rows exist with `method='clickwrap'` and the config versions.
- **2FA login path** → same redirect after `/login/2fa`; rows recorded (this is the production regression).
- Bumping `config.TERMS_VERSION` via monkeypatch → next request redirects again; only `terms` is pending.
- POST without the checkbox → 422/200 with error, no rows.
- Impersonating admin is not redirected on behalf of the target.
- Backfill script: seeded legacy `audit` login rows produce `backfill` rows; second run inserts nothing.
- Update `tests/test_login_acceptance.py` only if the login-page line changes (it should not).

**Done when:** for any host and any document version, the DB can show when, how and from where it was accepted — including production 2FA logins.

### BE-2 — Scheduled retention job, dry-run by default `[A-10] [A-11]` — P1

**Branch:** `feat/gdpr-retention-job` · **Depends on:** G-D4 (to leave dry-run), G-D7

**Files:** NEW `App/app/retention.py`, `App/app/scheduler.py`, `App/app/config.py`, `App/app/housebook.py`
(`expired_guest_ids` `:417`, `purge_expired` `:467`), `App/app/invoices.py` (`purge_expired` `:438`),
`App/app/routes/exports.py` (`purge_expired_records` `:357`), `App/app/alerts.py`, `App/app/host_i18n.py`.

**Steps**
1. `config.py`:
   - `RETENTION_AUTOPURGE = os.environ.get("UBYHOST_RETENTION_AUTOPURGE", "0") in ("1","true","yes")`
   - `RETENTION_NOTICE_DAYS = int(os.environ.get("UBYHOST_RETENTION_NOTICE_DAYS", "30"))`
2. `housebook.expired_guest_ids`: change the predicate to `COALESCE(date(g.stay_to), date(r.date_to)) < ?` — matching `passport_photos.purge_stale` — so a malformed `stay_to` cannot sort after every cutoff and live forever. Add `due_guest_ids(within_days)` returning ids whose cutoff falls in the next N days.
3. `retention.py`:
   ```python
   def run(today: date | None = None, *, dry_run: bool | None = None) -> dict:
       """Everything the retention schedule says may no longer be held."""
   ```
   - `dry_run` defaults to `not config.RETENTION_AUTOPURGE`.
   - Steps, each returning a count and each wrapped so one failure doesn't stop the rest (re-raise at the end so the scheduler marks the job failed):
     a. guest records → `housebook.purge_expired(today)` (global, `owner_user_id=None`), or in dry-run `len(housebook.expired_guest_ids(today))`.
     b. invoices → `invoices.purge_expired(today)` (10-year rule already there).
     c. BE-3 and BE-4 steps once those land.
   - Per workspace, when `housebook.due_guest_ids(RETENTION_NOTICE_DAYS)` is non-empty, `alerts.raise_alert("warning", "retention_due", …, dedupe_key=f"retention_due:{owner}:{YYYY-MM}", owner_user_id=owner)` with host_i18n strings telling the host how many records reach the end of their retention period and linking to `/housebook` exports.
   - Always `db.audit("retention_run", json.dumps({"dry_run": …, "counts": {...}}), actor="system", owner_user_id=None)`.
   - Store `db.set_setting("retention_last_run", <json>)` for FE-3.
4. `scheduler.py`: add `_job_retention()` following the `_job_photo_sweep` pattern; register
   `_scheduler.add_job(_job_retention, "cron", hour=3, minute=30, id="retention", max_instances=1, coalesce=True)`;
   add `"retention": "warning"` to `_JOB_LEVELS`; add `notification.job_name.retention` to `host_i18n.py` EN ("data retention") / CS ("uchovávání údajů").
5. `routes/exports.py:purge_expired_records` stays as the manual path but calls `retention.run(dry_run=False)` scoped to the owner (add an `owner_user_id` parameter to `run`), so the button and the job share one code path.

**Tests:** new `App/tests/test_retention_job.py` (plus keep `tests/test_retention.py` green)
- Dry-run: expired guests counted, **nothing deleted**, `retention_run` audit row with `dry_run: true`.
- `UBYHOST_RETENTION_AUTOPURGE=1`: expired guests + their photos deleted; non-expired untouched; other owners untouched.
- A guest with `stay_to = "garbage"` and an old `reservation.date_to` is treated as expired (the `date()` fix).
- Notice alert raised once per owner per month for records due within 30 days.
- Scheduler registers job id `retention` (construct the scheduler directly as `tests/test_scheduler.py` does).

**Done when:** retention no longer depends on anyone pressing a button, and the owner can turn deletion on with one env flag after counsel signs off G-D4.

### BE-3 — Minimise reservation data, claim e-mails and submitter IPs `[A-12] [A-13]` — P1

**Branch:** `feat/gdpr-reservation-minimisation` · **Depends on:** BE-2, G-D5, G-D6

**Files:** `App/app/retention.py`, `App/app/claim.py`, `App/app/mail.py`, `App/app/routes/guest.py`, `App/app/routes/admin.py`, tests.

**Steps** (all run inside `retention.run`, honouring dry-run):
1. **Claim e-mail:** `UPDATE reservation_claim SET email = NULL, updated_at = ? WHERE email IS NOT NULL AND reservation_id IN (SELECT id FROM reservation WHERE date(date_to) < date(?, '-<G-D5> days'))`. Keep `email_masked` (display only). Same for `reservation.guest_email` and `reservation.phone_last4`.
2. Before landing step 1, grep every read of `reservation_claim.email` / `claim["email"]` (e.g. `claim.py:238`, `:240`, `:654`) and `reservation.guest_email`, and make each tolerate `NULL` (treat as "no address on file"; never send). Add a test per call site.
3. **Submitter IP:** `UPDATE guest SET filled_ip = NULL WHERE filled_ip IS NOT NULL AND COALESCE(date(stay_to), (SELECT date(date_to) FROM reservation r WHERE r.id = guest.reservation_id)) < date(?, '-<G-D6> days')`.
4. **Empty reservations:** delete `reservation` rows whose `date(date_to)` is older than `housebook.retention_cutoff(today)` **and** have no `guest` rows. `reservation_claim` cascades (`ON DELETE CASCADE`); `email_outbox.reservation_id` and `invoice.reservation_id` are `ON DELETE SET NULL`, so invoices survive with their own buyer copy.
5. Update `docs/OPERATIONS.md` § "Retention and what is actually deleted" (remove "`guest.filled_ip` … never deleted").

**Tests:** `App/tests/test_retention_job.py` additions — each step in dry-run and live; a reminder sweep (`claim.sweep_reminders`) after the e-mail is nulled sends nothing and raises nothing.

**Done when:** no reservation, claim e-mail, phone fragment or IP outlives its purpose.

### BE-4 — Retention for audit, rate-limit and alert tables `[B-6] [B-7]` — P1

**Branch:** `feat/gdpr-log-table-retention` · **Depends on:** BE-2, G-D7

**Files:** `App/app/retention.py`, `App/app/rate_limit.py`, `App/app/config.py`, tests.

**Steps**
1. `config.py`: `AUDIT_RETENTION_DAYS` (default 1095), `ALERT_RETENTION_DAYS` (365), `RATE_LIMIT_RETENTION_HOURS` (24).
2. `retention.run`:
   - `DELETE FROM audit WHERE at < ? AND action NOT IN ('legal_accepted')` — acceptance evidence lives in `legal_acceptance`, which has its own rule (G-D7) — implement `legal_acceptance` deletion only for accounts inactive > G-D7 period.
   - `DELETE FROM alert WHERE resolved_at IS NOT NULL AND resolved_at < ?`
   - `DELETE FROM rate_limit_event WHERE at < ?` (epoch seconds; column is `REAL`).
3. `audit` rows for `login_failed` currently put the IP in `detail` (`admin_accounts.py:74`). Keep, but they now expire with the table.

**Tests:** seeded old/new rows per table; only old ones go; dry-run deletes nothing.

### BE-5 — Persist the guest's notice acknowledgement `[A-4]` — P1

**Branch:** `feat/gdpr-guest-notice-ack` · **Pairs with:** FE-2

**Files:** `App/app/db.py`, `App/app/config.py`, `App/app/routes/guest.py` (`guest_form_save`, check `:1485`, payload `:1553-1570`), `App/app/housebook.py` (registration PDF footer), tests.

**Schema** — add to the `guest` table in `SCHEMA` and append to `ADDED_COLUMNS`:
```python
("guest", "notice_version", "TEXT"),
("guest", "notice_lang", "TEXT"),
("guest", "notice_ack_at", "TEXT"),
```

**Steps**
1. `config.py`: `GUEST_NOTICE_VERSION = os.environ.get("UBYHOST_GUEST_NOTICE_VERSION", "1.0")`. Bump rule: whenever any `legal_notice_*` / `privacy_*` key in `i18n.py` changes materially.
2. In `guest_form_save`, add to `payload`: `notice_version=config.GUEST_NOTICE_VERSION`, `notice_lang=lang`, `notice_ack_at=now` (the check at `:1485` already guarantees the box was ticked).
3. Host-entered guests (`entered_by='host'`, host save path in `routes/admin.py`) leave these `NULL` — the host is responsible for informing that guest.
4. `housebook.registration_form_pdf`: add one line "Privacy notice v{version} acknowledged {date} ({lang})" when present.

**Tests:** guest save persists the three fields; missing checkbox still 422 and persists nothing; host-entered guest has `NULL`; PDF text contains the version.

### BE-6 — Audit sensitive reads and identify the real actor `[B-8] [B-9]` — P1

**Branch:** `feat/gdpr-access-audit` · **Depends on:** G-D10

**Files:** `App/app/db.py` (`audit` `:681`, context vars at top), `App/app/auth.py` (`require_login`), `App/app/routes/exports.py`, `App/app/routes/admin.py` (`guest_passport_photo` `:1837`), templates showing audit (Settings), tests.

**Schema** — append to `ADDED_COLUMNS` and the `audit` table in `SCHEMA`:
```python
("audit", "actor_user_id", "INTEGER REFERENCES user_account(id)"),
("audit", "impersonator_user_id", "INTEGER REFERENCES user_account(id)"),
```

**Steps**
1. `db.py`: add `_current_actor: ContextVar[Optional[tuple]]` (`(user_id, username, impersonator_id)`) and `set_current_actor(...)`. In `audit()`, when `actor == "host"` (the default) and a current actor is set, write the username into `actor`, and always fill `actor_user_id` / `impersonator_user_id` from the context var.
2. `auth.require_login`: after `workspace_user`, call `db.set_current_actor(user_id=account["id"], username=account["username"], impersonating=bool(workspace and workspace["id"] != account["id"]))`. Resulting audit row: `actor_user_id` = the human who is signed in (`current_user`), `impersonator_user_id` = that same id **only when** they are acting inside someone else's workspace (else `NULL`), `owner_user_id` = the workspace (unchanged behaviour).
3. Add `db.audit(...)` with ids only (never names) to each of these `routes/exports.py` handlers:
   `reservations.csv` → `export_reservations_csv`; `/guests/{id}/form.pdf` → `export_registration_pdf guest_id=…`;
   `/submissions/receipts.zip` → `export_receipts_zip`; `/submissions/{id}/receipt.pdf` / `errors.pdf` → `export_submission_pdf`;
   `/submissions/{id}/{which}.xml` → `export_submission_xml` (**high sensitivity**); `/housebook.csv` → `export_housebook_csv rows=N`;
   `/housebook/pdfs.zip` → `export_housebook_pdfs rows=N`.
   And in `routes/admin.py:guest_passport_photo` → `passport_photo_viewed guest_id=…`.
4. The Settings audit list (last 500 rows) shows actor username and "(as admin X)" when `impersonator_user_id` is set — host_i18n EN/CS.

**Tests:** new `App/tests/test_access_audit.py` — each endpoint writes exactly one row with the right action and owner; an impersonated export has `impersonator_user_id` set; no audit `detail` contains a guest name, e-mail or document number (assert against seeded values).

### BE-7 — Controller identity gate `[A-5]` — P1

**Branch:** `feat/gdpr-controller-gate` · **Depends on:** G-D9 · **Pairs with:** FE-6

**Files:** `App/app/routes/guest.py` (`_controller` `:667`, `_entity_details` `:647`, `pick_stay` `:853`, the `/claim`, `/new` and `/save` routes), `App/app/routes/admin.py` (`_readiness` `:108`), `App/app/alerts.py`, `App/app/i18n.py`, `App/app/host_i18n.py`.

**Steps**
1. `routes/guest.py`: add `_controller_complete(apartment) -> bool` = controller has non-empty `name` **and** `email` (from `_entity_details`) **and** either `ico` or `seat`. (LEGAL-GATED: counsel may add fields; keep the rule in one function.)
2. In `pick_stay`, the claim routes and `GET /l/{token}/{reservation_id}/new`: if not complete, return `_unavailable(request, lang, "controller_missing", 200, token)` and raise `alerts.raise_alert("critical", "controller_missing", …, dedupe_key=f"controller_missing:{apartment['id']}", apartment_id=apartment["id"], owner_user_id=apartment["owner_user_id"])`. Per G-D9 do **not** block `/edit/{guest_id}` or `/save` for an already-started guest.
3. Resolve that alert whenever the entity form is saved and the controller becomes complete (`routes/admin.py` entity POST handlers `:384`, `:408`).
4. `_readiness` invite list: add `{"key": "controller", "anchor": "basics", "done": <complete>}`; host_i18n key `apartment.form.readiness.item.controller` EN "Data controller name, address and e-mail" / CS "Správce údajů: název, sídlo a e-mail".
5. `i18n.py` guest string `unavailable_controller_missing` EN "This check-in form is not available yet. Please contact your host." / CS "Tento formulář zatím není dostupný. Kontaktujte prosím ubytovatele." (no mention of the reason).

**Tests:** `App/tests/test_controller_gate.py` — incomplete controller blocks pick/new/claim with 200 and the neutral page; started guest can still save; alert raised once and resolved on fix; readiness shows the item.

### BE-8 — Data-subject request register and per-guest export `[A-14] [A-16] [A-18]` — P2

**Branch:** `feat/gdpr-dsr-register` · **Pairs with:** FE-5

**Files:** `App/app/db.py`, NEW `App/app/dsr.py`, NEW `App/app/routes/privacy_requests.py` (include from `routes/admin.py` next to `router.include_router(exports.router)` at `:1268`), `App/app/routes/exports.py`, `App/app/access.py`, tests.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS data_subject_request (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id       INTEGER REFERENCES user_account(id),
    received_at         TEXT NOT NULL,
    due_at              TEXT NOT NULL,
    channel             TEXT NOT NULL CHECK (channel IN ('email','post','in_person','support','other')),
    request_type        TEXT NOT NULL CHECK (request_type IN
                          ('access','rectification','erasure','restriction','portability','objection','other')),
    subject_kind        TEXT NOT NULL CHECK (subject_kind IN ('guest','host_user','other')),
    guest_id            INTEGER REFERENCES guest(id) ON DELETE SET NULL,
    reservation_id      INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    identity_checked_at TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','extended','fulfilled','refused','withdrawn')),
    extended_until      TEXT,
    closed_at           TEXT,
    outcome_note        TEXT,
    handled_by          INTEGER REFERENCES user_account(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dsr_owner_status ON data_subject_request (owner_user_id, status, due_at);
```
Rule: `outcome_note` must not repeat the subject's data — ids only. `due_at = received_at + 1 month` (Art 12(3)); `extended` adds up to 2 months and requires a note.

**Endpoints** (host-scoped via `access.*`, CSRF via existing `security.protect_host_post`):
- `GET /privacy-requests` list (open first, overdue highlighted); `POST /privacy-requests` create; `POST /privacy-requests/{id}` update status/extension/close.
- `GET /guests/{guest_id}/export.json` — `dsr.guest_export(guest_id)`: all `guest` columns (decrypted via normal `db.query`), `signature_present: bool` (not the image), `passport_photo_present: bool`, notice fields (BE-5), the reservation's dates, submission states and receipt ids, and audit rows whose `detail` references `guest_id=<id>`. `Content-Disposition: attachment`. Audit `export_guest_dsr`.
- Existing `/guests/{id}/form.pdf` remains the human-readable copy.
- Erasure: reuse `routes/admin.py:guest_delete`; when refused for a sent guest, the flash links to "record a refused erasure request" pre-filled.
- Scheduler: extend `_job_deadlines` (or add to BE-2's run) to raise `alerts.raise_alert("warning","dsr_due",…)` for requests due within 5 days.

**Tests:** create → due date +1 month; overdue alert; export JSON contains decrypted doc number for the owner and 404 for another owner; export is audited.

### BE-9 — Restriction flag (LEGAL-GATED) `[A-17]` — P2

**Branch:** `feat/gdpr-restriction` · **Blocked by counsel** (can a restricted record still be filed?).

**Schema:** `("guest", "restricted_at", "TEXT")`, `("guest", "restricted_reason", "TEXT")`.
**Steps:** `POST /guests/{id}/restrict` and `/unrestrict` (host-scoped, audited). While restricted: guest and host edit forms read-only; excluded from CSV/PDF bulk exports (still in the per-guest DSR export); **reporting behaviour is a `config.RESTRICTED_BLOCKS_FILING` flag defaulting to `False` until counsel decides** — `reporting.collect_sendable` consults it. Badge in `submission_detail.html` / `reservation_detail.html`.
**Tests:** edits refused; bulk exports skip; filing unaffected with the default flag.

### BE-10 — Workspace export and termination deletion (LEGAL-GATED) `[A-19]` — P2

**Branch:** `feat/gdpr-workspace-termination` · **Depends on:** G-D11

**Files:** `App/app/routes/admin_accounts.py` (admin user routes `:377-500`), NEW `App/app/workspace_export.py`, `App/app/housebook.py`, tests.
**Steps**
1. `POST /admin/users/{id}/export` (platform admin only): builds a ZIP in a temp dir with `housebook.csv` (all rows incl. archived), per-guest PDFs (`housebook.build_housebook_pdfs_zip`), all Doručenka PDFs, invoices PDFs, and a `manifest.json` (counts, generated_at). Streams it; deletes the temp file; audits `workspace_exported`.
2. `POST /admin/users/{id}/schedule-deletion` sets `user_account.deletion_due_at` (new column `("user_account","deletion_due_at","TEXT")`) = now + G-D11 days; account disabled. `retention.run` deletes due workspaces: photos → guests → submissions → reservations → apartments → entities → invoices (the `invoice_purge_unlock` setting pattern in `db.py:400-424` must be used for issued invoices) → audit rows → `user_account`. Double confirmation form with the username typed.
**Tests:** export contents; deletion removes every row with that `owner_user_id` and nothing else; issued-invoice trigger respected.

### BE-11 — Run the document-number backfill on deploy `[A-9]` — P1

**Branch:** `chore/gdpr-backfill-on-deploy`

**Files:** `deploy/lightsail/scripts/deploy.sh`, `docs/OPERATIONS.md`.
**Steps:** after the post-deploy health check in `deploy.sh`, run `docker compose exec -T ubyhost python scripts/migrate_encrypt_doc_fields.py` (the script is documented as idempotent and refuses without a key). Fail the deploy loudly on non-zero exit. Add a `--check` (or reuse `--dry-run`) invocation that prints the remaining plaintext row count; log only the count.
**Tests:** none in pytest (shell). Add a smoke assertion to `deploy/lightsail/scripts/smoke-remote.sh` that the remaining count is 0. Record in `FOLLOWUPS.md` W2.2 that item 1 is done; item 2 (drop plaintext columns) stays open.

### BE-12 — Encrypt passport files and signatures at rest `[A-8]` — P2

**Branch:** `feat/gdpr-encrypt-blobs`

**Files:** `App/app/passport_photos.py` (`save_photo` `:92`, `read_photo`), `App/app/db.py` (`ENCRYPTED_GUEST_COLUMNS`), `App/app/housebook.py` (PDF uses signature), new migration script `App/scripts/migrate_encrypt_signatures.py`.
**Steps:** passport files: write `db.encrypt_secret`-style Fernet ciphertext (bytes variant) to `{guest_id}.{ext}.enc`; `read_photo` decrypts; `has_photo`/`delete_photo`/`_orphan_ids` recognise both suffixes; one-shot migration encrypts existing files. Signatures: add `("guest","signature_png_enc","TEXT")`, add `"signature_png": "signature_png_enc"` to `ENCRYPTED_GUEST_COLUMNS` (the existing hydrate/write-redirect machinery then does the rest), migration script modelled on `migrate_encrypt_doc_fields.py`. Names/DOB stay plaintext (search/sort) — note in `FOLLOWUPS.md`.
**Tests:** file on disk is not a valid image/PDF header; round-trip read; `reporting.guest_has_signature` still true after migration; decryption failure raises like `decrypt_field`.

### BE-13 — Security incident register `[B-10]` — P1

**Branch:** `feat/gdpr-incident-register` · **Pairs with:** LD-5

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS security_incident (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at             TEXT NOT NULL,
    reported_by             TEXT,
    summary                 TEXT NOT NULL,
    data_categories         TEXT,
    affected_owner_ids      TEXT,
    approx_subjects         INTEGER,
    risk_level              TEXT CHECK (risk_level IN ('none','low','high')),
    contained_at            TEXT,
    controllers_notified_at TEXT,
    authority_notified_at   TEXT,
    subjects_notified_at    TEXT,
    closed_at               TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);
```
**Steps:** platform-admin-only routes `GET/POST /admin/incidents`, `POST /admin/incidents/{id}` in `routes/admin_accounts.py` (admin role check as in `/admin/users`). "Notify controllers" button renders a pre-filled e-mail **draft** (to each affected workspace's legal-entity contact) as text to copy — do not auto-send. Link existing signals: when `guest_pin_abuse` alerts fire N times in 24 h, raise a platform-admin alert suggesting an incident review (no automatic incident creation).
**Tests:** non-admin 403; create/update; `affected_owner_ids` stored as JSON array; draft includes the 72-hour note from LD-5.

---

# B. App Frontend

### FE-1 — Clickwrap acceptance screen `[A-6] [A-7]` — P0 (with BE-1)

**Files:** NEW `App/app/templates/account_accept.html` (extend `auth_base.html` like `account_password.html`), `App/app/host_i18n.py`.
**UX requirements**
- Heading, one paragraph, then a list of the pending documents — each a link opening in a new tab, showing its version and effective date.
- **One unchecked** checkbox: "I have read and agree to the Terms of Service, the Data Processing Agreement and the Privacy Policy listed above." (LEGAL-GATED COPY; CS pair required.)
- One primary button "Continue" — disabled state is **not** used; server validates.
- "Sign out" secondary link.
- No pre-ticking, no hiding the links in a scroll box, tap targets ≥ 44 px (repo has `test_auth_tap_targets.py` — extend it).
**Tests:** rendered HTML contains an unchecked checkbox and one link per pending doc; EN/CS parity; no-JS submit works (`test_auth_forms_no_js.py` pattern).

### FE-2 — Guest notice version shown and acknowledged `[A-4]` — P1 (with BE-5)

**Files:** `App/app/templates/guest/_legal_notice.html`, `App/app/templates/guest/privacy.html`, `App/app/i18n.py`.
- Show "Privacy notice version {GUEST_NOTICE_VERSION}" under the notice and on `/l/{token}/privacy`.
- Split the current single checkbox label (`legal_ack_label`) into accuracy + notice only if counsel wants it (LEGAL-GATED); otherwise unchanged.
**Tests:** version string present in both languages.

### FE-3 — Settings → "Data protection" panel `[B-4]` — P2

**Files:** `App/app/templates/settings.html`, `App/app/routes/admin.py` (settings handler `:2126`), `App/app/host_i18n.py`.
Show: last retention run (from `settings.retention_last_run`) with dry-run/live badge and counts; records due in the next 30 days (link to house-book export); last successful backup from `/data/backups/.last_success.json` (OPS-1) — platform admin only, with "encrypted: yes/no"; open data-subject requests count (BE-8).
Then **fix the copy**: the host guide claim `guide.security.backups` must describe only what this panel shows (audit doc row "Settings shows backup status…" INCONSISTENT).
**Tests:** panel renders with and without the marker file; host (non-admin) never sees backup internals.

### FE-4 — Cookie & storage table, generated from one inventory `[M-3]` — P2

**Files:** NEW `App/app/cookie_inventory.py`, `App/app/templates/privacy.html`, `App/app/templates/guest/privacy.html`, `App/app/privacy_policy_i18n.py`, `App/app/i18n.py`, tests.
- `cookie_inventory.py`: a tuple of dicts `{name, set_by (file:function), party ('first'|'Cloudflare'), purpose_key, lifetime_key, surface ('host'|'guest'|'public'), kind ('cookie'|'localStorage')}` covering: `ubyhost_session`, `ubyhost_csrf`, `ubyhost_lang`, `ubyhost_pin`, `ubyhost_owned`, `ubyhost_claim`, `ubyhost_guest_lang`, localStorage `ubyhost-command-recents`, `ubyhost-saved-stay-views`, the sidebar key in `static/app.js:313`, and Cloudflare `__cf_bm`, `cf_clearance` (party Cloudflare; mark "set only when Cloudflare challenges the request" — confirm names in MK-2).
- Render a table (name, provider, purpose, lifetime) in `/privacy` §7 and in the guest privacy page "Necessary cookies" section.
**Tests:** `test_cookie_inventory.py` greps `App/app` for `set_cookie(` and `localStorage.setItem(` and asserts every cookie-name constant / storage key is in the inventory (fails when someone adds an undeclared cookie); lifetimes in the inventory equal the `max_age` constants in code.

### FE-5 — Data-subject request screens — P2 (with BE-8)

**Files:** NEW `App/app/templates/privacy_requests.html`, `App/app/templates/guest_form_admin.html` / `submission_detail.html` (add "Export data (JSON)" and "Record a request" actions on the guest detail), `App/app/host_i18n.py`, sidebar entry in `base.html` under Settings.
UX: list with due date and overdue badge; create form (type, channel, subject: pick guest by id from the guest page, no free-text personal data); close form with outcome enum + short note.

### FE-6 — Controller readiness and alert copy — P1 (with BE-7)

**Files:** `App/app/templates/apartment_form.html`, `App/app/templates/entities.html`, `App/app/host_i18n.py`.
Readiness item links to the entity form; entity form marks name, seat/IČO and contact e-mail as required when the entity is used as a controller.

---

# C. Marketing Site (ubyhost.com public pages in the same app)

### MK-1 — No-tracking guardrail test `[M-1] [M-5]` — P1

**Branch:** `test/gdpr-no-tracking`
**Files:** NEW `App/tests/test_no_tracking.py`.
For every public route (`/`, `/jak-to-funguje`, `/cenik`, every `/pruvodce/{slug}` from `public_guides.py`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`, `/login`) in `cs` and `en`:
- every `Set-Cookie` name ∈ `{"ubyhost_lang","ubyhost_csrf"}` (import from `cookie_inventory` once FE-4 lands);
- every `<script src>` / `<link href>` / `<img src>` / `<iframe src>` is same-origin or `https://challenges.cloudflare.com` (login only);
- the `Content-Security-Policy` header equals the expected string (so widening it requires changing this test — and this plan's MK-5).
**Done when:** adding GA, a pixel, a CDN font or a chat widget fails CI.

### MK-2 — Verify and record Cloudflare edge behaviour `[M-2]` — P2 (operator task, no code)

In the Cloudflare dashboard for `ubyhost.com` record in `docs/CLOUDFLARE.md` (new § "Privacy-relevant settings", with date): Web Analytics / RUM **off** (or: automatic beacon injection off); Zaraz **off**; Email Address Obfuscation (on — same-origin script, no cookie; acceptable); Bot Fight Mode off (already documented); challenge cookies observed (`__cf_bm`, `cf_clearance`) with lifetimes, from a real browser session's DevTools; Page Shield / client-side security mode (report-only CSP vs script). Feed exact names into FE-4.

### MK-3 — Public cookie section content `[M-3]` — P2

`privacy_policy_i18n.py` `privacy.s07_body` (EN/CS): keep the prose, add "The full list is in the table below" and render the FE-4 table; state that no consent banner is shown because only strictly necessary storage is used (LEGAL-GATED COPY — counsel to approve the wording and the § 89(3) ZEK exemption reasoning).

### MK-4 — Language-cookie lifetime — P3

`host_i18n.py` `LANG_COOKIE_MAX_AGE` is one year. ÚOOU lists disproportionate lifetimes as a deficiency; set it to 180 days unless the owner objects. Only set the cookie on an explicit switch or login (verify the existing `remember_language` call sites; do not set it on a plain page view).

### MK-5 — CMP specification, only if analytics or marketing tags are ever introduced — P3 (spec, no code now)

Add to `docs/DESIGN.md` a § "Consent banner (not in use)":
- Prefer no tracking. If measurement is needed, prefer server-side aggregate counts from the OPS-3 access log (route templates only) — no device access, no banner.
- If any client-side tag is added: self-hosted, open-source CMP bundled under `/static` (to satisfy CSP `'self'`), loaded before any tag; tags injected **only after** consent, per category.
- First layer: "Accept all" and "Reject all" as buttons of equal size, colour and contrast, plus "Settings"; no pre-ticked categories; banner does not block reading; Czech first.
- Second layer: per-category toggles + per-cookie table (FE-4).
- Persistent footer link "Cookie settings" in `_public_footer.html` to withdraw/change.
- Consent record table `cookie_consent (id, consent_id TEXT, choices JSON, banner_version, policy_version, at, ip_hash)` — hash IP with a rotating salt; retain 13 months (counsel).
- Re-prompt after 6–13 months or on material change (counsel).
- MK-1 must be updated in the same PR.

---

# D. Legal Docs & Policies

These are documents, not code. Store drafts under `docs/privacy/` (NEW directory). Each is an **input for counsel**, not a finished legal text.

### LD-1 — Records of processing (Art 30) — P1
`docs/privacy/ROPA.md` with two parts: (a) **Art 30(2) processor record** for guest data processed for each host (categories of controllers, processing, transfers, TOMs → LD-7); (b) **Art 30(1) controller record** for host accounts, security logs, support mailbox, invoicing to hosts (if any), and the public site. Pull categories from the review § 0.3 table.

### LD-2 — DPIA — P1
`docs/privacy/DPIA.md` using ÚOOU's DPIA methodology page as the template. Cover: identity documents, optional ID images, possible children, multi-tenant platform, automated police filing, admin impersonation, transfers. Output: residual risks and whether ÚOOU prior consultation is needed. **Counsel decides if it is mandatory.**

### LD-3 — Retention schedule — P1
`docs/privacy/RETENTION.md`: one table — data item → storage location → trigger → period → deletion mechanism (code path) → legal basis for the period. Must match BE-2/3/4, OPS-1/3, `mail.purge_old` (14 d), `SUBMISSION_PAYLOAD_DAYS` (90 d), `PHOTO_GRACE_DAYS` (30 d), invoices (10 y). Then align guest notice `privacy_retention_body` (`i18n.py:463`), `privacy_policy_i18n.py` §11, `dpa_i18n.py` §15 (LEGAL-GATED COPY). Fix the "six years from the last entry" vs per-row mismatch flagged in the audit.

### LD-4 — Correct the subprocessor register — P0
`App/app/subprocessors_i18n.py` EN/CS:
- Google Drive row: remove "encrypted" until OPS-1 is live; if G-D2 retires Drive, remove the row (30-day notice rule in `subprocessors.change_body` applies to **new** subprocessors, not removals).
- AWS row: S3 wording "encrypted" only after OPS-1/OPS-2.
- Add the **support mailbox provider** once identified.
- Bump `subprocessors.effective` date/version; bump `config.DPA_VERSION` if counsel treats the register as part of the DPA (it says so) → triggers BE-1 re-acceptance.
**Test:** extend `tests/test_legal_contents.py` (or `test_public_legal.py`) with a regression that renders `/subprocessors` in EN and CS and asserts the backup rows match the approved post-OPS-1 wording (update the expected string only together with LD-9 evidence that OPS-1/OPS-2 are live).

### LD-5 — Breach response runbook — P1
`docs/privacy/INCIDENT_RESPONSE.md`: detection sources (alerts, Cloudflare, AWS, host reports), triage within 24 h, containment steps (rotate `UBYHOST_SECRET_KEY` procedure already in `docs/OPERATIONS.md` § "If the secret key is lost or rotated", invalidate sessions via `session_version`, rotate permalinks/PINs), **processor → controller notification "without undue delay"** (target ≤ 24 h from awareness) with the BE-13 draft, reminder that the controller has 72 h to notify ÚOOU, evidence to preserve (logs from OPS-3 before rotation), post-incident review. Counsel approves thresholds.

### LD-6 — Data-subject request runbook — P2
`docs/privacy/DSR_RUNBOOK.md`: who handles requests arriving at the operator vs the host; identity verification; what each right means under Art 6(1)(c) (portability/objection generally not applicable; erasure limited by § 101); 1-month deadline; using BE-8 tooling; templates for replies (counsel).

### LD-7 — Technical and organisational measures annex — P1
`docs/privacy/TOMS.md`, split into **code-enforced** (cite `docs/SECURITY.md` rows) vs **operator-configured** (Cloudflare, backups, key custody, access to the Lightsail host, GitHub access, 2FA on all vendor accounts). Link from `dpa_i18n.py` §10 once counsel approves.

### LD-8 — Reconcile the INCONSISTENT rows in `docs/TECHNICAL_COMPLIANCE_AUDIT.md` — P1
Copy fixes (LEGAL-GATED): archive vs delete (`host_i18n` `archive.retention_note`); "audit log of everything" (`App/README.md`) → enumerated list; backup status claim (FE-3); retention trigger wording (LD-3); controller fallback (BE-7). Re-run the audit matrix and update its "Re-verified" date.

### LD-9 — Vendor evidence file — P1
`docs/vendors/README.md`: for AWS (DPA auto-incorporated; account id, regions: Lightsail region, SES `eu-central-1`, S3 bucket), Cloudflare (Self-Serve Subscription Agreement + DPA; plan; enabled features from MK-2), Render (render.com/dpa; confirm staging holds only synthetic data), Google (Workspace + Cloud DPA **or** "retired on <date>"), support mailbox provider, GitHub/Cursor (policy: no production data, logs or DB copies in dev tools or AI assistants; the Cloudflare observability MCP in `.cursor/mcp.json` must not be pointed at production logs unless that vendor is added as a subprocessor). Record date checked and who checked.

### LD-10 — Staging data policy — P2
One paragraph in `docs/DEPLOYMENT.md`: staging (Render) uses demo/synthetic data only; never restore a production backup to staging; `env_guard` keeps `prod` UbyPort off staging.

---

## Items this plan deliberately does **not** automate

Implement the mechanism, leave the switch off or the text as a placeholder, until
a qualified Czech/EU data-protection lawyer signs off:

1. Turning on `UBYHOST_RETENTION_AUTOPURGE=1` (retention anchor and periods — G-D4…G-D7).
2. Any change to statutory citations or the reporting deadline (including eTurista's proposed 24 h rule).
3. Making ID-image upload mandatory, or changing its default from `off`.
4. Under-15 signature handling and the e-signature claim on registration PDFs.
5. Restriction blocking police filing (`RESTRICTED_BLOCKS_FILING`).
6. Workspace deletion timing (G-D11).
7. Any public statement about transfers ("data stays in the EU"), DPIA/DPO conclusions, or breach-notification deadlines.
8. The wording of the clickwrap checkbox, the guest acknowledgement and the no-banner cookie statement.
