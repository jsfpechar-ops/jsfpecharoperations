# 0836: Invoice buyer prefilled from the stay's lead guest

Status: done
Depends on: 0841 (baseline first) | Base commit: b8c87df | Branch: task/0836-invoice-buyer-prefill
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When the host opens a new invoice for a stay, the buyer block already shows the stay's lead guest (name, street, city, country) and a one-line note that it came from the guest; the host checks it and issues. Target: about 7 taps to about 3 (open, pick stay, issue).

## 2. Context

- Today the buyer fills only after the host taps "Use the guest's details" (`fill_from_guest`) or the ARES button. ARES stays **click-only**: it needs an IČO the guest rarely has, and `register_lookup` in `App/app/routes/invoices.py` is documented as "One click-only ARES lookup under the existing per-owner limit". Do not call ARES automatically (new outbound request, rule 2).
- The prefill is a suggestion: visible values in the form, nothing is saved until the host presses issue. Copy only into blank slots (the existing `_merge_guest_fill` already does that).
- Hard rules: no new dependency; light mode; no fine print; one explanation in one place; the 12 px neighbour rule (MASTER `--space-3:12px`): the new note sits in the existing `.invoice-customer` section with the existing `hint` class, no new CSS.

`App/app/routes/invoices.py`, `_form_context` (around line 219), anchor:
```python
    values = dict(values or {})
    if stay and not values and stay["reservation"]["guest_email"]:
        values["buyer_email"] = stay["reservation"]["guest_email"]
    lang = "cs" if _lang(request) == "cs" else "en"
    lead_guest = _lead_guest(stay["reservation"]) if stay else None
```
and, in the returned dict:
```python
        "show_fill_guest": bool(lead_guest),
```
`App/app/templates/invoice_form.html` (around line 77), anchor:
```html
    <div class="invoice-buyer-fields">
```
i18n anchors: `App/app/host_i18n.py` line 1624 (EN) `        "invoice.fill_guest.none": "No checked-in guest on this stay yet.",`, line 3513 (CS) `        "invoice.fill_guest.none": "U tohoto pobytu zatím není vyplněný host.",`; `App/app/host_vi_i18n.py` line 1453 `    "invoice.fill_guest.none": "Lượt lưu trú này chưa có khách đã nhận phòng.",`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/invoices.py` | edit | `_form_context` prefill |
| `App/app/templates/invoice_form.html` | edit | One note line |
| `App/app/host_i18n.py` | edit | EN + CS key |
| `App/app/host_vi_i18n.py` | edit | VI key |
| `App/tests/test_invoice_autofill.py` | edit | Two tests |
| `docs/tasks/0836-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `invoices.py`: replace the five-line anchor with:
```python
    fresh = not values
    values = dict(values or {})
    if stay and fresh and stay["reservation"]["guest_email"]:
        values["buyer_email"] = stay["reservation"]["guest_email"]
    lang = "cs" if _lang(request) == "cs" else "en"
    lead_guest = _lead_guest(stay["reservation"]) if stay else None
    guest_prefilled = False
    if stay and fresh and lead_guest:
        # 0836: suggest the lead guest as buyer on first open; the host checks before issuing.
        _merge_guest_fill(values, lead_guest)
        guest_prefilled = bool(values.get("buyer_name"))
```
   and after `        "show_fill_guest": bool(lead_guest),` add `        "guest_prefilled": guest_prefilled,`. Command: `grep -n "guest_prefilled" app/routes/invoices.py 2>&1 | tail -30` (3 lines). Commit.
2. `invoice_form.html`: first `grep -c '<div class="invoice-buyer-fields">' app/templates/invoice_form.html` must print 1. Insert directly above that line:
```html
    {% if guest_prefilled %}<p class="hint" role="status">{{ t('invoice.fill_guest.prefilled') }}</p>{% endif %}
```
   Commit.
3. i18n, each directly below its `invoice.fill_guest.none` anchor:
   - EN `        "invoice.fill_guest.prefilled": "Filled in from the guest. Check before you issue.",`
   - CS `        "invoice.fill_guest.prefilled": "Vyplněno z údajů hosta. Před vystavením zkontrolujte.",`
   - VI `    "invoice.fill_guest.prefilled": "Đã điền từ thông tin của khách. Hãy kiểm tra trước khi xuất.",`
   Commit.
4. `test_invoice_autofill.py`: after `test_no_complete_guest_means_no_fill_button`, add (same helpers as `test_fill_guest_button_fills_blanks_only`):
```python
def test_first_open_prefills_the_lead_guest_as_buyer(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}")
    assert page.status_code == 200
    assert 'value="Hlavní 1"' in page.text
    assert 'value="Brno"' in page.text
    assert 'name="fill_from_guest"' in page.text


def test_no_guest_means_no_prefill_note(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}")
    assert "Check before you issue." not in page.text
    assert "Vyplněno z údajů hosta" not in page.text
```
   Run §6 command 1. If an older test asserts an empty buyer on first open, change only that expectation and name it in the report. Commit.
5. Run the rest of §6; take the screenshots. Commit.

## 5. Do not touch

ARES code (`register_lookup`, `_buyer_ares_fill`), `invoice_issue`, numbering, PDF, VAT. Wizard, onboarding and property-editor files (other threads). UbyPort rule 1: nothing here touches filing.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_autofill.py -q --tb=short -x 2>&1 | tail -30`
2. Invoices row: `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
4. Copy row: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
5. Screenshots (the test skips without the folder, which is not allowed): `UBYHOST_SHOTS_DIR=../docs/tasks/screenshots-0836 .venv/bin/python -m pytest tests/test_invoice_autofill.py -k screenshots -q --tb=short -rs 2>&1 | tail -30`

Expected: all pass, `0 skipped` in 2, 3 and 5.

## 7. Acceptance

- [ ] First open of `/invoices/new?reservation_id=…` with a complete guest shows the guest's street and city and the note; no guest, no note.
- [ ] No automatic ARES call (`git diff` shows no change near `register_lookup`).
- [ ] Commands 1-5 pass, 0 skipped.
- [ ] One 390 px screenshot of the invoice form in `docs/tasks/screenshots-0836/`.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0836-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Include the 0841 tap count for the invoice flow after the change.

## Risk list (for the reviewer)

`App/app/routes/invoices.py` (`fresh` must be computed before `values` is copied; a 422 re-render must not refill fields the host cleared).

## Owner steps

1. Open the PR, check the 390 px screenshot, merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
