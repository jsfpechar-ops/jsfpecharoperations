# 1075: Prefill what we hold, invoice "More options", share-text order

Status: review
Depends on: 1068 (merged first: same lines in payments.py, payments_new.html, admin.py, i18n) | Base commit: origin/main 2d265364 | Branch: claude/1075-prefill-more-options
Executor: Opus 5.5 (Tier B: step 1 is a payments route with new guest-data SQL; review 2026-11-10). Limits (owner override; the Haiku-only cap does not apply): 40 tool calls, checkpoint at 60k tokens

## 1. Objective

Queue item 1.3 (plan `docs/plans/speed-and-ease.md`, Q3, Q5, Q13, Q14): the host types less. Four prefills (guest e-mail in a payment request, operator e-mail from the account, default check-in 15:00 and check-out 10:00 in the wizard), one fold ("More options" on invoice details), one copy reorder (lock sharing steps before warnings). Nothing is stored that was not stored before.

**Code check done by the orchestrator (2026-11-10, base 2d265364). Dropped because already in the code:**

| Item | Verdict | Where it is |
|---|---|---|
| Q5 IČO lookup wherever an operator is created | DONE. ARES client `App/app/ares.py` (cached 24 h) is wired into the business editor (`_entity_business_fields.html` `ico_field`), the wizard (`setup_wizard/property.html`, 0884), invoice buyer, billing order. No new outside request is needed, so no owner decision. | drop |
| Q3 only operator preselected on invoices | DONE. `invoice_form.html:52` shows one operator as plain text; `_property_operator.html` preselects the single operator. | drop |
| Q3 BIC from bank code | DONE. `payments.bic_for_account`, `routes/invoices.py:495,611`, hint `invoice.fill_guest.bic_filled`. | drop |
| Q13 operator signature modes | DONE. Draw/type/upload sit in a dialog behind "Edit" (`signature_fields` macro). | drop |
| Q13 stay-fee pay options | DONE. They sit behind the "collect the stay fee" switch (`_stay_fee_fields.html`, 0897); the authority details already use the `details.fee-more` fold. | drop |
| Q14 turn on automatically with exactly one lock | DONE. `_default_on_first_lock` in `routes/admin.py:757` (0954). | drop |

**Not in this brief, needs a Tier B brief (multi-file, 6 test files couple to it):** Q14 "remove the second pair of hour selects". The pair `lock_checkin_hour` / `lock_checkout_hour` lives in `_property_editor.html:475`, is synced by `data-hour-twin` in `static/host.js:369`, merged by `_with_lock_tab_hours` in `routes/admin.py:2683`, and pinned by `test_door_lock_tab_times_0414.py`, `test_0952_lock_section_browser.py`, `test_property_page_buttons_browser.py`, `test_host_unsaved_changes_browser.py`, `test_ttlock_setup_0954*.py`, `test_property_navigation_browser.py`. Do not touch it here.

Not confirmed: whether the owner wants the payment e-mail to follow a change of the stay select without a page load (this brief prefills only when the page is opened with `?reservation_id=`, which is how the stays page links to it).

## 2. Context

Rules that apply: light mode only; no new stored personal-data field (every value below is already stored, so no `retention.py` line); no new outbound request; no new dependency; CS and EN keys added together, VI too; no em dash in UI copy. Host page UX gate (AGENTS rule 10). Anchors are verbatim; if one is not found, STOP (§8). Base moved by 1068 only in the lines named below; if another brief already changed an anchor, STOP.

