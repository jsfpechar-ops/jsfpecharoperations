# 0852: Invoice form: one tap for the last price, payment method remembered

Status: todo
Depends on: 0844 (keys), 0836 (PR #734, buyer prefill) and 0849 merged (all edit `routes/invoices.py`) | Base commit: main after them | Branch: task/0852-invoice-defaults
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On a new stay invoice: (a) a "Use last price: 2 500 Kč" button fills the stay price in one tap instead of typing it; (b) "Paid via" starts at the method of this operator's last paid invoice (Airbnb, Booking, cash, transfer or the custom text) instead of always "bank transfer". Together with 0836 and 0849 the invoice goes from about 9 taps + 1 typed field to 5 taps + 0 typed.

## 2. Context

- Already default today, do not change: DUZP = today (`invoice_form.html`), due date = issue date + the operator's `invoice_due_days` (server, `invoices.py` around line 388), VAT 12 % for payers, "already paid" checked. The price is never filled without the host's tap: an invoice is a tax document, and the issue button keeps its confirm dialog.
- ARES stays click-only. 0836 owns the buyer prefill in `_form_context`; this brief adds lines below the price hint only.
- `App/app/routes/invoices.py` anchors:
```python
    if stay:
        price_hint = _last_stay_price_hint(request, stay["reservation"]["apartment_id"])
```
  and `def _form_state(request, form, entity) -> Dict[str, Any]:` (insert the helper above it).
- `App/app/templates/invoice_form.html` anchors (old shell; its inline `<script>` sets `var form = document.querySelector(".invoice-form");`):
```jinja
            {% if stay_price_hint %}
            <span id="stay-price-hint" class="ui-sub">{{ t('invoice.price_hint', price=stay_price_hint) }}</span>
            {% endif %}
```
```js
  var entitySel = document.getElementById("legal_entity_id");
```
- The select already honours `values.paid_via` and shows the custom input when `values.paid_via_custom` is set.
- Key (0844): `invoice.price_use` (`%(price)s`). Rule 9: when the button shows, the hint sentence hides (the button says it); without JS the hint stays and the button stays hidden.
- 12 px rule: the button sits 12 px under the price input. CSS goes in `App/app/static/host2.css` (new block at the end), then a new `host2.css?v=` key in `App/app/templates/base.html` and `.venv/bin/python tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/invoices.py` | edit | `_remember_paid_via` + call |
| `App/app/templates/invoice_form.html` | edit | Button + 12 JS lines |
| `App/app/static/host2.css` | edit | `0852` block at the end |
| `App/app/templates/base.html` | edit | host2.css key only |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_invoice_autofill.py` | edit | Four tests at the end |
| `docs/tasks/0852-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `invoices.py`: directly above `def _form_state` insert:
```python
PAID_VIA_CHOICES = ("direct_transfer", "cash", "airbnb", "booking")


def _remember_paid_via(request: Request, entity_id: int, values: Dict[str, Any]) -> None:
    """0852: a new invoice starts with the payment method of this operator's last paid invoice."""
    row = db.query_one(
        "SELECT paid_via FROM invoice "
        f"WHERE legal_entity_id = ? AND {db.null_safe_eq('owner_user_id')} "
        "AND kind = 'invoice' AND paid_via IS NOT NULL AND paid_via != '' "
        "ORDER BY issue_date DESC, id DESC LIMIT 1",
        (entity_id, access.owner_id(request)),
    )
    if not row:
        return
    if row["paid_via"] in PAID_VIA_CHOICES:
        values["paid_via"] = row["paid_via"]
    else:
        values["paid_via_custom"] = row["paid_via"][:60]


```
   Directly below the two-line price-hint anchor add:
```python
    if stay and entity and not any(key in values for key in ("already_paid", "paid_via", "paid_via_custom")):
        _remember_paid_via(request, entity["id"], values)
```
   (a 422 re-render always carries `already_paid`, so the host's own choice is never overwritten). Commit `0852 step 1`.
2. `invoice_form.html`: replace the three-line hint anchor with
```jinja
            {% if stay_price_hint %}
            <span id="stay-price-hint" class="ui-sub">{{ t('invoice.price_hint', price=stay_price_hint) }}</span>
            {% if not values.get('stay_price') %}<button class="ui-btn ui-btn-quiet ui-btn-compact invoice-use-price" type="button" data-use-price="{{ stay_price_hint }}" hidden>{{ t('invoice.price_use', price=stay_price_hint) }}</button>{% endif %}
            {% endif %}
```
   and directly below the `var entitySel = ...` anchor insert:
```js

  /* 0852: one tap copies the last price on this property into the stay line. */
  var usePrice = form.querySelector("[data-use-price]");
  var priceInput = form.querySelector('input[name="stay_price"]');
  if (usePrice && priceInput) {
    var priceHint = document.getElementById("stay-price-hint");
    usePrice.hidden = false;
    if (priceHint) priceHint.hidden = true;
    usePrice.addEventListener("click", function () {
      priceInput.value = usePrice.getAttribute("data-use-price");
      priceInput.dispatchEvent(new Event("input", { bubbles: true }));
      usePrice.hidden = true;
      priceInput.focus();
    });
  }
```
   Commit `0852 step 2`.
3. Append to `host2.css`:
```css
/* 0852 invoice use price (start) */
.invoice-use-price{display:inline-flex;margin-top:12px;min-height:44px}
/* 0852 invoice use price (end) */
```
   Bump `host2.css?v=` to `20261103-0852`; `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0852 step 3`.
4. Tests at the end of `App/tests/test_invoice_autofill.py` (its `host`, `_add_entity`, `_owner`, `make_stay`, `stay_form`). Helper `_second_stay(first_id)`: insert a reservation in the first stay's apartment with `source="manual"`, `status="active"`, `date_from` = today - 12 days, `date_to` = today - 9, `uid=UID_PREFIX + "second-" + secrets.token_hex(4)` (`from tests.invoice_stay_helper import UID_PREFIX`; `import secrets`), `created_at`/`updated_at` = `db.utcnow()`; return its id. Helper `_issue(sid, **extra)`: `host.post("/invoices", data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **stay_form(sid, price="2500"), **extra}, follow_redirects=False)` must be 303 (pattern of `test_issue_for_a_stay_prints_the_stay` in `tests/test_invoice_stay_pages.py`).
   - `test_last_price_button_on_the_same_property`: entity, `s1 = make_stay(_owner(), entity_id=e)`, `_issue(s1)`, `s2 = _second_stay(s1)`; `GET /invoices/new?reservation_id={s2}&entity={e}`: has `data-use-price="2500"` and `Use last price: 2500 Kč`.
   - `test_payment_method_is_remembered`: `_issue(s1, paid_via="cash")`; form for `s2` contains `value="cash" selected`.
   - `test_custom_payment_text_is_remembered`: `_issue(s1, paid_via="custom", paid_via_custom="Revolut")`; form for `s2` contains `value="Revolut"`.
   - `test_first_invoice_keeps_bank_transfer`: no earlier invoice: `value="direct_transfer" selected`, no `data-use-price`.
   Run §6 command 1. Commit `0852 step 4`.
5. Run §6 commands 2-4. Commit.

## 5. Do not touch

0836's buyer lines, ARES (`register_lookup`, `_buyer_ares_fill`), `invoice_issue`, numbering, PDF, VAT logic, DUZP and due-date defaults, `invoice_stay_picker.html`.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_autofill.py -q --tb=short -x 2>&1 | tail -30`
2. Row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
4. `.venv/bin/python -m pytest tests/test_invoice_stay_browser.py tests/test_host_invoice_items_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped; the form's JS still works)

## 7. Acceptance

- [ ] The price is filled only by the tap; without JS the old hint shows and nothing else changes.
- [ ] Paid-via starts at the last used method of this operator; a re-render after an error keeps what the host chose.
- [ ] Commands 1-4 pass, 0 skipped.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found (0836 may have moved lines: anchors are text, not line numbers); a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0852-report.md` (400 tokens at most), `Status: review`: files, command tails, §7 ticked.

## Risk list (for the reviewer)

`App/app/routes/invoices.py` (owner scope in the query; no overwrite on re-render), `App/app/templates/invoice_form.html` (JS runs only when both elements exist).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
