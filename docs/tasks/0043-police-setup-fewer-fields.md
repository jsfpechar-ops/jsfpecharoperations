# 0043: Police setup asks for 3 fields, fills the rest

Status: review
Depends on: none | Base commit: main HEAD | Branch: task/0043-police-setup-fewer-fields
Executor: Cursor local agent | Fits one session
Risk: HIGH (UbyPort report header). Owner confirms §8.1 before merge.

## 1. Objective
The property "Police reporting" section shows only IDUB, web-service login and password. Abbreviation, facility name and contact are filled from data we already have and sit in a collapsed "Details sent to the police" block where they stay editable.

## 2. Context
- Rule 1: filing correctness beats every feature. A derived value must never overwrite a value the host typed.
- `App/app/routes/admin.py` `_apartment_payload(form)` (line ~907) builds the payload. It is called at lines ~972 (create) and ~1120 (update).
- `App/app/validation.py`: `_MARK_RE = ^[A-Za-z0-9]{5,6}$`, `_WS_USER_RE = ^(?:uby-ws[A-Za-z0-9]{6}|uby-tws[A-Za-z0-9]{5})$` (case-insensitive). The comment above `_MARK_RE` says the abbreviation is the part after UBY-WS in the login.
- `App/app/templates/apartment_form.html`, `<details ... id="ubyport">`: grids with uby_idub, uby_mark, uby_name, uby_contact, uby_ws_user, uby_ws_password.
- Operator e-mail: `legal_entities.contact_email`, linked by `apartments.legal_entity_id`.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/validation.py | edit | add `mark_from_ws_user(user) -> str` |
| App/app/routes/admin.py | edit | add `_apply_police_defaults(payload, entities)`; call it in create and update before validation |
| App/app/templates/apartment_form.html | edit | reorder the ubyport section |
| App/app/host_i18n.py | edit | EN + CS keys for the new labels and hints |
| App/tests/test_police_defaults.py | new | tests below |

## 4. Steps
1. `validation.mark_from_ws_user(user)`: strip; when `_WS_USER_RE` matches the production form `uby-ws` + 6 chars, return those 6 chars upper-case; otherwise return "". Never derive from the `uby-tws` test form.
2. `_apply_police_defaults(payload, entities)`, applied only to empty fields:
   - `uby_mark` empty → `mark_from_ws_user(payload["uby_ws_user"])`.
   - `uby_name` empty → `payload["internal_name"][:35].strip()`.
   - `uby_contact` empty → `contact_email` of the entity whose id == `payload["legal_entity_id"]`, cut to 50.
   Call it in both handlers right after `_apartment_payload(form)`, using the entity list each handler already loads (if a handler has none, load it with the existing helper the page uses; do not write new SQL).
3. Template: first row IDUB; second row WS login + password (unchanged markup). Move abbreviation, facility name and contact into `<details class="police-derived">` with summary key `apartment.form.ubyport.derived_summary` ("Details sent to the police (filled for you)" / "Údaje odesílané policii (doplněné za vás)"). Open it when any of the three has a validation issue. Each hint says where the default comes from (keys `...derived_mark_hint`, `...derived_name_hint`, `...derived_contact_hint`). Remove no existing field name.
4. Tests (`test_police_defaults.py`): name defaults from internal_name (40-char name → 35); contact defaults from the operator e-mail; mark derived from `UBY-WSab12cd` → `AB12CD`; nothing derived from `uby-tws1ab45`; a typed mark, name or contact is never replaced; the page renders with the details block closed when everything is valid and open when the mark is missing.

## 5. Do not touch
Submission code, `claim.py`, `reporting.py`, migrations, guest pages, CSS tokens. No new dependency.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q` → all pass. Root: `python3 scripts/context_lint.py` → OK. Browser and geometry tests 0 skipped (rule 7).

## 7. Acceptance
- [ ] New property: filling IDUB, login and password plus the property name and operator gives a readiness list with no police item missing.
- [ ] Existing properties: saved values unchanged after re-save.
- [ ] Screenshots of the property page at 360, 390 and 1280 px, block closed and open.

## 8. Stop and ask
1. OWNER CHECK before merge: on a real production protocol, are the 6 characters after UBY-WS the facility abbreviation? If not, delete step 1 and the mark tests, and keep the abbreviation visible.
2. The excerpts in §2 aren't found as described.
3. Either handler has no way to get the entity list without new SQL.

## 9. Report
docs/tasks/0043-report.md: files changed, test output tail, screenshots, answer to §8.1 if known.
