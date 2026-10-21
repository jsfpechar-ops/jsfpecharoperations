# 0203: Stay fees list shows the three pay steps (confirm, PDF, QR)

Status: todo
Depends on: none | Base commit: 2f043c8 | Branch: claude/project-thread-graf3i
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/stay-fees` (already filtered to one month), each set-up property gets a section with three numbered steps: 1 confirm the figures, 2 download the PDF, 3 pay with the QR code. Steps 2 and 3 show a dashed "appears after step 1" placeholder until the period is confirmed, so the host knows why the PDF and QR are not there yet and never has to open the report for the normal flow (owner, 2026-10-21).

## 2. Context

- Owner decisions: no "I've paid" button on the new section (paying is the host's business). The table under the sections stays as the overview. Data box sending is out of scope.
- MASTER rules: at most one `ui-btn-primary` per screen, so the step buttons are primary only when exactly one property section is shown, otherwise secondary. Tokens only in `host2.css` (no raw px except `1px` borders). Every new class goes into `docs/design/catalog.json` for the template. Copy says why. No em dash in copy.
- The PDF and QR exist only after the period is saved (frozen): `stay_fee_pdf_download` needs a filing row, and `payment_details(group)` builds the QR from the IBAN, VS and total (empty QR when the total is 0).
- `stay_fee_finalize` (POST `/stay-fees/{id}/finalize`, form fields `_csrf`, `month`, `confirm_collected`) currently always returns to the detail page. A list form needs to come back to the list, so finalize learns an optional `return_to`, validated by the existing `fee_return_path`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/stay_fees.py | edit | list rows carry pay data; finalize honours `return_to` |
| App/app/templates/stay_fees.html | edit | pay-step sections above the table |
| App/app/static/host2.css | edit | append the step styles |
| App/app/templates/base.html | edit | bump host2.css `?v=` |
| App/tests/static_versions.json | regenerate | `.venv/bin/python tests/test_static_versions.py --write` after the CSS change |
| App/app/host_i18n.py | edit | en and cs keys |
| App/app/host_vi_i18n.py | edit | vi keys |
| docs/design/catalog.json | edit | new classes for stay_fees.html |
| docs/design/pages/stay-fees.md | edit | page add-on lines |
| App/tests/test_design_fees.py | edit | list may now have one primary |
| App/tests/test_stay_fee_pay_steps.py | create | route tests |
| App/tests/test_stay_fee_pay_steps_browser.py | create | browser test + screenshots |

No other file may change.

## 4. Steps

### Step 1: route (App/app/routes/stay_fees.py)

1a. Anchor (inside `stay_fees_list`):
```python
        rows.append({
            **period,
            "total_display": stay_fee.format_czk(period["total_czk"]),
            "issues": issues,
            "unset": False,
        })
```
Replace with:
```python
        rows.append({
            **period,
            "total_display": stay_fee.format_czk(period["total_czk"]),
            "issues": issues,
            "unset": False,
            # 0203: the pay steps on the list need the same payment data as the report.
            "period_label": _ui_period_label(request, group["cadence"], selected_month),
            "pay": stay_fee.payment_details(group) if period.get("frozen") else None,
            "pay_total_czk": group["total_czk"],
            "pay_total_display": stay_fee.format_czk(group["total_czk"]),
        })
```

1b. Anchor (inside `stay_fee_finalize`, must match once):
```python
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    correcting = _form_str(form, "correct") == "1"
```
Replace with:
```python
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    # 0203: the confirm button on the fee list comes back to the list.
    back_path = fee_return_path(_form_str(form, "return_to"), apartment_id) or back_path
    correcting = _form_str(form, "correct") == "1"
