# 0204 report (push engine, steps 5 to 12)

Status: done

## Done
- Step 5: `App/app/push.py` created verbatim from brief (commit 5588290). `import app.push` OK.
- Steps 6 and 7: `App/app/retention.py` push cleanup, `_push_step`, STEPS entry, cutoff text (one commit, 4d4b4e2).
- Step 8: `App/app/scheduler.py` four edits, `_job_push`, push job every 1 min (10fd842). Import OK.
- Step 9: `App/app/host_i18n.py` alert strings EN/CS (f4cc7aa's sibling 5515a20). Import OK.
- Step 10: `App/app/host_vi_i18n.py` alert strings VI (f4cc7aa).
- Step 11: `docs/ENVIRONMENT.md` section "Urgent alerts (web push)" (b9fe9e4).
- Step 12: `App/tests/test_push.py` created verbatim from brief.

Steps 9 to 11 and 12 were inserted from the brief's own code blocks by script, with each anchor asserted to occur once. Step 6 and 7 share one commit.

## Commands (§6)
1. `pytest tests/test_webpush.py tests/test_push.py tests/test_migrations.py tests/test_db_*.py -q -x`: 63 passed.
2. `pytest tests/test_retention*.py tests/test_privacy_*.py ... -q -x`: 119 passed.
3. `pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_meta_capi.py -q -x`: FAILED.
   `test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects` fails in the
   CSRF primer GET (`tests/conftest.py:142`) with `sqlite3.OperationalError: no such table: apartment`.
   It fails when run alone too. Not verified whether it also fails before 0204.
   The other two files were not reached because of `-x`.
4. `python3 scripts/context_lint.py`: FAIL, not caused by code.
   - `docs/tasks/0204-push-engine.md` is about 13992 tokens, over the 12000 cap.
   - `docs/tasks/0204-cont-1.md` lacks the numbered `## N.` sections the lint expects.

## Deviations
- Stopped at the tool-call checkpoint with command 3 failing. Did not fix code, since the failure is in a CSRF/DB setup path outside §3 and needs a decision.
- Brief Status set to `blocked` (not `review`) because §6 command 3 and the lint are not green.
- Untracked `docs/tasks/0205-push-endpoints.md` and `0206-push-settings-ui.md` were already present and left alone.

## Questions
- Should the owner or orchestrator confirm the `test_host_i18n` failure is pre-existing (run the same file at commit b4b3c48), or allow a fix in the test DB setup?
- Should the two 0204 briefs be split or compacted to pass the lint?

## Owner steps left
- None until the questions above are answered. Then run §6 commands 3 and 4 and the §7 check `git diff --stat` against §3.

## Orchestrator review
- Steps 5 to 12 ran from a continuation note (now removed; the brief is compacted to pass the lint cap).
- The `test_host_i18n.py` failures (3 tests, "no such table: apartment") also fail at 0ab1834, before any push code: pre-existing, logged under K-T01.
- Commands 1 and 2 pass (63 and 119); `test_no_em_dashes.py` and `test_meta_capi.py` pass (33).
