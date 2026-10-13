# 0088 report: required operator, no active switch

Base: `00e5c4e` (combined staging branch with 0087/0095). Result: `b676b18`. Executor: Claude (owner-authorized).

## What changed

- `App/app/templates/_property_operator.html` (new): the only `legal_entity_id` control. It is a required `<select>`. With one operator, that operator is selected. With several, a disabled "Choose operator / Vyberte provozovatele" option is selected (a stored, submitted, `?legal_entity_id=` or copy-from id is kept). With none, it shows "Add an operator to continue." plus "Add business details" (opens `/entities` in a new tab) and a `formnovalidate` "Check again" button. That button posts the draft back and nothing is written. No `(none)` option and no hidden duplicate.
- `admin.py`: added `_valid_property_operator` as the brief specifies, plus `_property_operator_error` (operator + submitted controller) and `_property_draft`. Create, full save (and so test-connection) and wizard name all run the check before any write and before police defaults. A refusal re-renders the form with the typed values (status 400) and never echoes the password. `_apartment_payload` sets `active = 1`. `_save_apartment_form` sets `active = 0 if archived_at else 1`. If a form has no `data_controller_entity_id` field, any stored override is kept. Sending the operator's own id or an empty value clears it to None. Split out `_render_apartment_new` / `_render_apartment_detail` so error pages can render.
- `apartment_form.html`: removed the one-entity hidden+select pair, the `(none)` options, the controller checkbox with its explanation, and the active checkbox. One visible "Guest data controller" select ("Same as operator" default) now sits outside More options: always on edit, and on create only when copy-from carries an override. Create fields refill from `draft` after a refusal.
- `setup_wizard.py` / `setup/name.html`: the same partial and rule. The redundant hidden `active` is gone. The wizard name step also writes `legal_entity_id` when an existing first property is renamed.
- `host_i18n.py`: a `# 0088` block with 6 EN/CS keys.

## Anchors (old → new)

All anchors matched at `00e5c4e`, so nothing moved. `setup/address.html` also posts a hidden `active`. It is outside §3 and the address-only save ignores it, so I left it.

## Commands (from App/, staging/mock env, pinned Chromium)

```
pytest tests/test_property_operator_defaults.py tests/test_setup_wizard.py tests/test_host_property_controls_browser.py -q -rs
  40 passed, 1 warning in 17.38s   (0 skipped)
per-file run of the 58 test files that touch property/setup routes + test_privacy_first.py:
  all pass except baseline: test_host_wide_geometry_browser.py 3 failed (listed in 0087-evidence baseline);
  test_security.py::test_security_headers_on_healthz fails only when the file runs alone ("no such table", isolation; untouched);
  test_dashboard_missing_banner.py 1 skipped = its own capture gate (pre-existing)
ruff check app tests tools --select E9,F63,F7,F82,F401,F841  ->  All checks passed!
python3 scripts/context_lint.py  ->  context lint: OK
git diff --check  ->  clean
```

Note: `test_endtoend.py` fails when run in the same process after other modules, both at baseline and now. It passes alone (28 passed). This is a pre-existing order dependence. I did not run the full suite (the coordinator does).

## §7 checklist

- [x] No property can be created or full-saved without the host's own non-archived operator. This covers missing, malformed, zero, unknown, foreign and archived ids, the wizard and test-connection, with route tests showing no row and no secret write. The active switch is gone. A forged `active` of 0, false, blank or omitted still saves active=1. Archived properties stay inactive on save, and archive/restore still work.
- [x] The operator is the default controller and contact (`guest._controller`/`_host_contact` tested). An existing override survives a save without the field (no-JS) and a resubmit. It clears only on an explicit "Same as operator". A foreign, archived or malformed controller is refused. Copy-from keeps an explicit override. Reporting mode and hours are unchanged.
- [x] Browser: EN/CS at 360/390/1280 for zero, one and several operators, the wizard, edit, the error state and the check-again detour. Geometry runs at 760/1024/1440/1680/1920/2048 with the sidebar expanded and collapsed. 0 skipped.
- [x] No schema, dependency or outbound call. Data is synthetic. Evidence has no tokens or passwords.
- [ ] CI on the task head: not run here (no push, per instructions).

## Evidence

`docs/tasks/0088-evidence/`: `new-many-*`, `new-none-*`, `wizard-one-*`, `edit-*` (360/390/1280 × en/cs), `new-error-1280-en`, `new-detour-1280-en`. Captured with `UBYHOST_CAPTURE_0088=1`.

## Deviations / files outside §3

- `App/app/static/host.css`: appended a `/* 0088 */` block (field width, hint spacing, wrapping detour actions).
- Existing tests needed an operator in their fixtures or posts, and I changed only those inputs: test_accounts, test_calmer_forms, test_flash_next_step, test_guest_slugs, test_host_copy_corrections, test_host_flash_outcomes, test_new_property_defaults, test_property_form_save, test_stay_fee_property_panel, test_ui_consistency. Some assertions changed meaning on purpose and were replaced with stricter ones:
  - test_calmer_forms: the hidden input is gone, so it now checks for one control with the operator selected.
  - test_overhaul: the checkbox is gone, so it now checks that the visible controller select keeps the override.
  - test_operator_naming: the "Manage operators" link went with the controller block, so it now checks the selected sole operator plus the /entities link.
  - test_property_hub: the link now goes to `/entities?edit=N`.
- With zero operators, the draft survives the detour because the original tab stays open and "Check again" re-renders it. Nothing goes in the URL or in storage. Creating the entity in the new tab still sends that tab to `/apartments/new?legal_entity_id=…` (existing behaviour, untouched).
- The create form keeps the automation "More options" fold. Folds belong to 0092/0093, not here.

## Owner steps

1. Review this report and the screenshots in `docs/tasks/0088-evidence/`.
2. Let the coordinator run the full suite and CI on the integration branch.
3. On staging with synthetic data, try creating a property with zero, one and two operators.
