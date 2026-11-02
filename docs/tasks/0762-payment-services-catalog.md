# 0762: Saved services (cleaning, late checkout…) with one-tap payment requests

Status: review
Depends on: 0761 (this branch is stacked on it) | Base commit: task/0761-payment-link-share head | Branch: task/0762-payment-services (check it out; it already holds this brief)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Hosts charge the same extras again and again (extra cleaning 800 Kč, late checkout 500 Kč). Let a host save a short list of services with prices on `/payments`. Each saved service gets a "Request payment" link that opens the request form already filled in (amount, reason Custom, and a description the guest sees on Stripe).

## 2. Context

- No schema change. The list is stored as JSON in the existing `settings` key/value table under the key `payment_services:<owner_id>`, through `db.get_setting(key)` / `db.set_setting(key, value)` (App/app/db.py; both work on SQLite and PostgreSQL). The same pattern is used for `celebration_<owner_id>` in `App/app/celebrations.py`. Service names and prices are not personal data, so no retention line is needed.
- `App/app/routes/payments.py`: the request form handler `payment_request_new` already reads `guest_note` from the form and stores it. `payments_page` renders `payments.html` with a dict that contains `"selected_reservation_id": selected_reservation_id,`.
- `App/app/payment_links.py`:
  ```python
  def product_name(row: Dict[str, Any]) -> str:
      """What the guest sees on Stripe Checkout and the receipt (Czech)."""
      reason = host_i18n.translate("cs", f"payments.reason.{row['reason']}")
      return f"{reason} (žádost č. {row['id']})"
  ```
- `App/app/templates/payments.html` (on this branch), exact lines:
  - section start: `<div class="ui-section">` followed by `  <h2>{{ t('payments.new.title') }}</h2>`
  - amount: `      <input class="ui-input" type="number" name="amount_czk" min="1" step="1" required>`
  - reasons: `        {% for r in reasons %}<label class="ui-chip"><input type="radio" name="reason" value="{{ r }}" {% if loop.first %}required{% endif %}> {{ t('payments.reason.' ~ r) }}</label>{% endfor %}`
  - guest e-mail label: `      <span>{{ t('payments.field.guest_email') }}</span>`
  - list cell: `          <td data-label="{{ t('payments.col.reason') }}">{{ t('payments.reason.' ~ req.reason) }}</td>`
- `App/app/host_i18n.py` anchors: English `        "payments.share.back": "Back to payments",`, Czech `        "payments.share.back": "Zpět na platby",`.
- No CSS or JS change; no-JS forms. Copy never says Connect or webhook.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/payment_services.py | new | list / add / remove / get |
| App/app/routes/payments.py | edit | 2 POST routes; prefill from `?service=` |
| App/app/payment_links.py | edit | `product_name` uses the description for Custom |
| App/app/templates/payments.html | edit | services section; description field; prefill |
| App/app/host_i18n.py | edit | en + cs keys |
| App/tests/test_payment_services.py | new | unit + route tests + 390 px browser test |
| App/tests/test_payment_rails.py | edit | one product-name test |
| docs/design/pages/payments.md | edit | one line |
| docs/tasks/screenshots-0762/services-390.png | new | from the browser test |
| docs/tasks/0762-report.md | new | report |
| docs/tasks/0762-payment-services-catalog.md | edit | Status line only |

No other file may change.

## 4. Steps

1. `git checkout task/0762-payment-services`; set line 3 to `Status: in-progress`; commit `0762 start`.

