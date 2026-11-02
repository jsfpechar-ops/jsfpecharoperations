# 0834 report (sections A and D backend)

Status: blocked (context lint fails, see Questions). Nothing committed or pushed, per coordinator.

## Files changed
- `App/tests/wizard_taps.py` (new): wizard baseline measurement, prints `WIZARD_TAPS {...}`, asserts nothing about the target.
- `App/app/ruian.py` (new): RÚIAN suggest, cache, rate-limit helpers, `UBYHOST_RUIAN_ENABLED` gate.
- `App/tests/test_ruian.py` (new): 9 mocked tests.
- `App/app/routes/admin.py`: import line and `GET /apartments/ruian-suggest` (placed above `/apartments/{apartment_id}`).
- `docs/ENVIRONMENT.md`: one row for `UBYHOST_RUIAN_ENABLED`.
- `docs/context/decisions.md`: one line, "proposed, awaiting owner".
- `docs/tasks/0834-report.md` (this file).

## Commands (last lines)
- `pytest tests/test_ruian.py tests/test_ares.py tests/wizard_taps.py -q -rs`: `24 passed in 8.35s`, no skips.
- `python3 scripts/context_lint.py`: `FAIL`. Errors: decisions.md ~2256 tokens > 2200 cap; the brief file lacks a `Status:` line.

## Baseline (before any change, section A)
- Steps defined: 8. Walk (existing `walk_to`, to "done") visited 5 steps: calendar, automation, door_lock, guest_link, try_it. 5 POSTs.
- Fields: 56 controls, all 56 counted required-or-empty. Choice taps: 0.
- Caveat: every step page reports exactly 7 controls, so the counter may be picking up layout controls. Verify before using these as the "before" numbers.
- Fixture: pre-filled `_full_apartment`, not a fresh apartment. Cheapest answers from scratch were not measured.

## Deviations
- The route does one `findAddressCandidates` call and returns the structured attributes inline. The brief's suggest-then-lookup-per-pick would cost up to 6 extra requests.
- The baseline uses the pre-filled fixture (see above).

## TODO-verify (unconfirmed, outbound blocked here)
- `ruian.py` `_FIND_URL`: the ČÚZK GeocodeSOE URL.
- `ruian.py` `_ATTR_KEYS`: the ČÚZK attribute names. Field keys (street, house_no, orientation_no, zip, town, district_part, okres) must be aligned with the property form in the parked UI part.

## Privacy and limits
- Only the typed address text leaves the app. Nothing is stored. Rate limit 60/h per user (scope `ruian`). In-memory cache 24 h, keyed by lowercased query. Any error returns `[]`. Anonymous requests get 401.
- PR reason for the outbound request: property address lookup on the host property form.

## Questions
- `decisions.md` is over the lint cap. My line may have tipped it; the owner or orchestrator should compact it.
- Do not commit until the lint passes and the owner confirms the ČÚZK URL and terms.

## Owner steps left
1. Confirm the ČÚZK URL, attribute names and terms; approve or reject the "proposed" decision line.
2. Compact `decisions.md` below 2200 tokens; add `Status:` to the brief; rerun `python3 scripts/context_lint.py`.
3. Parked, not built: sections B, C, the JS and UI part of D, screenshots, and `test_static_versions.py` (no CSS or JS changed).
