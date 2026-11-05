# 0971 report (batch B13)

Status: blocked

Reason: token checkpoint reached after step 1. Nothing from steps 2 to 4 was applied.

## Done

- Step 1: created the venv symlink `App/.venv` (git-ignored, not committed). All 11 anchors from brief section 2 were found with `grep -cF` (counts 1 each):
  - `App/app/templates/_components.html`: `{% macro copy_icon() %}`
  - `App/app/templates/cleaning_settings.html`: the `help_tip` import line, `<p role="status">{{ ct('saved') }}</p>`, `<div class="cleaning-page cleaning-form-page settings-lane">`, `{% if code.value or code.pending %}<details class="cleaning-remove">`
  - `App/app/static/app.js`: `icon.className = "copy-state-icon";`, `  function initPage() {`, `    initSectionNotice();`
  - `App/app/cleaning_i18n.py`: `    "cancel": [`
  - `App/app/templates/base.html`: `app2.css?v=20261105-0961a`, `app.js?v=20261104-0955g`
  - Test files and `static_versions.json` exist.
- Status line of the brief set to blocked.

## Not done

- Step 2: patch not saved to `/tmp/ubyhost-b13/0971.patch`, so `git apply --check` was not run and nothing was applied or committed. The first transcription attempt was rejected by the tool and also contained one line that is not in the brief (a `code_source_ttlock ... if False else` variant in the `code-source-hint` help_tip). The next session must copy the patch verbatim from brief section 4 (lines 70 to 565 of `docs/tasks/0971-feedback-forms.md`) and verify with `git apply --check` before applying.
- Step 3: `test_static_versions.py --write` not run.
- Step 4 and section 6 commands a to e: not run. No browser test ran, so 0 skipped is not verified.
- Section 7 acceptance: all items unverified. No screenshots were taken or inspected.

## Deviations

- Done: steps 1 to 1. Left: steps 2 to 4. A fresh session continues from step 2.
- The brief's executor guide asks for a commit per step. No step commit was made, since no patch step ran. This commit only holds the report and the status line.

## Questions

- None.

## Owner steps left

- None yet. After the batch is finished and reviewed, the owner merges with `scripts/merge-pr-on-green.sh` and deploys by hand (brief, Owner steps).

## git diff --stat

- `docs/tasks/0971-feedback-forms.md` (status line) and `docs/tasks/0971-report.md` (new).