Facts verified in the code:
- `reservation.guest_email TEXT` exists (`App/app/db.py:207`); `routes/invoices.py:269` already prefills the invoice buyer from it.
- `auth.current_user(request)` is in the template context as `current_user` and has `email` (`templating.py:663`). Test accounts: `auth.create_account(email, name, username=...)`.
- The generic `body.v2 details.ui-details-box > summary` styles (app2.css:362-373) already draw the chevron and the 44 px summary. The fold needs no new CSS and no new component, so `design-system.md` gets no new line.
- `/entities` is a v2 page; `invoice_fields` is used only by `entities.html:66`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/payments.py` | edit | step 1: guest e-mail from the stay |
| `App/app/templates/payments_new.html` | edit | step 1: `value=` on the e-mail input |
| `App/app/routes/admin.py` | edit | step 2: `account_email` in the entities page context |
| `App/app/templates/_entity_business_fields.html` | edit | step 2: e-mail default on the new-business form only |
| `App/app/templates/setup_wizard/property.html` | edit | step 3: 15:00 and 10:00 preselected when empty |
| `App/app/templates/_entity_invoice_fields.html` | edit | step 4: "More invoice options" fold |
| `App/app/host_i18n.py` | edit | step 4: one key, EN and CS |
| `App/app/host_vi_i18n.py` | edit | step 4: one key, VI |
| `App/app/templates/_smart_lock_share.html` | edit | step 5: warnings after the steps |
| `App/tests/test_1075_prefill_more_options.py` | create | step 6 |

No other file may change. (Ten small files, each step independent. Tier B because of the step 1 SQL.)

## 4. Steps

Work in the worktree for branch `claude/1075-prefill-more-options`, from `App/`. After each step run its command.

**Step 1: payment request, guest e-mail from the stay.**

1a. `App/app/routes/payments.py`, in `payments_new_page`: the anchor appears twice (also in `payments_page`); use the second occurrence (line ~128, inside `payments_new_page`). Find
```
    prefill = payment_services.get(owner_id, str(request.query_params.get("service") or ""))
    return render(
```
replace with
```
    prefill = payment_services.get(owner_id, str(request.query_params.get("service") or ""))
    guest_email_prefill = ""
    if selected_reservation_id:
        stay_row = db.query_one(
            "SELECT r.guest_email FROM reservation r JOIN apartment a ON a.id = r.apartment_id"
            " WHERE r.id = ? AND a.owner_user_id = ?",
            (selected_reservation_id, owner_id),
        )
        guest_email_prefill = ((stay_row["guest_email"] if stay_row else "") or "").strip()
    return render(
```
1b. same function (again the second occurrence, line ~139), find `            "selected_reservation_id": selected_reservation_id,` and add under it
```
            "guest_email_prefill": guest_email_prefill,
```
1c. `App/app/templates/payments_new.html`, find
```
      <input id="pay-new-guest_email" type="email" name="guest_email"></div>
```
replace with
```
      <input id="pay-new-guest_email" type="email" name="guest_email" autocomplete="off" autocapitalize="none" spellcheck="false"{% if guest_email_prefill %} value="{{ guest_email_prefill }}"{% endif %}></div>
```
Command: `cd App && .venv/bin/python -m pytest tests/test_payments_dashboard.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

**Step 2: operator e-mail from the account (new business form only).**

2a. `App/app/routes/admin.py`, in `_entities_page`, find
```
    context.update(
        {
            "edit_entity": edit_entity,
```
replace with
```
    account_user = auth.current_user(request)
    context.update(
        {
            "account_email": (account_user["email"] or "") if account_user else "",
            "edit_entity": edit_entity,
```
2b. `App/app/templates/_entity_business_fields.html`, find
```
             value="{{ (entity.contact_email or '') if entity else '' }}">
```
replace with
```
             value="{{ (entity.contact_email if entity and entity.contact_email else (account_email if prefix == 'new_' else '')) or '' }}">
```
(An existing business with an empty e-mail is not changed; only the "new_" form gets the default.)
Command: `cd App && .venv/bin/python -m pytest tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

**Step 3: wizard hours, 15:00 and 10:00 when empty.**

`App/app/templates/setup_wizard/property.html`, find
```
        {% for h in range(24) %}<option value="{{ h }}" {% if apartment[name]|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
```
replace with
```
        {% set hour_now = apartment[name] if (apartment[name] is not none and apartment[name]|string != '') else (15 if name == 'checkin_hour' else 10) %}
        {% for h in range(24) %}<option value="{{ h }}" {% if hour_now|string == h|string %}selected{% endif %}>{{ '%02d:00' % h }}</option>{% endfor %}
```
Only the wizard changes. The property editor and the lock tab keep "Choose" (changing them would flip existing properties from "times missing" to "on" without the host asking).
Command: `cd App && .venv/bin/python -m pytest tests/test_wizard_four_steps_0884.py tests/test_wizard_friendly_0273.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If a test asserts the empty "Choose" option is selected, STOP and report it.

**Step 4: invoice "More invoice options" fold.**

4a. `App/app/templates/_entity_invoice_fields.html`: wrap the prefix and next-number fields in one fold. `registry_entry` stays visible next to VAT status, because `routes/invoices.py:488` refuses to issue an invoice without it. Find
```
    <div class="grid">
      <div class="field">
        <label for="invoice_prefix">
```
replace with
```
    <details class="ui-details-box invoice-more"{% if entity.invoice_prefix or entity.invoice_next_number %} open{% endif %}>
      <summary><span>{{ t('entities.invoice_more') }}</span></summary>
    <div class="grid">
      <div class="field">
        <label for="invoice_prefix">
```
4b. same file, find
```
        <input type="number" id="invoice_next_number" name="invoice_next_number" min="1" inputmode="numeric"
               value="{{ entity.invoice_next_number if entity.invoice_next_number else '' }}">
              </div>
```
replace with
```
        <input type="number" id="invoice_next_number" name="invoice_next_number" min="1" inputmode="numeric"
               value="{{ entity.invoice_next_number if entity.invoice_next_number else '' }}">
      </div>
    </div>
    </details>
    <div class="grid">
```
Then the `invoice_due_days` field that follows stays visible, in its own `<div class="grid">` that the macro's last `</div>` and `{% endmacro %}` already close. Read the macro after the edit: the `<div class="grid">` and `<details>` tags must balance (count them).
4c. `App/app/host_i18n.py`, find `        "stay_fees.setup.more_details": "More details (optional)",` and add under it `        "entities.invoice_more": "More invoice options",`. Find `        "stay_fees.setup.more_details": "Další údaje (nepovinné)",` and add under it `        "entities.invoice_more": "Další možnosti faktur",`.
4d. `App/app/host_vi_i18n.py`, find `    "stay_fees.setup.more_details": "Thêm thông tin (không bắt buộc)",` and add under it `    "entities.invoice_more": "Thêm tùy chọn hóa đơn",`.
Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_entity_editor_fields.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_host_help_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). Expected: all pass. If `test_entity_editor_fields.py` has a browser test that reads `#invoice_prefix` while the fold is closed, open the fold in the test with `page.click("details.invoice-more > summary")`; report it as a deviation.

**Step 5: lock sharing, steps first, warnings after.**

`App/app/templates/_smart_lock_share.html`: find
```
  <h2>{{ t('smart_locks.share_title') }}</h2>
  <p class="ui-sub">{{ t('smart_locks.warn_owner') }}</p>
  <p><strong>{{ t('smart_locks.name_label') }}</strong></p>
```
replace with
```
  <h2>{{ t('smart_locks.share_title') }}</h2>
  <p><strong>{{ t('smart_locks.name_label') }}</strong></p>
```
and find
```
  <p class="ui-sub"><strong>{{ t('smart_locks.warn_ekey') }}</strong></p>
```
replace with
```
  <p class="ui-sub">{{ t('smart_locks.warn_owner') }}</p>
  <p class="ui-sub"><strong>{{ t('smart_locks.warn_ekey') }}</strong></p>
```
Command: `cd App && .venv/bin/python -m pytest tests/test_ttlock_setup_0954.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

**Step 6: new test file `App/tests/test_1075_prefill_more_options.py`.** Rendering tests only, no template greps. Create it with this content (fixtures copy `test_payments_dashboard.py`; the lock account copies `test_wizard_second_lock_0400.py`):
```python
"""1075: prefills from data we already hold, the invoice fold, share-text order (rendered pages)."""
from __future__ import annotations

import json
import re
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.conftest import login_as

OWNER = "prefill1075"
FOLD = re.compile(r'<details class="ui-details-box invoice-more"( open)?>')


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
    for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apt['id']}",))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Prefill Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    client = TestClient(app)
    assert login_as(client, OWNER, url="/login?lang=en", follow_redirects=False).status_code == 303
    return client


def _entity(owner_id, **extra):
    return db.insert("legal_entity", {
        "name": "Prefill 1075 s.r.o.", "seat": "Praha", "ico": "12345678", "contact_email": "biz@example.test",
        "vat_status": "non_payer", "invoice_due_days": 14, "owner_user_id": owner_id, "created_at": db.utcnow(),
        **extra,
    })


def _flat(user, **extra):
    return db.insert("apartment", {
        "owner_user_id": user, "internal_name": "Home 1075", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual", "permalink_token": auth.new_permalink_token(), **extra,
    })


def _stay(user, email):
    now = db.utcnow()
    home = _flat(user, checkin_hour=15, checkout_hour=11)
    return db.insert("reservation", {
        "apartment_id": home, "uid": secrets.token_hex(16), "date_from": "2026-12-01",
        "date_to": "2026-12-03", "status": "active", "source": "manual",
        "guest_email": email, "created_at": now, "updated_at": now,
    })


def test_new_business_form_prefills_the_account_email(client):
    html = client.get("/entities?lang=en").text
    field = re.search(r'<input[^>]*id="new_contact_email"[^>]*>', html).group(0)
    assert f'value="{OWNER}@example.test"' in field


def test_edit_form_of_a_business_without_email_stays_empty(client, owner):
    entity = _entity(owner, contact_email="")
    html = client.get(f"/entities?edit={entity}&lang=en").text
    fields = [f for f in re.findall(r'<input[^>]*name="contact_email"[^>]*>', html) if 'id="new_contact_email"' not in f]
    assert fields
    for field in fields:
        assert 'value=""' in field and f"{OWNER}@example.test" not in field


def test_payment_form_prefills_guest_email_only_from_own_stay(client, owner):
    own = _stay(owner, "guest@example.test")
    other = auth.create_account("prefill1075-other@example.test", "Other", username="prefill1075-other", role="host")
    foreign = _stay(other, "secret@example.test")
    try:
        assert 'value="guest@example.test"' in client.get(f"/payments/new?reservation_id={own}&lang=en").text
        page = client.get(f"/payments/new?reservation_id={foreign}&lang=en").text
        assert "secret@example.test" not in page
        assert 'value="guest@example.test"' not in client.get("/payments/new?lang=en").text
    finally:
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (other,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (other,))
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_wizard_hours_default_to_15_and_10_and_keep_saved_hours(client, owner):
    empty = client.get(f"/apartments/{_flat(owner)}/setup/property?lang=en").text
    assert 'value="15" selected' in empty and 'value="10" selected' in empty
    saved = client.get(f"/apartments/{_flat(owner, checkin_hour=16, checkout_hour=11)}/setup/property?lang=en").text
    assert 'value="16" selected' in saved and 'value="11" selected' in saved
    assert 'value="15" selected' not in saved and 'value="10" selected' not in saved


def test_invoice_fold_is_closed_when_empty_and_open_when_a_prefix_is_set(client, owner):
    plain = client.get(f"/entities?edit={_entity(owner)}&lang=en").text
    assert [m.group(1) for m in FOLD.finditer(plain)] == [None]
    numbered = client.get(f"/entities?edit={_entity(owner, invoice_prefix='UB')}&lang=en").text
    assert [m.group(1) for m in FOLD.finditer(numbered)] == [" open"]
    fold = numbered[numbered.index('class="ui-details-box invoice-more"'):]
    fold = fold[:fold.index("</details>")]
    assert 'id="invoice_prefix"' in fold and 'id="invoice_next_number"' in fold
    assert 'id="registry_entry"' not in fold and 'id="invoice_due_days"' not in fold


def test_share_block_lists_steps_before_warnings(client, owner, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    now = db.utcnow()
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "x_prefill1075",
                               "status": "ok", "locks_json": json.dumps([]), "created_at": now, "updated_at": now})
    html = client.get(f"/apartments/{_flat(owner)}?view=settings&section=lock&lang=en").text
    start = html.index('id="smart-locks-share"')
    steps = html.index("In the TTLock app, add UbyHost as eAdmin", start)
    owner_warning = html.index("Only the owner of the lock can do this.", start)
    assert html.index("x_prefill1075", start) < steps < owner_warning < html.index("Do not use eKeys", start)
