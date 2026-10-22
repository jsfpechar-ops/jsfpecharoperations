# 0276 report

Status: review

## Files changed

- App/app/templates/setup_wizard/try_it.html (registered walkthrough moved above the message; stale instruction hidden when registered)
- App/tests/test_test_run_0272.py (order and stale-line asserts)
- App/app/static/host.css (demo message link: inline-flex, 2.75rem tap target, var(--brand-action))
- App/app/templates/_stay_fee_fields.html (three headings use fee_heading, default h4)
- App/app/templates/setup_wizard/stay_fee.html (set fee_heading = h3)
- App/app/templates/base.html (host.css key bumped to 20261022-0276)
- App/tests/static_versions.json (regenerated)
- App/tests/test_onboarding_wizard_browser.py (finish button expects police step)

## Commands (last lines)

1. `pytest tests/test_test_run_0272.py tests/test_static_versions.py tests/test_onboarding_wizard_survival.py tests/test_property_hub.py`: 40 passed, 0 failed, 0 skipped.
2. `UBYHOST_REQUIRE_BROWSER=1 pytest <finish test> tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -rs`: 26 passed, 0 failed, 0 skipped.
3. `scripts/design_lint.py`: OK. `scripts/context_lint.py`: FAIL (see Deviations).
4. Evidence restore: done, `docs/tasks/0102-evidence` clean.

## 7. Checklist

- [x] Command 1 passes
- [x] Command 2 passes, 0 skipped
- [ ] Command 3 passes (context lint fails, see Deviations)
- [x] No other file changed

## Deviations

- Step 5: the static-version writer refused until base.html's `?v=` was bumped. No value was given in the brief, so I used `20261022-0276`.
- context_lint fails with `missing section '## 9. Report'` in docs/tasks/0276-round3-review-fixes.md. The brief's report section is numbered 7. The brief file was not edited (not in scope).
- No 390 px screenshot was taken. AGENTS.md rule 7 asks for one per changed page; the brief's acceptance does not list it.
- Not pushed and no PR opened (the brief and the executor rules say never push).

## Questions

- Is the `## 9. Report` lint error in the brief to be fixed by the orchestrator?
- Is a 390 px screenshot per changed page still required for this brief?

## Owner steps left

- Review and push branch claude/project-thread-4b2e7k, then open the PR.
