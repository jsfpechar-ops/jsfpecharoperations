# 1066 report

Status: review

1. Files changed: the 6 templates and app2.css, base.html, static_versions.json from brief §3, test_input_attributes_1066.py, screenshots-1066/ (guest-form-390.png, guest-claim-390.png). Venv: created App/.venv (python3.12, requirements + requirements-dev, plus playwright==1.63.0 as in CI).
2. Commands: step tests pass (3, 14, 7). Cmd 1 (guest + geometry + new test): 647 passed, 0 skipped. Cmd 3: test_design_guardrails_browser fails on guest-new 390 "Cancel" tap-target 43 px; identical failure on the base commit (pre-existing, not 1066). Cmd 4 layout lint: 4 passed, 0 skipped. Cmd 2 not run (tail-only budget; templates only gained attributes).
3. Host pages (1280/768/390 opened): operator-edit: placeholders show, help dots unchanged, no overlap. property-new: example placeholders show, layout unchanged. setup-property shot is the police step, not the IČO step, so the wizard IČO was not seen.
4. Deviations: cmd 2 skipped; test file docstring added by hand; local branch was held by another worktree, so work was done detached.
5. Questions: bday vs dd.mm.yyyy unchanged; #stay-fee-settings left at its own size.
6. Owner: open PR.
