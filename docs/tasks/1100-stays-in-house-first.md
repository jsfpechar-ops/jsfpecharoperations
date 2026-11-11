# 1100: stays list shows in-house stays first, then upcoming, then past

Status: todo
Depends on: none | Base commit: main @ pull | Branch: claude/project-thread-iidrmq
Executor: Haiku 5.5 | Fits one session (about 15 tool calls)

## 1. Objective

Owner (Josef, 2026-11-11), reference Wolt's orders list (active orders on top, the rest below): on the host stays list `/reservations`, stays that are in the flat today come first, then upcoming stays, then past ones. Ordering only: no template, CSS or copy change, so no screenshot is needed (AGENTS rule 7 does not apply).

## 2. Context

`reservations_list` in `App/app/routes/admin.py` (grep `def reservations_list`) builds one SQL with the filters (status, apartment, `range`, dates, `report`), counts it, then ends with:

```
sql += " ORDER BY r.date_from ASC, r.date_to ASC, r.id ASC LIMIT ? OFFSET ?"
reservations = db.query(sql, [*params, RESERVATION_PAGE_SIZE, offset])
```

`today` (ISO string) is already defined above. Dates are ISO text. Paging is done in SQL, so the new order must be in the same ORDER BY (never sort in Python after the page is cut).

Groups, by `today`:
- 0 in house: `r.date_from <= today AND r.date_to >= today`
- 1 upcoming: `r.date_from > today`
- 2 past: `r.date_to < today` (this also covers the overdue-unfiled stays the default view keeps, so they land at the bottom)

Order inside a group: in house by `date_to` soonest first; upcoming by `date_from` soonest first; past by `date_to` most recent first. Ties: `date_from ASC, id ASC`.

The existing filters are unchanged. `range=past` has only group 2, `range=current` only group 0, `range=upcoming` groups 0, 1 and any overdue group 2, `all`, `archive` and custom ranges can have all three. The new ORDER BY works for every one of them with no per-range branch.

## 3. Files

- `App/app/routes/admin.py` (the ORDER BY line only)
- new: `App/tests/test_1100_stays_in_house_first.py`

## 4. Steps

Commit after each step: `1100 step k`. Find the anchor with `grep -nF` first; not found: STOP.

### Step 1: the ORDER BY

Replace the ORDER BY line shown above (anchor: `ORDER BY r.date_from ASC, r.date_to ASC, r.id ASC LIMIT ? OFFSET ?`) with this, Postgres-portable (plain CASE, no dialect functions):

```python
    # 1100: in house first (leaving soonest), then upcoming (arriving soonest), then past (latest first).
    group = (
        "CASE WHEN r.date_from <= ? AND r.date_to >= ? THEN 0 "
        "WHEN r.date_from > ? THEN 1 ELSE 2 END"
    )
    sql += (
        f" ORDER BY {group},"
        f" CASE WHEN {group} = 0 THEN r.date_to WHEN {group} = 1 THEN r.date_from END ASC,"
        f" CASE WHEN {group} = 2 THEN r.date_to END DESC,"
        " r.date_from ASC, r.id ASC LIMIT ? OFFSET ?"
    )
    reservations = db.query(sql, [*params, *([today] * 12), RESERVATION_PAGE_SIZE, offset])
```

(`group` appears four times, each with three `?`, so twelve `today` values.) Do not touch the COUNT query above it.

Run: `cd App && .venv/bin/python -m pytest tests/test_deadline_after_reporting.py -q --tb=short -x 2>&1 | tail -30`

### Step 2: the test

Create `App/tests/test_1100_stays_in_house_first.py`. Copy the login and cleanup pattern from `App/tests/test_deadline_after_reporting.py` (fixture that creates an owner, an apartment, reservations with `db` helpers, `TestClient(app)` + `login_as`, `host_i18n.LANG_COOKIE` = `en`). Insert six stays for one apartment with distinct guest-visible `guest_name`/`summary` text (use whatever column the stays row prints; grep the `reservation` insert in that test file) and dates relative to `date.today()`:

- A: in house, leaves in 3 days; B: in house, leaves tomorrow
- C: arrives in 10 days; D: arrives in 2 days
- E: left 5 days ago; F: left 20 days ago

Tests:
1. `/reservations?range=all`: order is B, A, D, C, E, F.
2. `/reservations` (default): B, A, D, C appear in that order and E, F do not.
3. `/reservations?range=past`: E before F.
4. `/reservations?range=current`: B before A.
5. Paging: monkeypatch `RESERVATION_PAGE_SIZE` in `app.routes.admin` to 2; page 1 of `range=all` holds B and A, page 2 holds D and C.

Run: `cd App && .venv/bin/python -m pytest tests/test_1100_stays_in_house_first.py tests/test_deadline_after_reporting.py -q --tb=short -x 2>&1 | tail -30`

## 5. Done when

Both commands pass. Write `docs/tasks/1100-report.md` (status, tests run, deviations). Do not push, merge or touch anything else.

## 6. Stop rules

A test fails twice, an anchor is missing, or the stays row has no printable text to order by: STOP and report.
