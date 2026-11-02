# 0845: Stay fee: one POST confirms every ready period the host sees

Status: todo
Depends on: PR #707 merged, 0844 merged | Base commit: main after both | Branch: task/0845-stay-fee-confirm-ready
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `POST /stay-fees/confirm-ready`: it seals, for one month, each listed property whose period is ready, using exactly the code the daily job already uses (`stay_fee_auto.confirm`). Today a host with N properties taps "Ano, sedí" N times; brief 0848 puts one button on the list that posts here. The filed amounts must be identical to the single button.

## 2. Context

**UbyPort / filing rule 1:** this must not change what is filed. Equality argument (verify while working): the list's "Ano, sedí" form posts `month`, `confirm_collected=1`, `return_to` and no `collected_*` fields to `stay_fee_finalize`, which then stores `collected[guest_id] = line["amount_czk"]`, `rate = period["rate_czk"]`, `issued_on=today`, `cadence=group["cadence"]`, all from `stay_fee_auto.check(...)`. `stay_fee_auto.confirm` (`App/app/stay_fee_auto.py`) does the same with the same `check`. The only difference is the audit event name, which this brief makes a parameter. The tests in step 4 assert equality.

`App/app/stay_fee_auto.py` anchors:
```python
def confirm(apartment, month, today) -> Optional[int]:
    """Seal a clean period with the fee as calculated (job only). None when blocked or saved."""
```
```python
    db.audit("stay_fee_auto_finalize", f"apartment_id={apartment['id']} period={checked['key']}")
```

