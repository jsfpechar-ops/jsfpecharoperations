# 1002: Stay page "Download Doručenka (PDF)" downloads every receipt of the stay

Status: todo
Depends on: none | Base commit: c42eb8e3 | Branch: task/1002-download-all-dorucenka
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A stay can have several reports (submissions), each with its own stored `receipt_pdf`, but the top button on the stay page links to one only. Add `GET /reservations/{reservation_id}/dorucenka.zip` (one receipt: that PDF; several: a zip) and point the top button at it. The label and the per-report downloads further down stay as they are. Filing and submit code are not touched.

## 2. Context

Stay URLs are `/reservations/{id}` (there is no `/stays/` route). Rules: AGENTS rule 8 (no push to main), rule 9 (no new copy: the label `reports.detail.download_receipt` stays), the Doručenka cannot be masked so the route uses `_dorucenka_hidden` like the single route. The stay page finds its reports through `guest.submission_id` and `guest.receipt_submission_id` (`App/app/routes/admin.py` ~3752).

Anchors (each verbatim, else STOP):

`App/app/routes/exports.py` (the single route, the zip helper and `_pdf_response` already exist; reuse them):
```
@router.get("/submissions/{submission_id}/errors.pdf")
def submission_errors(submission_id: int, request: Request):
```
`App/app/routes/exports.py` imports: `import base64`, `import os`, `from datetime import datetime`, `from .. import (access, auth, ... db, ... reporting, ...)`. `_zip_download(background_tasks, rows, builder, filename)` returns None when the builder wrote nothing.

`App/app/templates/reservation_detail.html` line 53:
```
      <a data-turbo="false" class="btn" href="/submissions/{{ receipt_report.id }}/receipt.pdf">{{ t('reports.detail.download_receipt') }}</a>
```
`App/tests/test_admin_route_split.py` (set `exports`, ~line 44):
```
        ("GET", "/submissions/{submission_id}/receipt.pdf"),
```
`App/tests/test_wp25_reported_bugs.py` line 342 (inside `test_stay_page_offers_the_doručenka`):
```
    assert f'href="/submissions/{seeded["with_pdf"]}/receipt.pdf">Download Doručenka (PDF)</a>' in page
```
(the same text also appears at line 300 in `test_report_offers_the_doručenka_download`; that one is the report page and stays unchanged. Edit only the occurrence inside `test_stay_page_offers_the_doručenka`.)

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/exports.py | edit | new builder + new route, placed directly before the `errors.pdf` route |
| App/app/templates/reservation_detail.html | edit | button href |
| App/tests/test_admin_route_split.py | edit | register the new route in the `exports` set |
| App/tests/test_wp25_reported_bugs.py | edit | fix one assertion, add 3 tests |

No other file may change.

## 4. Steps

1. `exports.py`: insert this block immediately above `@router.get("/submissions/{submission_id}/errors.pdf")`:
```python
def _build_stay_receipts_zip(rows: List[Any], dest_path: str) -> int:
    """Write one stay's stored Doručenka PDFs, named dorucenka-<submission_id>-<date>.pdf."""
    import zipfile

    count = 0
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            try:
                raw = base64.b64decode(row["receipt_pdf"])
            except Exception:
                continue
            date_part = (row["created_at"] or "")[:10] or "report"
            archive.writestr(f"dorucenka-{row['id']}-{date_part}.pdf", raw)
            count += 1
    return count


@router.get("/reservations/{reservation_id}/dorucenka.zip")
def stay_receipts(reservation_id: int, request: Request, background_tasks: BackgroundTasks):
    """Every stored Doručenka of one stay: the PDF itself when there is one, else a zip."""
    guard = auth.require_login(request)
    if guard:
        return guard
    hidden = _dorucenka_hidden(request, f"/reservations/{reservation_id}")
    if hidden:
        return hidden
    reservation = access.reservation(request, reservation_id, "r.id, r.apartment_id")
    rows = []
    if reservation:
        rows = db.query(
            "SELECT id, created_at, receipt_pdf FROM submission WHERE id IN ("
            "  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = ? AND submission_id IS NOT NULL"
            "  UNION SELECT DISTINCT receipt_submission_id FROM guest"
            "  WHERE reservation_id = ? AND receipt_submission_id IS NOT NULL"
            ") AND apartment_id = ? AND receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != '' "
            "ORDER BY created_at DESC",
            (reservation_id, reservation_id, reservation["apartment_id"]),
        )
    if reservation and rows:
        detail = f"reservation_id={reservation_id} which=receipts count={len(rows)}"
        if auth.impersonating(request):
            detail += " while_supporting=1"
        db.audit("export_submission_pdf", detail)
    if len(rows) == 1:
        return _pdf_response(rows[0]["receipt_pdf"], f"dorucenka-{rows[0]['id']}.pdf")
    response = _zip_download(
        background_tasks,
        rows,
        _build_stay_receipts_zip,
        f"dorucenky-{reservation_id}-{datetime.now().strftime('%Y%m%d')}.zip",
    ) if rows else None
    # No stored receipt (or not this host's stay): the same 404 text as the single route.
    return response or _pdf_response(None, f"dorucenka-{reservation_id}.pdf")
```
   Command: `cd App && .venv/bin/python -c "import app.routes.exports" 2>&1 | tail -30` (no output).
