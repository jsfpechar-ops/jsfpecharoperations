# 1523: Go port of the business editor (GET /entities?edit=N) and "Fill from register" (ARES)

Status: todo
Depends on: 1522 | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** The owner wants one big pull request. You work on the current branch: commit `1523 step k` after each step that changes a file, never create a branch, never push, never open a PR. The orchestrator merges. Acceptance below does not depend on a base commit: it uses `git log --oneline --grep='^1523 step'` and `git show --stat` on those commits.

## 1. Objective

Serve the open business editor of `/entities?edit=N` on Go (Business details and Invoice details forms, linked properties) and make the "Fill from register" button of both forms work: look the IČO up in ARES, fill the blank name, seat and DIČ, render the page again. This replaces the 501 of brief 1302 for `?edit=N` and the hook of brief 1522.

## 2. Context

Sidecar `docs/tasks/1523-files/`; copy, check, test. **Do not open the files.**

| Part | Python | Parity |
|---|---|---|
| editor page | `entities` admin.py 858-870, `_entities_page` 903-949, `_entity_linked_properties` 886-895, `templates/entities.html` 20-75, `_entity_business_fields.html`, `_entity_invoice_fields.html`, `_account_parts.html`, `invoices.invoice_bank_view` invoices.py 492-500, `payments.czech_account_parts` 36-53, `payments.bic_for_account` 82-95 (+ `App/app/data/bank_codes.csv`), `contact_phone.form_parts` | an id that is not the host's (or past int64) opens no editor and shows the list; an archived business shows Business details only; the open row has `row-selected`; the stored values, the linked properties and the stored invoice defaults fill the forms. **The Python-made golden of the existing list test now also covers this page** (case `entities_edit_not_ported`, 678 items) |
| Fill from register | `_entities_ares_rerender` 1108-1139, `_entity_form_values` 1059-1085, `invoices.register_lookup` 766-780, `register_filled_note` 782-788, `ares.py` (all), `rate_limit.blocked/record` | typed values win, blank name/seat/DIČ are filled from ARES, the page is rendered with status 200 and nothing is saved; 20 lookups an hour per owner (`rate_limit_event`), then `ares.rate_limited`; an invalid IČO gives `ares.failure` without charging the limit; 24 h in-memory cache, a 404 is cached, other failures are not |

