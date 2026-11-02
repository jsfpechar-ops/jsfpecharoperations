# 0886: Invoice buyer switch: Guest or Company

Status: review
Depends on: 0836 (merged in f7b1637) | Base commit: 83aea3e | Branch: task/0886-invoice-buyer-type-switch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The single invoice page gets a two-choice switch at the top of the buyer block: **Guest** or **Company** (owner decision: no wizard). Guest shows the lead guest's details, which 0836 already prefills. Company shows the IČO field with the existing ARES button. The guest-only parts are hidden, and one tap on the ARES button fills the name and address. The issuer picker shows only when the host has two or more entities. Dates, items and amount stay as they are.
Target taps, counted as in 0836 (open, pick stay, Issue; the confirm dialog is not counted): Guest is 3. Company adds two taps (Company, ARES button) plus typing the IČO, so it is 5 from the list and 4 when opened from a stay. Report the counts you see.

## 2. Context

- **Overlap:** PR #707 (guest book and invoices redesign) edits the invoice list and detail pages. This brief touches only `invoice_form.html`, its route context in `invoices.py`, the i18n keys and `test_invoice_autofill.py`. Never touch `invoices.html`, `invoice_detail.html` or any CSS file. First command (must print nothing): `git diff --stat 83aea3e -- App/app/templates/invoice_form.html App/app/routes/invoices.py 2>&1 | tail -30`. If it prints anything, or an anchor below is not found verbatim, STOP (section 8).
- **What exists today:** the issuer `<select id="legal_entity_id">` is always shown, even with one entity. Keep the select in the page, because the VAT script reads `entitySel.selectedOptions` and tests look for `name="legal_entity_id"`. Only hide its wrapper with `hidden` when there are fewer than two entities. The supplier name line `.invoice-supplier-meta` stays visible.
- **ARES stays a click:** there is no new outbound request and no automatic lookup. Do not edit `_buyer_ares_fill` or `register_lookup`. `_buyer_ares_fill` only fills **blank** slots, so a guest name prefilled by 0836 would block it. The fix is a new route helper that blanks the slots that still hold the guest's suggestion, before the lookup, and only when `buyer_kind == "company"`. Values the host typed stay. The country stays, because its select always posts a value.
- **No JS:** the switch is two real radios (`buyer_kind`) inside the form. They are posted, and the server keeps the choice on every re-render (`_form_state`). Without JS, every buyer field shows. With JS, the parts for the other choice get `hidden` and `disabled`, so they are never posted (an IČO typed before switching to Guest does not reach the invoice). Global `[hidden] { display: none !important; }` already exists in `app.css`.
- **No new CSS:** reuse `choice_card` (`_components.html`, 0410) and the existing `ui-toolbar` row. `.host-workspace .ui-toolbar` has `gap: var(--space-3)`, which is the 12 px neighbour rule. Inside a card, the "?" sits at `gap: var(--space-2) var(--space-3)`. Help goes only in the "?" on the Company card, with no fine print. The 0836 note stays the one explanation for Guest. `test_design_invoices.py` forbids raw `style`.
- **Never autosaved:** add no `localStorage`, `sessionStorage` or `fetch` save. Nothing is stored until Issue, and Issue keeps its `data-confirm` dialog.
- Light mode only. Rule 1 (UbyPort) is not touched.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/invoices.py` | edit | Helper, `_form_state` key, `_form_context` default, ARES branch |
| `App/app/templates/invoice_form.html` | edit | Import, picker `hidden`, switch, part markers, DIČ marker, script |
| `App/app/host_i18n.py` | edit | EN and CS keys |
| `App/app/host_vi_i18n.py` | edit | VI keys |
| `App/tests/test_invoice_autofill.py` | edit | Four tests and one screenshot test |
| `docs/tasks/0886-report.md` | new | Report |
| `docs/tasks/screenshots-0886/` | new | PNGs |

No other file may change.

## 4. Steps

Find each anchor with `grep -nF`. Every anchor must match exactly once.

**Step 1. `App/app/routes/invoices.py`, four edits.**

1a. Anchor (the end of `_merge_guest_fill`):
```python
        if value and not (state.get(key) or "").strip():
            state[key] = value
```
Directly below it, after one blank line, add:
```python


def _drop_guest_suggestion(state: Dict[str, Any], guest) -> None:
    """0886: blank buyer slots that still hold the guest's suggestion, so ARES can fill them."""
    if not guest:
        return
    for key, value in _guest_buyer_values(guest).items():
        if key != "buyer_country" and value and (state.get(key) or "").strip() == value:
            state[key] = ""
