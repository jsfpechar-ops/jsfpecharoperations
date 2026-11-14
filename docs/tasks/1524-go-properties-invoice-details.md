# 1524: Go port of Invoice details (POST /entities/{id}/invoice) with the VAT register lookup

Status: review
Depends on: 1523 | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1524 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1524 step'` and `git show --stat` on those commits.

## 1. Objective

Port the save and the register lookup of the editor's Invoice details form: bank account in three parts, BIC (derived from the bank code when absent), VAT status, registry entry, numbering and due days; plus the MFČR VAT register lookup that proposes VAT status and published bank accounts.

## 2. Context

Sidecar `docs/tasks/1524-files/`; copy, check, test. **Do not open the files.**

| Route | Python | Parity |
|---|---|---|
| `POST /entities/{id}/invoice` | `entity_invoice_details` admin.py 966-980, `_invoice_details_response` 950-964, `invoices.save_invoice_details` 503-525, `lookup_invoice_details` 544-591, `_fill_register_account` 593-618, `_typed_bank_parts` 620-640, `_settings_entity_from_form` 528-541, `derive_missing_bic` 752-764, `apply_account_payload(accept_parts=True)` 718-750; `vat_register.py` (all) | a business that is not the host's, unknown or archived is `flash.error.no_such_entity`; a refused account renders the page with status 422, the typed values and `entities.bank.invalid`, and writes nothing; an all-empty account never wipes a stored IBAN-only account; a sent blank clears account and IBAN; an absent and unstored BIC is derived from the bank code, a posted BIC (even blank) wins; the save writes only the posted columns and one `audit` row `entity_invoice_details_saved` (`id=<id>`, owner = the workspace); success goes to `next` else `/entities?edit=<id>#entity-invoice` with `flash.entities.saved`; the lookup (button `fill_from_register` or `use_register_account`) saves nothing, fills a blank registry entry, proposes the VAT status, and offers or fills published accounts; a typed account is never replaced |

**New outbound request: PR text (hard rule 2).** The lookup button sends, besides the ARES request of brief 1523, one HTTPS POST (SOAP) to `https://adisrws.mfcr.cz/dpr/axis2/services/rozhraniCRPDPH.rozhraniCRPDPHSOAP` with only the DIČ digits, `User-Agent: UbyHost`, 6 s timeout, 24 h cache, on the host's click: exactly `vat_register.py` today. Reason: fill VAT status and the published bank account from the official register. Tests use a local server (`vatURL` is a variable); the real register is never called. Owner note: the Go container needs outbound HTTPS to `adisrws.mfcr.cz`.

**Paths.** `/entities/{id}/invoice` is its own path. With 1522, 1523 and 1524 the whole `/entities/*` prefix is served by Go (archive, unarchive, delete from 1300). `/entities` (exact) still needs brief 1525.

**Live on deploy.** The new route is registered at deploy. Assumption: no `/entities/*` prefix is routed today (the existing routes are exact paths), so it is not live; if the prefix is routed, it is.

Rules: hard rules 2, 3, 5, 8.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/vatregister.go` | create | SOAP client, parser, cache |
| `go/internal/web/properties/invoice_details.go` | create | `RegisterInvoiceDetails`, save, lookup, account helpers |
| `go/internal/web/properties/invoice_details_test.go` | create | tests (local servers) |
| `go/cmd/ubyhost-web/register_web_properties_invoice.go` | create | `init()` calling `registerRoutes` |
| `docs/tasks/1524-go-properties-invoice-details.md` | edit | `Status:` line only |
| `docs/tasks/1524-report.md` | create | report |

No other file may change (the catalog keys were added by 1523).

## 4. Steps

1. Copy the new files:

```bash
mkdir -p go/internal/web/properties && cp docs/tasks/1524-files/go/internal/web/properties/vatregister.go.txt go/internal/web/properties/vatregister.go
mkdir -p go/internal/web/properties && cp docs/tasks/1524-files/go/internal/web/properties/invoice_details.go.txt go/internal/web/properties/invoice_details.go
mkdir -p go/internal/web/properties && cp docs/tasks/1524-files/go/internal/web/properties/invoice_details_test.go.txt go/internal/web/properties/invoice_details_test.go
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1524-files/go/cmd/ubyhost-web/register_web_properties_invoice.go.txt go/cmd/ubyhost-web/register_web_properties_invoice.go
```

2. Check them:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -12
3e8535560e976bd892f566a1b813a0fd8fb4e45c68228c1352253b596b33207c  go/internal/web/properties/vatregister.go
30355756c9c25017186cefb9bc6eeb5f4695f1906c96513e426a3e6a3806e6b2  go/internal/web/properties/invoice_details.go
e317a787c598ae17b03c8b623adb59bd5b7eda30c5a67fe04615441ab44d611d  go/internal/web/properties/invoice_details_test.go
5576a2a7bfc9ea6da8e06aac67fb6a8af24c9feaace47c9d4fe0a28a8c6f84f7  go/cmd/ubyhost-web/register_web_properties_invoice.go
SUMS
```

Expected: 4 lines ending `OK`. Commit: `git add go && git commit -q -m "1524 step 2: files" && git show --stat HEAD | tail -8`.

3. Run §6, write the report, set `Status: review`, commit `1524 step 3`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `App/tests/conftest.py`, every file under `App/app/`, `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere (deploy files, env docs, tests). Do not edit the sidecar files, `go.mod` or `go.sum`; no `go get`, no `go mod tidy`.
- Hard rules 2, 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge; no branch, no PR.

## 6. Commands

From the repo root. The Go tests need PostgreSQL: `export UBYHOST_TEST_DATABASE_URL=postgresql://...` as the owner's environment gives (unset means the database tests skip, which is a stop (§8), not a pass).

```bash
cd go && test -z "$(gofmt -l .)" && go build ./... && go vet ./internal/web/properties/ ./cmd/... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -50
```

Expected: no `SKIP`; `--- PASS` for `TestParseVAT`, `TestInvoiceDetailsSave`, `TestInvoiceDetailsLookup` and all older tests; two `ok` lines.

```bash
python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3
git log --oneline --grep='^1524 step' | tail -10
```

Expected: `context lint: OK`; one commit per step that changed a file.

## 7. Acceptance

- [ ] Step 2: 4 `OK`; gofmt, vet, build clean; the §6 tests ran and pass.
- [ ] `git log --oneline --grep='^1524 step'` and `git show --stat` touch only §3 paths.

## 8. Stop and ask

Stop, and write the report, if: a sidecar `sha256sum` or `git apply --check` fails; an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1524-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of the `1524 step` commits), each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/invoice_details.go`: the ownership and archived check in `invoiceDetails`, `applyAccountParts` (never wipes an IBAN-only account), the single `UPDATE` of posted columns, the audit row.
- `go/internal/web/properties/vatregister.go` (outbound SOAP: only the DIČ digits; response size cap 200 000 bytes).

## Owner steps

1. Nothing to deploy yet. Confirm the container reaches `adisrws.mfcr.cz` before the lookup is used on Go.
