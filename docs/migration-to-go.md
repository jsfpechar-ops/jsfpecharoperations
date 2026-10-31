# Migration to Go (proposal, not started)

> ⚠️ UNKNOWN — needs human input: the repository contains **no Go code and no
> recorded decision** to migrate to Go + River + Caddy. The brief describes this
> as "being considered". The repo shows the Postgres step is planned and deferred
> (commit `84763c6b`, `docs/context/status.md`). Confirm the decision before
> acting on this page. Everything below is a proposal built from the code's
> constraints.

## Blockers the code shows today (read before any port)

1. **Database is SQLite-specific.** `COLLATE NOCASE` (`App/app/db.py:97`), `AUTOINCREMENT` (`db.py:96`), `PRAGMA` (`db.py:685-690`), `sqlite_master` (`db.py:1190`), `BEGIN IMMEDIATE` (`db.py:1212`), `IS` null-safe equality (`db.py:1416`). The app's own rule says SQL must be Postgres-portable (`AGENTS.md` rule 5), but these exist.
2. **Migrations are a custom runner** (`App/app/db.py:1124-1260`, 32 files `App/app/migrations/0002–0033`). Port the schema via the SQL files, not the Python runner.
3. **Job system is in-process APScheduler** with SQLite-table queues and optimistic claims (`App/app/scheduler.py`, `App/app/mail.py:655-661`). There is no River-style queue. A port must choose between a DB-backed job table (River uses Postgres) and external triggers.
4. **Encryption is Python Fernet with key derivation** (`App/app/db.py:1592-1700`). Any Go port must read the same ciphertexts: same key derivation (SHA-256 of session secret for legacy key, `db.py:1592-1607`) and Fernet format.
5. **Police client is NTLM SOAP with hand-built XML** (`App/app/ubyport/client.py`, `soap.py`). Go needs a compatible NTLM SOAP client; confirm the library choice against the real service in `test`.
6. **PDF is reportlab with fonts in `App/app/static/fonts/`**; output must be byte-compatible enough for the police receipts and any stored hashes (`pdf_sha256` in `invoices`).
7. **Deadline arithmetic** (`App/app/deadlines.py`) — the Czech holiday list and Prague-time rules must be ported exactly.

## Target architecture (from the brief — `⚠️ UNKNOWN` as a decision)

Go single binary, PostgreSQL, River for jobs, Caddy in front. Not in the repo.

## Cutover order (proposed)

1. **iCal sync** — read-only, lowest risk (`App/app/icalsync.py`).
2. **Read paths** — host dashboard views, read-only.
3. **Registration writes** — guest data writes, with the shared schema.
4. **PDF generation** — reportlab parity tests.
5. **Police API** — last; only after characterization tests (below).

## Compatibility contract

- Shared PostgreSQL schema during transition; both stacks behind one reverse proxy (Caddy), routing by path or host.
- Both stacks must honour the same encryption keys (`UBYHOST_DATA_KEYS`) and the same `schema_migrations` table.
- The Python stack remains the authority for filing until cutover of step 5.

## Rollback plan (per feature)

- Each feature routes behind a Caddy rule; rollback = route back to Python. `⚠️ UNKNOWN` current Caddy configuration in `deploy/lightsail/caddy` (not read in full).
- Data written by Go must be readable by Python: rollback is blocked on schema drift; define a freeze point per step.

## Characterization tests required before the police-API port

Must exist and pass against both stacks:
- `App/tests/test_deadlines.py` and `test_deadline_after_reporting.py` (existing).
- `App/tests/test_filing_watchdog.py` (existing).
- SOAP envelope golden tests for `ZapisUbytovane`, `TestDostupnosti`, `DejMiCiselnik` (`App/app/ubyport/soap.py`) — `⚠️ UNKNOWN` whether such golden files exist; none were located in the research pass.
- Error mapping tests for codes 1, 112, 150 and unknown severity (`App/app/ubyport/errors.py`).
- Outcome-unknown behaviour: never auto-resend except the one sweep retry (`App/app/reporting.py:97`).
- A run against UbyPort `test` (`ws_uby_test`) with NTLM — requires credentials from the owner.

## Open questions
- Is the Go migration decided? Who owns it?
- Is Postgres going first (SQLite → Postgres in Python) or is the Go port the way there?
- Target hosting: stays on Lightsail (`docs/LIGHTSAIL.md`)?
