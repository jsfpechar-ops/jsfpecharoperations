# 0176: empty-state action button is centred under its text

Status: todo
Depends on: 0175 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

On `/invoices` with no invoices, the empty state centres its title and text, but the "Generate invoice" button below sits about 45 px from the left edge, off the text's centre line (owner: "geometrically doesnt make sense"). The button must sit centred under the text, in every empty state.

## 2. Context

`ui_empty` macro in `App/app/templates/_ui.html` line 100; rules `.host-workspace .ui-empty` (host2.css lines 93-95, `text-align: center`, `p` has `margin: 0 auto`). The button is probably a block or flex element with a left margin or `display: flex` that ignores `text-align`. Find the cause by running the page and reading computed styles, not by guessing: from `App/` use `/tmp/claude-0/-home-user-jsfpecharoperations/38363728-17ed-5130-bb5b-482347d88982/scratchpad/probe.py` (usage: `.venv/bin/python <probe.py> <path> "<js>" <width>`; it starts a seeded server). The seeded demo data has invoices, so make the empty state appear by using a page that has an empty state with an action (find one: `grep -rn "ui_empty(" App/app/templates | cut -c1-160 | head`), or evaluate JS that injects the same markup copied from the macro into the page and measure it.

## 3. Files

`App/app/static/host2.css` (append a `/* 0176 */` block, tokens only; S1 no raw colours, S2 no bare px in margin, padding, gap, font-size), `App/app/templates/base.html` (host2.css key to one ending `-0176`), `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (one new test), `docs/tasks/0176-*`.

## 4. Steps

1. Find the cause (section 2) and fix it in the appended CSS block so that `.ui-empty` actions are centred (for example `.host-workspace .ui-empty { display: flex; flex-direction: column; align-items: center; }` plus `margin: 0` on the action, adapting to what the probe shows). The title and text must stay centred as today.
2. Run `python3 scripts/design_lint.py 2>&1 | tail -2` from the repo root. Expected: OK.
3. Bump the host2.css key (`-0176`), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Add `test_empty_state_action_is_centred_under_its_text` to `test_design_guardrails_browser.py`: use the `wide_host` / `wide_base` fixtures like the other tests in that file; open a host page that renders an empty state with an action at 1280 px (for a host with no invoices, `/invoices?lang=en` for a fresh host, or the page you found in section 2), and assert the horizontal centre of the action button is within 2 px of the horizontal centre of the empty-state paragraph. If no seeded page shows an empty state, inject the macro's markup with `page.set_content`-free JS (`document.querySelector('main').insertAdjacentHTML(...)`) and assert on that.
5. From `App/`, foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -6`. Then from the repo root `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped.
6. Commit: `git add App docs/tasks/0176-* && git commit` with message "0176: empty-state action centred under its text" and the two trailers given by the orchestrator.

## 5. Do not touch

Page templates, copy, the guard script; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Button centred under the text; new test passes; guard tests pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0176-report.md`, short; `Status: review`.
