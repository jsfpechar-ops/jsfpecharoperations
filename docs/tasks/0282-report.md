# 0282 report

Status: blocked
Branch: claude/project-thread-j2cl8a | Steps done: 1 to 8 (shots taken). Stopped at §6 design lint.

## Files changed
- App/app/static/fonts/DancingScript.ttf, LICENSE-DancingScript.txt (new, step 1)
- App/app/templates/_entity_business_fields.html (macro signature_fields, step 2)
- App/app/static/host.js (pad block replaced, step 3); App/app/templates/base.html (host.js and host2.css keys, steps 3 and 4)
- App/app/static/host2.css (appended, step 4)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (entity.signature.* keys, step 5)
- App/tests/test_0282_signature_dialog_browser.py (new, step 6)
- docs/context/decisions.md (one line, step 8)
- App/tests/static_versions.json (regenerated with --write, see Deviations)
- docs/tasks/0282-report.md (this file)

## Commands (last lines)
- `pytest tests/test_0282_signature_dialog_browser.py -rs`: `1 passed` (0 skipped)
- `pytest test_fee_signature_0209, test_stay_fee_signature, test_static_versions, test_design_lint, test_design_guardrails_browser` (first run, after the 0282 test): `1 failed, 14 passed`; failure is test_static_versions, fixed by the --write run
- After --write, same group with -x: `1 failed, 15 passed`; failure is test_design_lint (below). test_design_guardrails_browser.py was not reached.
- `pytest test_design_setup_wizard_browser.py test_onboarding_wizard_browser.py` with UBYHOST_REQUIRE_BROWSER=1: `77 passed, 1 warning in 168.29s`, 0 skipped
- `python3 scripts/context_lint.py`: `ERROR docs/context/decisions.md: ~2239 tokens > cap 2200` then `context lint: FAIL`

## §7 acceptance
- [x] Locked, greyed preview; no visible canvas before Edit (test)
- [x] Edit opens a dialog; Type and Draw both save a PNG (test)
- [x] Font loads via document.fonts.check (test); served from /static/fonts/
- [x] Shots in /mnt/project-files/notify-sign/0282/ (shots.py: 6 shots, 0 with problems; dialog-type-390.png and dialog-type-1280.png)
- [ ] Not viewed: I did not open the screenshots (brief asks to look at each once).

## Deviations
- App/tests/static_versions.json regenerated with `.venv/bin/python tests/test_static_versions.py --write` (allowed).
- test_fee_signature_0209.py needed no assertion change.
- Done: steps 1 to 8. Left: §6 design lint and context lint, and the screenshot review.

## Questions
1. Design lint fails: `scripts/design_lint.py` S1 rejects any `font-family:` in host2.css that does not start with `var(`, and the @font-face in step 4 has a literal family name. Fix needs either the @font-face moved to App/app/static/tokens.css (not in the brief's file list) or a lint exemption. Owner decision needed.
2. Context lint: decisions.md is over its 2200-token cap after the step 8 line. Compaction needs a file outside the brief's list. I did not check whether the base was already over the cap.

## Owner steps left
None until questions 1 and 2 are answered. No PR opened, nothing pushed.

Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JpzT2hdU1n57BJdfYc3L4S
