# 1290: Go onboarding part 1: property_setup port and the settings-only POST routes

Status: review
Depends on: none | Base commit: a83df54 | Branch: claude/1290-go-onboarding-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (exact files; fresh Fable review of the full diff before ready)

## 1. Objective

Port App/app/property_setup.py (all but `guest_city`) and the four settings-only POST routes of App/app/routes/onboarding.py to a new Go package `go/internal/web/onboarding`, and register the routes in ubyhost-web. Nothing goes into UBYHOST_GO_PATHS, so production keeps serving these routes from Python; a Python golden file plus a parity test keep the two in step until brief 1291 switches them.

## 2. Context

You do not need to open any Python or Go source: every new file is given whole in `docs/tasks/1290-files/files.txt` (committed with this brief; kept out of the brief for the 12k-token brief cap), and step 1 writes them all with one command. Do not read that file unless a check fails. This section records why the files look the way they do (for the reviewer).

- Routes ported (App/app/routes/onboarding.py): `POST /onboarding/dismiss`, `POST /onboarding/resume`, `POST /welcome-back/dismiss`, `POST /celebrations/dismiss`. Order as in Python: CSRF first (`admin.router` has `Depends(security.protect_host_post)`) via `hostweb.CSRF`, then `hostweb.Login` (require_login).
- Owner id: `access.owner_id` is `auth.workspace_user`'s id, which is `session.Host.Workspace.ID` (an admin previewing a workspace acts for it). `welcome_back_dismiss` uses `auth.current_user`, which is `Host.Account.ID`. No session/ change was needed.
- Settings writes mirror `db.set_setting` (`INSERT ... ON CONFLICT(key) DO UPDATE SET value = excluded.value`): `onboarding_dismissed_<owner>` = "1"/"0", `welcome_back_<account>` = "", `celebration_<owner>` = str(milestone) when owner and milestone are non-zero.
- Audit (`db.audit` after `require_login` called `set_current_actor`): `at` = utcnow (whole seconds, "+00:00"), `actor` = signed-in username, `detail` = "", `owner_user_id` = workspace id, `actor_user_id` = account id, `impersonator_user_id` = account id only while previewing, else NULL. Actions `onboarding.dismissed` / `onboarding.resumed`.
- Redirects: 303, empty body, Location quoted like Starlette's RedirectResponse (`quote(url, safe=":/%#?=@[]!$&'()*+,;")`). `return_to` goes through `safeLocalPath`, an unexported port of `security.safe_local_path`, tested on the Python test's cases and on 61 x 3 golden inputs.
- `form_str`: the LAST value of a field (Starlette `FormData.get`), Python `str.strip()`.
- Milestone: `int(_form_str(form,"milestone") or "0")` raises ValueError on a non-int, which Python answers with its server_error_handler 500. **Go answers 500** (plain "Internal Server Error", `Cache-Control: no-store, private`) and writes nothing. Python's int() rules are ported for ASCII (sign, single underscores between digits, 4300-digit limit, any size via math/big).
- `_save` JSON is written by hand to equal `json.dumps(..., sort_keys=True)` byte for byte (", " and ": " separators, ensure_ascii). `load` keeps Python's dict semantics: steps walked in document order, a repeated key keeps its first place and its last value; numbers are truthy by value (1e-400 is false, 1e400 true).
- `pyStrip` is Python `str.strip()`: `unicode.IsSpace` plus U+001C..U+001F.
- DB functions take a small `Settings` interface (`Get`, `Set`); `PoolSettings(pool)` is the PostgreSQL one. The golden write operations run against an in-memory stub in both languages; the route test checks `PoolSettings` on PostgreSQL.

