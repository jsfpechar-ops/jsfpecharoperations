# 0846: Stay fee: one download for every saved report of the month

Status: todo
Depends on: 0845 (same route file; branch from main after 0845 merges) | Base commit: main after 0845 | Branch: task/0846-stay-fee-pdfs-zip
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `GET /stay-fees/pdfs.zip?month=YYYY-MM`: a ZIP with the sealed PDF of every property that has a saved period covering that month. A host with N properties downloads once instead of N times; brief 0848 adds the button.

## 2. Context

- Rule 1: the PDFs in the ZIP must be byte-identical to the single download (`stay_fee_filing.pdf_bytes(row)`), which the test asserts. Nothing is computed or saved.
- Privacy (rule 2): no new data, no new storage; the same bytes the single route already serves, to the same owner. Audit one line per ZIP. `zipfile` and `io` are standard library (no new dependency).
- **Route order matters.** `@router.get("/stay-fees/{apartment_id}")` would catch `/stay-fees/pdfs.zip` and answer 422, so the new route goes directly **above** it.
- Single download, `App/app/routes/stay_fees.py` (after #707), to mirror:
```python
    pdf = stay_fee_filing.pdf_bytes(row)
    db.audit(
        "stay_fee_pdf",
        f"apartment_id={apartment['id']} period={row['period_key']} total={row['total_due_czk']}",
    )
```
  and its filename `f'hlaseni-poplatek-z-pobytu-{row["period_key"]}-{stay_fee.vs_of(apartment)}.pdf'`.
- Anchor for the insert: `@router.get("/stay-fees/{apartment_id}")` (one occurrence).
- Month handling as in the list: `stay_fee.parse_month(...)`, future month falls back to `_default_month(today)`.
- Existing flash key for "nothing saved": `flash.stay_fees.not_saved`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/stay_fees.py` | edit | imports + new route |
| `App/tests/test_stay_fee_bulk_0845.py` | edit | Two tests at the end |
| `docs/tasks/0846-report.md` | new | Report |

No other file may change.

## 4. Steps

1. Imports: below `import unicodedata` add `import io` above it and `import zipfile` below it, so the block reads `import io` / `import unicodedata` / `import zipfile`. Commit `0846 step 1`.
2. Directly above `@router.get("/stay-fees/{apartment_id}")` insert:
```python
@router.get("/stay-fees/pdfs.zip")
def stay_fee_pdfs_zip(request: Request):
    """0846: every saved report of one month in one ZIP, the same bytes as each PDF button."""
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    month = stay_fee.parse_month(request.query_params.get("month")) or _default_month(today)
    if month > today.replace(day=1):
        month = _default_month(today)
    apartments = db.query(
        f"SELECT * FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL "
        "ORDER BY internal_name, id",
        (access.owner_id(request),),
    )
    buffer = io.BytesIO()
    names = set()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for apartment in apartments:
            row = stay_fee_filing.covering(apartment["id"], month)
            if not row:
                continue
            name = f'hlaseni-poplatek-z-pobytu-{row["period_key"]}-{stay_fee.vs_of(apartment)}-{apartment["id"]}.pdf'
            if name in names:
                continue
            names.add(name)
            archive.writestr(name, stay_fee_filing.pdf_bytes(row))
            count += 1
    if not count:
        return _back(f"/stay-fees?month={stay_fee.month_key(month)}", err=_flash(request, "flash.stay_fees.not_saved"))
    db.audit("stay_fee_pdf_zip", f"month={stay_fee.month_key(month)} files={count}")
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="poplatek-z-pobytu-{stay_fee.month_key(month)}.zip"',
            "Cache-Control": "no-store",
        },
    )


```
   Check `grep -n 'list_filter.parse' app/routes/stay_fees.py` still works with the list's `?month=` (it does not change). Commit `0846 step 2`.
3. Tests at the end of `App/tests/test_stay_fee_bulk_0845.py` (same fixtures):
   - `test_zip_holds_each_saved_pdf_byte_for_byte`: two ready properties, seal both with one `/stay-fees/confirm-ready` POST, then `client.get("/stay-fees/pdfs.zip?month=2026-08")`: 200, `content-type` starts `application/zip`; open with `zipfile.ZipFile(io.BytesIO(resp.content))`; 2 names; for each property, the member whose name ends `-{apartment_id}.pdf` equals `client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08").content`.
   - `test_zip_without_saved_period_goes_back_to_the_list`: no seal; `follow_redirects=False` gives 303 with `Location` starting `/stay-fees?month=2026-08`; another owner's sealed property never appears (seal one for a second account first, then assert the first owner's ZIP is the redirect).
   Run §6 command 1. Commit `0846 step 3`.
4. Run §6 command 2. Commit.

## 5. Do not touch

The single PDF/CSV routes, `stay_fee_filing.py`, templates, CSS, locale files. No migration.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_stay_fee_bulk_0845.py -q --tb=short -x 2>&1 | tail -30`
2. Row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] ZIP members are byte-identical to the single PDFs; only the owner's properties.
- [ ] `/stay-fees/7` and `/stay-fees/7/pdf` still route as before (command 2 passes).
- [ ] Commands 1-2 pass.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0846-report.md` (400 tokens at most), `Status: review`: files, command tails, §7 ticked.

## Risk list (for the reviewer)

`App/app/routes/stay_fees.py` (route sits above `/stay-fees/{apartment_id}`; owner-scoped query).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
