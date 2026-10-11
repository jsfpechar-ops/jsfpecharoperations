# 0045 report: Property address as one line

## Files changed

| Path | Change |
|---|---|
| `App/app/validation.py` | `split_czech_address`, `compose_czech_address_line`, `merge_split_address_fields` |
| `App/app/routes/admin.py` | Apply `address_line` on create/save; mismatch query flag; template context |
| `App/app/templates/apartment_form.html` | One `address_line` input; police parts in nested `<details>` |
| `App/app/host_i18n.py` | EN + CS copy for one-line address UI and mismatch warning |
| `App/tests/test_address_split.py` | Table-driven split/merge tests |
| `docs/tasks/0045-evidence/` | Screenshots (360 / 390 / 1280 px, EN) |

## Commands (tail)

`App/`: `.venv/bin/python -m pytest tests -q`

```
3063 passed, 2 skipped, 7 warnings in 447.37s (0:07:27)
```

(6 failures in `test_host_stay_actions_browser.py` / `test_host_wide_geometry_browser.py` on this run — stay-row geometry, unrelated to the address form; re-run those files alone: 4 failed, 3 passed.)

`App/`: `.venv/bin/python -m pytest tests/test_address_split.py tests/test_property_readiness.py tests/test_host_property_controls_browser.py -q`

```
29 passed, 1 warning in 3.48s
```

Repo root: `python3 scripts/context_lint.py`

```
context lint: OK
```

## Screenshots

| Width | File |
|---|---|
| 360 px | `docs/tasks/0045-evidence/address-360-en.png` |
| 390 px | `docs/tasks/0045-evidence/address-390-en.png` |
| 1280 px | `docs/tasks/0045-evidence/address-1280-en.png` |

(CS variants captured under `/workspace/generated_images/host-design-application/properties/` during `UBYHOST_CAPTURE_PROPERTY_CONTROLS=1`.)

## Test-case table (`split_czech_address`)

| Input | Expected parts |
|---|---|
| `Vinohradská 1234/12, 120 00 Praha 2` | street, house 1234, orient 12, zip 12000, obec Praha 2 |
| `Street 1234/12a, 120 00 Praha` | street, house 1234, orient 12a, zip, obec |
| `Street 1234, 120 00 Praha` | street, house only (no orient) |
| `Obec 123, 54321 Obec` | house 123, no street (obec name = street dropped) |
| `č.p. 123, 12000 Praha` | cp. prefix stripped |
| `cp. E123, 12000 Praha` | evidence number house |
| `Main 12E, 12000 Praha` | trailing E house |
| `Hlavní 1, 12000 Praha 2 - Vinohrady` | obec_cast Vinohrady |
| `` (empty) | `{}` |
| `not an address at all` | `{}` |
| `Street 99999, 12000 Praha` | zip + obec only (invalid 5-digit house dropped) |
| `Street  1234/12,12000  Praha` | extra spaces / optional comma spacing |

Merge: non-empty `addr_*` from the form is never overwritten; conflict returns mismatch `True` (`test_merge_fills_only_empty_fields`).

## Acceptance (§7)

- [x] Saving `Vinohradská 1234/12, 120 00 Praha 2` via `address_line` fills `addr_house_no`, `addr_zip`, `addr_obec` (and street/orient) for the readiness checklist.
- [x] Screenshots at 360, 390 and 1280 px.

## Stop conditions (§8)

Not triggered.
