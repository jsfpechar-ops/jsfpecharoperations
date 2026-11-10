# 1068a-cont-2 report

Status: review

## Files changed (`git diff 5252adb4 --stat`, code only)

`App/app/static/app2.css` (+2 lines), `App/app/templates/_property_editor.html`, `App/app/templates/base.html` (`?v=` 1130k to 1130l), `App/app/templates/payments_new.html`, `App/tests/static_versions.json`. Plus this brief, this report and 9 PNGs in `docs/tasks/screenshots-1068a-cont-2/`.

## Commands (last lines)

- `tests/test_static_versions.py --write`: `wrote .../App/tests/static_versions.json (52 files)`; `pytest tests/test_static_versions.py`: `3 passed`.
- Payments tests (8 files): `119 passed in 6.75s`.
- Reviewer correction 2, `UBYHOST_REQUIRE_BROWSER=1` property navigation, property controls, TTLock setup 0954, smart locks page: `59 passed`, 0 skipped. `test_property_navigation_browser.py:209` (`count == 1`) still passes: that fixture is in the `on` state, so neither the deleted link nor the new offline-only amber links render there. The count did not change and the test was not edited.
- `test_layout_lint_browser.py -k "not webkit"`: `4 passed in 242.33s`, 0 skipped, no host findings.
- `test_design_guardrails_browser.py -k "not webkit"`: `1 failed, 10 passed`, 0 skipped. The one failure is the known sandbox finding `guest-new 390 tap-target-small "Cancel"` (43 px), which also fails on main. Not fixed.

## Step 7 measurements (throwaway script, not committed)

- Toast: link-to-X gap 10.8 px at 390/768/1280; the link is on one line at all three widths.
- `/payments/new` without a bank account: the label centre is 0 px off the button centre at every width; the box is 44 px high at 390/768 and 24 px at 1280. Bank QR chip `opacity` 0.5 (disabled), Card chip 1. Gaps between the chips and the sentence, and between the sentence and the button: 18 px and 18 px.
- Property lock (offline, `#lock-setup-state`): the guide link in the amber box is visible at 390 (284x44), 768 (552x44) and 1280 (111x24). Exactly 1 visible `/guide#door-codes` link at each width.

## Per page

- Toast: 390: the text is on one line, with "Add bank account (1 min)" as an underlined quiet link below it and a clear gap before the X; 768: the same; 1280: everything sits on one row and the link has clear space before the X.
- payments-new (no account): 390: the Bank QR chip is visibly greyed against the black Card chip; the sentence comes next, then an underlined quiet "Add bank account (1 min)" that is vertically centred; 768: the same; 1280: the same, left-aligned and above "Get link". It no longer looks like a high pill.
- property-lock: 390: the amber "lock offline" box ends with an underlined "Step-by-step guide". The white note above it no longer has a link, so the link appears once; 768: the same, with the note hidden; 1280: the same.

## Deviations

- Reviewer corrections 1 to 4 were added to the brief (commit "step 1"). Correction 1: the link in `.prop-sec-missing` was deleted and the grep expects `2`.
- Correction 3: I kept `ui-btn ui-btn-quiet ui-btn-compact`. Below 1024 px the 100 % width rule stretches its tap box, but the quiet variant has no fill or border, so by eye it reads as a short underlined text link, not a bar. This markup is the same as the toast and invoice fix links.
- The measuring script ran as a temporary file in `App/tests/` so the conftest fixtures would load. It was deleted before commit.

## §7 Acceptance

- [x] quiet button, label centred
- [x] chip opacity 0.5 / 1
- [x] guide link visible at 390/768/1280, one per width
- [x] toast gap ≥ 8 px at all widths
- [x] diff only §3 files; app2.css +2 lines; `?v=` bumped; static versions green
- [x] lint and guardrails green, 0 skipped (known Cancel 43 px excepted); payments green
- [x] 9 screenshots described
- [x] no added `paid` line in code

## Design-system checklist (§5)

- [x] Extends the host shell; no `<style>` and no raw colour (opacity only).
- [x] Header unchanged.
- [x] One Save per form (unchanged).
- [x] No fine print added.
- [x] 12 px between neighbours (18/18 measured); toast link to X ≥ 8 px within a control row.
- [x] 390/768/1280 checked, no sideways scroll.
- [x] Layout lint green, 0 skipped; screenshots inspected.
- [x] No new keys.
- [ ] CI watched: for the orchestrator.

## Owner steps

None.