2. Create `App/app/payment_services.py`:
   ```python
   """Saved extras a host charges often (0762): name + price, per owner.

   Stored as JSON in the settings table (key payment_services:<owner>), so no
   schema change. Not personal data: a service name and a price.
   """
   from __future__ import annotations

   import json
   import secrets
   from typing import Any, Dict, List, Optional

   from . import db

   MAX_SERVICES = 20
   MAX_NAME = 60
   MAX_AMOUNT = 1_000_000


   def _key(owner_user_id: int) -> str:
       return f"payment_services:{int(owner_user_id)}"


   def list_for(owner_user_id: int) -> List[Dict[str, Any]]:
       raw = db.get_setting(_key(owner_user_id)) or "[]"
       try:
           items = json.loads(raw)
       except ValueError:
           return []
       return [i for i in items if isinstance(i, dict) and i.get("id") and i.get("name")]


   def get(owner_user_id: int, service_id: str) -> Optional[Dict[str, Any]]:
       return next((s for s in list_for(owner_user_id) if s["id"] == service_id), None)


   def add(owner_user_id: int, name: str, amount_czk: int) -> Dict[str, Any]:
       name = " ".join((name or "").split())[:MAX_NAME]
       if not name:
           raise ValueError("name required")
       if not isinstance(amount_czk, int) or not 1 <= amount_czk <= MAX_AMOUNT:
           raise ValueError("amount out of range")
       items = list_for(owner_user_id)
       if len(items) >= MAX_SERVICES:
           raise ValueError("too many services")
       item = {"id": secrets.token_hex(4), "name": name, "amount_czk": amount_czk}
       items.append(item)
       db.set_setting(_key(owner_user_id), json.dumps(items, ensure_ascii=False))
       return item


   def remove(owner_user_id: int, service_id: str) -> bool:
       items = list_for(owner_user_id)
       kept = [s for s in items if s["id"] != service_id]
       if len(kept) == len(items):
           return False
       db.set_setting(_key(owner_user_id), json.dumps(kept, ensure_ascii=False))
       return True
   ```

3. `App/app/routes/payments.py`:
   a. Add `payment_services` to the `from .. import …` line (keep alphabetical order: after `payment_request`).
   b. In `payments_page`, directly above `    return render(` add:
   ```python
       services = payment_services.list_for(owner_id)
       prefill = payment_services.get(owner_id, str(request.query_params.get("service") or ""))
   ```
   and under `            "selected_reservation_id": selected_reservation_id,` add:
   ```python
               "services": services,
               "prefill": prefill,
   ```
   c. Directly above `@router.post("/payments/requests/new")` add:
   ```python
   @router.post("/payments/services")
   async def payment_service_add(request: Request):
       """0762: save one extra (name + price)."""
       guard = auth.require_login(request)
       if guard:
           return guard
       form = await request.form()
       raw_amount = str(form.get("amount_czk") or "").strip()
       if not raw_amount.isdigit():
           return _back("/payments", err=_flash(request, "payments.err.amount"))
       try:
           payment_services.add(access.owner_id(request), str(form.get("name") or ""), int(raw_amount))
       except ValueError:
           return _back("/payments", err=_flash(request, "payments.services.err"))
       return _back("/payments", msg=_flash(request, "payments.services.saved"))


   @router.post("/payments/services/{service_id}/delete")
   async def payment_service_delete(request: Request, service_id: str):
       guard = auth.require_login(request)
       if guard:
           return guard
       payment_services.remove(access.owner_id(request), service_id)
       return _back("/payments", msg=_flash(request, "payments.services.removed"))


   ```

4. `App/app/payment_links.py`: replace the body of `product_name` (the two lines after the docstring) with:
   ```python
       note = " ".join((row.get("guest_note") or "").split())[:60]
       if row["reason"] == "custom" and note:
           return f"{note} (žádost č. {row['id']})"
       reason = host_i18n.translate("cs", f"payments.reason.{row['reason']}")
       return f"{reason} (žádost č. {row['id']})"
   ```

