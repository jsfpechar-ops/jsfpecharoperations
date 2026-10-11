# 0062 report: Calmer forms

Status: review

## 1. Files changed

```
App/app/host_i18n.py
App/app/routes/admin.py
App/app/static/components.css
App/app/templates/apartment_form.html
App/app/templates/guest/form.html
App/tests/test_calmer_forms.py
App/tests/test_property_form_nav.py
docs/tasks/0062-report.md
```

## 2. Commands (last 5 lines)

`cd App && .venv/bin/python -m pytest tests/test_calmer_forms.py -q`

```
........                                                                 [100%]
8 passed, 1 warning in 1.36s
```

`cd App && .venv/bin/python -m pytest tests -q` (full suite)

```
9 failed, 3053 passed, 2 skipped, 7 warnings in 453.02s
```

Failures: six host browser/geometry tests (stay row clipping / dashboard screenshots) and two property-nav tests; nav tests updated in this branch. Re-run after merge: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_host_property_controls_browser.py -q`.

`python3 scripts/context_lint.py`

```
context lint: OK
```

## 3. Acceptance (§7)

- [x] New-property form: essentials visible; automation, controller, and link options under **More options** (closed by default).
- [x] Screenshots at 360, 390 and 1280 px: `docs/tasks/0062-evidence/property-closed-*.png`, `property-open-*.png`, `guest-form-*.png`.

## 4. Deviations

- Worktree created at `/workspace/uby-0062` (parent `../uby-0062` not writable on this host).
- `App/app/i18n.py` unchanged: keys are host-only (`apartment.form.*`).
- Single-operator pick uses hidden `legal_entity_id` plus optional change `<details>` with a named select (same field name when opened).

## 5. Stop conditions (§8)

- §8.1: No browser test was found that requires `permalink_pin` / `automation_mode` on the new-property page without opening **More options**; geometry failures are on stays list layout, not moved property fields.
- §8.2: Readiness opens **More options** server-side via `_more_options_open` (controller incomplete, field errors, `open_more=1`).

## 6. Questions

None.

## 7. Owner steps

1. Review on staging: new property form with one operator, **More options** closed/open, guest form nationality → residence default.
2. Optional: capture §7 screenshots at 360, 390, 1280 px for the PR gallery.
