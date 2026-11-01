# 0630: Stay fee list: two steps, PDF + data box + QR in one box
Status: todo
Depends on: none | Base commit: main | Branch: claude/project-thread-edfdua
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens

## 1. Objective
On `/stay-fees` each property card has 3 steps today: 1 check, 2 download PDF, "Next", 3 pay and send. The QR code only shows in step 3, so hosts miss it. Josef approved (2026-11-01) a 2-step card: **1 Check** (unchanged) and **2 Send and pay**: one box with Download PDF, Open datová schránka (the one coral button) and the QR panel beside them. Mockup: `/mnt/project-files/ux-redesign/stay-fee/stay-fee-flow.html` (no "Odesláno/Zaplaceno" marks: Josef dropped them). No data, calculation, PDF or route-URL changes. No JS.

## 2. Context
- Template: `App/app/templates/stay_fees.html` lines 24-88 (stepper + `.fee-step` branches).
- Route: `App/app/routes/stay_fees.py` lines 161-181 (`step_apartment`, `step_three`, `list_query`, `fee_step_url`, `row["step"]`).
- CSS: `App/app/static/host2.css` lines 840-860 (`.fee-pay`, `.fee-stepper*`, `.fee-step-actions`, `.fee-qr-amount`, `.fee-send-line`).
- Strings: `App/app/host_i18n.py` (en block near 6936, cs block near 6965) and `App/app/host_vi_i18n.py` (near 3431). Tests require en and cs to have the same keys, vi a subset of en with the same placeholders.
- Redesign rules (UX thread): existing tokens only (`--accent`, `--accent-soft`, `--surface`, `--line`, `--space-*`, `--radius-3`), one primary button per card, generous whitespace.

## 3. Files
`App/app/templates/stay_fees.html`, `App/app/routes/stay_fees.py`, `App/app/static/host2.css`, `App/app/templates/base.html` (host2.css `?v=` key only), `App/tests/static_versions.json`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/tests/test_stay_fee_pay_steps.py`, `docs/tasks/0630-report.md`. Nothing else.

## 4. Steps
1. **Route.** In `stay_fees.py` delete the `step_apartment` try/except, `step_three`, `list_query`, the `fee_step_url` function and the `"fee_step_url": fee_step_url,` render entry. The step line becomes `row["step"] = 2 if row.get("frozen") else 1`. Update the 0292 comment to: `# 0630: step 1 until the period is confirmed, then 2 (send and pay).` If `urlencode` is no longer used anywhere in the file, remove its import. Commit `0630 step 1`.
2. **Template.** In `stay_fees.html`: change `{% for n in (1, 2, 3) %}` to `{% for n in (1, 2) %}`. Replace everything from `{% elif period.step == 2 %}` down to (not including) the `{% endif %}` that closes the step branches (the one just before `</div>` / `</section>`) with:
```jinja
  {% else %}
    <h3>{{ t('stay_fees.pay.step2') }}</h3>
    <div class="fee-send-pay">
      <ol class="fee-tasks">
        <li>
          <strong>{{ t('stay_fees.pay.task_pdf') }}</strong>
          <a class="ui-btn ui-btn-secondary" href="{{ pdf_url }}" download>{{ t('stay_fees.download_pdf') }}</a>
        </li>
        <li>
          <strong>{{ t('stay_fees.pay.task_send') }}</strong>
          <p class="ui-sub">{% if apartment.stay_fee_authority_databox %}{{ t('stay_fees.pay.send_to', databox=apartment.stay_fee_authority_databox) }}{% else %}{{ t('stay_fees.pay.send') }}{% endif %}</p>
          <a class="ui-btn ui-btn-primary" href="https://www.mojedatovaschranka.cz/" target="_blank" rel="noopener noreferrer">{{ t('stay_fees.pay.open_databox') }}</a>
        </li>
        {% if period.pay_total_czk != 0 %}
        <li>
          <strong>{{ t('stay_fees.pay.task_pay') }}</strong>
          {% if period.pay and period.pay.qr %}<p class="ui-sub">{{ t('stay_fees.payment.qr_help', amount=period.pay_total_display) }}</p>{% endif %}
        </li>
        {% endif %}
      </ol>
      <div class="fee-qr-panel">
      {% if period.pay_total_czk == 0 %}
        <p>{{ t('stay_fees.pay.nothing') }}</p>
      {% elif period.pay and period.pay.qr %}
        <img src="{{ period.pay.qr }}" width="176" height="176" alt="{{ t('stay_fees.payment.qr_alt') }}">
        <p class="fee-qr-amount">{{ period.pay_total_display }}</p>
        <dl class="fee-qr-meta">
          <div><dt>{{ t('stay_fees.payment.account') }}</dt><dd>{{ period.pay.account or period.pay.iban_display }}</dd></div>
          <div><dt>{{ t('stay_fees.payment.vs') }}</dt><dd>{{ period.pay.vs }}</dd></div>
        </dl>
      {% else %}
        <p class="ui-sub">{{ t('stay_fees.pay.no_account') }} <a href="{{ fee_settings_url(apartment.id, fee_return) }}">{{ t('stay_fees.pay.add_account') }}</a></p>
      {% endif %}
      </div>
    </div>
```
   Check `grep -n "fee_step_url\|pay.next\|pay.back\|pay.step3\|short3\|download_why\|fee-send-line" App/app/templates/stay_fees.html` prints nothing. Commit `0630 step 2`.
