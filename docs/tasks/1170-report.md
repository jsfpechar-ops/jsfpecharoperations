# 1170 report: Hetzner in the /subprocessors register and the ROPA

Status: review
Executor: Haiku 5.5. Legal status: DRAFT, owner + lawyer sign-off required; never mark ready.

## 1. Files changed

- App/app/routes/legal.py (step 1, `hetzner` last in SUBPROCESSOR_IDS)
- App/app/subprocessors_i18n.py (steps 2 and 3, version 1.3, effective 15 December 2026, five hetzner_* keys en and cs)
- App/tests/test_legal_contents.py (step 4, version 1.3 assertion, new Hetzner render test)
- docs/privacy/ROPA.md (step 5, Transfers row, Backups row, open question for counsel)
- docs/vendors/README.md (step 6, one Hetzner row)
- docs/tasks/1170-report.md (this file)

## 2. Commands

- Legal test set (App/, scratch venv with requirements.txt, no conftest issue): `68 passed in 4.48s`, 0 failed, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none from this change).
- `git diff --stat 142f89a HEAD`: 6 files, 340 insertions, 7 deletions (incl. the brief file from the base commit).

## 3. Section 7 acceptance

- [x] `hetzner_` count = 10
- [x] `"hetzner",` in routes/legal.py = 1 line
- [x] Version 1.3 / Verze 1.3 count = 2
- [x] ROPA Hetzner count = 3; vendors = 1
- [x] Tests pass; diff lists only section 3 files

## 4. Deviations

- Test venv created under /tmp/claude-0 (outside the repo), not the scratchpad. Nothing added to the repo.

## 5. Questions

None.

## 6. Owner steps left

See brief "Owner steps" 1 to 6 (lawyer review, DPA signature, notice, effective date, no drill before effective date, then ready and merge).
