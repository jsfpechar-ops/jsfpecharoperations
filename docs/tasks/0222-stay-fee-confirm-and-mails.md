# 0222: One confirm step for button and job, plus the two stay-fee emails

Status: done
Depends on: 0220, 0221 | Base commit: ffacd5e + 0221 | Branch: claude/project-thread-9ov0nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [stay-fee-monthly-email](../plans/stay-fee-monthly-email.md) (brief 3 of 4)

## 1. Objective

The "Save period" button and the coming daily job (0223) must apply exactly the same checks before a period is sealed. Move those checks into `stay_fee_auto.check()`, add `stay_fee_auto.confirm()` for a clean period, and add the two mails: the finished report (PDF + QR + how to pay) and the "what to fix" notice.

## 2. Context

- Checks today, inline in `App/app/routes/stay_fees.py` `stay_fee_finalize` (~line 713): `period = stay_fee.property_period(apartment, calc_month, live_only=True, cadence=cadence, rate=...)`, `group = stay_fee.report_group(apartment, calc_month, live_only=True, period=period, cadence=cadence)`, `issues = stay_fee.report_issues(group, today)`, plus `"stay_fees.issue.unsigned"` when `stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"], period)`. Seal: `stay_fee_filing.save(apartment, group["first"], rate_czk=rate, collected=..., issued_on=today, cadence=group["cadence"], replacing_id=...)`; rate = `period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])`.
- Payment data: `stay_fee.payment_details(group)` needs `group["anchor"]` (the apartment), `group["vs"]`, `group["total_czk"]`; returns `None` without a council IBAN, else `{account, iban, iban_display, vs, spayd, ...}` (`spayd` empty when total is 0 or no VS). `stay_fee.format_czk(n)`.
- Period names in the host's language: copy the body of `_ui_period_label` (`routes/stay_fees.py:51`) into `stay_fee_auto.period_label(lang, cadence, month)` (keys `month.<n>`, `stay_fees.quarter`). Do not change `_ui_period_label` (PR #419 edits that file).
- Mail: `mail.enqueue(kind=, idempotency_key=, to_email=, subject=, payload=, apartment_id=, owner_user_id=)`; new kinds must go in `mail.KINDS` and `mail.HOST_KINDS` (`test_mail.py`-style guard). 0220 payload keys: `mail.STAY_FEE_FILING_KEY`, `mail.QR_SPAYD_KEY`, `mail.QR_CONTENT_ID`, optional `"attachment_name"`.
- Composer to copy: `mail_notify.build_workspace_deletion` (~line 929) and its queue function: `_text(lang, key, **kw)`, `_shell(lang=, title=, preheader=, blocks=, footer_lines=)`, `_button(url, label)`, `_public(path)`, `_esc`, recipient `_entity_contact_email(apartment["legal_entity_id"])`, language `host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)`.
- Keys go in `App/app/host_i18n.py` (`en`, `cs`) and `App/app/host_vi_i18n.py`, one block each next to the other `mail.*` keys. Placeholders use `%(name)s` like the existing mail keys.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee_auto.py` | edit | `period_label`, `check`, `confirm` |
| `App/app/routes/stay_fees.py` | edit | `stay_fee_finalize` uses `stay_fee_auto.check` (nothing else in the file) |
| `App/app/mail.py` | edit | two kinds |
| `App/app/mail_notify.py` | edit | builders + queue functions |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | keys below |
| `App/tests/test_stay_fee_auto.py` | new | tests below |

No other file may change.

## 4. Steps

1. `stay_fee_auto.py` add:
```python
def check(apartment, month, today, *, cadence=None, rate=None) -> dict:
    """Everything that blocks sealing ``month``. The button and the job both call this."""
    cadence = cadence or stay_fee.cadence_of(apartment)
    period = stay_fee.property_period(apartment, month, live_only=True, cadence=cadence, rate=rate)
    group = stay_fee.report_group(apartment, month, live_only=True, period=period, cadence=cadence)
    issues = stay_fee.report_issues(group, today)
    if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"], period):
        issues.append("stay_fees.issue.unsigned")
    return {"period": period, "group": group, "issues": issues,
            "key": stay_fee_filing.period_key(group["cadence"], group["first"])}