```
Payments need no Stripe state for the GET page; if `/payments/new` redirects for a missing consent or Stripe setup, STOP and report (do not mock around it).
Command: `cd App && .venv/bin/python -m pytest tests/test_1075_prefill_more_options.py -q --tb=short -x -rs 2>&1 | tail -30`. Expected: 6 passed, 0 skipped.

**Step 7: UX gate and screenshots.** From `App/`:
`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: passed, 0 skipped, zero host findings.
The lint writes `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` (and `<page>+open-...`) for `payments-new`, `operators`, `operator-add`, `operator-edit`, `invoice-settings`, `setup-property`, `smart-locks`. The states it does not reach (stay e-mail filled, fold closed and open, hours empty, share block with a lock account) come from this script, saved in the session scratchpad as `shots_1075.py` (not committed; not a repo file):
```python
"""1075 step 7: 390/768/1280 shots of the touched pages in the states the layout lint does not reach."""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

import playwright.sync_api as sync_api
import uvicorn
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as, mark_security_prompt_seen

OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", "/tmp/shots")) / "1075"
TIP = """() => { const b = document.querySelector('[aria-controls="invoice-next-number-help"]');
  b.scrollIntoView({block: 'center'}); b.click();
  const tip = document.getElementById('invoice-next-number-help').getBoundingClientRect();
  const box = document.querySelector('details.invoice-more').getBoundingClientRect();
  return {tip: [tip.left, tip.top, tip.right, tip.bottom], box: [box.left, box.top, box.right, box.bottom],
          clipped: tip.left < box.left || tip.right > box.right || tip.top < box.top || tip.bottom > box.bottom}; }"""


def test_1075_shots(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    name = f"shots1075-{secrets.token_hex(3)}"
    owner = mark_security_prompt_seen(auth.create_account(f"{name}@example.test", "Shots 1075", role="host", username=name))
    now = db.utcnow()
    base = {"seat": "Praha", "ico": "12345678", "contact_email": "plain@example.test", "vat_status": "non_payer",
            "invoice_due_days": 14, "owner_user_id": owner, "created_at": now}
    plain = db.insert("legal_entity", {**base, "name": "Plain s.r.o."})
    numbered = db.insert("legal_entity", {**base, "name": "Numbered s.r.o.", "invoice_prefix": "UB", "invoice_next_number": 7})
    flat = db.insert("apartment", {"legal_entity_id": plain, "owner_user_id": owner, "internal_name": "Shots flat",
                                   "permalink_token": auth.new_permalink_token(), "active": 1, "created_at": now,
                                   "automation_mode": "manual"})
    stay = db.insert("reservation", {"apartment_id": flat, "uid": secrets.token_hex(16), "date_from": "2026-12-01",
                                     "date_to": "2026-12-03", "status": "active", "source": "manual",
                                     "guest_email": "guest@example.test", "created_at": now, "updated_at": now})
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "x_shots1075", "status": "ok",
                               "locks_json": json.dumps([]), "created_at": now, "updated_at": now})
    client = TestClient(app)
    assert login_as(client, name, url="/login?lang=en", follow_redirects=False).status_code == 303
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    pages = {
        "payments-new-stay": f"/payments/new?reservation_id={stay}",
        "operator-add": "/entities?new=1",
        "operator-edit-fold-closed": f"/entities?edit={plain}",
        "operator-edit-fold-open": f"/entities?edit={numbered}",
        "setup-property": f"/apartments/{flat}/setup/property",
        "lock-tab": f"/apartments/{flat}?view=settings&section=lock",
        "smart-locks": "/smart-locks",
    }
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}"
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            for width in (390, 768, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": url + "/"}])
                page = context.new_page()
                for key, path in pages.items():
                    sep = "&" if "?" in path else "?"
                    response = page.goto(f"{url}{path}{sep}lang=en")
                    assert response and response.status < 400, f"{key}/{width}: {response.status if response else 'none'}"
                    page.wait_for_timeout(400)
                    scroll = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    print(key, width, "sideways scroll px:", scroll)
                    page.screenshot(path=str(OUT / f"{key}-{width}.png"), full_page=True)
                    if key == "operator-edit-fold-open":
                        fold = page.locator("details.invoice-more > summary").bounding_box()
                        print(key, width, "fold summary height:", fold and fold["height"])
                        if width == 1280:
                            print("tip at 1280:", page.evaluate(TIP))
                            page.wait_for_timeout(300)
                            page.screenshot(path=str(OUT / "operator-edit-tip-1280.png"), full_page=False)
                context.close()
            browser.close()
    finally:
        server.should_exit = True
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (flat,))
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{flat}",))
        db.execute("DELETE FROM apartment WHERE id = ?", (flat,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))
```
Run from `App/`: `UBYHOST_SHOTS_DIR=/tmp/shots PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest -p tests.conftest <scratchpad>/shots_1075.py -q -s --rootdir=. 2>&1 | grep -E 'scroll|fold|tip|passed|failed|Error' | tail -40`. Shots land in `/tmp/shots/1075/<page>-{390,768,1280}.png` plus `operator-edit-tip-1280.png`. The share block is covered by the Door lock tab and `/smart-locks` (the wizard door-lock step is retired since 0884).
**Help tip inside the fold:** the fold has `overflow:hidden` (app2.css `details.ui-details-box`) and holds the `invoice-next-number-help` tip, which is `position:absolute` at 1024 px and up. The script opens it at 1280 and prints `clipped`. If it is clipped (check `operator-edit-tip-1280.png` by eye too), STOP: the only allowed fix is dropping `overflow:hidden` from the fold, and only if `docs/design/design-system.md` says so; otherwise set Status: blocked. Open each PNG and look with your own eyes: the fold summary is 44 px high with one chevron and no clipped label; fold fields do not touch the box edge (16 px inset); nothing wraps under a neighbour; no sideways scroll. Write per page in the report and the PR "390: ...; 768: ...; 1280: ..." for every touched page (all three widths each). A shot you could not take is a finding, not a skip.
Also run: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). From the repo root: `python3 scripts/context_lint.py | tail -3`. Expected: `context lint: OK`.