3. **CSS.** In `host2.css` delete the `.fee-send-line` rule and add after `.fee-qr-amount`:
```css
.host-workspace .fee-send-pay { display: grid; grid-template-columns: minmax(0, 1fr) 16rem; gap: var(--space-6); align-items: start; }
.host-workspace .fee-tasks { margin: 0; padding: 0; list-style: none; counter-reset: fee-task; display: grid; gap: var(--space-5); }
.host-workspace .fee-tasks li { counter-increment: fee-task; position: relative; padding-left: 2.5rem; min-width: 0; }
.host-workspace .fee-tasks li::before { content: counter(fee-task); position: absolute; left: 0; top: 0; width: 1.75rem; height: 1.75rem; border-radius: 50%; background: var(--accent-soft); color: var(--accent-ink); font-weight: 700; display: flex; align-items: center; justify-content: center; }
.host-workspace .fee-tasks strong { display: block; }
.host-workspace .fee-tasks p { margin: var(--space-1) 0 var(--space-2); overflow-wrap: anywhere; }
.host-workspace .fee-tasks .ui-btn { margin-top: var(--space-2); }
.host-workspace .fee-qr-panel { background: var(--accent-soft); border-radius: var(--radius-3); padding: var(--space-4); text-align: center; min-width: 0; }
.host-workspace .fee-qr-panel img { background: #fff; border-radius: var(--radius-2); padding: var(--space-2); max-width: 100%; height: auto; }
.host-workspace .fee-qr-panel p { margin: var(--space-2) 0 0; }
.host-workspace .fee-qr-meta { margin: var(--space-3) 0 0; display: grid; gap: var(--space-1); text-align: left; font-size: var(--size-13); }
.host-workspace .fee-qr-meta div { display: flex; justify-content: space-between; gap: var(--space-3); }
.host-workspace .fee-qr-meta dt { color: var(--ink-3); }
.host-workspace .fee-qr-meta dd { margin: 0; overflow-wrap: anywhere; }
```
   Inside the existing `@media (max-width: 639px)` block add:
```css
  .host-workspace .fee-send-pay { grid-template-columns: minmax(0, 1fr); }
  .host-workspace .fee-qr-panel { order: -1; }
  .host-workspace .fee-tasks .ui-btn { display: flex; justify-content: center; }
```
   In `base.html` change `host2.css?v=20261101-0495b` to `host2.css?v=20261101-0630`. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0630 step 3`.
4. **Strings.** In all three blocks (en, cs, vi): delete `stay_fees.pay.step3`, `stay_fees.pay.short3`, `stay_fees.pay.download_why`, `stay_fees.pay.next`, `stay_fees.pay.back`. Change and add:

| key | en | cs | vi |
|---|---|---|---|
| `stay_fees.pay.step` | Step %(n)s of 2 | Krok %(n)s ze 2 | Bước %(n)s trên 2 |
| `stay_fees.pay.step2` | Send the PDF and pay | Pošlete PDF úřadu a zaplaťte | Gửi PDF và thanh toán |
| `stay_fees.pay.short2` | Send and pay | Odeslat a zaplatit | Gửi và trả |
| `stay_fees.pay.task_pdf` | Download the PDF | Stáhněte PDF | Tải PDF |
| `stay_fees.pay.task_send` | Send it from your data box | Pošlete ho z datové schránky | Gửi từ hộp dữ liệu của bạn |
| `stay_fees.pay.task_pay` | Pay with the QR code | Zaplaťte QR kódem | Thanh toán bằng mã QR |

   Then `grep -rn "pay.next\|pay.back\|pay.step3\|pay.short3\|pay.download_why" App/app App/tests` must print nothing. Commit `0630 step 4`.
5. **Test.** In `test_stay_fee_pay_steps.py`, `test_confirm_from_the_list_comes_back_with_pdf_and_qr`: delete the `fee_step=3` request and its assert; after `assert 'data-fee-step="2"' in page` add `assert "https://www.mojedatovaschranka.cz/" in page and 'class="fee-qr-panel"' in page`. Update the module docstring to `"""0203/0630: the fee list shows check, then one send-and-pay box (PDF, data box, QR) after the confirm."""`. Commit `0630 step 5`.

## 5. Do not touch
`App/app/static/app.js` and any JS (UX thread owns it), `stay_fee_detail.html`, `stay_fee.py`, PDF code, other CSS files, `.fee-step-locked` rules.

## 6. Commands (from `App/`)
- `.venv/bin/python -m pytest tests/test_stay_fee_pay_steps.py tests/test_stay_fee_detail.py tests/test_host_i18n.py tests/test_static_versions.py tests/test_fee_setup_compatibility.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_stay_fee_pay_steps_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30` (0 skipped)
- Screenshot: `UBYHOST_CAPTURE_0203=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_stay_fee_pay_steps_browser.py -q 2>&1 | tail -5`; keep `stay-fees-after-en-390.png` and `stay-fees-after-cs-1280.png`, copy them to `/mnt/project-files/ux-redesign/stay-fee/0630/`.
- Repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`.

## 7. Acceptance
- [ ] `git diff --stat origin/main` lists only section 3 files and this brief.
- [ ] Both pytest commands pass, browser 0 skipped.
- [ ] After confirm, the card shows step 2 with PDF button, data box button (only primary) and QR panel together; at 390 px the QR panel is above the tasks and nothing scrolls sideways.

## 8. Stop and ask
Stop if an anchor in section 2 is missing, if `fee_step_url` is used outside `stay_fees.html`/`stay_fees.py`, or if a test outside section 6 references a deleted key.

## 9. Report
`docs/tasks/0630-report.md`: command tails, diff stat, the two screenshot paths.
