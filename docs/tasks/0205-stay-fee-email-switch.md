# 0205: On/off switch for the monthly stay-fee email

Status: done
Depends on: none (0204 may land first) | Base commit: 2f043c8 | Branch: claude/project-thread-9ov0nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [stay-fee-monthly-email](../plans/stay-fee-monthly-email.md) (brief 2 of 4)

## 1. Objective

From 0207 on, UbyHost confirms each complete stay-fee period on the 2nd day after it ends and emails the operator the PDF and QR. Add the host's switch for it (on by default) in Settings, and one short status line on the Stay fees list, so a host who prefers to do it by hand can turn it off.

## 2. Context

- Model to copy: the onboarding-tips switch. Column `user_account.onboarding_emails_opt_out`; route `App/app/routes/admin_accounts.py:320` `onboarding_emails_submit`; settings context `App/app/routes/admin.py` `_onboarding_emails(request)` (returns True/False, None when hidden) passed as `"onboarding_emails"` (~line 4349); template `App/app/templates/settings.html:50` form `#settings-onboarding-emails`.
- Schema change = a new file `App/app/migrations/0011_stay_fee_emails.sql` (run `python3 scripts/context_lint.py` first; if it names another free number, use that). Style of `0009_stay_fee_send.sql`: plain `ALTER TABLE ... ADD COLUMN`. Never edit `db.SCHEMA` / `db.ADDED_COLUMNS`.
- A fee property: `stay_fee.is_active(apartment)` = `stay_fee_rate_czk > 0`.
- Copy rules: novice-first, say why; "no tracking cookies" rule does not apply here. Keys in `App/app/host_i18n.py` (`en` and `cs` dicts) and `App/app/host_vi_i18n.py`. PR #419 also edits these files; add your keys as one block next to the `settings.account.onboarding_emails*` keys and do not reorder anything.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0011_stay_fee_emails.sql` | new | two columns |
| `App/app/stay_fee_auto.py` | new | read/write helpers |
| `App/app/routes/admin_accounts.py` | edit | POST `/account/stay-fee-emails` |
| `App/app/routes/admin.py` | edit | `_stay_fee_emails(request)` + context key |
| `App/app/routes/stay_fees.py` | edit | pass `stay_fee_emails` to the list template only (do not touch `stay_fee_finalize`) |
| `App/app/templates/settings.html` | edit | one form row after the onboarding row |
| `App/app/templates/stay_fees.html` | edit | one status line under `#fee-list-summary` |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | keys below |
| `App/app/retention.py` | edit | only if `onboarding_emails_opt_out` is listed there: add the two new columns the same way |
| `App/tests/test_stay_fee_email_switch.py` | new | tests below |

No other file may change.

## 4. Steps

1. Migration:
```sql
ALTER TABLE user_account ADD COLUMN stay_fee_emails_opt_out INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_account ADD COLUMN stay_fee_emails_opt_out_at TEXT;
```
2. `App/app/stay_fee_auto.py`:
```python
"""Monthly stay-fee email (plan: docs/plans/stay-fee-monthly-email.md).

0205: the host's switch. 0206/0207 add the shared confirm step and the daily job.
"""
from __future__ import annotations

from . import db


def emails_enabled(user_id: int) -> bool:
    row = db.query_one("SELECT stay_fee_emails_opt_out FROM user_account WHERE id = ?", (user_id,))
    return bool(row) and not row["stay_fee_emails_opt_out"]


def set_emails_enabled(user_id: int, enabled: bool, *, actor: str) -> None:
    db.execute(
        "UPDATE user_account SET stay_fee_emails_opt_out = ?, stay_fee_emails_opt_out_at = ? "
        "WHERE id = ?",
        (0 if enabled else 1, None if enabled else db.utcnow(), user_id),
    )
    db.audit("stay_fee_emails_on" if enabled else "stay_fee_emails_off", f"user_id={user_id} by={actor}")


def workspace_has_fee_property(user_id: int) -> bool:
    row = db.query_one(
        "SELECT 1 AS n FROM apartment WHERE owner_user_id = ? AND archived_at IS NULL "
        "AND COALESCE(stay_fee_rate_czk, 0) > 0 LIMIT 1",
        (user_id,),
    )
    return bool(row)
```
   Check `db.execute` and `db.audit` signatures in `db.py` first (grep `^def execute\|^def audit`); adapt the call, not the meaning.