```
1b. In `_form_state`, replace `        "due_date", "duzp", "note",` with `        "due_date", "duzp", "note", "buyer_kind",`.

1c. In `_form_context`, anchor `        guest_prefilled = bool(values.get("buyer_name"))`. Directly below it add (4 spaces of indent, not 8):
```python
    buyer_kind = values.get("buyer_kind")
    if buyer_kind not in ("guest", "company"):
        buyer_kind = "company" if str(values.get("buyer_ico") or "").strip() else "guest"
```
Then, below `        "guest_prefilled": guest_prefilled,`, add `        "buyer_kind": buyer_kind,`.

1d. In `invoice_issue`, anchor:
```python
        values = _form_state(request, form, entity)
        meta = _buyer_ares_fill(request, form, values)
```
Replace it with:
```python
        values = _form_state(request, form, entity)
        if values.get("buyer_kind") == "company":
            _drop_guest_suggestion(values, _lead_guest(stay["reservation"]))
        meta = _buyer_ares_fill(request, form, values)
```
Command: `grep -n "buyer_kind\|_drop_guest_suggestion" app/routes/invoices.py 2>&1 | tail -30`. Expected: 8 lines (1a def, 1b, 1c three, 1c dict, 1d two). Commit `0886 step 1`.

**Step 2. `App/app/templates/invoice_form.html`, five edits.**

2a. Replace `{% from "_components.html" import field_label, help_tip with context %}` with `{% from "_components.html" import field_label, help_tip, choice_card with context %}`.

2b. Replace `    <div class="ui-field invoice-supplier-picker">` with `    <div class="ui-field invoice-supplier-picker"{% if entities|length < 2 %} hidden{% endif %}>`.

2c. Replace these three lines (customer section, around line 60):
```html
    <h2>{{ t('invoice.section.customer') }}</h2>
    <div class="invoice-lookup">
      <div class="ui-field invoice-lookup-ico">
```
with:
```html
    <h2 id="invoice-customer-title">{{ t('invoice.section.customer') }}</h2>
    <div class="ui-toolbar invoice-buyer-kind" role="radiogroup" aria-labelledby="invoice-customer-title">
      {{ choice_card('buyer_kind', 'guest', t('invoice.buyer_kind.guest'), buyer_kind == 'guest') }}
      {{ choice_card('buyer_kind', 'company', t('invoice.buyer_kind.company'), buyer_kind == 'company', 'buyer-kind-company-help', t('invoice.buyer_kind.company_help')) }}
    </div>
    <div class="invoice-lookup"{% if not show_fill_guest %} data-buyer-only="company"{% endif %}>
      <div class="ui-field invoice-lookup-ico" data-buyer-only="company">
```
2d. Replace these two lines:
```html
      <div class="invoice-lookup-guest">
        <span class="ui-sub">{{ t('invoice.buyer.or') }}</span>
```
with:
```html
      <div class="invoice-lookup-guest" data-buyer-only="guest">
        <span class="ui-sub" data-buyer-or>{{ t('invoice.buyer.or') }}</span>
```
Then replace `{% if guest_prefilled %}<p class="hint" role="status">` with `{% if guest_prefilled %}<p class="hint" role="status" data-buyer-only="guest">`.

2e. Replace the two lines:
```html
      <div class="ui-field invoice-f-half">
        <label for="buyer_dic">
```
with:
```html
      <div class="ui-field invoice-f-half" data-buyer-only="company">
        <label for="buyer_dic">
