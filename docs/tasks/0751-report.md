# 0751 report: phone v2 stay page (Airbnb reservation style)

Status: review (not committed, not pushed, no PR: orchestrator said do not commit or push). Screenshot step not done (see Deviations).

## Files changed
- App/app/templates/reservation_detail.html: copy round button removed from `.stay-top`; pill line `ph-hide`; facts rewritten as `card facts stay-dates` (Arrival/Departure cells + `tot` line); guest list gets class `guests`; door code wrapped in a div; bottom Request payment list `ph-hide`; phone-only menu items "Copy guest link" (`ph-only`, data-copy="stay-link") and "Request payment" (`ph-only`).
- App/app/static/app2.css: `right:64px` to `right:16px` for the phone menu; dead rule `.sub.sub-phone{margin-bottom:10px}` removed; new `@media (max-width:1023px)` block at the end of the 0529 section, prefixed `body.v2 .host-stay-detail`, values from mockup pobyt. No `!important`. No new classes.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: one new key `stay.detail.facts.guests` ("%(count)s guests" / "%(count)s khách"). No cs file carries the nights key.
- App/tests/v2_mockup.py: `stay` entry gets `phone_mockup`, new `phone_selectors`; `missing_ok` `.stay-door-card`; old `stay:.facts@*` and `stay:.card@*` overrides removed; new text-dependent overrides under `# text-dependent: ... (0751)`.

## Commands (tails)
1. `pytest tests/test_0710_v2_mockup_match_browser.py -k stay`: `22 passed, 2 failed` (the 2 failures are `stays-320` and `stays-390`, the stays LIST entry, not stay detail; selectors `.mh .big`, `.stay .in b`, `.pill.p-warn`). All `stay-320/390/768` pass with 0 skipped.
2. All stay and reservation_detail test files plus `test_design_guardrails_browser.py` and `test_host_wide_geometry_browser.py` (browser and non-browser): `4 failed, 280 passed`, 0 skipped. The 4 failures are all on the stays list (/reservations): `test_design_stays.py:10` and `test_stays_empty_workspace.py:232` (`<div class="chips">` missing), `test_host_stay_actions_browser.py:191` (`.stays-phone a.row` not visible), `test_host_wide_geometry_browser.py:639` (`.stays-phone .list a.row` count 0). None is on the stay detail page. Not verified against a baseline, because the other executor (0750) is editing the stays list at the same time.

## Deviations
- No commit per step (orchestrator instruction). No PR.
- Screenshot `docs/tasks/screenshots-0751/stay-390.png` NOT taken. The 0710 screenshot test writes into `screenshots-0710` and would overwrite files. Owner or orchestrator to run it with a dedicated step.
- Check-in/out time line omitted: the stay context has no check-in time and no new query was added.
- Labels stay "Arrival" and "Departure" (existing keys), not "Check-in" and "Check-out".
- Dead rules: only the `sub-phone` margin rule was deleted. Other phone rules kept (desktop shares them).
- Text-dependent overrides added (fixture copy vs demo copy): `stay:.stay-dates@320/390` height, `stay:.stay-dates .tot@320` height, `stay:.police-card@320/390` height, `stay:.guests .row@320/390` height, `stay:.guests .row b` and `small` widths @320/390. Values are the app's measured sizes.
- Not run: `test_static_versions` and `design_lint` (orchestrator bumps versions).

## Owner steps left
- Run the screenshot step (`UBYHOST_SHOTS_V2=1` with the 0710 test, or a dedicated script) and save `docs/tasks/screenshots-0751/stay-390.png`.
- Check the 4 stays-list failures after 0750 lands.
