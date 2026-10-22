# 0241: Send by data box, buttons on the Stay fee pages and in the monthly email

Status: review
Depends on: 0240 | Base commit: branch head | Branch: claude/project-thread-jf2b3v
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Show a "Send by data box" button on the Stay fee list (step 2, next to Download PDF) and on the report page (top of the send panel), and point the monthly email at it. Everything stays hidden while `isds_gateway.configured()` is false, so production looks exactly as today until the owner sets the gateway up.

## 2. Context

Decisions (owner thread, 2026-10-22):
- **The email never opens the data box directly.** The draft has to be created by our server at the moment the host is ready (it lives at most 2 hours, and mail scanners follow links), so the email's button opens the report page at `#fee-send`, where the host presses "Send by data box" (a POST, brief 0240).
- Every step button is `ui-btn ui-btn-secondary` (MASTER one-primary rule; `test_design_fees` asserts no plain primary on the list).
- Before the period is frozen, step 2 is the locked placeholder: no send button there.
- Copy: no extra sentences beyond those given here.

POST route from 0240: `POST /stay-fees/{apartment_id}/filings/{filing_id}/databox` (form: `_csrf` only). Report-page context has `send_panel.databox_send` (bool) from 0240.

`App/app/templates/stay_fees.html` step 2 (lines ~50-62):

```html
      {% if period.frozen %}
        {% if apartment.stay_fee_authority_databox %}
          <p class="ui-sub">{{ t('stay_fees.pay.send_to', databox=apartment.stay_fee_authority_databox) }}</p>
        {% else %}
          <p class="ui-sub">{{ t('stay_fees.pay.send') }}</p>
        {% endif %}
        <a class="{{ pay_btn }}" href="/stay-fees/{{ apartment.id }}/pdf?month={{ month_q }}" download>{{ t('stay_fees.download_pdf') }}</a>
```

List rows are built in `stay_fees.py` in the `rows.append({ **period, ... "pay_total_display": ... })` block of the overview route.

`App/app/templates/stay_fee_detail.html` send panel starts:

```html
{% if frozen and send_panel %}
<section class="ui-section" id="fee-send">
  <h2>{{ t('stay_fees.send.title') }}</h2>
  <p class="ui-sub">{{ t('stay_fees.send.lede') }}</p>
  <div class="ui-field">
    <label>{{ t('stay_fees.send.recipient') }}</label>
```

`App/app/mail_notify.py` `build_stay_fee_report(...)` picks `step_send` from `mail.stay_fee.step_send` / `step_send_plain`; `queue_stay_fee_report` builds `report_url = _public(f"/stay-fees/{apartment['id']}?month={stay_fee.month_key(month)}")` and passes `databox=apartment["stay_fee_authority_databox"] or ""`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/stay_fees.py | edit | list rows get `databox_send` and `filing_id` |
| App/app/templates/stay_fees.html | edit | button in step 2 |
| App/app/templates/stay_fee_detail.html | edit | button + lede at the top of `#fee-send`, "Or send it by hand" heading |
| App/app/mail_notify.py | edit | `databox_send` flag → new step line, link to `#fee-send` |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | keys below |
| App/tests/test_databox_send_ui.py | create | tests |

No other file may change. No CSS: use existing classes only (`inline-form`, `ui-btn ui-btn-secondary`, `fee-send-marks-title`). If the layout needs CSS, STOP.

## 4. Steps

1. `stay_fees.py` overview rows: add
```python
            # 0241: Send by data box on step 2; hidden until the gateway is set up.
            "databox_send": bool(period.get("frozen") and apartment["stay_fee_authority_databox"]
                                 and isds_gateway.configured()),
            "filing_id": _list_filing_id(apartment["id"], selected_month) if period.get("frozen") else None,
```
with
```python
def _list_filing_id(apartment_id: int, month: date):
    row = stay_fee_filing.covering(apartment_id, month)
    return row["id"] if row else None
```
(`isds_gateway` is already imported by 0240; if not, import it.) Set `databox_send` False when `filing_id` is None.

2. `stay_fees.html`, inside `{% if period.frozen %}`, replace the lone Download link with:
```html
        <div class="action-group">
          {% if period.databox_send %}
          <form method="post" action="/stay-fees/{{ apartment.id }}/filings/{{ period.filing_id }}/databox" class="inline-form">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <button class="{{ pay_btn }}" type="submit">{{ t('stay_fees.send.databox_button') }}</button>
          </form>
          {% endif %}
          <a class="{{ pay_btn }}" href="/stay-fees/{{ apartment.id }}/pdf?month={{ month_q }}" download>{{ t('stay_fees.download_pdf') }}</a>
        </div>
```
Check `action-group` is used elsewhere in stay_fees.html or detail (it is in the detail page). The `send_to` / `send` line above stays.

