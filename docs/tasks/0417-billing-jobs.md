# 0417: Billing jobs (B5): new periods, invoices, apartment counts, dunning

Status: todo
Depends on: 0413, 0414, 0416 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0417-billing-jobs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The daily `billing` job (06:00, from 0414) runs `billing_jobs.run()`:

1. **Trials.** The 0414 trial run.
2. **New periods.** A period that has ended rolls into the next one, applying the change that was waiting. A cancelled plan pauses instead.
3. **Invoices.** The current period's invoice is issued and mailed once.
4. **Apartment counts.** More active apartments than billed are billed from today; on a yearly plan that means a supplementary invoice. Fewer apartments count from the next period.
5. **Dunning.** A reminder goes out 1 day and 7 days after the due date (the account turns `overdue`). After 14 days the account is read-only (`paused`), with one mail.
6. **Payment.** `settle()` puts a paid account back to `active`; the ČSOB brief calls it.

One host's failure never stops the run. UbyPort reporting does not depend on any of this.

## 2. Context

You copy two finished files from `docs/plans/billing-0417/` and make small anchored edits. All mail is Czech service mail.

**Excerpt A**, `App/app/scheduler.py` (from 0414):

```python
def _job_billing() -> None:
    """UbyHost's own billing, daily at 06:00 (0414): trials. Nothing while billing is off."""
    from . import billing_trial

    started = time.perf_counter()
    try:
        counts = billing_trial.run()
```

**Excerpt B**, `App/app/mail.py`: the two lines below appear twice (end of `KINDS` and end of `HOST_KINDS`):

```python
    # 0414: trial reminders, 7 and 3 days before the end and on the last day.
    "billing_trial",
```

**Excerpt C**, `App/app/mail_notify.py` (end of `billing_trial`):

```python
        payload={"text": content["text"], "html": content["html"], "lang": "cs",
                 "reply_to": config.OPERATOR_EMAIL},
    )
```

**Excerpt D**, `App/app/host_i18n.py`: `"mail.billing_trial.action": "Choose a plan",` and `"mail.billing_trial.action": "Vybrat plán",`.

**Excerpt E**, `App/tests/test_claim_mail.py`:

```python
        # 0414: the trial reminders.
        "billing_trial",
```

If any excerpt is not found verbatim (and once, except B), STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/billing_jobs.py` | create | copy of `docs/plans/billing-0417/billing_jobs.py` |
| `App/app/scheduler.py` | edit | the job runs `billing_jobs.run()` |
| `App/app/mail.py` | edit | kind `billing_overdue` |
| `App/app/mail_notify.py` | edit | `build_billing_overdue`, `billing_overdue` |
| `App/app/host_i18n.py` | edit | 6 keys EN, 6 keys CS |
| `App/tests/test_claim_mail.py` | edit | pinned kinds |
| `App/tests/test_billing_jobs.py` | create | copy |
| `docs/tasks/0417-report.md` | create | the report |

## 4. Steps

### Step 1. Copy

```bash
cp docs/plans/billing-0417/billing_jobs.py App/app/billing_jobs.py
cp docs/plans/billing-0417/test_billing_jobs.py App/tests/test_billing_jobs.py
```

### Step 2. `scheduler.py`

In Excerpt A make three replacements: the docstring becomes `"""UbyHost's own billing, daily at 06:00 (0414, 0417): trials, periods, invoices, dunning."""`, `from . import billing_trial` becomes `from . import billing_jobs`, and `counts = billing_trial.run()` becomes `counts = billing_jobs.run()`.

### Step 3. Mail

3a. `mail.py`: after **each** copy of Excerpt B add:

```python
    # 0417: payment reminders 1 and 7 days after the due date, and the read-only notice.
    "billing_overdue",
```

3b. `mail_notify.py`: after Excerpt C add:

```python