```
Command: `cd App && .venv/bin/python -c "import app.routes.stay_fees" 2>&1 | tail -5`. Commit `0203 step 1`.

### Step 2: template (App/app/templates/stay_fees.html)

Anchor:
```
{% block body %}
{% if periods %}
```
Replace with the anchor followed by this block (the rest of the file stays):
```
{% block body %}
{% if periods %}
{% set pay_rows = periods | rejectattr('unset') | list %}
{% set pay_btn = 'ui-btn ui-btn-primary' if pay_rows | length == 1 else 'ui-btn ui-btn-secondary' %}
{% for period in pay_rows %}
{% set apartment = period.apartment %}
{% set month_q = selected_month.strftime('%Y-%m') %}
{% set report_url = '/stay-fees/' ~ apartment.id ~ '?month=' ~ month_q %}
<section class="ui-section fee-pay" aria-labelledby="fee-pay-{{ apartment.id }}">
  <div class="ui-section-h">
    <h2 id="fee-pay-{{ apartment.id }}">{{ apartment.internal_name }}</h2>
    <a href="{{ report_url }}">{{ t('stay_fees.open_report') }}</a>
  </div>
  <p class="ui-sub">{{ t('stay_fees.pay.lede', period=period.period_label) }}</p>
  <ol class="fee-steps">
    <li class="fee-step">
      <p class="ui-sub">{{ t('stay_fees.pay.step', n=1) }}</p>
      <h3>{{ t('stay_fees.pay.step1') }}</h3>
      <p>{{ t('stay_fees.col.liable') }}: {{ period.liable_nights }} · {{ t('stay_fees.col.exempt') }}: {{ period.exempt_nights }} · {{ t('stay_fees.col.total') }}: {{ period.pay_total_display }}</p>
      {% if period.frozen %}
        <p><span class="ui-badge ui-badge-done" data-tone="green">{{ t('stay_fees.pay.confirmed') }}</span></p>
        <p class="ui-sub">{{ t('stay_fees.pay.confirmed_help') }}</p>
      {% elif period.status == 'ready' %}
        <p class="ui-sub">{{ t('stay_fees.pay.confirm_why') }}</p>
        <form method="post" action="/stay-fees/{{ apartment.id }}/finalize" class="inline-form">
          <input type="hidden" name="_csrf" value="{{ csrf_token }}">
          <input type="hidden" name="month" value="{{ month_q }}">
          <input type="hidden" name="confirm_collected" value="1">
          <input type="hidden" name="return_to" value="{{ fee_return }}">
          <button class="{{ pay_btn }}" type="submit">{{ t('stay_fees.pay.confirm') }}</button>
        </form>
      {% elif period.status == 'waiting' %}
        <p class="ui-sub">{{ t('stay_fees.issue.period_running') }}</p>
      {% else %}
        <ul class="fee-step-issues">
          {% for issue in period.issues %}<li>{{ t(issue) }}</li>{% endfor %}
        </ul>
        <a class="{{ pay_btn }}" href="{{ report_url }}">{{ t('stay_fees.pay.fix') }}</a>
      {% endif %}
    </li>
    <li class="fee-step">
      <p class="ui-sub">{{ t('stay_fees.pay.step', n=2) }}</p>
      <h3>{{ t('stay_fees.pay.step2') }}</h3>
      {% if period.frozen %}
        {% if apartment.stay_fee_authority_databox %}
          <p class="ui-sub">{{ t('stay_fees.pay.send_to', databox=apartment.stay_fee_authority_databox) }}</p>
        {% else %}
          <p class="ui-sub">{{ t('stay_fees.pay.send') }}</p>
        {% endif %}
        <a class="{{ pay_btn }}" href="/stay-fees/{{ apartment.id }}/pdf?month={{ month_q }}" download>{{ t('stay_fees.download_pdf') }}</a>
      {% else %}
        <div class="fee-step-locked"><p>{{ t('stay_fees.pay.locked') }}</p></div>
      {% endif %}
    </li>
    <li class="fee-step">
      <p class="ui-sub">{{ t('stay_fees.pay.step', n=3) }}</p>
      <h3>{{ t('stay_fees.pay.step3') }}</h3>
      {% if not period.frozen %}
        <div class="fee-step-locked fee-step-locked-qr"><p>{{ t('stay_fees.pay.locked') }}</p></div>
      {% elif period.pay_total_czk == 0 %}
        <p>{{ t('stay_fees.pay.nothing') }}</p>
      {% elif period.pay and period.pay.qr %}
        <div class="fee-qr">
          <img src="{{ period.pay.qr }}" width="176" height="176" alt="{{ t('stay_fees.payment.qr_alt') }}">
          <div>
            <p class="ui-sub fee-qr-help">{{ t('stay_fees.payment.qr_help', amount=period.pay_total_display) }}</p>
            <p class="ui-sub">{{ t('stay_fees.payment.account') }}: {{ period.pay.account or period.pay.iban_display }}</p>
            <p class="ui-sub">{{ t('stay_fees.payment.vs') }}: {{ period.pay.vs }}</p>
          </div>
        </div>
      {% else %}
        <p class="ui-sub">{{ t('stay_fees.pay.no_account') }}</p>
        <a class="ui-btn ui-btn-secondary" href="{{ fee_settings_url(apartment.id, fee_return) }}">{{ t('stay_fees.pay.add_account') }}</a>
      {% endif %}
    </li>
  </ol>
