# 0413: Billing invoices (B2): numbering, PDF, storno, mail, 10-year purge

Status: review
Depends on: 0411 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0413-billing-invoices
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

UbyHost issues its own invoices to hosts: `UBY-{year}-{0001}` numbers, VS = year + 4 digits, a stored PDF from the existing `invoice_pdf.render`, storno, "paid" marking, a Czech service e-mail with the PDF attached, and the 10-year purge. Nothing calls this yet (the jobs brief does), and billing stays off.

Invoices only: nothing for cards or a payment gateway.

## 2. Context

You copy two finished files from `docs/plans/billing-0413/` and make small anchored edits. Do not retype the copied files.

- `billing_invoices.py` uses `billing.account/quote` (0411), `invoice_pdf.render`, `operator.details`, `invoices.retention_cutoff`, `validation.fmt_date_range`, and the `platform_invoice*` / `bank_payment` tables from `0023_billing.sql`.
- The new mail kind `billing_invoice` is host service mail (not a lifecycle tip). `tests/test_claim_mail.py` pins the set of kinds, so this brief edits that set.
- Mail rule: a file is attached at send time from a payload key, never stored in the outbox (see `STAY_FEE_FILING_KEY` in `mail.py`).

**Excerpt A**, `App/app/mail.py` (lines 64–68, end of `KINDS`; the same two lines end `HOST_KINDS` at 110–113):

```python
    # 0319: Havel support hand-off and the AI budget warning, both to the operator.
    "havel_support",
    "ai_budget",
)
```

**Excerpt B**, `App/app/mail.py` (lines 342–344):

```python
STAY_FEE_FILING_KEY = "stay_fee_filing_id"
QR_SPAYD_KEY = "qr_spayd"
QR_CONTENT_ID = "stayfeeqr"
```

**Excerpt C**, `App/app/mail.py` (in `attachments`, lines 361–362):

```python
    spayd = str(payload.get(QR_SPAYD_KEY) or "")
    if spayd:
```

**Excerpt D**, `App/app/mail_notify.py` (end of `ai_budget`, lines 2593–2600):

```python
    return mail.enqueue(
        kind="ai_budget",
        idempotency_key=f"ai-budget-{feature}-{month}",
        to_email=config.OPERATOR_EMAIL,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": HOST_MAIL_LANGUAGE},
    )
```

**Excerpt E**, `App/app/host_i18n.py`: `"mail.ai_budget.action": "Open Operations",` (line 5142) and `"mail.ai_budget.action": "Otevřít Provoz",` (line 5319).

**Excerpt F**, `App/app/retention.py` (lines 44–47 and STEPS line 468):

```python
def _run_invoice_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    if dry_run:
        return len(invoices.expired_ids(today, owner_user_id=owner_user_id))
    return invoices.purge_expired(today, owner_user_id=owner_user_id)
```
```python
    ("invoices", _run_invoice_step),
```

**Excerpt G**, `App/tests/test_claim_mail.py` (end of the pinned set, about line 1840):

```python
        # 0319: the Havel support hand-off and the AI budget warning, both to the operator.
        "havel_support",
        "ai_budget",
    }
```

If any excerpt is not found verbatim (line numbers may drift a little), STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0024_platform_invoice_pdf.sql` | create | two PDF columns |
| `App/app/billing_invoices.py` | create | copy of `docs/plans/billing-0413/billing_invoices.py` |
| `App/app/mail.py` | edit | kind `billing_invoice`, PDF attachment |
| `App/app/mail_notify.py` | edit | `build_billing_invoice`, `billing_invoice` |
| `App/app/host_i18n.py` | edit | 3 keys EN, 3 keys CS |
| `App/app/retention.py` | edit | `platform_invoices` purge step |
| `App/tests/test_claim_mail.py` | edit | pinned kinds |
| `App/tests/test_billing_invoices.py` | create | copy of `docs/plans/billing-0413/test_billing_invoices.py` |
| `docs/privacy/RETENTION.md` | edit | name the purge step |
| `docs/tasks/0413-report.md` | create | the report |

No other file may change.

## 4. Steps

### Step 1. Migration

Create `App/app/migrations/0024_platform_invoice_pdf.sql`:

```sql
-- Brief 0413: the PDF of each UbyHost invoice, stored once at issue and never re-rendered.
ALTER TABLE platform_invoice ADD COLUMN pdf_blob BLOB;
ALTER TABLE platform_invoice ADD COLUMN pdf_sha256 TEXT;
```

### Step 2. Copy the module and the tests

```bash
cp docs/plans/billing-0413/billing_invoices.py App/app/billing_invoices.py
cp docs/plans/billing-0413/test_billing_invoices.py App/tests/test_billing_invoices.py
```

### Step 3. `App/app/mail.py`

3a. In `KINDS` (first copy of Excerpt A), add after `"ai_budget",`:

```python
    # 0413: UbyHost's own invoice to a host, PDF attached (service mail).
    "billing_invoice",
```

3b. In `HOST_KINDS` (second copy of Excerpt A), add the same two lines after `"ai_budget",`.

3c. After Excerpt B add:

```python
PLATFORM_INVOICE_KEY = "platform_invoice_id"
```

3d. Directly before Excerpt C (inside `attachments`) add:

```python
    platform_invoice_id = payload.get(PLATFORM_INVOICE_KEY)
    if platform_invoice_id:
        from . import billing_invoices

        data = billing_invoices.pdf_bytes(int(platform_invoice_id))
        name = str(payload.get("attachment_name") or f"faktura-{platform_invoice_id}.pdf")
        parts.append({"filename": name, "maintype": "application", "subtype": "pdf",
                      "data": data, "cid": None})
