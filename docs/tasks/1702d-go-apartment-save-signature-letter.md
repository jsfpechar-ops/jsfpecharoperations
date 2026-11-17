# 1702d: Go property settings 3d: signature, fee return and police-letter test on save

Status: todo — scoped (split out of 1702b by its exact-diff pass, 2026-11-17). Executable only after its own exact-diff pass (sidecars in `docs/tasks/1702d-files/`, step-0 hashes, sha256 table).
Decision 2026-11-17 (orchestrator, rule 2): the Go UbyPort login test calls the same host Python already calls; no new destination; give the reason in the PR.
Depends on: 1702c2 (after 1702c1) | Base commit: current tip of the working branch | Branch: task/1702d-go-apartment-save-signature-letter
Executor: Haiku 5.5 | Tier: A

> **One big PR mode.** Commit each step as `1702d step k`; never branch, push or open a PR.

## 1. Objective

Finish the tail of `apartment_update` (`App/app/routes/admin.py` 2544-2601) on top of 1702c: the signature save to the operator's `legal_entity` (`fee_signature_section`, `_signature_payload` 1145; `flash.entities.signature_invalid`; an undecryptable stored signature keeps showing as none, as 1701b), `stay_fee_routes.fee_return_after_save` (`fee_return_to`), and the police-letter branch (`police_letter.confirmed_fields`; `letter_saved_untested`, `_run_connection_test` only when `uby_ws_password` was typed in the same save, `property_setup.mark_tested`, `letter_test_ok`/`letter_test_failed`/`letter_test_unreachable`).

## 2. Context

- The connection test is a new outbound request on Go: reuse `go/internal/ubyport` (read-only login), never a new client; give the reason in the PR. A new login with an old password could lock the police account: keep Python's "typed in this save" rule exactly.
- Reuse the signature code of the entity editor (`entity_editor.go`) and of 1701b; the 1702c golden pair gets the new seeds (the connection test is faked at the client seam on both sides).

## 3. Files

Fixed by the exact-diff pass.
