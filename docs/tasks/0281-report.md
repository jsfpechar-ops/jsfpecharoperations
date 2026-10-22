# 0281 report

Status: review

## Files changed
- App/app/static/host2.css (append, card borders)
- App/app/templates/base.html (host2.css v key to 20261022-0281)
- App/tests/test_0281_card_borders_browser.py (new)
- App/tests/static_versions.json (regenerated, see Deviations)

## Commands
- Step 2: `shots.py ... --pages "/apartments,/entities,/entities?edit=1" --widths 390,820,1024,1280,2000` last line: `24 shots, 0 with problems`
- Step 3/§6: `pytest tests/test_0281_card_borders_browser.py tests/test_static_versions.py tests/test_design_properties.py tests/test_design_guardrails_browser.py -q -rs` last line: `17 passed, 1 warning in 67.61s` (0 skipped)

## Brief §7
- [x] Cards outlined at 390 on /apartments and /entities (checked in shots and test). 820 shots taken, not viewed; desktop shots taken, not viewed.
- [x] Buttons never cover the business name (overlap probe on /entities?edit=1 passes).
- [x] Shots in /mnt/project-files/notify-sign/0281/ (report.json present).

## Deviations
- Step 3 test run needed `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`: the venv's Playwright expects a chromium build that is not installed.
- test_static_versions.py failed after the step 1 version bump. Ran its own `--write` command, which changed App/tests/static_versions.json (not named in the brief). Commit includes it.
- Not done: the push and PR step. Executor rules say do not push; the owner or orchestrator must push the branch and open the PR.

## Questions
None.

## Owner steps left
1. Push claude/project-thread-j2cl8a and open the PR (use scripts/merge-pr-on-green.sh to merge only when green).
2. After deploy, open Properties on the phone: each property is a framed card.