</section>
{% endfor %}
```
Command: `cd App && .venv/bin/python -m pytest tests/test_stay_fee_list.py -q --tb=short -x 2>&1 | tail -30`. Commit `0203 step 2`.

### Step 3: CSS and cache key

Append to the end of `App/app/static/host2.css`:
```css
/* 0203: stay fees list, the three pay steps per property. */
.host-workspace .fee-steps { list-style: none; margin: var(--space-4) 0 0; padding: 0; display: grid; gap: var(--space-5); }
.host-workspace .fee-step { min-width: 0; }
.host-workspace .fee-step h3 { margin: 0 0 var(--space-2); font-size: var(--size-16); font-weight: 600; }
.host-workspace .fee-step > p { margin: 0 0 var(--space-2); }
.host-workspace .fee-step .fee-qr { flex-wrap: wrap; margin-top: 0; }
.host-workspace .fee-step .fee-qr p { margin: 0 0 var(--space-1); }
.host-workspace .fee-step-issues { margin: 0 0 var(--space-3); padding-left: var(--space-5); }
.host-workspace .fee-step-locked { border: 1px dashed var(--line-2); border-radius: var(--radius-2); background: var(--surface-2); color: var(--ink-3); padding: var(--space-4); }
.host-workspace .fee-step-locked p { margin: 0; }
.host-workspace .fee-step-locked-qr { width: 11rem; height: 11rem; display: flex; align-items: center; justify-content: center; text-align: center; padding: var(--space-3); }
@media (min-width: 1024px) {
  .host-workspace .fee-steps { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```
In `App/app/templates/base.html` change `/static/host2.css?v=20261021-0201d` to `/static/host2.css?v=20261021-0203a`. If any other template links host2.css with the old key (`grep -rn "host2.css?v=" App/app/templates`), change it the same way.
Command: `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Commit `0203 step 3`.

### Step 4: copy

4a. `App/app/host_i18n.py`, anchor (once):
```python
for _lang, _strings in _FEE_0082_STRINGS.items():
    STRINGS[_lang].update(_strings)
```
Add right after it:
```python

# 0203: the three pay steps on the fee list.
_FEE_0203_STRINGS = {
    "en": {
        "stay_fees.pay.lede": "%(period)s. Three steps: confirm the figures, send the PDF to the council, then pay with the QR code.",
        "stay_fees.pay.step": "Step %(n)s of 3",
        "stay_fees.pay.step1": "Check and confirm the figures",
        "stay_fees.pay.step2": "Download the PDF for the council",
        "stay_fees.pay.step3": "Pay with the QR code",
        "stay_fees.pay.confirm_why": "Confirming freezes the numbers, so the PDF and the payment match what the council sees.",
        "stay_fees.pay.confirm": "Confirm figures",
        "stay_fees.pay.confirmed": "Confirmed",
        "stay_fees.pay.confirmed_help": "To change something, open the report and correct it there.",
        "stay_fees.pay.fix": "Fix in the report",
        "stay_fees.pay.locked": "Appears after step 1, once the figures are confirmed.",
        "stay_fees.pay.send_to": "Send it from your data box to the council's data box %(databox)s.",
        "stay_fees.pay.send": "Send it to the council, for example from your data box.",
        "stay_fees.pay.nothing": "Nothing to pay for this period. The council still needs the PDF.",
        "stay_fees.pay.no_account": "Add the council's bank account and the QR code appears here.",
        "stay_fees.pay.add_account": "Add bank account",
    },
    "cs": {
        "stay_fees.pay.lede": "%(period)s. Tři kroky: potvrďte čísla, pošlete PDF úřadu a zaplaťte QR kódem.",
        "stay_fees.pay.step": "Krok %(n)s ze 3",
        "stay_fees.pay.step1": "Zkontrolujte a potvrďte čísla",
        "stay_fees.pay.step2": "Stáhněte PDF pro úřad",
        "stay_fees.pay.step3": "Zaplaťte QR kódem",
        "stay_fees.pay.confirm_why": "Potvrzením se čísla uzamknou, takže PDF i platba odpovídají tomu, co uvidí úřad.",
        "stay_fees.pay.confirm": "Potvrdit čísla",
        "stay_fees.pay.confirmed": "Potvrzeno",
        "stay_fees.pay.confirmed_help": "Chcete-li něco změnit, otevřete hlášení a opravte ho tam.",
        "stay_fees.pay.fix": "Opravit v hlášení",
        "stay_fees.pay.locked": "Zobrazí se po kroku 1, až potvrdíte čísla.",
        "stay_fees.pay.send_to": "Pošlete ho ze své datové schránky do datové schránky úřadu %(databox)s.",
        "stay_fees.pay.send": "Pošlete ho úřadu, například ze své datové schránky.",
        "stay_fees.pay.nothing": "Za toto období se nic neplatí. Úřad ale PDF potřebuje.",
        "stay_fees.pay.no_account": "Doplňte bankovní účet úřadu a QR kód se zobrazí zde.",
        "stay_fees.pay.add_account": "Doplnit účet",
    },
}
for _lang, _strings in _FEE_0203_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

4b. `App/app/host_vi_i18n.py`, anchor (the end of `STRINGS`):
```python
    "calendar.cleaning_timing_unavailable": "Đặt giờ hợp lệ cho chỗ ở để hiển thị khung giờ dọn dẹp.",
}
```
Replace with:
```python
    "calendar.cleaning_timing_unavailable": "Đặt giờ hợp lệ cho chỗ ở để hiển thị khung giờ dọn dẹp.",
    "stay_fees.pay.lede": "%(period)s. Ba bước: xác nhận số liệu, gửi PDF cho chính quyền địa phương, rồi thanh toán bằng mã QR.",
    "stay_fees.pay.step": "Bước %(n)s trên 3",
    "stay_fees.pay.step1": "Kiểm tra và xác nhận số liệu",
    "stay_fees.pay.step2": "Tải PDF cho chính quyền",
    "stay_fees.pay.step3": "Thanh toán bằng mã QR",
    "stay_fees.pay.confirm_why": "Xác nhận sẽ khóa số liệu, để PDF và khoản thanh toán khớp với những gì chính quyền nhận được.",
    "stay_fees.pay.confirm": "Xác nhận số liệu",
    "stay_fees.pay.confirmed": "Đã xác nhận",
    "stay_fees.pay.confirmed_help": "Muốn thay đổi, hãy mở báo cáo và sửa ở đó.",
    "stay_fees.pay.fix": "Sửa trong báo cáo",
    "stay_fees.pay.locked": "Hiện ra sau bước 1, khi số liệu đã được xác nhận.",
    "stay_fees.pay.send_to": "Gửi PDF từ hộp dữ liệu của bạn đến hộp dữ liệu của chính quyền %(databox)s.",
    "stay_fees.pay.send": "Gửi PDF cho chính quyền, ví dụ từ hộp dữ liệu của bạn.",
    "stay_fees.pay.nothing": "Kỳ này không phải trả gì. Chính quyền vẫn cần PDF.",
    "stay_fees.pay.no_account": "Thêm tài khoản ngân hàng của chính quyền, mã QR sẽ hiện ở đây.",
    "stay_fees.pay.add_account": "Thêm tài khoản",
}
```
If the anchor is not the end of `STRINGS` (check: the next non-blank line after it must not be indented as a dict entry), STOP.
Command: `cd App && .venv/bin/python -m pytest tests/ -q --tb=short -x -k "i18n or parity or em_dash" 2>&1 | tail -30`. Commit `0203 step 4`.

### Step 5: catalog and page file

5a. In `docs/design/catalog.json`, in the list under `"legacy"` → `"App/app/templates/stay_fees.html"`, add these strings, keeping the list sorted: `fee-pay`, `fee-qr`, `fee-qr-help`, `fee-step`, `fee-step-issues`, `fee-step-locked`, `fee-step-locked-qr`, `fee-steps`, `inline-form`.

5b. In `docs/design/pages/stay-fees.md`, under `## Stays fees list` after the `- row menu:` line, add:
```
- pay steps (0203): above the table, one `ui-section` per set-up property with an `ol` of three steps (confirm figures, Download PDF, QR Platba). Before the period is saved, steps 2 and 3 show a dashed `fee-step-locked` placeholder ("appears after step 1"). Step buttons are primary only when one property is shown, else secondary. No paid button.
```
(The heading in the file is `## Stay fees list`; add the line there.) The file must stay under 40 lines.
Command: `python3 scripts/design_lint.py 2>&1 | tail -10` from the repo root. Commit `0203 step 5`.

