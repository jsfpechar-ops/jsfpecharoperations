# 1240: Go stay-fee calculation, read side (`go/internal/stayfee`), parity-checked against Python

Status: todo
Depends on: none | Base commit: a202945 | Branch: claude/1240-go-stay-fee-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the new shared package `go/internal/stayfee` (package `stayfee`): the Go port of the stay-fee calculation that `stay_fee_auto.check` and `stay_fee_filing.save` read (App/app/stay_fee.py, stay_fee_rate.py, stay_fee_adjustment.py and the read side of stay_fee_filing.py), everything but the PDF and the QR image, with Python parity pinned by a golden file. Nothing calls it yet: brief 1242 (writes, check/confirm, the `stay_fee_mail` job) and the stay-fee pages thread import it; files are added only.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: this is the money and night count of the hlášení the host sends to the town, so parity is the whole point; 2 privacy: no new personal-data field, no outbound request, the golden holds invented data only (`example.test`, fake names, no Fernet token); 3 nothing real in the repo; 4 no new dependency (pgx, `golang.org/x/text` and the repo's `validation` and `secure` packages are already in the module; `go mod tidy -diff` stays empty); 5 SQL: read-only `SELECT`s through a `Querier` (pgx `Query`), Postgres placeholders.

**The code is in a separate file.** The six files are too long for a brief under the lint cap, so they sit as fenced blocks 1 to 6 in `docs/tasks/1240a-go-stay-fee-calc-code.md` (blocks fenced with four backticks). **Do not read that file**: the helper in step 0 copies each block byte for byte and checks its sha256 before it writes anything. Only `git diff`/review reads the code.

**Package shape.** Pure layer (no I/O): `calc.go`, `report.go` and the key functions of `filing.go` take plain structs (`Apartment`, `Entity`, `GuestRow`, `RateRow`, `Adjustment`, `FilingRow`) and return `Period`, `Group`, `[]string` issues, `Payment`, `[]RegisterRow`, CSV bytes, `Hlaseni`. Thin loader: `loader.go` and the `Covering`/`ForeignOverlap`/`Latest`/`CorrectionRate` functions of `filing.go` read rows through `Querier` (`*pgxpool.Pool` or `pgx.Tx`) and decrypt through a `Decrypter` (`FernetDecrypter(*secure.MultiFernet)` for production); nothing runs at package init and nothing touches the database until a function is called. Empty string stands for SQL NULL, as in the other Go ports. Python's `schedule_for` uses `date.today()` when the rate column moved without a history row; Go takes it as `Opts.ScheduleToday`.

**Parity.** `App/scripts/stay_fee_golden.py` seeds a throwaway SQLite database (8 apartments, 4 legal entities, 3 rate rows, 21 reservations, 28 guests, 5 adjustments, 4 filings), runs the real Python and writes `go/internal/stayfee/testdata/stay_fee_golden.json` (12108 lines): 21 cases (monthly and quarterly cadence, a mid-period rate change, a flat-rate override, a bogus cadence, a mid-month and mid-quarter month argument, exempt guests by age, host decision and same-obec residence, document types, stays across period edges and over 60 nights, the 60-night scope ruling, adjustments that add and remove, unsigned stays, every `report_issues` key, no VS, no payer, an inactive property, a sealed filing (frozen and superseded), an overlapping sealed filing), each with `property_period`, `check` (group, issues, key), `unsigned_stays` both ways, `payment_details` (without the QR), `register_rows`, `register_csv` (base64 bytes) and `hlaseni`; 8 apartment checks (`is_active`, `cadence_of`, `vs_of`, `usable_rail_keys`, `payout_account`, `no_pay_way` with the guest-pay switch on and off); 23 helper tables (`shift_month`, `previous_month`, `period_bounds`, `month_key`, `period_label_cs`, `period_complete`, `parse_month`, `parse_czk_int`, `clamp_rate`, `format_czk`, `counted_days_in`, `obec_key`, `fold_text`, `conservative_birth`, `default_doc_type`, `period_key`, `overlap_keys`, `period_anchor`, `spayd`, `net_bed_days`, 40 filing reads (`latest`, `covering`, `foreign_overlap`), `correction_rate`, schedule `is_uniform`/`rate_on`). `golden_test.go` replays it three ways: `TestGoldenHelpers` (pure helpers), `TestGoldenPure` (the seed through the pure layer, with an in-memory backend that does what the loader's SQL does) and `TestGoldenLoader` (the seed loaded into a fresh PostgreSQL database with `App/migrations_pg` applied, then the real loader; it skips without `UBYHOST_TEST_DATABASE_URL`, and CI's Go job sets it). Plus `TestPackageConstants` and `TestFernetDecrypter`.

**Verified by the brief writer** on the working tree of a202945 (files created, tested, then deleted): `gofmt -l internal/stayfee` empty, `go vet ./internal/stayfee/` clean, `go test ./internal/stayfee/` ok, and with a local PostgreSQL 16 (`UBYHOST_TEST_DATABASE_URL` set) `--- PASS: TestGoldenLoader` with all 21 cases; `cd go && go build ./internal/stayfee/` ok; `go mod tidy -diff` empty; golden generation deterministic (same sha twice). A first run found one Go bug (no-break space before "Kč" in `FormatCZK`), fixed in the block, which shows the comparison bites. Line counts: `stay_fee_golden.py` 502, `calc.go` 1045, `report.go` 575, `filing.go` 201, `loader.go` 396, `golden_test.go` 954. Generated file hash: `go/internal/stayfee/testdata/stay_fee_golden.json` sha256 `56e95933694c64daa0068b2a8c007479ee4e96d3732d7690e09bf4d5d8f56115`. A different hash means the base differs: STOP.

Anchors that must exist verbatim (step 0, `grep -cF` prints 1 or more): App/app/stay_fee.py `def property_period(`, `def report_issues(`, `def register_csv(`, `def hlaseni(`; App/app/stay_fee_filing.py `def correction_rate(`; App/app/stay_fee_adjustment.py `def net_bed_days(`; App/app/stay_fee_rate.py `def schedule_for(`; go/internal/validation/validation.go `func ParseISODate(s string) (time.Time, bool) {`; go/internal/secure/fernet.go `func (m *MultiFernet) Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error) {`; go/internal/secure/datakeys.go `func LoadDataKeys(getenv func(string) string) (*MultiFernet, error) {`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/stay_fee_golden.py` | create (block 1 of the code file) | writes the golden JSON from the real Python |
| `go/internal/stayfee/calc.go` | create (block 2 of the code file) | types, constants, dates, money, rates, exemptions, `BuildPeriod` |
| `go/internal/stayfee/report.go` | create (block 3 of the code file) | `ReportGroup`, `ReportIssues`, payment, pay ways, hlášení data, register rows and CSV |
| `go/internal/stayfee/filing.go` | create (block 4 of the code file) | period keys, filing reads, `CorrectionRate`, `FrozenSummary` |
| `go/internal/stayfee/loader.go` | create (block 5 of the code file) | `Querier`, `Decrypter`, `FernetDecrypter`, the Load functions, `PropertyPeriod`, `Check` |
| `go/internal/stayfee/golden_test.go` | create (block 6 of the code file) | Go vs golden: helpers, pure layer, loader on PostgreSQL |
| `go/internal/stayfee/testdata/stay_fee_golden.json` | create (generated by the golden script) | seed, cases and Python outputs |
| `docs/tasks/1240-report.md` | create | the report (section 9) |

`docs/tasks/1240a-go-stay-fee-calc-code.md` is part of this brief (already committed with it); do not edit it. No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/1240-go-stay-fee-mail`; `ls go/internal/stayfee App/scripts/stay_fee_golden.py 2>&1 | tail -5` says "No such file" twice; `git status --short | tail` is empty; `grep -cF` of each anchor in section 2 prints 1 or more. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Anything failing: STOP (section 8). Then write the helper into your scratchpad directory (use `/tmp` only if you have none; below, `$S` is that directory):

````bash
cat > "$S/extract_1240.py" <<'EOF'
import hashlib, pathlib, re, sys
text = pathlib.Path("docs/tasks/1240a-go-stay-fee-calc-code.md").read_text(encoding="utf-8").split("\n")
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
if len(found) != 6:
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

1. Create the six code files (one call, from the repo root): `python3 "$S/extract_1240.py" 2>&1 | tail -10` prints six `wrote` lines. Then `sha256sum App/scripts/stay_fee_golden.py go/internal/stayfee/*.go | tail -10` must print exactly (order may differ):

````text
6bdd94a48504ac7d886e2152e5a3f18fad7c45e7f76350f9ec40a2116e1a1f9e  App/scripts/stay_fee_golden.py
aae92cff2665d1255ea7e062a026a3a43af5a407642985621d71eead4ad7f8a2  go/internal/stayfee/calc.go
1b73fac0fe4c76966ca17c3205bc1cc2e2c2e64fb3b4494918ce148be6a65307  go/internal/stayfee/report.go
c53b840ba649d14ea9b6592361673269b82d0fe6dfba4a7e1087c78be122381f  go/internal/stayfee/filing.go
e99c4f136bb83d3feacf509bc8dc83d2ec25e8075284eade372d7a66e260d6c6  go/internal/stayfee/loader.go
14be605ce193cb33c8bcf9ed642bafbe75037e20eaceaaccab256e8d1e7b1821  go/internal/stayfee/golden_test.go
````

   A `STOP:` line or a different hash: STOP (section 8); never type or edit the code by hand. Commit `1240 step 1`.

2. Generate the golden (do not type it): `cd App && .venv/bin/python scripts/stay_fee_golden.py 2>&1 | tail -3` prints a line ending in `go/internal/stayfee/testdata/stay_fee_golden.json`. Then from the repo root `sha256sum go/internal/stayfee/testdata/stay_fee_golden.json | tail -3` prints `56e95933694c64daa0068b2a8c007479ee4e96d3732d7690e09bf4d5d8f56115`. Any difference: STOP. Commit `1240 step 2`.

3. Run section 6. Commit nothing else; write the report (section 9) and commit it as `1240 report`.

## 5. Do not touch

`go/internal/stayfeemail/` (brief 1241, done), `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/internal/mail/`, `go/internal/validation/`, `go/internal/secure/`, `go/cmd/ubyhost-web/`, `go/go.mod`, `go/go.sum`, all Python under `App/app/` and `App/tests/` (conftest.py included), `App/migrations_pg/`, `docs/context/*`, `docs/ENVIRONMENT.md`, `docs/tasks/1240a-go-stay-fee-calc-code.md`. Rules 1 to 5 of AGENTS.md as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/stayfee 2>&1 | tail -5` prints nothing.
- `cd go && go vet ./internal/stayfee/ 2>&1 | tail -30` prints nothing.
- `cd go && go test -count=1 -v ./internal/stayfee/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10` prints `--- PASS` for `TestGoldenPure`, `TestGoldenHelpers`, `TestPackageConstants`, `TestFernetDecrypter`, `--- SKIP: TestGoldenLoader` (no local PostgreSQL; CI runs it; if `UBYHOST_TEST_DATABASE_URL` is set it must PASS), and `ok`.
- `cd go && go build ./internal/stayfee/ 2>&1 | tail -10` prints nothing but `go: downloading` lines at most.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python scripts/stay_fee_golden.py 2>&1 | tail -1 && cd .. && sha256sum go/internal/stayfee/testdata/stay_fee_golden.json | tail -1 && git status --short | tail -10`: the hash is still `56e95933694c64daa0068b2a8c007479ee4e96d3732d7690e09bf4d5d8f56115` (deterministic) and the tree is clean apart from the uncommitted report, if any.

Test-map row: new Go package `stayfee`; no Python file under `App/app` or `App/tests` changes, so no pytest run is needed.

## 7. Acceptance

- [ ] `git diff --stat a202945..HEAD -- . ':!docs/tasks/1240-go-stay-fee-calc.md' ':!docs/tasks/1240a-go-stay-fee-calc-code.md'` lists exactly the files of section 3.
- [ ] The six code files and the golden match the sha256 values of steps 1 and 2.
- [ ] `go test ./internal/stayfee/` ok with the four PASS lines and the one SKIP of section 6; `gofmt -l` and `go vet` clean; `cd go && go build ./internal/stayfee/` ok; `go mod tidy -diff` empty.
- [ ] `go/internal/stayfeemail/` and `go/go.mod` unchanged (`git diff --stat a202945..HEAD -- go/internal/stayfeemail go/go.mod` prints nothing).

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

Write `docs/tasks/1240-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat a202945..HEAD | tail -15`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/stayfee/calc.go`: `GuestPeriod` (per-night liable/exempt loop, conservative birth date, host decision, same-obec auto exemption, the 60-night threshold and `applyScopeBoundary`), `ScheduleFor`/`RateOn`/`IsUniform`, `rateSegments` (the deficit of a negative adjustment taken from the highest rate first) and `applyAdjustments`: this is the money on the hlášení. `ObecKey`/`FoldText` port Python's `str.upper()` and `unicodedata` folding; known gaps (ASCII-only digits where Python's `isdigit` takes superscripts and full-width digits, `str.upper()` special cases other than ß) are listed in the package comment and are outside the golden.
- `go/internal/stayfee/loader.go` and `filing.go`: the SQL must match `stay_fee._GUESTS_SQL` (active, not archived, not demo, stay touching the period, order by stay start then id), `stay_fee_adjustment.active`, `stay_fee_filing._active`/`latest`/`covering`/`foreign_overlap`. Only `TestGoldenLoader` checks the SQL, and it runs in CI only (skips locally): confirm in the CI log that it passed, not skipped.
- `go/internal/stayfee/report.go`: `ReportIssues` order, `RegisterCSV` bytes (BOM, `;`, CRLF, quoting, the formula-injection apostrophe), `SPAYD` (ASCII upper-casing of the message), `NormaliseAccount` (Czech mod-11 and IBAN check), `UsableRailKeys` order.
- Not ported: the QR image (`payments.qr_data_uri`; callers render `Payment.SPAYD` with the payments package), the PDF (`Hlaseni` is its input only), all writes (brief 1242). The golden passes `ScheduleToday` 2026-11-13 for Python's `date.today()`; any day after the seeded periods gives the same figures.
- No Python test pins the committed golden against `App/app`: a later Python change to the stay-fee maths is not caught until the golden is regenerated (follow-up for brief 1242 or the pages thread).

## Owner steps

1. None for this brief: nothing calls the package until brief 1242 and the pages thread. Merge when CI is green (check that `TestGoldenLoader` ran in the Go job).
