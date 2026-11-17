# 1702d2: Go property settings 3d2: the police-letter connection test on save

Status: todo — scoped (split out of 1702d by its exact-diff pass, 2026-11-17). Executable only after its own exact-diff pass (sidecars in `docs/tasks/1702d2-files/`, step-0 hashes, sha256 table).
Decision 2026-11-17 (orchestrator, rule 2): **new outbound request on Go.** The Go UbyPort login test calls the same host Python already calls (the police UbyPort endpoint of `ubyport.EndpointFor`); no new destination. The PR must state that reason.
Depends on: 1702d1 (its step 7 committed) | Base commit: current tip of the working branch | Branch: task/1702d2-go-apartment-save-letter-test
Executor: Haiku 5.5 | Tier: A

> **One big PR mode.** Commit each step as `1702d2 step k`; never branch, push or open a PR.

## 1. Objective

Replace the 1702d1 seam `"the police-letter connection test (brief 1702d2)"` in `apartmentUpdateNotPorted` (`go/internal/web/properties/apartment_update.go`): police-letter values saved with `uby_ws_password` typed in the same save run Python's `_run_connection_test` (`App/app/routes/admin.py` 3506-3549) once, then `onboarding.MarkTested` on `ok`, and answer `flash.apartments.letter_test_ok` / `flash.error.letter_test_failed` (`auth`) / `flash.error.letter_test_unreachable` at `path#ubyport` (admin.py 2585-2600). Keep Python's "typed in this save" rule exactly: a new login with an old password could lock the police account.

## 2. Context (found by the 1702d exact-diff pass; not built yet)

- `go/internal/ubyport.Client` has `Post` and `Submit` only. Missing read-only calls: `test_availability` (TestDostupnosti), `max_batch_size` (MaximalniDelkaSeznamu), `code_list` (DejMiCiselnik) of `App/app/ubyport/client.py` 190-210, with `soap.build_simple_call`, `build_dej_mi_ciselnik`, `parse_scalar_response`, `parse_ciselnik_response`. Add them to the existing client (reuse `Post`, `ClientFor`), never a new client. This touches filing code: own sidecar + golden envelopes against the Python builders.
- `_run_connection_test` also writes: audits `ubyport_connection_ok` / `ubyport_connection_failed` / `ubyport_codebook_refresh_failed`; `billing_trial.mark_verified(apartment_id, owner)` (no Go port found: grep `MarkVerified` in go/ before writing); `alerts.resolve("ubyport_auth_failed:{id}")` (`privacy.ResolveAlert` exists); `codelists.store(KIND_ERRORS, rows)` (Go only reads the codebook in `ubyport/sweep.go`; no store found).
- Flash keys: none of the three is in a Go catalog yet; add them to `apartmentupdate/i18n_keys.txt` and regenerate with `App/scripts/go_host_i18n.py` (as 1702d1).
- Tests: no real network. Point `ClientFor` at an `httptest.Server` through the environment (`EndpointFor(getenv)`, mock environment, no NTLM) and assert each SOAPAction sent; cases ok, 401 (auth), dial failure (unreachable), code-list failure after a passed test (still ok, audit row).
- Likely too big for one Haiku session: the exact-diff pass decides whether to split into the client calls (ubyport) and the route.

## 3. Files

Fixed by the exact-diff pass.
