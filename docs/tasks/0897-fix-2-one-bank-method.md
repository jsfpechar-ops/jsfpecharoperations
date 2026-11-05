# 0897-fix-2: one bank method, no Automatic, audit the operator account

Status: replaced by 0959
Depends on: none. Do not run. The same host-side work is already on `claude/zealous-johnson-kjnz4e` in brief 0959 (commit 8ca3f9de).
Base: branch `cursor/guest-pay-operator-preview-237c`. Stay on it. Do not push. Do not open a PR.
Executor: Haiku | Report: docs/tasks/0897-fix-2-report.md

## 1. Objective

Owner decisions: the "Show first" list has no "Automatic" choice. There is one bank method, not a separate QR checkbox. Czech and Slovak guests get a QR above the IBAN; everyone else gets the IBAN only. A stored `qr` value is treated as `iban` with no migration. Saving a changed operator account writes an audit row and does not write the account number into the log.

## 2. Context

Anchors, verbatim today:

`App/app/routes/stay_fees.py` inside `guest_pay_values`:

```
    default_rail = _form_str(form, "stay_fee_guest_default_rail")
    if default_rail not in rails:
        default_rail = ""
```

`App/app/routes/stay_fees.py` inside `apply_guest_operator_account`, the update:

```
    db.update("legal_entity", entity_id, {"bank_account": bank_account, "iban": iban})
```

`App/app/routes/guest.py` inside `_fee_pay_panel`, the rail loop starts at `rails = []` and ends at the cash `rails.append`. `RAIL_ORDER = ("qr", "iban", "revolut", "cash")` sits above `_qr_offered`.

`App/app/templates/_stay_fee_fields.html` has a checkbox `value="qr"` and an option `stay_fees.guest_pay.default_auto`.

`App/app/static/stay-fee-guest-pay.js` sets `defaultRail.value = ""` when the selected method is unticked.

