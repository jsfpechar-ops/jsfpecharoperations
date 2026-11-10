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

## Questions

None.

## Owner steps left

None until the strict review. Then one draft PR (body per brief section 9); 1086 adds the browser tests and the UX gate.
