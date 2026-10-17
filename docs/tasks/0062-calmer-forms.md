# 0062: Calmer forms: "More options", default guest message, one-operator auto-pick, residence = nationality

Status: done
Depends on: none (rebase after 0043/0045 if they merged first) | Branch: task/0062-calmer-forms
Executor: Cursor local agent | Fits one session

## 1. Objective
The property form shows only what a host must answer: name, address, the police fields and calendar links. Everything that already has a good default moves into a closed "More options" section. Small defaults remove more typing.

## 2. Context
- `App/app/templates/apartment_form.html`: sections basics/address/ubyport/automation/communication/stay-fee/door-code/calendars; fields `legal_entity_id`, `data_controller_entity_id`, `automation_mode`, `submit_after_hours`, `default_purpose`, `guest_message`, `guest_link_name`, `permalink_pin`, `permalink_window_days`, `permalink_reachback_days`, `passport_photo_policy`; calendar fields `url`, `label`, `own_name`.
- `App/app/routes/admin.py` `_apartment_payload` (~line 900–980) and the update handler (~1120). The PIN is generated (`auth.new_permalink_pin`), the purpose defaults to `validation.DEFAULT_PURPOSE`, the platform is detected (`icalsync.platform_of`).
- `App/app/templates/guest/form.html`: `nationality` select (~line 130), `res_country` select (~line 215), the `val()` macro.
- HOST_APP_DESIGN §1; rule 6 (works without JS); readiness links (`_readiness`) must still reach every field.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/apartment_form.html | edit | wrap automation mode, after-hours, purpose, link name, PIN, windows, passport policy, controller and the calendar `label`/`own_name` inputs in `<details class="more-options">` "More options", `open` when any of those fields has an error or a readiness link targets one |
| App/app/templates/apartment_form.html | edit | when the host has exactly one operator: a hidden `legal_entity_id` and the text "Operator: {name} · change" (a link to show the select via `<details>`) |
| App/app/routes/admin.py | edit | blank `guest_message` on **create** → the i18n default text (CS/EN by host language); never on update |
| App/app/templates/guest/form.html | edit | `res_country` falls back to the chosen nationality when empty (`val('res_country', val('nationality'))`); small JS mirrors nationality → residence until the guest changes residence |
| App/app/host_i18n.py, App/app/i18n.py | edit | EN + CS: `apartment.form.more_options`, `apartment.form.guest_message.default`, `apartment.form.operator_only` |
| App/app/static/components.css | edit | `.more-options` summary styled like the existing section headers |
| App/tests/test_calmer_forms.py | new | tests |

## 4. Steps
1. Default guest message (EN): "Hello, before you arrive please fill in the short check-in form at the link below. It takes about 2 minutes per person and is required by Czech law. Thank you and see you soon!" CS: the same meaning, natural Czech.
2. The readiness checklist links to a field inside "More options" → the section renders `open` (server-side, from the `#anchor` the readiness item uses, or an `open_more=1` query).
3. Residence default: server-side only when `res_country` has no saved or posted value; the JS stops mirroring after the first manual change of `res_country`.
4. Tests: the form renders with `<details>` closed by default and open on a related error; one operator → the hidden input is posted and saves correctly; two operators → the select is shown; create with a blank message stores the default, update with a blank message stores blank; guest form: nationality DEU and empty residence → residence preselected DEU; a saved residence is never replaced.

## 5. Do not touch
UbyPort submission, validation rules, migrations (none), the stay-fee and door-code sections.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] The new-property page shows at most name, address, the police fields and the calendar URL above the fold at 390 px.
- [ ] Screenshots of the property form (closed and open) and the guest form at 360, 390 and 1280 px.

## 8. Stop and ask
1. Any browser test relies on a moved field being visible without opening `<details>`; list them before changing the tests.
2. The readiness anchors can't open the section without JS.

## 9. Report
Files, test tail, screenshots.
