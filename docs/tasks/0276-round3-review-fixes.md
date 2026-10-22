# 0276: Round 3 review fixes (test run order, demo link, fee headings, finish test)

Status: todo
Depends on: 0270-0275 | Branch: claude/project-thread-4b2e7k (commit here, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Four small fixes from the round 3 review:
1. After the test guest registers, the walkthrough ("what happens next") sits under the long example message, and the "open the link, then come back" instruction is stale. Show the walkthrough first and hide that instruction.
2. The demo message link fails contrast (4.17:1) and is a 27 px tap target on iPad.
3. The stay fee fields use `h4` under the wizard's `h2` (skipped heading level).
4. `test_wizard_polish_and_overview_cards` still expects the old finish button (dashboard). Since 0274 (idea M) the finish button goes to the first missing step, here the police login.

## 2. Context

Found by the round 3 screenshot matrix and the wide test run.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/setup_wizard/try_it.html | edit |
| App/app/static/host.css | edit (one rule) |
| App/app/templates/_stay_fee_fields.html | edit (3 headings) |
| App/app/templates/setup_wizard/stay_fee.html | edit (one line) |
| App/tests/test_test_run_0272.py | edit (one test) |
| App/tests/test_onboarding_wizard_browser.py | edit (2 lines) |
| App/app/static_versions.json or whatever `tests/test_static_versions.py --write` updates | regenerated |

No other file may change.

## 4. Steps

**Step 1. try_it.html.**
a) Cut the whole block from `{% if demo_state == 'registered' %}` (the line before `<section class="setup-rehearsal"`) down to and including its `</section>`. Paste it right after the line `{% set demo_state = setup_demo.state if setup_demo else 'none' %}` (line 7) and close it there with `{% endif %}`.
b) Where the block was, keep only:
```
{% if demo_state == 'open' %}
<p class="setup-wizard-instruction" data-wizard-demo-wait>{{ t('wizard.try_it.waiting') }}</p>
{% endif %}
```
c) Change the line `  <p class="setup-wizard-instruction">{{ t('wizard.try_it.instructions') }}</p>` to
`  {% if demo_state != 'registered' %}<p class="setup-wizard-instruction">{{ t('wizard.try_it.instructions') }}</p>{% endif %}`.

**Step 2. tests/test_test_run_0272.py**, in `test_walkthrough_after_demo_registration`, after `assert 'data-rehearsal-step="paste"' in text` add:
```
        # 0276: the walkthrough comes first and the stale "open the link" line is gone.
        assert text.index("data-rehearsal") < text.index('id="demo-property-heading"')
        assert t(lang, "wizard.try_it.instructions") not in text
```
Use the translation helper the file already imports (look at its imports; if the loop variable is not `lang`, use the file's name for it). Run the file. Commit `0276 step 1-2`.

**Step 3. host.css** line with `.setup-demo-message-link {`: replace `display: inline;` with `display: inline-flex; align-items: center; min-height: 2.75rem; max-width: 100%;` and `color: var(--brand);` with `color: var(--brand-action);`. Keep everything else in the rule.

**Step 4. Fee headings.** In `_stay_fee_fields.html` change each of the three `<h4 class="property-subsection-title">` … `</h4>` to `<{{ fee_heading|default('h4') }} class="property-subsection-title">` … `</{{ fee_heading|default('h4') }}>`. In `setup_wizard/stay_fee.html`, put `{% set fee_heading = 'h3' %}` on the line before `{% include "_stay_fee_fields.html" %}`. The property editor keeps `h4`.

**Step 5. Static versions.** From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` (host.css changed). Then make sure every `?v=` reference for host.css was updated (`grep -rn 'host.css?v=' app/templates | head`). Commit `0276 step 3-5`.

**Step 6. Finish test.** In `tests/test_onboarding_wizard_browser.py` `test_wizard_polish_and_overview_cards`, replace
```
        # 0203: the finish button goes to the dashboard, not the property.
        assert "/setup" not in page.url and "/apartments/" not in page.url, page.url
```
with
```
        # 0274 (M): police is still waiting, so the finish button opens that step.
        assert f"/apartments/{flat['id']}/setup/police" in page.url, page.url
```
Commit `0276 step 6`.

## 5. Do not touch

Other templates, routes, i18n. Never loosen or delete another assertion. Never push.

## 6. Commands (from `App/`)

1. `.venv/bin/python -m pytest tests/test_test_run_0272.py tests/test_static_versions.py tests/test_onboarding_wizard_survival.py tests/test_property_hub.py -q --tb=short 2>&1 | tail -15`
2. `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pwb .venv/bin/python -m pytest "tests/test_onboarding_wizard_browser.py::test_wizard_polish_and_overview_cards" tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q --tb=line -rs -p no:cacheprovider 2>&1 | tail -15` (timeout 900000 ms; 0 failed, 0 skipped)
3. `cd .. && python3 scripts/design_lint.py 2>&1 | tail -5 && python3 scripts/context_lint.py 2>&1 | tail -3`
4. Restore evidence: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (from the repo root).

Never run `playwright install`.

## 7. Acceptance

- [ ] All three command lines pass, 0 skipped.
- [ ] No other file changed (`git status --short`).

## 8. Stop and ask

Per TEMPLATE.

## 9. Report

`docs/tasks/0276-report.md` (400 tokens max), `Status: review`. Do not push.
