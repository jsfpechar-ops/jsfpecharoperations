# Limitations and technical debt

Ranked by impact on safety, legal correctness and the migration. Each item
cites code. ⚠️ marks items needing owner confirmation.

## Ranked debt

1. **SQLite is the only database, with a single writer.** `App/app/db.py:667-686`. Limits concurrency and horizontal scale. The Postgres move is deferred (commit `84763c6b`).
2. **Tenancy is enforced per query, not by the database.** No RLS (`App/app/migrations/`, `App/app/db.py`). Safety relies on `App/app/access.py` helpers and inline `owner_user_id` clauses. Some lookups rely on an upstream check (`routes/admin.py:4265`). NULL-owner rows can match `owner_user_id IS NULL` (`db.py:1416`; backfill `auth.py:779-782`).
3. **No protocol-level idempotency with the police service.** A duplicate filing returns code 150 (`App/app/ubyport/errors.py:56`). Protection is app-side (`reporting.py:97`).
4. **Holiday list is hardcoded and sampled by tests.** `App/app/deadlines.py:38-59`; tests cover 2024–2026 and Easter 2015–2016 (`App/tests/test_deadlines.py`). Not checked against the official calendar.
5. **Plaintext copies of sensitive fields remain.** Guest `doc_number` and `visa_number` columns sit beside `_enc` columns (`App/app/db.py:222-225`). Submission receipts and `response_xml` are plaintext (`db.py:287-291`).
6. **Backups contain the key.** The archive includes `secret_key` (`docs/OPERATIONS.md` § Backup and restore). Encrypted with age in production, but key custody is an operator task.
7. **Documentation drift.** `docs/OPERATIONS.md` says the scheduler runs "in the web process"; in production it runs in the worker (`App/app/main.py:159`, `App/app/worker.py`).
8. **Production deploys automatically on green `main`, with no approval gate.** `.github/workflows/deploy-production.yml:19-22`; the GitHub `production` environment has no protection rules (checked). This contradicts `AGENTS.md` rule 8.
9. **Retention autopurge is off by default** (`App/app/config.py:221`). Data accumulates until enabled; the retention job only counts.
10. **Unverified against the real police service.** CI exercises only the mock (`App/mock_ubyport/server.py`). NTLM, TLS and WS-Addressing are not proven against `ws_uby_test`.
11. **Turnstile fails open** when Cloudflare is unreachable, for 5 attempts per 15 min per IP (`App/app/turnstile.py:19-20`, `:63-83`, confirmed). A bot-protection gap during vendor outages.
11a. **ARES and VAT-register modules are not called.** `App/app/ares.py` and `App/app/vat_register.py` have no importers in `App/app` (only UI strings in `host_vi_i18n.py`). Dead code, or imported by a path not found in this pass.
12. **Large inline i18n modules.** `App/app/host_i18n.py` (357 KB), `guide_i18n.py` and others; copy changes mean editing Python dictionaries (`docs/context/architecture.md`).
13. **Large modules.** `App/app/routes/admin.py` (116 KB), `App/app/reporting.py` (100 KB), `App/app/db.py` (69 KB), `App/app/mail_notify.py` (69 KB), `App/app/routes/guest.py` (77 KB).
14. **Dependency drift.** boto3 is `1.43.108` in `App/requirements.lock:31` but `1.43.118` in `App/requirements.txt:15`.
15. **Docs drift in env names.** `UBYHOST_ADMIN_PASSWORD` is documented in `docs/ENVIRONMENT.md` but not used in code; nine code-read names (e.g. `UBYHOST_SIGNUP_ENABLED`, `UBYHOST_META_*`) are undocumented.

## Deliberately deferred

- Postgres migration (`docs/context/status.md`; commit `84763c6b`).
- Go migration: no code and no recorded decision in the repo (see [migration-to-go](migration-to-go.md)).
- File retention plan: "decided, no build now" (`docs/context/status.md`, `docs/plans/file-retention.md`).
- Live door codes: `UBYHOST_DOOR_CODES_LIVE` defaults to 0 (`App/app/config.py:194`).
- Lawyer review of legal texts (`docs/context/status.md` § Blocked).

## Fragile: do not touch casually

- **`App/app/ubyport/` and the submission path in `App/app/reporting.py`.** The filing rule outranks other features (`AGENTS.md` rule 1; `docs/UBYPORT_CORE.md`).
- **`App/app/deadlines.py`.** Deadline arithmetic (D3 rule, Prague civil time). Changing it changes legal deadlines.
- **`App/app/db.py` migration runner and `startup_lock`** (`db.py:1088-1116`, `:1201-1229`).
- **`App/app/auth.py` session cookie and `session_version`** (`auth.py:315`, `:677-683`). Bumping it invalidates all sessions.
- **Secret key `data/secret_key` and `UBYHOST_DATA_KEYS`** (`App/app/config.py:44-95`, `App/app/db.py:1592-1607`). Losing or rotating them makes encrypted columns unreadable.
- **Single-writer assumption.** Never run two workers on one data volume (`App/app/worker.py:1-12`).
- **Scheduler job ids and `job_last_ok` keys** (`App/app/scheduler.py`). Used by the Operations page and heartbeats.
- **`App/app/retention.py`.** Every new personal-data field needs a line here (`AGENTS.md` rule 2).
