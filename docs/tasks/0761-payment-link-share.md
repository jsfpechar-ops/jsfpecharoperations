# 0761: Get a card payment link and share it (no guest e-mail needed)

Status: review
Depends on: none | Base commit: 1bd21484 | Branch: task/0761-payment-link-share (check it out; it already holds this brief)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Today a card request can only reach the guest by e-mail, and only when the host typed the guest's e-mail. Hosts talk to guests in WhatsApp or the Airbnb chat, so add a "Get link" button on every open card request. It makes (or reuses) the Stripe link and opens a share page with the link, a Copy button, "Send on WhatsApp" and "Send by e-mail".

## 2. Context

- Owner goal (1 Nov 2026): hosts "quickly and easily generate a payment link" for extras (cleaning, locksmith…). Setup must be dumbproof; copy is plain and never says Connect or webhook.
- **CSP lesson (0730):** our CSP has `form-action 'self'`. A form POST must never redirect to another site. The new POST redirects to our own share page only; Stripe and WhatsApp are opened by plain links.
- `payment_links.send(request_id)` (App/app/payment_links.py) returns the link URL, reusing an active link, or `None` when the host's Stripe is not ready; it raises `stripe_connect.StripeOff` when payments are off.
- `App/app/routes/payments.py`: imports already include `host_i18n`, `payment_links`, `payment_request`, `stripe_connect`, `RedirectResponse`, `render`, `_back`, `_flash`. The send route starts with the line `@router.post("/payments/requests/{request_id}/send")`.
- `App/app/templates/payments.html`, request row actions (exact):
  ```
              {% if req.status == 'draft' and req.guest_email %}
              <form method="post" action="/payments/requests/{{ req.id }}/send" style="display:inline">
  ```
- `host_i18n` placeholders use `%(name)s`. English anchor: `        "payments.qr.preview": "Show QR",`; Czech anchor: `        "payments.qr.preview": "Zobrazit QR",` (raw UTF-8 in that file is fine).
- Copy button: `copy_button(target_id)` from `_components.html` copies an input's `value`.
- Page add-on: `docs/design/pages/payments.md` (you add 3 lines, step 7). No CSS or JS change.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/payments.py | edit | POST `/payments/requests/{id}/link`, GET `/payments/requests/{id}/share` |
| App/app/templates/payments_share.html | new | share page |
| App/app/templates/payments.html | edit | "Get link" button on open card requests |
| App/app/host_i18n.py | edit | en + cs keys |
| App/tests/test_payment_rails.py | edit | 4 tests |
| App/tests/test_payment_share_browser.py | new | 390 px geometry + screenshot |
| docs/design/pages/payments.md | edit | share page lines |
| docs/tasks/screenshots-0761/share-390.png | new | from the browser test |
| docs/tasks/0761-report.md | new | report |
| docs/tasks/0761-payment-link-share.md | edit | Status line only |

No other file may change.

## 4. Steps

1. `git checkout task/0761-payment-link-share`; set line 3 to `Status: in-progress`; commit `0761 start`.

2. `App/app/routes/payments.py`: directly above `@router.post("/payments/requests/{request_id}/send")` insert:
   ```python
   _OPEN_CARD = ("draft", "sent", "awaiting_payment")


   def _own_card_request(request: Request, request_id: int):
       """The owner's open card request, or None."""
       row = payment_request.get(request_id)
       if row is None or int(row["owner_user_id"]) != access.owner_id(request):
           return None
       if row["rail"] != "card" or row["status"] not in _OPEN_CARD:
           return None
       return row


   @router.post("/payments/requests/{request_id}/link")
   async def payment_request_link(request: Request, request_id: int):
       """0761: make (or reuse) the card link without an e-mail, then show the
       share page. Never redirect this POST off-site (CSP form-action, 0730)."""
       guard = auth.require_login(request)
       if guard:
           return guard
       row = _own_card_request(request, request_id)
       if row is None:
           return _back("/payments", err=_flash(request, "payments.err.invalid"))
       try:
           link = payment_links.send(request_id) or ""
       except stripe_connect.StripeOff:
           return _back("/payments", err=_flash(request, "payments.err.stripe_off"))
       if not link:
           return _back("/payments", err=_flash(request, "payments.err.not_ready"))
       if row["status"] == "draft":
           from datetime import date

           payment_request.set_status(request_id, "sent", today=date.today())
       return RedirectResponse(f"/payments/requests/{request_id}/share", status_code=303)


   @router.get("/payments/requests/{request_id}/share")
   def payment_request_share(request: Request, request_id: int):
       """0761: the link, Copy, WhatsApp and e-mail. Reached only after the POST."""
       guard = auth.require_login(request)
       if guard:
           return guard
       row = _own_card_request(request, request_id)
       if row is None or not row.get("stripe_payment_link_id"):
           return _back("/payments", err=_flash(request, "payments.err.invalid"))
       try:
           link = payment_links.send(request_id) or ""
       except stripe_connect.StripeOff:
           return _back("/payments", err=_flash(request, "payments.err.stripe_off"))
       if not link:
           return _back("/payments", err=_flash(request, "payments.err.not_ready"))
       from urllib.parse import quote

       lang = host_i18n.lang_from_request(request)
       reason = host_i18n.translate(lang, f"payments.reason.{row['reason']}")
       message = host_i18n.translate(
           lang, "payments.share.message", reason=reason, amount=row["amount_czk"], link=link
       )
       subject = host_i18n.translate(lang, "payments.share.subject")
       email = (row.get("guest_email") or "").strip()
       return render(
           request,
           "payments_share.html",
           {
               "nav": "payments",
               "how_key": "payments",
               "req": row,
               "link": link,
               "whatsapp_url": "https://wa.me/?text=" + quote(message),
               "mailto_url": f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(message)}",
           },
       )


   ```
   If `payment_request.get` returns a Row and `.get(...)` fails on it, wrap it: `row = dict(row)` right after the None check in `_own_card_request`.

