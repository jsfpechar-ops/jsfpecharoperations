# 0477 report: UbyPort request XML golden files

Status: review

## Files changed
- App/scripts/ubyport_golden.py (new, generator)
- App/tests/golden/ubyport/cases.json (new, 6 invented cases)
- App/tests/golden/ubyport/*.xml (6 golden envelopes)
- App/tests/test_ubyport_golden.py (new, 3 tests)
- docs/tasks/0477-ubyport-golden-xml.md (brief)

## Commands
- `.venv/bin/python scripts/ubyport_golden.py | tail -3` gave `golden files written: 6`
- `.venv/bin/python -m pytest tests/test_ubyport_golden.py tests/test_soap.py -q --tb=short -x` gave `32 passed in 3.36s`, exit 0, 0 skipped
- `python3 scripts/context_lint.py | tail -3` gave `context lint: OK` (warning: 19 commits touched App/ after last status.md update, orchestrator to update status)

## Cases
eu_single, non_eu_visa, escaping, fallback_dates, batch_three, wsa_header.

## Section 7
- 6 golden files committed: yes
- test fails on one byte change (byte compare of regenerated output): yes
- DB-path test captures the envelope at `_post`: yes (compares to builder on DB rows)
- branch diff lists only section 3 files plus brief: yes

## Deviations
None. Done: steps 1 to 4.

## Questions
None.

## Owner steps left
None. Orchestrator opens the PR.

## Observations in the current XML (not changed)
- Nationality is sent as the 2-letter code (`eu_single` gives `<d:cNati>SK</d:cNati>`). The existing fixture in tests/test_ubyport_dorucenka.py uses 3-letter `GBR`. Check which the spec wants.
- `cResi` renders the country as 2-letter code twice: `..., Brno, CZ-CZ`. Appendix 3 (per the docstring of `compose_residence`) says three-letter code, hyphen, country name.
- `header_from_apartment` on an empty `addr_obec_cast` gives `<d:uObCa i:nil="true" />` (nil, not empty). Expected, but worth confirming with the spec.
