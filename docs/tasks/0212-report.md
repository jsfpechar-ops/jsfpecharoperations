# 0212 report: calm, readable wizard ledes

Status: review

## Files changed

- App/app/templates/setup_wizard/stay_fee.html (dropped `setup-wizard-fee-intro`)
- App/app/static/host2.css (deleted the two fee-intro rules; appended weight 400 rule for `.setup-wizard-lede` and `.setup-wizard-instruction`)
- App/app/templates/base.html (host2 key `20261021-0207` to `20261021-0212`)
- App/tests/static_versions.json (regenerated with `--write`, 32 files)
- App/tests/test_onboarding_wizard_browser.py (two pins: fee lede vs page heading, lede weight 400)

docs/catalog.json and the design lint legacy lists were not changed (lint was OK as is).

## Commands (last lines)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py -q --tb=line -rs`
   ```
   ........................................................................ [ 93%]
   .....                                                                    [100%]
   77 passed, 1 warning in 119.85s (0:01:59)
   ```
   0 skipped.
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=line`
   `6 passed, 1 warning in 0.23s`
3. `python3 scripts/design_lint.py`: `design lint: OK`
4. Evidence restore: `git checkout -- docs/tasks/*-evidence`, untracked PNGs under docs/tasks/ deleted.

## Acceptance (§7)

- [x] Ledes and instructions render at weight 400 on every wizard step; the stay-fee lede matches the others. §6 passes.

## Screenshots

21 changed `-390.png` evidence files were copied to `/mnt/project-files/onboarding-screens-0212/` before restore. No PNG is committed.

## Deviations

- Commit messages are `0212 step k: ...` with trailers, not the bare `NNNN step k` form. Final commit is `0212 calm wizard ledes`.
- Brief §5 did not name the browser tests to rerun the step-4 pin; the run above covers them.
- Executor.md asks for a PR; the brief says do not push, so no PR was opened. Owner must push.

## Questions

None.

## Owner steps left

1. Review commits 1cee1bd..HEAD on claude/project-thread-cf47ju.
2. Push the branch and open the PR, then merge with `scripts/merge-pr-on-green.sh`.