**Existing files that change (exact patch, `git apply`):** `lists.go` (struct `entitiesData` gets `Editor` and `NewForm`; the `?edit=` 501 branch now only answers 501 for a non-ASCII digit string; the handler builds the data and calls `renderEntities`; the unused `strings` import goes), `templates/lists.tmpl` (the editor template is included after the banner, `row-selected` on the open row, the add form body is the shared `entities.business_body`), `testdata/lists_cases.json` (the case `entities_edit_not_ported` loses `"go": 501`, so it is now compared with Python's output) and `lists_test.go` (`want 3` becomes `want 2` not-ported cases). **Exception to "new test files only":** these two test files encode the old gap and must change with it; the change only removes the 501 expectation. What changes for live traffic: `GET /entities?edit=N` answers 200 with the editor instead of 501; `GET /entities` without `edit` renders the same page as before (the existing golden test proves it).

**New outbound request: PR text (hard rule 2).** "Fill from register" sends one HTTPS GET to `https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/<IČO>` with `User-Agent: UbyHost`, a 4 s timeout, on the host's click only, with the host's own typed IČO and no other data. This is exactly `ares.py` today. Reason: the host asks the public business register to fill the business details. Tests use a local server (`aresURL` is a variable); the real register is never called. Owner note: the Go container needs outbound HTTPS to `ares.gov.cz` (it already reaches other hosts for iCal and Stripe).

**Layout-shell gap (not worked around).** `entities.html` also includes `_host_alerts.html` in its body. Go's layout builds the alert stack only for non-v2 pages, so `GET /entities` still answers 501 when the workspace has an open alert (brief 1525, blocked). This brief keeps that branch.

**Paths.** `/entities` becomes fully served only when brief 1525 is done. `/entities/{id}` (POST) is served by 1522, `/entities/{id}/invoice` by 1524.

Rules: hard rules 2, 3, 5, 8.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/ares.go` | create | ARES client, mapping, cache, rate limit, `registerLookup` |
| `go/internal/web/properties/entity_editor.go` | create | editor data, `openEditor`, `renderEntities`, the real `fillFromRegister`, bank and phone helpers |
| `go/internal/web/properties/templates/entity_editor.tmpl` | create | editor card, business body, invoice fields |
| `go/internal/web/properties/entity_editor_test.go` | create | tests (a local ARES server) |
| `go/internal/web/properties/bank_codes.csv` | create | copy of `App/app/data/bank_codes.csv` (ČNB bank codes; public data) |
| `go/internal/web/properties/lists.go` | edit (patch) | see §2 |
| `go/internal/web/properties/templates/lists.tmpl` | edit (patch) | see §2 |
| `go/internal/web/properties/testdata/lists_cases.json` | edit (patch) | see §2 |
| `go/internal/web/properties/lists_test.go` | edit (patch) | see §2 |
| `go/internal/web/properties/i18n_keys.txt` | edit (append) | keys |
| `go/internal/web/properties/i18n.json` | edit (generated) | catalog |
| `docs/tasks/1523-go-properties-entity-editor.md` | edit | `Status:` line only |
| `docs/tasks/1523-report.md` | create | report |

No other file may change.

## 4. Steps

1. Copy the new files and the data file:

```bash
mkdir -p go/internal/web/properties && cp docs/tasks/1523-files/go/internal/web/properties/ares.go.txt go/internal/web/properties/ares.go
mkdir -p go/internal/web/properties && cp docs/tasks/1523-files/go/internal/web/properties/entity_editor.go.txt go/internal/web/properties/entity_editor.go
mkdir -p go/internal/web/properties/templates && cp docs/tasks/1523-files/go/internal/web/properties/templates/entity_editor.tmpl.txt go/internal/web/properties/templates/entity_editor.tmpl
mkdir -p go/internal/web/properties && cp docs/tasks/1523-files/go/internal/web/properties/entity_editor_test.go.txt go/internal/web/properties/entity_editor_test.go
```
```bash
cp App/app/data/bank_codes.csv go/internal/web/properties/bank_codes.csv
```

2. Check them:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -12
d207a0fdcec0e92681400dab9f67702421efd69cc19078a7e7dc968d356fb13c  go/internal/web/properties/ares.go
4501a1ac032a13a11fbe8c449611dc449e697fd2855ce94e25b4f894422649a9  go/internal/web/properties/entity_editor.go
10c8a37f3f340721b6854b696f4c12eb3f55f6590b328add6b66eaeb698752a6  go/internal/web/properties/templates/entity_editor.tmpl
d01c38bee557ec732fd1358c6b98f0d6caaba15edab183d8c575af27e1352097  go/internal/web/properties/entity_editor_test.go
SUMS
```
```bash
sha256sum -c <<'SUMS' 2>&1 | tail -3
28d02ec1afe8a1d2a6e62c8e01fa3fb09b6d070137a9ddaa636158db41001835  go/internal/web/properties/bank_codes.csv
59bea876c1b2dc7f38d1cbc0aac8a275faf36d9c73f274d05b9821dfb933b70f  docs/tasks/1523-files/lists.patch.txt
SUMS
```

Expected: 6 lines ending `OK`.

3. Apply the patch to the four existing files (check first):

```bash
git apply --check docs/tasks/1523-files/lists.patch.txt && git apply docs/tasks/1523-files/lists.patch.txt && git diff --stat | tail -6
```

Expected: 4 files changed. A `--check` failure means an anchor moved: stop (§8).

4. Append the keys and regenerate the catalog:

```bash
printf '\n' >> go/internal/web/properties/i18n_keys.txt
cat docs/tasks/1523-files/i18n_keys_append.txt >> go/internal/web/properties/i18n_keys.txt
cd App && .venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import go_host_i18n as g
d = Path('../go/internal/web/properties')
(d / 'i18n.json').write_text(g.render(g.read_keys(d / 'i18n_keys.txt')), encoding='utf-8')
" && cd .. && sha256sum go/internal/web/properties/i18n.json
```

Expected: `a5079e6b0856bc96d09d4fa39e1159a97e2838dbb45fe507707fc5e88f21afa6  go/internal/web/properties/i18n.json`. Commit: `git add go && git commit -q -m "1523 step 4: editor, ARES, catalog" && git show --stat HEAD | tail -16`.

5. Run §6, write the report, set `Status: review`, commit `1523 step 5`.

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

Expected: no `SKIP`; `--- PASS` for `TestListsMatchPython` (now with the editor case), `TestMapAres`, `TestAresLookup`, `TestRegisterLookupLimit`, `TestBankAndPhoneParts`, `TestEntityEditorPage`, `TestFillFromRegister` and all older tests; two `ok` lines.

```bash
python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3
git log --oneline --grep='^1523 step' | tail -10
```

Expected: `context lint: OK`; one commit per step that changed a file.

## 7. Acceptance

- [ ] Step 2: 6 `OK`; step 3: 4 files changed; step 4: the sha256 given there.
- [ ] gofmt, vet, build clean; the §6 tests ran and pass; `TestListsMatchPython` passes without the 501 case.
- [ ] `git log --oneline --grep='^1523 step'` and `git show --stat` touch only §3 paths.
- [ ] Screenshots (rule 7, rule 10, host page): the executor cannot run the Go service; the reviewer takes the 390/768/1280 px screenshots of `/entities?edit=<id>` after staging and writes what they saw (owner step 2).

## 8. Stop and ask

Stop, and write the report, if: a sidecar `sha256sum` or `git apply --check` fails; an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1523-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of the `1523 step` commits), each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/lists.go` and `go/internal/web/properties/templates/lists.tmpl` (live code; the patch).
- `go/internal/web/properties/ares.go` (the outbound request: only the IČO is sent; limit and cache), `go/internal/web/properties/entity_editor.go` (`loadEntityFull` keeps `owner_user_id IS NOT DISTINCT FROM`; `fillFromRegisterAnswer` loads the entity of this host only and saves nothing).

## Owner steps

1. Nothing to deploy yet (paths not switched).
2. On staging with `/entities` in `UBYHOST_GO_PATHS`: open a business, press Fill from register with a real IČO, check the flash text and the three screenshots. Confirm the container reaches `ares.gov.cz`.
