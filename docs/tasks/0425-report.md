# 0425 report

Status: review
Branch: jsfpechar-ops-patch-1 (#542) — owner authorized direct implementation in chat ("you implement it").

## Files changed

- `App/app/migrations/0026_payment_requests.sql`: new — `stripe_account` + `payment_request` tables, indexes, CHECK constraints.
- `App/app/payment_request.py`: new — create/get/for_owner/set_status/mark_paid/expire_sweep/qr_payload.
- `App/app/retention.py`: two comment blocks (0425 fields) + workspace-deletion DELETEs for both new tables.
- `App/tests/test_payment_request_model.py`: new — 12 tests.
- Lint maintenance (compaction, per workflow.md): `docs/context/decisions.md` tightened + 6 oldest lines archived to `docs/archive/decisions-2026.md`; `docs/context/status.md` 0425 line + compaction; brief gained the `## 9. Report` section the lint requires.

## Commands (last lines)

- `pytest tests/test_payment_request_model.py tests/test_migrations.py tests/test_retention.py` → `38 passed in 5.31s`, 0 skipped.
- `python3 scripts/context_lint.py` → `context lint: OK`.

## Section 7

- [x] Migration 0026 applies fresh + upgraded; VS UNIQUE holds (tested).
- [x] Model functions per §4; `db.audit` on every status change (`payment_request_status`, `payment_request_paid`).
- [x] Retention lines exist (comment + workspace deletion coverage).
- [x] Scoped tests pass 0 skipped; no other test file changed.

## Deviations

- Brief renumbered 0421 → 0425 (0421 was taken by backup-cadence; lint names 0425 as next free).
- Test cleanup deletes the owner's `audit` rows too (FK on user_account has no cascade).
- Czech-account test uses a mod-11-valid number (`19-2000145399/0800`); the first draft failed the checksum by design of `payments.normalise_account`.
- No `.venv` in the sandbox: deps installed from `requirements.txt`/`requirements-dev.txt` per repo pins.
- `expire_sweep` exists here but no scheduler job calls it yet (deliberate: next brief wires it).

## Questions

None.

## Owner steps left

- Merge #542 when green (CI runs the full suite + browser shards).
- Brief 0426 next: Stripe Connect module (`stripe` SDK pinned+hashed, `UBYHOST_STRIPE_MODE=test`, the owner's `sk_test` env var, webhook signature verification).