3. Create `App/app/templates/payments_share.html`:
   ```
   {% extends "host_page.html" %}
   {% set nav = 'payments' %}
   {% set how_key = 'payments' %}
   {% set body_kind = 'detail' %}
   {% from "_ui.html" import ui_button with context %}
   {% from "_components.html" import copy_button with context %}
   {% block title %}{{ t('payments.share.title') }}{% endblock %}
   {% block primary_action %}{% endblock %}
   {% block tabs %}{% endblock %}
   {% block toolbar %}{% endblock %}
   {% block body %}
   <div class="ui-section" data-payment-share>
     <p>{{ t('payments.reason.' ~ req.reason) }} · <strong>{{ req.amount_czk }} {{ t('payments.czk') }}</strong></p>
     <p>{{ t('payments.share.lead') }}</p>
     <label class="ui-field" for="pay-share-link">
       <span>{{ t('payments.share.link_label') }}</span>
       <input class="ui-input" id="pay-share-link" type="text" readonly value="{{ link }}">
     </label>
     <div class="ui-form-actions">
       {{ copy_button('pay-share-link') }}
       {{ ui_button(t('payments.share.email'), 'secondary', href=mailto_url, attrs='data-no-prefetch') }}
       {{ ui_button(t('payments.share.whatsapp'), 'primary', href=whatsapp_url, attrs='target="_blank" rel="noopener"') }}
     </div>
     <p class="ui-sub">{{ t('payments.share.paid_note') }}</p>
     <p><a href="/payments">{{ t('payments.share.back') }}</a></p>
   </div>
   {% endblock %}
   ```

4. `App/app/templates/payments.html`: directly above the line `            {% if req.status == 'draft' and req.guest_email %}` insert:
   ```
               {% if req.rail == 'card' and req.status in ['draft', 'sent', 'awaiting_payment'] %}
               <form method="post" action="/payments/requests/{{ req.id }}/link" style="display:inline">
                 <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('payments.get_link') }}</button>
               </form>
               {% endif %}
   ```
   Then, in the same block, change `            {% elif req.status == 'draft' %}` to `            {% elif req.status == 'draft' and req.rail != 'card' %}` (a card request no longer needs an e-mail, so the "add the e-mail first" hint stays only for QR).

5. `App/app/host_i18n.py`: under the English anchor insert:
   ```python
           "payments.get_link": "Get link",
           "payments.share.title": "Share the payment link",
           "payments.share.lead": "Send this link to the guest in any chat. They pay by card on Stripe, and you see it here as paid.",
           "payments.share.link_label": "Payment link",
           "payments.share.whatsapp": "Send on WhatsApp",
           "payments.share.email": "Send by e-mail",
           "payments.share.subject": "Payment request",
           "payments.share.message": "%(reason)s: %(amount)s CZK. You can pay by card here: %(link)s",
           "payments.share.paid_note": "The link works for one payment. When the guest pays, the request turns to Paid.",
           "payments.share.back": "Back to payments",
   ```
   Under the Czech anchor insert:
   ```python
           "payments.get_link": "Získat odkaz",
           "payments.share.title": "Sdílejte odkaz k platbě",
           "payments.share.lead": "Pošlete odkaz hostovi do jakéhokoli chatu. Zaplatí kartou přes Stripe a tady uvidíte, že je zaplaceno.",
           "payments.share.link_label": "Odkaz k platbě",
           "payments.share.whatsapp": "Poslat přes WhatsApp",
           "payments.share.email": "Poslat e-mailem",
           "payments.share.subject": "Žádost o platbu",
           "payments.share.message": "%(reason)s: %(amount)s Kč. Zaplatit kartou můžete zde: %(link)s",
           "payments.share.paid_note": "Odkaz platí pro jednu platbu. Až host zaplatí, žádost se změní na Zaplaceno.",
           "payments.share.back": "Zpět na platby",
   ```
   Run `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q -k same_keys 2>&1 | tail -3` → pass.

