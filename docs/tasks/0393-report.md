# 0393 report: Leon starts with topics, brief premium-concierge voice

Status: review
Executor: Haiku 5.5, finished by the orchestrator | Branch: claude/0393-leon-topics-first

## Files changed

- App/app/i18n.py, App/app/guest_uk_i18n.py: `leon_sit_other`, `leon_other_prompt` (en, cs, de, es, fr, uk)
- App/app/templates/guest/_leon.html: `data-text-other`, `data-text-other-prompt`
- App/app/static/guest-leon.js: "Other question" chip (`data-leon-other`) always last; box hidden until it is tapped or the stay has stored messages; the two "Other question" bubbles are marked `data-leon-msg="other"` (never a sent message or a reply); `updateCount()` on open so the box height is measured while visible
- App/app/leon.py: CHARACTER: five-star concierge line, "Premium but brief" bullet (~40 words, one courtesy at most), steps at most four
- App/app/templates/guest/base.html, App/tests/static_versions.json: guest-leon.js `20261025-0393b`
- App/tests/test_guest_leon_browser.py: `_open_box` helper before typing, chip count 4 -> 5, new `test_leon_other_question_opens_box`
- docs/tasks/screenshots-0393/: leon-topics-first-390.png, leon-other-390.png

## Commands (last lines)

- §6 pytest set: 121 passed, 2 failed (static_versions: key bump needed after the orchestrator's JS fix; fixed with `0393b` and `--write`, file re-run: 3 passed); 0 skipped
- ruff: All checks passed. node --check: ok. context lint: OK

## Deviations

- Haiku stopped with 5 browser tests failing; the orchestrator added the `data-leon-other` hook (the cs test could not find the English label), marked the two bubbles "other" (tests waiting for `[data-leon-msg=leon]` matched the prompt), and re-measured the box height on open (the placeholder sat on a second line).
- Owner: re-run `leon_eval.py` on staging after merge; the CHARACTER changed.
