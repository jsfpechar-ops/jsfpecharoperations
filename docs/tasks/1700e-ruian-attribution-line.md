# 1700e: RÚIAN credit line on the privacy/licence page

Status: todo — scoped (2026-11-17). Executable only after its exact-diff pass (sidecars, anchors, sha256 table), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku).
Depends on: 1700c (`go/internal/ruian/attribution.go`), 1700d | Branch: task/1700e-ruian-attribution-line
Executor: Haiku 5.5 | Tier: C (Sonnet writes the exact-diff pass)

> **One big PR mode.** Work on the current branch; commit `1700e step k` with explicit `git add <paths>`; never push, branch or open a PR.

## 1. Objective

The ČÚZK address data (CC BY 4.0) needs a credit. Show `ruian.Attribution` ("Adresní data: ČÚZK, RÚIAN (CC BY 4.0)") once, on the page that already lists data sources or licences (privacy page or legal/licence page; the exact-diff pass finds which with `grep`), in every language that page has. One place only (rule 9); the suggest list and `ruian_suggest.js` stay unchanged. Plan: [ruian-local](../plans/ruian-local.md) §4.

## 2. Scope notes for the exact-diff pass

- If the page is still Python-rendered, the copy goes into its template and catalog as today (legal copy: check [legal positions](../UbyHost_workplan/04_legal_positions.md#summary-of-decisions) wording; no lawyer item, a licence credit is not a legal position). If a Go port of the page exists, change the Go side instead.
- Guest or public page change: rule 7 browser and geometry tests with 0 skipped and one 390 px screenshot.
- Keep the Czech text equal to `ruian.Attribution`; a Go test or the catalog check pins it.

## Rollout and rollback

Ships with the page; revert the commits.
