# 0392 report: Havel answers short and direct

Status: review
Executor: Haiku 5.5 | Branch: claude/0391-havel-topics-first (not pushed, no PR)

## Files changed

- App/app/havel_topics.py: `short` key per question (not wrong/error); `answer()` shows the short key; `read_keys()` unchanged; docstring updated
- App/app/havel_prompt.py: "at most four" steps with the button line; new "about 60 words" line after "Start with one short sentence"; "up to two in one reply"
- App/app/host_i18n.py: 12 `havel.short.*` keys in en (after the en `havel.topic.support_body`) and cs (after the cs one)
- App/app/host_vi_i18n.py: the same 12 keys in vi
- App/tests/test_havel_topics.py: expected paragraph count is 1 for short questions; guest_link/where check uses `havel.short.guest_link.where`; new test for short length (<= 220 chars, en/cs/vi) and `read_keys()`
- docs/tasks/screenshots-0391/answer-ask-390.png: refreshed by the 0391 browser test
- docs/tasks/0392-havel-short-answers.md: Status done

## Commands (last lines)

- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `pytest tests/test_0391_havel_topics_first_browser.py tests/test_havel*.py tests/test_ai*.py tests/test_guide*.py -q -rs`: 141 passed, 0 skipped
- Brief §6 cleanup: reverted the guide screenshots that the test run rewrote (only screenshots-0391 kept)
- `python3 scripts/context_lint.py`: context lint: OK (one WARN about RETENTION.md named by open briefs 0347 and 0350; not blocking)

## Acceptance (§7)

- [x] §6 passes, 0 skipped; context lint OK
- [x] answer-ask-390.png: three-line answer bubble, then the Stays page button, then the ask prompt (390 px)

## Deviations

- Commit: one commit as §9 and the orchestrator say, not one per step as executor.md says.
- No push and no PR, because the orchestrator said do not push. Owner step: `git push` and open the PR when ready.
- Test file: the existing paragraph-count assertion had to change (`len(q["keys"])` would be 1 for short answers), which is inside §3 scope.

## Questions

None.

## Owner steps left

- Review the copy in the 12 `havel.short.*` keys (en, cs, vi) before merge.
- Push the branch and merge through `scripts/merge-pr-on-green.sh`, as usual.
