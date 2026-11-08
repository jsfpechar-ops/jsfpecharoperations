# 1024 report

Branch `claude/save-errors` (pushed, no PR). Files: see `git diff --stat origin/main`.

Tests (from App/, all with UBYHOST_REQUIRE_BROWSER=1, 0 skipped):
- test_0833_property_editor_browser, test_property_form_save, test_required_stars, test_static_versions, test_host_property_controls_browser, test_property_navigation_browser: 57 passed.
- test_layout_lint_browser: see hand-over message.

Screenshots (`/mnt/project-files/ux-shots/save-errors/`): failed-390/768/1280.png, saved-390/768/1280.png.
- Failed: 390 error directly under Council account, field focused and in view, stars on VS, account, office name; 768 same; 1280 same, two-column layout, error under its input.
- Saved: 390/768/1280 green banner "Saved. ..." with dismiss, no duplicate toast.

Choices: success banner uses `?saved=1` on the redirect plus `editor_saved` in templating.py; base.html hides the toast only then. Banner reuses `section-notice` classes (no new CSS). Stars use `aria-required`, not `required`. Rate star unchanged. No refusal for blank VS/account/office name.

Deviations: runtime star test lives in test_property_form_save.py (needs its fixtures); address error `<p>` not given `data-field-error` (file not in scope); `templating.py` touched; guest operator error was not moved.