```

### Step 4. `App/app/mail_notify.py`

After Excerpt D (the end of `ai_budget`), add:

```python


def build_billing_invoice(*, number: str, vs: str, amount_czk: int, due: str, period: str) -> Dict[str, str]:
    lang = "cs"  # UbyHost invoices a Czech host in Czech
    amount = f"{amount_czk:,}".replace(",", " ")
    subject = _text(lang, "mail.billing_invoice.subject", number=number)
    body = _text(lang, "mail.billing_invoice.body", number=number, amount=amount,
                 period=period, due=_fmt_date(due), vs=vs)
    action = _text(lang, "mail.billing_invoice.action")
    link = _app("/predplatne")
    footer = _signup_footer(lang)
    text = "\n".join([body, "", f"{action}: {link}", "", "--", *footer])
    blocks = [_block_heading(subject), _block_paragraph(body), _block_button(link, action)]
    return {"subject": subject, "text": text,
            "html": _shell(lang=lang, title=subject, preheader=body, blocks=blocks, footer_lines=footer)}


def billing_invoice(
    *, invoice_id: int, to_email: str, owner_user_id: int, number: str, vs: str,
    amount_czk: int, due: str, period: str,
) -> Optional[int]:
    """One mail per invoice (key billing-invoice-<id>); the PDF is attached at send time."""
    content = build_billing_invoice(number=number, vs=vs, amount_czk=amount_czk, due=due, period=period)
    return mail.enqueue(
        kind="billing_invoice",
        idempotency_key=f"billing-invoice-{invoice_id}",
        to_email=to_email,
        subject=content["subject"],
        owner_user_id=owner_user_id,
        payload={
            "text": content["text"],
            "html": content["html"],
            "lang": "cs",
            "reply_to": config.OPERATOR_EMAIL,
            mail.PLATFORM_INVOICE_KEY: invoice_id,
            "attachment_name": f"{number}.pdf",
        },
    )
```

### Step 5. `App/app/host_i18n.py`

After the EN line of Excerpt E add:

```python
        "mail.billing_invoice.subject": "Invoice %(number)s from UbyHost",
        "mail.billing_invoice.body": "Here is invoice %(number)s for %(amount)s CZK for %(period)s, due on %(due)s, variable symbol %(vs)s. The invoice is attached; its QR payment code is inside.",
        "mail.billing_invoice.action": "Open your plan",
```

After the CS line of Excerpt E add:

```python
        "mail.billing_invoice.subject": "Faktura %(number)s od UbyHost",
        "mail.billing_invoice.body": "Posíláme fakturu %(number)s na %(amount)s Kč za období %(period)s se splatností %(due)s, variabilní symbol %(vs)s. Faktura je v příloze, QR Platba je přímo v ní.",
        "mail.billing_invoice.action": "Otevřít předplatné",
```

### Step 6. `App/app/retention.py`

After the `_run_invoice_step` function (Excerpt F) add:

```python


def _platform_invoice_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Brief 0413: UbyHost's own invoices and bank payments, 10 years (§ 35 zákon 235/2004 Sb.).

    They are UbyHost's records, not a workspace's, so a one-workspace run skips them.
    """
    from . import billing_invoices

    if owner_user_id is not None:
        return 0
    if dry_run:
        return len(billing_invoices.expired_ids(today))
    return billing_invoices.purge_expired(today)
```

In `STEPS`, after `("invoices", _run_invoice_step),` add `    ("platform_invoices", _platform_invoice_step),`.

### Step 7. `App/tests/test_claim_mail.py`

In the pinned set (Excerpt G), after `"ai_budget",` add:

```python
        # 0413: UbyHost's own invoice to a host.
        "billing_invoice",
```

### Step 8. `docs/privacy/RETENTION.md`

In the row that starts `| UbyHost's own invoices to hosts`, replace `10-year purge step comes with the billing-invoices brief, first due 2037` with `` `retention.py` `platform_invoices` step (`billing_invoices.purge_expired`), first due 2037``.

### Step 9. Run §6, write the report, set `Status: review`, commit.

## 5. Do not touch

`invoice_pdf.py`, `invoices.py`, `billing.py`, `0023_billing.sql`, the host's guest-invoice code. No new dependency.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_invoices.py tests/test_billing_core.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_claim_mail.py tests/test_mail.py tests/test_ses_mail.py -q --tb=short -x 2>&1 | tail -30`
3. `.venv/bin/python -m pytest tests/test_retention.py tests/test_retention_job.py tests/test_retention_alignment.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] All commands pass.
- [ ] `git diff --stat` shows only the §3 files.
- [ ] No string `stripe`, `gopay`, `comgate` or `card` in `billing_invoices.py`.

## 8. Stop and ask

- An excerpt is not found.
- A test in command 2 or 3 fails for a reason outside this brief (for example another test pins the mail kinds or retention steps).
- A test in `test_billing_invoices.py` fails twice: report the failing assertion and the last 30 lines. Do not change the copied files beyond one obvious typo fix, and name it under Deviations.

## 9. Report

`docs/tasks/0413-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- `issue()` renders the PDF inside the write transaction: the lock is held for the render (tens of ms).
- A paid invoice cannot be cancelled here; refunds stay manual.
