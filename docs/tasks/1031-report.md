# 1031 report

Status: blocked

## Files changed
- `App/app/templates/base.html`: security prompt markup replaced with the card structure from the brief (step 1, commit `ad8c99a9`).
- `App/app/static/app.css`: the five old `.security-prompt*` lines replaced with the brief's CSS block plus `.admin-dialog.security-prompt { border: 0; }` (step 2, commit `01c676ba`).
- `docs/tasks/screenshots-1031/` (7 PNGs, untracked, not committed).
- `docs/tasks/1031-report.md` (this file).

## Blocker
`App/app/templates/base.html` loads different stylesheets per branch: lines 21-23 load `tokens.css` and `app2.css` (the `body.v2` branch), lines 25-30 load `tokens.css`, `app.css`, `components.css`, `host.css`. The new rules are only in `app.css`. On the host dashboard, which the screenshots render, the card gets none of them: measured dialog width is 390 px at a 390 px viewport (brief: min(100% - 32px, 440px)), option rows are 19 to 38 px tall (brief: min-height 64 px), and the dialog sits in page flow at y about 1650 instead of as a modal. Which sheet the card must live in for `body.v2` is a decision for the orchestrator (the brief names only `app.css`). Not fixed, because that is outside the brief.

## Tests
Not run. Step 3 is incomplete, and the brief's test command depends on the screenshot check passing. Setup note: `App/.venv` was created from `requirements.txt`, `requirements-dev.txt` and `playwright==1.63.0` (pinned in `.cursor/install.sh`), plus `playwright install --with-deps chromium`. `.venv` is git-ignored.

## Screenshots (what I saw)
- `prompt-en-390.png`: dashboard with the "Nothing is being reported to the police" banner; no visible prompt card in the viewport. Viewed.
- `prompt-en-1280.png`, `prompt-en-768.png`, `prompt-cs-390/768/1280.png`, `prompt-en-390-nojs.png`: saved, not viewed.

## Deviations
- Throwaway screenshot script lives in the scratchpad (`/tmp/claude-0/-home-user-jsfpecharoperations/0405aa71-b521-5826-8d1b-19327d272a26/scratchpad/shot_1031.py`), not `/tmp/shot_1031.py`, per the session scratchpad rule. Not committed.
- The script accepted the legal documents and cleared `two_factor_prompted_at` for a throwaway test account in the test database.
- Done: steps 1 and 2. Left: step 3 (stylesheet decision, re-screenshot, geometry check), section 6 tests, context_lint.

## Questions
1. Should the `.security-prompt*` CSS also go to `app2.css` (the `body.v2` branch that the host dashboard uses), or should the v2 branch load `app.css`?

## Owner steps left
None until the question above is answered.
