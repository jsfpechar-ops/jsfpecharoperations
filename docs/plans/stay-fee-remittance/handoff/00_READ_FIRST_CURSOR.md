# Cursor: install the stay-fee core from this folder (step 1)

This folder (`docs/plans/stay-fee-remittance/handoff/`) is a delivery package, not final repo content. Do this first, on a new branch `feat/stay-fee-core` from `main`. Do not push to `main`.

1. Copy every file under `handoff/files/` to the same path from the repo root. Example: `handoff/files/App/app/db.py` -> `App/app/db.py`; `handoff/files/docs/plans/stay-fee-remittance-design/DESIGN.md` -> `docs/plans/stay-fee-remittance-design/DESIGN.md`. Overwrite existing files. 13 files: 6 new, 7 edited (`db.py`, `validation.py`, the plan, and the two `stay-fee-document*` mockups as html + jpg).
   - Do not edit any of the 13 files while copying. They were tested as they are.
   - `handoff/stay-fee-remittance-core.patch` is the same change as a git patch. Use it only if copying fails.
2. Check the result: `git status` shows exactly those 13 files (plus the `handoff/` folder). Nothing else should change.
3. Run from `App/` with the Python 3.12 venv:
   `python -m pytest tests/test_stay_fee.py tests/test_db_upgrade.py tests/test_payments.py tests/test_host_i18n.py -q`
   Expected: 60 passed. Then run the whole suite and note failures that also fail on `main`.
4. Run `python ../docs/plans/stay-fee-remittance-design/build_sample.py` and confirm the PDF looks like `handoff/sample-hlaseni-invoice-companion.pdf` (one A4 page, Invoice companion design).
5. Delete the `handoff/` folder from the branch (it was only for delivery) and commit `feat: stay-fee remittance core (calculator, Invoice companion PDF, tests, plan v2)`. Open a PR into `main`.
6. Report: files changed, test results, anything unexpected.

Then continue with steps 2-8 in `docs/plans/stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md` (section 13). The copy-paste prompts per step are in `handoff/01_CURSOR_PROMPTS.md`.

Rules for the whole feature: host-only calculator, guests see nothing, rate per property with 0 = off, never edit `stay-fee-remittance-design/DESIGN.md`, one PR per step. If the plan and the code disagree, stop and ask.
