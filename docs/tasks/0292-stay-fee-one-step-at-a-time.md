# 0292: Stay fee list: one step at a time (check → download → pay and send)

Status: todo
Depends on: 0291 | Base commit: the 0291 commit | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The fee list shows all three pay steps side by side; the owner (2026-10-24) finds it too much. Each property card now shows **one step at a time** with a small 1-2-3 stepper: (1) "Are these numbers right?" with **Yes, they're right** or **Edit**; (2) download the PDF, then **Next**; (3) the payment QR and "send the PDF from your datová schránka" with a button that opens the official data-box login. Every step has exactly one primary button.

## 2. Context

- Template: `App/app/templates/stay_fees.html` lines 12-87: `{% if periods %}` … the `{% for period in pay_rows %}` loop that renders `<section class="ui-section fee-pay" …>` … `{% endfor %}`. Only that loop (from `{% set pay_btn = 'ui-btn ui-btn-secondary' %}` through the loop's `{% endfor %}`) is replaced.
- Route: `App/app/routes/stay_fees.py` `stay_fees_list` (line ~109) renders `stay_fees.html`. `_list_return(request)` gives `/stay-fees?<current query without lang>`.
- Finalize (`POST /stay-fees/{id}/finalize`) already returns to `return_to` (the list), so after **Yes** the card comes back on step 2.
- Data-box login link (owner): `https://www.mojedatovaschranka.cz/` (a plain link, no server request; `rel="noopener noreferrer"`, `target="_blank"`).
- Strings: EN + CS in `App/app/host_i18n.py` dict `_FEE_0203_STRINGS` (line ~5975, keys `stay_fees.pay.*`); VI in `App/app/host_vi_i18n.py` line ~3125. New keys go next to the existing `stay_fees.pay.*` keys in all three.
- Old keys `stay_fees.pay.lede`, `stay_fees.pay.locked`, `stay_fees.pay.confirmed_help`, `stay_fees.pay.confirm_why` stop being used; leave them (an i18n test may list unused keys: if it fails, delete those four keys in all three languages).
- host2.css lint: tokens only, no raw colours, no bare px except 0 and 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/stay_fees.py | edit | step 1 |
| App/app/templates/stay_fees.html | edit | step 2 |
| App/app/host_i18n.py | edit | step 3 (en, cs) |
| App/app/host_vi_i18n.py | edit | step 3 (vi) |
| App/app/static/host2.css | append | step 4 |
| App/app/templates/base.html | edit | host2 key `?v=20261024-0292` |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_stay_fee_pay_steps.py | edit | step 5 |
| App/tests/test_stay_fee_pay_steps_browser.py | edit | step 5 |
| App/app/static/host2.css (property-summary / entities name width) | edit | step 6 |

No other file may change.

## 4. Steps

1. In `stay_fees_list`, before `return render(...)`, add:

```python
    # 0292: which step each property card shows. Step 1 until the period is
    # confirmed; then 2 (download), and 3 (pay and send) when the host pressed Next.
    try:
        step_apartment = int(request.query_params.get("fee_apt", ""))
    except ValueError:
        step_apartment = None
    step_three = request.query_params.get("fee_step") == "3"
    list_query = [(k, v) for k, v in request.query_params.multi_items() if k not in ("lang", "fee_step", "fee_apt")]

    def fee_step_url(apartment_id: int, step: int) -> str:
        query = urlencode(list_query + ([("fee_step", "3"), ("fee_apt", str(apartment_id))] if step == 3 else []))
        return f"/stay-fees?{query}#fee-pay-{apartment_id}" if query else f"/stay-fees#fee-pay-{apartment_id}"

    for row in rows:
        if not row.get("unset"):
            row["step"] = 1 if not row.get("frozen") else (3 if step_three and step_apartment == row["apartment"]["id"] else 2)
```

   and add `"fee_step_url": fee_step_url,` to the render context dict. `urlencode` is already imported in this module (used by `_list_return`); check, and import from `urllib.parse` if not.

2. In `stay_fees.html`, replace the `pay_btn` line and the whole `{% for period in pay_rows %}…{% endfor %}` loop with:

```jinja
{% for period in pay_rows %}
{% set apartment = period.apartment %}
{% set month_q = selected_month.strftime('%Y-%m') %}
{% set report_url = '/stay-fees/' ~ apartment.id ~ '?month=' ~ month_q %}
{% set pdf_url = '/stay-fees/' ~ apartment.id ~ '/pdf?month=' ~ month_q %}
<section class="ui-section fee-pay" id="fee-pay-{{ apartment.id }}" aria-labelledby="fee-pay-h-{{ apartment.id }}" data-fee-step="{{ period.step }}">
  <div class="ui-section-h">
    <h2 id="fee-pay-h-{{ apartment.id }}">{{ apartment.internal_name }}</h2>
    <span class="ui-sub">{{ period.period_label }}</span>
  </div>
  <ol class="fee-stepper" aria-label="{{ t('stay_fees.pay.step', n=period.step) }}">
    {% for n in (1, 2, 3) %}
    <li class="fee-stepper-item" data-state="{{ 'done' if n < period.step else ('current' if n == period.step else 'todo') }}"{% if n == period.step %} aria-current="step"{% endif %}>
      <span class="fee-stepper-dot" aria-hidden="true">{% if n < period.step %}✓{% else %}{{ n }}{% endif %}</span>
      <span class="fee-stepper-label">{{ t('stay_fees.pay.short' ~ n) }}</span>
    </li>
    {% endfor %}
  </ol>
  <div class="fee-step">
  {% if period.step == 1 %}
    {% if period.status == 'ready' %}
      <h3>{{ t('stay_fees.pay.ask') }}</h3>
      <dl class="fee-figures">
        <div><dt>{{ t('stay_fees.col.liable') }}</dt><dd>{{ period.liable_nights }}</dd></div>
        <div><dt>{{ t('stay_fees.col.exempt') }}</dt><dd>{{ period.exempt_nights }}</dd></div>
        <div class="fee-figures-total"><dt>{{ t('stay_fees.col.total') }}</dt><dd>{{ period.pay_total_display }}</dd></div>
      </dl>
      <form method="post" action="/stay-fees/{{ apartment.id }}/finalize" class="fee-step-actions">
        <input type="hidden" name="_csrf" value="{{ csrf_token }}">
        <input type="hidden" name="month" value="{{ month_q }}">
        <input type="hidden" name="confirm_collected" value="1">
        <input type="hidden" name="return_to" value="{{ fee_return }}">
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('stay_fees.pay.yes') }}</button>
        <a class="ui-btn ui-btn-secondary" href="{{ report_url }}">{{ t('stay_fees.pay.edit') }}</a>
      </form>
    {% elif period.status == 'waiting' %}
      <h3>{{ t('stay_fees.pay.ask') }}</h3>
      <p class="ui-sub">{{ t('stay_fees.issue.period_running') }}</p>
    {% else %}
      <h3>{{ t('stay_fees.pay.fix_first') }}</h3>
      <ul class="fee-step-issues">
        {% for issue in period.issues %}<li>{{ t(issue) }}</li>{% endfor %}
      </ul>
      <div class="fee-step-actions"><a class="ui-btn ui-btn-primary" href="{{ report_url }}">{{ t('stay_fees.pay.fix') }}</a></div>
    {% endif %}
  {% elif period.step == 2 %}
    <h3>{{ t('stay_fees.pay.step2') }}</h3>
    <p class="ui-sub">{{ t('stay_fees.pay.download_why') }}</p>
    <div class="fee-step-actions">
      <a class="ui-btn ui-btn-primary" href="{{ pdf_url }}" download>{{ t('stay_fees.download_pdf') }}</a>
      <a class="ui-btn ui-btn-secondary" href="{{ fee_step_url(apartment.id, 3) }}">{{ t('stay_fees.pay.next') }}</a>
    </div>
  {% else %}
    <h3>{{ t('stay_fees.pay.step3') }}</h3>
    {% if period.pay_total_czk == 0 %}
      <p>{{ t('stay_fees.pay.nothing') }}</p>
    {% elif period.pay and period.pay.qr %}
      <div class="fee-qr">
        <img src="{{ period.pay.qr }}" width="176" height="176" alt="{{ t('stay_fees.payment.qr_alt') }}">
        <div>
          <p class="fee-qr-amount">{{ period.pay_total_display }}</p>
          <p class="ui-sub">{{ t('stay_fees.payment.account') }}: {{ period.pay.account or period.pay.iban_display }}</p>
          <p class="ui-sub">{{ t('stay_fees.payment.vs') }}: {{ period.pay.vs }}</p>
        </div>
      </div>
    {% else %}
      <p class="ui-sub">{{ t('stay_fees.pay.no_account') }} <a href="{{ fee_settings_url(apartment.id, fee_return) }}">{{ t('stay_fees.pay.add_account') }}</a></p>
    {% endif %}
    <p class="fee-send-line">{% if apartment.stay_fee_authority_databox %}{{ t('stay_fees.pay.send_to', databox=apartment.stay_fee_authority_databox) }}{% else %}{{ t('stay_fees.pay.send') }}{% endif %}</p>
    <div class="fee-step-actions">
      <a class="ui-btn ui-btn-primary" href="https://www.mojedatovaschranka.cz/" target="_blank" rel="noopener noreferrer">{{ t('stay_fees.pay.open_databox') }}</a>
      <a class="ui-btn ui-btn-quiet" href="{{ fee_step_url(apartment.id, 2) }}">{{ t('stay_fees.pay.back') }}</a>
    </div>
  {% endif %}
  </div>
</section>
{% endfor %}
```

3. New strings (keep `%(databox)s` placeholders as they are in the existing `send_to`):

| key | en | cs | vi |
|---|---|---|---|
| stay_fees.pay.short1 | Check | Kontrola | Kiểm tra |
| stay_fees.pay.short2 | Download | Stažení | Tải về |
| stay_fees.pay.short3 | Pay and send | Platba a odeslání | Trả và gửi |
| stay_fees.pay.ask | Are these numbers right? | Sedí tato čísla? | Các số này đúng chưa? |
| stay_fees.pay.yes | Yes, they're right | Ano, sedí | Đúng rồi |
| stay_fees.pay.edit | Edit | Upravit | Sửa |
| stay_fees.pay.fix_first | Fix this first | Nejdřív opravte tohle | Hãy sửa điều này trước |
| stay_fees.pay.download_why | The council needs this PDF. | Tohle PDF potřebuje úřad. | Chính quyền cần tệp PDF này. |
| stay_fees.pay.next | Next | Další | Tiếp |
| stay_fees.pay.back | Back | Zpět | Quay lại |
| stay_fees.pay.open_databox | Open datová schránka | Otevřít datovou schránku | Mở datová schránka |

   Change these existing values (all three languages):
   - `stay_fees.pay.step2`: en "Download the PDF", cs "Stáhněte PDF", vi "Tải PDF"
   - `stay_fees.pay.step3`: en "Pay, then send the PDF", cs "Zaplaťte a pošlete PDF", vi "Thanh toán, rồi gửi PDF"
   - `stay_fees.pay.step`: en "Step %(n)s of 3" stays as it is.

4. Append to host2.css:

```css
/* 0292: the fee list leads the host one step at a time (owner 2026-10-24). */
.host-workspace .fee-pay .ui-section-h { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: var(--space-1) var(--space-3); }
.host-workspace .fee-stepper { display: flex; gap: var(--space-2); margin: var(--space-3) 0 var(--space-4); padding: 0; list-style: none; }
.host-workspace .fee-stepper-item { flex: 1 1 0; min-width: 0; display: flex; align-items: center; gap: var(--space-2); padding-top: var(--space-2); border-top: 3px solid var(--line); color: var(--ink-3); font-size: var(--size-13); font-weight: 600; }
.host-workspace .fee-stepper-item[data-state="done"] { border-top-color: var(--green-700); color: var(--ink-2); }
.host-workspace .fee-stepper-item[data-state="current"] { border-top-color: var(--accent); color: var(--ink); }
.host-workspace .fee-stepper-dot { flex: 0 0 auto; display: inline-flex; align-items: center; justify-content: center; width: 1.5rem; height: 1.5rem; border: 1px solid var(--line-strong); border-radius: 50%; background: var(--surface); font-size: var(--size-12); }
.host-workspace .fee-stepper-item[data-state="current"] .fee-stepper-dot { border-color: var(--accent); background: var(--accent); color: var(--on-accent); }
.host-workspace .fee-stepper-item[data-state="done"] .fee-stepper-dot { border-color: var(--green-700); color: var(--green-700); }
.host-workspace .fee-stepper-label { min-width: 0; overflow-wrap: anywhere; }
.host-workspace .fee-figures { display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-6); margin: 0 0 var(--space-4); }
.host-workspace .fee-figures div { min-width: 0; }
.host-workspace .fee-figures dt { color: var(--ink-3); font-size: var(--size-13); }
.host-workspace .fee-figures dd { margin: 0; font-size: var(--size-18); font-weight: 600; }
.host-workspace .fee-figures-total dd { font-size: var(--size-22); }
.host-workspace .fee-step-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin: var(--space-3) 0 0; }
.host-workspace .fee-qr-amount { font-size: var(--size-22); font-weight: 600; }
.host-workspace .fee-send-line { margin: var(--space-4) 0 0; }
@media (max-width: 639px) {
  .host-workspace .fee-step-actions { flex-direction: column; align-items: stretch; }
  .host-workspace .fee-stepper-label { font-size: var(--size-12); }
}
```

   If a token used above (`--green-700`, `--ink-2`, `--space-6`, `--size-22`, `--on-accent`) is missing in `App/app/static/tokens.css`, use the nearest existing one and say so in the report.
   Also delete the now-dead 0203 rule `.host-workspace .fee-steps { … }` media block **only if** the lint complains; otherwise leave old rules.

5. Tests:
   - `test_stay_fee_pay_steps.py` test 1: replace the two lines `assert "Step 1 of 3" …` and `assert page.count("fee-step-locked") >= 2` with `assert 'data-fee-step="1"' in page and "Are these numbers right?" in page`.
   - test 2: replace `assert "Confirmed" in page` and `assert "fee-step-locked" not in page` with `assert 'data-fee-step="2"' in page`; then add: `page = client.get(f"/stay-fees?month=2026-08&fee_step=3&fee_apt={apartment_id}&lang=en").text` and `assert 'data-fee-step="3"' in page and "https://www.mojedatovaschranka.cz/" in page`.
   - browser test: in `_CHECK_JS` count primaries per card: `primaries: Math.max(0, ...[...document.querySelectorAll('.fee-pay')].map(s => s.querySelectorAll('.ui-btn-primary').length))`; change the click locator to `.fee-step form button.ui-btn-primary`.

6. Carry-over from 0291 (the Open label is wider than the old 28 px arrow, so `test_0285_rows_browser.py::test_properties_rows_match_stays_rows` fails at 1280 px: the Open wraps under the name). In host2.css change
   `.host-workspace .property-summary-table td:first-child .row-primary-link { display: inline-block; max-width: calc(100% - var(--space-12)); vertical-align: middle; }`
   so that `max-width` is `calc(100% - 7rem)`. If the entities rows (`.lc-entities td.col-name`) fail the same test, give their `.row-primary-link` the same `max-width: calc(100% - 7rem)` in a new rule next to the line `.host-workspace .lc-entities tbody td.col-name .row-primary-link + .row-open`. Add `tests/test_0285_rows_browser.py` to the §6 command.

## 5. Do not touch

`stay_fee.py`, `stay_fee_filing.py`, the finalize route, the table below the cards, `stay_fee_detail.html`. Rule 2: the data-box link is a plain link (no server request).

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_design_fees.py tests/test_static_versions.py tests/test_design_guardrails_browser.py tests/test_host_i18n*.py -q --tb=short 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Unconfirmed card: stepper 1 current, figures, Yes (primary) + Edit.
- [ ] Confirmed card: step 2 with Download (primary) + Next; `fee_step=3&fee_apt=<id>` shows step 3 with QR, send line, Open datová schránka (primary) + Back.
- [ ] One primary per card; EN/CS/VI strings present.
- [ ] Commands run; failures listed.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0292-report.md` (600 tokens max), `Status: review`. Commit `0292: stay fee list one step at a time`.

## Risk list (for the reviewer)

stay_fees.py (query parsing), stay_fees.html loop.

## Owner steps

None.
