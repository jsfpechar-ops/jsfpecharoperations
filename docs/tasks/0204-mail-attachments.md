# 0204: Mail outbox can send a PDF and an inline QR image

Status: done
Depends on: none | Base commit: 2f043c8 | Branch: claude/project-thread-9ov0nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [stay-fee-monthly-email](../plans/stay-fee-monthly-email.md) (brief 1 of 4)

## 1. Objective

The monthly stay-fee mail (0206/0207) must carry the sealed PDF as an attachment and the payment QR as an inline image (Gmail blocks `data:` images). Teach `app/mail.py` to build those parts at send time from a reference in the payload, so the outbox never stores file bytes.

## 2. Context

- `App/app/mail.py` `_send_ses(row)` sends through SES v1 `send_email` (or v2 `Content.Simple` when `list_unsubscribe_headers` returns headers). `_send_console(row)` writes `console_mail_log` and logs one line. `_deliver(row)` retries on any exception.
- Payload is JSON in `email_outbox.payload`. The outbox is purged after 14 days.
- Sealed filing: `stay_fee_filing.pdf_bytes(row)` decrypts the stored PDF (`App/app/stay_fee_filing.py:71`). Row: `SELECT * FROM stay_fee_filing WHERE id = ?`.
- QR: `payments.qr_png_bytes(spayd_string) -> bytes` (`App/app/payments.py:153`).
- No new dependency: use the standard library `email.message.EmailMessage` (policy `email.policy.SMTP`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/mail.py` | edit | `attachments(row, payload)`, raw MIME send, console note |
| `App/tests/test_mail_attachments.py` | new | tests below |

No other file may change.

## 4. Steps

1. In `mail.py`, add near `delivery_html`:

```python
# 0204: files built at send time from a reference in the payload. The outbox
# never holds file bytes; a row whose file is gone fails and retries like any
# other send error.
STAY_FEE_FILING_KEY = "stay_fee_filing_id"
QR_SPAYD_KEY = "qr_spayd"
QR_CONTENT_ID = "stayfeeqr"


def attachments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """``[{filename, maintype, subtype, data, cid}]``; ``cid`` set = inline image."""
    parts: List[Dict[str, Any]] = []
    filing_id = payload.get(STAY_FEE_FILING_KEY)
    if filing_id:
        from . import stay_fee_filing

        row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (int(filing_id),))
        data = stay_fee_filing.pdf_bytes(row) if row else b""
        if not data:
            raise MailConfigError("stay fee filing PDF is missing")
        name = str(payload.get("attachment_name") or f"poplatek-z-pobytu-{row['period_key']}.pdf")
        parts.append({"filename": name, "maintype": "application", "subtype": "pdf",
                      "data": data, "cid": None})
    spayd = str(payload.get(QR_SPAYD_KEY) or "")
    if spayd:
        from . import payments

        parts.append({"filename": "qr-platba.png", "maintype": "image", "subtype": "png",
                      "data": payments.qr_png_bytes(spayd), "cid": QR_CONTENT_ID})
    return parts
```

2. Add `_raw_message(row, payload, body, html, reply_to, headers, parts) -> bytes`: an `EmailMessage(policy=email.policy.SMTP)` with `From` = `display_from()`, `To`, `Cc` (when set), `Subject`, `Reply-To` (when set), each `headers` item as a header; `set_content(body)`; when `html`: `add_alternative(html, subtype="html")`, then for each part with a `cid`, `get_payload()[1].add_related(data, maintype, subtype, cid=f"<{cid}>", filename=...)`; then for each part without `cid`, `add_attachment(data, maintype=, subtype=, filename=)`. Return `msg.as_bytes()`.
3. In `_send_ses`, after `headers = list_unsubscribe_headers(row, payload)`: `parts = attachments(payload)`. If `parts`, send `_sesv2_client().send_email(FromEmailAddress=display_from(), Destination=destination, Content={"Raw": {"Data": _raw_message(...)}})` and skip the other two branches. Keep the existing branches unchanged otherwise.
4. In `_send_console`: call `parts = attachments(payload)` after `delivery_html(payload)` (so a missing file fails the same way as SES). When `parts`, append `"\n\n[Attachments: " + ", ".join(p["filename"] for p in parts) + "]"` to the stored `body_text`, and add `attachments=%d` to the log line.
5. Tests in `test_mail_attachments.py` (copy the db/config fixture setup from `tests/test_ses_mail.py`; monkeypatch `stay_fee_filing.pdf_bytes` and the `stay_fee_filing` row lookup, or insert a minimal row if the fixture makes that easy):
   - SES path with a filing id and a spayd: a fake `_sesv2_client` captures kwargs; parse `Content.Raw.Data` with `email.message_from_bytes(..., policy=email.policy.default)`; assert one `application/pdf` part with the filename, one `image/png` part with `Content-ID: <stayfeeqr>`, a text and an HTML part, and the Reply-To header.
   - Payload without either key: v1 `send_email` is still used (no Raw).
   - Missing filing: `_send_ses` raises `MailConfigError`.
   - Console backend: `console_mail_log.body_text` ends with the attachment note.

## 5. Do not touch

`enqueue`, `KINDS`, the claim-secret and door-code logic, any template, i18n file or route. No new dependency. No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_mail_attachments.py tests/test_ses_mail.py tests/test_mail_failed_alert.py -q --tb=short -x 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] New tests pass; `test_ses_mail.py` still passes unchanged.
- [ ] `git diff --stat` shows only the two files in §3.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

Write `docs/tasks/0204-report.md` (600 tokens at most), set `Status: review`.

## Risk list (for the reviewer)

`App/app/mail.py` (`_send_ses` branch order; no PDF bytes in `email_outbox`).

## Owner steps

1. After deploy to staging, trigger one stay-fee mail (0207) and look at it in your inbox.
2. If the log shows `AccessDenied` for the send, open AWS IAM, find the UbyHost SES user's policy, and add the action `ses:SendRawEmail` next to `ses:SendEmail`.
