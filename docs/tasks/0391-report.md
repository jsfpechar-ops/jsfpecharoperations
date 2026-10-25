# 0391 report: Havel starts with topics

Status: review
Executor: Haiku 5.5, finished by the orchestrator | Branch: claude/0391-havel-topics-first (PR #513)

## Files changed

- App/app/routes/havel.py: `ask` flag; `havel_ask`, `havel_locked` in the context (GET `?ask=1`, every POST but reset)
- App/app/templates/_havel_form.html: `hidden data-havel-locked` while locked
- App/app/templates/_havel_topics.html: "Other topic" chip, ask branch with the fixed prompt, "Didn't help?" chip as an `ask=1` link
- App/app/static/havel.js: composerOpen/openComposer, saved `composer` state, load() keeps page/return_to and focuses the box after an ask link, focusPanel, UbyHavel.open
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `havel.topic.other`, `havel.other_prompt`, `havel.ask_prompt`; `havel.topic.ask` reworded
- App/app/templates/base.html, App/tests/static_versions.json: havel.js `20261025-0391`
- App/tests/test_0391_havel_topics_first_browser.py (new); older Havel tests click "Other topic" or use `?ask=1`, chip count 5 -> 6
- docs/tasks/screenshots-0391/: topics-390, other-390, answer-ask-390, topics-1280

## Commands (last lines)

- `pytest test_0391 test_0386 test_havel*.py test_ai*.py test_static_versions.py test_design_*.py test_guide*.py` (browser required): 286 passed, 1 failed (test_havel_topics ask-chip markup, fixed, file re-run: 4 passed); 0 skipped
- ruff: All checks passed. design lint: OK. node --check: ok.

## Deviations

- restore(): openComposer() runs before fill(), so fill()'s save() keeps `composer: true`.
- Haiku stopped at the cap with old tests failing; the orchestrator patched those tests.