def confirm(apartment, month, today) -> Optional[int]:
    """Seal a clean period with the fee as calculated (job only). None when blocked or saved."""
    checked = check(apartment, month, today)
    if checked["issues"] or stay_fee_filing.latest(apartment["id"], checked["key"]):
        return None
    period, group = checked["period"], checked["group"]
    rate = period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])
    collected = {line["guest_id"]: line["amount_czk"] for line in (period or {}).get("lines") or []}
    try:
        filing_id = stay_fee_filing.save(apartment, group["first"], rate_czk=rate,
                                         collected=collected, issued_on=today,
                                         cadence=group["cadence"])
    except (ValueError, sqlite3.IntegrityError):
        return None
    db.audit("stay_fee_auto_finalize", f"apartment_id={apartment['id']} period={checked['key']}")
    return filing_id
```
   (imports: `sqlite3`, `Optional`, `stay_fee`, `stay_fee_filing`; match `db.audit` to how 0221 called it.)
2. `stay_fee_finalize`: replace the `period = ...` / `group = ...` / `issues = ...` / unsigned lines with `checked = stay_fee_auto.check(apartment, calc_month, today, cadence=cadence, rate=sealed["rate_czk"] if correcting else None)` and `period, group, issues = checked["period"], checked["group"], checked["issues"]`. Behaviour must stay identical; `tests/test_stay_fee_finalize.py` proves it.
3. `mail.py`: add `"stay_fee_report"` and `"stay_fee_blocked"` to `KINDS` and to `HOST_KINDS` with a `# 0222: monthly stay-fee email (plan stay-fee-monthly-email).` comment.
4. `mail_notify.py`, a `# --- stay-fee monthly email ---` section with:
   - `build_stay_fee_report(*, lang, property_name, period, amount, total_czk, authority, databox, account, vs, has_qr, report_url) -> {subject, text, html}`. Text and HTML from the same strings: intro, step 1 (with or without data box), step 2 (with QR / without QR) or the zero line when `total_czk == 0`, the fix line + button, footer line `mail.stay_fee.footer`. When `has_qr`, the HTML has `<img src="cid:stayfeeqr" width="200" height="200" alt="{qr_alt}">` right after step 2, and the text part says "(QR code attached)" via `mail.stay_fee.qr_alt`.
   - `queue_stay_fee_report(apartment, filing_row, lang=None) -> Optional[int]`: recipient `_entity_contact_email`; none → return None. `month = stay_fee_filing.period_anchor(filing_row)`; group-like dict `{"anchor": apartment, "vs": stay_fee.vs_of(apartment), "total_czk": filing_row["total_due_czk"]}` for `payment_details`; `report_url = _public(f"/stay-fees/{apartment['id']}?month={stay_fee.month_key(month)}")`. Payload: `text`, `html`, `lang`, `mail.STAY_FEE_FILING_KEY: filing_row["id"]`, `mail.QR_SPAYD_KEY: details["spayd"]` only when present. Key `f"stay_fee_report:{apartment['id']}:{filing_row['period_key']}:v{filing_row['version']}"`.
   - `build_stay_fee_blocked(*, lang, property_name, period, issues, report_url)` and `queue_stay_fee_blocked(apartment, group, issues, lang=None)`: issues rendered with `_text(lang, key)` as a list; key `f"stay_fee_blocked:{apartment['id']}:{stay_fee_filing.period_key(group['cadence'], group['first'])}"`.
5. Copy (exact; `%(x)s` placeholders):

