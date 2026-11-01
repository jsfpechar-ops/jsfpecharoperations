# 0622: Read guard hook (block whole-file reads over 350 lines)

Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0622-read-guard-hook
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Block the `Read` tool when it would load more than 350 lines of a file in one call, so agents grep or read a range instead. Rules in AGENTS.md are suggestions; a `PreToolUse` hook enforces them. Owner approved 2026-11-01.

## 2. Context

Claude Code runs a `PreToolUse` hook with a JSON object on stdin, for example `{"tool_name": "Read", "tool_input": {"file_path": "/abs/path", "offset": 10, "limit": 100}}`. Exit code 0 allows the call. Exit code 2 blocks it and shows stderr to the agent. `offset` and `limit` are optional. Without `limit` the tool reads up to 2000 lines.

Rule: allow when the file has 350 lines or fewer, when `limit` is given and is 350 or less, when the file is missing or not text, or when the path is outside the repo. Block when the file has more than 350 lines and `limit` is missing or above 350. Every call is allowed when the environment variable `ALLOW_FULL_READ=1` is set: that is the owner's escape hatch.

The block message must tell the agent what to do: `File has N lines. Grep for the symbol, then Read with offset and limit (150 lines or fewer), or ask a Haiku subagent to answer from it.`

Stdlib only. No new dependency.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/hooks/read_guard.py` | create | the hook |
| `.claude/settings.json` | create | registers the hook for `Read` |
| `App/tests/test_read_guard_hook.py` | create | runs the script with `subprocess` |
| `docs/context/test-map.md` | edit | one new row |
| `docs/context/workflow.md` | edit | one bullet in "Token budget" |
| `AGENTS.md` | edit | one sentence, see step 5 |
| `docs/context/decisions.md` | edit | one `[workflow]` line, see step 6 |

No other file may change.

## 4. Steps

1. Create `scripts/hooks/read_guard.py`:
   ```python
   #!/usr/bin/env python3
   """PreToolUse hook: block Read calls that would load more than MAX_LINES lines."""
   import json
   import os
   import sys

   MAX_LINES = 350


   def main() -> int:
       if os.environ.get("ALLOW_FULL_READ") == "1":
           return 0
       try:
           data = json.load(sys.stdin)
       except ValueError:
           return 0
       if data.get("tool_name") != "Read":
           return 0
       args = data.get("tool_input") or {}
       path = args.get("file_path") or ""
       limit = args.get("limit")
       if isinstance(limit, int) and 0 < limit <= MAX_LINES:
           return 0
       try:
           with open(path, "rb") as fh:
               head = fh.read(4096)
               if b"\0" in head:
                   return 0
               lines = head.count(b"\n") + sum(chunk.count(b"\n") for chunk in iter(lambda: fh.read(65536), b""))
       except OSError:
           return 0
       if lines <= MAX_LINES:
           return 0
       sys.stderr.write(
           f"Blocked: {path} has {lines} lines. Grep for the symbol, then Read with "
           f"offset and limit (150 lines or fewer), or ask a Haiku subagent to answer from it.\n"
       )
       return 2


   if __name__ == "__main__":
       sys.exit(main())
   ```
   Check: `echo '{"tool_name":"Read","tool_input":{"file_path":"AGENTS.md"}}' | python3 scripts/hooks/read_guard.py; echo $?` prints `0`.

2. Create `.claude/settings.json`:
   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Read",
           "hooks": [
             {
               "type": "command",
               "command": "python3 \"$CLAUDE_PROJECT_DIR\"/scripts/hooks/read_guard.py"
             }
           ]
         }
       ]
     }
   }
   ```

3. Create `App/tests/test_read_guard_hook.py` with a helper that runs `scripts/hooks/read_guard.py` (path from `Path(__file__).resolve().parents[2]`) via `subprocess.run([sys.executable, script], input=json_text, capture_output=True, text=True)`, and five tests using `tmp_path` files: (a) 100-line file, no limit: returncode 0; (b) 500-line file, no limit: returncode 2 and `"500 lines"` in stderr; (c) 500-line file with `limit` 150: 0; (d) 500-line file with `limit` 900: 2; (e) 500-line file with env `ALLOW_FULL_READ=1` (pass `env={**os.environ, "ALLOW_FULL_READ": "1"}`): 0. Also one test: missing file: 0.

4. `docs/context/test-map.md`: add the row `| Hooks (scripts/hooks, .claude/settings.json) | test_read_guard_hook.py |` at the end of the table.

5. `AGENTS.md`: in "Limits (every chat, strict)" append to the last bullet's neighbour a new bullet: `- A hook blocks whole-file reads over 350 lines: grep, then read a range of 150 lines or fewer. Owner override: ALLOW_FULL_READ=1.` Nothing else in the file changes (no dates, no status).

6. `docs/context/workflow.md`, section "Token budget": add the bullet `- Enforced by hook: scripts/hooks/read_guard.py blocks Read over 350 lines without a limit (0622). Questions about a large file go to a Haiku subagent that returns only the answer.` Then append to `docs/context/decisions.md` one line: `- 2026-11-01 | [workflow] PreToolUse hook blocks Read over 350 lines without a limit; ALLOW_FULL_READ=1 overrides. Review token use after one week | owner | 0622`.

## 5. Do not touch

`App/app/`, templates, CSS, migrations, any existing hook or setting, `requirements.txt`. Hard rules 3 and 4 apply: no secrets, no new dependency. Order: the `decisions.md` and `test-map.md` edits are single appended lines, so this brief may run before or after 0428 and 0350.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_read_guard_hook.py -q --tb=short -x 2>&1 | tail -30` (expect 6 passed). Repo root: `python3 scripts/context_lint.py | tail -3` (expect `context lint: OK`). Then confirm the live block: `printf '{"tool_name":"Read","tool_input":{"file_path":"%s/docs/OPERATIONS.md"}}' "$PWD" | python3 scripts/hooks/read_guard.py; echo $?` (expect exit `2` if that file is over 350 lines, otherwise pick the longest file from `wc -l docs/*.md | sort -n | tail -3`).

## 7. Acceptance

- [ ] §6 tests pass, 0 skipped; lint OK.
- [ ] A 500-line file without `limit` exits 2 with the message; with `limit` 150 exits 0; `ALLOW_FULL_READ=1` exits 0.
- [ ] `.claude/settings.json` is valid JSON (`python3 -m json.tool .claude/settings.json | tail -3`).
- [ ] Only the files in §3 changed (`git diff --stat origin/main`).

## 8. Stop and ask

An anchor is missing; `.claude/settings.json` already exists; the lint fails on AGENTS.md size or wording; a test fails twice; you reach 25 tool calls.

## 9. Report

`docs/tasks/0622-report.md`. Add under "Owner steps left": merge through `scripts/merge-pr-on-green.sh`, and after one week compare token use per chat with and without the hook.
