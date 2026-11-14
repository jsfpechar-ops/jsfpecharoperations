# 1580: Go stay-fee hlášení PDF renderer (`go/internal/stayfeepdf`) and its wiring into the stay_fee_mail job

Status: review
Depends on: 1220, 1240, 1241, 1242 | Base commit: current tip of the working branch | Branch: task/1580-go-stay-fee-hlaseni-pdf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1580 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1580 step'` and `git show --stat <commit>`, never a fixed base commit.

## 1. Objective

Port the hlášení PDF renderer (`App/app/stay_fee_remittance_pdf.py`, `render`) to Go as `stayfee.PDFRenderer` in the new package `go/internal/stayfeepdf`, and set `stayFeeRenderer` in `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` so the registered `stay_fee_mail` job has a renderer. Brief 1243 (which the old comments name) was never written; this brief replaces it. Nothing is switched on.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the PDF carries the figures `stayfee.MakeHlaseni` computes and is not changed by this brief; 2 privacy: no new personal-data field, no outbound request; 3 fixtures are made up (`@example.test`); 4 no new dependency (gopdf and the DejaVu fonts are already used by `go/internal/pdf`; `image/png` and `image/jpeg` are standard library); 6 not applicable (no web page); 11 Go first: this is the Go port, no file under `App/` changes.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1580-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `0cb2636db98f1f421095b5cc661505aa434550cbaa02e909da3fd89b3c9c1e6f` | `go/internal/pdf/doc.go` | replace (original sha256 `674cc3afbe911f98355a6d18ee943ae9136211fef5fe7402c8f205a0afa87f1f`) | 338 |
| `6de7bff3222f07636440d12f208d26a5c79dec9df200478bfe52533739e1b0e4` | `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` | replace (original `f9bb9b89b053cb63391f336c6ca173377383fd67d1b0bc50332c0ba6f2dfcae4`) | 33 |
| `323eeb68977ab9cff76fc0378940ac46051814194a647be584a0b262f98db814` | `go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go` | replace (original `668dd0ec18741be3d22d1cc88756b9bb9463ee5786474d22e2c7870f57ea90de`) | 24 |
| `ef407069f5d51b70208c6eb3b1e5a9d29c3a00885fa88cb5e9091c759951b343` | `go/internal/stayfeepdf/render.go` | create | 510 |
| `ec8b7f74bbf0249a20968d7a40e964d6cd3b514685b5f51f4df32bc71ec80960` | `go/internal/stayfeepdf/render_test.go` | create | 150 |
| `eee97e836d6e72cd486698f88631a5d94fb69b7e99272cfcc77daa60aafac3fe` | `go/internal/stayfeepdf/testdata/gen_golden.py` | create | 199 |
| `14a9b944623f381891eaea8def4fa0c7657adb266974ddab86617c0a9978d287` | `go/internal/stayfeepdf/testdata/hlaseni_golden.json` | create | 6516 |

