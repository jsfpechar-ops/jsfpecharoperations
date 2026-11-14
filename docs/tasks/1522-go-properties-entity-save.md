# 1522: Go port of the business save (POST /entities and POST /entities/{id})

Status: todo
Depends on: none | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1522 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1522 step'` and `git show --stat` on those commits.

## 1. Objective

Port `create_entity` and `update_entity` of `App/app/routes/admin.py` with the payload helpers they use, so the "add business" and "save business" forms work on Go. This closes the collision `POST /entities` (Python only while Go served GET). The "Fill from register" button is a hook that answers 501 until brief 1523.

## 2. Context

Sidecar `docs/tasks/1522-files/`; copy, check, test. **Do not open the files.**

| Route | Python | Parity |
|---|---|---|
| `POST /entities` | `create_entity` admin.py 1195-1228, `_entity_post_payload` 989-1008, `_entity_details_payload` 1011-1034, `_drawn_signature` 1037-1056, `_signature_payload` 1135-1160, `_resolve_controller_alerts` ~1163, `invoices.invoice_detail_payload` invoices.py 683-715, `apply_account_payload` 718-750, `payments.normalise_account` payments.py 109-125, `contact_phone.with_country_code` | blank name, bad IČO, bad account and bad signature each redirect to `/entities` with their error and write nothing; posted fields only (a field not in the form is not touched); account stored as display form plus IBAN; BIC upper-case without spaces; prefix = up to 6 letters or digits upper-case; next number > 0 with the current year; due days 0-365 (default 14); signature encrypted with the data key (Fernet) as `signature_png_enc`; row gets `created_at` and `owner_user_id` = the workspace; `controller_missing:<apartment>` alerts clear when the controller identity is complete; success goes to `next` (safe local path), else `/apartments/new?legal_entity_id=` with `flash.entities.added_first` when the host has no live property, else `/entities` with `flash.entities.added` |
| `POST /entities/{id}` | `update_entity` 1230-1259, `_reconcile_pay_way_alerts` ~1180 (Go: `stayfeemail.ReconcileNoPayWay`) | a business that is not the host's (or unknown) is `flash.error.no_such_entity`; an archived one can be edited; the same payload rules; goes to `next` else `/entities` with `flash.entities.saved` |

Known small gaps (all on inputs Python itself handles oddly): non-ASCII digits in IČO, next number and due days are not read as numbers; `.upper()` of `ß`. Both are listed for the reviewer.

**Paths.** After brief 1523 and 1524 and the layout gap of brief 1525 are closed, `/entities` and `/entities/*` can be switched. **Do not switch `/entities` or `/entities/*` before that**: `GET /entities` answers 501 for a host with an open alert (layout gap, brief 1525) and `POST ... fill_from_register` answers 501 until 1523.

**Live on deploy.** `POST /entities` and `POST /entities/{id}` are new Go routes. Assumption: `/entities` (exact path) is routed to Go today, because the list page is live. Then **`POST /entities` goes live the moment this deploys** (the add form), and so does `POST /entities/{id}` only if a `/entities/*` prefix is routed (assumed not: the archive routes of brief 1300 are separate paths). The add form's "Fill from register" button then answers 501 until 1523 is deployed too: ship 1522 and 1523 in the same deploy.

