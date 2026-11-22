# 2037: Leon never knows entry codes; one fixed pointer line, plus a test that no code reaches the prompt

Status: todo (runnable now; prompt change only, no UI)
Depends on: none (the test seeds codes through 2032's table when it is on main; until then it seeds `apartment.entry_code_enc`, which 1661 added) | Base commit: fill from `git rev-parse --short HEAD` | Branch: task/2037-leon-entry-code-pointer
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (guest-facing AI prompt; the byte-pinned prompt is shared with Python)

## 1. Objective

Guests will ask Leon "what is the gate code?". Leon must never know a code. Add one fixed instruction to Leon's character prompt: for door, gate, garage or building entry codes he answers "Your entry codes are on your stay page." (in the guest's language) and gives no digits. Add a test that seeds entry codes, builds Leon's real system blocks and asserts no code value is in them.

## 2. Context (verified on main)

- Go: `go/internal/web/ai/leon_core.go:25` `//go:embed leon_prompt.txt` (the character); `LeonSystemBlocks(cards, propertyName)` (`:279`) returns `[]string{leonCharacter, LeonGuideBlock(cards, propertyName)}`; the guide block holds only `LeonCard` fields (`Kind, Title, Location, Steps, WatchOut, VideoURL, Photos, Facts`; `:201-209`). Cards come from `leon_facts.go`. No code field exists, so no code can reach the guide block unless a host types it into a card (the existing card text rules stay).
- Python twin: `App/app/leon.py:66` `CHARACTER = """You are Leon, ...`, `system_blocks` at `:227`. `go/internal/web/ai/leon_prompt.txt` is that string byte for byte, written by `App/scripts/leon_try_golden.py` (`:10`, `:200`: `PKG / "leon_prompt.txt": leon.CHARACTER`). Both must change together or the golden breaks.
- The prompt's sections (`go/internal/web/ai/leon_prompt.txt`): `WHAT YOU KNOW` (line 3), `SITUATIONS` (18), `KINDS` (28). The reply kinds are `answer`, `ask_host`, `about_me`, `refuse`, `emergency`, `unclear`. Entry codes are not in the guide, so by the existing rules the honest kind is `ask_host`; the new line makes it a fixed `answer`-free pointer instead of asking the host. Keep the change to one added paragraph.
- go-first (`docs/context/go-first.md`): the Go file is the change; the Python edit is exception 1 (port plumbing: the byte-identical twin the golden reads), the same sentence, nothing else in Python. Check whether Python still serves guest Leon: `grep -n "leon" App/app/routes/guest*.py | head -5`; if it does, the Python change also protects production now.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/leon_prompt.txt` | edit | one paragraph, step 1 |
| `App/app/leon.py` | edit (exception 1) | the same paragraph in `CHARACTER` |
| `go/internal/web/ai/leon_entry_code_test.go` | new | step 3 |
| `App/tests/test_leon_entry_code_prompt.py` | new | the Python twin of the test |

No other file may change. If `leon_try_golden.py --check` (or the test that compares the two files; find it with `grep -rn "leon_prompt" App/tests go/internal | head -3`) fails after your edit, copy the Python string into the Go file exactly; never hand-edit one side only.

## 4. Steps

1. Add after the `WHAT YOU KNOW` paragraph (before `YOUR CHARACTER`) in both files, as its own paragraph with a blank line before and after:

```
ACCESS CODES
You never know any door, gate, garage, bike room or building entry code, and no code is ever in the guide. When a guest asks for one, answer in the guest's language: "Your entry codes are on your stay page." Give no digits, do not guess, and never ask the guest to type a code here. This does not change what a guide card says, for example the Wi-Fi.
```

   In the JSON answer that is kind `answer` with `sources` as the schema requires; if the schema forces at least one card id, use kind `ask_host`'s fixed text instead: STOP and report (the orchestrator decides), do not change the schema.
2. Run the Python golden writer in check mode if it has one (`cd App && .venv/bin/python scripts/leon_try_golden.py --help 2>&1 | tail -5`); otherwise rewrite the Go file from Python with `.venv/bin/python scripts/leon_try_golden.py 2>&1 | tail -5` and confirm only `leon_prompt.txt` changed (`git status --short | tail -5`).
3. Go test `TestLeonPromptNeverHoldsEntryCodes` (DB test like `leon_facts_test.go`; read its fixtures first): seed an apartment with guide cards and codes `7741#`, `5502`, `GARAGE-93` (ciphertext or, for a unit test with no key, the plain value in the seed row; the point is that the value is unique and searched for); load cards through the real path used by the guest Leon handler, call `LeonSystemBlocks` and `LeonUserTurn`, and assert none of the three values (and none of their ciphertexts) occurs in any block; assert the character contains `Your entry codes are on your stay page.` exactly once. Add a case where a host card text contains `7741#`: the test documents that this is the host's own card text and only asserts the system prompt constant is unchanged by seeding the table.
4. Python test: same assertions on `leon.system_blocks(cards, "Flat")` and `leon.CHARACTER`, plus a test that `leon.CHARACTER` equals the content of `go/internal/web/ai/leon_prompt.txt` (read the file by relative path from the repo root).

## 5. Do not touch

The JSON schema, the KINDS section, the user turn, the guide block builder, photos, the guest chat handler, Leon's host pages.

## 6. Commands

From `go/`: `gofmt -l internal/web/ai/ 2>&1 | tail -5`; `go vet ./internal/web/ai/ 2>&1 | tail -10`
From `go/`, with `UBYHOST_TEST_DATABASE_URL` set: `go test ./internal/web/ai/ -run 'Leon' 2>&1 | tail -30`
From `App/`: `.venv/bin/python -m pytest tests/test_leon_entry_code_prompt.py tests/test_leon*.py -q --tb=short -x 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] The paragraph is identical in `leon.py` and `leon_prompt.txt`; the existing Leon golden and tests stay green.
- [ ] The test fails if a code value is added to any Leon block (prove it once by temporarily adding one; remove it).
- [ ] No other prompt text changed.

## 8. Stop and ask

Stop if: the schema cannot express the fixed answer (step 1); the golden fails for a reason other than the new paragraph; Python and Go prompts differ before your edit; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/2037-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

The prompt is shared with Python byte for byte; a wording that makes Leon refuse real card questions about the Wi-Fi.

## Owner steps

1. None. Open question for the owner: should the pointer be a fixed non-model reply (a keyword check before the model, cheaper and certain) instead of a prompt line? Default here: prompt line.
