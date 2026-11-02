# 0834 report

Status: blocked
Branch claude/project-thread-6ozz7x. Not pushed, no PR.

## Done
- Step 1 (54130d38): migration 0034_apartment_ocr_scan.sql plus the two db.py lines. Problem, see Questions.
- Step 2 (6a775479): doc_ocr.available gates on ocr_scan and policy, plus module docstring line.
- Step 3 (3030e6f4): admin.py allowed field and payload rule.
- Step 4 (2e6ec36b): _property_editor.html switch row.
- Step 5 (655017ed): EN and CS keys apartment.form.ocr_scan.label and .hint.
- Step 6 partly, uncommitted: 3 gate tests (a, b, c) in test_doc_ocr.py; _max_owner sets ocr_scan 1; geometry world sets ocr_scan 1.

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_doc_ocr.py -q --tb=short -x`: ERROR at setup, `sqlite3.OperationalError: duplicate column name: ocr_scan` (app/db.py apply_migrations). Blocks all DB tests.
- Browser and billing commands: not run. Editor test file not chosen (see Questions).
- `python3 scripts/context_lint.py`: not run.

## Questions
1. Step 1 conflict: db.py adds `ocr_scan` to the CREATE TABLE (line ~166) and to the column list (line ~970), but migration 0034 also runs ADD COLUMN. Fresh DBs fail with duplicate column. Existing migrations (e.g. 0032 business_type) are not in db.py. Should I drop the two db.py lines and keep only the migration?
2. Step 6 editor test file: the test-map row "Onboarding, properties" names only the glob test_property_*.py. Candidate: App/tests/test_property_form_save.py. Which file should carry tests (d) and (e)?
3. Step 6 (a)-(c) and the geometry edit are uncommitted until question 1 is answered.

## Owner steps left
- Answer questions 1 and 2, then the executor can finish steps 6 to 9, the browser run with 0 skipped (UBYHOST_BROWSER_EXECUTABLE set), and context lint.
