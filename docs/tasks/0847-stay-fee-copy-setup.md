# 0847: Stay fee setup: copy it from the host's property in the same municipality

Status: todo
Depends on: 0846 (same route file), 0844 (flash keys) | Base commit: main after 0846 | Branch: task/0847-stay-fee-copy-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

For a property with no stay fee yet, find the host's own configured property in the same municipality and offer its setup (rate, period, symbol, council account, council). One tap on "Use this setup" saves it. Today the host opens the property settings and types 4 required fields (rate, VS, account, council name) plus up to 3 optional ones. This brief adds the route and the list data; 0848 shows the card.

## 2. Context

- The host sees every value before the tap (0848 shows them); nothing is saved without the tap, so this is not autosave. Only council data is copied (no personal data: no `retention.py` line).
- Same municipality = `_fold_place(apartment["addr_obec"])` equal and not empty (`_fold_place` is in `App/app/routes/stay_fees.py`, case and diacritics removed).
- Refuse when the target already has a fee (`stay_fee.is_active`) or any sealed filing (a period mode change over old filings is guarded elsewhere; do not go around it).
- Columns (`App/app/db.py` around line 1054): `stay_fee_rate_czk`, `stay_fee_cadence`, `stay_fee_council_account`, `stay_fee_council_iban`, `stay_fee_vs`, `stay_fee_authority_name`, `stay_fee_authority_address`, `stay_fee_authority_contact`, `stay_fee_payee`, `stay_fee_instruction`, `stay_fee_scope_rule`, `stay_fee_scope_reference`, `stay_fee_authority_databox`.
- Anchors in `App/app/routes/stay_fees.py` (after #707):
```python
    configured = {row["apartment"]["id"] for row in rows}
    for apartment in apartments:
        if apartment["id"] not in configured:
            rows.append({"apartment": apartment, "unset": True, "issues": []})
```
  and `@router.post("/stay-fees/{apartment_id}/finalize")` (insert the new route above it; 0845 put `confirm-ready` there too, keep it).
- `apartments` in `stay_fees_list` is `SELECT * ... active = 1 AND archived_at IS NULL`, so it carries every fee column.
- Keys from 0844: `flash.stay_fees.copy_done` (`%(name)s`), `flash.stay_fees.copy_failed`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/stay_fees.py` | edit | `FEE_COPY_FIELDS`, `fee_copy_source`, list `copy_from`, POST route |
| `App/tests/test_stay_fee_copy_setup_0847.py` | new | Tests |
| `docs/tasks/0847-report.md` | new | Report |

No other file may change.

## 4. Steps

1. Directly below the `_fold_place` function (after its `return` line and one blank line) insert:
```python


# 0847: the council fields a property can take over from a sibling in the same municipality.
FEE_COPY_FIELDS = (
    "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs",
    "stay_fee_council_account", "stay_fee_council_iban",
    "stay_fee_authority_name", "stay_fee_authority_address",
    "stay_fee_authority_contact", "stay_fee_authority_databox",
    "stay_fee_payee", "stay_fee_instruction",
    "stay_fee_scope_rule", "stay_fee_scope_reference",
)


def fee_copy_source(apartment, candidates):
    """The first candidate with an active fee in the same municipality, or None."""
    place = _fold_place(apartment["addr_obec"])
    if not place:
        return None
    for candidate in candidates:
        if (
            candidate["id"] != apartment["id"]
            and stay_fee.is_active(candidate)
            and _fold_place(candidate["addr_obec"]) == place
        ):
            return candidate
    return None
```
   Commit `0847 step 1`.
2. Replace the `rows.append({"apartment": apartment, "unset": True, "issues": []})` line (inside the anchor) with:
```python
            rows.append({
                "apartment": apartment, "unset": True, "issues": [],
                "copy_from": fee_copy_source(apartment, apartments),
            })
```
   Commit `0847 step 2`.
3. Directly above `@router.post("/stay-fees/{apartment_id}/finalize")` insert:
```python
@router.post("/stay-fees/{apartment_id}/copy-setup")
async def stay_fee_copy_setup(apartment_id: int, request: Request):
    """0847: one tap takes over the fee setup the host was shown on the list."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    back_path = fee_return_path(_form_str(form, "return_to"), apartment_id) or "/stay-fees"
    raw = _form_str(form, "source_id")
    source = access.apartment(request, int(raw)) if raw.isdigit() else None
    has_filing = db.query_one("SELECT id FROM stay_fee_filing WHERE apartment_id = ?", (apartment["id"],))
    if (
        not source
        or source["archived_at"]
        or stay_fee.is_active(apartment)
        or has_filing
        or fee_copy_source(apartment, [source]) is None
    ):
        return _back(back_path, err=_flash(request, "flash.stay_fees.copy_failed"))
    db.update("apartment", apartment["id"], {key: source[key] for key in FEE_COPY_FIELDS})
    db.audit("stay_fee_copy_setup", f"apartment_id={apartment['id']} source_id={source['id']}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.copy_done", name=source["internal_name"] or ""))


```
   Check `grep -n "def update" app/db.py | head -3` shows `update(table, row_id, values)`; if not, STOP. Commit `0847 step 3`.
4. New `App/tests/test_stay_fee_copy_setup_0847.py`: fixture copied from `App/tests/test_stay_fee_finalize.py` lines 13-57 with prefix `stay-fee-copy-` (cleanup, account, username). Helper `_flat(owner_id, entity_id, name, city, **fee)` inserts an apartment with `internal_name=name`, `addr_obec=city`, `active=1` and the fee fields given. Source: `_flat(..., "Source", "Praha 3", stay_fee_rate_czk=50, stay_fee_vs="123456", stay_fee_authority_name="Městský úřad", stay_fee_council_account="19-2000781379/0800", stay_fee_council_iban="CZ3008000000192000781379", stay_fee_cadence="quarterly", stay_fee_authority_databox="abc1234")`. Tests:
   - `test_copy_takes_every_fee_field`: target `"Target", "praha 3"` (other case); POST `/stay-fees/{target}/copy-setup` with `_csrf`, `source_id`, `return_to=/stay-fees`: 303; every `FEE_COPY_FIELDS` value of the target equals the source's.
   - `test_list_offers_the_source_only_in_the_same_place`: call `stay_fees.fee_copy_source(target_row, [source_row])` (import `from app.routes import stay_fees as stay_fee_routes`) returns the source for `Praha 3`/`praha 3`, `None` for `Brno`, `None` when the target `addr_obec` is empty, `None` when the source rate is 0.
   - `test_copy_refuses_other_place_active_target_foreign_source`: three POSTs, each a 303 whose followed page shows `This setup cannot be copied here.`, and the target's rate stays 0 (for the active-target case, the target keeps its own rate). Foreign source: a second account (prefix `stay-fee-copy-`) owns the source.
   - `test_copy_refuses_when_target_has_a_filing`: insert one `stay_fee_filing` row for the target by sealing it first is heavy, so instead: give the target rate 50 with one signed stay in 2026-08 (as `_stay` in the finalize test), seal it through `/stay-fees/{target}/finalize`, set its rate back to 0 with `db.update`, then POST copy: refused, rate stays 0.
   Run §6 command 1. Commit `0847 step 4`.
5. Run §6 command 2. Commit.

## 5. Do not touch

`fee_form_values`, `apply_fee_account`, the property editor (`routes/admin.py`, `_stay_fee_fields.html`, `_property_editor.html`: other threads), templates, CSS, locale files. No migration.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_stay_fee_copy_setup_0847.py -q --tb=short -x 2>&1 | tail -30`
2. Row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_fee_*.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] Copy writes exactly `FEE_COPY_FIELDS` from an owned, same-municipality, active source; refuses every other case.
- [ ] `stay_fees_list` rows for unset properties carry `copy_from` (a source row or `None`).
- [ ] Commands 1-2 pass.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0847-report.md` (400 tokens at most), `Status: review`: files, command tails, §7 ticked, deviations.

## Risk list (for the reviewer)

`App/app/routes/stay_fees.py` (owner scope on both ids; refusal when the target has filings).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
