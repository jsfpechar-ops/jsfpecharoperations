# 1300: Go port of property settings POST actions

Status: review
Depends on: none | Base commit: a83df54 | Branch: task/1300-go-property-actions
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Port eight host POST routes of `App/app/routes/admin.py` to Go in a new package `go/internal/web/properties/`: entity archive, unarchive and delete; property archive, unarchive, new PIN and new guest link; calendar feed delete. Same status, `Location` (path, flash text, toast keys), row changes and audit rows as Python, proven by a golden file the Python test writes and the Go test replays on Postgres; the routes stay switched off (nothing is added to `UBYHOST_GO_PATHS`).

## 2. Context

Every file was written and run green in a dry run by the brief writer; the finished files are in `docs/plans/1300-files/` (they do not fit the brief's 12k-token cap). You do not write code: step 1 copies them, step 2 checks their sha256, steps 3-4 generate the two derived files, the rest are checks. **Do not open the bundle files**; the reviewer reads them.

Python sources ported (read-only, for the reviewer):

- `App/app/routes/admin.py`: `_form_return_to` (~341), `archive_entity` / `unarchive_entity` / `delete_entity` (~1261-1330), `regenerate_pin` (~3046, with `_PROPERTY_SUMMARIES` at ~3068), `regenerate_link` (~3137), `archive_apartment` / `unarchive_apartment` (~3182-3222), `delete_feed` (~3400).
- `App/app/access.py` `entity`, `apartment`, `feed` (owner match `owner_user_id IS NOT DISTINCT FROM <workspace id>`); `App/app/db.py` `audit`, `set_current_actor` (impersonator id only while inside another workspace), `utcnow` (`YYYY-MM-DDTHH:MM:SS+00:00`), `lock_key`; `App/app/auth.py` `new_permalink_pin` (6 digits), `new_permalink_token` (20 of `PERMALINK_ALPHABET`); `App/app/guest_slug.py` `rotate`, `_insert_current`, `_generated_readable`; `App/app/security.py` `safe_local_path`; `App/app/routes/admin_helpers.py` `back`.

Go code reused (read-only): `hostweb.CSRF`, `hostweb.Login`, `hostweb.Back`, `hostweb.Lang`, `hostweb.Load` (go/internal/hostweb/), `registerRoutes` and `metrics.wrap` (go/cmd/ubyhost-web/registry.go), order CSRF then path id then Login as FastAPI does (like go/internal/payments/requests.go). Private copies made in `properties/` (each commented with its Python source): `formStr`, `safeLocalPath`, `formReturnTo`, `pyUnquote`, Starlette's `Location` quoting (`locationQuote`), pydantic's lax int path parameter (`parseID`), and the slug helpers.

CI: the `go` job runs `go test ./... -count=1` with `UBYHOST_TEST_DATABASE_URL` set, so `TestActionsMatchPython` runs there against Postgres 17; the Python test runs in the SQLite suite and in `test-postgres-full`. Both backends give the same golden (checked in the dry run).

Rules that apply: AGENTS.md hard rule 2 (no new outbound request, no new personal-data field: none here), rule 3 (the seed holds only made-up names), rule 4 (no new dependency: `golang.org/x/text` is already in go/go.mod), rule 5 (SQL in Go is Postgres; no schema change), rule 8.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/properties.go` | create | the eight handlers, `Register`, audit, flash |
| `go/internal/web/properties/localpath.go` | create | `formStr`, `safeLocalPath`, `formReturnTo`, `locationQuote` |
| `go/internal/web/properties/slug.go` | create | PIN/token generation, `guest_slug.rotate` |
| `go/internal/web/properties/properties_test.go` | create | golden replay on Postgres, return_to, readable, shapes |
| `go/internal/web/properties/i18n_keys.txt` | create | the flash keys the package reads |
| `go/internal/web/properties/i18n.json` | create (generated, step 3) | flash catalog from `App/app/host_i18n.py` |
| `go/internal/web/properties/testdata/actions_cases.json` | create | seed rows and cases |
| `go/internal/web/properties/testdata/actions_golden.json` | create (generated, step 4) | what Python did per case |
| `go/cmd/ubyhost-web/register_web_properties.go` | create | `init()` calling `registerRoutes` |
| `App/tests/test_go_properties_actions.py` | create | Python replay; writes and checks the golden |
| `docs/tasks/1300-go-property-actions.md` | edit | `Status:` line only |
| `docs/tasks/1300-report.md` | create | report |

No other file may change.

## 4. Steps

1. Create the branch and copy the eight finished files from `docs/plans/1300-files/` (flat bundle, run from the repo root):

```bash
git checkout -b task/1300-go-property-actions 2>&1 | tail -2
mkdir -p go/internal/web/properties/testdata
cp docs/plans/1300-files/properties.go go/internal/web/properties/properties.go
cp docs/plans/1300-files/localpath.go go/internal/web/properties/localpath.go
cp docs/plans/1300-files/slug.go go/internal/web/properties/slug.go
cp docs/plans/1300-files/properties_test.go go/internal/web/properties/properties_test.go
cp docs/plans/1300-files/i18n_keys.txt go/internal/web/properties/i18n_keys.txt
cp docs/plans/1300-files/actions_cases.json go/internal/web/properties/testdata/actions_cases.json
cp docs/plans/1300-files/register_web_properties.go go/cmd/ubyhost-web/register_web_properties.go
cp docs/plans/1300-files/test_go_properties_actions.py App/tests/test_go_properties_actions.py
```

2. Check the copied files:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -10
cc6a1819bf30eec3bf5d27c3d7d1609d27f1c89768883649819743b927a82b28  go/internal/web/properties/properties.go
7dcad94d25c9013ebda3cb124f1414c94b431e093acb27a0301d81e60b15ed43  go/internal/web/properties/localpath.go
89ed8191317401b3a0f8952bdaac22d1288b0730341c08f23766dcdc0400284d  go/internal/web/properties/slug.go
d7cfa4586c59f6fcc40463881f99efe5971e0bb2be8a9e6a22440e36d70551d9  go/internal/web/properties/properties_test.go
9dd89d7424954552c2cb3c3628e9e8da9217059f1a628e956d43fe58ef7c6016  go/internal/web/properties/i18n_keys.txt
7262bc28be34b26f8c2ac1dea5df445775732dec9bdb51c99c00000945599cb4  go/internal/web/properties/testdata/actions_cases.json
f42a4f2173783dc6d89c5c8066c1dabdf503afc10354917dec07bb02d59c656c  go/cmd/ubyhost-web/register_web_properties.go
8668ad313c0953147dfe41c97fd0329122f717149ec4d9d54cc4ee98eb91090a  App/tests/test_go_properties_actions.py
SUMS
```

Expected: 8 lines ending `OK`. Any `FAILED`: stop (§8).

3. Generate the flash catalog:

```bash
cd App && .venv/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
import go_host_i18n as g
d = Path('../go/internal/web/properties')
(d / 'i18n.json').write_text(g.render(g.read_keys(d / 'i18n_keys.txt')), encoding='utf-8')
" && sha256sum ../go/internal/web/properties/i18n.json
```

Expected: `4296e438fc7898167208410d0d58735ebe4098dd56dede30353f3f9331bf2828  ../go/internal/web/properties/i18n.json`.

4. Generate the golden (Python on the fixture database) and check it:

```bash
cd App && UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_actions.py -q --tb=short -x 2>&1 | tail -5 && sha256sum ../go/internal/web/properties/testdata/actions_golden.json
```

Expected: `2 passed`, then `7a17d6974ee4c552aed292edcc7cb5150a94b7dd6513a344ebf2385cffdd770f  ../go/internal/web/properties/testdata/actions_golden.json`. A different sum: stop (§8); do not edit the golden by hand.

5. Run the checks in §6. Then commit:

```bash
git add go/internal/web/properties go/cmd/ubyhost-web/register_web_properties.go App/tests/test_go_properties_actions.py && git commit -q -m "1300: Go port of property settings POST actions" && git show --stat HEAD | tail -15
```

6. Set `Status: review` in this brief, write `docs/tasks/1300-report.md` (§9), commit both.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/registry.go`, `go/cmd/ubyhost-web/register_web.go`, `App/tests/conftest.py`, every file under `App/app/`, `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere (deploy files, env docs, tests).
- Do not edit the copied files, `docs/plans/1300-files/` or the golden by hand. No new dependency, no `go get`, no `go mod tidy`.
- Hard rules 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge.

## 6. Commands

From the repo root, with the test database the owner's environment gives (`export UBYHOST_TEST_DATABASE_URL=postgresql://USER@HOST/DATABASE`; if it is unset the Go replay test skips, which is a stop (§8), not a pass):

```bash
cd go && test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL|PASS)' | tail -30 && go build -o /dev/null ./cmd/ubyhost-web && echo BUILD OK
```

Expected: no `SKIP`, `--- PASS: TestActionsMatchPython`, `--- PASS` for `TestReturnToMatchesPython`, `TestReadableMatchesPython`, `TestRandomShapes`, `TestCatalogHasEveryKey`, `TestRegisterDoesNotTouchThePool`, `TestRoutesRegisterOnce`, two `ok` lines, `BUILD OK`.

```bash
cd App && .venv/bin/python -m pytest tests/test_go_properties_actions.py -q --tb=short -x 2>&1 | tail -5
python3 scripts/context_lint.py 2>&1 | tail -3
git status --short | tail -20
```

Expected: `2 passed`; `context lint: OK`; after the commit, a clean tree (before it: only the §3 paths).

## 7. Acceptance

- [ ] Step 2: 8 `OK`; steps 3 and 4: the sha256 sums given there.
- [ ] `go vet ./...` clean, `gofmt -l .` empty, `go build ./cmd/ubyhost-web` OK.
- [ ] `TestActionsMatchPython` ran (not skipped) and passed; the other five properties tests and `./cmd/ubyhost-web` pass.
- [ ] `tests/test_go_properties_actions.py`: 2 passed.
- [ ] `git diff --stat a83df54..HEAD` lists only §3 paths, plus this brief and `docs/plans/1300-files/` (both from the brief commit).
- [ ] `grep -rn UBYHOST_GO_PATHS go/internal/web go/cmd/ubyhost-web/register_web_properties.go` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- a `cp` in step 1 fails, or a sum in steps 2-4 differs;
- `TestActionsMatchPython` is skipped (no `UBYHOST_TEST_DATABASE_URL`) or a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go` wants to change `go.mod`/`go.sum`;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1300-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat a83df54..HEAD`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of these files against the Python sources in §2:

- `go/internal/web/properties/properties.go`: ownership SQL (`IS NOT DISTINCT FROM` the workspace id), the order of checks per route, redirect targets, which routes read `return_to` and with which default, the `_PROPERTY_SUMMARIES` case, `active` 0/1, audit row columns (actor = account username, `impersonator_user_id` only while impersonating), no audit row on feed delete (as Python).
- `go/internal/web/properties/slug.go`: `rotateSlug` runs in one transaction under `pg_advisory_xact_lock(hashtext('apartment_slug'), id)`, deletes every slug of the apartment and inserts one current slug; `crypto/rand` for PIN, token and code.
- `go/internal/web/properties/localpath.go`: `safeLocalPath` / `formReturnTo` (open-redirect guard); the golden's 72 `return_to` cases cover it.

Known differences left on purpose (none reaches a browser form):

- A non-integer path id answers 422 with a plain-text body; FastAPI sends a JSON `detail` list. Status matches.
- An id past int64 is looked up as 0 (no row, same "no longer exists" redirect as Python on Postgres; Python on SQLite would answer 500).
- Every row written in one request uses one clock reading; Python calls `utcnow()` per write (same second in practice).
- The routes are registered but not reachable until the owner adds them to `UBYHOST_GO_PATHS` in a later brief.

## Owner steps

1. Wait for the draft PR's CI to go green (the `go` job runs the Postgres replay).
2. Nothing to deploy or configure: the routes stay off until a later brief adds them to `UBYHOST_GO_PATHS`.