def build_billing_overdue(*, stage: str, number: str, amount_czk: int, due: str, today: str) -> Dict[str, str]:
    lang = "cs"  # UbyHost bills Czech hosts in Czech
    amount = f"{amount_czk:,}".replace(",", " ")
    subject = _text(lang, f"mail.billing_overdue.subject_{stage}", number=number)
    body = _text(lang, "mail.billing_overdue.body_" + ("paused" if stage == "paused" else "reminder"),
                 number=number, amount=amount, due=_fmt_date(due), date=_fmt_date(today))
    action = _text(lang, "mail.billing_overdue.action")
    link = _app("/predplatne")
    footer = _signup_footer(lang)
    text = "\n".join([body, "", f"{action}: {link}", "", "--", *footer])
    blocks = [_block_heading(subject), _block_paragraph(body), _block_button(link, action)]
    return {"subject": subject, "text": text,
            "html": _shell(lang=lang, title=subject, preheader=body, blocks=blocks, footer_lines=footer)}


def billing_overdue(
    *, invoice_id: int, owner_user_id: int, stage: str, number: str, amount_czk: int, due: str, today: str,
) -> Optional[int]:
    """One mail per invoice and stage (reminder, second, paused). Service mail, not a tip."""
    from . import billing_invoices

    content = build_billing_overdue(stage=stage, number=number, amount_czk=amount_czk, due=due, today=today)
    return mail.enqueue(
        kind="billing_overdue",
        idempotency_key=f"billing-overdue-{invoice_id}-{stage}",
        to_email=billing_invoices.recipient(owner_user_id),
        subject=content["subject"],
        owner_user_id=owner_user_id,
        payload={"text": content["text"], "html": content["html"], "lang": "cs",
                 "reply_to": config.OPERATOR_EMAIL},
    )
```

3c. `test_claim_mail.py`: after Excerpt E add:

```python
        # 0417: payment reminders and the read-only notice.
        "billing_overdue",
```

### Step 4. Copy keys, `host_i18n.py`

After the EN line of Excerpt D add:

```python
        "mail.billing_overdue.subject_reminder": "Invoice %(number)s is overdue",
        "mail.billing_overdue.subject_second": "Reminder: invoice %(number)s",
        "mail.billing_overdue.subject_paused": "Your UbyHost account is read-only",
        "mail.billing_overdue.body_reminder": "Invoice %(number)s for %(amount)s CZK was due on %(due)s and we have not received the payment yet. If you have already paid, please ignore this e-mail. The invoice and its QR payment code are on your plan page.",
        "mail.billing_overdue.body_paused": "We had not received payment for invoice %(number)s for %(amount)s CZK by %(date)s, so the account is now read-only. Guests who have already filled in their details are still reported to the police. The account opens again once the invoice is paid.",
        "mail.billing_overdue.action": "Open your plan",
```

After the CS line of Excerpt D add:

```python
        "mail.billing_overdue.subject_reminder": "Faktura %(number)s je po splatnosti",
        "mail.billing_overdue.subject_second": "Připomínka: faktura %(number)s",
        "mail.billing_overdue.subject_paused": "Účet UbyHost je jen pro čtení",
        "mail.billing_overdue.body_reminder": "Faktura %(number)s na %(amount)s Kč byla splatná %(due)s a platbu jsme zatím nepřijali. Pokud jste už zaplatili, tento e-mail prosím ignorujte. Fakturu i QR Platbu najdete v přehledu předplatného.",
        "mail.billing_overdue.body_paused": "Platbu faktury %(number)s na %(amount)s Kč jsme do %(date)s nepřijali, proto je účet jen pro čtení. Hosty, kteří už vyplnili údaje, cizinecké policii hlásíme dál. Po zaplacení se účet znovu otevře.",
        "mail.billing_overdue.action": "Otevřít předplatné",
```

### Step 5. Run §6, write the report, `Status: review`, commit.

## 5. Do not touch

`billing.py`, `billing_invoices.py`, `billing_trial.py`, `billing_order.py`, `reporting.py`, templates, CSS.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_jobs.py tests/test_billing_trial.py tests/test_billing_order.py tests/test_billing_invoices.py tests/test_billing_core.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_claim_mail.py tests/test_ses_mail.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] All commands pass.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- An excerpt is not found.
- A copied test fails twice: report the assertion and the last 30 lines. One obvious typo fix in a copied file is allowed; name it under Deviations.

## 9. Report

`docs/tasks/0417-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- Monthly plans are not prorated: an apartment added mid-month is billed from the next invoice.
- A period that starts on the 29th–31st moves to the 1st after a short month (`billing_trial.period_end`).
- The run catches up one period per day if the server was down for longer.