```
2f. Script. Anchor `  if (paidRadio && dueRadio) {`. Directly above it insert:
```js
  /* 0886: Guest or Company. Without JS every buyer field shows. With JS the
     other choice's parts are hidden and disabled, so they are never posted. */
  function syncBuyerKind() {
    var checked = form.querySelector('input[name="buyer_kind"]:checked');
    var kind = checked ? checked.value : "";
    form.querySelectorAll("[data-buyer-only]").forEach(function (part) {
      var off = kind !== "" && part.getAttribute("data-buyer-only") !== kind;
      part.hidden = off;
      part.querySelectorAll("input, select, button").forEach(function (control) { control.disabled = off; });
    });
    form.querySelectorAll("[data-buyer-or]").forEach(function (part) { part.hidden = kind !== ""; });
  }
  form.querySelectorAll('input[name="buyer_kind"]').forEach(function (radio) {
    radio.addEventListener("change", syncBuyerKind);
  });
  syncBuyerKind();

```
Command: `grep -c 'data-buyer-only' app/templates/invoice_form.html 2>&1 | tail -30`. Expected: `7` (lookup box, IČO, guest div, note, DIČ, and two script lines). Commit `0886 step 2`.

**Step 3. i18n.** Each line goes directly below its `invoice.fill_guest.prefilled` line.
- `App/app/host_i18n.py` EN (below `        "invoice.fill_guest.prefilled": "Filled in from the guest. Check before you issue.",`):
```python
        "invoice.buyer_kind.guest": "Guest",
        "invoice.buyer_kind.company": "Company",
        "invoice.buyer_kind.company_help": "For a company that pays the stay. The name and address come from ARES, the Czech business register, by IČO.",
```
- CS (below `        "invoice.fill_guest.prefilled": "Vyplněno z údajů hosta. Před vystavením zkontrolujte.",`):
```python
        "invoice.buyer_kind.guest": "Host",
        "invoice.buyer_kind.company": "Firma",
        "invoice.buyer_kind.company_help": "Pro firmu, která pobyt platí. Název a adresu doplní ARES, obchodní rejstřík ČR, podle IČO.",
```
- `App/app/host_vi_i18n.py` (below `    "invoice.fill_guest.prefilled": "Đã điền từ thông tin của khách. Hãy kiểm tra trước khi xuất.",`):
```python
    "invoice.buyer_kind.guest": "Khách",
    "invoice.buyer_kind.company": "Công ty",
    "invoice.buyer_kind.company_help": "Dành cho công ty thanh toán lượt lưu trú. Tên và địa chỉ được lấy từ ARES, sổ đăng ký doanh nghiệp Séc, theo IČO.",
```
Command: `grep -c "invoice.buyer_kind" app/host_i18n.py app/host_vi_i18n.py 2>&1 | tail -30`. Expected: `6` and `3`. Commit `0886 step 3`.

**Step 4. `App/tests/test_invoice_autofill.py`.** Add near the top, below `from tests.invoice_stay_helper import drop_stays, make_stay, stay_form`: `from unittest.mock import patch`. Then, directly after the function `test_no_guest_means_no_prefill_note` (before `def test_fill_guest_without_complete_guest_does_not_issue`), add:
```python
ARES_FIRM = {"name": "ARES Test s.r.o.", "street": "Ulice 5", "city": "Praha", "zip": "11000",
             "country": "CZE", "dic": "CZ04656679"}


def _ares_post(host, entity_id, stay_id, kind, buyer_name="Jan Novák"):
    with patch("app.ares.lookup", return_value=dict(ARES_FIRM)), \
         patch("app.ares.rate_limited", return_value=False), \
         patch("app.ares.record_lookup"):
        return host.post(
            "/invoices?lang=en",
            data={
                "legal_entity_id": str(entity_id), **stay_form(stay_id),
                "buyer_kind": kind, "buyer_ico": "04656679", "fill_buyer_from_register": "1",
                "buyer_name": buyer_name, "buyer_street": "Hlavní 1", "buyer_city": "Brno",
                "buyer_zip": "", "buyer_country": "CZE", "lang": "cs",
            },
        )


def test_switch_renders_two_radios_and_all_fields_without_js(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}").text
    assert '<input type="radio" name="buyer_kind" value="guest" checked>' in page
    assert '<input type="radio" name="buyer_kind" value="company">' in page
    assert 'id="buyer_ico"' in page and 'id="buyer_dic"' in page
    assert 'data-buyer-only="company" hidden' not in page
    assert 'invoice-supplier-picker" hidden' in page


def test_two_entities_show_the_issuer_picker(host):
    entity_id = _add_entity()
    _add_entity(name="Second s.r.o.")
    stay_id = make_stay(_owner(), entity_id=entity_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}").text
    assert 'invoice-supplier-picker" hidden' not in page
    assert 'id="legal_entity_id"' in page


def test_company_lookup_replaces_the_guest_suggestion(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    response = _ares_post(host, entity_id, stay_id, "company")
    assert response.status_code == 200
    assert 'value="ARES Test s.r.o."' in response.text
    assert 'value="Ulice 5"' in response.text
    assert 'value="Hlavní 1"' not in response.text
    assert '<input type="radio" name="buyer_kind" value="company" checked>' in response.text
    assert db.query_one("SELECT 1 AS x FROM invoice WHERE owner_user_id = ?", (_owner(),)) is None


def test_company_lookup_keeps_what_the_host_typed(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    response = _ares_post(host, entity_id, stay_id, "company", buyer_name="Typed Firm")
    assert 'value="Typed Firm"' in response.text
    guest = _ares_post(host, entity_id, stay_id, "guest")
    assert 'value="Jan Novák"' in guest.text
```
Then, at the end of the file, add the screenshot test (same setup as `test_invoice_fill_screenshots_at_required_widths`):
```python
def test_invoice_buyer_kind_screenshots():
    """0886 acceptance: Guest and Company at 390 and 1280; the switch hides the other parts."""
    import os
    import secrets
    import socket
    import threading
    import time

    import pytest
    import uvicorn

    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.test_invoice_stay_browser import _browser_session_cookie, _launch

    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if not shots:
        pytest.skip("set UBYHOST_SHOTS_DIR to capture acceptance screenshots")

    db.init_db()
    username = f"invkind{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Kind Shots", username=username)
    entity = db.insert(
        "legal_entity",
        {
            "name": "Kind s.r.o.", "seat": "Praha 1", "ico": "04656679",
            "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
            "vat_status": "non_payer", "invoice_due_days": 14,
            "owner_user_id": owner, "created_at": db.utcnow(),
        },
    )
    stay_id = make_stay(owner, entity_id=entity)
    _complete_guest(stay_id)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    session = _browser_session_cookie(username)
    path = f"/invoices/new?reservation_id={stay_id}&entity={entity}&lang=en"

    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in (390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            page.goto(base + path)
            page.wait_for_load_state("networkidle")
            assert page.locator("#legal_entity_id").is_hidden()
            assert page.locator("#buyer_ico").is_hidden()
            assert page.locator('button[name="fill_from_guest"]').is_visible()
            page.screenshot(path=os.path.join(shots, f"invoice-kind-guest-{width}.png"), full_page=True)
            page.click('label.ui-choice-card-label:has(input[value="company"])')
            assert page.is_checked('input[name="buyer_kind"][value="company"]')
            assert page.locator("#buyer_ico").is_visible()
            assert page.locator('button[name="fill_from_guest"]').is_hidden()
            page.screenshot(path=os.path.join(shots, f"invoice-kind-company-{width}.png"), full_page=True)
            context.close()
        browser.close()
    server.should_exit = True
    thread.join(timeout=5)
```
Run section 6, command 1. If an older test in this file breaks only because the picker is now `hidden` or the switch was added, change only that expectation and name it in the report. Commit `0886 step 4`.

**Step 5.** Run the rest of section 6, then commit the screenshots and the report as `0886 step 5`.

## 5. Do not touch

`_buyer_ares_fill`, `register_lookup`, `app/ares.py`, `invoice_issue` beyond step 1d, `_draft`, numbering, PDF and VAT. `invoices.html`, `invoice_detail.html`, every `.css` file (PR #707), wizard and onboarding files. Add no storage or autosave.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_autofill.py tests/test_0293_invoice_form.py tests/test_design_invoices.py -q --tb=short -x 2>&1 | tail -30`
2. Invoices row: `UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0886 .venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x -rs 2>&1 | tail -30` (run `mkdir -p ../docs/tasks/screenshots-0886` first)
3. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
4. Copy row: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
5. Screenshots: `UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0886 .venv/bin/python -m pytest tests/test_invoice_autofill.py -k "kind_screenshots" -q --tb=short -rs 2>&1 | tail -30`

Expected: all pass, with `0 skipped` in 2, 3 and 5. The 0836 report named two failures that already happen on the base commit: `test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry` and `test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects`. If only those fail, rerun 3 and 4 without `-x`, report the counts, and do not fix them.

## 7. Acceptance

- [ ] With one entity the issuer select is hidden (still posted); with two it shows.
- [ ] First open shows Guest checked, the guest's details and no IČO field (JS on); Company shows the IČO and the ARES button and hides "Use the guest's details".
- [ ] The ARES lookup in Company mode replaces the guest suggestion, keeps typed values and issues nothing.
- [ ] Without JS all buyer fields render (`data-buyer-only` is never `hidden` in server HTML).
- [ ] `git diff 83aea3e -- App/app/ares.py App/app/static` is empty; `git diff 83aea3e | grep -c "localStorage\|sessionStorage"` prints 0.
- [ ] Commands 1 to 5 pass, 0 skipped.
- [ ] `docs/tasks/screenshots-0886/` holds `invoice-kind-guest-390.png`, `invoice-kind-company-390.png`, `invoice-kind-guest-1280.png`, `invoice-kind-company-1280.png`.

## 8. Stop and ask

Stop and write the report if:
- the first command in section 2 prints anything, or `invoice_form.html` differs from the excerpts here (PR #707 or another thread may have changed it);
- an anchor is not found, or is found more than once;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md);
- a CSS change seems needed for the layout (send the screenshot and do not edit CSS);
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need to push, merge, set secrets, use SSH or deploy.

## 9. Report

Write `docs/tasks/0886-report.md` (600 tokens at most) and set `Status: review`. Include:
- the files changed (`git diff --stat 83aea3e`);
- each command with its last 5 lines;
- section 7, ticked;
- deviations and questions;
- the owner steps left;
- the tap counts for Guest and Company as in section 1;
- that command 2 also rewrites the 0836 `invoice-fill-*` shots into this folder (expected).

## Risk list (for the reviewer)

- `invoice_form.html`: the 12 px gap between the two cards at 390 px; the empty grey lookup box is hidden when there is no guest.
- `invoices.py` step 1d: only an untouched guest suggestion may be blanked.

## Owner steps

1. Open the PR and look at the four screenshots.
2. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
