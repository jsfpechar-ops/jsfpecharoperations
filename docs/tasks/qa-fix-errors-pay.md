# QA fix: guest /pay page shows its amount, bad ids and bad paths show the 404 page

Status: todo
Depends on: none | Base commit: 8fb8047f | Branch: task/qa-fix-errors-pay
Executor: Haiku 5.5 | Fits one session (about 22 tool calls)

## 1. Objective

Three QA findings, all checked in the code:

1. **P1 guest-stay-fee-01 (real bug).** `/pay/ID/TOKEN` shows "Amount:  CZK" and an empty variable symbol. Cause: `templating.render()` sets `data["request"] = request` (the HTTP request), which overwrites the payment row passed as `"request"` in `App/app/routes/payments.py`. The template `payments_qr.html` then reads `request.amount_czk` from the HTTP request. The host preview route `payment_request_qr` has the same bug.
2. **P1 errors-hostile-02 (real bug).** `/apartments/abc` returns raw FastAPI JSON 422. No handler exists for `RequestValidationError`. `main.py` already has a friendly 404 page (`error.html`, `error_kind="not_found"`, with a home button) used by `http_error_handler`.
3. **P2 errors-hostile-03 (real, small).** `GET /apartments/{id}`, `/reservations/{id}`, `/guests/{id}` and `/stay-fees/{id}` redirect to the list with an error flash when the id is unknown (so the QA tool saw 200 after the redirect). They must answer 404 with the friendly page instead. Foreign ids behave the same (no leak of which ids exist).

Dropped as not in scope or not a bug: `/p/` and `/pay/` 404 content type (booking area owns it); errors-hostile-04 (clamping odd input, needs owner copy decision), -05, -06, -07 and all guest-stay-fee P2/P3 and host-reservations-fees items (see Deferred). host-reservations-fees-01 is "payments off on the server" behaviour, not a page bug here.

## 2. Context

Rules: AGENTS.md hard rules 5, 6, 9 and 7. Rule 7 applies only to the template change in step 1 (a guest-facing page): browser test plus one 390 px screenshot. No migrations, no new dependency, no new copy (reuse `error.not_found.*`, `payments.qr.*`).

## 3. Files

| Path | Action |
|---|---|
| `App/app/routes/payments.py` | edit: rename context key in 2 routes |
| `App/app/templates/payments_qr.html` | edit: `request.` to `pay_request.` |
| `App/app/main.py` | edit: add a `RequestValidationError` handler |
| `App/app/routes/admin.py` | edit: 3 GET routes raise 404 |
| `App/app/routes/stay_fees.py` | edit: 1 GET route raises 404 |
| `App/tests/test_payment_rails.py` | edit: one assertion in an existing test |
| `App/tests/test_error_pages.py` | edit: 2 new tests |
| `App/tests/test_host_unknown_ids.py` | create |
| `docs/tasks/qa-fix-errors-pay-report.md` | create (report) |

## 4. Steps

Find each anchor with `grep -nF`; read at most 40 lines around it. Commit after each step: `qa-fix-errors-pay step k`.

**Step 1: pay page context key.**
- In `App/app/routes/payments.py`, in `guest_qr_page` (grep `def guest_qr_page`) change `"request": row,` to `"pay_request": row,`. In `payment_request_qr` (grep `def payment_request_qr`) change `"request": row,` to `"pay_request": row,` inside the dict that also has `"nav": "payments"`. Change nothing else.
- In `App/app/templates/payments_qr.html` replace the three uses: `request.status` to `pay_request.status`, `request.amount_czk` to `pay_request.amount_czk`, `request.variable_symbol` to `pay_request.variable_symbol`.
- In `App/tests/test_payment_rails.py`, in `test_guest_qr_page_opens_without_login`, after `assert page.status_code == 200` add:
  `row = payment_request.get(rid)`
  `assert str(row["variable_symbol"]) in page.text and str(row["amount_czk"]) in page.text`
  (`_draft` creates the row; if `variable_symbol` is empty in a draft, assert only on `amount_czk` and STOP-and-ask is not needed.)
