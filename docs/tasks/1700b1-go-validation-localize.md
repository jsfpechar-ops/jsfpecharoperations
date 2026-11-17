# 1700b1: Go port of `validation_i18n.localize` (validation sentences in the host's language)

Status: in-progress
Depends on: 1700a done (verified 2026-11-17) | Base commit: current tip of the working branch | Branch: task/1700b1-go-validation-localize
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 8)
Tier: A (the brief writer wrote, compiled and tested every file; the orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700b1 step k` (`k` is the step number). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1700b1 step'`.

## 1. Objective

Brief 1700b (POST /apartments, create a property) was split on 2026-11-17: **1700b1** (this brief) ports `validation_i18n.localize` to a reusable Go package `go/internal/validationi18n` (`Localize(message, lang string) string`); **1700b2** (the create handler, its golden script and tests) depends on it, and so will 1702 (property settings save). 1700a's `ApartmentNewForm.AddressErrors` must hold the address messages already in the host's language; this is the function that does it, exactly as the Jinja filter `validation_message` does (`App/app/templating.py` `_template_validation_message` calls `validation_i18n.localize(message, lang)`).

## 2. Context

Rules (AGENTS.md): 1 filing correctness: this brief only translates error text for display, it writes nothing and changes no validation; 2 privacy: no data, no request; 3 no secrets, fixtures are made-up sentences; 4 no new dependency (stdlib `regexp`, `encoding/json`, `embed`); 5 no SQL; 11 Go first. One generator script and its freshness test are added under `App/` (go-first exception 1: Go tables generated from Python, the same pattern as `App/scripts/go_guide_facts_i18n.py` and `App/tests/test_go_guide_facts_i18n.py`). No file under `App/app/` changes.

**How the port works (for the reviewer; the executor only copies and runs).**

- Python (`App/app/validation_i18n.py` 314-336): empty message → itself; `vi` → `host_vi_i18n.VALIDATION`, then the two `CS_PATTERNS` regexes with `host_vi_i18n.VALIDATION_PATTERNS[index]`; `cs` → `CS_MESSAGES`, then `CS_PATTERNS`; any other language → the message.
- `App/scripts/go_validation_i18n.py` writes `go/internal/validationi18n/messages.json` (both tables without empty values, the patterns as `[regex, cs template, vi template]`) and `testdata/localize_golden.json` (252 cases: every table sentence plus 9 edge cases, in `cs`, `vi`, `en` and `""`, with Python's answer). `--check` exits 1 when either file is stale; `App/tests/test_go_validation_i18n.py` runs it, so CI fails when someone edits a Python table without regenerating.
- `localize.go` embeds `messages.json`; Python regex syntax is mapped to Go: `\d` → `\p{Nd}` (Python's `\d` matches any Unicode digit) and the final `$` → `\n?\z` (Python's `$` also matches before one trailing newline). `{name}` fields are filled from the named groups (`str.format(**groupdict())`). The golden covers both mappings (Arabic-Indic digits, trailing newline).
- `localize_test.go`: `TestLocalizeGolden` replays every golden case; `TestLocalizeTablesLoaded` checks the tables loaded and that `Street is required.` (the create form's own street sentence) has a Czech entry.

**All code is pre-written, compiled and tested** (in a throwaway copy of this branch). Sidecars: `docs/tasks/1700b1-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `281d6ed071d982af54110134b230336d8ddd37108709f7617cc10a753666a5f6` | `go/internal/validationi18n/localize.go` | create | 102 |
| `ecfba36278fddd8abeffdc7407a090a696b9b05430c38094aec7a60417b84784` | `go/internal/validationi18n/localize_test.go` | create | 40 |
| `4d0d8f46460eda67dc13731d3883cfd3a47415401d977c682e157366269f1cb8` | `go/internal/validationi18n/messages.json` | create | 126 |
| `1ce2e87f776a34672713ccae8131039ebddba849a3c60cca63c968ec0bed24b8` | `go/internal/validationi18n/testdata/localize_golden.json` | create | 1262 |
| `6a86a31b69d91778f74f7dc589ad5259ad8346b27e39d809985c72fc69a2fee7` | `App/scripts/go_validation_i18n.py` | create | 84 |
| `82eae7fe1fdea834ef6c881d2a08140ee8394aba888b7b7a8768bf971a0a5245` | `App/tests/test_go_validation_i18n.py` | create | 11 |

**Verified by the brief writer** (throwaway copy of this branch at `9ede95f`, sidecars copied as step 1 does): `gofmt -l` printed nothing, `go vet ./internal/validationi18n/` silent, `go test ./internal/validationi18n/ -count=1 -v` printed `--- PASS` for both tests (0 skipped), and `python3 scripts/go_validation_i18n.py --check` (from `App/`) printed nothing and exited 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/validationi18n/localize.go` | create | `Localize`, the embedded tables |
| `go/internal/validationi18n/localize_test.go` | create | golden replay, tables loaded |
| `go/internal/validationi18n/messages.json` | create | tables generated from Python |
| `go/internal/validationi18n/testdata/localize_golden.json` | create | Python's answers |
| `App/scripts/go_validation_i18n.py` | create | generator and `--check` (go-first exception 1) |
| `App/tests/test_go_validation_i18n.py` | create | freshness test |
| `docs/tasks/1700b1-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1700b1-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root, one call). Anything other than the stated result: STOP (§8).

   ```bash
   git branch --show-current | tail -1; grep -cF 'def localize(message: str, lang: str = "cs") -> str:' App/app/validation_i18n.py | tail -1; grep -cF 'VALIDATION_PATTERNS: Tuple[str, ...] = (' App/app/host_vi_i18n.py | tail -1; ls go/internal/validationi18n App/scripts/go_validation_i18n.py App/tests/test_go_validation_i18n.py 2>&1 | grep -c 'No such file' | tail -1; find docs/tasks/1700b1-files -type f -name '*.txt' | wc -l | tail -1
   ```

   Expected, one per line: the branch you were started on (not `main`), `1`, `1`, `3`, `6`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700b1-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOT' 2>&1 | tail -10
   281d6ed071d982af54110134b230336d8ddd37108709f7617cc10a753666a5f6  go/internal/validationi18n/localize.go
   ecfba36278fddd8abeffdc7407a090a696b9b05430c38094aec7a60417b84784  go/internal/validationi18n/localize_test.go
   4d0d8f46460eda67dc13731d3883cfd3a47415401d977c682e157366269f1cb8  go/internal/validationi18n/messages.json
   1ce2e87f776a34672713ccae8131039ebddba849a3c60cca63c968ec0bed24b8  go/internal/validationi18n/testdata/localize_golden.json
   6a86a31b69d91778f74f7dc589ad5259ad8346b27e39d809985c72fc69a2fee7  App/scripts/go_validation_i18n.py
   82eae7fe1fdea834ef6c881d2a08140ee8394aba888b7b7a8768bf971a0a5245  App/tests/test_go_validation_i18n.py
   EOT
   ```

   Every line must end with `: OK` (6 lines). Then `git add -A && git commit -m "1700b1 step 1"`.

2. Format, vet and test the Go package (one call):

   ```bash
   cd go && gofmt -l internal/validationi18n 2>&1 | tail -5; go vet ./internal/validationi18n/ 2>&1 | tail -10; go test ./internal/validationi18n/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10
   ```

   Expected, exactly: `--- PASS: TestLocalizeGolden`, `--- PASS: TestLocalizeTablesLoaded` (with times) and one `ok` line. No `SKIP`, no `FAIL`, nothing else. No commit (nothing changed).

3. The Python freshness check (one call, from `App/`). With the venv: `cd App && .venv/bin/python -m pytest tests/test_go_validation_i18n.py -q --tb=short -x 2>&1 | tail -30` → `1 passed`. Without `App/.venv`: `cd App && python3 scripts/go_validation_i18n.py --check; echo rc=$?` → only `rc=0`. Then `git status --porcelain | tail -5` must print nothing (the check writes no file). No commit.

4. Write the report (§9), set `Status: review` in this file, `git add -A && git commit -m "1700b1 step 4"`.

## 5. Do not touch

`App/app/` (the Python tables stay the source of truth); `go/internal/validation` (the English sentences); `go/internal/web/**` (1700b2 wires `Localize` into the create handler); `UBYHOST_GO_PATHS` or any server file; filing code.

## 6. Commands

Exactly those of steps 2 and 3. Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files). No UI: no UX gate.

## 7. Acceptance

- [ ] Step 1: 6 lines `: OK`.
- [ ] Step 2: two `--- PASS`, one `ok`, nothing printed by gofmt or vet.
- [ ] Step 3: `1 passed` or `rc=0`; working tree clean.
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1700b1 step') | tail -20` lists only §3 paths.

## 8. Stop and ask

Stop and write the report (`blocked`) if: a check of step 0 or a hash of step 1 differs; a test fails (do not edit a sidecar file); the `--check` prints `stale:` (a Python table changed after this brief was written: the orchestrator regenerates the sidecars); a file outside §3 would change; you reach 25 tool calls.

## 9. Report

`docs/tasks/1700b1-report.md` (300 tokens at most): files changed, the last lines of steps 2 and 3, §7 ticked, deviations, questions.

## Risk list (for the reviewer)

`localize.go`: the Python-to-Go regex mapping (`\d`, `$`) and the vi rule (a pattern without a vi template is skipped, as `index < len(VALIDATION_PATTERNS)` does); the golden is generated, never hand-edited. `go_validation_i18n.py`: imports only `app.validation_i18n` and `app.host_vi_i18n`, no database.

## Rollout wave and rollback

- **Rollout:** a library only; nothing calls it until 1700b2.
- **Rollback:** revert the commits.

## Owner steps

None.
