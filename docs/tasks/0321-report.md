# 0321 report

Status: review
Done: steps 1 to 3. Left: step 3 verification (test_havel_cases.py fails until 0327 adds the guide_* page ids), then section 7 acceptance.

## Files changed

- App/tests/havel_cases.json (new, 75 cases; step 1)
- scripts/havel_eval.py (new, runner; step 2)
- App/tests/test_havel_cases.py (new, shape check; step 3)
- docs/tasks/0321-report.md (this file)

## Commands

- `python3 -c "...len(d['cases'])"` prints 75.
- `App/.venv/bin/python -m pytest tests/test_havel_cases.py tests/test_havel_engine.py -q -rs --tb=short -x` (from App/):
  FAILED in test_the_75_cases_are_numbered_and_well_formed:
  `AssertionError: (1, ['property_calendars', 'guide_stays', 'guide_connect_calendar'])`, extra item `guide_connect_calendar`.
- `App/.venv/bin/python scripts/havel_eval.py | tail -2` (no key): prints `Set UBYHOST_ANTHROPIC_API_KEY to the staging key (it has a spend limit).`
- `python3 scripts/context_lint.py | tail -30`: `context lint: OK` (warnings only).

## Deviations

- Blocked on a missing anchor (brief section 4 step 3 note): `havel.PAGES` lacks 5 ids used by the case file:
  guide_add_property, guide_connect_calendar, guide_finding, guide_guest_links, guide_privacy_requests.
  These are the 0327 ids. Not added here, per the brief's "stop and report" rule.
- Section 7 not ticked.

## Questions

- Confirm 0327 is merged before rerunning the pytest command.

## Owner steps left

- None before rerun. Real eval (0323, step 3) needs the staging key.

- Orchestrator: after 0327 (page ids) was merged into this branch, `pytest tests/test_havel_cases.py tests/test_havel_engine.py` gives 24 passed; section 7 holds.
