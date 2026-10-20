# 0176 report

Status: review

## Files changed

- `App/app/static/host2.css`: appended `/* 0176 */` block, one rule: `.host-workspace .ui-empty .ui-btn-group { justify-content: center; }`
- `App/app/templates/base.html`: host2.css key now `?v=20261019-0176`
- `App/tests/static_versions.json`: regenerated (host2.css v `20261019-0176`)
- `App/tests/test_design_guardrails_browser.py`: new `test_empty_state_action_is_centred_under_its_text` (1280 px, button centre vs paragraph centre within 2 px)
- `docs/tasks/0176-report.md`

## Cause

The brief guessed a button margin. The probe showed `margin: 0px`. The real cause: the `empty_state` macro (`App/app/templates/_components.html` line 267, used by `/invoices`) wraps the button in `.ui-btn-group`, which is `display: flex` with default `justify-content` (flex-start), so the button hugs the left edge. Before fix at 390 px: button centre 104 px, text centre 195 px. At 1280 px: 360 vs 760.

## Commands (last 5 lines)

- `python3 scripts/design_lint.py 2>&1 | tail -2`: `design lint: OK`
- `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`: `3 passed, 1 warning in 0.10s`
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -6`: `8 passed, 1 warning in 113.89s` (0 skipped)
- `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`: ran, no changes there, nothing refused

## Acceptance (section 7)

- [x] Button centred under the text; new test passes; guard tests pass with 0 skipped.

## Screenshot

390 px, /invoices empty state (injected with the same markup as the real empty state, since seeded data has invoices): `/tmp/claude-0/-home-user-jsfpecharoperations/38363728-17ed-5130-bb5b-482347d88982/scratchpad/0176-invoices-390.png`. Button centred under the text.

## Deviations

- Commit trailer: the brief asked for Claude Sonnet 5.5. The session attribution rule says Claude Haiku 5.5, and this executor is Haiku 5.5, so the commit uses Haiku 5.5. The Claude-Session line is unchanged.
- No PR opened: the brief says never push, and a PR needs a push.
- Untracked `docs/tasks/0177-stays-one-column-fewer-rows.md` was already present and is not part of this commit.

## Questions

None.

## Owner steps left

- Review the commit on `claude/project-thread-5hw8cf`, then merge via `scripts/merge-pr-on-green.sh` when a PR is opened.
