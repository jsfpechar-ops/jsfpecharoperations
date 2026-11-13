# 1242: Go `stay_fee_mail` job (seal, mails, no-pay-way sweep), switched off until a PDF renderer exists, parity-checked against Python

Status: todo
Depends on: 1240, 1241 (both on this branch) | Base commit: 969a383 | Branch: claude/1240-go-stay-fee-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the rest of the Go port of the daily Python job `stay_fee_mail` except the PDF layout: the write side of the stay fee (`Save`, `Confirm`, adjustment add and reverse) in `go/internal/stayfee`, the job itself (`DueMonth`, `Run`, the two host mails, the no-pay-way alert sweep, `Handler`) in `go/internal/stayfeemail`, and the registration of the kind. Until brief 1243 plugs in a real PDF renderer the handler fails at once with `stayfeemail.ErrNoRenderer`, before it reads or writes anything, so putting `stay_fee_mail` in `UBYHOST_GO_JOB_KINDS` early only raises the job_failed alert: no seal, no mail.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: `Save` writes the sealed hlášení the host sends to the town, so parity with `stay_fee_filing.save` is the point; 2 privacy: no new personal-data field and no outbound request (mail is queued into `email_outbox` as Python does; the sender is unchanged); the golden holds invented data only (`example.test`) and no Fernet token; 3 nothing real in the repo; 4 no new dependency (pgx, the repo's `secure`, `deadlines`, `hostweb`, `ubyport`, `jobs`; `go mod tidy -diff` stays empty); 5 SQL with Postgres placeholders, no schema change.

**The code is in a separate file.** The eight files are too long for a brief under the lint cap, so they sit as fenced blocks 1 to 8 in `docs/tasks/1242a-go-stay-fee-job-code.md` (four-backtick fences). **Do not read that file**: the helper in step 0 copies each block byte for byte and checks its sha256 before it writes anything.

**What the code does** (Python at 969a383 is the source):
- `stayfee.Save(ctx, db DB, deps SaveDeps, ap *Apartment, a SaveArgs) (int64, error)` is `stay_fee_filing.save`: figures read before the transaction; in the transaction `pg_advisory_xact_lock(hashtext('stay_fee_filing'), apartment id)` (the form of `db.lock_key` on PostgreSQL, so Go and Python contend on the same lock), supersede `ReplacingID` or refuse an overlapping live filing, next version, INSERT with `pdf_enc`/`csv_enc` as the bytes of a Fernet token (`db.encrypt_blob`) and `payload_enc` the token of `json.dumps(payload, sort_keys=True)` (`PyJSONSorted`: ASCII escapes, `", "`/`": "`), then link the open adjustments. Errors `ErrInactive`, `ErrOverlap`, `ErrChanged` (Python's three `ValueError`s) and `ErrDuplicate` (unique violation). `PDFRenderer interface{ Render(h Hlaseni) ([]byte, error) }` is passed in `SaveDeps`; `FernetEncrypter` uses the first data key, as Python's `MultiFernet.encrypt`.
- `stayfee.Confirm(ctx, db, deps, ap, month, today, ConfirmOpts) (int64, error)` is `stay_fee_auto.confirm`: 0 when blocked, already sealed, or refused (the four errors or any class-23 integrity error), else the id plus the audit row `stay_fee_auto_finalize` (actor `host`, detail `apartment_id=N period=KEY`).
- `stayfee.AddAdjustment(ctx, db, enc, AdjustmentInput, now) (int64, error)` and `ReverseAdjustment(ctx, db, id, actorID, now) error` port `stay_fee_adjustment.add`/`reverse` (Python writes no audit row there). `RecentLive` is the job's "live filings created since cutoff" query (`ORDER BY id` added; Python has none).
- `stayfeemail`: `DueMonth(cadence, today) (time.Time, bool)`; `Run(ctx, pool, Deps) (Counts, error)` is `stay_fee_auto.run`/`_run_apartment` (hosts with role host, no `deletion_due_at`, not opted out; unarchived apartments; inactive and demo apartments skipped, `demo.is_demo_apartment` ported; Prague today from `deadlines.LocalNow`; cutoff now minus 3 days; per-apartment errors logged and skipped); `queueReport`/`queueBlocked` port `queue_stay_fee_report`/`queue_stay_fee_blocked` with the same keys (`stay_fee_report:<apt>:<period>:v<version>`, `stay_fee_blocked:<apt>:<period>`), kinds, subjects and payload JSON (`text`, `html`, `lang`, `stay_fee_filing_id`, `qr_spayd`), gated like `mail.enqueue` (`UBYHOST_MAIL_BACKEND` console or ses) and written with `ubyport.EnqueueMail`; `ReconcileNoPayWay`/`ReconcileAllNoPayWay` port the alert sweep with `ubyport.RaiseAlert`/`ResolveAlert` (key `stay_fee_no_pay_way:<apt>`, same copy and params). `Handler(pool, Deps)` is `scheduler._job_stay_fee_mail`: `ErrNoRenderer` first, then Run, then the sweep (its error only logged); it returns confirmed + reports + blocked.
- `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` calls `registerJob("stay_fee_mail", 24*60, stayFeeMailJob)` from `init()`; `stayFeeRenderer` is a nil `stayfee.PDFRenderer` var that brief 1243 sets. The factory does not touch the pool.

**Python behaviour kept on purpose:** `mail.enqueue` returns the existing row's id for a known key, so a repeated run counts the same reports and blocked mails again (counts are not "new mails"); the report goes only to the legal entity's `contact_email`, never a login; a blocked mail goes only when `confirm` failed because of issues (a refused save with no issues sends nothing).

**Parity.** `App/scripts/stay_fee_job_golden.py` seeds a throwaway SQLite database (5 users, 4 legal entities, 13 apartments, 11 reservations, 12 guests, 2 adjustments, 3 filings, 1 outbox row, 1 alert), patches `db.utcnow` and the job clock to fixed values and `stay_fee_remittance_pdf.render` to fixed bytes that record their input, and runs the real job three times (2026-10-05, the same day again, 2026-10-20 after one `UPDATE`), then direct writes (adjustment add and reverse, a correction with `replacing_id`, and the `filing changed`, `overlaps saved period` and `inactive property` refusals), plus `due_month` for every day of 2026 in both cadences. It writes `go/internal/stayfeemail/testdata/stay_fee_job_golden.json` (3123 lines). Covered: clean monthly seal with QR, blocked mail (no VS, unsigned), already sealed, out-of-window day, quarterly, opted-out host, deletion-due host, admin user, archived, demo by name and by entity, report re-send for a new version, zero-total report, no contact email, no-pay-way alert raised and resolved (and a stale one resolved), a second run writing nothing new. `job_test.go` replays it on PostgreSQL (`TestJobGolden`: counts, sweep count, every PDF input, decrypted filings, adjustments, outbox rows with the payload byte for byte, alerts and audit rows); `TestRunNoRendererWritesNothing` (seeded database unchanged), `TestHandlerNeedsRenderer` and `TestDueMonthGolden` (no database). In cmd, `TestStayFeeMailNeedsRenderer` calls the registered handler with a nil pool.

**Verified by the brief writer** on the working tree of 969a383 (files created, tested, then deleted): `gofmt -l` empty, `go vet` clean, `go test ./internal/stayfee/ ./internal/stayfeemail/ ./cmd/ubyhost-web/` ok with a local PostgreSQL 16 (`UBYHOST_TEST_DATABASE_URL` set: `TestJobGolden` and `TestRunNoRendererWritesNothing` PASS), `go build ./...` ok, `go mod tidy -diff` empty, the golden generation deterministic (same sha twice), and a deliberate one-character change to the report key made `TestJobGolden` fail, so the comparison bites. Generated file hash: `go/internal/stayfeemail/testdata/stay_fee_job_golden.json` sha256 `d25e591636e4515daed201701fd573af0546b6fcca507a3a71ace70cddf03d25`. A different hash means the base differs: STOP.

Anchors that must exist verbatim (step 0, `grep -cF` prints 1 or more): App/app/stay_fee_auto.py `def run(`, `def due_month(`, `def confirm(`; App/app/stay_fee_filing.py `def save(`; App/app/stay_fee_adjustment.py `def reverse(`; App/app/mail_notify.py `def queue_stay_fee_blocked(`; App/app/stay_fee.py `def reconcile_all_no_pay_way(`; App/app/db.py `pg_advisory_xact_lock(hashtext(?), ?)`; go/internal/ubyport/notify.go `func EnqueueMail(`; go/internal/ubyport/effects.go `func RaiseAlert(`; go/internal/stayfee/loader.go `const ApartmentSelect = apartmentSelect`; go/internal/stayfeemail/stay_fee_mail.go `func BuildStayFeeReport(`; go/cmd/ubyhost-web/registry.go `func registerJob(`; go/internal/jobs/queue.go `"stay_fee_mail":`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/stay_fee_job_golden.py` | create (block 1) | runs the real Python job, writes the golden JSON |
| `go/internal/stayfee/save.go` | create (block 2) | `DB`, `Encrypter`, `PDFRenderer`, errors, `Save`, `Confirm`, `RecentLive`, `PyJSONSorted`, `UTCStamp` |
| `go/internal/stayfee/adjust.go` | create (block 3) | `AddAdjustment`, `ReverseAdjustment` |
| `go/internal/stayfeemail/job.go` | create (block 4) | `Deps`, `Counts`, `ErrNoRenderer`, `DueMonth`, `Run`, `Handler` |
| `go/internal/stayfeemail/queue.go` | create (block 5) | the two mails, `ReconcileNoPayWay`, `ReconcileAllNoPayWay` |
| `go/internal/stayfeemail/job_test.go` | create (block 6) | Go vs golden on PostgreSQL, no-renderer tests |
| `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` | create (block 7) | registers the kind, nil renderer |
| `go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go` | create (block 8) | the registered handler fails without a renderer |
| `go/internal/stayfeemail/testdata/stay_fee_job_golden.json` | create (generated) | seed, steps and Python outputs |
| `docs/tasks/1242-report.md` | create | the report (section 9) |

`docs/tasks/1242a-go-stay-fee-job-code.md` is part of this brief (committed with it); do not edit it. No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints the branch the orchestrator gave you; `ls App/scripts/stay_fee_job_golden.py go/internal/stayfee/save.go go/internal/stayfeemail/job.go go/cmd/ubyhost-web/register_job_stay_fee_mail.go 2>&1 | tail -5` says "No such file" four times; `git status --short | tail` is empty; `grep -cF` of each anchor in section 2 prints 1 or more. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Anything failing: STOP (section 8). Then write the helper into your scratchpad directory (`/tmp` only if you have none; below, `$S` is that directory):

````bash
cat > "$S/extract_1242.py" <<'EOF'
import hashlib, pathlib, re, sys
text = pathlib.Path("docs/tasks/1242a-go-stay-fee-job-code.md").read_text(encoding="utf-8").split("\n")
head = re.compile(r"^### Block (\d+): `([^`]+)` sha256 `([0-9a-f]{64})`$")
found, i = [], 0
while i < len(text):
    m = head.match(text[i])
    i += 1
    if not m:
        continue
    while not text[i].startswith("````"):
        i += 1
    i += 1
    start = i
    while text[i] != "````":
        i += 1
    data = ("\n".join(text[start:i]) + "\n").encode("utf-8")
    got = hashlib.sha256(data).hexdigest()
    if got != m.group(3):
        sys.exit(f"STOP: block {m.group(1)} {m.group(2)} sha256 {got}")
    found.append((pathlib.Path(m.group(2)), data))
if len(found) != 8:
    sys.exit(f"STOP: {len(found)} blocks")
for path, data in found:
    if path.exists():
        sys.exit(f"STOP: {path} exists")
for path, data in found:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print("wrote", path)
EOF
````

1. Create the eight files (one call, from the repo root): `python3 "$S/extract_1242.py" 2>&1 | tail -10` prints eight `wrote` lines. Then `sha256sum App/scripts/stay_fee_job_golden.py go/internal/stayfee/save.go go/internal/stayfee/adjust.go go/internal/stayfeemail/job.go go/internal/stayfeemail/queue.go go/internal/stayfeemail/job_test.go go/cmd/ubyhost-web/register_job_stay_fee_mail*.go | tail -10` must print exactly:

````text
2f4077b7ef2a9dd4976dde075a9537d190e2a1568430078fb7d343d42b2a4da7  App/scripts/stay_fee_job_golden.py
1badab6a857c4c98b9c2357acc67ea5137a4c1ef06e9dd85d2def7c6d0738c19  go/internal/stayfee/save.go
c53925ad6a21454007d7475e234ec3da00f8edf3342c480d7705880aad3ae0c9  go/internal/stayfee/adjust.go
9f9d07e3111a357f0c180c780b3ba6266f298f4f5540430b675c508f06d41ac6  go/internal/stayfeemail/job.go
fef367d07ead89587675e6bf9bf7e9631b65704f0af36600f5a58dbcb0ea0dc2  go/internal/stayfeemail/queue.go
dc26766b5921caa17cef144d263fc24b938a0d765c92bd898b0d30570bd724cf  go/internal/stayfeemail/job_test.go
f9bb9b89b053cb63391f336c6ca173377383fd67d1b0bc50332c0ba6f2dfcae4  go/cmd/ubyhost-web/register_job_stay_fee_mail.go
668dd0ec18741be3d22d1cc88756b9bb9463ee5786474d22e2c7870f57ea90de  go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go
````

   A `STOP:` line or a different hash: STOP (section 8); never type or edit the code by hand. Commit `1242 step 1`.

2. Generate the golden (do not type it): `cd App && .venv/bin/python scripts/stay_fee_job_golden.py 2>&1 | tail -3` prints `wrote /.../go/internal/stayfeemail/testdata/stay_fee_job_golden.json`. Then from the repo root `sha256sum go/internal/stayfeemail/testdata/stay_fee_job_golden.json | tail -3` prints `d25e591636e4515daed201701fd573af0546b6fcca507a3a71ace70cddf03d25`. Any difference: STOP. Commit `1242 step 2`.

3. Run section 6. Commit nothing else; write the report (section 9) and commit it as `1242 report`.

## 5. Do not touch

`go/internal/stayfee/` files other than the two new ones, `go/internal/stayfeemail/` files other than the new ones and the generated golden, `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/internal/secure/`, `go/cmd/ubyhost-web/` files other than the two new ones (main.go, registry.go, register_*.go), `go/go.mod`, `go/go.sum`, all Python under `App/app/` and `App/tests/` (conftest.py included), `App/migrations_pg/`, `docs/context/*`, `docs/ENVIRONMENT.md`, `docs/tasks/1242a-go-stay-fee-job-code.md`. Never set `UBYHOST_GO_JOB_KINDS` or touch a server. Rules 1 to 5 of AGENTS.md as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/stayfee internal/stayfeemail cmd/ubyhost-web 2>&1 | tail -5` prints nothing.
- `cd go && go vet ./internal/stayfee/ ./internal/stayfeemail/ ./cmd/ubyhost-web/ 2>&1 | tail -30` prints nothing.
- `cd go && go test -count=1 -v ./internal/stayfeemail/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -12` prints `--- PASS` for `TestDueMonthGolden`, `TestHandlerNeedsRenderer` and the three 1241 tests, `--- SKIP` for `TestJobGolden` and `TestRunNoRendererWritesNothing` (no local PostgreSQL; CI runs them; if `UBYHOST_TEST_DATABASE_URL` is set they must PASS), and `ok`.
- `cd go && go test -count=1 ./internal/stayfee/ ./cmd/ubyhost-web/ 2>&1 | tail -5` prints two `ok` lines.
- `cd go && go build ./... 2>&1 | tail -10` prints nothing but `go: downloading` lines at most.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python scripts/stay_fee_job_golden.py 2>&1 | tail -1 && cd .. && sha256sum go/internal/stayfeemail/testdata/stay_fee_job_golden.json | tail -1 && git status --short | tail -10`: the hash is still `d25e591636e4515daed201701fd573af0546b6fcca507a3a71ace70cddf03d25` and the tree is clean apart from the uncommitted report, if any.

Test-map row: Go packages `stayfee`, `stayfeemail`, `cmd/ubyhost-web`; no Python file under `App/app` or `App/tests` changes, so no pytest run.

## 7. Acceptance

- [ ] `git diff --stat 969a383..HEAD -- . ':!docs/tasks/1242-go-stay-fee-job.md' ':!docs/tasks/1242a-go-stay-fee-job-code.md'` lists exactly the files of section 3.
- [ ] The eight files and the golden match the sha256 values of steps 1 and 2.
- [ ] Section 6 output as stated: `gofmt`, `go vet`, `go build`, `go mod tidy -diff` clean; the PASS and SKIP lines; two more `ok` lines.
- [ ] `git diff --stat 969a383..HEAD -- go/internal/ubyport go/internal/jobs go/cmd/ubyhost-web/main.go go/cmd/ubyhost-web/registry.go go/go.mod App/app` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, the helper prints `STOP:`, or a hash differs;
- a test fails twice (do not change code to make it pass: the code is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1242-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat 969a383..HEAD | tail -15`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/stayfee/save.go` `Save`: the transaction order (lock, supersede or overlap check, version, INSERT, adjustment link), the advisory-lock form (must equal Python's `hashtext(name), key`), `pdf_enc`/`csv_enc` stored as the token's bytes (Python `encrypt_blob` returns bytes into `bytea`) and `payload_enc` as text, `PyJSONSorted` byte equality with `json.dumps(sort_keys=True)`. Only `TestJobGolden` checks this and it runs in CI only: confirm in the CI log that it passed, not skipped.
- `Confirm` error mapping: which errors mean "not sealed" (0, nil) and which fail the apartment.
- `go/internal/stayfeemail/job.go` `Run`/`apartment`: host and apartment filters, demo check (entity name only when `UBYHOST_UBYPORT_ENV` is mock or unset), `DueMonth` window, Prague today vs UTC schedule day, 3-day cutoff string compare.
- `queue.go`: idempotency keys, payload key order, `mailEnabled` gate, `NoPayWay` inputs, alert key and copy.
- `Handler` must return `ErrNoRenderer` before any pool use (the cmd test passes a nil pool).
- Deviations from Python: `ORDER BY id` added to the host, apartment and recent-filing queries (Python relies on SQLite row order); an `EnqueueMail` error is logged and counts nothing (Python logs and returns an existing row if one appeared); the sweep iterates ids in ascending order (Python a set); `ubyport.NormaliseEmail` supports the two stored address forms only (known, documented in ubyport).

## Owner steps

1. None for this brief. Do not add `stay_fee_mail` to `UBYHOST_GO_JOB_KINDS` yet: it would only fail (job_failed alert) until brief 1243 adds the PDF renderer. Merge when CI is green and `TestJobGolden` ran in the Go job.