Order of ticked methods: iban, then revolut, then cash. `qr` is never stored after a save.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/stay_fees.py` | edit | normalise rails and default; audit account changes |
| `App/app/routes/guest.py` | edit | one iban rail, QR image only when `qr_ok` |
| `App/app/templates/_stay_fee_fields.html` | edit | one bank checkbox, no Automatic option |
| `App/app/templates/guest/_fee_pay.html` | edit | QR image sits inside the bank-transfer details |
| `App/app/static/stay-fee-guest-pay.js` | edit | select the first enabled method |
| `App/app/host_i18n.py` | edit | labels, drop `default_auto`, fix Vietnamese strings that are still English |
| `App/app/templates/_stay_fee_fields.html` | edit | script query `?v=20261105-gp4` |
| `App/tests/static_versions.json` | edit | via the version test `--write` |
| `App/tests/test_stay_fee_guest_pay_0897.py` | edit | expectations for stored `iban` and the audit row |
| `App/tests/test_guest_browser_e2e.py` | edit | three payment methods, QR inside bank transfer for CZE |
| `docs/tasks/0897-fix-2-report.md` | create | report |

`_stay_fee_fields.html` is one file. The version bump is part of step 3, not a second edit later.

## 4. Steps

1. `guest_pay_values` in `App/app/routes/stay_fees.py`. After the set of rails is built and sorted, if `"qr"` is in `rails`, discard it and add `"iban"`. Map a posted default of `qr` to `iban`. If the default is not in `rails`, set it to the first of `iban`, `revolut`, `cash` that is in `rails`, or `""` only when `rails` is empty. Replace the two-line anchor in section 2 with that logic. Do not sort the default away. Command: `cd App && .venv/bin/python -c "import app.routes.stay_fees" 2>&1 | tail -30`. Commit `0897-fix-2 step 1`.

2. Same file, `apply_guest_operator_account`. Read `before_account = entity["bank_account"] or ""` and `before_iban = entity["iban"] or ""` before the update. After a successful `normalise_account`, call `db.update` only when `bank_account` or `iban` differs from those two. When they differ, call `db.audit("operator_bank_account_changed", f"entity={entity_id}", owner_user_id=apartment.get("owner_user_id"))`. The detail string must not contain the account or the IBAN. Command: same import command as step 1. Commit `0897-fix-2 step 2`.

3. `App/app/routes/guest.py`. Change `RAIL_ORDER = ("qr", "iban", "revolut", "cash")` to `RAIL_ORDER = ("iban", "revolut", "cash")`. In `_fee_pay_panel`, before the loop: if `"qr"` is in `enabled`, discard it and add `"iban"`. If `first == "qr"`, set `first = "iban"`. Wrap the read of `stay_fee_guest_default_rail` so a missing column (`IndexError` or `KeyError`) yields `""` instead of a 500. In the loop, delete the `key == "qr"` branch. The `iban` branch, when `account` is set, appends `{"key": "iban", "iban": payments.format_iban(account), "qr": payments.qr_data_uri(payments.spayd(account, total, vs, message)) if qr_ok else ""}`. Revolut and cash stay as they are. Command: `cd App && .venv/bin/python -c "import app.routes.guest" 2>&1 | tail -30`. Commit `0897-fix-2 step 3`.

4. `App/app/templates/_stay_fee_fields.html`. Remove the checkbox whose value is `qr`. The bank checkbox value stays `iban`, and it is checked when `iban` or `qr` is in `guest_rails`. Put `<small class="muted gp-rail-note">{{ t('stay_fees.guest_pay.qr_note') }}</small>` inside that bank label. Delete the `<option value="">` that prints `default_auto`. The select lists only `iban`, `revolut`, `cash`. An option is disabled and hidden unless that method is ticked (`iban` counts as ticked when the stored rails contain `qr`). The selected option is the stored default when that method is ticked (`qr` stored as default counts as `iban`); otherwise the first ticked method in that order. Bump the script tag to `stay-fee-guest-pay.js?v=20261105-gp4`. Command: `cd App && .venv/bin/python -c "from app.templating import env; env.get_template('_stay_fee_fields.html')" 2>&1 | tail -30`. If that import path fails, `cd App && .venv/bin/python -c "import app.templating" 2>&1 | tail -30` and stop if you cannot find the Jinja environment. Commit `0897-fix-2 step 4`.

5. `App/app/templates/guest/_fee_pay.html`. Remove the `{% if rail.key == 'qr' %}` branch. In the `iban` branch, when `rail.qr` is non-empty, render the existing `g-fee-qr` image (same alt `fee_qr_alt`, width 176, height 176) above the `<dl>`. Keep the payee, IBAN, amount and variable symbol lines. Command: `cd App && grep -n "rail.key == 'qr'" App/app/templates/guest/_fee_pay.html | tail -5` (expect no hits). Commit `0897-fix-2 step 5`.

6. `App/app/static/stay-fee-guest-pay.js`, function `syncDefault`. After marking options disabled, if the current value is not an enabled rail, set it to the first enabled `option[data-rail]`. Do not set it to `""` while an enabled option exists. Commit `0897-fix-2 step 6` with no test yet.

7. `App/app/host_i18n.py`, the `_STAY_FEE_GUEST_PAY_STRINGS` dict only. Delete the three `stay_fees.guest_pay.default_auto` lines. Set these values:

- en `stay_fees.guest_pay.rail.iban`: `Bank transfer (IBAN)`
- cs `stay_fees.guest_pay.rail.iban`: `Bankovní převod (IBAN)`
- vi `stay_fees.guest_pay.rail.iban`: `Chuyển khoản ngân hàng (IBAN)`
- en `stay_fees.guest_pay.operator_account_label`: `IBAN`
- cs `stay_fees.guest_pay.operator_account_label`: `IBAN`
- vi `stay_fees.guest_pay.operator_account_label`: `IBAN`
- en `stay_fees.guest_pay.operator_account_help`: `A Czech account number also works, for example 19-2000145399/0800. Used on invoices. Saving changes the account for every property of this operator.`
- cs `stay_fees.guest_pay.operator_account_help`: `České číslo účtu také projde, například 19-2000145399/0800. Stejný účet je na fakturách. Uložení změní účet u všech nemovitostí tohoto provozovatele.`
- vi `stay_fees.guest_pay.operator_account_help`: `Số tài khoản Séc cũng được, ví dụ 19-2000145399/0800. Dùng trên hóa đơn. Lưu sẽ đổi tài khoản cho mọi chỗ ở của đơn vị này.`
- en `stay_fees.guest_pay.operator_invoice_note`: `This account is shared by every property of this operator, and by invoices.`
- cs `stay_fees.guest_pay.operator_invoice_note`: `Tento účet je společný pro všechny nemovitosti tohoto provozovatele a pro faktury.`
- vi `stay_fees.guest_pay.operator_invoice_note`: `Tài khoản này dùng chung cho mọi chỗ ở của đơn vị này và cho hóa đơn.`
- en `stay_fees.guest_pay.default_help`: `The method that opens first on the guest page.`
- cs `stay_fees.guest_pay.default_help`: `Způsob, který se na stránce hosta otevře jako první.`
- vi `stay_fees.guest_pay.default_help`: `Cách thanh toán mở đầu tiên trên trang của khách.`
- vi `stay_fees.guest_pay.preview_qr_alt`: `Mã QR thanh toán mẫu`
- vi `stay_fees.guest_pay.preview_sample_note`: `QR mẫu để kiểm tra (50 CZK hoặc giá mỗi đêm, ký hiệu 1234567890). Trên trang khách, số tiền và ký hiệu khớp với kỳ lưu trú.`
- vi `stay_fees.guest_pay.operator_change`: `Đổi tài khoản ngân hàng`
- en `flash.stay_fees.operator_account_required`: `Enter the IBAN guests should pay. A Czech account number also works.`
- cs `flash.stay_fees.operator_account_required`: `Zadejte IBAN, na který mají hosté platit. České číslo účtu také projde.`
- vi `flash.stay_fees.operator_account_required`: `Nhập IBAN để khách thanh toán. Số tài khoản Séc cũng được.`

No em dash. Leave `qr_note` as it is. Command: `cd App && .venv/bin/python -m pytest tests/test_no_em_dashes.py -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Commit `0897-fix-2 step 7`.