2. `reservation_detail.html` line 53: replace `href="/submissions/{{ receipt_report.id }}/receipt.pdf"` with `href="/reservations/{{ reservation.id }}/dorucenka.zip"`. Nothing else on the line or in the block changes (the `{% set receipt_report ... %}` and `{% if receipt_report %}` lines stay: they decide when the button shows).
3. `test_admin_route_split.py`: after the `("GET", "/submissions/{submission_id}/receipt.pdf"),` line add `        ("GET", "/reservations/{reservation_id}/dorucenka.zip"),`.
4. `test_wp25_reported_bugs.py`: in `test_stay_page_offers_the_doručenka` replace the assertion with `assert f'href="/reservations/{seeded["reservation"]}/dorucenka.zip">Download Doručenka (PDF)</a>' in page`. Then add `import io` and `import zipfile` to the imports (next to `import base64`), and append after that test:
```python
def _second_receipt(seeded):
    now = db.utcnow()
    apartment = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (seeded["reservation"],)
    )["apartment_id"]
    second = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "finished_at": now,
            "state": "ok",
            "guest_ids": f"[{seeded['by_hand']}]",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 second").decode(),
            "pseudo_stamp": "C94208F8-DA48-4F07-BBF9-95CB757B41F7",
        },
    )
    db.update("guest", seeded["by_hand"], {"submission_id": second})
    return second


def test_stay_receipts_with_one_receipt_is_the_pdf(client, seeded):
    response = client.get(f"/reservations/{seeded['reservation']}/dorucenka.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 receipt"


def test_stay_receipts_with_two_receipts_is_a_zip_of_two(client, seeded):
    second = _second_receipt(seeded)
    response = client.get(f"/reservations/{seeded['reservation']}/dorucenka.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len(names) == 2
    assert all(re.fullmatch(r"dorucenka-\d+-\d{4}-\d{2}-\d{2}\.pdf", n) for n in names)
    assert any(n.startswith(f"dorucenka-{seeded['with_pdf']}-") for n in names)
    assert any(n.startswith(f"dorucenka-{second}-") for n in names)


def test_stay_receipts_of_another_hosts_stay_are_denied(client, seeded):
    auth.create_account("wp25-other@example.test", "WP25 Other", username="wp25-other")
    other = TestClient(app)
    assert login_as(other, "wp25-other", url="/login?lang=en", follow_redirects=False).status_code == 303
    response = other.get(f"/reservations/{seeded['reservation']}/dorucenka.zip")
    assert response.status_code == 404
    assert b"%PDF" not in response.content
```
   Command: `cd App && .venv/bin/python -m pytest tests/test_wp25_reported_bugs.py tests/test_admin_route_split.py -q --tb=short -x 2>&1 | tail -30` (all pass). If `re` or `auth` were not imported, they are: both appear in the file header.

## 5. Do not touch

Filing, submit, claim and worker code; `reporting.py`; `host_i18n.py`; the per-report download links (`reservation_detail.html` line ~339, `submission_detail.html`, `submissions.html`); the single `receipt.pdf` route; CSS. No new dependency. No new copy, no new stored data.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_wp25_reported_bugs.py tests/test_admin_route_split.py tests/test_dorucenka_access.py tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` (browser tests 0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.
- Rule 10 UX gate: the button's label, size and position do not change, so no screenshot of a new layout is needed; run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` and put one 390 px screenshot of a reported stay in the report.

## 7. Acceptance

- [ ] A stay with one stored receipt: `GET /reservations/{id}/dorucenka.zip` answers the PDF (`application/pdf`).
- [ ] Two stored receipts: a zip with two `dorucenka-<submission_id>-<date>.pdf` entries.
- [ ] Another host's stay or a stay without receipts: 404 text, no bytes; an `export_submission_pdf` audit line with `count=N` is written only for the owner's stay with receipts.
- [ ] The top button on a reported stay points to `/reservations/{id}/dorucenka.zip`, label unchanged; the bottom per-report links unchanged.
- [ ] Listed tests pass, 0 skipped; context lint clean.

## 8. Stop and ask

An excerpt is not found; a test fails twice; 25 tool calls; a file outside section 3 needs a change; any step would touch section 5.

## 9. Report

`docs/tasks/1002-report.md` (600 tokens at most), `Status: review`: files changed, last 5 lines of each command, section 7 ticked, deviations.
