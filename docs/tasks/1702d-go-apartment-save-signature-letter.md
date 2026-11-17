# 1702d: Go property settings 3d: signature, fee return and police-letter test on save

Status: replaced by 1702d1 and 1702d2 (exact-diff pass 2026-11-17 split it: [1702d1](1702d1-go-apartment-save-signature-fee-return.md) ready, [1702d2](1702d2-go-apartment-save-letter-test.md) scoped).
Decision 2026-11-17 (orchestrator, rule 2): the Go UbyPort login test calls the same host Python already calls; no new destination; the PR that adds it (1702d2) gives the reason.
Depends on: 1702c2 (after 1702c1) | Base commit: current tip of the working branch | Branch: task/1702d-go-apartment-save-signature-letter
Executor: Haiku 5.5 | Tier: A

Nothing to run here. 1702d1: signature, `fee_return_to` and police-letter values saved without a typed password (sidecars in `docs/tasks/1702d-files/`). 1702d2: the read-only connection test when the password was typed in the same save.
