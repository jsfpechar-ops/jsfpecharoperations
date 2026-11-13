# 1205 report: lock vulnerability bumps

Status: review (pip-audit not run, see Deviations)
Branch: exec-1205c (base exec-1205b, 7a31f97a)

## 1. Files changed

- `App/requirements.txt`: appended `pillow==13.0.0` (commit 7ae66fc8, `1205 step 1`).
- `App/requirements.lock`: only the three vulnerable entries replaced (pillow 12.3.0 to 13.0.0, pyasn1 0.6.4 to 0.6.5, certifi 2026.7.22 to 2026.10.18). New entries from a pip-compile of those three pins only (`--generate-hashes`, scratch dir). Header and `# via` lines unchanged.
- `docs/context/known-issues.md`: K-O04 row, "Pillow undeclared; " removed. `scripts/context_lint.py`: OK.
- `docs/tasks/1205-report.md`: this report.

## 2. Commands run (last lines)

- `pip-compile --allow-unsafe --generate-hashes --no-header --no-annotate` on three.in: output holds exactly certifi, pillow, pyasn1.
- `git diff --stat`: 1 file (App/requirements.lock), 90 insertions, 94 deletions.
- `git diff App/requirements.lock | grep -E '^[-+][a-z0-9_.-]+=='`: `-certifi==2026.7.22`, `+certifi==2026.10.18`, `-pillow==12.3.0`, `+pillow==13.0.0`, `-pyasn1==0.6.4`, `+pyasn1==0.6.5`.
- `pip install -q --require-hashes -r App/requirements.lock` (fresh venv, Python 3.13.18): succeeded, no errors.
- `pip install -q -r App/requirements-dev.txt`: succeeded.
- `pip check`: `No broken requirements found.`
- pytest group 1 (passport, guide photos, doc_ocr, validation, property page photos, guest guide view): `124 passed, 127 warnings`.
- pytest group 2 (guide translate, property page, payments dashboard, payment request model, payment services): `54 passed, 1 skipped`.

## 3. Acceptance (section 7)

- [x] `pip install --require-hashes -r requirements.lock` succeeds.
- [x] Both pytest groups pass (0 failed); 1 skip in group 2, not investigated.
- [ ] pip-audit: not run.
- [x] `python3 scripts/context_lint.py`: OK.

## 4. Deviations

- Method changed per orchestrator: three-package pip-compile, not a full lock regeneration. The brief's `--upgrade-package` header restore was not needed.
- pillow entry has 83 hash lines (was 87).
- pip-audit 2.9.0 was not in scratch and was not run. `--strict` audit still needed before merge.
- Test-map names `test_payment_qr.py`, `test_stripe_connect.py`, `test_payment_links.py` which are not in App/tests; not run. Group 2 used the existing payment files.
- Lock drift: a full pip-compile of requirements.txt also changes anthropic, boto3, botocore, cryptography, fastapi, psycopg, python-multipart, reportlab, starlette, stripe; not done here, owner decision.

## 5. Questions

- Run pip-audit (owner or next executor) before marking ready.

## 6. Owner steps left

- Review, then open the draft PR per the brief's owner steps once pip-audit is green.
