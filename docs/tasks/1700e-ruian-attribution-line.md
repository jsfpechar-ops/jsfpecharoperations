# 1700e: RÚIAN credit line on the legal page

Status: done — executed and reviewed 2026-11-17 (390 px checked; margin fix in 1700e-fix-1)
Depends on: 1700c (`go/internal/ruian/attribution.go` exists on this branch; verified at 5aa4d42) | Base commit: current tip of the working branch | Branch: task/1700e-ruian-attribution-line
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: C (Sonnet wrote the exact-diff pass; the orchestrator reads the risk-listed files).

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700e step k` (`k` is the step number) using explicit `git add <paths>`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1700e step'`, never a fixed base commit.

## 1. Objective

The ČÚZK address data (CC BY 4.0) needs a credit. Show `ruian.Attribution` ("Adresní data: ČÚZK, RÚIAN (CC BY 4.0)") once, on the public legal notice `/legal`, the only public page that is about the product itself rather than about personal data or contracts. One place only (rule 9): the suggest list and `ruian_suggest.js` stay unchanged. The line is a data-source name and a licence, so it is the same text in Czech and English (no catalog key). Plan: [ruian-local](../plans/ruian-local.md) §4 and Q4.

## 2. Context

Settled from the code (nothing for the owner to decide):

- `/legal` is rendered by Go (`go/internal/web/public/`, template `templates/legal.tmpl`, brief 1270). Python (`App/app/templates/legal.html`) still serves the same path in production until the path switch, so it gets the same panel; this is port plumbing ([go-first](../context/go-first.md) item 1: the parity test `App/tests/test_go_public_legal.py` regenerates the Go golden pages from the Python page and fails when the two differ). No owner switch is needed: the credit shows on both stacks.
- The Go page is a `page` struct plus text/template. Every printed value must go through the escaping methods (`TestEveryActionEscapes`); the credit is printed with `{{.E .Attribution}}`. `Attribution` is set only for `/legal`, from the one constant `ruian.Attribution`.
- The four legal golden pages (`legal-cs`, `legal-en`, `legal-posthog`, `legal-no-dic-email`) are normalized one-line HTML; each gets the same inserted panel by hand-written text (no Python golden script is run).
- Python carries the credit as a literal in `legal.html`. No new Python test (Go-only tests for this brief): the text cannot drift because the existing parity test `App/tests/test_go_public_legal.py` compares the Go golden pages with the Python page, and the Go test `legal_attribution_test.go` pins `ruian.Attribution` in the goldens.
- Privacy (rule 2): no personal data, no new request, no cookie. Dependency (rule 4): none (`ruian` is in the same Go module).

Sidecar (one new Go test file), copied unchanged in step 1:

| sha256 | file | action | lines |
|---|---|---|---|
| `2a2edd2a9dda7d992feeebe8d230dd56586acc5e7c23792cced0ac0e3f18ac46` | `go/internal/web/public/legal_attribution_test.go` | create | 34 |

(The hashes are of the sidecar files `docs/tasks/1700e-files/<repo path>.txt`; after step 1 the copies must have the same hashes.)

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/public/page.go` | edit | import `ruian`, field `Attribution`, set for `/legal` |
| `go/internal/web/public/templates/legal.tmpl` | edit | one panel before the disclaimer panel |
| `go/internal/web/public/testdata/legal-cs.html`, `legal-en.html`, `legal-posthog.html`, `legal-no-dic-email.html` | edit | the same panel, by `sed` |
| `go/internal/web/public/legal_attribution_test.go` | create | credit once on `/legal`, none elsewhere |
| `App/app/templates/legal.html` | edit | the same panel (Python still serves `/legal`) |
| `docs/tasks/1700e-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1700e-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `grep -cF 'const Attribution = "Adresní data: ČÚZK, RÚIAN (CC BY 4.0)"' go/internal/ruian/attribution.go | tail -1` prints `1`.
   - `grep -cF 'p.Prefix = "legal"' go/internal/web/public/page.go | tail -1` prints `1`.
   - `grep -cF '<h2 style="margin-top:0">{{.T "legal.disclaimer_title"}}</h2>' go/internal/web/public/templates/legal.tmpl | tail -1` prints `1`.
   - `grep -cF "<h2 style=\"margin-top:0\">{{ t('legal.disclaimer_title') }}</h2>" App/app/templates/legal.html | tail -1` prints `1`.
   - `for f in cs en posthog no-dic-email; do grep -o '<div class="panel quiet"><h2 style="margin-top:0">' go/internal/web/public/testdata/legal-$f.html | wc -l; done | tr '\n' ' ' | tail -1` prints `1 1 1 1`.
   - `grep -c 'ČÚZK' go/internal/web/public/testdata/legal-cs.html App/app/templates/legal.html | tail -2` prints `0` for both.
   - `find docs/tasks/1700e-files -name '*.txt' | wc -l | tail -1` prints `1`.