- Run: `cd App && .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -30`.
- Not covered: payee, account and amount text next to the QR (Deferred).

**Step 2: validation errors on pages show the 404 page.**
In `App/app/main.py`:
- Add the import `from fastapi.exceptions import RequestValidationError` next to the other fastapi imports.
- Add `from fastapi.exception_handlers import request_validation_exception_handler` by extending the existing line `from fastapi.exception_handlers import http_exception_handler` to import both names.
- Directly after `http_error_handler` (grep `async def http_error_handler`), add:

```python
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """A bad id in a page URL (``/apartments/abc``) is a missing page, not raw JSON.

    Only path-parameter errors on HTML requests; forms, queries and the API
    keep the 422 JSON body.
    """
    path_only = all(err.get("loc", ("",))[0] == "path" for err in exc.errors())
    if not path_only or not _wants_html(request):
        return await request_validation_exception_handler(request, exc)
    if _is_guest_path(request):
        return guest.error_page(request, "not_found", 404)
    return templating.render(request, "error.html", {"error_kind": "not_found"}, status_code=404)
```

- Append to `App/tests/test_error_pages.py`:

```python
def test_a_bad_id_in_a_page_url_is_the_404_page_not_json():
    db.init_db()
    client = TestClient(app)
    page = client.get("/apartments/abc?lang=en", headers={"accept": "text/html"})
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "Page not found" in page.text or "Stránka nenalezena" in page.text
    assert "int_parsing" not in page.text


def test_a_bad_id_for_scripts_keeps_the_422_json():
    db.init_db()
    api = TestClient(app).get("/apartments/abc")
    assert api.status_code == 422
    assert api.headers["content-type"].startswith("application/json")
```
  (An anonymous request to `/apartments/abc` fails validation before the login guard runs, so no login is needed.)
- Run: `cd App && .venv/bin/python -m pytest tests/test_error_pages.py -q --tb=short -x 2>&1 | tail -30`.

**Step 3: unknown ids answer 404.**
Add `HTTPException` to the fastapi import in each file if it is not already imported (`grep -n "^from fastapi import" <file>`). Then:
- `App/app/routes/admin.py`, `apartment_detail`: replace `return _back("/apartments", err=_flash(request, "flash.error.no_such_apartment"))` (the one inside `def apartment_detail`, after `if not apartment:`) with `raise HTTPException(status_code=404)`.
- `admin.py`, `reservation_detail`: replace the `_back("/reservations", err=_flash(request, "flash.error.no_such_stay"))` after `if not reservation:` with `raise HTTPException(status_code=404)`.
- `admin.py`, `guest_edit`: replace the `_back("/reservations", err=_flash(request, "flash.error.no_such_guest"))` after `if not guest:` with `raise HTTPException(status_code=404)`.
- `App/app/routes/stay_fees.py`, `stay_fee_detail`: right after `apartment = access.apartment(request, apartment_id)` add `if not apartment:` then `raise HTTPException(status_code=404)`. Leave the existing redirect for an apartment whose fee is off untouched (it then only runs for a real apartment).
- Do NOT touch other routes, POST routes, `/export.json`, `/form.pdf` or the 37 other `_back(... no_such_...)` uses.
- Create `App/tests/test_host_unknown_ids.py`:

```python
"""An unknown or foreign id in a host page URL is a 404 page, not a redirect."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USER = "unknownidshost"


@pytest.fixture
def client():
    db.init_db()
    auth.create_account(f"{USER}@example.test", "Unknown Ids", username=USER)
    c = TestClient(app)
    assert login_as(c, USER, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield c
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USER,))
    if row:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.mark.parametrize(
    "path",
    ["/apartments/999999", "/reservations/999999", "/guests/999999", "/stay-fees/999999"],
)
def test_unknown_id_is_a_404_page(client, path):
    page = client.get(path, headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
```
  If the fixture cleanup fails with a foreign-key error, copy the `_cleanup()` approach from `tests/test_payment_rails.py` lines 24-35 (same file, same pattern) and rerun once; a second failure is a STOP.
