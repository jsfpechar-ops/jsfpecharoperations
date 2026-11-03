# 0849: New invoice: recent stays without an invoice are one tap each

Status: todo
Depends on: 0844 merged (keys). Runs after 0836 (PR #734) if that is still open: both edit `routes/invoices.py` in different functions, so branch from main after 0836 merges, or rebase | Base commit: main | Branch: task/0849-invoice-picker-one-tap
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`/invoices/new` (the stay picker) lists up to 6 recent stays that have started and have no active invoice as buttons; one tap opens the invoice form for that stay. The select stays below for any other stay. Picking a stay goes from 3 taps (open select, choose, Continue) to 1.

## 2. Context

- Brief 0836 (PR #734) prefills the buyer from the lead guest when the form opens; it owns `_form_context`. This brief only touches `_stay_options`, the picker branch of `invoice_new` and the picker template. ARES stays click-only (not touched).
- `App/app/routes/invoices.py` anchors:
  - in `_stay_options`: `        options.append({"id": row["id"], "label": f"{name}, {dates}"})`
  - in `invoice_new`:
```python
            {
                "nav": "invoices",
                "stays": _stay_options(request),
```
  - `def _last_stay_price_hint(request: Request, apartment_id: int) -> str:` (insert the helper above it)
  - `invoices.active_invoice_for_stay(reservation_id)` returns the stay's live invoice or `None` (`App/app/invoices.py`).
- `App/app/templates/invoice_stay_picker.html` (old shell, not v2; CSS is `App/app/static/host2.css`) anchor:
```jinja
  {% if stays %}
  <form method="get" action="/invoices/new">
```
- Keys (0844): `invoice.picker.recent`, `invoice.picker.other`.
- 12 px rule: the buttons are 12 px apart; no fine print (no new help sentence).
- Changed CSS needs a new key: `grep -n 'host2.css?v=' app/templates/base.html` then `.venv/bin/python tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/invoices.py` | edit | `date_from` in options, `_quick_stays`, picker context |
| `App/app/templates/invoice_stay_picker.html` | edit | Quick list |
| `App/app/static/host2.css` | edit | `0849` block at the end of the file |
| `App/app/templates/base.html` | edit | host2.css key only |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_invoice_stay_pages.py` | edit | Three tests at the end |
| `docs/tasks/0849-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `invoices.py`: replace the `options.append(...)` anchor with
```python
        options.append({"id": row["id"], "label": f"{name}, {dates}", "date_from": str(row["date_from"])[:10]})
```
   Directly above `def _last_stay_price_hint` insert:
```python
QUICK_STAYS = 6


def _quick_stays(options):
    """0849: started stays without a live invoice, newest first, as one-tap links."""
    today = claim.prague_today().isoformat()
    quick = []
    for option in options[:40]:
        if option["date_from"] > today or invoices.active_invoice_for_stay(option["id"]):
            continue
        quick.append(option)
        if len(quick) == QUICK_STAYS:
            break
    return quick


```
   Replace the `"stays": _stay_options(request),` line of the `invoice_new` anchor with
```python
                "stays": (stays := _stay_options(request)),
                "quick_stays": _quick_stays(stays),
```
   Run `grep -n "quick_stays" app/routes/invoices.py` (3 lines). Commit `0849 step 1`.
2. Template: replace the two-line anchor with
```jinja
  {% if stays %}
  {% if quick_stays %}
  <h2 class="invoice-quick-title">{{ t('invoice.picker.recent') }}</h2>
  <ul class="invoice-quick-stays">
    {% for option in quick_stays %}<li><a class="ui-btn ui-btn-secondary" href="/invoices/new?reservation_id={{ option.id }}">{{ option.label }}</a></li>{% endfor %}
  </ul>
  <h2 class="invoice-quick-title">{{ t('invoice.picker.other') }}</h2>
  {% endif %}
  <form method="get" action="/invoices/new">
```
   Commit `0849 step 2`.
3. CSS: append to the end of `host2.css`:
```css
/* 0849 invoice quick stays (start) */
.invoice-quick-title{font-size:16px;font-weight:600;margin:0 0 12px}
.invoice-quick-stays{list-style:none;margin:0 0 24px;padding:0;display:flex;flex-direction:column;gap:12px}
.invoice-quick-stays .ui-btn{width:100%;min-height:44px;justify-content:flex-start;text-align:left;white-space:normal}
/* 0849 invoice quick stays (end) */
```
   Bump the `host2.css?v=` key to `20261103-0849`; run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0849 step 3`.
4. Tests at the end of `App/tests/test_invoice_stay_pages.py` (its `host`, `_add_entity`, `_owner`, `make_stay`, `stay_form`):
   - `test_picker_lists_an_uninvoiced_stay_as_one_tap`: `_add_entity()`, `sid = make_stay(_owner())`; `host.get("/invoices/new?lang=en")` has `href="/invoices/new?reservation_id={sid}"` and `Recent stays without an invoice`.
   - `test_invoiced_stay_leaves_the_quick_list`: issue for `sid` exactly as `test_issue_for_a_stay_prints_the_stay` does; the picker no longer has that href (the select may still list it).
   - `test_future_stay_is_not_in_the_quick_list`: `past = make_stay(_owner())`, then insert a second reservation in the same apartment (`db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (past,))`) with `source="manual"`, `status="active"`, `date_from` = `claim.prague_today()` + 5 days, `date_to` = + 8 days, `uid=UID_PREFIX + "future-" + secrets.token_hex(4)` (`from tests.invoice_stay_helper import UID_PREFIX`, so `drop_stays` removes it), `created_at`/`updated_at` = `db.utcnow()`; its href is absent and `past`'s href is present.
   Run §6 command 1. Commit `0849 step 4`.
5. Run §6 commands 2-3. Screenshot: a scratchpad Playwright snippet is not needed; 0890 takes the 390 px picker screenshot. Commit.

## 5. Do not touch

`_form_context`, `invoice_form.html` (0836, 0888), ARES code, `invoice_issue`, numbering, PDF, the invoices list `invoices.html` (#707).

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_stay_pages.py -q --tb=short -x 2>&1 | tail -30`
2. Row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
3. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)

## 7. Acceptance

- [ ] Picker shows up to 6 started, uninvoiced stays as links; the select still works without JS.
- [ ] Commands 1-3 pass, 0 skipped.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0849-report.md` (400 tokens at most), `Status: review`: files, command tails, §7 ticked.

## Risk list (for the reviewer)

`App/app/routes/invoices.py` (owner scope stays in `_stay_options`; at most 40 extra queries).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
