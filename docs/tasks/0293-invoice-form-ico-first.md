# 0293: Invoice form: IČO lookup first, calmer customer and items layout

Status: todo
Depends on: 0292 | Base commit: the 0292 commit | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner (2026-10-24) finds the new-invoice form ugly and wants the customer's IČO with **Fill from register** first, as in the Business (operator) form, so a host fills it immediately when the customer is a company. This brief puts a lookup strip at the top of Customer, orders the address fields the way people write an address, tidies the supplier row and makes item rows compact.

## 2. Context

- Template `App/app/templates/invoice_form.html`. The supplier block is lines ~38-58 (`<div class="ui-section invoice-supplier">` … its closing `</div>`); the customer block is lines ~60-110 (`<div class="ui-section">` with `<h2>{{ t('invoice.section.customer') }}</h2>` … the closing `</div>` after the `buyer_email` field). Field names and ids must not change (route `App/app/routes/invoices.py` reads them; the inline script uses `.invoice-supplier-meta`, `.invoice-supplier a`, `#legal_entity_id`).
- The supplier link must remain the **first `<a>` inside `.invoice-supplier`** (the script swaps its href).
- Existing CSS: `App/app/static/app.css` `.invoice-buyer-grid` (3 columns) line ~481; host2.css lines ~411-441 the items grid and `@container (max-width: 850px)` stacked items.
- Strings EN/CS live in `App/app/host_i18n.py` near `"invoice.buyer.ico"` (line ~1385 en, ~2928 cs); VI in `App/app/host_vi_i18n.py` (grep `invoice.buyer.ico`).
- host2.css lint: tokens only, no raw colours, no bare px except 0 and 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/invoice_form.html | edit | steps 1-2 |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | step 3 |
| App/app/static/host2.css | append | step 4 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0293` |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0293_invoice_form.py | new | step 5 |

No other file may change, except a test that pinned the old field order or classes (report each).

## 4. Steps

1. Replace the supplier block with:

```jinja
  <div class="ui-section invoice-supplier">
    <a class="invoice-supplier-edit" href="/entities?edit={{ entity.id }}&amp;next={{ (('/invoices/new?reservation_id=' ~ (stay.reservation.id if stay else '') ~ '&entity=' ~ entity.id) | urlencode) }}#entity-invoice">{{ t('invoice.edit_details') }}</a>
    <div class="ui-field invoice-supplier-picker">
      <label for="legal_entity_id">{{ t('invoice.entity.label') }}</label>
      <select id="legal_entity_id" name="legal_entity_id">
        {% for option in entities %}
          <option value="{{ option.id }}"
                   data-vat-payer="{{ 1 if (option.vat_status or 'non_payer') == 'payer' else 0 }}"
                   {% if entity and option.id == entity.id %}selected{% endif %}>{{ option.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="invoice-supplier-meta">
      <span class="invoice-supplier-name">{{ entity.name }}</span>
      <span class="ui-sub">
        {% if entity.ico %}IČO {{ entity.ico }}{% endif %}
        {% if entity.seat %}· {{ entity.seat }}{% endif %}
      </span>
    </div>
  </div>
```

2. Replace the customer block with:

```jinja
  <div class="ui-section invoice-customer">
    <h2>{{ t('invoice.section.customer') }}</h2>
    <div class="invoice-lookup">
      <div class="ui-field invoice-lookup-ico">
        <label for="buyer_ico">{{ t('invoice.buyer.ico') }} <span class="opt">{{ t('common.optional') }}</span></label>
        <div class="invoice-lookup-row">
          <input type="text" id="buyer_ico" name="buyer_ico" inputmode="numeric" maxlength="8" autocomplete="off" value="{{ values.get('buyer_ico', '') }}">
          <button class="ui-btn ui-btn-primary" type="submit" name="fill_buyer_from_register" value="1" formnovalidate>{{ t('ares.fill') }}</button>
        </div>
        {% if ares_error %}<p class="alert">{{ ares_error }}</p>{% endif %}
        {% if ares_note %}<p class="hint">{{ t('ares.source_note') }} {{ ares_note }}</p>{% endif %}
      </div>
      {% if show_fill_guest %}
      <div class="invoice-lookup-guest">
        <span class="ui-sub">{{ t('invoice.buyer.or') }}</span>
        <button type="submit" name="fill_from_guest" value="1" formnovalidate class="ui-btn ui-btn-secondary">{{ t('invoice.fill_guest.button') }}</button>
      </div>
      {% endif %}
    </div>
    <div class="invoice-buyer-fields">
      <div class="ui-field invoice-f-full">
        <label for="buyer_name">{{ t('invoice.buyer.name') }}</label>
        <input type="text" id="buyer_name" name="buyer_name" required autocomplete="organization" value="{{ values.get('buyer_name', '') }}">
      </div>
      <div class="ui-field invoice-f-full">
        <label for="buyer_street">{{ t('invoice.buyer.street') }}</label>
        <input type="text" id="buyer_street" name="buyer_street" autocomplete="address-line1" value="{{ values.get('buyer_street', '') }}">
      </div>
      <div class="ui-field invoice-f-zip">
        <label for="buyer_zip">{{ t('invoice.buyer.zip') }}</label>
        <input type="text" id="buyer_zip" name="buyer_zip" autocomplete="postal-code" value="{{ values.get('buyer_zip', '') }}">
      </div>
      <div class="ui-field invoice-f-city">
        <label for="buyer_city">{{ t('invoice.buyer.city') }}</label>
        <input type="text" id="buyer_city" name="buyer_city" autocomplete="address-level2" value="{{ values.get('buyer_city', '') }}">
      </div>
      <div class="ui-field invoice-f-full">
        <label for="buyer_country">{{ t('invoice.buyer.country') }}</label>
        <select id="buyer_country" name="buyer_country">
          {% for country in countries %}
            <option value="{{ country.code }}" {% if values.get('buyer_country', 'CZE') == country.code %}selected{% endif %}>{{ country.label }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="ui-field invoice-f-half">
        <label for="buyer_dic">{{ t('invoice.buyer.dic') }} <span class="opt">{{ t('common.optional') }}</span></label>
        <input type="text" id="buyer_dic" name="buyer_dic" value="{{ values.get('buyer_dic', '') }}">
      </div>
      <div class="ui-field invoice-f-half">
        <label for="buyer_email">{{ t('invoice.buyer.email') }} <span class="opt">{{ t('common.optional') }}</span></label>
        <input type="email" id="buyer_email" name="buyer_email" autocomplete="email" value="{{ values.get('buyer_email', '') }}">
      </div>
    </div>
  </div>
```

   In the items table, change each `data-remove-item` button's classes from `ui-btn ui-btn-secondary ui-btn-compact` to `ui-btn ui-btn-quiet ui-btn-compact` (two places), and the `data-add-item` button stays secondary.

3. New key `invoice.buyer.or`: en "or", cs "nebo", vi "hoặc" (next to `invoice.buyer.ico` in each language).

4. Append to host2.css:

```css
/* 0293: invoice builder (owner 2026-10-24): the IČO lookup comes first, the
   address reads like an address, item rows stay compact. */
.host-workspace .invoice-supplier { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2) var(--space-4); align-items: start; }
.host-workspace .invoice-supplier-edit { grid-column: 2; grid-row: 1; font-size: var(--size-14); }
.host-workspace .invoice-supplier-picker { grid-column: 1; grid-row: 1; max-width: 22rem; margin: 0; }
.host-workspace .invoice-supplier-meta { grid-column: 1 / -1; padding: 0; }
.host-workspace .invoice-lookup { display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--space-3) var(--space-4); margin: var(--space-3) 0 var(--space-5); padding: var(--space-4); border: 1px solid var(--line-strong); border-radius: var(--radius-md); background: var(--surface-2); }
.host-workspace .invoice-lookup-ico { flex: 1 1 18rem; min-width: 0; margin: 0; }
.host-workspace .invoice-lookup-row { display: flex; gap: var(--space-2); }
.host-workspace .invoice-lookup-row input { flex: 1 1 auto; min-width: 0; max-width: 12rem; }
.host-workspace .invoice-lookup-row .ui-btn { flex: 0 0 auto; }
.host-workspace .invoice-lookup-guest { display: flex; align-items: center; gap: var(--space-3); }
.host-workspace .invoice-buyer-fields { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: var(--space-4); }
.host-workspace .invoice-buyer-fields > .ui-field { margin: 0; min-width: 0; }
.host-workspace .invoice-f-full { grid-column: span 6; }
.host-workspace .invoice-f-zip { grid-column: span 2; }
.host-workspace .invoice-f-city { grid-column: span 4; }
.host-workspace .invoice-f-half { grid-column: span 3; }
@media (max-width: 639px) {
  .host-workspace .invoice-buyer-fields > .ui-field { grid-column: 1 / -1; }
  .host-workspace .invoice-lookup-row input { max-width: none; }
  .host-workspace .invoice-supplier { grid-template-columns: minmax(0, 1fr); }
  .host-workspace .invoice-supplier-edit { grid-column: 1; grid-row: 3; }
}
@container (max-width: 850px) {
  .invoice-items-grid tbody tr { gap: var(--space-2) var(--space-4); padding: var(--space-3) 0; }
  .invoice-items-grid td.row-actions { grid-column: auto / -1; text-align: right; }
}
```

   The Fill-from-register button is this section's one primary (MASTER 7.1: one primary per group); **Issue invoice** stays the form's primary in its action bar. If `tests/test_design_invoices.py` or the guardrails test counts primaries per page and fails, change that assertion to count primaries inside `.invoice-actions` only, and report it.

5. New `App/tests/test_0293_invoice_form.py`: reuse the fixture/helpers of an existing invoice-builder test (grep `"/invoices/new"` in `tests/test_invoice_*.py` and import the same fixture). Assert on the `/invoices/new` HTML: `page.index('id="buyer_ico"') < page.index('id="buyer_name"')`, `'name="fill_buyer_from_register"' in page`, and `page.index('id="buyer_zip"') < page.index('id="buyer_city"')`.

## 5. Do not touch

`App/app/routes/invoices.py`, the inline `<script>` in invoice_form.html, the payment section, the action bar.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_0293_invoice_form.py tests/test_invoice_*.py tests/test_design_invoices.py tests/test_static_versions.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Customer starts with the IČO lookup strip; guest-details button sits beside it when offered.
- [ ] Name, street full width; postcode + city on one row; VAT ID + e-mail on one row (desktop); one column at 390 px.
- [ ] Remove buttons quiet; key bumped; tests run, failures listed.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0293-report.md` (600 tokens max), `Status: review`. Commit `0293: invoice form IČO first`.

## Risk list (for the reviewer)

invoice_form.html (field names unchanged), host2.css block.

## Owner steps

None.
