# 0168 report

Status: review (step 8 not committed; a fixed rule still reports)
Executor: Haiku 5.5 | Branch: claude/project-thread-5hw8cf | Nothing pushed.

## Files changed (committed, one commit per step)

- Step 1 `600e5d2`: `App/app/static/app.css` line 23 `a` colour to `--coral-600`; line 1022 `label .opt` to `--ink-500`.
- Step 2 `53d6e31`: `App/app/static/host2.css` appended the 24 px `.help-tip-btn` rule.
- Step 3 `cd2da3a`: `App/app/host_i18n.py` added `nav.more_menu` in both blocks ("More menu"; Czech "Další – nabídka"). `App/app/templates/_shell_tabbar.html` line 12 got `aria-label`.
- Step 4 `ea7e699`: `App/app/templates/_components.html` help-tip link got `aria-label`.
- Step 5 `bf88067`: `App/app/templates/guest_form_admin.html` hint paragraph got `id="sig-help"`.
- Step 6 `b1f9d42`: `App/app/templates/base.html` keys `app.css?v=20261006a-0168`, `host2.css?v=20261019-0168`; `App/tests/static_versions.json` refreshed.

## Commands and last lines

- Step 6 `test_static_versions.py`: `2 passed, 1 warning`. `design_lint.py`: `design lint: OK`.
- Step 7 unit tests (shell, i18n, copy, validation): `23 passed, 1 warning`.
- Step 7 browser tests (a11y, design guardrails, guest e2e), `-rfs`: `3 failed, 20 passed`, 0 skipped. Failed: `test_a11y_guard_browser::test_every_page_passes_the_page_checks`, `test_a11y_guard_browser::test_keyboard_focus_is_visible_and_not_covered`, `test_design_guardrails_browser::test_every_host_page_passes_the_layout_guard`.
- Layout guard: `21 layout findings {'field-button-misaligned': 21}`, all on fee-setup, guest-links, automation, stay-detail (expected per coordinator).
- A11y page check: `50 findings {'nav-no-current': 24, 'no-accessible-name': 24, 'generic-link-text': 2}`. Contrast 0, target-size-24 0, aria-target-missing 0.
- Evidence cleanup run (`0102-evidence`): done.

## Stop reason (brief §8: a fixed rule still reports)

`generic-link-text` still fires twice: `property-new en 390` and `property-new en 1280`, on `a "Read more"`. The step 4 `aria-label` did not clear it, so the checker reads visible text, not the accessible name. No template has a literal "Read more"; it comes from `help.tip.more` in the help-tip macro. I did not change the check or guess a second fix.

## Deviations

- Step 8 combined commit not made, since the brief stops on a fixed rule.
- Screenshots (390 px per changed page) not taken; the brief stopped before the final review.
- `test_keyboard_focus_is_visible_and_not_covered` fails with 10 `focus-not-visible` and 9 `focus-obscured` findings. It is not on the expected list; it may belong to brief 0169.

## Questions

1. The two "Read more" links: should the fix be visible text (e.g. "Read more about <topic>"), or should the checker accept an aria-label? Owner or coordinator decides.
2. Is `test_keyboard_focus_is_visible_and_not_covered` expected to be red until 0169?

## Owner steps left

None. Brief 0169 was not started.
