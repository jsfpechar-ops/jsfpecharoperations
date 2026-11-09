# 1071: Host alert when stay-fee collection is on and no pay way works

Status: todo
Depends on: 1068a (merged first) | Base commit: 0d851ca4 | Branch: task/1071-host-alert-no-pay-way
Executor: Sonnet 5.5 at medium effort (owner override: `[workflow]` decision 2026-11-09 in docs/context/decisions.md and workflow.md#roles-and-models, added in PR #854; the 30-call cap is Haiku only) | Limits: 40 tool calls, checkpoint at 60k tokens.
Re-copy anchors in `host_i18n.py`, `host_vi_i18n.py` and `routes/admin.py` from main after 1068a merges. Queue item 2.4, Tier C. Plan: docs/plans/guest-group-registration.md section 8 (P6) and section 9 (F5).

## 1. Objective

When a property collects the stay fee from guests and none of the pay ways it offers works (for example the bank account was removed), the host gets one alert at once: "Guests cannot pay the stay fee: add a bank account", with a button to the fix. The alert clears by itself when a pay way works again or collection is turned off.

Guest side is out of scope. One alert kind, no schema change, no mail (a new `warning` alert sends none; see §2).

## 2. Context

**Which goes first.** Open brief 1068a (`claude/1068-errors-link-fix`, status blocked) edits `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` and `App/app/routes/admin.py` too. **1068a goes first (merged before this brief runs).** This brief's anchors are single lines 1068a does not touch (the `notification.action.business` lines, the `_resolve_controller_alerts` function, the `apartment_updated` audit line), if an anchor is missing, STOP. Briefs 1066 and 1067 (guest form, `base.html`, `app2.css`, `static_versions.json`) share no file with this one; order does not matter.

**The pay-way rule today is inline.** There is no function that says "this property has a working pay way". The guest pay box builds its list inside `_fee_pay_panel` in `App/app/routes/guest.py` (about lines 2412-2468). A way works when it is enabled in `apartment.stay_fee_guest_rails` (a stored `qr` counts as `iban`) and: `iban` needs an account on the property's operator (`legal_entity.iban`, else `legal_entity.bank_account`); `revolut` needs `apartment.stay_fee_guest_revolut_link`; `cash` always works. Stripe is not part of the guest stay-fee ways, so "Stripe not ready" never matters here. Step 1 moves exactly this rule into `App/app/stay_fee.py` and makes `_fee_pay_panel` call it, so the alert and the guest box can never disagree. Do not write the rule a third time.

The guest hub shows "Your host has not finished setting up payment yet" (`fee_no_rails`, `i18n.py`) when the list is empty. Save time already blocks an empty setup (`check_guest_pay_setup`, `routes/stay_fees.py:582`), so the broken state arises later: the account is removed, or an operator is switched.

**Alert mechanism (`App/app/alerts.py`), reused as is.**
- `alerts.raise_alert(level, kind, message, detail, dedupe_key=, apartment_id=, params=)` inserts, or refreshes the open row with the same `dedupe_key` (unique index on open rows).
- `alerts.resolve(dedupe_key)` closes it. `alerts.open_alert(dedupe_key)` reads it.
- A kind not in `_COMPUTED_ALERT_KINDS` is rendered from its stored `params` and the `notification.<kind>.title` / `.detail` keys (`_present_stored`). The button comes from `_ACTIONS`.
- The card shows on the dashboard and every host page through `_host_alerts.html`; no template change is needed.
- Mail and push: `raise_alert` sends nothing. Push is only the four urgent events of brief 0228 (`push.py:455`). So level `warning` mails nobody. Step 8 checks this by command.
- Precedent for raise-then-resolve in one function: `apartment_setup` in `reporting.py:2155-2170`.

**Hook points (when the state can change).** Property save (`routes/admin.py`, the `apartment_updated` audit in the save function), operator edit (`routes/admin.py`, `_resolve_controller_alerts` is called after `db.update("legal_entity", ...)`), and the daily 07:00 job `_job_stay_fee_mail` in `scheduler.py`, which catches everything else (for example the deployment switch). Two more writers change the inputs but get **no hook** and are sweep-only, cleared by the 07:00 job: the operator account edit in `routes/invoices.py` (near line 519, `db.update("legal_entity", entity["id"], detail)`) and the rails form `booking_rails.parse_form`. Do not add hooks for them. A host who dismisses the card sees it again at the next 07:00 run while the fault remains; that is intended.

**Copy (rule 9).** One explanation, in the `detail` key only; the title says what is wrong, the button says where to go. Never the word "paid" (or its translation) (the app does not record guest payments). No em dash. Host languages are en, cs, vi: all three get the keys. `test_english_and_czech_carry_the_same_keys` and the vi check in `test_host_i18n.py` enforce it.

| Key | en | cs | vi |
|---|---|---|---|
| `notification.stay_fee_no_pay_way.title` | `%(property)s: guests cannot pay the stay fee. Add a bank account.` | `%(property)s: hosté nemohou zaplatit pobytový poplatek. Přidejte bankovní účet.` | `%(property)s: khách không thể thanh toán phí lưu trú. Hãy thêm tài khoản ngân hàng.` |
| `notification.stay_fee_no_pay_way.detail` | `You ask guests to pay the stay fee, but none of the ways you offer works, so they see that you have not finished setting up payment. Add a bank account, or turn on cash.` | `Žádáte hosty o úhradu pobytového poplatku, ale žádný z nabízených způsobů nefunguje, takže vidí, že jste nedokončili nastavení plateb. Přidejte bankovní účet nebo zapněte hotovost.` | `Bạn yêu cầu khách thanh toán phí lưu trú, nhưng không cách nào bạn đưa ra hoạt động, nên khách thấy bạn chưa hoàn tất cài đặt thanh toán. Hãy thêm tài khoản ngân hàng hoặc bật tiền mặt.` |
| `notification.action.stay_fee_pay` | `Fix stay fee payment` | `Opravit platbu poplatku` | `Sửa cách thanh toán phí` |

The English log copy stored in the row (`message`) is `Guests cannot pay the stay fee: add a bank account` (the owner's wording); the card a host reads comes from the keys above.

**UX gate (rule 10, workflow.md#ux-gate).** The only host-visible change is a card in the existing alert stack. No template or CSS changes, but the dashboard page shows a new card, so run the gate: layout lint green, screenshots at 390/768/1280 of the touched pages, a line per page, and the design-system checklist ticked. Step 7 seeds the card into the layout-lint fixture so it appears in the screenshots.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | `RAIL_ORDER`, `payout_account`, `usable_rail_keys`, `no_pay_way`, `reconcile_no_pay_way_alert`, `reconcile_all_no_pay_way` |
| `App/app/routes/guest.py` | edit | `_fee_pay_panel` calls the shared rule; delete the local `RAIL_ORDER` |
| `App/app/alerts.py` | edit | one `_ACTIONS` entry |
| `App/app/routes/admin.py` | edit | two hook calls and one small helper |
| `App/app/scheduler.py` | edit | import `stay_fee`; one call in `_job_stay_fee_mail` |
| `App/app/host_i18n.py` | edit | 3 keys en, 3 keys cs |
| `App/app/host_vi_i18n.py` | edit | 3 keys vi |
| `App/tests/test_stay_fee_no_pay_way_1071.py` | create | raise, dedupe, auto-resolve, copy, shared rule |
| `App/tests/test_alert_language.py` | edit | one `STORED_KINDS` entry |
| `App/tests/test_layout_lint_browser.py` | edit | seed the card for the screenshots |
| `docs/context/test-map.md` | edit | add the missing alerts row |

No other file may change. Never edit `go/`, never a migration, never a template or CSS file.

## 4. Steps

Work from `App/`. Each step: edit, run the command, check the result. If an anchor is not found verbatim, STOP (§8).

1. **Shared rule in `App/app/stay_fee.py`.** Directly after

```python
def is_active(apartment) -> bool:
    return bool(apartment) and int(apartment["stay_fee_rate_czk"] or 0) > 0
```

add (no existing import changes: `alerts` is added next to the existing `from . import ...` line, see below):

```python


RAIL_ORDER = ("iban", "revolut", "cash")
NO_PAY_WAY_KIND = "stay_fee_no_pay_way"


def payout_account(apartment) -> Tuple[str, str]:
    """(account, payee) of the operator guests pay, or ("", "") when none is on file."""
    account = ""
    payee = ""
    if apartment["legal_entity_id"]:
        entity = db.query_one(
            "SELECT iban, bank_account, name FROM legal_entity WHERE id = ?",
            (apartment["legal_entity_id"],),
        )
        if entity is not None:
            payee = (entity["name"] or "").strip()
            if entity["iban"]:
                account = entity["iban"]
            elif entity["bank_account"]:
                account = payments.normalise_account(entity["bank_account"])[1]
    return account, payee


def usable_rail_keys(apartment) -> List[str]:
    """The guest pay ways that work for this property, in the order the guest sees them.

    The one rule for the guest pay box and for the host alert (brief 1071).
    A stored "qr" is the bank rail. A way works when it is enabled and has what it needs:
    bank transfer an account, Revolut a link; cash needs nothing.
    """
    enabled = {part for part in (apartment["stay_fee_guest_rails"] or "").split(",") if part}
    if "qr" in enabled:
        enabled.add("iban")
    first = apartment["stay_fee_guest_default_rail"] or ""
    if first == "qr":
        first = "iban"
    order = ([first] if first in RAIL_ORDER else []) + [key for key in RAIL_ORDER if key != first]
    account, _payee = payout_account(apartment)
    usable = []
    for key in order:
        if key not in enabled:
            continue
        if key == "iban" and not account:
            continue
        if key == "revolut" and not apartment["stay_fee_guest_revolut_link"]:
            continue
        usable.append(key)
    return usable


def no_pay_way(apartment) -> bool:
    """Collection is on, the fee is active, the deployment asks guests to pay, and no way works."""
    return (
        bool(apartment["stay_fee_collect"])
        and is_active(apartment)
        and bool(config.STAY_FEE_GUEST_PAY)
        and not apartment["archived_at"]
        and not usable_rail_keys(apartment)
    )


def reconcile_no_pay_way_alert(apartment_id: int) -> None:
    """Raise the host alert while no pay way works; resolve it as soon as one does or collection is off."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    key = f"{NO_PAY_WAY_KIND}:{apartment_id}"
    if apartment is None or not no_pay_way(apartment):
        alerts.resolve(key)
        return
    alerts.raise_alert(
        "warning",
        NO_PAY_WAY_KIND,
        "Guests cannot pay the stay fee: add a bank account",
        "",
        dedupe_key=key,
        apartment_id=apartment_id,
        params={"property": apartment["internal_name"]},
    )


def reconcile_all_no_pay_way() -> int:
    """Daily sweep: re-check every property that collects, and every open alert of this kind."""
    ids = {
        row["id"]
        for row in db.query("SELECT id FROM apartment WHERE stay_fee_collect = 1 AND archived_at IS NULL")
    }
    ids |= {
        row["apartment_id"]
        for row in db.query(
            "SELECT apartment_id FROM alert WHERE kind = ? AND resolved_at IS NULL AND apartment_id IS NOT NULL",
            (NO_PAY_WAY_KIND,),
        )
    }
    for apartment_id in ids:
        reconcile_no_pay_way_alert(apartment_id)
    return len(ids)
```

Then change the import line `from . import config, db, payments, reporting, stay_fee_rate, validation` to `from . import alerts, config, db, payments, reporting, stay_fee_rate, validation`.
Command: `.venv/bin/python -c "from app import stay_fee; print(stay_fee.RAIL_ORDER)" 2>&1 | tail -30`. Expected: `('iban', 'revolut', 'cash')`, no ImportError (reporting already imports alerts, so no new cycle).

2. **Guest box uses the shared rule.** In `App/app/routes/guest.py`, function `_fee_pay_panel`, replace

```python
    account = ""
    payee = ""
    if apartment["legal_entity_id"]:
        entity = db.query_one(
            "SELECT iban, bank_account, name FROM legal_entity WHERE id = ?",
            (apartment["legal_entity_id"],),
        )
        if entity is not None:
            payee = (entity["name"] or "").strip()
            if entity["iban"]:
                account = entity["iban"]
            elif entity["bank_account"]:
                account = payments.normalise_account(entity["bank_account"])[1]
```

with

```python
    account, payee = stay_fee.payout_account(apartment)
```

and replace the block from `    rails = []` down to and including the `rails.append({"key": "cash", ...})` statement (it ends with `"note": apartment["stay_fee_guest_cash_note"] or t("fee_cash_default")})`) with

```python
    rails = []
    for key in stay_fee.usable_rail_keys(apartment):
        if key == "iban":
            qr = ""
            if qr_ok:
                payload = payments.spayd(account, total, vs, message)
                qr = payments.qr_data_uri(payload)
            rails.append({"key": "iban", "iban": payments.format_iban(account), "qr": qr})
        elif key == "revolut":
            rails.append({"key": "revolut", "link": apartment["stay_fee_guest_revolut_link"]})
        else:
            rails.append({"key": "cash",
                          "note": apartment["stay_fee_guest_cash_note"] or t("fee_cash_default")})
```

Keep the `return {"total": total, ...}` line after it unchanged. Then delete the line `RAIL_ORDER = ("iban", "revolut", "cash")` (above `_fee_pay_panel`; nothing else uses it).
Command: `.venv/bin/python -m pytest tests/test_stay_fee_audit_1025.py tests/test_stay_fee_guest_pay_0897.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (the guest box behaves exactly as before).

3. **Button target.** In `App/app/alerts.py`, in `_ACTIONS`, directly after the `"guest_question": (...)` line add

```python
    "stay_fee_no_pay_way": ("notification.action.stay_fee_pay", "/apartments/{apartment}?view=settings&section=reporting#stay-fee-settings"),
```

Command: `grep -n "stay_fee_no_pay_way" app/alerts.py | tail -30`. Expected: one line.

4. **Copy.** In `App/app/host_i18n.py`, directly after the line `        "notification.action.business": "Add business details",` add the en keys; directly after `        "notification.action.business": "Doplnit údaje o firmě",` add the cs keys; in `App/app/host_vi_i18n.py`, directly after `    "notification.action.business": "Thêm thông tin doanh nghiệp",` add the vi keys. Text exactly as in the §2 table, same indentation as the line above (8 spaces in `host_i18n.py`, 4 in `host_vi_i18n.py`), keys in this order: `notification.stay_fee_no_pay_way.title`, `notification.stay_fee_no_pay_way.detail`, `notification.action.stay_fee_pay`. Keep `%(property)s` as written.
Command: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

5. **Hooks in `App/app/routes/admin.py`.**
   a. Directly after the function `_resolve_controller_alerts` (it ends with `            alerts.resolve(f"controller_missing:{apartment['id']}")`) add:

```python


def _reconcile_pay_way_alerts(entity_id: int) -> None:
    """1071: an operator's bank account may have changed; re-check the properties that use it."""
    for apartment in db.query("SELECT id FROM apartment WHERE legal_entity_id = ?", (entity_id,)):
        stay_fee.reconcile_no_pay_way_alert(apartment["id"])
```

   b. In the entity update route, replace

```python
    db.update("legal_entity", entity_id, payload)
    _resolve_controller_alerts(entity_id)
    # 0076: back to where the editor was opened from (property, invoice), if any.
```

with the same three lines plus `    _reconcile_pay_way_alerts(entity_id)` inserted after `_resolve_controller_alerts(entity_id)`. (Do not touch the create route, whose new entity has no property yet.)

   c. In the property save function, replace

```python
    db.audit("apartment_updated", f"id={apartment_id}")
    if "lock_provider" in payload and payload["lock_provider"] != prior_lock_provider:
```

with `    db.audit("apartment_updated", f"id={apartment_id}")`, then `    stay_fee.reconcile_no_pay_way_alert(apartment_id)`, then the original `if "lock_provider"...` line.
Command: `.venv/bin/python -c "import app.routes.admin" 2>&1 | tail -30`. Expected: no output.

6. **Daily sweep.** In `App/app/scheduler.py`, in the import block replace `    signup,\n    stay_fee_auto,\n)` with `    signup,\n    stay_fee,\n    stay_fee_auto,\n)`. In `_job_stay_fee_mail`, directly after `        counts = stay_fee_auto.run()` add its own guarded call, so a sweep failure never marks `stay_fee_mail` failed:

```python
        try:
            stay_fee.reconcile_all_no_pay_way()
        except Exception:
            log.exception("stay-fee no-pay-way sweep failed")
```

(inside the existing `try`, same indentation as the line above; the inner `try/except Exception` swallows the error so the outer handler is not reached).
Command: `.venv/bin/python -m pytest tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`. Expected: pass.

7. **Tests.**
   a. Create `App/tests/test_stay_fee_no_pay_way_1071.py` with exactly:

```python
"""1071: the host is told at once when stay-fee collection is on and no guest pay way works."""
from __future__ import annotations

import pytest

from app import alerts, config, db, stay_fee

OWNER = "no-pay-way-1071"
IBAN = "CZ6508000000192000145399"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (OWNER,)):
        oid = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


