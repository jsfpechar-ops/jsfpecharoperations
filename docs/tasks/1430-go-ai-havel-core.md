# 1430: Go port of Havel's core: prompt, redaction, signed history, validation and ask(), parity-checked against Python

Status: todo
Depends on: none | Base commit: c240f4445 (main when this brief was written) | Branch: task/1430-go-ai-havel-core
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy-relevant outbound request: Havel's model calls)

## 1. Objective

Add the pure core of the Havel support assistant to `go/internal/web/ai`: the system blocks, redaction, signed history, host context, request messages, local replies, the validation guardrails, the quick-help topics and `HavelAsk`, each compared with the real Python through a generated golden. No route, no database, nothing switched on.

## 2. Context

Rules (AGENTS.md): 1 filing correctness (not touched); **2 privacy first (this brief builds what Havel may send to the model; see "PR text")**; 3 fixtures are made up (`@example.test`); 4 no new dependency (`golang.org/x/text` is not used here; nothing is added to go.mod); 5 no SQL in this brief.

**All code is pre-written, compiled and tested** over main at c240f4445. Sidecars: `docs/tasks/1430-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. The three generated data files and the golden are written by `App/scripts/havel_golden.py` from the real Python and are copied too, so they carry sha256 values; step 2 proves the script still writes the same bytes.

**What this ports** (Python mirror, file and lines): `App/app/havel.py` 25-124 (tables, schema) to `havel_data.go`; 124-169 `guide_lang`, `label`, `page_url`, `guide_block`, `pages_block`, `system_blocks`; 168-211 `redact`, `restore`; 213-240 `sign_history`, `read_history`; 242-296 `Host`, `host_context`, `model_history`, `build_messages`; 298-314 `local_reply`; 384-540 `Reply`, `validate`; 542-569 `ask` (all in `havel_engine.go`); `App/app/havel_topics.py` (all) to `havel_topics.go`. The limits, stats, gap log and the model client wiring are briefs 1431 and 1433; nothing here touches the database or the network, and no route is added.

**Why the Unicode helper:** Python's `re` is Unicode-aware and has look-around; Go's RE2 has neither. `havelFold` maps each character to one ASCII byte (non-ASCII letter or number to `_`, non-ASCII decimal digit to `0`, any whitespace to a space) so RE2's `\w \d \s \b` see what Python sees; the look-behind of `_PHONE` is a loop (`havelPhones`). The golden holds 20 redaction texts (accents next to digits, no-break spaces, Arabic-Indic digits), 28 local-reply messages, 70 validation cases and 9 `ask` runs.

**Known and accepted differences** (list them in the PR): (a) a non-ASCII decimal digit counts as an ASCII digit inside the folded matcher (Python's `[A-Za-z0-9]` classes would not match it); (b) an action field that is not text (`guest_email`, `note` as a number) is a plain `fail("action_text")` where Python would raise (a 500); (c) `next` given as a string is iterated by character as in Python, any other non-list is ignored where Python would raise.

**PR text (outbound request, hard rule 2).** Havel is the host support assistant. When a signed-in host sends a question and the feature switches and limits allow it (brief 1433), UbyHost sends one request to the model API (Anthropic, or Mistral when `UBYHOST_AI_PROVIDER=mistral`, through `go/internal/anthropic`, which enforces `UBYHOST_AI_FEATURES`, the key and the three spend caps). The reason: to answer how-to questions about UbyHost from the guide text. This brief only **builds** that request and sends nothing. It holds exactly what Python sends today and nothing more: the constant system blocks (prompt, the guide strings of the host's language, the page list), the host's earlier questions and answers of this one conversation (the last four, 4,000 characters at most) and the new question, **all passed through `HavelRedact` (e-mail addresses, phone numbers and ID-like tokens become `[email 1]`, `[phone 1]`, `[number 1]`)**, plus a `<host_context>` block with the date, the interface language, phone or computer, the property names and cities of the host, the page the host is on, and the quick-help topic. No guest data, no door code, no e-mail address, no phone number, no user id, no account name. The reply is checked by `HavelValidate` before the host sees it; numbers, addresses, markup, foreign scripts, prompt leaks and echoed secrets are refused. No new recipient and no new field.


## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/havel_golden.py` | create | writes the data files and the golden cases from the real Python |
| `App/tests/test_go_ai_havel.py` | create | pytest: the Go files are current with the Python |
| `go/internal/web/ai/havel_common.go` | create | Python str helpers and the Unicode folding the regexps need |
| `go/internal/web/ai/havel_data.go` | create | tables: pages, anchors, topics, schema, limits, embeds |
| `go/internal/web/ai/havel_engine.go` | create | blocks, redaction, signed history, host context, messages, local replies, validate, ask |
| `go/internal/web/ai/havel_engine_test.go` | create | parity tests against the golden |
| `go/internal/web/ai/havel_guide.json` | create | GUIDE_STRINGS, generated |
| `go/internal/web/ai/havel_i18n.json` | create | host strings the Havel pages read, generated from the keys file |
| `go/internal/web/ai/havel_i18n_keys.txt` | create | keys for the generator (Havel, Leon-free) |
| `go/internal/web/ai/havel_prompt.txt` | create | HAVEL_SYSTEM_PROMPT, generated |
| `go/internal/web/ai/havel_topics.go` | create | the quick-help layer (no model) |
| `go/internal/web/ai/testdata/havel_golden.json` | create | Python's answers, generated |
| `docs/tasks/1430-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1430-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root): `git branch --show-current` prints `task/1430-go-ai-havel-core`; `ls go/internal/web/ai 2>&1 | tail -5` shows no file named `havel*` (the directory may not exist, or may hold the guide editor's `guide*.go` files); `grep -cF 'def validate(data: Dict[str, Any], host: Host, message: str, history: List[Dict[str, str]],' App/app/havel.py` prints `1`; `grep -cF 'def ask(host: Host, history: List[Dict[str, str]], message: str, today: Optional[date] = None) -> Reply:' App/app/havel.py` prints `1`; `grep -cF 'def answer(lang: str, topic_id: str, q_id: str)' App/app/havel_topics.py` prints `1`; `find docs/tasks/1430-files -type f | wc -l` prints `12`. Anything else: STOP (§8).

1. Copy the files (one call, repo root). Run exactly:

   ```bash
   mkdir -p App/scripts && cp docs/tasks/1430-files/App/scripts/havel_golden.py.txt App/scripts/havel_golden.py
   mkdir -p App/tests && cp docs/tasks/1430-files/App/tests/test_go_ai_havel.py.txt App/tests/test_go_ai_havel.py
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_common.go.txt go/internal/web/ai/havel_common.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_data.go.txt go/internal/web/ai/havel_data.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_engine.go.txt go/internal/web/ai/havel_engine.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_engine_test.go.txt go/internal/web/ai/havel_engine_test.go
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_guide.json.txt go/internal/web/ai/havel_guide.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_i18n.json.txt go/internal/web/ai/havel_i18n.json
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_i18n_keys.txt.txt go/internal/web/ai/havel_i18n_keys.txt
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_prompt.txt.txt go/internal/web/ai/havel_prompt.txt
   mkdir -p go/internal/web/ai && cp docs/tasks/1430-files/go/internal/web/ai/havel_topics.go.txt go/internal/web/ai/havel_topics.go
   mkdir -p go/internal/web/ai/testdata && cp docs/tasks/1430-files/go/internal/web/ai/testdata/havel_golden.json.txt go/internal/web/ai/testdata/havel_golden.json
   ```

   Then check them: `sha256sum App/scripts/havel_golden.py App/tests/test_go_ai_havel.py go/internal/web/ai/havel_common.go go/internal/web/ai/havel_data.go go/internal/web/ai/havel_engine.go go/internal/web/ai/havel_engine_test.go go/internal/web/ai/havel_guide.json go/internal/web/ai/havel_i18n.json go/internal/web/ai/havel_i18n_keys.txt go/internal/web/ai/havel_prompt.txt go/internal/web/ai/havel_topics.go go/internal/web/ai/testdata/havel_golden.json | tail -30`. Every hash must equal this table:

| sha256 | file (sidecar = `docs/tasks/1430-files/<path>.txt`) |
|---|---|
| `d562c068f34bea574b6005d9ed3dedd44820d186b360886dc5a4dd5d7159e650` | `App/scripts/havel_golden.py` |
| `99ef38d7d855150eb5bd068603238fb3ad0a9138fe8eb362b791dc7d0ac1beb5` | `App/tests/test_go_ai_havel.py` |
| `83b5719da956f69c452772cd4f2f2ed32751d670d2978502eb23a233af372f23` | `go/internal/web/ai/havel_common.go` |
| `e591d9d2887ebb360b9a797efb9a0dd42c9dc0e65312da9cb211a4c3c853087b` | `go/internal/web/ai/havel_data.go` |
| `6e1c17df356c66902a5afbb90f4f6029c66fd3fd7610c5fcf82b32f68d8a6e7b` | `go/internal/web/ai/havel_engine.go` |
| `ae020ea50277a5594dbb1d9ab8a9658c0d328897cd268b1e95c7fb640d796458` | `go/internal/web/ai/havel_engine_test.go` |
| `a930fd47a2a5c335f56e6852ee8aeb53192c143d6a165e84dba45fb855461126` | `go/internal/web/ai/havel_guide.json` |
| `efcf532a9f7aca83817a951dce93dfa66d17f83accbc2d2b599f6952da21ce3f` | `go/internal/web/ai/havel_i18n.json` |
| `e87e76a4e7f1104d5a3ff55f265224790a07ac047a020f1eebfea4ead1f355cb` | `go/internal/web/ai/havel_i18n_keys.txt` |
| `b95ac095d14746e21d473b9d8c832b3dd6feacab8ae3a889d1488e7e2d146a04` | `go/internal/web/ai/havel_prompt.txt` |
| `d8df44e77210cade78ccf103ec075f65caa43dba27d2ca85ef110540a8da61c2` | `go/internal/web/ai/havel_topics.go` |
| `940907ed6f0d05cd2d5b2c9b3cba719c439b703bb7a3066872fbcd42c0f9ad5d` | `go/internal/web/ai/testdata/havel_golden.json` |

   Commit "1430 step 1".

2. Golden freshness (from `App/`, no database needed): `.venv/bin/python scripts/havel_golden.py --check 2>&1 | tail -5; echo rc=$?` prints `rc=0` and no `stale:` line. Then, from the repo root, `git status --short | tail -5` prints nothing. A `stale:` line or a changed file: STOP (Python moved; never edit a sidecar, the Python or the Go to match).

3. Go (from `go/`): `test -z "$(gofmt -l ./internal/web/ai)" && go build ./... 2>&1 | tail -30 && go vet ./internal/web/ai/ 2>&1 | tail -30 && go test ./internal/web/ai/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: no output from gofmt, build or vet, then `--- PASS:` for TestHavelRedactMatchesPython, TestHavelLocalReplyMatchesPython, TestHavelHistoryMatchesPython, TestHavelBlocksMatchPython, TestHavelSchemaMatchesPython, TestHavelMessagesMatchPython, TestHavelValidateMatchesPython, TestHavelAskMatchesPython, TestHavelAskPassesDatabaseErrorsOn, TestHavelTopicsMatchPython, TestHavelSystemBlocksAreConstantPerLanguage and one `ok`. No PostgreSQL is needed. A FAIL: read the last 30 lines, fix nothing in the sidecars, STOP and paste them. Commit "1430 step 3".

