# 0393 report

Status: blocked
Done: steps 1 to 6 (copy, template, JS, prompt, version key, tests written). Left: the 5 failing browser tests below, then one rerun of §6.

## Files changed
- App/app/i18n.py, App/app/guest_uk_i18n.py: leon_sit_other, leon_other_prompt in 6 languages
- App/app/templates/guest/_leon.html, App/app/templates/guest/base.html (?v=20261025-0393)
- App/app/static/guest-leon.js: Other question chip, openBox/askOther, box hidden until opened or stored messages
- App/app/leon.py: CHARACTER edits only (no test pinned the old text)
- App/tests/static_versions.json, App/tests/test_guest_leon_browser.py (new test test_leon_other_question_opens_box, helper _open_box)
- docs/tasks/0393-leon-topics-first.md (status), docs/tasks/0393-report.md, docs/tasks/screenshots-0393/leon-topics-first-390.png, docs/tasks/screenshots-0393/leon-other-390.png

## Command results
- ruff E9,F63,F7,F82,F401,F841: All checks passed!
- node --check guest-leon.js: OK
- static versions --write: wrote 37 files
- pytest tests/test_guest_leon_browser.py (last run): 5 failed, 4 passed (70 s). The §6 set was not rerun.
- context lint: WARN  20 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review. next free: task 0394 | migration 0022 context lint: OK 

## Failing tests (first assertion or error line)
- test_the_chat_works_and_lays_out_on_a_phone[en] and [cs]: tests/test_guest_leon_browser.py:79 "assert False" (the test is on a fresh chat after _open_box; not yet analysed).
- test_leon_chat_look_on_a_phone: _open_box timed out clicking the "Other question" chip (30 s).
- test_messages_written_while_leon_answers_are_queued_and_sent_as_one: _open_box timed out (line 182).
- test_leon_greets_first: tests/test_guest_leon_browser.py:272 "'What can I do for you' in 'Leon / Of course. Write your question below...'": the reply wait picks the prompt bubble.
- Passing: test_leon_other_question_opens_box (new), test_leon_topic_chips, test_without_javascript..., test_a_reload....

## Deviations
- One commit as §9 says (executor.md says per step); the owner asked for one commit.
- The new test sends with the Send button, not Enter.
- Test edits beyond the brief: _open_box helper before each fill; chip count 4 to 5 in test_leon_topic_chips; .last on guest and leon locators.
- The i18n insert script was written to /tmp (deleted), not the scratchpad.

## Questions
- Is the "Other question" chip click timing out in the _open_box path a real page bug (chip hidden or covered at 390 px) or a test race? Needs a look at the 390 px welcome screenshot.

## Owner steps left
- None yet. The executor or a fresh session must fix the 5 tests and rerun §6 before review.
