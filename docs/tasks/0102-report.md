# 0102 report: Onboarding wizard

Status: review

## Files changed

```
 docs/tasks/0102-onboarding-wizard.md               |  (brief)
 docs/tasks/0102-evidence/*.png                    | 28 screenshots
 App/app/routes/onboarding_wizard.py               | new
 App/app/templates/setup_wizard/*                   | new (9)
 App/app/property_setup.py, admin.py, main.py       | wizard + redirects
 App/app/templates/_property_overview.html          | continue card, guest link
 App/app/templates/_property_setup_guide.html       | deleted
 App/app/host_i18n.py, host.css, base.html          | strings + styles + ?v
 App/tests/test_onboarding_wizard_browser.py        | new
 App/tests/test_property_setup_guide_browser.py     | removed
 + 12 test files updated for wizard redirects/overview
```

(`git diff --stat origin/claude/quirky-lamport-9svmd1...HEAD` — 62 files, ~+1382/−1088 lines.)

## Commands (last lines)

**§6 subset** (`UBYHOST_REQUIRE_BROWSER=1`, mock UbyPort, staging, scheduler off):

```
............................................................
60 passed, 1 warning in 81.99s
```

**Full suite + coverage:**

```
TOTAL                             17575   1696    90%
Required test coverage of 86% reached. Total coverage: 90.35%
3 failed, 3437 passed, 15 skipped, 7 warnings in 804.95s
```

Failures (also on `origin/claude/quirky-lamport-9svmd1` without 0102 CSS): `test_host_feedback_browser` (CS `data-feedback-live` empty), `test_host_fit_browser`, `test_host_list_layouts_browser` (CS row height 109px vs ≤72). Not wizard-related.

**Ruff / context lint:**

```
All checks passed!
context lint: OK
```

## §7 acceptance

- [x] Add property → lands on Step 2 of 8 · Connect your calendar (step 1 done from create data).
- [x] One primary filled button per step; optional Skip; Back; no property tabs on wizard pages.
- [x] Guest link step: full URL + PIN cards + copy message; Overview uses copy button, no `/l/` path.
- [x] Try-it demo stay flow; `test_demo_stay_exclusion` unchanged in subset.
- [x] Police fields on police step; waiting outlined button + note; done shows waiting until complete.
- [x] Banner removed; compact continue card when incomplete; complete properties show no card.
- [x] Browser test journey EN+CS at 390/1280, geometry widths, screenshots in `docs/tasks/0102-evidence/` (steps 01–07; door_lock screenshots not captured separately — step uses existing lock UI).
- [ ] Full suite green on CI (3 pre-existing/env browser geometry failures in this VM; §6 subset green).

## Deviations

- `base.html`: only `host.css?v=20261013-0102` bump (allowed by brief).
- `_form_return_to`: re-attaches safe URL fragments stripped by `safe_local_path` (fixes inline automation-timing `return_to` with `#property-summaries`).
- Evidence: 28 PNGs (calendar→done × EN/CS × 390/1280); no dedicated `door_lock` filename.

## Questions

- None.

## Screenshot paths

`docs/tasks/0102-evidence/01-calendar-{en,cs}-{390,1280}.png` through `07-done-{en,cs}-{390,1280}.png`.