6. `App/tests/test_payment_rails.py`, append at the end:
   ```python
   # --- share link without e-mail (0761) -----------------------------------------


   def test_get_link_without_email_opens_share_page(owner, client, stripe_env, fake_link):
       _complete_account(owner)
       rid = _draft(owner, rail="card", email="")
       response = client.post(f"/payments/requests/{rid}/link", follow_redirects=False)
       assert response.status_code == 303
       assert response.headers["location"] == f"/payments/requests/{rid}/share"
       assert payment_request.get(rid)["status"] == "sent"
       page = client.get(f"/payments/requests/{rid}/share")
       assert page.status_code == 200
       assert "https://buy.stripe.com/test_1" in page.text
       assert "https://wa.me/?text=" in page.text
       assert len(fake_link.created) == 1  # the page reused the link


   def test_get_link_never_redirects_off_site(owner, client, stripe_env, fake_link):
       _complete_account(owner)
       rid = _draft(owner, rail="card")
       location = client.post(f"/payments/requests/{rid}/link", follow_redirects=False).headers["location"]
       assert location.startswith("/") and not location.startswith("//")


   def test_get_link_refused_when_not_ready(owner, client, stripe_env):
       rid = _draft(owner, rail="card")
       response = client.post(f"/payments/requests/{rid}/link", follow_redirects=False)
       assert response.headers["location"].startswith("/payments?err=")
       assert payment_request.get(rid)["status"] == "draft"


   def test_share_page_hidden_from_other_owners_and_qr(owner, client, stripe_env, fake_link):
       rid = _draft(owner, rail="qr")
       response = client.post(f"/payments/requests/{rid}/link", follow_redirects=False)
       assert "err=" in response.headers["location"]
       response = client.get(f"/payments/requests/{rid}/share", follow_redirects=False)
       assert "err=" in response.headers["location"]
   ```
   If `_draft(..., email="")` fails because the model wants `None`, pass `email=None`. Run `cd App && .venv/bin/python -m pytest tests/test_payment_rails.py -q --tb=short -x 2>&1 | tail -15` → all pass.

7. `docs/design/pages/payments.md`: under the `## Body` list, after the line starting `- section 2:`, add:
   ```
   - request row: open card requests get a `secondary compact` "Get link" (POST, then our share page; never a POST to Stripe).
   - share page `/payments/requests/{id}/share` (template `payments_share.html`, body_kind `detail`): reason and amount, the link in a read-only field, then Copy, Send by e-mail (secondary) and Send on WhatsApp (primary, new tab), one note, a back link.
   ```

8. Create `App/tests/test_payment_share_browser.py`, modelled on `App/tests/test_payments_setup_browser.py` (copy its imports, fixtures and server/login code). Changes: docstring `"""0761: share page fits a phone."""`, `OWNER = "payshare"`, `SHOTS = … / "screenshots-0761"`, `_cleanup` also deletes `payment_request` and `stripe_account` rows for the owner. In the test: insert a complete `stripe_account` row (same columns as `_complete_account` in test_payment_rails.py), create a card request with `payment_request.create(...)`, then `db.execute("UPDATE payment_request SET stripe_payment_link_id = 'plink_x', status = 'sent' WHERE id = ?", (rid,))`, and monkeypatch `app.payment_links.send` to `lambda _rid: "https://buy.stripe.com/test_share_long_link_1234567890"`. Open `/payments/requests/{rid}/share?lang=cs` at 390×844, assert no horizontal overflow (`scrollWidth - clientWidth <= 0`) and that `[data-payment-share] input` is visible, save `share-390.png`.
   Run `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payment_share_browser.py -q --tb=short -rs 2>&1 | tail -8` → 1 passed, 0 skipped. Open the PNG and check it.

9. Commit after each of steps 2 to 8 (`0761 step N`).

## 5. Do not touch

`App/app/main.py` (CSP), `App/app/static/`, `payment_links.py`, `stripe_connect.py`, migrations, `docs/context/*`. Hard rules 2, 6, 7, 8.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_payment_rails.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payments_consent.py -q --tb=short -k "not fits_a_phone" 2>&1 | tail -10` → all pass.
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payment_share_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -10` → all pass, 0 skipped.
3. `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -3` → `design lint: OK`.
From the repo root: 4. `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] An open card request without a guest e-mail shows "Get link"; pressing it lands on our share page with the Stripe link, Copy, e-mail and WhatsApp.
- [ ] The POST never redirects off-site; a not-ready account gets an error flash and the request stays a draft.
- [ ] §6 passes; `docs/tasks/screenshots-0761/share-390.png` shows the Czech share page with no overflow.

## 8. Stop and ask

As in the TEMPLATE.

## 9. Report

Write `docs/tasks/0761-report.md` (500 tokens at most), set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/routes/payments.py` (ownership checks, redirects), `payments_share.html`.

## Owner steps

After merge and deploy: Platby → create a card request without an e-mail → "Získat odkaz" → "Poslat přes WhatsApp".
