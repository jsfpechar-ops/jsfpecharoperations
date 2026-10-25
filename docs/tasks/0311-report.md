# 0311 report: Havel engine

Status: review

## Files changed
- App/app/havel_prompt.py (new): HAVEL_SYSTEM_PROMPT, cut verbatim from plan section 4 (lines 91-198).
- App/app/havel.py (new): page map, schema, redaction, request, limits, history signing, validate(), ask().
- App/tests/test_havel_engine.py (new): 17 unit tests.
- docs/tasks/0311-report.md (new).

## Commands (last lines)
- Step 1 prompt check: `True True True True True`
- Step 2 `havel.PAGES` check: `41 True True`
- `.venv/bin/python -m pytest tests/test_havel_engine.py tests/test_ai.py -q --tb=short -x 2>&1 | tail -30`: `25 passed in 0.39s`
- `python3 scripts/context_lint.py 2>&1 | tail -30`: `context lint: OK` (WARN lines are other open briefs and the status.md note; not from this change)
- `grep -n 'log\.' App/app/havel.py`: no output.

## Brief section 7
- [x] havel_prompt.py holds the plan prompt verbatim (five Trues).
- [x] test_havel_engine.py passes (redaction, schema/page enum, guardrails, limits, Monday/1st windows, history signature).
- [x] No `log.` in havel.py.

## Deviations
1. `_PHONE` now has a lookbehind `(?<![A-Za-z\d])`. Without it, `AB1234567` was redacted as `AB[phone 2]`, not `[number 1]` as the brief's test expects. Risk: a phone number directly after a letter is no longer matched as a phone.
2. `ask()` now calls `record_stat("guardrail_fail", today)` on the API-error path too. The brief's test expects `guardrail_fail == 2` for a refusal and a bad-JSON reply, which the brief's code did not record.
3. Route check: no route matched the literal `@router.get("/apartments/{id}")`. The real route is `/apartments/{apartment_id}` (App/app/routes/admin.py:1589), so the page stays. All other 16 paths matched; PAGES stays at 41.
4. Step 3 was done in one commit with the step-2 fixes; the report is a separate commit.

## Questions
- Is the phone-regex lookbehind (deviation 1) acceptable, or should the ID pattern run before the phone pattern?

## Owner steps left
None.
