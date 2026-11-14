# 1651: Go twin of `validation.mark_from_ws_user` (the zkratka from the web-service login)

Status: todo
Tier: B (a small pure function that fills a field of the police filing; golden from Python)
Depends on: none | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 25k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1651 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

Port `validation.mark_from_ws_user` (`App/app/validation.py` 1083-1100) as `validation.MarkFromWSUser(user string) string`. The demo seed (brief 1597) sets `uby_mark` from the web-service login with it; nothing else uses it yet.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: `uby_mark` goes into the UbyPort submission, so the function must give Python's answer for every input; the golden below is Python's own output. 2 no personal data (made-up logins). 4 no dependency. 11 Go first: port plumbing for a Go brief.

Python: strip the login; it must match `^(?:uby-ws[A-Za-z0-9]{6}|uby-ws_[A-Za-z0-9]{5,6}|uby-tws[A-Za-z0-9]{5})$` ignoring case; `uby-tws...` gives `""`; `uby-ws_` + 5 or 6 characters gives those characters in upper case; `uby-ws` + 6 characters gives them in upper case. `go/internal/validation/validation.go` already has the same pattern as `wsUserRE` (line 121) and `pyStrip`; the new function uses both, so the pattern exists once.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1651-files/<repo path>.txt`.

| sha256 | file | action | lines |
|---|---|---|---|
| `be50a3bf015c3f39a7d9f94de982277da7bf96790dac6e69cca48e2cbe493c33` | `go/internal/validation/ws_user.go` | create | 26 |
| `787feaba85fc48694e3451e2c4bb97fbbefd2512e49fbbd1d6e7b8d8a706e9e2` | `go/internal/validation/ws_user_test.go` | create | 29 |
| `7159e52b25c9fe12d0396a66f58797b96822e3e6c9b7cf4d0b2cd8a5d5a7cd4f` | `go/internal/validation/testdata/ws_user_golden.json` | create | 113 |

The golden holds 28 inputs and Python's answers (Python 3.12), made by running the body of `mark_from_ws_user` and its pattern: the plain forms (with and without underscore, upper and lower case), too short and too long, `uby-tws` logins, spaces and tabs and a newline around the login, empty and prefix-only strings, a prefix typed twice, and the Unicode folding cases Python accepts through `re.IGNORECASE` (the long s, the Kelvin sign) and refuses (`é`). Two Python cases with a dotless or dotted i are left out on purpose: the existing `wsUserRE` does not accept them, which also holds for the login check in `ValidateApartment`.

**Verified by the brief writer** in a throwaway copy of `go/` with exactly these files: `gofmt -l` empty, `go vet ./internal/validation` clean, `go test ./internal/validation/ -count=1` ok (the older golden test of the package still passes).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/validation/ws_user.go` | create | `MarkFromWSUser` |
| `go/internal/validation/ws_user_test.go` | create | the golden test |
| `go/internal/validation/testdata/ws_user_golden.json` | create | Python's answers |
| `docs/tasks/1651-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1651-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `ls go/internal/validation/ws_user.go 2>&1 | tail -1` says "No such file"; `grep -c 'wsUserRE' go/internal/validation/validation.go | tail -1` prints `2`; `grep -c 'func pyStrip' go/internal/validation/validation.go | tail -1` prints `1`; `grep -cF 'def mark_from_ws_user(user: str) -> str:' App/app/validation.py | tail -1` prints `1`; `find docs/tasks/1651-files -name '*.txt' | wc -l | tail -1` prints `3`. Anything else: STOP (§8).

1. Copy the sidecars and check them (repo root):

   ```bash
   cd docs/tasks/1651-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -5
   be50a3bf015c3f39a7d9f94de982277da7bf96790dac6e69cca48e2cbe493c33  go/internal/validation/ws_user.go
   787feaba85fc48694e3451e2c4bb97fbbefd2512e49fbbd1d6e7b8d8a706e9e2  go/internal/validation/ws_user_test.go
   7159e52b25c9fe12d0396a66f58797b96822e3e6c9b7cf4d0b2cd8a5d5a7cd4f  go/internal/validation/testdata/ws_user_golden.json
   EOF
   ```

   All three lines must end with `: OK`. Commit "1651 step 1".

2. Format, build, vet, test (from `go/`; no database needed):

   ```bash
   cd go && gofmt -l internal/validation 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/validation/ 2>&1 | tail -30; go test ./internal/validation/ -count=1 -v 2>&1 | grep -E '^(--- FAIL|--- SKIP|ok|FAIL)|MarkFromWSUser' | tail -10
   ```

   Expected: nothing from gofmt, build and vet; then `--- PASS: TestMarkFromWSUserMatchesPython` is not printed by the grep (passing tests are not matched), so the line `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation` is the proof; no `--- FAIL` or `--- SKIP`.

3. Write the report (§9), set `Status: review`, commit "1651 step 3". Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 5. Do not touch

`validation.go` and its golden, every other file under `go/`, `App/`, `deploy/`, `docs/context/*`.

## 6. Commands

Exactly those of §4. Test-map: the `go/internal/validation` row, if any, is the coordinator's. Never the full suite.

## 7. Acceptance

- [ ] `sha256sum -c` printed `: OK` for all 3 files.
- [ ] Step 2 printed nothing before the final `ok` line.
- [ ] `git diff --stat main...HEAD | tail -10` lists only the paths of §3 and the sidecars.

## 8. Stop and ask

Stop, and write the report, if a check or hash is not as stated, a test fails twice (do not edit sidecars: report), you reach 12 tool calls or about 25k tokens, a file outside §3 needs a change, or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1651-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`ws_user.go`: the order of the prefix checks (`uby-tws` first, then `uby-ws_`, then `uby-ws`) and the cut by characters (runes), not bytes.

## Owner steps

None (nothing uses it yet).
