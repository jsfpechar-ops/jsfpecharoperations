# 0820: Records pages: last three CI browser failures (PR #707, shard 3)

Status: todo
Depends on: 0817 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make these three failures pass (all reproduce locally). Fix the page when the v2 page really breaks the rule; update a test selector only when it asserts old-shell markup the v2 page intentionally dropped (comment "v2, 0792/0794").

## 2. Context

1. `tests/test_design_guardrails_browser.py:287` `test_empty_state_action_is_centred_under_its_text`: the injected `.ui-empty` action is 420.5 px off its text centre. A v2 rule in `app2.css` (0792/0818 blocks or the "v2 ports of shared ui-* classes" block) makes `.ui-empty .ui-btn-group` or `.ui-empty` left-aligned or full-width. Centre the action under the text, matching the old `.ui-empty` look.
2. `tests/test_host_button_contrast_browser.py:154` `test_small_primary_buttons_on_stay_fees_meet_contrast`: `('stay-fees/1280', [])`, the BUTTONS probe finds no small primary buttons. Read BUTTONS; if v2 stay-fees intentionally uses other classes (e.g. `.btn` / `.round`), point the probe at the v2 primary buttons on /stay-fees so contrast is still checked; never drop the check.
3. `tests/test_host_list_cards_browser.py:120`: `('fees', en/cs, 760/1024, 'expanded') 'no list panel'`. Update the `fees` entry's panel selectors to the v2 `.card.stays-desk` / `.stays-phone` markup, as 0795 did for invoices in the same file.

## 3. Files

`App/app/static/app2.css`, `App/app/templates/stay_fees.html`, `invoices.html`; the three test files (selector updates only, rule in §1). If you change app2.css, bump `app2.css?v=` in `App/app/templates/base.html` to `20261102-0820` and run `.venv/bin/python tests/test_static_versions.py --write` from `App/`.

## 4. Steps

Reproduce, fix, rerun, one item at a time.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_button_contrast_browser.py tests/test_host_list_cards_browser.py -q -rs --tb=short`
2. If app2.css changed: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_static_versions.py -q -rs --tb=short`

## 7. Acceptance

- [ ] Commands: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0820-report.md`, 200 tokens at most. Do not commit or push.
