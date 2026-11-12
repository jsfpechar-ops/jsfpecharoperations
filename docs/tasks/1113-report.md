# 1113 report

Status: review

## Files changed

```
 .github/workflows/ci.yml | ~20 lines
 docs/tasks/1113-ci-apt-retry.md
 docs/tasks/1113-report.md
```

## Commands (last lines)

- `grep -nF "timeout 90s sudo apt-get update -qq"`: 2 lines (52, 57) before edit.
- After edit `grep -n "apt-get"`: 2 lines, both with `-o Acquire::Retries=5`.
- `grep -c "Acquire::Retries=5"`: `2`
- YAML parse: no output, exit 0.
- `bash -n /tmp/step1113.sh && echo syntax-ok`: `syntax-ok`
- `python3 scripts/context_lint.py`: `context lint: OK`
- No pytest (workflow-only).

## §7 Acceptance

- [x] `Acquire::Retries=5` count is 2
- [x] No apt-get outside apt_install (2 lines under .github/workflows)
- [x] Loop `for attempt in 1 2 3` with `sleep 10`
- [x] `command -v age >/dev/null` before `age --version`
- [x] YAML parses; bash -n ok
- [ ] Owner: real CI run of `test` job

## Deviations

- Step 3/4/5 code fences in the brief carry +3 spaces from list nesting; applied using Context-section / neighbouring-line indentation (12/10 spaces), which matches the file.
- shellcheck not installed locally; skipped optional shellcheck run.

## Questions

None.

## Owner steps left

1. Open the combined PR and wait for checks.
2. Confirm `test` "Install system tools used by tests" is green, then coverage.
3. Confirm `workflow-lint` and `shellcheck` green.
4. Merge with `scripts/merge-pr-on-green.sh` once the combined PR is ready.
