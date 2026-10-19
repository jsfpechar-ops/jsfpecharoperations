# 0160: setup wizard sits on the page lane; phone action buttons stack cleanly

Status: todo
Depends on: 0144-b | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 or Haiku 5.5 | Fits one session

## 1. Objective

The orchestrator reviewed the 0144-b screenshots and found three problems:
1. At 1280 the wizard body is inset 40 px from the page title. Legacy `host.css` caps `.setup-wizard-body` and `.setup-wizard-foot` at 640 px and centres them inside the 720 px form lane.
2. At 390 the police step's footer mixes a quiet "Back", a secondary "I'm still waiting for my police login" and the primary "Save and continue". They are right-aligned at three different widths.
3. The "See an example police letter" button touches the paragraph under it.

## 2. Context

`host2.css` loads after `host.css`, so rules here win at equal specificity. Footer markup (`setup_wizard/_layout.html`): `<footer class="setup-wizard-foot">` holds the back link (or an empty span) and then the step's `{% block wizard_actions %}`. The police step's actions are a `div.setup-wizard-actions` with a wait form and the primary button. The current host2.css key is `20261019-0144w`.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `docs/tasks/0160-*`.

## 4. Steps

1. Append to `App/app/static/host2.css`:

```
/* 0160: wizard on the page lane; phone footer = full-width stack, primary first, back last */
.host-workspace .setup-wizard, .host-workspace .setup-wizard-body, .host-workspace .setup-wizard-foot { max-width: none; margin-left: 0; margin-right: 0; }
.host-workspace .police-sample-link { margin-bottom: var(--space-3); }
@media (max-width: 599px) {
  .host-workspace .setup-wizard-foot { flex-direction: column-reverse; align-items: stretch; }
  .host-workspace .setup-wizard-foot > span:empty { display: none; }
  .host-workspace .setup-wizard-actions { flex-direction: column-reverse; align-items: stretch; width: 100%; margin-left: 0; }
  .host-workspace .setup-wizard-foot .ui-btn, .host-workspace .setup-wizard-actions form, .host-workspace .setup-wizard-actions form .ui-btn { width: 100%; margin-left: 0; }
}
```

2. Bump the key to `20261019-0160`. Then run versions `--write`, the version test and `scripts/design_lint.py`.
3. From `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium` on the same command line: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_design_setup_wizard_browser.py tests/test_onboarding_wizard_browser.py tests/test_onboarding_followup_browser.py tests/test_shell_lane_browser.py -q -rs 2>&1 | tail -8` (foreground, timeout 600000). Expected: all passed, 0 skipped. If a wizard test asserts the old 640 px width or the old footer order, report it verbatim and do not edit it.
4. Revert any `docs/tasks/0102-evidence` PNG changes the tests made (`git checkout -- docs/tasks/0102-evidence`). Commit by path: `0160: wizard on the page lane; phone footer stacks`. Do not push.

## 5. Do not touch

Templates and other CSS. Hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Tests pass with 0 skipped; lint and versions OK.

## 8. Stop and ask

A test fails twice.

## 9. Report

`docs/tasks/0160-report.md`, `Status: review`.
