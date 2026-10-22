# 0239 report: data box return pages

Status: review
Executor: Haiku 5.5 | Branch: claude/project-thread-jf2b3v | Base: c1ebb74 | Not committed (owner instruction).

## Files changed

- App/app/routes/databox_return.py (new): public router, GET and POST for `/stay-fees/databox/done` and `/stay-fees/databox/error`.
- App/app/templates/databox_return.html (new): one auth card on `auth_base.html`.
- App/app/main.py: import added to the `.routes` line; `app.include_router(databox_return.router)` placed before `stay_fees.router`.
- App/app/host_i18n.py: 5 EN and 5 CS `databox_return.*` keys.
- App/app/host_vi_i18n.py: 5 VI keys.
- App/tests/test_databox_return.py (new): 3 tests (6 parametrized cases plus the Czech check).
- docs/context/decisions.md: one line appended (2026-10-22, 0239).

## Commands

- `App/.venv/bin/python -m pytest tests/test_databox_return.py tests/test_host_i18n.py tests/test_stay_fee*.py -q --tb=short -x`: NOT RUN. `App/.venv` does not exist in this checkout.
- `python3 -m py_compile` on the 5 changed Python files: exit 0.
- `python3 scripts/context_lint.py | tail -10`: FAIL.
  `ERROR docs/context/decisions.md: ~2248 tokens > cap 2200.`
  The file was about 2198 tokens before the appended line (word count 1256 at HEAD). The appended line alone pushes it over the cap.

## Acceptance (§7)

- [ ] Both URLs answer 200 signed out, by GET and POST: not verified (tests not run).
- [ ] Posted fields and query values never appear in the page: not verified.
- [ ] EN, CS, VI keys present: present by inspection; i18n tests not run.
- [ ] decisions line added: done. Lint NOT clean.
- Screenshots: not required of the executor.

## Deviations

- Done: steps 1 to 6. Nothing left except the lint fix and the test run below.
- Steps 2 to 6 were applied as written. The §4 step 5 Czech test uses `?lang=cs` instead of a cookie, because `host_i18n.resolve_language` reads the `?lang=` query parameter.
- Step 1 `{% set %}` in the template was left at top level (the brief's fallback was not needed; not verified because no render test ran).
- Per owner instruction, no per-step commits and no PR.

## Questions

1. Decisions cap: `docs/context/decisions.md` is at the 2200-token cap. Someone must compact older lines (orchestrator, or owner approval to edit that file beyond §3) before lint passes.
2. Venv: `App/.venv` is missing in this checkout. Create it, or confirm where the tests should run.

## Owner steps left

- Decide who compacts decisions.md, then re-run `python3 scripts/context_lint.py | tail -10`.
- Create `App/.venv`, then run: `cd App && .venv/bin/python -m pytest tests/test_databox_return.py tests/test_host_i18n.py tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30`.

## Orchestrator review (2026-10-22)

- Built App/.venv; scoped tests: `156 passed, 2 skipped` (the 2 skips are Playwright tests in other stay-fee files).
- Fixed: tests needed `db.init_db()` and `?lang=en` (signed-out default is Czech); the language switch echoed the ISDS query string in its `next` field, now `lang_next` is the bare path.
- decisions.md over cap: compacted the 0001 line and shortened the new line; lint OK.
- Screenshots 390/820/1280/2000 x EN/CS/VI x done/error in project files `databox-return/`, no horizontal scroll. No CSS/JS changed, so no `?v=` keys.