8. Tests. In `App/tests/test_stay_fee_guest_pay_0897.py`:
- `test_default_rail_is_saved_only_when_that_rail_is_enabled`: posting rails `qr` plus default `cash` stores default `iban` and rails that contain `iban` and do not contain `qr`.
- Posting rails `qr` and `revolut` with default `revolut` still stores default `revolut`.
- `test_qr_rail_saves_operator_account_on_legal_entity`: after the save, `SELECT action, detail FROM audit WHERE action = 'operator_bank_account_changed'` has one row, and `detail` does not contain `CZ65` or `2000145399`.
- `test_the_qr_option_says_it_is_for_czech_and_slovak_guests_only`: the sentence is still on the page, and the page has no checkbox `value="qr"` and no `Automatic`.
- The settings page for a property whose stored rails are `qr` shows the bank checkbox checked.

In `App/tests/test_guest_browser_e2e.py`:
- The CZE card has 3 `.g-fee-rail` blocks, not 4. The open one contains the QR image and the text `Bank transfer (IBAN)`.
- The GBR card has no `.g-fee-qr-img` and has 3 rails (bank, Revolut, cash).
- A default of `revolut` still opens Revolut first.

Then `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit the json if it changes. Command: `cd App && .venv/bin/python -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_stay_fee_obec_0898.py::test_charge_excludes_demo_unsigned_and_respects_the_kill_switch -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Browser, in tmux because it is slow: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -k fee -q --tb=short -p no:cacheprovider 2>&1 | tail -30`. Expect pass. `test_the_finish_card_passes_the_lint` is not in this command. Commit `0897-fix-2 step 8`.

9. Report `docs/tasks/0897-fix-2-report.md`. Set this brief `Status: review`. Commit `0897-fix-2 step 9`. Do not push.

## 5. Do not touch

`App/app/i18n.py`, `App/app/guest_uk_i18n.py`, `guest.css`, estimate copy, the legal question mark. Those belong to 0897-fix-3. Do not add a migration. Do not call `apply_account_payload`.

## 6. Commands

Section 4, then `python3 scripts/context_lint.py 2>&1 | tail -5` from the repo root.

## 7. Acceptance

- [ ] Settings HTML has no `default_auto` and no `value="qr"`.
- [ ] A posted rail `qr` is stored as `iban`. An invalid default becomes the first ticked method in order iban, revolut, cash.
- [ ] A Czech guest's card has the QR image inside bank transfer. A British guest's card has the IBAN and no QR image.
- [ ] Changing the operator account writes `operator_bank_account_changed` with no account number in `detail`. Saving the same account again does not add a second row.
- [ ] Vietnamese preview and invoice-note strings in this dict are not the English sentences.
- [ ] `test_stay_fee_guest_pay_0897.py` and the fee browser tests pass.

## 8. Stop and ask

An anchor is missing. A test fails twice. You need a migration. The bank checkbox would disappear for a property that only had `qr` stored.

## 9. Report

`docs/tasks/0897-fix-2-report.md`. Owner steps: none beyond the deploy note already in 0897-fix-1. Say that Postgres migration `App/migrations_pg/00007_stay_fee_guest_default_rail.sql` is still not applied on Lightsail, and production must not turn the flag on until the owner runs it.

## Risk list (reviewer)

Guest rail loop and `guest_pay_values`. Audit detail must not contain the IBAN.
