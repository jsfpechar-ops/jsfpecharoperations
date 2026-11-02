# 0763: Guests can open the bank-transfer (QR) payment page

Status: in-progress
Depends on: 0762 (stacked) | Base commit: task/0762-payment-services head | Branch: task/0763-qr-guest-link (check it out; it already holds this brief)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Bug: the e-mail for a QR (bank transfer) payment request links to `/payments/qr/{id}`. That path is relative, so it is not a full web address, and it needs the host's login, so the guest can't open it. Add a public guest page `/pay/{id}/{token}` (and its PNG), where the token is an HMAC of the request, so nobody can guess other requests. Send that full URL in the e-mail.

## 2. Context

- No schema change. The token is `hmac.new(config.secret_key().encode(), f"payreq:{id}:{variable_symbol}".encode(), hashlib.sha256).hexdigest()[:32]`. The same HMAC pattern is in `App/app/havel.py` line ~216. Compare with `hmac.compare_digest`.
- `config.app_base_url()` gives the public https base (used for Stripe return URLs).
- `App/app/routes/payments.py`, the send route (exact):
  ```python
      else:
          link = f"/payments/qr/{request_id}"
  ```
- Host preview routes `@router.get("/payments/qr/{request_id:int}.png")` and `@router.get("/payments/qr/{request_id}")` stay as they are, login only. `payment_request.qr_payload(row)` returns `(payload, png)` and raises `ValueError` when the host has no IBAN.
- `App/app/templates/payments_qr.html` is rendered with `{"nav": "payments", "request": row, "qr_payload": payload, "show_nav": False}`. Its `<img src="/payments/qr/{{ request.id }}.png" …>` must use a `png_url` variable instead, so the guest page can point at the public PNG.
- Test file `App/tests/test_payment_rails.py`, `test_qr_send_mails_page_link` asserts `f"/payments/qr/{rid}" in rows[0]["payload"]`.
- Privacy: the page shows only the amount, the variable symbol, the QR (the host's IBAN is inside the QR by design) and the disclosure. No guest data. No third-party script.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/payment_request.py | edit | `guest_token(row)` and `guest_token_ok(row, token)` |
| App/app/routes/payments.py | edit | public GET `/pay/{id}/{token}` and `.png`; e-mail uses the full public URL; host preview passes `png_url` |
| App/app/templates/payments_qr.html | edit | `png_url`; paid state |
| App/tests/test_payment_rails.py | edit | update 1 test, add 3 |
| docs/tasks/0763-report.md | new | report |
| docs/tasks/0763-qr-guest-link.md | edit | Status line only |

No other file may change.

## 4. Steps

1. `git checkout task/0763-qr-guest-link`; set line 3 to `Status: in-progress`; commit `0763 start`.

2. `App/app/payment_request.py`: add `import hashlib` and `import hmac` to the imports, add `config` to the `from . import …` line, and at the end of the file add:
   ```python
   def guest_token(row: Dict[str, Any]) -> str:
       """0763: unguessable token for the public QR page (no schema change)."""
       message = f"payreq:{int(row['id'])}:{row.get('variable_symbol') or ''}"
       return hmac.new(config.secret_key().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


   def guest_token_ok(row: Dict[str, Any], token: str) -> bool:
       return hmac.compare_digest(guest_token(row), str(token or ""))
   ```
   If importing `config` there causes a circular import, import it inside the function instead.

3. `App/app/routes/payments.py`:
   a. In the send route replace `        link = f"/payments/qr/{request_id}"` with:
   ```python
           link = f"{config.app_base_url()}/pay/{request_id}/{payment_request.guest_token(row)}"
   ```
   b. In the host preview `payment_request_qr`, add `"png_url": f"/payments/qr/{row['id']}.png",` to the render dict.
   c. At the end of the file add:
   ```python
   # --- public guest QR page (0763) ----------------------------------------------


   def _guest_qr_row(request_id: int, token: str):
       row = payment_request.get(request_id)
       if row is None or row["rail"] != "qr" or row["status"] == "cancelled":
           return None
       if not payment_request.guest_token_ok(row, token):
           return None
       return row


   @router.get("/pay/{request_id:int}/{token}.png")
   def guest_qr_png(request_id: int, token: str):
       row = _guest_qr_row(request_id, token)
       if row is None:
           return Response(status_code=404)
       try:
           _, png = payment_request.qr_payload(row)
       except ValueError:
           return Response(status_code=404)
       return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


   @router.get("/pay/{request_id:int}/{token}")
   def guest_qr_page(request: Request, request_id: int, token: str):
       """0763: the guest's bank-transfer page; no login, token-checked."""
       row = _guest_qr_row(request_id, token)
       if row is None:
           return Response(status_code=404)
       try:
           payload, _ = payment_request.qr_payload(row)
       except ValueError:
           return Response(status_code=404)
       response = render(
           request,
           "payments_qr.html",
           {
               "request": row,
               "qr_payload": payload,
               "show_nav": False,
               "png_url": f"/pay/{request_id}/{token}.png",
           },
       )
       response.headers["X-Robots-Tag"] = "noindex"
       return response
   ```
   Route order matters: the `.png` route must be declared before the page route (as above).

4. `App/app/templates/payments_qr.html`: change the `<img src="/payments/qr/{{ request.id }}.png"` to `<img src="{{ png_url }}"`. Directly under the `<h1>` line add:
   ```
     {% if request.status == 'paid' %}<p><span class="ui-badge ui-badge-done" data-tone="green">{{ t('payments.status.paid') }}</span></p>{% endif %}
   ```

5. `App/tests/test_payment_rails.py`:
   a. In `test_qr_send_mails_page_link` replace the `f"/payments/qr/{rid}" in rows[0]["payload"]` assert with:
   ```python
       token = payment_request.guest_token(payment_request.get(rid))
       assert f"/pay/{rid}/{token}" in rows[0]["payload"]
       assert "https://" in rows[0]["payload"] or "http://" in rows[0]["payload"]
   ```
   b. Append:
   ```python
   # --- public guest QR page (0763) -----------------------------------------------


   def test_guest_qr_page_opens_without_login(owner):
       rid = _draft(owner, rail="qr")
       token = payment_request.guest_token(payment_request.get(rid))
       anonymous = TestClient(app)
       page = anonymous.get(f"/pay/{rid}/{token}")
       assert page.status_code == 200
       assert f"/pay/{rid}/{token}.png" in page.text
       png = anonymous.get(f"/pay/{rid}/{token}.png")
       assert png.status_code == 200 and png.headers["content-type"] == "image/png"


   def test_guest_qr_page_rejects_wrong_token_and_card(owner):
       anonymous = TestClient(app)
       rid = _draft(owner, rail="qr")
       assert anonymous.get(f"/pay/{rid}/{'0' * 32}").status_code == 404
       card = _draft(owner, rail="card")
       token = payment_request.guest_token(payment_request.get(card))
       assert anonymous.get(f"/pay/{card}/{token}").status_code == 404


   def test_host_preview_still_needs_login(owner):
       rid = _draft(owner, rail="qr")
       response = TestClient(app).get(f"/payments/qr/{rid}", follow_redirects=False)
       assert response.status_code == 303
   ```
   Make sure `TestClient` and `app` are imported in that file (they are used by its `client` fixture). If `test_guest_qr_page_opens_without_login` fails because the owner has no IBAN, look at how `test_qr_page_renders_disclosure_and_png` gets one (the `owner` fixture) and reuse it; do not change the fixture.
   Run `cd App && .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -15` → all pass.

6. Commit after each of steps 2 to 5 (`0763 step N`).

## 5. Do not touch

`App/app/main.py`, `App/app/static/`, migrations, `stripe_connect.py`, `payment_links.py`, `docs/context/*`. Hard rules 2, 3, 8.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_payment_rails.py tests/test_payment_qr*.py tests/test_payment_request_model.py tests/test_payments_dashboard.py tests/test_payment_services.py -q --tb=short -k "not fits_a_phone" 2>&1 | tail -10` → all pass (drop the `test_payment_qr*.py` glob if no such file exists).
2. `.venv/bin/python -m pytest tests/test_privacy_first.py -q --tb=short 2>&1 | tail -5` → pass.
From the repo root: 3. `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] The QR e-mail carries a full `https://…/pay/{id}/{token}` URL that opens without login.
- [ ] A wrong token, a card request or a cancelled request gives 404; the host preview still needs login.
- [ ] §6 passes.

## 8. Stop and ask

As in the TEMPLATE.

## 9. Report

Write `docs/tasks/0763-report.md` (400 tokens at most), set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/routes/payments.py` (public routes), `App/app/payment_request.py` (token).

## Owner steps

After merge and deploy: create a QR request with your own e-mail, press Odeslat, open the link from the e-mail in a private window.
