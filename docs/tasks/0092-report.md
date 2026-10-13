# 0092 report: one short Add property page

Base: `34bffcb` (combined staging branch with 0087–0091, 0093a, 0075, 0080–0082). Result: `db4d5d2` (code), report commit after it. Executor: Claude (owner-authorized).

## What changed

- New partials, each used once per document, none owns a form or route:
  - `_property_identity_fields.html`: name (required) and city (optional), helper text behind the shared `?`.
  - `_property_address_fields.html`: the seven structured fields with their old ids, names and lengths; optional per-field error (`address_errors`, translated with `validation_message`). No parsing.
  - `_property_create.html`: Property details, Managed by (the 0088 `_property_operator.html`, plus "Manage business details"), a visible compact Address card, Cancel / Create property. A narrow "After you create it" panel lists Connect a calendar, Share the guest form, Set up reporting, plus Digital door lock · optional, and holds the optional "Copy settings from…" GET form. A container query moves the panel under the form when the content lane is under 900 px (sidebar-aware); no horizontal rail.
- `apartment_form.html`: the not-editing branch now renders only the breadcrumb, header and create partial. The numbered section-nav, the setup banner, More options (reporting mode/hours/purpose), credentials, guest message, notes and the copied fee block are gone from create. The edit form includes the identity and address partials instead of its own copies; the inline `<style>` moved to `host.css`.
- `admin.py`:
  - Create checks name, operator and typed address parts before any write and re-renders 400 with every typed value (the blank-name redirect that lost the draft is gone). A blank or partial address is allowed (setup incomplete; readiness still blocks reporting); a component that was typed must pass the existing `validate_apartment` field check.
  - Copy: values copied from an authorized property travel as hidden fields (`automation_mode`, hours, link windows, fee fields, `copy_from`) only after the host pressed Copy; a refusal keeps them and the source name. The existing `default_purpose=10` default is a hidden field.
  - Success goes to `/apartments/{id}?created=1`, which shows an optional first-use choice: Connect a calendar · Add stay manually · Continue to overview.
- `setup_wizard.py`: `/setup`, `/setup/welcome`, `/setup/name` → `/apartments/new` (no property) or the property; `/setup/address` → `#address`; `/setup/bookings` → `#calendars`. Legacy POSTs are kept as guarded adapters (login, ownership, 0088 operator, address-only save, 0089 platform+URL) and return to the property. Dead step helpers removed.
- `onboarding.py`: `WIZARD_TOTAL_STEPS = len(WIZARD_STEPS)` (was a misleading 5); `wizard_step` stays as a readiness indicator. The banner line no longer counts steps ("Continue setup →").
- `host_i18n.py`: `# 0092` block, 22 EN/CS keys.
- `host.css`: `/* 0092 */` block (create layout, label row spacing, address grid alignment).

## Anchors (old → new)

All brief anchors matched. The create form also posts `_csrf` explicitly so it works with JavaScript off (csrf.js sets the same token).

## Tests (from App/, staging/mock env, pinned Chromium)

```
pytest tests/test_setup_wizard.py tests/test_property_create_browser.py tests/test_property_operator_defaults.py tests/test_calendar_platform_required.py -q -rs
  → 74 passed, 0 skipped
per-file run of all 75 files touching /apartments, setup/, onboarding, apartment_form + the new file
ruff check app tests tools --select E9,F63,F7,F82,F401,F841 → All checks passed!
python3 scripts/context_lint.py → context lint: OK
```

Per-file run: 992 passed across 76 files. Only baseline failures remain, both also failing at `34bffcb` in an untouched copy: test_host_quiet_dashboard_browser (1) and test_security (1, fails only when run alone). test_dashboard_missing_banner has 1 skip, which is its own evidence-capture gate and was already there before this task.

## §7 checklist

- [x] One short create page: required name and operator, optional structured address, no wizard. Legacy URLs work.
- [x] Regressions: zero/one/many operators, operator detour keeping name/city/address, blank and partial address, invalid part, Manual mode and purpose 10, guest default, one-submit create, copy (explicit, survives refusal, foreign 404), legacy GET/POST, login, foreign operator, admin preview, no-JS create.
- [x] Browser EN/CS 360/390/1280 plus 760–2048 with sidebar expanded and collapsed, long name, error state; 0 skipped.
- [x] No schema, dependency or outbound call; synthetic data.
- [ ] CI on the task head: not run (no push).

## Evidence

`docs/tasks/0092-evidence/`: `create-{360,390,1280}-{en,cs}.png`, `create-error-1280-en.png`, `created-{390,1280}-en.png` (`UBYHOST_CAPTURE_0092=1`). The created page still shows the pre-0094 long editor; 0094 replaces it.

## Files outside §3 / deviations

- Tests changed because the create page intentionally lost fields, with replacement assertions: test_new_property_defaults (no mode control on create; Manual shown on the property), test_calmer_forms (no fold), test_copy_property_settings (hidden copied values), test_property_form_nav (no numbered nav), test_host_copy_corrections (guest default stored by the server, no password at create, address error on the create form), test_host_property_controls_browser (create footer selector, no guest message on create), test_host_wide_geometry_browser (create result lane is `.property-create-lane`; footer selector).
- The dashboard checklist (`onboarding_welcome`) is in dashboard.html, owned by the 0079 worker; not changed here. `/onboarding` still shows the dismissible checklist.
- The legacy `setup/*.html` templates remain only for POST refusals.

## Owner steps

1. Look at `docs/tasks/0092-evidence/create-1280-en.png` and `create-390-cs.png`.
2. On staging, add a property with one operator, then with two, then with none (use "Check again").