Rules: hard rules 2 (a signature image is stored only encrypted, as Python does; no new field), 3, 5, 8.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/entities.go` | create | `RegisterEntities`, `createEntity`, `updateEntity`, payload helpers, the `fillFromRegister` hook |
| `go/internal/web/properties/entities_test.go` | create | tests; `multipartPost` and `readEntity` are reused by 1523 and 1524 |
| `go/cmd/ubyhost-web/register_web_properties_entities.go` | create | `init()` calling `registerRoutes` |
| `go/internal/web/properties/i18n_keys.txt` | edit (append) | keys |
| `go/internal/web/properties/i18n.json` | edit (generated) | catalog |
| `docs/tasks/1522-go-properties-entity-save.md` | edit | `Status:` line only |
| `docs/tasks/1522-report.md` | create | report |

No other file may change.

## 4. Steps

1. Copy the new files:

```bash
mkdir -p go/internal/web/properties && cp docs/tasks/1522-files/go/internal/web/properties/entities.go.txt go/internal/web/properties/entities.go
mkdir -p go/internal/web/properties && cp docs/tasks/1522-files/go/internal/web/properties/entities_test.go.txt go/internal/web/properties/entities_test.go
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1522-files/go/cmd/ubyhost-web/register_web_properties_entities.go.txt go/cmd/ubyhost-web/register_web_properties_entities.go
```

2. Check them:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -12
5e5bbe4b4baaaeb63e40ab7d7666661ba76eee5ba99899143e08573fc9b03adc  go/internal/web/properties/entities.go
b0273f98ce28c17e5f8523db593d8d09a99c646518d2b11d07d3f600374570d1  go/internal/web/properties/entities_test.go
cf18945aa1e9e04ed21434145c8549de512acf087b263d98ebbf8efdee4aa4ca  go/cmd/ubyhost-web/register_web_properties_entities.go
SUMS
```

Expected: 3 lines ending `OK`.

3. Append the keys and regenerate the catalog:

```bash
printf '\n' >> go/internal/web/properties/i18n_keys.txt
cat docs/tasks/1522-files/i18n_keys_append.txt >> go/internal/web/properties/i18n_keys.txt
cd App && .venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import go_host_i18n as g
d = Path('../go/internal/web/properties')
(d / 'i18n.json').write_text(g.render(g.read_keys(d / 'i18n_keys.txt')), encoding='utf-8')
" && cd .. && sha256sum go/internal/web/properties/i18n.json
```

Expected: `6c71ed7c4bfbd28d1e3b25f48985d8ac7586df9c2b1f44a948210c2e52fd5756  go/internal/web/properties/i18n.json`. Commit: `git add go && git commit -q -m "1522 step 3: files and catalog" && git show --stat HEAD | tail -10`.

4. Run §6, write the report, set `Status: review`, commit `1522 step 4`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `App/tests/conftest.py`, every file under `App/app/`, `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere (deploy files, env docs, tests). Do not edit the sidecar files, `go.mod` or `go.sum`; no `go get`, no `go mod tidy`.
- Hard rules 2, 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge; no branch, no PR.

## 6. Commands

From the repo root. The Go tests need PostgreSQL: `export UBYHOST_TEST_DATABASE_URL=postgresql://...` as the owner's environment gives (unset means the database tests skip, which is a stop (§8), not a pass).

```bash
cd go && test -z "$(gofmt -l .)" && go build ./... && go vet ./internal/web/properties/ ./cmd/... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -40
```

Expected: no `SKIP`; `--- PASS` for `TestNormaliseAccount`, `TestInvoiceDetailPayload`, `TestWithCountryCode`, `TestDrawnSignature`, `TestEntitySave`, `TestEntitySignature`, `TestEntityUpdate` and the older tests; two `ok` lines.

```bash
python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3
git log --oneline --grep='^1522 step' | tail -10
```

Expected: `context lint: OK`; one commit per step that changed a file.

## 7. Acceptance

- [ ] Step 2: 3 `OK`; step 3: the sha256 given there.
- [ ] gofmt, vet, build clean; the §6 tests ran and pass.
- [ ] `git log --oneline --grep='^1522 step'` and `git show --stat` touch only §3 paths.

## 8. Stop and ask

Stop, and write the report, if: a sidecar `sha256sum` or `git apply --check` fails; an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1522-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of the `1522 step` commits), each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/entities.go`: the ownership lookup in `updateEntity` (`entityOwnedRowSQL` keeps `owner_user_id IS NOT DISTINCT FROM`), `resolveControllerAlerts`, `signaturePayload` (encryption, size and type limits), `updateSQL` (writes only posted columns).
- Nothing outbound, nothing deletes.

## Owner steps

1. Nothing to deploy yet. Do not add `/entities` to `UBYHOST_GO_PATHS` until briefs 1523, 1524 and 1525 are done (see §2).