1. Copy the sidecar and check it (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700e-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -5
   2a2edd2a9dda7d992feeebe8d230dd56586acc5e7c23792cced0ac0e3f18ac46  go/internal/web/public/legal_attribution_test.go
   EOF2
   ```

   The line must end with `: OK`. Do not commit yet (the Go test fails until step 2 to 4 are done).

2. Go page data. In `go/internal/web/public/page.go` make three edits (use the Edit tool, each `old` text occurs once):

   a. import block, replace
   ```
   	"unicode"
   	"unicode/utf8"
   )
   ```
   with
   ```
   	"unicode"
   	"unicode/utf8"

   	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
   )
   ```
   b. struct `page`, replace the line
   ```
   	Prefix                string   // "terms", "privacy" or "dpa"
   ```
   with
   ```
   	Prefix                string   // "terms", "privacy" or "dpa"
   	Attribution           string   // /legal only: the ČÚZK credit line (brief 1700e)
   ```
   c. in `newPage`, replace
   ```
   	case "/legal":
   		p.Prefix = "legal"
   ```
   with
   ```
   	case "/legal":
   		p.Prefix = "legal"
   		p.Attribution = ruian.Attribution
   ```
   Then run `cd go && gofmt -l internal/web/public | tail -5` (must print nothing; if it lists `page.go`, run `gofmt -w internal/web/public/page.go`).

3. Go template. In `go/internal/web/public/templates/legal.tmpl` replace
   ```
   <div class="panel quiet">
     <h2 style="margin-top:0">{{.T "legal.disclaimer_title"}}</h2>
   ```
   with
   ```
   <div class="panel quiet">
     <p class="small muted" style="margin-bottom:0">{{.E .Attribution}}</p>
   </div>
   <div class="panel quiet">
     <h2 style="margin-top:0">{{.T "legal.disclaimer_title"}}</h2>
   ```
   (two-space indent on the `<p>` and `<h2>` lines, as the file has.)

4. Golden pages (one call, repo root):

   ```bash
   for f in cs en posthog no-dic-email; do sed -i 's|<div class="panel quiet"><h2 style="margin-top:0">|<div class="panel quiet"><p class="small muted" style="margin-bottom:0">Adresní data: ČÚZK, RÚIAN (CC BY 4.0)</p></div>&|' go/internal/web/public/testdata/legal-$f.html; done; grep -c 'Adresní data: ČÚZK, RÚIAN (CC BY 4.0)' go/internal/web/public/testdata/legal-*.html | tail -4
   ```

   Expected: four lines, each ending `:1`. Then run the Go tests (step 6) before committing step 2 to 4 together: `git add go/internal/web/public/page.go go/internal/web/public/templates/legal.tmpl go/internal/web/public/testdata go/internal/web/public/legal_attribution_test.go && git commit -m "1700e step 4" | tail -3`.

5. Python page. In `App/app/templates/legal.html` replace
   ```
   <div class="panel quiet">
     <h2 style="margin-top:0">{{ t('legal.disclaimer_title') }}</h2>
   ```
   with
   ```
   <div class="panel quiet">
     <p class="small muted" style="margin-bottom:0">Adresní data: ČÚZK, RÚIAN (CC BY 4.0)</p>
   </div>

   <div class="panel quiet">
     <h2 style="margin-top:0">{{ t('legal.disclaimer_title') }}</h2>
   ```
   Commit: `git add App/app/templates/legal.html && git commit -m "1700e step 5" | tail -3`.

6. Go tests, format, vet (one call, repo root; the commit of step 4 comes after this passes):

   ```bash
   cd go && gofmt -l internal/web/public | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/public/ 2>&1 | tail -30; go test ./internal/web/public/ ./internal/ruian/ -run 'TestGoldenPages|TestLegalShowsRuianCreditOnce|TestEveryActionEscapes|TestHeadHasNoBody|Test[A-Z]' -v 2>&1 | grep -c -- '--- PASS' | tail -1; go test ./internal/web/public/ -run 'TestGoldenPages|TestLegalShowsRuianCreditOnce|TestEveryActionEscapes|TestHeadHasNoBody' -v 2>&1 | grep -- '--- FAIL\|--- SKIP\|^ok\|^FAIL' | tail -10
   ```

   Expected: gofmt, build and vet print nothing; the last command prints only `ok  	github.com/.../go/internal/web/public` (no FAIL, no SKIP). The count line is informational (about 40).

7. Python tests (existing files only, no new test; they run in CI; locally only if `App/.venv` exists):

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_public_legal.py tests/test_legal_contents.py tests/test_legal_registry.py tests/test_public_chrome.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: all pass. `test_go_public_legal.py` is the check that the hand-written golden edit equals what Python renders; if it names a stale file, STOP (§8). No `App/.venv`: write "Python: CI" in the report and still finish.

8. Screenshot (rule 7), one 390 px page: in `go/`, run `PUBLIC_LEGAL_SHOTS_ADDR=127.0.0.1:18700 go test ./internal/web/public/ -run TestServeForScreenshots -count=1 > /dev/null 2>&1 &`, take a 390 px wide screenshot of `http://127.0.0.1:18700/legal?lang=cs` with the Playwright set-up of the repo (`App/.venv`), open it and check: the credit is one muted line in its own quiet panel between the DPA panel and the Disclaimer panel, nothing overflows sideways. Stop the server (`kill %1`). Put one sentence on what you saw in the report; no screenshot, no Playwright: say so in the report and finish (the owner item, §9).