- Run, each ending `-q --tb=short -x 2>&1 | tail -30`, from `App/`:
  `.venv/bin/python -m pytest tests/test_host_unknown_ids.py tests/test_error_pages.py tests/test_host_*.py tests/test_stay_fee*.py tests/test_property_*.py tests/test_onboarding*.py -q --tb=short -x 2>&1 | tail -30`
  A test that asserted the old redirect for an unknown id on one of these four GET routes: update only that assertion to `404` and list it under Deviations. Any other failure is a STOP.

**Step 4: browser check (template changed).**
- Test-map rows: Guest pages (`test_guest_*.py test_guest_browser_e2e.py`, 0 skipped, add `-rs`) and Host pages (`test_host_geometry.py`, 0 skipped). Run: `cd App && .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30`. Skipped means broken.
- Rule 7 screenshot: run the app locally (`cd App && ./run.sh`), create a QR payment request in a test account, open `/pay/ID/TOKEN` at 390 px width and save one screenshot as `docs/tasks/qa-fix-errors-pay-390.png`. Confirm in the report that Amount and Variable symbol have values. If you cannot start a browser in your session, say so under Deviations and leave the screenshot to the reviewer. Do not retake.

**Step 5: lint and report.**
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Write `docs/tasks/qa-fix-errors-pay-report.md` (600 tokens at most), set `Status: review`, open one PR titled "QA: pay page shows its amount, bad ids show the 404 page". Do not merge.

## 5. Do not touch

- The 404 content type of `/p/...` and `/pay/...` bad-token responses (`return Response(status_code=404)` in `guest_qr_page`): the booking area owns it.
- Any other `_back(... no_such_...)` route, POST routes, JSON export routes, `App/app/migrations/`, secrets, templates other than `payments_qr.html`, CSS, i18n files.
- No new dependency, no deploy, no merge.

## 6. Acceptance

- [ ] `/pay/ID/TOKEN` page text contains the amount and the variable symbol (test in step 1 green).
- [ ] `/apartments/abc` with `Accept: text/html` is a 404 HTML page; without it, still 422 JSON.
- [ ] `/apartments|reservations|guests|stay-fees/999999` give 404 HTML.
- [ ] All commands of steps 1-4 green; browser and geometry files 0 skipped.
- [ ] One 390 px screenshot of `/pay/ID/TOKEN` in the PR.
- [ ] `context lint: OK`.

## 7. Stop and ask

An anchor is not found; a test fails twice; any file outside section 3 needs a change; `/pay/` 404 behaviour seems to need a change.

## Deferred (not in this brief)

- Pay page content: show payee, account and amount in text next to the QR (guest-stay-fee-01 fix part 2); copy-account button, scan hint, "pay from abroad" hint (guest-stay-fee-02, -06). Needs copy and a UX gate.
- `/pay/` and `/p/` 404 should be HTML with a "link expired" message (errors-hostile-01, host-reservations-fees-05): booking area.
- errors-hostile-04 (clamp `?page=-5`, reject `/reservations/-1`; the latter is now a 422-to-404 via step 2 for HTML), -05 and host-reservations-fees-08 (tap targets), -06 (`/smart-locks/setup` 405 page shows Stays), -07.
- host-reservations-fees-02 (payment amount upper limit, for example 100000), -03, -04 (inline stay-fee errors), -06, -07, -09; guest-stay-fee-03, -04, -05, -07, -08.
- host-reservations-fees-01: Stripe-off behaviour of `/payments/new`; needs an owner decision on hiding versus listing drafts.
