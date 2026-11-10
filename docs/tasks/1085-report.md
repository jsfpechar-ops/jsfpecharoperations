# 1085 report: police letter paste, check and confirm flow

Status: review

## Files

`App/app/routes/admin.py`, `App/app/templates/_property_editor.html`, `App/app/templates/_police_letter_figure.html` (new), `App/app/static/host.css`, `App/app/static/app.js`, `App/app/templates/base.html`, `App/tests/static_versions.json`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/tests/test_police_letter_flow.py` (new). `origin/main` (with 1088, PR #879) merged first; all anchors found.

## Commands (from `App/`)

1. Section 6 list (flow, parser, property form, i18n, static versions…): `366 passed, 1 skipped` (the skip is the Playwright import in `test_host_ux_acceptance.py`, before Playwright was installed locally). `test_police_letter_flow.py` alone: `40 passed`.
2. Filing row (`test_ubyport_* test_police_* test_endtoend test_submission_*`): `399 passed, 2 warnings`.
3. Host pages row (`test_host_*.py`, Playwright 1.63.0 + Chromium): `2 failed, 246 passed, 1 skipped`. See Deviations.
4. `python3 scripts/context_lint.py`: `context lint: OK` (only warnings about other briefs and status.md).

## Section 7

- [x] Auto test only at `apartment_update`'s final exit, never with `setup_step`; `/test-connection` skips a new letter login with no password.
- [x] Discard warning wired (source pin); the check-answers page starts dirty.
- [x] Each filled value shows its source and "Check this against your letter"; no printed mark is filled.
- [x] Nothing saves until every pre-filled value is ticked, on both paths; forged line numbers never crash.
- [x] Auto test only with a password in the same save, once; ok, refused, unreachable in plain words; other saves as on main.
- [x] Read-only proof green: only the three read-only methods, guest unchanged, no submission.
- [x] Text and password never stored, logged, audited or echoed, also when the parser raises; `no-store`, 422, 400.
- [x] Figure: real labels, fake values, tokens only; copy in `en cs vi`.
- [x] `git diff --stat origin/main` touches only section 3 files (plus this report and the brief).

## Deviations

- Host row: `test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber` and `test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state` (one finding: guide page, `cs`, 390 px, a `help-tip-btn`) fail in this container. Both fail identically on a clean `origin/main` (a3806a2a) checkout with the same venv, so this branch did not cause them. Not fixed (outside the brief). The one skip is `test_host_copy_corrections.py:369` (its own `UBYHOST_REQUIRE_BROWSER` condition). WebKit could not be downloaded here; CI must run the browser jobs.
- `#sec-police` is opened with `settings_section="reporting"` instead of `inline_flash_section="police"`: both together would print `open` twice on the `<details>`.
- `letter_check` (and so `data-dirty-start`) is set only when at least one value was pre-filled, not on `empty`, `too_long`, `failed` or an all-missing letter: nothing unsaved is on the page there.
- After 1088 the parser never returns markup in `source`, so the "`<b>` comes back escaped" test uses a monkeypatched result and the refused-save path (`letter_src_*`).
- Posted `letter_src_*` values lose every Unicode category C character (control and format), slightly more than "control characters".
- On a refused save only the listed rows and the password row are rebuilt; the plain lines of unfilled fields are not posted, so they are not shown again.
- The `/test-connection` lockout guard applies only when that post also saved (it carried credentials).

## Attempt 2 (UX gate and CI fixes)