| key | en | cs | vi |
|---|---|---|---|
| `mail.stay_fee.subject` | Stay fee for %(period)s: %(amount)s to pay – %(property)s | Poplatek z pobytu za %(period)s: k úhradě %(amount)s – %(property)s | Phí lưu trú kỳ %(period)s: cần trả %(amount)s – %(property)s |
| `mail.stay_fee.subject_zero` | Stay fee for %(period)s: nothing to pay – %(property)s | Poplatek z pobytu za %(period)s: nic k úhradě – %(property)s | Phí lưu trú kỳ %(period)s: không phải trả – %(property)s |
| `mail.stay_fee.intro` | Your stay fee report for %(period)s at %(property)s is confirmed. It is attached as a PDF. | Hlášení poplatku z pobytu za %(period)s pro %(property)s je potvrzené. Najdete ho v příloze jako PDF. | Báo cáo phí lưu trú kỳ %(period)s cho %(property)s đã được xác nhận và đính kèm dưới dạng PDF. |
| `mail.stay_fee.step_send` | 1. Send the PDF to %(authority)s (data box %(databox)s). | 1. Pošlete PDF úřadu %(authority)s (datová schránka %(databox)s). | 1. Gửi tệp PDF cho %(authority)s (hộp dữ liệu %(databox)s). |
| `mail.stay_fee.step_send_plain` | 1. Send the PDF to %(authority)s. | 1. Pošlete PDF úřadu %(authority)s. | 1. Gửi tệp PDF cho %(authority)s. |
| `mail.stay_fee.step_pay` | 2. Pay %(amount)s to account %(account)s, variable symbol %(vs)s. Scan the QR code in your bank app and it fills this in for you. | 2. Zaplaťte %(amount)s na účet %(account)s, variabilní symbol %(vs)s. Naskenujte QR kód v aplikaci banky a údaje se vyplní samy. | 2. Thanh toán %(amount)s vào tài khoản %(account)s, mã biến số (VS) %(vs)s. Quét mã QR bằng ứng dụng ngân hàng để tự điền thông tin. |
| `mail.stay_fee.step_pay_plain` | 2. Pay %(amount)s to the council's account, variable symbol %(vs)s. | 2. Zaplaťte %(amount)s na účet obce, variabilní symbol %(vs)s. | 2. Thanh toán %(amount)s vào tài khoản của chính quyền địa phương, mã biến số (VS) %(vs)s. |
| `mail.stay_fee.zero` | Nothing to pay this period. Some councils still want the report, so send it if yours does. | Za toto období se nic neplatí. Některé obce hlášení chtějí i tak, proto ho pošlete, pokud to vaše obec vyžaduje. | Kỳ này không phải trả gì. Một số địa phương vẫn muốn nhận báo cáo, vì vậy hãy gửi nếu nơi bạn yêu cầu. |
| `mail.stay_fee.qr_alt` | QR code for the payment (attached) | QR kód k platbě (v příloze) | Mã QR thanh toán (đính kèm) |
| `mail.stay_fee.fix` | Something wrong? Open the report, correct it, and we will email you the new version. | Něco nesedí? Otevřete hlášení, opravte ho a novou verzi vám pošleme e-mailem. | Có gì sai? Mở báo cáo, sửa lại và chúng tôi sẽ gửi email phiên bản mới cho bạn. |
| `mail.stay_fee.open` | Open the report | Otevřít hlášení | Mở báo cáo |
| `mail.stay_fee.footer` | You get this email because "Stay fee report by email" is on in Settings. | Tento e-mail dostáváte, protože máte v Nastavení zapnuté „Hlášení poplatku z pobytu e-mailem“. | Bạn nhận email này vì mục "Báo cáo phí lưu trú qua email" đang bật trong Cài đặt. |
| `mail.stay_fee_blocked.subject` | Stay fee for %(period)s needs your help – %(property)s | Poplatek z pobytu za %(period)s potřebuje doplnit – %(property)s | Phí lưu trú kỳ %(period)s cần bạn bổ sung – %(property)s |
| `mail.stay_fee_blocked.intro` | We could not confirm the stay fee report for %(period)s at %(property)s yet, because: | Hlášení poplatku za %(period)s pro %(property)s zatím nemůžeme potvrdit, protože: | Chúng tôi chưa thể xác nhận báo cáo phí lưu trú kỳ %(period)s cho %(property)s, vì: |
| `mail.stay_fee_blocked.after` | Fix this on the report page. We check again every morning and email you the finished report as soon as nothing is missing. | Opravte to na stránce hlášení. Každé ráno to znovu zkontrolujeme a hotové hlášení vám pošleme, jakmile nic nebude chybět. | Hãy sửa trên trang báo cáo. Mỗi sáng chúng tôi kiểm tra lại và gửi báo cáo hoàn chỉnh ngay khi không còn thiếu gì. |

   Before adding, grep that `settings.account.stay_fee_emails` (0221) has the same title as quoted in `mail.stay_fee.footer`; if 0221 changed it, quote the actual title.