Accepted differences (only reachable with hand-made requests or rows, never from the app's own forms):
1. `safe_local_path` input with a netloc that makes Python's urlsplit raise (e.g. `//[x`): Python 500, Go redirects to the default.
2. Stored JSON with the Python-only literals `NaN` / `Infinity`: Python loads it, Go treats the row as not JSON (nil state).
3. Milestone written with non-ASCII digits (e.g. Arabic-Indic): Python accepts, Go answers 500.
4. Malformed url-encoded bodies (invalid `%` escapes, raw non-ASCII bytes, `;` separators) are decoded by net/http, not Starlette; the result is still the default or a same-site path.
5. Python's 500 for a browser is the HTML error page; Go's is plain text until the Go host layout exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/onboarding/setup.go | create (files.txt) | property_setup.py port: constants, State, pure functions, Load/Start/Mark/SetHidden/Finish/CelebrateOnce/MarkTested/MarkTestedInWizard, PoolSettings |
| go/internal/web/onboarding/routes.go | create (files.txt) | the 4 handlers, audit, formStr, pyInt, safeLocalPath, starletteQuote |
| go/internal/web/onboarding/setup_test.go | create (files.txt) | golden parity tests |
| go/internal/web/onboarding/routes_test.go | create (files.txt) | table tests; route tests on PostgreSQL (skipped without UBYHOST_TEST_DATABASE_URL) |
| go/internal/web/onboarding/testdata/setup_golden.json | create (generated in step 2) | written by the golden script, never by hand |
| go/cmd/ubyhost-web/register_web_onboarding.go | create (files.txt) | init() calls registerRoutes; 4 routes via m.wrap |
| App/scripts/onboarding_setup_golden.py | create (files.txt) | writes the golden file from the real Python |
| App/tests/test_go_onboarding_setup.py | create (files.txt) | re-runs the script into a temp path and compares bytes |
| docs/tasks/1290-files/files.txt | read only | the file contents step 1 writes (already committed) |
| docs/tasks/1290-report.md | create | your report |

No other file may change. In this brief change only the `Status:` line.

## 4. Steps

Run every command from the repo root unless it starts with `cd`. After each step that changed files, commit with `git add -A && git commit -m "1290 step k"` (k = step number).

**Step 1. Write the seven files from docs/tasks/1290-files/files.txt.** Do not type them; run exactly:

```bash
python3 - <<'PYEOF' 2>&1 | tail -30
import pathlib, re
allowed = {
    "go/internal/web/onboarding/setup.go",
    "go/internal/web/onboarding/routes.go",
    "go/internal/web/onboarding/setup_test.go",
    "go/internal/web/onboarding/routes_test.go",
    "go/cmd/ubyhost-web/register_web_onboarding.go",
    "App/scripts/onboarding_setup_golden.py",
    "App/tests/test_go_onboarding_setup.py",
}
brief = pathlib.Path("docs/tasks/1290-files/files.txt").read_text(encoding="utf-8")
found = re.findall(r"^<!-- file: (\S+) -->\n~~~~[a-z]*\n(.*?)^~~~~$", brief, re.S | re.M)
assert {p for p, _ in found} == allowed and len(found) == 7, sorted(p for p, _ in found)
for path, body in found:
    target = pathlib.Path(path)
    assert not target.exists(), f"{path} already exists"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    print("wrote", path)
PYEOF
```

Then check the bytes:

```bash
sha256sum -c - <<'SUMS' 2>&1 | tail -30
9f68c5f76c1101e6ea7b62421d1af24a3cc59896387578b77be666d05f234a1d  go/internal/web/onboarding/setup.go
fcfee76aec83b69b3d3f110ac94e295959830a386a9aa6d47a6929512eb800d3  go/internal/web/onboarding/routes.go
9c051b4f31d1abba157d922d939156fe93e333147244973aae2062f4433ea6d3  go/internal/web/onboarding/setup_test.go
fbcb1556983e11e93bb494085374f58ecb1cd4c59722e0a980f1e1d4b935114c  go/internal/web/onboarding/routes_test.go
2e21b010c3651ee3315cce2454e831bef97d8f69abe080688ccd4c0a70e579e2  go/cmd/ubyhost-web/register_web_onboarding.go
51d633d2b39d04afaeda37942ff8343bb1a1aa1edcedc380dc81c482bdc75fc3  App/scripts/onboarding_setup_golden.py
3bba2db251f2de15a069dcf1749d174b2f3b3b6ac3d7667e99a3a26b4598c7e8  App/tests/test_go_onboarding_setup.py
SUMS
```

Expected: seven lines ending `OK`. Any `FAILED`: STOP (§8). Commit `1290 step 1`.

**Step 2. Generate the golden file.** If `App/.venv` is missing, first run `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Then:

```bash
cd App && .venv/bin/python scripts/onboarding_setup_golden.py 2>&1 | tail -5
```

```bash
echo "46f64482de471fec08455f01b0dc47f1708ea2186ffa2f50232bb7b56f4ba305  go/internal/web/onboarding/testdata/setup_golden.json" | sha256sum -c - 2>&1 | tail -3
```

Expected: `wrote .../setup_golden.json`, then `OK`. `FAILED`: STOP (§8); never edit the JSON. Commit `1290 step 2`.

**Step 3. Run §6 commands 1 and 2** (Go). No commit unless a file changed (none should).

**Step 4. Run §6 commands 3 and 4** (Python test, context lint).

**Step 5. Write the report** (§9), set `Status: review` here, commit `1290 step 5`.

## 5. Do not touch

- go/internal/hostweb/, go/internal/session/, go/internal/jobs/, go/cmd/ubyhost-web/main.go, registry.go, register_web.go, register_jobs.go, register_filing.go, register_schema.go, all of App/app/, App/tests/conftest.py, docs/context/*, Caddy and deploy files, UBYHOST_GO_PATHS anywhere.
- Never edit testdata/setup_golden.json by hand, and never make a golden mismatch pass by changing Go or Python code: STOP instead.
- Hard rules: no new dependency (rule 4); never push to main or merge (rule 8); no secrets or .env (rule 3).

## 6. Commands

1. `cd go && test -z "$(gofmt -l .)" && echo gofmt-clean; go vet ./... 2>&1 | tail -30`
   Expected: `gofmt-clean`, no vet output.
2. `cd go && go test -count=1 ./internal/web/onboarding/ ./cmd/ubyhost-web/ 2>&1 | tail -30`
   Expected: two `ok` lines. Without UBYHOST_TEST_DATABASE_URL, `TestOnboardingRoutes` skips; that is fine, CI runs it on PostgreSQL.
3. `cd App && .venv/bin/python -m pytest tests/test_go_onboarding_setup.py -q 2>&1 | tail -30`
   Expected: `2 passed`.
4. `python3 scripts/context_lint.py 2>&1 | tail -3`
   Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `git diff --name-only a83df54..HEAD` lists only the §3 paths and this brief.
- [ ] Step 1 check: 7 x `OK`; step 2 check: `OK`.
- [ ] §6 commands 1 to 4 give the expected output.
- [ ] `grep -c "UBYHOST_GO_PATHS" go/cmd/ubyhost-web/register_web_onboarding.go` prints `1` (the comment only; nothing switches the routes on).

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 check fails, or the step 1 script raises;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1290-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat a83df54..HEAD | tail -15`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- go/internal/web/onboarding/routes.go: CSRF then login order, owner (Workspace) vs account id, audit columns, safeLocalPath, Location quoting, milestone 500.
- go/internal/web/onboarding/setup.go: load normalisation, saveJSON bytes, each pure function against property_setup.py.
- go/cmd/ubyhost-web/register_web_onboarding.go: 4 POST patterns only, no "GET /", pool unused while building.
- App/scripts/onboarding_setup_golden.py: the stub replaces only `property_setup.db`; the matrix covers legacy/finished/hidden/waiting/tested states, aliases, invalid marks, whitespace, both lock values.

Skim: setup_test.go, routes_test.go, App/tests/test_go_onboarding_setup.py. docs/tasks/1290-files/files.txt only carries the file bodies; step 1's sha256 check ties it to them.

## Owner steps

None for merging: the routes stay switched off (no path in UBYHOST_GO_PATHS). The steps to switch them on come with brief 1291.
