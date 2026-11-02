# 0838: Guest form, 2nd person: carry over surname and stay dates too

Status: todo
Depends on: 0841 (baseline first) | Base commit: b8c87df | Branch: task/0838-guest-carry-over
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When the same device fills the next person on a stay, the form already shows person 1's surname and stay dates, as it already does for the residence address. The guest sees the values and changes them if they differ. Target: about 9 to about 6 taps for the 2nd person.

## 2. Context

Verified on b8c87df: `_residence_prefill` in `App/app/routes/guest.py` (line 196) copies street, city and country from the most recent **completed** guest this device created on the same stay; the form shows the hint `residence_copied`. The stay dates are hidden inputs (`App/app/templates/guest/form.html` lines 58-61) that read `values.get('stay_from')` first, then the reservation. The surname input (line 113) reads `val('surname')`.

Hard limits:
- The guest PIN stays exactly as it is (do not touch `templates/guest/pin.html` or the `/pin` route).
- No autosave: values are shown in the form; nothing is stored until the guest submits. Police data is a suggestion the guest confirms by passing the step.
- First name, birth date, nationality and document number are never copied.
- No new copy key (it would need every guest language). The surname is a visible, required field on step 1, which the guest must pass.

Anchor, `App/app/routes/guest.py` (lines 224-228):
```python
        name = _guest_display_name(row["first_name"], row["surname"])
        return (
            {"res_street": street, "res_city": city, "res_country": country},
            name,
        )
```
Test anchor, `App/tests/test_guest_residence_prefill.py` lines 179-183:
```python
        assert values == {
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
        }
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/guest.py` | edit | `_residence_prefill` adds surname, stay_from, stay_to |
| `App/tests/test_guest_residence_prefill.py` | edit | Updated assertion + surname check in the next-person test |
| `docs/tasks/0838-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `guest.py`: replace the anchor with:
```python
        name = _guest_display_name(row["first_name"], row["surname"])
        values = {"res_street": street, "res_city": city, "res_country": country}
        # 0838: family name and stay dates usually match too. Shown in the form for
        # the guest to confirm or change; nothing is saved until they submit.
        for key in ("surname", "stay_from", "stay_to"):
            value = row[key]
            if value:
                values[key] = str(value).strip()
        return values, name
```
   Also add one sentence to the docstring end: `Since 0838 it also carries the surname and the stay dates.` Commit.
2. Test: read `_first_person_done` in the test file to learn the surname it types. Replace the anchor assertion with:
```python
        assert {key: values[key] for key in ("res_street", "res_city", "res_country")} == {
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
        }
        assert values.get("surname") == "<the surname from _first_person_done>"
        assert "first_name" not in values and "birth_date" not in values
```
   In `test_the_next_person_sees_the_address_already_filled_in` add one assertion that the rendered form has `id="surname"` with that surname as its value (same style as the address assertions there). Commit.
3. Run §6. Take one 390 px screenshot of the 2nd person's form step 1 (use the screenshot pattern of the guest browser e2e test; if it has none, write the screenshot with Playwright inside the new assertion's test only when `UBYHOST_SHOTS_DIR` is set and run it with that variable). Commit.

## 5. Do not touch

PIN code and template, `/another` route (`add_another_person`), the device cookie, `reporting.guest_is_complete`, UbyPort payload code. Wizard, onboarding and property-editor files (other threads).

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_guest_residence_prefill.py -q --tb=short -x -rs 2>&1 | tail -30`
2. Guest row: `.venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Filing row smoke (the payload must not change): `.venv/bin/python -m pytest tests/test_endtoend.py tests/test_ubyport_*.py -q --tb=short -x 2>&1 | tail -30`

Expected: all pass, 0 skipped in 2.

## 7. Acceptance

- [ ] 2nd person on the same device sees person 1's surname, street, city and country; first name is empty.
- [ ] A different device sees nothing copied (existing test still passes).
- [ ] Commands 1-3 pass, 0 skipped.
- [ ] One 390 px screenshot of the 2nd person's step 1.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0838-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left, and the 0841 count for the 2nd person after the change.

## Risk list (for the reviewer)

`App/app/routes/guest.py` (`_residence_prefill`: only completed, device-owned guests; no first name or document fields copied).

## Owner steps

1. Check the screenshot, then merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