5. `App/app/templates/payments.html`:
   a. Directly above the `<div class="ui-section">` whose next line is `  <h2>{{ t('payments.new.title') }}</h2>`, insert the services section:
   ```
   <div class="ui-section" data-payment-services>
     <h2>{{ t('payments.services.title') }}</h2>
     {% if services %}
     <ul>
       {% for s in services %}
       <li data-service="{{ s.id }}">
         <strong>{{ s.name }}</strong> · {{ s.amount_czk }} {{ t('payments.czk') }}
         <a class="ui-btn ui-btn-secondary ui-btn-compact" href="/payments?service={{ s.id }}#new-request">{{ t('payments.services.request') }}</a>
         <form method="post" action="/payments/services/{{ s.id }}/delete" style="display:inline">
           <button class="ui-btn ui-btn-quiet ui-btn-compact" type="submit">{{ t('payments.services.remove') }}</button>
         </form>
       </li>
       {% endfor %}
     </ul>
     {% else %}
     <p class="ui-sub">{{ t('payments.services.empty') }}</p>
     {% endif %}
     <form method="post" action="/payments/services" class="ui-form">
       <label class="ui-field">
         <span>{{ t('payments.services.name') }}</span>
         <input class="ui-input" type="text" name="name" maxlength="60" required>
       </label>
       <label class="ui-field">
         <span>{{ t('payments.field.amount') }}</span>
         <input class="ui-input" type="number" name="amount_czk" min="1" step="1" required>
       </label>
       {{ ui_button(t('payments.services.add'), 'secondary', type='submit') }}
     </form>
   </div>
   ```
   b. On the request section's opening `<div class="ui-section">` (the one directly above `  <h2>{{ t('payments.new.title') }}</h2>`), add `id="new-request"`: `<div class="ui-section" id="new-request">`.
   c. Replace the amount input line with:
   `      <input class="ui-input" type="number" name="amount_czk" min="1" step="1" required{% if prefill %} value="{{ prefill.amount_czk }}"{% endif %}>`
   d. In the reasons line, change `{% if loop.first %}required{% endif %}>` to `{% if loop.first %}required{% endif %}{% if prefill and r == 'custom' %} checked{% endif %}>`.
   e. Directly above the `<label class="ui-field">` that contains `      <span>{{ t('payments.field.guest_email') }}</span>`, insert:
   ```
       <label class="ui-field">
         <span>{{ t('payments.field.note') }}</span>
         <input class="ui-input" type="text" name="guest_note" maxlength="60"{% if prefill %} value="{{ prefill.name }}"{% endif %}>
       </label>
   ```
   f. Replace the list cell line with:
   `          <td data-label="{{ t('payments.col.reason') }}">{% if req.reason == 'custom' and req.guest_note %}{{ req.guest_note }}{% else %}{{ t('payments.reason.' ~ req.reason) }}{% endif %}</td>`

   If `ui-btn-quiet` makes `scripts/design_lint.py` fail, use `ui-btn-secondary` instead and note it in the report.

6. `App/app/host_i18n.py`: under the English anchor insert:
   ```python
           "payments.services.title": "Your services",
           "payments.services.empty": "Save what you charge often, for example extra cleaning 800 CZK or late checkout 500 CZK. Then one tap fills in the request.",
           "payments.services.name": "Service name",
           "payments.services.add": "Save service",
           "payments.services.request": "Request payment",
           "payments.services.remove": "Remove",
           "payments.services.saved": "Service saved.",
           "payments.services.removed": "Service removed.",
           "payments.services.err": "That service cannot be saved. Check the name and price (20 services at most).",
           "payments.field.note": "What the guest pays for (optional)",
   ```
   Under the Czech anchor insert:
   ```python
           "payments.services.title": "Vaše služby",
           "payments.services.empty": "Uložte si, co účtujete často, třeba úklid navíc 800 Kč nebo pozdní odjezd 500 Kč. Žádost pak vyplníte jedním klepnutím.",
           "payments.services.name": "Název služby",
           "payments.services.add": "Uložit službu",
           "payments.services.request": "Požádat o platbu",
           "payments.services.remove": "Odebrat",
           "payments.services.saved": "Služba uložena.",
           "payments.services.removed": "Služba odebrána.",
           "payments.services.err": "Službu nejde uložit. Zkontrolujte název a cenu (nejvýš 20 služeb).",
           "payments.field.note": "Za co host platí (nepovinné)",
   ```
   Run `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q -k same_keys 2>&1 | tail -3` → pass.