### Step 6: tests

6a. `App/tests/test_design_fees.py`, anchor:
```python
    assert 'class="ui-btn ui-btn-primary"' not in listing
```
Replace with:
```python
    # 0203: one property shows its pay steps with one primary action.
    assert listing.count('class="ui-btn ui-btn-primary"') <= 1
```

6b. Create `App/tests/test_stay_fee_pay_steps.py`:
```python
"""0203: the fee list shows confirm, PDF and QR steps; PDF and QR wait for the confirm."""
from __future__ import annotations

import re

from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401


def _csrf(html: str) -> str:
    return re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)


def test_steps_are_locked_until_the_period_is_confirmed(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    assert 'class="ui-section fee-pay"' in page
    assert "Step 1 of 3" in page and "Step 3 of 3" in page
    assert page.count("fee-step-locked") >= 2
    assert f'/stay-fees/{apartment_id}/pdf?month=2026-08' not in page
    assert 'name="return_to" value="/stay-fees?month=2026-08' in page


def test_confirm_from_the_list_comes_back_with_pdf_and_qr(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    response = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(page), "month": "2026-08", "confirm_collected": "1",
              "return_to": "/stay-fees?month=2026-08"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/stay-fees?month=2026-08")
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    assert f'/stay-fees/{apartment_id}/pdf?month=2026-08' in page
    assert "Confirmed" in page
    assert "fee-step-locked" not in page


def test_return_to_outside_the_fee_pages_is_ignored(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    response = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(page), "month": "2026-08", "confirm_collected": "1",
              "return_to": "https://evil.example/"},
        follow_redirects=False,
    )
    assert response.headers["location"].startswith(f"/stay-fees/{apartment_id}?month=2026-08")
```
If a fixture or helper name differs, read only `App/tests/test_stay_fee_detail.py` lines with `def _property`, `def _stay`, `def host` and adapt the call; if the detail test's flow posts other required fields to finalize, add them the same way. If the seeded property has no IBAN, do not assert the QR image; asserting the PDF link is enough.