3. `stay_fee_detail.html`: replace the lede line with
```html
  {% if send_panel.databox_send %}
  <form method="post" action="/stay-fees/{{ apartment.id }}/filings/{{ send_panel.filing_id }}/databox" class="inline-form">
    <input type="hidden" name="_csrf" value="{{ csrf_token }}">
    <button class="ui-btn ui-btn-secondary" type="submit">{{ t('stay_fees.send.databox_button') }}</button>
  </form>
  <p class="ui-sub">{{ t('stay_fees.send.databox_lede') }}</p>
  <h3 class="fee-send-marks-title">{{ t('stay_fees.send.by_hand') }}</h3>
  {% else %}
  <p class="ui-sub">{{ t('stay_fees.send.lede') }}</p>
  {% endif %}
```

4. `mail_notify.py`: add keyword `databox_send: bool = False` to `build_stay_fee_report`; when `databox and databox_send`, `step_send = _text(lang, "mail.stay_fee.step_send_databox", authority=authority)` and `report_url` gets `#fee-send` appended (both the text and the button). In `queue_stay_fee_report` pass `databox_send=isds_gateway.configured()` (import inside the function like the existing `from . import stay_fee, ...`). Do not change the idempotency key or attachments: the PDF stays attached as the fallback.

5. i18n keys (insert after the existing `stay_fees.pay.send` key in each language; mail key after `mail.stay_fee.step_send_plain`):

EN
```
"stay_fees.send.databox_button": "Send by data box",
"stay_fees.send.databox_lede": "Your data box opens with the PDF attached. Log in there and press Send.",
"stay_fees.send.by_hand": "Or send it by hand",
"mail.stay_fee.step_send_databox": "1. Send the PDF to %(authority)s from your data box: open the report and press \"Send by data box\".",
```
CS
```
"stay_fees.send.databox_button": "Odeslat datovou schránkou",
"stay_fees.send.databox_lede": "Otevře se vaše datová schránka s PDF v příloze. Přihlaste se a stiskněte Odeslat.",
"stay_fees.send.by_hand": "Nebo ho pošlete ručně",
"mail.stay_fee.step_send_databox": "1. Pošlete PDF úřadu %(authority)s ze své datové schránky: otevřete hlášení a stiskněte „Odeslat datovou schránkou“.",
```
VI
```
"stay_fees.send.databox_button": "Gửi qua hộp dữ liệu",
"stay_fees.send.databox_lede": "Hộp dữ liệu của bạn sẽ mở với tệp PDF đính kèm. Hãy đăng nhập ở đó và bấm Gửi.",
"stay_fees.send.by_hand": "Hoặc tự gửi",
"mail.stay_fee.step_send_databox": "1. Gửi PDF cho %(authority)s từ hộp dữ liệu của bạn: mở báo cáo và bấm “Gửi qua hộp dữ liệu”.",
```
If VI has no `mail.stay_fee.*` keys at all, skip the VI mail key (it falls back to English) and say so.

6. Tests `App/tests/test_databox_send_ui.py` (reuse fixtures from `tests/test_stay_fee_send_panel.py`):
   - gateway off (default): list and report page contain no `/databox"` form; email text has no "Send by data box".
   - `monkeypatch.setattr(isds_gateway, "configured", lambda: True)`, frozen period with a council data box: list page step 2 and the report page each have exactly one form posting to `/filings/<id>/databox`, the button class is `ui-btn ui-btn-secondary`, the report page shows "Or send it by hand".
   - same but no council data box: no form.
   - not frozen: no form.
   - `build_stay_fee_report(..., databox="abc1234", databox_send=True)` → text contains `#fee-send` and the new step line; with `databox_send=False` it is unchanged from today.

## 5. Do not touch

CSS/JS, `base.html`, `routes/databox_return.py`, `isds_gateway.py`, migrations. Hard rules 6, 7, 9.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_databox_send_ui.py tests/test_databox_send.py tests/test_stay_fee_pay_steps.py tests/test_stay_fee_send_panel.py tests/test_stay_fee_auto*.py tests/test_design_fees*.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Browser tests are run by the orchestrator. Root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] Gateway off: pages and email are byte-for-byte as before (tests prove no form, no new line).
- [ ] Gateway on: one secondary button in list step 2 and on the report page; email points to `#fee-send`.
- [ ] Tests and lint pass. Screenshots: orchestrator.

## 8. Stop and ask

As TEMPLATE.md §8.

## 9. Report

`docs/tasks/0241-report.md`, `Status: review`. Do not commit.