6. Tests `test_stay_fee_auto.py` (fixture: copy from `tests/test_stay_fee_finalize.py`, which builds a fee property with a finished month):
   - `check` on a clean finished month → no issues; on the running month → `stay_fees.issue.period_running`.
   - `confirm` seals once (row in `stay_fee_filing`, audit `stay_fee_auto_finalize`), second call returns None.
   - `queue_stay_fee_report` with `UBYHOST_MAIL_BACKEND=console` (see how `test_ses_mail.py`/`test_lifecycle_mail.py` enable mail): one outbox row, kind `stay_fee_report`, payload has the filing id and no PDF bytes; repeated call gives the same id. With a council IBAN + VS set, payload has `qr_spayd` and the HTML has `cid:stayfeeqr`.
   - Zero total → subject uses `subject_zero` and no `qr_spayd`.
   - `queue_stay_fee_blocked` lists the translated issue text; same key twice → one row.
   - CS and VI builds return non-empty subject/text/html (no missing-key fallback).

## 5. Do not touch

Anything else in `routes/stay_fees.py`, the stay-fee bank fields, templates, CSS. No scheduler change (0223). No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee_auto.py tests/test_stay_fee_finalize.py tests/test_mail_attachments.py tests/test_notification_copy.py -q --tb=short -x 2>&1 | tail -30`
Then the mail row of the test-map: `.venv/bin/python -m pytest tests/test_ses_mail.py $(ls tests/test_mail_*.py tests/test_*_mail.py) -q --tb=line 2>&1 | tail -15`, plus `ls tests | grep -i i18n` (run those).
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] All above pass; `test_stay_fee_finalize.py` unchanged and green.
- [ ] Report pastes the EN text part of one built report mail.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

Write `docs/tasks/0222-report.md` (600 tokens at most), set `Status: review`.

## Risk list (for the reviewer)

`stay_fee_finalize` diff (must be behaviour-neutral), `stay_fee_auto.confirm`, the idempotency keys.

## Owner steps

None.

## Addendum (orchestrator, after the first run was blocked)

The first run applied §4 steps 1-6; do not redo them. Finish with:

7. `App/tests/test_claim_mail.py`: add `"stay_fee_report"` and `"stay_fee_blocked"` to the pinned kinds set in `test_the_registered_mail_kinds_are_the_ones_the_app_can_send` (add only, change nothing else).
8. Add next to `notification.mail_kind.door_code_notice` in each dict:

| key | en | cs | vi |
|---|---|---|---|
| `notification.mail_kind.stay_fee_report` | monthly stay fee report | měsíční hlášení poplatku z pobytu | báo cáo phí lưu trú hằng tháng |
| `notification.mail_kind.stay_fee_blocked` | stay fee report that needs fixing | hlášení poplatku, které je třeba doplnit | báo cáo phí lưu trú cần bổ sung |

9. Run the §6 mail row again. If `test_no_outbox_code_ever_reaches_the_card[stay_fee_*]` still fails, read that test and fix the cause in the files of §3 only; else stop.
