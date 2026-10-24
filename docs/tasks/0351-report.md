# 0351 report: guest handoff

Status: review

## Files changed (vs 0350 head)

- Created: `App/app/guest_handoff.py`, `App/app/routes/guest_questions.py`, `App/app/templates/guest_questions.html`, `App/app/templates/guest_question.html`, `App/tests/test_guest_handoff.py` (copied from `docs/plans/0351-files/`)
- Edited: `App/app/leon.py` (hook), `App/app/alerts.py` (one row), `App/app/mail.py` (kind in `KINDS` and `HOST_KINDS`), `App/app/main.py` (import, router before guide router), `App/app/routes/guest_guide.py` (`questions_open`), `App/app/templates/guest_guide.html` (second button), `App/app/host_i18n.py`, `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (via `add_handoff_i18n.py`), `docs/design/catalog.json`, `App/tests/test_design_guardrails_browser.py`, `docs/context/test-map.md`, `docs/plans/guest-guide.md` (todo to review)
- No migration (next free: migration 0018, not used).

## Commands (last lines)

- Step 1 preflight: `guest_question` count 7, `guest_guide_routes.router` count 1, `next free: task 0370 | migration 0018`.
- `pytest tests/test_guest_handoff.py`: `14 passed, 1 warning in 5.02s`.
- `pytest` the 11-file set: `3 failed, 178 passed`. All 3 failures are in `tests/test_host_i18n.py` (the known Vietnamese failures: `test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_accepts_vietnamese`). Not fixed.
- Browser guard `-k every_host_page`: `1 failed`. Chromium is not installed here: `Executable doesn't exist at /opt/pw-browsers/chromium-1134/chrome-linux/chrome`. Not run; CI or the reviewer must run it (0 skipped was not reached).
- `design_lint.py`: `design lint: OK`.
- `context_lint.py`: `context lint: OK`.
- Ruff (E9,F63,F7,F82,F401,F841): `All checks passed!`.

## Section 7 acceptance

- [x] `test_guest_handoff.py` passes (14).
- [x] `grep -c 'ui-' guest_question.html` = 9 (above 0); design lint OK.
- [x] Log grep for text/answer/summary = 0.
- [x] Em dash count in the four new files = 0.

## Deviations

- Step 4 once created a stray file inside the worktree by a bad path; it was deleted before any commit. Nothing stray is committed.
- Commits per step: `0351 step 2` to `0351 step 10`, plus this report commit (`0351 step 11`). Not pushed.

## Questions

- None blocking. Browser guard not run locally (see above).

## Owner steps left

- Nothing new beyond the brief's section 9 (merge with `scripts/merge-pr-on-green.sh` once CI is green; production Leon stays off until 0352).
- Review (orchestrator): 390 px screenshots of the questions list and one question, scrollWidth 390; browser guard every_host_page 1 passed with Chromium.