- B1/B2/S6: every helper rule moved to `app2.css` under `body.v2` (the editor is a v2 page; `host.css` is back to main's bytes and key). Type tokens for HTML text; the SVG keeps 8/9 user units, with a comment. Key `app2.css?v=20261110-1085e`.
- B3/B5/S5: the two `details` are plain disclosure rows (no border box, same left edge as their content, full grid width at 768+), figure margin 0, legend `ol` padding `--space-5`; 16 px under "Read the letter".
- B4 and required star: the tick is `div.checkline > input + label` with the `req-star`; label is flex, 44 px high, box 20 x 20.
- S1: `police_letter.check_against` deleted (template and three languages). S2: password row dropped. S3: one save error per unticked value.
- S4: the brief says a refused unconfirmed save answers **400** (422 is the paste route). Kept 400; pinned in `test_two_missing_ticks_are_two_errors` and in the browser test.
- New: after a paste the page starts on `sec-police` at 768+ (`data-start-section`); before, the desktop editor showed the fee section and hid the check block.
- `test_property_navigation_browser.py`: its form parser now skips a control whose `form=` names another form (as a browser does), so `letter_text` is not counted in the settings form. `letter_text` is never sent with Save.
- Browser test `test_the_letter_helper_is_styled_in_the_browser` (in `test_police_letter_flow.py`): `.pl-sheet` fill, `.police-letter-name` display, sizes, no sideways scroll, 422 and 400 at 390/768/1280.
- Screenshots: `/mnt/project-files/reviews/1085/v2/{helpers-open,check-block,refused-save}-{390,768,1280}.png`. Seen: figure readable with no overlap, 360 px wide at most; rows flush with their summaries; ticks and errors clear. The crops show the fixed bottom nav across the middle (an element-screenshot artefact).

Attempt 2 runs (`UBYHOST_REQUIRE_BROWSER=1`, Chromium, 0 skipped):

- `test_layout_lint_browser.py test_police_letter_flow.py test_required_stars.py test_static_versions.py test_host_i18n.py`: `69 passed`.
- `test_host_geometry.py test_host_property_controls_browser.py test_host_ux_acceptance.py test_host_fit_browser.py test_host_help_browser.py test_property_navigation_browser.py` plus the section 6 list: `2 failed, 428 passed`. The two: `test_host_ux_acceptance` (the known guide, `cs`, 390 px `help-tip-btn`; same on clean main a3806a2a) and `test_reporting_help_0097.py::test_reporting_and_fee_list_geometry_and_tips_in_the_browser` (a fee help button not visible; fails the same on clean main 39962ad7). Neither is from this branch.
- `scripts/design_lint.py`: `design lint: OK`. `origin/main` (39962ad7) merged again, clean.

## Questions

None.

## Owner steps left

None until the strict review. Then one draft PR (body per brief section 9); 1086 adds the browser tests and the UX gate.

## Attempt 3 (contrast)

The legend note and the "Saved now" line were `small muted` (4.40:1). Both now use `police-letter-note` with `--ink-secondary`; the global muted token is untouched. Key `app2.css?v=20261110-1085f`. With `UBYHOST_REQUIRE_BROWSER=1`: `test_a11y_guard_browser.py test_layout_lint_browser.py test_police_letter_flow.py test_property_navigation_browser.py test_required_stars.py test_static_versions.py`: `79 passed`, 0 skipped. `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: `All checks passed!`

## Attempt 4 (phone landing, tick alignment)

`origin/main` merged again (clean). N1: after "Read the letter" `initPoliceLetterForm` scrolls `#police-letter-check` (start) or `#letter_text-error` (centre) into view; without JavaScript the first unticked box, or the textarea in the error case, has `autofocus`. A refused save keeps its own summary and focus. N2: `margin:0` on the tick label, at the specificity of the `prop-form-single` label rule. Keys `app.js?v=20261110-1085b`, `app2.css?v=20261110-1085h`. The browser test now asserts the landing (result and error in the viewport) and box/text centred within 2 px at 390/768/1280. With `UBYHOST_REQUIRE_BROWSER=1`: flow, layout lint, a11y guard, navigation, required stars, static versions: `79 passed`, 0 skipped. Ruff: `All checks passed!`. Shots: `/mnt/project-files/reviews/1085/v3/landing-{390,768,1280}.png` and `landing-error-*.png`.