## 5. Do not touch

- `App/app/ares.py`, filing code, `retention.py`, migrations, `db.py` schema.
- The property editor and lock tab hour selects (`_property_editor.html`, `host.js` twin sync, `_with_lock_tab_hours`).
- Any other copy key. No new CSS, no new JS, no inline `style=`.
- Hard rules: no new dependency, no new outbound request, light mode only, never push to `main`.

## 6. Commands

Each step above names its own command; all end `2>&1 | tail -30`. Test-map rows used: host pages (`test_host_*.py`, `test_host_geometry.py`), payments (`test_payments_dashboard.py`), onboarding/wizard (`test_wizard_*`), cleaning of copy (`test_host_i18n.py`, `test_no_em_dashes.py`), door lock (`test_ttlock_setup_0954.py`, `test_smart_locks_page.py`), any host template (`test_design_guardrails_browser.py`, 0 skipped).

## 7. Acceptance

- [ ] `GET /payments/new?reservation_id=<own stay>` shows the stay's guest e-mail; another owner's stay shows none.
- [ ] `/entities` new-business form shows the account e-mail; the edit form of an existing business is unchanged.
- [ ] Wizard property step opens with 15:00 and 10:00 selected when the property has no hours; the property editor still shows "Choose".
- [ ] Invoice details: bank, BIC, VAT status, registry entry, due days visible; prefix and next number inside "More invoice options", closed when both are empty, open when either has a value; saving still stores both (existing `test_entity_editor_fields.py` green); the next-number help tip is not clipped at 1280.
- [ ] Share block order: name, steps, then both warnings.
- [ ] `tests/test_1075_prefill_more_options.py`: 6 passed, 0 skipped. `test_layout_lint_browser.py` and the guardrail/geometry files: 0 skipped.
- [ ] 390, 768 and 1280 px screenshots of every touched page (payments new, entities add and edit with the fold closed and open, wizard property step, Door lock tab, smart locks); report and PR list per page what was seen at each width.
- [ ] Design-system checklist (`docs/design/design-system.md` section 5) pasted into the PR and ticked: extends `host_page.html`, no own `<style>` or `style=""`, one Save per form, no fine print, 12 px between neighbours, 390/768/1280 no sideways scroll, CS and EN (and VI) keys added together, no em dash, CI watched to the end. No new component, so no new line in `design-system.md`.
- [ ] `python3 scripts/context_lint.py | tail -3` prints `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (also if 1068, 1071 or 1072 changed it);
- a test fails twice;
- you reach 40 tool calls or the 60k-token checkpoint (write the report as `blocked`, see executor.md);
- a new dependency or outside request seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- step 3 breaks a wizard test that expects an empty hour;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1075-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/routes/payments.py` (new SQL: owner-scoped by `a.owner_user_id`).
- `App/app/templates/_entity_invoice_fields.html` (balanced `<div>`/`<details>`; fields stay in the form when the fold is closed).
- `App/app/templates/setup_wizard/property.html` (default hours are written when the host presses Next; confirm that is the wanted behaviour).
- The reviewer opens every screenshot.

## Order with other open work

1068 (touches payments.py, payments_new.html, admin.py, both i18n files) merges first; then 1071 (admin.py, i18n; different lines), 1072 (no overlap), the 1.2 brief (1074, check its §3 against this one; lint warns on shared files), then 1075. 1075 stops at its first anchor that moved.

## Owner steps

1. After the PR is green, open the PR "Files" tab and look at the 390 px screenshots of `/entities` and the wizard step.
2. Merge with `scripts/merge-pr-on-green.sh`. Deploy stays manual (you).