@pytest.fixture
def flat():
    """A property that collects by bank transfer, with an operator that has no account yet."""
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "NoPayWay", "created_at": db.utcnow()})
    entity = db.insert("legal_entity", {"name": "NoPayWay s.r.o.", "owner_user_id": oid,
                                        "created_at": db.utcnow()})
    aid = db.insert("apartment", {
        "internal_name": "Loft 1071", "owner_user_id": oid, "legal_entity_id": entity,
        "addr_obec": "Praha", "stay_fee_rate_czk": 30, "stay_fee_collect": 1,
        "stay_fee_guest_rails": "iban", "permalink_token": "tok-1071",
        "created_at": db.utcnow()})
    try:
        yield {"apartment": aid, "entity": entity}
    finally:
        _cleanup()


def _key(aid):
    return f"stay_fee_no_pay_way:{aid}"


def _update(aid, **values):
    db.update("apartment", aid, values)


def test_the_alert_is_raised_at_once_when_the_only_way_has_no_account(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    row = alerts.open_alert(_key(aid))
    assert row is not None
    assert row["level"] == "warning" and row["kind"] == "stay_fee_no_pay_way"
    assert row["message"] == "Guests cannot pay the stay fee: add a bank account"


def test_raising_twice_keeps_one_open_alert(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    stay_fee.reconcile_no_pay_way_alert(aid)
    rows = db.query("SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (_key(aid),))
    assert len(rows) == 1


def test_it_resolves_itself_when_a_bank_account_is_added(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is not None
    db.update("legal_entity", flat["entity"], {"iban": IBAN})
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_it_resolves_itself_when_collection_is_turned_off(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    _update(aid, stay_fee_collect=0)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_cash_alone_is_a_working_way_so_there_is_no_alert(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_guest_rails="cash")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_revolut_without_a_link_does_not_work(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_guest_rails="revolut")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is not None
    _update(aid, stay_fee_guest_revolut_link="https://revolut.me/loft")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_guest_box_and_the_alert_share_one_rule(flat):
    aid = flat["apartment"]
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.usable_rail_keys(apartment) == []
    db.update("legal_entity", flat["entity"], {"iban": IBAN})
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.usable_rail_keys(apartment) == ["iban"]


def test_collection_on_with_rate_zero_raises_no_alert(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_collect=1, stay_fee_rate_czk=0)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_deployment_switch_off_means_no_alert(flat, monkeypatch):
    aid = flat["apartment"]
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_daily_sweep_raises_and_resolves(flat):
    aid = flat["apartment"]
    assert stay_fee.reconcile_all_no_pay_way() >= 1
    assert alerts.open_alert(_key(aid)) is not None
    _update(aid, stay_fee_collect=0)
    stay_fee.reconcile_all_no_pay_way()
    assert alerts.open_alert(_key(aid)) is None


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_card_reads_in_every_host_language_and_never_says_paid(flat, lang):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    card = alerts.present(dict(alerts.open_alert(_key(aid))), lang)
    shown = card["display_title"] + " " + card["display_detail"]
    assert "Loft 1071" in card["display_title"]
    assert "%(" not in shown and "notification." not in shown
    assert "paid" not in shown.lower()
    assert card["action_href"] == f"/apartments/{aid}?view=settings&section=reporting#stay-fee-settings"
    assert card["action_label_key"] == "notification.action.stay_fee_pay"
```

   b. In `App/tests/test_alert_language.py`, in `STORED_KINDS`, after the line `    "guest_pin_abuse": {},` add `    "stay_fee_no_pay_way": {"property": "Loft"},`.
   c. In `App/tests/test_layout_lint_browser.py`, function `test_every_host_page_passes_the_layout_lint`, replace

```python
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    findings: list[dict] = []
    report_only: list[dict] = []
    with sync_api.sync_playwright() as playwright:
```

with the same lines preceded by (so the new card is in the screenshots):

```python
    from app import alerts as _alerts
    _alerts.raise_alert(
        "warning", "stay_fee_no_pay_way", "Guests cannot pay the stay fee: add a bank account",
        dedupe_key=f"stay_fee_no_pay_way:{wide_host['configured_apartment']}",
        apartment_id=wide_host["configured_apartment"], params={"property": "Layout flat"},
    )
```

   If that exact five-line anchor appears more than once or not at all, STOP.
Command: `.venv/bin/python -m pytest tests/test_stay_fee_no_pay_way_1071.py tests/test_alert_language.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 failed (about 17 tests).

8. **No mail, no push.** Command: `grep -n "stay_fee_no_pay_way\|NO_PAY_WAY" app/mail_notify.py app/push.py app/scheduler.py app/mail.py | tail -30`. Expected: one hit, the `stay_fee.reconcile_all_no_pay_way()` call in `scheduler.py`; none in `mail_notify.py`, `push.py` or `mail.py`. Then `grep -n "raise_alert" app/push.py app/mail_notify.py | tail -30`. Expected: no output. If any of them handles the new kind, STOP.

9. **Test-map row.** In `docs/context/test-map.md` (from the repo root), directly after the line starting `| Cleaning |` add exactly:

```
| Alerts, notification cards | `test_alert*.py test_needs_you*.py test_host_alert_stack_browser.py test_design_alerts_phone.py` (browser files 0 skipped) |
```

Command: `grep -n "Alerts, notification cards" docs/context/test-map.md | tail -30`. Expected: one line. The files exist (checked: `test_alert_language.py`, `test_alert_stack.py`, `test_needs_you_0240.py`, `test_needs_you_dashboard_0241.py`, `test_host_alert_stack_browser.py`, `test_design_alerts_phone.py`).

10. **Run the map rows** (from `App/`, each `2>&1 | tail -30`, stop at the first failure):
   - `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_invoice_*.py -q --tb=short -x`
   - `.venv/bin/python -m pytest tests/test_alert*.py tests/test_needs_you*.py tests/test_host_alert_stack_browser.py tests/test_design_alerts_phone.py -q --tb=short -x` (browser files 0 skipped)
   - `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x` (0 skipped)
   - `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x`
   - `.venv/bin/python -m pytest tests/test_scheduler.py tests/test_design_guardrails_browser.py -q --tb=short -x` (0 skipped)

11. **UX gate.** From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: 1 passed, 0 skipped, zero findings. Open `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` for the pages that show the card (the dashboard `/` page and the property page of the configured apartment; take the names from the `ROUTES` map in the test) and write per page in the report: "390: ...; 768: ...; 1280: ...", saying what you saw of the card: title on one to three lines without clipping, the "Fix stay fee payment" action line under it, the dismiss cross reachable, no overlap with the next card, no sideways scroll. A finding is fixed, never silenced. Owner rule: every touched host page gets 390, 768 and 1280 px screenshots saved, and a reviewer looks at them by eye (the layout lint and geometry tests passing is not enough). Both must pass with 0 skipped, and the PR says per page what was seen. Copy the 390 px screenshots of those pages to `docs/tasks/screenshots-1071/` only if the report asks for them; otherwise name their `/tmp/shots` path.

## 5. Do not touch

`App/app/migrations/`, any template, any CSS or JS, `App/app/i18n.py` and the guest languages (guest side is out of scope), `go/`, `check_guest_pay_setup` and the pay-way settings page, `App/app/payment_request.py` (1068a owns it), `App/tests/static_versions.json`. Rules that apply: AGENTS.md 2 (no new personal data: the alert stores the property name only), 3, 4 (no dependency), 5 (SQL through `db.py` helpers), 9 (copy), 10 (UX gate). No em dash in any copy. No new outbound request.

## 6. Commands

All from `App/` unless marked; each ends `2>&1 | tail -30`. The commands are in §4 (steps 1-11; step 9 runs from the repo root). Final check from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (only status.md over its cap is acceptable).

## 7. Acceptance

- [ ] With collection on and no working way, `alerts.open_alert("stay_fee_no_pay_way:<id>")` is a `warning` row (step 7 tests green).
- [ ] The same alert resolves when an account is added, a Revolut link is added, cash is enabled, collection is turned off, or the deployment switch is off (tests green).
- [ ] Raised twice gives one open row (test green).
- [ ] The guest box and the alert call `stay_fee.usable_rail_keys`; `grep -n "RAIL_ORDER" app/routes/guest.py` prints nothing; `test_stay_fee_audit_1025.py` and `test_stay_fee_guest_pay_0897.py` pass unchanged.
- [ ] The card reads in en, cs and vi, contains no "paid", and links to `#stay-fee-settings` (parametrised test green).
- [ ] No mail or push code mentions the new kind (step 8 greps print no hit).
- [ ] No schema change: `git diff --stat` shows no `migrations/` file.
- [ ] Layout lint and geometry tests green, 0 skipped; 390/768/1280 screenshots saved and looked at by eye per touched page, and described per page; design-system checklist (docs/design/design-system.md section 5) ticked in the report.
- [ ] `python3 scripts/context_lint.py`: OK apart from the known status.md cap.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found verbatim (1068a may have changed the i18n or admin files; say which anchor);
- a test fails twice;
- the work seems to need a second alert kind or a schema change (the owner said stop and say so);
- you reach 40 tool calls or the checkpoint at 60k tokens (report as `blocked`, see executor.md; the 30-call cap is Haiku only, under the owner override);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1071-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked, with the per-page 390/768/1280 lines.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of: `App/app/stay_fee.py` (the shared rule: must equal the old inline rule, including the `qr` to `iban` mapping and the order), `App/app/routes/guest.py` `_fee_pay_panel` (the refactor must change nothing the guest sees), `App/app/routes/admin.py` (the two hooks), `App/app/scheduler.py` (the sweep sits inside the existing `try`).

## Owner steps

1. After the PR is green and reviewed, merge it with `scripts/merge-pr-on-green.sh`.
2. Deploy as usual. No setting, secret or migration is needed.
3. To see it: on a property that asks guests to pay, remove the operator's bank account (Business details), open the dashboard: the card "Guests cannot pay the stay fee" shows. Add the account again: the card disappears after the save.