`App/app/routes/stay_fees.py` (after #707) anchors:
```python
@router.post("/stay-fees/{apartment_id}/finalize")
async def stay_fee_finalize(apartment_id: int, request: Request):
```
Helpers already imported there: `access`, `auth`, `claim`, `db`, `stay_fee`, `stay_fee_auto`, `_back`, `_flash`, `_form_str`, `fee_return_path`, `_default_month`. `fee_return_path(raw, apartment_id)` accepts only `/stay-fees` (with query) or `/stay-fees/<id>`.

Keys from 0844: `flash.stay_fees.bulk_saved` (`%(count)s`), `flash.stay_fees.bulk_none`.

Test fixture pattern: copy `_cleanup`, `host`, `_property`, `_stay`, `_csrf` and `SIGNATURE` from `App/tests/test_stay_fee_finalize.py` (lines 13-131), renaming the username prefix to `stay-fee-bulk-` everywhere (cleanup `LIKE 'stay-fee-bulk-%'`, account `stay-fee-bulk-owner@example.test`, username `stay-fee-bulk-owner`). That fixture fixes today at 2026-09-30, so August 2026 is a closed, ready month.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee_auto.py` | edit | `confirm(..., audit_event=...)` |
| `App/app/routes/stay_fees.py` | edit | New route above `stay_fee_finalize` |
| `App/tests/test_stay_fee_bulk_0845.py` | new | Equality and safety tests |
| `docs/tasks/0845-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `stay_fee_auto.py`: replace the two-line `def confirm` anchor with
```python
def confirm(apartment, month, today, *, audit_event: str = "stay_fee_auto_finalize") -> Optional[int]:
    """Seal a clean period with the fee as calculated. None when blocked or saved.

    The daily job and the list's "confirm all ready" button (0845) both call this.
    """
```
   and the audit anchor line with
```python
    db.audit(audit_event, f"apartment_id={apartment['id']} period={checked['key']}")
```
   Run §6 command 1. Commit `0845 step 1`.
2. `routes/stay_fees.py`: directly above `@router.post("/stay-fees/{apartment_id}/finalize")` insert:
```python
@router.post("/stay-fees/confirm-ready")
async def stay_fee_confirm_ready(request: Request):
    """0845: seal every listed property's ready period for one month, one tap.

    Same sealing as the job (stay_fee_auto.confirm), which equals the list's
    "Ano, sedí": collected = the calculated amount per guest. A blocked or
    already saved period is skipped, never changed.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(today)
    if month > today.replace(day=1):
        month = _default_month(today)
    back_path = fee_return_path(_form_str(form, "return_to"), 0) or "/stay-fees"
    saved = 0
    seen = set()
    for raw in form.getlist("apartment_id"):
        text = str(raw).strip()
        if not text.isdigit() or text in seen:
            continue
        seen.add(text)
        apartment = access.apartment(request, int(text))
        if not stay_fee.is_active(apartment) or apartment["archived_at"] or not apartment["active"]:
            continue
        if stay_fee_auto.confirm(apartment, month, today, audit_event="stay_fee_finalize"):
            saved += 1
    if not saved:
        return _back(back_path, err=_flash(request, "flash.stay_fees.bulk_none"))
    return _back(back_path, msg=_flash(request, "flash.stay_fees.bulk_saved", count=saved))
```
   Then `grep -n '"/stay-fees/confirm-ready"' app/routes/stay_fees.py` prints 1 line. Commit `0845 step 2`.
3. Check `access.apartment` returns `None` for another owner's id: `grep -n "def apartment(" -A8 app/access.py | head -12`. If it does not scope by owner, STOP.
4. New `App/tests/test_stay_fee_bulk_0845.py` with the fixture copy from §2 (`_property` gets a `name` parameter used as `internal_name`; `_stay(apartment_id, uid, signed=True)` uses `uid` and sets `signature_png` to `SIGNATURE if signed else None`). Tests:
   - `test_bulk_seals_the_same_amounts_as_the_single_button`: two properties A and B with identical stays (uids `bulk-a`, `bulk-b`). `expected = stay_fee_auto.check(db.query_one("SELECT * FROM apartment WHERE id = ?", (a,)), date(2026, 8, 1), date(2026, 9, 30))["group"]["total_czk"]`. POST `/stay-fees/{a}/finalize` with `{"_csrf": token, "month": "2026-08", "confirm_collected": "1", "return_to": "/stay-fees?month=2026-08"}` (the list form). POST `/stay-fees/confirm-ready` with `[("_csrf", token), ("month", "2026-08"), ("return_to", "/stay-fees?month=2026-08"), ("apartment_id", str(b))]`. Both 303. `ra = stay_fee_filing.latest(a, "2026-08")`, `rb = ...(b, ...)`; assert both exist; `ra["total_due_czk"] == rb["total_due_czk"] == expected`; `ra["rate_czk"] == rb["rate_czk"]`; `sorted(stay_fee_filing.payload(ra)["collected"].values()) == sorted(stay_fee_filing.payload(rb)["collected"].values())` (if `payload()` has no `collected` key, compare `frozen_summary(row, apartment)["total_czk"]` instead and say so in the report).
   - `test_bulk_skips_blocked_and_saved_periods`: A ready, B with `signed=False` (blocked), C already sealed via the single route. Note C's filing id. One bulk POST with all three ids: A sealed; `stay_fee_filing.latest(b, "2026-08") is None`; C's latest id unchanged; the redirect `Location` contains the `bulk_saved` flash (follow with `client.get(location)` and assert `Periods saved: 1` in the text, `?lang=en` login is already English).
   - `test_bulk_ignores_other_owners_and_garbage_ids`: create a second account and property with a ready stay (cleanup must remove it: give it the `stay-fee-bulk-` username prefix); POST its id plus `"x"` and `"-1"`: nothing sealed for it; response flash `No period was ready to save.`
   - `test_bulk_future_month_falls_back`: POST month `2027-01`: no exception, 303.
   - `test_job_audit_name_is_unchanged`: call `stay_fee_auto.confirm(apartment, date(2026, 8, 1), date(2026, 9, 30))` on a ready property; assert `db.query_one("SELECT id FROM audit WHERE action = ? AND detail LIKE ?", ("stay_fee_auto_finalize", f"apartment_id={apartment_id} %"))` is not None (`db.audit(action, detail, ...)` in `App/app/db.py` line 2138; outside a request the owner column may be NULL, so the test deletes that row itself at the end with the same WHERE).
   Run §6 command 2. Commit `0845 step 4`.
5. Run §6 commands 3-4. Commit.

## 5. Do not touch

`stay_fee_finalize`, `stay_fee_filing.save`, `stay_fee.py`, any template, CSS, locale file. No migration. No new dependency.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_stay_fee_auto.py tests/test_stay_fee_auto_job.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_stay_fee_bulk_0845.py -q --tb=short -x 2>&1 | tail -30`
3. Invoices/stay fee row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30`
4. Copy row (flash keys): `.venv/bin/python -m pytest tests/test_flash_literals.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`

Expected: all pass.

## 7. Acceptance

- [ ] Equality test passes: bulk and single filings have the same total, rate and collected amounts, equal to `check()`'s total.
- [ ] Blocked, saved, foreign and garbage ids are skipped; nothing already sealed changes.
- [ ] The daily job still audits `stay_fee_auto_finalize`.
- [ ] Commands 1-4 pass.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; the equality test fails (that is a filing difference: report it, do not "fix" the test); you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0845-report.md` (500 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations.

## Risk list (for the reviewer)

`App/app/routes/stay_fees.py` (owner scope through `access.apartment`; only `confirm` writes), `App/app/stay_fee_auto.py` (default keeps the job's audit name).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green. No visible change until 0848.