7. `App/tests/test_payment_rails.py`, append:
   ```python
   def test_custom_request_uses_the_description_as_product_name(owner):
       rid = payment_request.create(
           owner, reason="custom", amount_czk=500, rail="card",
           expires_at="2026-11-27", guest_note="Pozdní odjezd",
       )
       assert payment_links.product_name(payment_request.get(rid)) == f"Pozdní odjezd (žádost č. {rid})"
   ```
   Add `payment_links` to that file's `from app import …` line if it is not there.

8. Create `App/tests/test_payment_services.py`. Copy the imports, `_cleanup`, `owner`, `stripe_env` and browser server/login code from `App/tests/test_payments_setup_browser.py`, with `OWNER = "payservices"` and `SHOTS = … / "screenshots-0762"`; `_cleanup` also runs `db.execute("DELETE FROM settings WHERE key = ?", (f"payment_services:{oid}",))` and deletes `payment_request` rows for the owner. Add a `client` fixture like the one in `App/tests/test_payments_consent.py`. Tests:
   - `test_add_list_remove`: `payment_services.add(owner, "  Úklid   navíc ", 800)` → `list_for` has one item named `"Úklid navíc"`; `remove` returns True and the list is empty.
   - `test_add_rejects_bad_input`: `pytest.raises(ValueError)` for name `""`, amount `0`, and a 21st service after adding 20.
   - `test_route_add_and_prefill`: `client.post("/payments/services", data={"name": "Pozdní odjezd", "amount_czk": "500"}, follow_redirects=False)` → 303 with `msg=`; take the id from `payment_services.list_for(owner)[0]["id"]`; `client.get(f"/payments?service={sid}")` contains `value="500"`, `value="Pozdní odjezd"` and `checked`.
   - `test_route_delete_only_own`: a service saved for the owner is removed by `client.post(f"/payments/services/{sid}/delete", follow_redirects=False)`; deleting an unknown id still answers 303.
   - `test_services_fit_a_phone` (browser, same pattern as the setup browser test): save two services, open `/payments?lang=cs&service=<first id>` at 390×844, assert no horizontal overflow and `[data-payment-services] li` count is 2, screenshot `services-390.png`.
   Run `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payment_services.py tests/test_payment_rails.py -q --tb=short -rs 2>&1 | tail -10` → all pass, 0 skipped. Open the PNG and check it.

9. `docs/design/pages/payments.md`: after the `- section 2:` line add `- services (0762): "Your services" section above the request form: saved name + price rows with "Request payment" (link to /payments?service=…#new-request, prefills amount, Custom and the description) and Remove; a 2-field add form.`

10. Commit after each of steps 2 to 9 (`0762 step N`).

## 5. Do not touch

`App/app/db.py`, migrations, `App/app/static/`, `App/app/main.py`, `stripe_connect.py`, `docs/context/*`. Hard rules 2, 5, 6, 7, 8.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_payment_services.py tests/test_payment_rails.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payments_consent.py -q --tb=short -k "not fits_a_phone" 2>&1 | tail -10` → all pass.
2. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_payment_services.py tests/test_payments_setup_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs -k "phone or guardrail or design" 2>&1 | tail -10` → all pass, 0 skipped.
3. `.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -3` → `design lint: OK`.
From the repo root: 4. `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] A host can save, see and remove services on `/payments`; at most 20.
- [ ] "Request payment" opens the form with amount, Custom and the description filled in.
- [ ] A Custom card request shows the description to the guest on Stripe (`product_name`).
- [ ] §6 passes; `docs/tasks/screenshots-0762/services-390.png` shows the Czech section with no overflow.

## 8. Stop and ask

As in the TEMPLATE.

## 9. Report

Write `docs/tasks/0762-report.md` (500 tokens at most), set `Status: review`. Do not push.

## Risk list (for the reviewer)

`App/app/payment_services.py`, `App/app/routes/payments.py`, `App/app/payment_links.py` (guest-facing name).

## Owner steps

After merge and deploy: Platby → Vaše služby → save "Úklid navíc 800" → "Požádat o platbu" → the form is filled in.
