# 1250: Port guide import job to Go

Status: review
Depends on: none (P0 registry, #965, is on main) | Base commit: a83df54 | Branch: task/1250-go-guide-import
Executor: Haiku 5.5 | Fits one session: no. About 40k tokens of code to copy; expect one handover (executor.md: commit after every step, report `blocked`, a fresh session continues).

Tier B. Lane J5 of [go-full-move](../plans/go-full-move.md) §7.

## 1. Objective

Port the Python `guide_import` job (`scheduler._job_guide_import`: `guest_guide_import.process_queue()` then `guest_guide_merge.process_pending()`, with the part of `ai.call` it uses) to new Go packages `go/internal/guideimport` and `go/internal/anthropic`, registered as job kind `guide_import` in a new `register_job_guide_import.go`. The port stays OFF: nothing changes in production until the owner adds `guide_import` to `UBYHOST_GO_JOB_KINDS`.

Every file is pre-written below and was dry-run on a scratch copy of this base (go build, go vet, go test with a real Postgres 16, the golden script). You copy; you do not design. The Python source stays the source of truth; a Python golden script writes fixtures and the Go tests reproduce them exactly.

## 2. Context

Facts checked while writing this brief (do not re-check):

- Go module root is `go/` (`go/go.mod`, module `github.com/jsfpechar-ops/jsfpecharoperations/go`). Run Go commands from `go/`. The module needs go 1.25: with `GOTOOLCHAIN=auto` the toolchain downloads itself on first use.
- **No new dependency.** The Anthropic client is a thin `net/http` client behind the `anthropic.Doer` interface (owner decision, final). `golang.org/x/text` is already in go.mod (used for NFKC and case folding). `time/tzdata` is the Go standard library.
- **Photos.** `_run_one` calls `_photo_urls(source, data)` on the TRIMMED data; `trim()` keeps no `photos` or `images` key, so Python never reaches `download_listing_photos` and stores 0 photos. Go has no photo code. The golden file holds, for fixtures whose raw item has photos, Python's list for the trimmed data (empty), and `TestTrimMatchesPython` asserts it and that Go's trimmed data has no photo key.
- **Interval.** Python `job_intervals()` gives `guide_import: 60` minutes; the file registers `registerJob("guide_import", 60, ...)`. Alert level: Python `_JOB_LEVELS["guide_import"] = "warning"`; Go `jobLevels` defaults to "warning" and `jobNames` already has `guide_import`. Nothing to change in `go/internal/jobs`.
- **Switch.** `registerJob` adds the kind to `goIntervals` and `jobFactories`; `jobs.Run` only claims kinds listed in `UBYHOST_GO_JOB_KINDS` (`parseGoKinds`), and Python refuses a Go kind that is not also in `UBYHOST_JOB_QUEUE_KINDS`. Default env: nothing runs in Go. The factory builds services without touching the pool or the network (the tests and `parseGoKinds` call it with a nil pool).
- **Job outcome.** The Go runner (`jobs.drain`) does `Finish` + `recordOK` (clears the `job_failed:guide_import` alert and writes `job_last_ok:guide_import`) on success, and `Fail` with backoff, then the alert after 5 attempts, on an error. Python raised the alert on the first failure. The handler returns runs plus merged and logs both counts.
- **Parity gap 1: budget mail.** `ai._warn_budget` mails the operator at 80 percent of the monthly budget through `mail_notify.ai_budget`, which builds an HTML mail and calls `mail.enqueue`. That builder is in `go/internal/mail`, off limits here. Go logs one `slog.Warn` per feature and month instead. While `guide_import` runs on Go, this one mail is not sent for this feature (havel and leon still send theirs from Python). The coordinator must list this in known-issues, or a follow-up brief adds the mail row once `go/internal/mail` has an enqueue helper.
- **Parity gap 2 (edge cases, harmless).** A model answer whose card fields are not strings (the json_schema output forbids it) is stringified as JSON, not as the Python repr. A numeric env var that does not parse falls back to its default (Python stops at import). The Python image-block branch of `estimate_input_tokens` is not ported (text only). Python `isupper`/`islower` use the Unicode Lowercase and Uppercase properties; Go uses the same plus `Other_*`.
- Python's `trim` size loop never ends if nothing can shrink; Go stops after a pass with no change.
- **Outbound requests (rule 2), for the PR text.** Apify (`api.apify.com`): fetch the host's own public Booking.com or Airbnb listing that the host pasted; the URL is rebuilt from an allowlist before it is queued; nothing about guests is sent. Anthropic (`api.anthropic.com`) or Mistral (`api.mistral.ai`, only with `UBYHOST_AI_PROVIDER=mistral`): draft guest-guide cards from that listing text. No guest data is sent. These are the same requests the Python job already makes; the PR moves them, it adds none.
- Never logged: listing text, model text, tokens. The code logs ids, counts, short codes, timings only.
- Coordinator-only files (not in §3): `docs/ENVIRONMENT.md`, `docs/context/test-map.md`, `decisions.md`, `known-issues.md`, `status.md`. The lines the coordinator adds are at the end of this brief.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/anthropic/pyjson.go` | new | Python-style JSON string quoting, input token estimate |
| `go/internal/anthropic/client.go` | new | `Doer` interface, thin Messages API client, request body |
| `go/internal/anthropic/mistral.go` | new | `MistralDoer`, thin Mistral client, request body |
| `go/internal/anthropic/ai.go` | new | config, caps, ledger, `Service.Call` (port of ai.call) |
| `go/internal/anthropic/ai_test.go` | new | parity and client tests |
| `go/internal/anthropic/testdata/golden.json` | new | written by the golden script |
| `go/internal/guideimport/kinds.go`, `pytext.go`, `trim.go`, `apify.go`, `page.go`, `merge.go`, `job.go` | new | the port |
| `go/internal/guideimport/system_rules.txt`, `schema.json` | new | byte-exact copies of SYSTEM_RULES and SCHEMA |
| `go/internal/guideimport/golden_test.go`, `apify_test.go`, `job_db_test.go` | new | parity and Postgres tests |
| `go/internal/guideimport/testdata/golden.json` | new | written by the golden script |
| `go/cmd/ubyhost-web/register_job_guide_import.go` | new | `registerJob("guide_import", 60, ...)` |
| `App/scripts/guide_import_golden.py` | new | writes both golden files |
| `docs/tasks/1250-go-guide-import.md` | this brief | |

No other file may change. In particular not `hostweb/`, `session/`, `jobs/`, `mail/`, `main.go`, `registry.go`, `register_jobs.go`, `App/tests/conftest.py`, `go.mod`, `go.sum`.

## 4. Steps

Method for every code step: create each file with the Write tool, content exactly as in the block (no reformatting, no extra blank lines), run the sha256 check, run the step's command, commit with `1250 step k`. Do not run `gofmt -w`: the blocks are already gofmt-clean; `gofmt -l` is only a check.

### Step 1. Base check

```bash
cd /home/user/jsfpecharoperations && git branch --show-current && git log -1 --format=%h && ls go/cmd/ubyhost-web/registry.go go/internal/jobs/queue.go App/app/guest_guide_import.py 2>&1 | tail -30
```
Branch must be `task/1250-go-guide-import`. If `registry.go` is missing: STOP.

### Step 2. The anthropic package (client, caps, ledger)

#### `go/internal/anthropic/pyjson.go`

sha256 `23f01018e0c26960a8d6fe7a6a3f81687259ecf76c03e602f797d5f7c1e3934b`, 59 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/anthropic/client.go`

sha256 `f578001e79a7d1797050b6000f5929ba85ded0eabbf8bf3af0345d814bf828b2`, 244 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/anthropic/mistral.go`

sha256 `e9a442da3d232047566b6b2d104190a3412aef6c401f2c11b8098219d207a61c`, 173 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/anthropic/ai.go`

sha256 `460da4c5eafe289582dcc7b288753e36dbc16dfda68292ae68ec820163b2323d`, 472 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
23f01018e0c26960a8d6fe7a6a3f81687259ecf76c03e602f797d5f7c1e3934b  go/internal/anthropic/pyjson.go
f578001e79a7d1797050b6000f5929ba85ded0eabbf8bf3af0345d814bf828b2  go/internal/anthropic/client.go
e9a442da3d232047566b6b2d104190a3412aef6c401f2c11b8098219d207a61c  go/internal/anthropic/mistral.go
460da4c5eafe289582dcc7b288753e36dbc16dfda68292ae68ec820163b2323d  go/internal/anthropic/ai.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

```bash
cd /home/user/jsfpecharoperations/go && gofmt -l internal/anthropic; go build ./internal/anthropic/ && go vet ./internal/anthropic/ 2>&1 | tail -30
```
Expected: no output (first run may print `go: downloading ...`). Commit `1250 step 2`.

### Step 3. The guideimport package, pure half

#### `go/internal/guideimport/kinds.go`

sha256 `212c9e1e2cc33902884f0b08eef12294854c7a14bb1e0158fdc082987dd7e8b6`, 46 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/pytext.go`

sha256 `97bc9838cab04d0d69268464ea1814d756b7a60a9ad312b3107bd29372cd7a89`, 144 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/trim.go`

sha256 `2f21441525586c2f16605a3f1bb619f8e52b392ad39ebc6e3b0aeae8d13df960`, 181 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/apify.go`

sha256 `81e6ff6c867affc0fcbcdc8acb41d54d5ff929e4ac58c3a6f9cdb0c2fc12966b`, 147 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/page.go`

sha256 `7c7d08be03f65e9e5f7d9127eb9aeb1c3c0716cd0e1417479f6c1ff35a64d187`, 79 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/merge.go`

sha256 `283996d00ab245f5a23842592089347db88d8dac302ad700305377033e238da1`, 339 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/system_rules.txt`

sha256 `92d00f913b439bc422fab4dcb32fb162e4144f54bae396ae0614792305409cd6`, 40 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/schema.json`

sha256 `e0e5215e67c2fa3eb06fb267f05a85cb4117049ba20ea5002ec57997d6a4ed77`, 95 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
212c9e1e2cc33902884f0b08eef12294854c7a14bb1e0158fdc082987dd7e8b6  go/internal/guideimport/kinds.go
97bc9838cab04d0d69268464ea1814d756b7a60a9ad312b3107bd29372cd7a89  go/internal/guideimport/pytext.go
2f21441525586c2f16605a3f1bb619f8e52b392ad39ebc6e3b0aeae8d13df960  go/internal/guideimport/trim.go
81e6ff6c867affc0fcbcdc8acb41d54d5ff929e4ac58c3a6f9cdb0c2fc12966b  go/internal/guideimport/apify.go
7c7d08be03f65e9e5f7d9127eb9aeb1c3c0716cd0e1417479f6c1ff35a64d187  go/internal/guideimport/page.go
283996d00ab245f5a23842592089347db88d8dac302ad700305377033e238da1  go/internal/guideimport/merge.go
92d00f913b439bc422fab4dcb32fb162e4144f54bae396ae0614792305409cd6  go/internal/guideimport/system_rules.txt
e0e5215e67c2fa3eb06fb267f05a85cb4117049ba20ea5002ec57997d6a4ed77  go/internal/guideimport/schema.json
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

Do not build yet: `job.go` comes in step 4. Commit `1250 step 3`.

### Step 4. The job, and the registration file

#### `go/internal/guideimport/job.go`

sha256 `bbc225862fa57ec8c882d034a0bc113e1e844f4973effbf013ad217ffa46202a`, 454 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/cmd/ubyhost-web/register_job_guide_import.go`

sha256 `0cf77733302e55edeba971eb33b85e0ab6e116f69722872960e1bdbe17399ad8`, 25 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
bbc225862fa57ec8c882d034a0bc113e1e844f4973effbf013ad217ffa46202a  go/internal/guideimport/job.go
0cf77733302e55edeba971eb33b85e0ab6e116f69722872960e1bdbe17399ad8  go/cmd/ubyhost-web/register_job_guide_import.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

```bash
cd /home/user/jsfpecharoperations/go && gofmt -l internal cmd; go build ./... && go vet ./internal/guideimport/ ./internal/anthropic/ ./cmd/... 2>&1 | tail -30
```
Expected: no output. Commit `1250 step 4`.

### Step 5. The golden script, and the golden files

#### `App/scripts/guide_import_golden.py`

sha256 `e8d03093e51ce4f4ecf98e04155258647856dd33f1ef1272b82d15b8372205d0`, 616 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
e8d03093e51ce4f4ecf98e04155258647856dd33f1ef1272b82d15b8372205d0  App/scripts/guide_import_golden.py
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

Create the venv if `App/.venv` is missing, then run the script from `App/`:
```bash
cd /home/user/jsfpecharoperations/App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt)) 2>&1 | tail -5; .venv/bin/python scripts/guide_import_golden.py 2>&1 | tail -8
```
Expected last line: `wrote go/internal/guideimport/testdata/golden.json and go/internal/anthropic/testdata/golden.json` (the lines before it are log lines of the fakes; ignore them). Then:
```bash
cd /home/user/jsfpecharoperations && sha256sum go/internal/guideimport/testdata/golden.json go/internal/anthropic/testdata/golden.json | tail -30
```
Expected (written with Python 3.13 and the pinned requirements):
```
9ed62bd86a120caf857b686621b0d122cd9fc4b3c4eae4ed847228916e996c03  go/internal/guideimport/testdata/golden.json
902f65cf8f49c16414b94762e7a0999bd86351dc61b31c4f31b39ba7e67436d0  go/internal/anthropic/testdata/golden.json
```
A different sha with a different Python version is possible (Unicode tables); then continue, run the tests in the next steps, and report the difference. Run the script a second time: both sums must not change, and `git status --short` must show no change beyond the new files. Commit `1250 step 5`.

### Step 6. anthropic tests

#### `go/internal/anthropic/ai_test.go`

sha256 `2be7e812cac5c9591eb046a37898f9403642da04382bfae125e9c81fa2d7d0d1`, 404 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
2be7e812cac5c9591eb046a37898f9403642da04382bfae125e9c81fa2d7d0d1  go/internal/anthropic/ai_test.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

```bash
cd /home/user/jsfpecharoperations/go && go test -count=1 ./internal/anthropic/... 2>&1 | tail -30
```
Expected: `ok  .../internal/anthropic`. Commit `1250 step 6`.

### Step 7. guideimport parity tests

#### `go/internal/guideimport/golden_test.go`

sha256 `703049c1b49b39e3b15037ba998d9f66b203e503aab4ebbcb3efb27aaef303e8`, 242 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

#### `go/internal/guideimport/apify_test.go`

sha256 `78bda1ac9e7d6c10a99227555cfa81a371f6d96980e80bdaf9968da59e88cfa8`, 109 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
703049c1b49b39e3b15037ba998d9f66b203e503aab4ebbcb3efb27aaef303e8  go/internal/guideimport/golden_test.go
78bda1ac9e7d6c10a99227555cfa81a371f6d96980e80bdaf9968da59e88cfa8  go/internal/guideimport/apify_test.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

```bash
cd /home/user/jsfpecharoperations/go && go test -count=1 ./internal/guideimport/... 2>&1 | tail -30
```
Expected: `ok` (the Postgres tests are not there yet). Commit `1250 step 7`.

### Step 8. Postgres tests

#### `go/internal/guideimport/job_db_test.go`

sha256 `dd3638cf9fc7ac027899eacc09eab9c938e175bd4b473adde222f6590918079b`, 280 lines. Copy the block exactly (the block ends with one newline).

_Code block removed after execution: the file is in this PR and the sha256 above pins it._

```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
dd3638cf9fc7ac027899eacc09eab9c938e175bd4b473adde222f6590918079b  go/internal/guideimport/job_db_test.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).

The test skips without a database URL. The owner's CI has `UBYHOST_TEST_DATABASE_URL`; if you have no PostgreSQL, run only the skip check and say so in the report (Postgres tests: skipped, ran on the brief writer's machine). With a database:
```bash
cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/... 2>&1 | grep -v ' INFO \| WARN ' | tail -30
```
Expected: three `ok` lines. Commit `1250 step 8`.

### Step 9. Final checks

```bash
cd /home/user/jsfpecharoperations/go && gofmt -l internal cmd; go vet ./internal/guideimport/ ./internal/anthropic/ ./cmd/... && go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/... 2>&1 | tail -30
```
```bash
cd /home/user/jsfpecharoperations && git diff --stat origin/main...HEAD | tail -30; python3 scripts/context_lint.py 2>&1 | tail -10
```
`git diff --stat` must list only the §3 files (plus this brief). Whole-file sha check of everything at once:
```bash
cd /home/user/jsfpecharoperations && sha256sum -c <<'EOF' 2>&1 | tail -30
23f01018e0c26960a8d6fe7a6a3f81687259ecf76c03e602f797d5f7c1e3934b  go/internal/anthropic/pyjson.go
f578001e79a7d1797050b6000f5929ba85ded0eabbf8bf3af0345d814bf828b2  go/internal/anthropic/client.go
e9a442da3d232047566b6b2d104190a3412aef6c401f2c11b8098219d207a61c  go/internal/anthropic/mistral.go
460da4c5eafe289582dcc7b288753e36dbc16dfda68292ae68ec820163b2323d  go/internal/anthropic/ai.go
212c9e1e2cc33902884f0b08eef12294854c7a14bb1e0158fdc082987dd7e8b6  go/internal/guideimport/kinds.go
97bc9838cab04d0d69268464ea1814d756b7a60a9ad312b3107bd29372cd7a89  go/internal/guideimport/pytext.go
2f21441525586c2f16605a3f1bb619f8e52b392ad39ebc6e3b0aeae8d13df960  go/internal/guideimport/trim.go
81e6ff6c867affc0fcbcdc8acb41d54d5ff929e4ac58c3a6f9cdb0c2fc12966b  go/internal/guideimport/apify.go
7c7d08be03f65e9e5f7d9127eb9aeb1c3c0716cd0e1417479f6c1ff35a64d187  go/internal/guideimport/page.go
283996d00ab245f5a23842592089347db88d8dac302ad700305377033e238da1  go/internal/guideimport/merge.go
92d00f913b439bc422fab4dcb32fb162e4144f54bae396ae0614792305409cd6  go/internal/guideimport/system_rules.txt
e0e5215e67c2fa3eb06fb267f05a85cb4117049ba20ea5002ec57997d6a4ed77  go/internal/guideimport/schema.json
bbc225862fa57ec8c882d034a0bc113e1e844f4973effbf013ad217ffa46202a  go/internal/guideimport/job.go
0cf77733302e55edeba971eb33b85e0ab6e116f69722872960e1bdbe17399ad8  go/cmd/ubyhost-web/register_job_guide_import.go
e8d03093e51ce4f4ecf98e04155258647856dd33f1ef1272b82d15b8372205d0  App/scripts/guide_import_golden.py
2be7e812cac5c9591eb046a37898f9403642da04382bfae125e9c81fa2d7d0d1  go/internal/anthropic/ai_test.go
703049c1b49b39e3b15037ba998d9f66b203e503aab4ebbcb3efb27aaef303e8  go/internal/guideimport/golden_test.go
78bda1ac9e7d6c10a99227555cfa81a371f6d96980e80bdaf9968da59e88cfa8  go/internal/guideimport/apify_test.go
dd3638cf9fc7ac027899eacc09eab9c938e175bd4b473adde222f6590918079b  go/internal/guideimport/job_db_test.go
EOF
```
Every line must say OK. A line that says FAILED: re-copy that file once; still FAILED: STOP (§8).


## 5. Do not touch

Everything outside §3. Hard rules in play: 2 (privacy: no new personal-data field; the outbound reasons are in the PR text below), 3 (public repo: no secrets; tests use fake keys like `test-key`), 4 (no new dependency: `go.mod` and `go.sum` stay unchanged; `git diff --stat` must not show them), 5 (SQL: Postgres, `$n` placeholders, same statements and effects as Python), 8 (never push to main, never merge). Never push at all: the orchestrator does that.

## 6. Commands

Test-map row: Go job ports run the package tests (there is no row for these packages yet; the coordinator adds one, see below). Exactly these, each ending `| tail -30`:

- `cd go && go build ./... && go vet ./internal/guideimport/ ./internal/anthropic/ ./cmd/...`
- `cd App && .venv/bin/python scripts/guide_import_golden.py`
- `cd go && go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/...` (with `UBYHOST_TEST_DATABASE_URL` for the Postgres tests)

Never `go test ./...` and never the Python suite.

## 7. Acceptance

- [ ] Every sha256 line in step 9's check says OK; the golden sums match or the difference is reported.
- [ ] `go build ./...`, `go vet`, `gofmt -l` clean.
- [ ] The three `go test` packages pass; the Postgres tests ran (not skipped) or the report says where they ran.
- [ ] Re-running the golden script leaves the sums and `git status` unchanged.
- [ ] `git diff --stat origin/main...HEAD` lists only §3 files; `go.mod` and `go.sum` are not in it.
- [ ] Default state is off: `grep -rn guide_import go/cmd/ubyhost-web/main.go` finds nothing new, and the only registration is `register_job_guide_import.go`.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 check still fails after one re-copy;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`: `Done: steps 1 to k. Left: steps k+1 to 9.`);
- `go.mod` or `go.sum` change (a dependency seems needed);
- a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1250-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command above with the last 5 lines of its output, the sha256 matches (OK counts), and whether the Postgres tests ran.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of these files; the rest is tests and fixtures:

- `go/internal/guideimport/job.go`: every SQL statement against `guest_guide_import.py` and `guest_guide_merge.py` (guards `AND status = 'running'` and `AND status = 'done'`, the stale cutoff, the budget fail, the attempt counter, `_write` writable rule).
- `go/internal/guideimport/merge.go`: `verify` and `clean` (they decide which model text reaches a host's guide; quotes must be substrings of the listing).
- `go/internal/anthropic/ai.go`: the three spend caps, the ledger upsert, and the refusal order (disabled, budget, input too large).
- `go/internal/anthropic/client.go` and `mistral.go`: no redirects, the key only in headers, no body text in logs or errors.
- `go/cmd/ubyhost-web/register_job_guide_import.go`: interval 60, nil-pool-safe factory.
- Parity gaps in §2 (budget mail above all).

## Owner steps

Nothing to do before merge: the port is off. To switch on later (after one clean run on a copy, in a separate step the coordinator will write):

1. Add `guide_import` to `UBYHOST_JOB_QUEUE_KINDS` and to `UBYHOST_GO_JOB_KINDS` in both containers' env, then `docker compose up -d`, then check with `docker inspect`.
2. To roll back, remove it from `UBYHOST_GO_JOB_KINDS` again and run `docker compose up -d`.

## PR text (outbound requests, rule 2)

This PR adds no new request. It moves three existing ones to Go, switched off:
- Apify: fetches the host's own public Booking.com or Airbnb listing that the host pasted (link rebuilt from an allowlist). No guest data.
- Anthropic (or Mistral with `UBYHOST_AI_PROVIDER=mistral`): drafts guest-guide cards from that listing text. No guest data.
- Parity gap: the 80 percent AI budget mail is logged, not mailed, while this kind runs on Go.

## Lines for the coordinator (not in this PR)

- `docs/context/test-map.md`: row "Go guide import / model client (`go/internal/guideimport`, `go/internal/anthropic`)": `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/...`; golden: `cd App && .venv/bin/python scripts/guide_import_golden.py` (then `git status` clean).
- `docs/ENVIRONMENT.md`: the Go job reads the same variables as Python and no new ones: `UBYHOST_APIFY_TOKEN`, `UBYHOST_APIFY_MONTHLY_RUNS` (40), `UBYHOST_APIFY_TIMEOUT` (120), `UBYHOST_AI_FEATURES`, `UBYHOST_AI_PROVIDER`, `UBYHOST_ANTHROPIC_API_KEY`, `UBYHOST_MISTRAL_API_KEY`, `UBYHOST_AI_MODEL`, `UBYHOST_MISTRAL_MODEL`, `UBYHOST_AI_MAX_TOKENS`, `UBYHOST_AI_MAX_INPUT_TOKENS`, `UBYHOST_AI_PRICE_*`, `UBYHOST_AI_MONTHLY_USD_GUIDE_IMPORT`, `UBYHOST_AI_KEY_DAILY_USD_GUIDE_IMPORT`. Switch: `guide_import` in `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS`.
- `docs/context/decisions.md`: `[go] guide_import job ported to Go (brief 1250), off by default; Anthropic client is a thin net/http client in go/internal/anthropic behind the Doer interface, no new dependency (owner, 2026-11-13); a swap to the official SDK touches only that package.`
- `docs/context/known-issues.md`: while `guide_import` runs on Go, the 80 percent AI budget mail for that feature is only logged (Go has no mail enqueue helper in `anthropic`); fix after `go/internal/mail` offers one. Also: Go raises the `job_failed` alert after 5 attempts, Python on the first failure.
- `docs/context/status.md`: brief 1250 PR link, port off, owner switch steps above.