4. Python freshness test (from `App/`): `.venv/bin/python -m pytest tests/test_go_ai_havel.py -q --tb=short -rs 2>&1 | tail -30` prints `2 passed` with 0 skipped. Write the report (§9) and commit "1430 step 4".

## 5. Do not touch

`App/app/` and every other Python file (new files under `App/scripts/` and `App/tests/` named in §3 only), `App/migrations_pg/`, `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/anthropic/`, `go/internal/mail/`, `go/internal/ubyport/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go` and every other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/tests/conftest.py`, `deploy/`, `.github/`, `docs/ENVIRONMENT.md`, `docs/context/` (status, test-map, decisions, known-issues, workflow), and every file in `go/internal/web/ai/` that is not named in §3 (the guide-editor thread owns the `guide*.go` files there). No env var, no `UBYHOST_GO_PATHS` value, no migration, no dependency. Hard rules 1 to 5, 8 and 9 of AGENTS.md.

## 6. Commands

Step 2 (golden), step 3 (Go) and step 4 (pytest) above are the commands. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (warnings about other briefs are not yours). Never `go test ./...` and never the full pytest suite (AGENTS.md).

## 7. Acceptance

- [ ] The 12 sha256 values match §4 step 1.
- [ ] `havel_golden.py --check` prints no `stale:` line (exit 0); `git status --short` is empty after step 1's commit.
- [ ] gofmt, `go build ./...` and `go vet ./internal/web/ai/` print nothing; the 11 tests named in step 3 PASS, `ok` for the package.
- [ ] `pytest tests/test_go_ai_havel.py` passes with 0 skipped.
- [ ] `git diff --stat main..HEAD | tail -20` lists only §3 paths.
- [ ] Commits "1430 step 1", "1430 step 3", "1430 step 4"; nothing pushed.

## 8. Stop and ask

As brief 1430 §8 (stop and write the report if an anchor is missing, a sha256 differs, a test fails twice, you reach 25 tool calls or about 50k tokens, a dependency seems needed, a file outside §3 needs a change, §5 would be touched, or a step is unclear). A golden `--check` that prints `stale:` is a STOP: never edit a sidecar, a Python file or a golden to match.

## 9. Report

Write `docs/tasks/1430-report.md` (600 tokens at most) and set this brief's `Status: review`: diff stat, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`go/internal/web/ai/havel_engine.go`: **`HavelBuildMessages` and `HavelHostContext` are what is sent to the model** (against havel.py 259-295; the guide and pages blocks and the prompt are constant text); `HavelRedact` (168-211: e-mail, phone with its look-behind in `havelPhones`, number); `HavelValidate` (426-540: the guardrails: scripts, address, markup, prompt leak, secret echo, number check, link and action checks, property ownership of an action); `HavelAsk` (542-569: the `input_too_large` retry drops one exchange, a disabled or budget error is returned, every other failure is a `fail` reply). `havel_common.go` `havelFold` (the Unicode mapping every regexp depends on). The golden tests are the proof; read the 70 validate cases' names in the golden only if a test is changed. Also check that `git diff` shows no change under `go/internal/anthropic/` and that `go/go.mod` is unchanged.

## Owner steps

None: nothing is switched on.
