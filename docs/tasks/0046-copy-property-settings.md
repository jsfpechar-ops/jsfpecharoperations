# 0046: "Copy from another property"

Status: todo
Depends on: none | Branch: task/0046-copy-property-settings
Executor: Cursor local agent | Fits one session

## 1. Objective
When a host with at least one property adds or edits another, one select "Copy settings from…" fills the operator, the controller, the stay-fee settings and the guest-link timing from the chosen property. Each copied field stays editable. Hosts with 3 flats fill them once.

## 2. Context
- `App/app/routes/admin.py` `_apartment_payload(form)`: stay-fee keys stay_fee_rate_czk, stay_fee_cadence, stay_fee_vs, stay_fee_authority_name/address/contact, stay_fee_payee, stay_fee_instruction, the account fields; legal_entity_id, data_controller_entity_id; permalink_window_days, permalink_reachback_days, submit_after_hours, automation_mode.
- Never copy: IDUB, uby_mark, uby_name, WS login, WS password, the address, the permalink token, the door-code lock, stay_fee_vs (it is per property at most councils, so leave it empty and hint).

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | GET param `copy_from={id}` on new/edit pre-fills the form values (owner-scoped) |
| App/app/templates/apartment_form.html | edit | a small GET form with the select + "Copy" button at the top (only when the owner has ≥1 other property) |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_copy_property_settings.py | new | tests |

## 4. Steps
1. GET `copy_from` → load that apartment with the same owner check; build a dict of the allowed keys; pass it to the template as defaults for empty fields. Nothing is saved until the host presses Save.
2. Show a one-line notice: "Copied from {name}. Check and save." Mark the copied sections open.
3. Tests: allowed keys copied, blocked keys never copied (police credentials, address, VS), another owner's id → 404, a host with one property sees no select.

## 5. Do not touch
Migrations, submission code, guest pages.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px, before and after Copy.

## 8. Stop and ask
1. The stay-fee account field is stored encrypted or in a form the template can't pre-fill safely. Then skip the account and say so in the hint.

## 9. Report
Files, test tail, screenshots.
