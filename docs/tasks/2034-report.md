# 2034 report

Status: review

## Summary

Public guide import (`source=url`) on Go guide index: Apify `website-content-crawler`, `FilterCodes` before `raw_json` and on model cards, `codes_left_out`, host form field `public_url`, notice copy per Design. Migration **00024** (00023 taken on branch 2032). Notion fetch not run against real Apify (owner step).

## Files (main)

`App/migrations_pg/00024_guide_import_public_url.sql`, `go/internal/guideimport/*`, `go/internal/web/ai/guide_import.go`, `guide_index.go`, `guide/templates/guide_index.tmpl`, `guide/i18n.json`, `App/app/host_i18n.py`, `host_vi_i18n.py`, `guide_i18n.py`, `templates/guide.html`, tests, `docs/privacy/*`, retention golden.

## Commands (last 5 lines each)

`gofmt -l …`: (empty)

`go vet …`: (empty)

`go test ./internal/guideimport/... ./internal/web/ai/... ./internal/schema/`: all ok

`go_host_i18n.py --check`: (empty)

`pytest` (brief §6 subset): 53 passed (host_i18n, guide_coverage, no_em_dashes, copy_cleanup, flash_literals, guest_guide, privacy_first)

`UBYHOST_REQUIRE_BROWSER=1 … test_go_guide_import_public_url_states`: **ERROR** at `go_web` setup — `pg_schema.py apply` failed (`current=False`, `extra_tables=5`, `column_mismatches=1` on fresh DB on this runner).

`context_lint.py`: `context lint: OK`

## §7

- [x] No code value in model input or cards (DB + unit); counts in `codes_left_out` only
- [x] Cards `check` only
- [x] URL refusals table in `guide_import_public_test.go`
- [x] Migration 00024, schema golden, Python tests pass
- [ ] 1668 harness screenshots **blocked** (see above); `UBYHOST_APIFY_TOKEN` set in test module for import UI

## Screenshots

None captured (harness DB apply blocked). Intended: `/tmp/shots2034/layout-lint/guide-import-url-{empty,notice,notice-one,error,queued}-{390,768,1280}.png` → `/opt/cursor/artifacts/2034/`.

## Deviations

- Migration **00024** (not 00023).
- E2E `codes_left_out` asserts **2** from fetch filter; output filter shown via `FilterCardFields` unit in same test (merge `clean` drops code-bearing cards).
- ROPA: no prior Apify line; new controller row added.
- Retention cutoff text: `listing or public page text fetched before`.
- `guide_import_test` “same source” replaced with bad `public_url` (single-value form fields).
- Help keys under `guide.setup` section.

## Owner

1. Staging Apify: paste public Notion URL; confirm drafts + notice (brief Owner step).
2. Enable via existing `UBYHOST_GO_PATHS` / job kinds switches.

## Final commit

`git rev-parse HEAD` on branch `cursor/2034-guide-import-url-992e` (see executor return).