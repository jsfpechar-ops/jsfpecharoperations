# 0959 report (executor, steps 3 and 4)

Status: blocked. The regression test fails at the switch from the Czech page back to EN. Cause: a product bug in the submit guard, not the discard guard. Not a test fault.

## Changed files
- App/tests/test_guest_browser_e2e.py: added test_0959_discard_warning_cancel_keeps_draft. The regression test is unchanged (the planned dialog change was not applied, see Deviations).
- docs/tasks/0959-report.md (this file), docs/tasks/0959-guest-draft-language.md (blocked reason).
- Commits: 0959 step 3 (test), 0959 step 4 (report), 0959 status (brief reason). Nothing pushed.

## Commands (pass / fail / skip)
- `pytest tests/test_guest_browser_e2e.py -k 0959`: 1 passed (cancel test), 1 failed (regression, line 810), 0 skipped.
- `pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py` (guest row): 569 passed, 1 failed (same regression test), 0 skipped.
- `pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: 16 passed, 0 failed, 0 skipped.
- `python3 scripts/context_lint.py`: OK (WARN lines pre-existing, not from this change).
- `git diff --check`: clean. No static asset changed, so no version regeneration.

## Product finding (exact observed behaviour)
- After the Accept switch to CS, the signature is empty, the tick is unchecked and there is no photo input file.
- Clicking EN on that page sends no request, opens no dialog, leaves the URL at /relang?lang=cs, and the navigation times out after 30 s.
- Cause (from code): App/app/static/signature.js, form submit listener (about lines 127 to 140), calls preventDefault when the signature hidden field is empty. The language menu buttons are submit buttons with formaction, so the switch is cancelled.
- The discard guard (signature.js about line 635) did not fire here. That is correct: nothing was drawn, ticked or chosen.
- Inferred, not tested: a guest who has not drawn a signature cannot switch language with JS on. The brief says the switch works without a drawn signature. Decision needed.

## Acceptance
- Discard warning asks before losing a drawn signature, tick or photo: met for the signature and tick (cancel test passes, dialog text is the CS lang_draft_warning).
- Switch back to EN keeps draft and step: not met (blocked by the finding above).
- Other acceptance items: not verified (the brief's full list was not re-checked in this run).

## Screenshots (in /tmp/ubyhost-b01, not in repo)
- 390 CS (0959-review-cs-390.png): step 3 of 3 Podpis. Name case kept ("Synthetica Testovic"). The summary shows 4 rows; the birth date row is not visible (cause not checked). No horizontal overflow seen. Full-width save button.
- 768 CS (0959-review-cs-768.png): all five summary rows, birth date "1. ledna 1980" present, name case kept, no overflow.
- 1280 CS (0959-review-cs-1280.png): two columns with step list (Vaše údaje Hotovo, Trvalé bydliště Hotovo, 3 Podpis), all rows present, no overflow.
- EN pages and the open language menu at 390: not captured. Not verified.

## Deviations
- The planned change (accept the dialog on CS to EN and assert the warning) was not applied. The dialog never appears in that state, so that assertion would always fail.
- Commit trailers: the brief asked for a Codex trailer. I used the Claude Co-Authored-By and Claude-Session trailers required by the session attribution.

## Done / Left
- Done: cancel test added and passing; guest row run; lint and diff check.
- Left: decide the signature submit guard (signature.js) so the switch works without a drawn signature; then rerun the regression test; EN and menu screenshots; full acceptance check. Owner to decide.