6c. Create `App/tests/test_stay_fee_pay_steps_browser.py`:
```python
"""0203: pay steps on the fee list at 390, 1280 and 2000 px in en, cs, vi.

Screenshots: ``UBYHOST_CAPTURE_0203=1`` writes PNGs to /mnt/project-files/design-reset/stay-fee-steps/.
"""
from __future__ import annotations

import os
from pathlib import Path

from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _context, _dismiss_prompt, _settle, _with_lang, acc, base, sync_api,
)

OUT = Path("/mnt/project-files/design-reset/stay-fee-steps/")
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0203") == "1"

_CHECK_JS = """() => {
  const doc = document.documentElement;
  const steps = [...document.querySelectorAll('.fee-step')];
  return {sideways: doc.scrollWidth > doc.clientWidth + 1, steps: steps.length,
          primaries: document.querySelectorAll('.ui-btn-primary').length};
}"""


def test_pay_steps_fit_every_width_and_language(acc, base):
    failures = []
    if CAPTURE:
        OUT.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for state in ("before", "after"):
            for lang in ("en", "cs", "vi"):
                for width in (390, 1280, 2000):
                    context = _context(browser, base, acc["cookie"], width=width, height=900)
                    page = context.new_page()
                    page.goto(base + _with_lang("/stay-fees", lang))
                    _settle(page)
                    _dismiss_prompt(page)
                    if state == "after" and lang == "en" and width == 390:
                        button = page.locator(".fee-step form button")
                        if button.count():
                            button.first.click()
                            _settle(page)
                    result = page.evaluate(_CHECK_JS)
                    label = (state, lang, width)
                    if result["sideways"]:
                        failures.append((label, "page scrolls sideways"))
                    if result["steps"] == 0:
                        failures.append((label, "no pay steps"))
                    if result["primaries"] > 1:
                        failures.append((label, "more than one primary"))
                    if CAPTURE:
                        page.screenshot(path=str(OUT / f"stay-fees-{state}-{lang}-{width}.png"), full_page=True)
                    context.close()
        browser.close()
    assert not failures, failures
```
Commands, from `App/`. Browser tests need this env prefix: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium` (`.venv` and playwright are already installed):
- `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_design_fees.py tests/test_host_fee_navigation.py -q --tb=short -x 2>&1 | tail -30`
- `UBYHOST_CAPTURE_0203=1 .venv/bin/python -m pytest tests/test_stay_fee_pay_steps_browser.py tests/test_host_list_cards_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
Commit `0203 step 6`.

