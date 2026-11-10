# 1082 report: server draft of an unfinished guest form (ships dark)

Status: review

## Files changed

Created: `App/app/migrations/0042_guest_form_draft.sql`, `App/migrations_pg/00013_guest_form_draft.sql`, `App/app/guest_draft.py`, `App/tests/test_guest_form_draft_1082.py`.
Edited: `App/app/scheduler.py`, `App/app/retention.py`, `App/app/routes/guest.py`, `App/app/cookie_inventory.py`, `App/app/guest_uk_i18n.py`, `docs/privacy/RETENTION.md`, `docs/privacy/ROPA.md`, `App/tests/test_migrations.py`, `App/tests/test_db_postgres.py`, `App/tests/test_privacy_first.py`, `App/tests/test_cookie_inventory.py`.

## Commands (last lines)

- A (SQLite): `40 passed, 55 skipped in 5.31s`. The 55 skips are `test_db_postgres.py` without a database URL.
- A, Postgres part, local PostgreSQL 16 (`UBYHOST_TEST_DATABASE_URL`, fresh `ubyhost_test`): `tests/test_db_postgres.py` `55 passed in 31.17s`.
- B: `96 passed in 6.07s`.
- C: `118 passed in 11.28s`.
- Extra: `tests/test_guest_form_draft_1082.py` with `UBYHOST_DATABASE_URL` on the same local PostgreSQL: `25 passed in 7.93s` (the upsert runs on both engines).
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none new from this brief except the standing "update status.md at review").

## Acceptance (section 7)

- [x] Keyed by `(reservation_id, sha256(device key))` plus claim generation and owned count; cookie value never stored; other device gets nothing (5c); late autosave never reaches the next guest (5f).
- [x] `fields_enc` holds no plaintext document number (5b); photo, signature and tick never stored.
- [x] Sent form deletes the draft; purge pins 7 days and the day after check-out, runs in the 12-hour sweep with autopurge off; workspace deletion removes drafts; no `STEPS` entry; retention comment, `RETENTION.md` and `ROPA.md` rows.
- [x] Filing pin (5d) green.
- [x] Throttle 120 per 15 min; CSRF refused without the token; 413 over 16 KB.
- [x] Migrations 0042 and goose 00013; every pin bumped; command A green.
- [x] Privacy crawl reaches `ubyhost_draft`; inventory in six languages.
- [x] Diff against `origin/main` touches only section 3 files (plus this brief and report); no template, CSS, JS or i18n change.

## Deviations

- `/draft`: a non-numeric `Content-Length` header counts as 0 (`try/except ValueError`) instead of raising; the 16 KB rule is unchanged.
- Step 4 names command B, but its test file is created in step 5; B ran after step 5.
- The test file has its own `_cleanup`, `_seed`, `_payload` modelled on `test_guest_child_document.py` (own token, an owner account for the host-preview and workspace tests, extra stays for the purge); it imports only `SIGNATURE` from that file. Route tests run with mail off (`mail.mail_enabled` patched), so no claim step.
- 5g: the workspace-deletion test calls `retention._delete_workspace` directly. The `STEPS` check asserts `"guest_draft"` is nowhere in `repr(retention.STEPS)`.
- Goose itself is not installed locally; the goose twin was exercised only through `test_db_postgres.py`. CI runs `goose up`.
- No PR opened and no fresh-reviewer step run (left to the orchestrator).

## Questions

None.

## Owner steps left

None until review. After review: one PR, merged only with `scripts/merge-pr-on-green.sh`.
