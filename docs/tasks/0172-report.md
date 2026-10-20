# 0172 report

Status: review

- host.css key is now `20261019-0172` and app.css key is `20261006a-0172` in every template (base, public_legal_base, auth_base, cleaning_shared); one key per file.
- `test_static_versions.py --write` now refuses a changed file under an unchanged key; new test `test_write_refuses_a_changed_file_under_an_unchanged_key`; 3 passed.
- `test_host_controls_browser.py`: 1 passed, 0 skipped. Commit 7d1be3b.
- The 0102-evidence cleanup was not needed (git status clean there).