3. Route in `admin_accounts.py`, a copy of `onboarding_emails_submit` with: path `/account/stay-fee-emails`, `stay_fee_auto.set_emails_enabled(...)`, flash keys `flash.accounts.stay_fee_emails_on` / `_off`, back to `/settings#settings-stay-fee-emails`.
4. `admin.py`: `_stay_fee_emails(request)` = same guards as `_onboarding_emails`, and also `None` when `not stay_fee_auto.workspace_has_fee_property(account["id"])`; else `stay_fee_auto.emails_enabled(account["id"])`. Add `"stay_fee_emails": _stay_fee_emails(request)` next to `"onboarding_emails"`.
5. `settings.html`: copy the onboarding form block right after it, with `id="settings-stay-fee-emails"`, action `/account/stay-fee-emails`, `{% if stay_fee_emails is not none %}`, keys `settings.account.stay_fee_emails`, `_help`, `_save`. No JavaScript (the form posts; rule 6).
6. `stay_fees.py` list route (`stay_fees_list`): add `"stay_fee_emails": stay_fee_auto.emails_enabled(<workspace owner id>)` to the template context (use the same owner id the route already uses for its queries). `stay_fees.html`: directly after the `#fee-list-summary` paragraph:
```jinja
<p class="ui-sub" id="fee-list-email">{{ t('stay_fees.list.email_on' if stay_fee_emails else 'stay_fees.list.email_off') }} <a href="/settings#settings-stay-fee-emails">{{ t('stay_fees.list.email_change') }}</a></p>
```
7. Copy (exact):

| key | en | cs | vi |
|---|---|---|---|
| `settings.account.stay_fee_emails` | Stay fee report by email | Hlášení poplatku z pobytu e-mailem | Báo cáo phí lưu trú qua email |
| `settings.account.stay_fee_emails_help` | On the 2nd day after each fee period ends, we confirm the report if nothing is missing and email the PDF and payment QR code to your business address. You only forward the PDF to the council and pay. Untick this to confirm each period yourself on the Stay fees page. | Druhý den po skončení každého období hlášení potvrdíme, pokud nic nechybí, a pošleme PDF a QR kód k platbě na e-mail vaší firmy. Vy jen přepošlete PDF obci a zaplatíte. Když políčko odškrtnete, potvrdíte každé období sami na stránce Poplatek z pobytu. | Vào ngày thứ 2 sau khi mỗi kỳ phí kết thúc, nếu không thiếu gì, chúng tôi xác nhận báo cáo và gửi tệp PDF cùng mã QR thanh toán đến email doanh nghiệp của bạn. Bạn chỉ cần chuyển tiếp PDF cho chính quyền địa phương và thanh toán. Bỏ chọn nếu bạn muốn tự xác nhận từng kỳ trên trang Phí lưu trú. |
| `settings.account.stay_fee_emails_save` | Save | Uložit | Lưu |
| `flash.accounts.stay_fee_emails_on` | We will email you each stay fee report. | Hlášení poplatku vám budeme posílat e-mailem. | Chúng tôi sẽ gửi email cho bạn mỗi báo cáo phí lưu trú. |
| `flash.accounts.stay_fee_emails_off` | Stay fee emails are off. Confirm each period on the Stay fees page. | E-maily s hlášením jsou vypnuté. Každé období potvrďte na stránce Poplatek z pobytu. | Đã tắt email phí lưu trú. Hãy tự xác nhận từng kỳ trên trang Phí lưu trú. |
| `stay_fees.list.email_on` | Complete reports are emailed to you on the 2nd day after each period. | Úplná hlášení vám pošleme e-mailem 2. den po skončení období. | Báo cáo đầy đủ được gửi qua email cho bạn vào ngày thứ 2 sau mỗi kỳ. |
| `stay_fees.list.email_off` | Stay fee emails are off. | E-maily s hlášením jsou vypnuté. | Email phí lưu trú đang tắt. |
| `stay_fees.list.email_change` | Change in Settings | Změnit v Nastavení | Thay đổi trong Cài đặt |

   If the page is called something else in a language (grep the nav label key for `/stay-fees`), use that name instead of "Stay fees / Poplatek z pobytu / Phí lưu trú".
8. Tests `test_stay_fee_email_switch.py` (copy the client/login fixture from `tests/test_stay_fee_list.py`): default is on; POST without `enabled` turns it off and sets `_at`; POST `enabled=1` turns it on; the Settings row is hidden for a host with no fee property and shown with one; the list line text matches the state.
9. Screenshots with the shared tool (it seeds demo data; read its docstring with `head -15`):
`cd App && .venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app "$PWD" --out /mnt/project-files/design-reset/stay-fee-email/ --pages /settings,/stay-fees --widths 390,1280,2000 2>&1 | tail -15`, then once more with `--lang cs` into `.../stay-fee-email/cs/` and `--lang vi` into `.../stay-fee-email/vi/` (if `vi` is refused, say so in the report). Open the 390 shots and check the new row and line wrap cleanly.

## 5. Do not touch

`stay_fee_finalize`, the stay-fee bank/account fields, any CSS (no CSS should be needed; if it is, stop). No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee_email_switch.py tests/test_stay_fee_list.py tests/test_lifecycle_mail.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
Any i18n parity test: `ls tests | grep -i i18n` and run those too.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] Tests pass; lint OK.
- [ ] Screenshots of `/settings` and `/stay-fees` at 390/1280/2000 (sidebar open and collapsed) in EN, CS, VI saved; `report.json` shows no new problems on those pages.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

Write `docs/tasks/0205-report.md` (600 tokens at most), set `Status: review`.

## Risk list (for the reviewer)

Migration file, `admin_accounts.py` route guard, `settings.html`.

## Owner steps

None (the migration runs on start).