## 5. Do not touch

`go/internal/ruian/`, `go/internal/web/public/catalog.json` and the other testdata (generated by `App/scripts/public_legal_golden.py`; do not run it or edit the catalog), the other templates, `UBYHOST_GO_PATHS`, Caddy and compose files, every Python file except `App/app/templates/legal.html`, `go/internal/web/properties/` and `go/cmd/ubyhost-web/` (brief 1701 owns them), `ruian_suggest.js`.

## 6. Commands

Exactly the commands of §4 (steps 6, 7, 8). Test-map row "Public pages, legal, landing" (`test_legal_*.py`, `test_public_*.py`) is covered by step 7; the Go side has no row yet, the coordinator adds `go test ./internal/web/public/` to the row.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK`.
- [ ] `gofmt -l`, `go build ./...` and `go vet` of step 6 printed nothing; the Go test run printed `ok` only, 0 FAIL, 0 SKIP.
- [ ] Step 7: pass lines, or "Python: CI" in the report.
- [ ] `grep -c 'Adresní data: ČÚZK, RÚIAN (CC BY 4.0)' go/internal/web/public/testdata/legal-cs.html App/app/templates/legal.html | tail -2` prints `1` for both, and the string appears in no other file under `go/internal/web/public/` except `legal_attribution_test.go` and the other three legal goldens.
- [ ] `git log --oneline --grep='^1700e step' | tail -5` lists the step commits and `git show --stat --format=%s $(git log --format=%h --grep='^1700e step') | tail -30` lists only the paths of §3.
- [ ] UI: public page changed; one 390 px screenshot described in the report (or "no browser, owner item"). The host-page UX gate (rule 10) does not apply: `/legal` is a public page.
- [ ] Nothing pushed, no Caddy, compose, env or `go/internal/ruian/` change.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report), or `test_go_public_legal.py` names a stale file;
- you reach 30 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1700e-report.md` (400 tokens at most) and set this brief's `Status: review`. It has: the files changed (`git show --stat`), each command with the last 5 lines of its output and the SKIP count, §7 ticked, the step 8 sentence, deviations, questions.

## Risk list (for the reviewer)

`legal.tmpl` and `page.go` (the credit is printed with `{{.E .Attribution}}`, set only for `/legal`, from `ruian.Attribution`); the Python panel text equals the Go constant (kept in line by `test_go_public_legal.py` and `legal_attribution_test.go`, no new Python test). No query, no form, no owner scoping, no `_csrf` is involved. Copy: no heading, so no sentence repeats what the line says (rule 9).

## Owner steps

None. The credit shows on Python and on Go with no switch. Rollback: revert the commits.