## 5. Do not touch

The fee settings fields (`_stay_fee_fields.html`, `fee_form_values`, bank-account parsing): another task is changing them. The detail page `stay_fee_detail.html`. The sent/paid routes. UbyPort code. No new dependency. Never push to `main`.

## 6. Commands

As in each step. Last: `python3 scripts/context_lint.py 2>&1 | tail -5` and `python3 scripts/design_lint.py 2>&1 | tail -5` from the repo root, both OK.

## 7. Acceptance

- [ ] `/stay-fees?month=` shows one pay section per set-up property, above the table, steps 1 to 3.
- [ ] Before confirming, steps 2 and 3 show the dashed placeholder text; after Confirm figures the page returns to the list with Download PDF and the QR (or "Nothing to pay" at 0 Kč).
- [ ] At most one primary button on the page.
- [ ] All tests in §6 pass, browser tests 0 skipped.
- [ ] Screenshots in /mnt/project-files/design-reset/stay-fee-steps/ for before and after, en/cs/vi, 390/1280/2000.

## 8. Stop and ask

As in TEMPLATE.md: excerpt not found, a test fails twice, 25 tool calls or about 50k tokens, a file outside §3, a step unclear.

## 9. Report

`docs/tasks/0203-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions. Set `Status: review`. Do not push.