**How it is built.** `go/internal/pdf` draws a single page (`Doc.Bytes`). The hlášení can run to several pages, so `doc.go` gets two additions and `Bytes` becomes a thin call: `PagesBytes(docs ...*Doc)` replays one `Doc` per A4 page into one PDF, and `Mark()` returns the footer mark PNG. The invoice path is unchanged (`Bytes()` is `PagesBytes(d)`). `stayfeepdf.Layout(h, sample)` returns one `Doc` per page, and `Renderer{Sample bool}.Render(h)` is the `stayfee.PDFRenderer` (`Sample` is false in production; it only adds the "NÁHLED · UKÁZKOVÁ DATA" label for mockups, as Python's `sample=True`).

**Parity notes (Python `App/app/stay_fee_remittance_pdf.py` -> Go `go/internal/stayfeepdf/render.go`):**

| Python | Go |
|---|---|
| `validate` 78-113 | `Validate` (same error texts; the Python `isinstance int` checks are the Go types, a negative rate or count is refused) |
| `_text`, `_label`, `_rule`, `_card`, `_split`, `_wrap` | `page.text`, `page.label`, `page.rule`, `page.card`, `page.split`, `page.wrap` |
| `_date`, `period_phrase`, `_plural`, `_nights`, `_amount` | `czDate`, `PeriodPhrase`, `nights`, `amount` |
| `_footer`, `_page_top`, `_table_header`, `_row_height`, `_table_row`, `_summary`, `_signature`, `_signature_height` | `footer`, `pageTop`, `tableHeader`, `rowHeight`, `tableRow`, `summary`, `signature`, `signatureHeight` |
| `render` | `Layout` (pages) and `Renderer.Render` (bytes) |

**Python draws no QR payment code** (the SPAYD code is on the guest and Go stay-fee pages, not in this PDF), so none is drawn here. Page size A4, fonts DejaVu Sans regular and bold (the same files), file naming is not decided by the renderer (the caller names the file).

**Easy to get wrong, all tested against the Python golden:** the amount format is thousands separated by a plain space and ` Kč` (`1 234 Kč`, `-1 050 Kč`); Czech counted nouns (1 lůžkoden, 2 to 4 lůžkodny, 0 and 5+ lůžkodnů); `za srpen 2026` uses the nominative month; quarterly reports say `3. čtvrtletí 2026`; the payer name drops from 13 pt to 10 pt when it wraps to more than two lines and at most three lines are drawn; the recipient card grows with its text; a table row breaks the page when fewer than 55 mm are left; the summary and signature move to a continuation page when `need` does not fit; negative removal rows are allowed as long as the report total is not negative; the signature line uses the line width left by the last rule of the page (0.55; 1 on a page without a rule); the signature image is a PNG or JPEG in base64 (a `data:` prefix is cut at the first comma), scaled into 45 mm x 13 mm.

**Known differences from Python:** the PDF bytes are not identical to reportlab's (not required): gopdf writes the file, the Info dictionary has no creation date, and the Python page compression is not mirrored. The draw operations (every text with its font, size, colour and position, every rule, card and image) are identical within 0.01 pt. A signature image that is not valid base64 or not a PNG/JPEG makes `Render` return an error (Python raises too).

**Verification without Python in CI.** `testdata/hlaseni_golden.json` was made from the real Python renderer (reportlab 5.0.1) by `testdata/gen_golden.py`, which replaces the reportlab canvas with a recorder (same method as brief 1220). The Go test lays out the same seven cases (single row with a typed signature name, quarterly report with a PNG signature, exempt groups, payee and a long instruction, long wrapping names, 14 rows over two pages with the sample label, a zero period, a negative removal row, a refused report) and compares all operations. The executor does not run Python.

**Wiring.** `stayFeeRenderer` is now `stayfeepdf.Renderer{}` (type `stayfee.PDFRenderer`; keep this name and type, briefs 1585 and 1586 read it). The registered `stay_fee_mail` job can now run, but its job kind stays off: which process runs a kind is decided by `UBYHOST_GO_JOB_KINDS` and the queue kinds, and the owner steps are in brief 1589. The old test that expected `ErrNoRenderer` became `TestStayFeeMailHasRenderer` (interval 24 h, handler registered, renderer type, kind parses).

**Paths that become fully served by Go:** none (a library and a job renderer). **Goes live on deploy if** `stay_fee_mail` is already listed in `UBYHOST_GO_JOB_KINDS` (assumed not): the job would then seal due periods and mail reports; check the variable before the deploy.

**Verified by the brief writer** (in a throwaway worktree of go-wave3 with this brief's steps applied exactly and in order): `gofmt -l` printed nothing, `go build ./...` and `go vet ./internal/pdf/... ./internal/stayfeepdf/... ./cmd/...` were silent, and `go test ./internal/stayfeepdf ./internal/pdf ./internal/stayfee ./internal/stayfeemail ./cmd/ubyhost-web -count=1` passed on PostgreSQL 16, with the invoice golden test (`TestLayoutMatchesPythonOps` in `internal/pdf`) still green. Skipped tests: 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/pdf/doc.go` | replace | `PagesBytes`, `Mark`; `Bytes` calls `PagesBytes` |
| `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` | replace | `stayFeeRenderer = stayfeepdf.Renderer{}`, comments |
| `go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go` | replace | renderer test |
| `go/internal/stayfeepdf/render.go` | create | the renderer |
| `go/internal/stayfeepdf/render_test.go` | create | golden test against Python |
| `go/internal/stayfeepdf/testdata/gen_golden.py` | create | golden generator (never run by CI) |
| `go/internal/stayfeepdf/testdata/hlaseni_golden.json` | create | golden from Python |
| `docs/tasks/1580-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1580-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/stayfee/report.go go/internal/stayfeemail/job.go go/internal/pdf/invoice.go 2>&1 | tail -3` lists all three.
   - `grep -cF "Render(h Hlaseni) ([]byte, error)" go/internal/stayfee/save.go | tail -1` prints `1`.
   - `grep -cF "func (d *Doc) Bytes() ([]byte, error) {" go/internal/pdf/doc.go | tail -1` prints `1`.
   - `sha256sum go/internal/pdf/doc.go go/cmd/ubyhost-web/register_job_stay_fee_mail.go go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go | tail -3` prints the three "original" hashes of the table in §2 (`674cc3af...`, `f9bb9b89...`, `668dd0ec...`).
   - `ls go/internal/stayfeepdf 2>&1 | tail -1` says "No such file" (nothing of this brief exists yet).
   - `find docs/tasks/1580-files -name '*.txt' | wc -l | tail -1` prints `7`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1580-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -9
   0cb2636db98f1f421095b5cc661505aa434550cbaa02e909da3fd89b3c9c1e6f  go/internal/pdf/doc.go
   6de7bff3222f07636440d12f208d26a5c79dec9df200478bfe52533739e1b0e4  go/cmd/ubyhost-web/register_job_stay_fee_mail.go
   323eeb68977ab9cff76fc0378940ac46051814194a647be584a0b262f98db814  go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go
   ef407069f5d51b70208c6eb3b1e5a9d29c3a00885fa88cb5e9091c759951b343  go/internal/stayfeepdf/render.go
   ec8b7f74bbf0249a20968d7a40e964d6cd3b514685b5f51f4df32bc71ec80960  go/internal/stayfeepdf/render_test.go
   eee97e836d6e72cd486698f88631a5d94fb69b7e99272cfcc77daa60aafac3fe  go/internal/stayfeepdf/testdata/gen_golden.py
   14a9b944623f381891eaea8def4fa0c7657adb266974ddab86617c0a9978d287  go/internal/stayfeepdf/testdata/hlaseni_golden.json
   EOF
   ```

   Every line must end with `: OK`. Then commit "1580 step 1".

2. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/pdf internal/stayfeepdf cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/pdf/... ./internal/stayfeepdf/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it already runs (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55580/data status' | tail -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55580 && chown postgres /var/tmp/pg55580 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55580/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55580/data -o "-p 55580 -k /var/tmp/pg55580" -l /var/tmp/pg55580/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Then use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55580/postgres`. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run only the commands of step 4 that need no database (the `stayfeepdf` and `pdf` tests need none), and STOP before the other packages.

4. Run the tests (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55580/postgres go test ./internal/stayfeepdf ./internal/pdf ./internal/stayfee ./internal/stayfeemail ./cmd/ubyhost-web -count=1 2>&1 | tail -30
   ```

   Expected: five `ok` lines (the five packages), no `FAIL`. Then show that the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55580/postgres go test ./internal/stayfeepdf ./internal/pdf ./cmd/ubyhost-web -count=1 -v -run '^TestLayoutMatchesPythonOps$|^TestRenderIsPDFAndDeterministic$|^TestMultiPageHasTwoPages$|^TestAmountAndNights$|^TestStayFeeMailHasRenderer$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: `--- PASS` for `TestLayoutMatchesPythonOps` (in `stayfeepdf` and in `pdf`, the invoice one), `TestRenderIsPDFAndDeterministic`, `TestMultiPageHasTwoPages`, `TestAmountAndNights`, `TestStayFeeMailHasRenderer`, then three `ok` lines. No `--- SKIP`, no `--- FAIL`. Report the SKIP count (0).

5. Write the report (§9), set `Status: review` in this file and commit "1580 step 5". Do not open a PR (one big PR mode).

## 5. Do not touch

`App/` (no Python file changes; `gen_golden.py` only reads it and the executor does not run it), `docs/ENVIRONMENT.md`, Caddy and compose files, `UBYHOST_GO_PATHS`, `UBYHOST_GO_JOB_KINDS`, and every other file of `go/internal/pdf` (only `doc.go` changes there). Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the data is made up), nothing pushed to `main`.

## 6. Commands

Exactly the commands of §4 (steps 2 and 4). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about the files of this brief).

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 7 files; the step 0 "original" hashes matched before.
- [ ] The format, build and vet step printed nothing.
- [ ] The test step printed `ok` for the five packages; the named tests printed `--- PASS` (none `SKIP`, none `FAIL`).
- [ ] `git log --oneline --grep='^1580 step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1580 step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS` or `UBYHOST_GO_JOB_KINDS`; no Caddy, compose, env or Python application file changed; nothing was pushed to `main`.
- [ ] UI: not applicable (no web page changes; the PDF is checked by the golden test).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated;
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1580-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has: 1. the files changed (`git diff --stat`), 2. each command with the last 5 lines of its output, 3. §7 ticked, 4. Deviations, 5. Questions, 6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `go/internal/pdf/doc.go` (only the `Bytes` split; the invoice golden test must stay green), `render.go` (`Validate` refuses before any drawing; the table and page-break arithmetic copies Python's), `register_job_stay_fee_mail.go` (the renderer is only a variable; no kind is switched on).

## Owner steps

None in this brief: nothing is switched on. Before the `stay_fee_mail` kind is added to `UBYHOST_GO_JOB_KINDS`, follow the owner steps of brief 1589 (Python and Go must not both run the job). To look at a PDF once, brief 1589 or the finalize brief (1585) produces a real one; the layout is covered here by the golden test only, so a visual check of one real hlášení (all pages, signature) is still open.
