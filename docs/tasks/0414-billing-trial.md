# 0414: Billing trial (B3): start, reminders, end, the billing line on host pages

Status: review
Report: docs/tasks/0414-billing-trial-report.md
Depends on: 0411, 0413 | Base commit: the head of `claude/billing-phase1-impl` | Branch: task/0414-billing-trial
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The 30-day trial:

- **Start.** A new host's trial starts when UbyPort is verified (a passed connection test or a guest already reported), or 7 days after they confirm their e-mail, whichever comes first.
- **Reminders.** Czech service e-mails go out 7 and 3 days before the end and on the last day, unless the host has already ordered a plan.
- **End.** The account becomes active on the ordered plan, or paused when no plan was ordered.
- **Billing line.** Host pages show one line for trial, overdue, paused or canceling. While billing is off, and for "OG" hosts with no `billing_account` row, nothing changes.

## 2. Context

You copy three finished files from `docs/plans/billing-0414/` and make small anchored edits.

- `billing_trial.py` uses `billing.*` (0411), `validation.fmt_date`, and the `apartment.ubyport_verified_at` column (0023).
- `mail_notify.billing_trial` (step 4) uses `billing_invoices.recipient` (0413).
- Paused means read-only, but guests already registered are still reported (`Entitlements.ubyport_submit` is always True). The copy says so.
- UbyPort rule: this brief does not touch the filing code (`reporting.py`, `ubyport/`). The connection-test route only gets one extra call after its success audit line.

**Excerpt A**, `App/app/signup.py` (in `activate`, line 600):

```python
    db.audit("signup_verified", actor=account["username"], owner_user_id=account["id"])
```

**Excerpt B**, `App/app/routes/admin.py` (in `test_connection`, lines 2929–2933):

```python
    db.audit(
        "ubyport_connection_ok",
        f"apartment={apartment_id} endpoint={client.endpoint} "
        f"available={available} max_batch={limit}",
    )
```

**Excerpt C**, `App/app/scheduler.py` (lines 466–469 after drift, in `start`):

```python
    _scheduler.add_job(
        _job_stay_fee_mail, "cron", hour=7, minute=0, id="stay_fee_mail",
        max_instances=1, coalesce=True,
    )
```

and the function `def _job_stay_fee_mail() -> None:` (line 391).

**Excerpt D**, `App/app/templating.py`:

```python
def _template_door_codes_enabled() -> bool:
    from . import ttlock

    return ttlock.enabled()
```

and `templates.env.globals["door_codes_enabled"] = _template_door_codes_enabled` (line 476).

**Excerpt E**, `App/app/templates/base.html` (line 54):

```
    {% if not hide_alert_stack | default(false) %}{% include "_host_alerts.html" %}{% endif %}
```

**Excerpt F**, `App/app/mail.py`: the two lines below appear twice (end of `KINDS` and end of `HOST_KINDS`):

```python
    # 0413: UbyHost's own invoice to a host, PDF attached (service mail).
    "billing_invoice",
```

**Excerpt G**, `App/app/mail_notify.py` (end of `billing_invoice`):

```python
            mail.PLATFORM_INVOICE_KEY: invoice_id,
            "attachment_name": f"{number}.pdf",
        },
    )
```

**Excerpt H**, `App/app/host_i18n.py`: `"mail.billing_invoice.action": "Open your plan",` and `"mail.billing_invoice.action": "Otevřít předplatné",`.

**Excerpt I**, `App/tests/test_claim_mail.py` (pinned set):

```python
        # 0413: UbyHost's own invoice to a host.
        "billing_invoice",
```

If any excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/billing_trial.py` | create | copy of `docs/plans/billing-0414/billing_trial.py` |
| `App/app/signup.py` | edit | billing row on e-mail confirmation |
| `App/app/routes/admin.py` | edit | connection test marks the apartment verified |
| `App/app/scheduler.py` | edit | daily `billing` job |
| `App/app/templating.py` | edit | `billing_banner` global |
| `App/app/templates/_billing_banner.html` | create | the billing line |
| `App/app/templates/base.html` | edit | include it |
| `App/app/mail.py` | edit | kind `billing_trial` |
| `App/app/mail_notify.py` | edit | `build_billing_trial`, `billing_trial` |
| `App/app/host_i18n.py` | edit | 13 keys EN, 13 keys CS |
| `App/tests/test_claim_mail.py` | edit | pinned kinds |
| `App/tests/test_billing_trial.py` | create | copy from `docs/plans/billing-0414/` |
| `App/tests/test_0414_billing_banner_browser.py` | create | copy from `docs/plans/billing-0414/` |
| `docs/tasks/screenshots-0414/dashboard-390.png` | create | the screenshot |
| `docs/tasks/0414-billing-trial-report.md` | create | the report |

## 4. Steps

### Step 1. Copy

```bash
cp docs/plans/billing-0414/billing_trial.py App/app/billing_trial.py
cp docs/plans/billing-0414/test_billing_trial.py App/tests/test_billing_trial.py
cp docs/plans/billing-0414/test_0414_billing_banner_browser.py App/tests/test_0414_billing_banner_browser.py
```

### Step 2. `signup.py` and `routes/admin.py`

After Excerpt A add:

```python
    # 0414: a confirmed sign-up gets its billing row; the trial clock starts later.
    from . import billing

    if billing.enabled():
        billing.ensure_account(int(account["id"]))
```

After Excerpt B add:

```python
    # 0414: a passed test is the verified UbyPort connection that starts the trial.
    from .. import billing_trial

    billing_trial.mark_verified(apartment_id, apartment["owner_user_id"])
```

### Step 3. `scheduler.py`

Directly before `def _job_stay_fee_mail() -> None:` add:

```python
def _job_billing() -> None:
    """UbyHost's own billing, daily at 06:00 (0414): trials. Nothing while billing is off."""
    from . import billing_trial

    started = time.perf_counter()
    try:
        counts = billing_trial.run()
    except Exception:
        log.exception("billing run failed")
        _job_failed("billing")
        _log_run("billing", started, False)
        return
    _job_ok("billing")
    _log_run("billing", started, True, counts)


```

After Excerpt C add:

```python
    _scheduler.add_job(
        _job_billing, "cron", hour=6, minute=0, id="billing",
        max_instances=1, coalesce=True,
    )
```

### Step 4. Mail

4a. `mail.py`: after **each** of the two copies of Excerpt F add:

```python
    # 0414: trial reminders, 7 and 3 days before the end and on the last day.
    "billing_trial",
```

4b. `mail_notify.py`: after Excerpt G add:

```python


def build_billing_trial(*, days_left: int, ends: str) -> Dict[str, str]:
    lang = "cs"  # UbyHost bills Czech hosts in Czech
    subject = _text(lang, f"mail.billing_trial.subject_{days_left}")
    body = _text(lang, "mail.billing_trial.body", date=_fmt_date(ends))
    action = _text(lang, "mail.billing_trial.action")
    link = _app("/predplatne")
    footer = _signup_footer(lang)
    text = "\n".join([body, "", f"{action}: {link}", "", "--", *footer])
    blocks = [_block_heading(subject), _block_paragraph(body), _block_button(link, action)]
    return {"subject": subject, "text": text,
            "html": _shell(lang=lang, title=subject, preheader=body, blocks=blocks, footer_lines=footer)}


def billing_trial(*, owner_user_id: int, days_left: int, ends: str) -> Optional[int]:
    """One reminder per stage (key billing-trial-<owner>-<end>-<days>). Service mail, not a tip."""
    from . import billing_invoices

    content = build_billing_trial(days_left=days_left, ends=ends)
    return mail.enqueue(
        kind="billing_trial",
        idempotency_key=f"billing-trial-{owner_user_id}-{ends}-{days_left}",
        to_email=billing_invoices.recipient(owner_user_id),
        subject=content["subject"],
        owner_user_id=owner_user_id,
        payload={"text": content["text"], "html": content["html"], "lang": "cs",
                 "reply_to": config.OPERATOR_EMAIL},
    )
```

4c. `test_claim_mail.py`: after Excerpt I add:

```python
        # 0414: the trial reminders.
        "billing_trial",
```

### Step 5. Copy keys, `host_i18n.py`

After the EN line of Excerpt H add:

```python
        "mail.billing_trial.subject_7": "Your UbyHost trial ends in 7 days",
        "mail.billing_trial.subject_3": "Your UbyHost trial ends in 3 days",
        "mail.billing_trial.subject_0": "Your UbyHost trial ends today",
        "mail.billing_trial.body": "Your UbyHost trial ends on %(date)s. Choose a plan before then and everything carries on. Without a plan the account becomes read-only; guests who have already filled in their details are still reported to the police.",
        "mail.billing_trial.action": "Choose a plan",
        "billing.banner.trial": "Your trial ends on %(date)s.",
        "billing.banner.overdue": "An invoice is overdue. Pay it to keep the account active.",
        "billing.banner.paused": "The account is read-only. Guests already registered are still reported.",
        "billing.banner.canceling": "Your plan ends on %(date)s.",
        "billing.banner.action_trial": "Choose a plan",
        "billing.banner.action_overdue": "Pay the invoice",
        "billing.banner.action_paused": "Choose a plan",
        "billing.banner.action_canceling": "Keep my plan",
```

After the CS line of Excerpt H add:

```python
        "mail.billing_trial.subject_7": "Zkušební doba UbyHost končí za 7 dní",
        "mail.billing_trial.subject_3": "Zkušební doba UbyHost končí za 3 dny",
        "mail.billing_trial.subject_0": "Zkušební doba UbyHost dnes končí",
        "mail.billing_trial.body": "Zkušební doba UbyHost končí %(date)s. Když si do té doby vyberete plán, vše poběží dál bez přerušení. Bez plánu půjde účet jen prohlížet; hosty, kteří už vyplnili údaje, ale cizinecké policii ohlásíme dál.",
        "mail.billing_trial.action": "Vybrat plán",
        "billing.banner.trial": "Zkušební doba končí %(date)s.",
        "billing.banner.overdue": "Faktura je po splatnosti. Zaplaťte ji, ať účet zůstane aktivní.",
        "billing.banner.paused": "Účet je jen pro čtení. Už zaregistrované hosty hlásíme dál.",
        "billing.banner.canceling": "Předplatné končí %(date)s.",
        "billing.banner.action_trial": "Vybrat plán",
        "billing.banner.action_overdue": "Zaplatit fakturu",
        "billing.banner.action_paused": "Vybrat plán",
        "billing.banner.action_canceling": "Ponechat předplatné",
```

### Step 6. The billing line

6a. `templating.py`: after the function in Excerpt D add:

```python


def _template_billing_banner(owner_user_id):
    """0414: the one billing line for host pages, or None (billing off, OG host)."""
    from . import billing_trial

    return billing_trial.banner(owner_user_id)
```

After the line `templates.env.globals["door_codes_enabled"] = _template_door_codes_enabled` add:

```python
templates.env.globals["billing_banner"] = _template_billing_banner
```

6b. Create `App/app/templates/_billing_banner.html`:

```
{#- 0414: one billing line (trial, overdue, paused, canceling). Nothing while billing is off or for OG hosts. -#}
{% set billing_line = billing_banner(workspace_user.id if workspace_user else None) %}
{% if billing_line %}
<aside class="banner {{ 'warning' if billing_line.warning }} billing-banner" role="status" data-billing-banner="{{ billing_line.kind }}">
  <div class="grow"><strong>{{ t('billing.banner.' ~ billing_line.kind, date=billing_line.date) }}</strong></div>
  <a class="btn small" href="/predplatne">{{ t('billing.banner.action_' ~ billing_line.kind) }}</a>
</aside>
{% endif %}
```

6c. `base.html`: directly before Excerpt E add the line `    {% include "_billing_banner.html" %}`.

### Step 7. Run §6, take the screenshot, write the report, `Status: review`, commit.

## 5. Do not touch

`reporting.py`, `ubyport/`, `billing.py`, `billing_invoices.py`, any CSS (the line reuses `.banner`). No new dependency.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_billing_trial.py tests/test_billing_core.py tests/test_billing_invoices.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_claim_mail.py tests/test_ses_mail.py tests/test_signup.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`
3. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_0414=1 .venv/bin/python -m pytest tests/test_0414_billing_banner_browser.py tests/test_dashboard_phone_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped)
4. `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short 2>&1 | tail -30`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] All commands pass, 0 skipped in command 3.
- [ ] `docs/tasks/screenshots-0414/dashboard-390.png` exists; look at it once: the line sits under the top bar, nothing scrolls sideways.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

- An excerpt is not found.
- A test outside the new files fails because of a pinned list (mail kinds, scheduler jobs, i18n keys): report it, do not edit that test beyond step 4c.
- A copied test fails twice: report the assertion and the last 30 lines.

## 9. Report

`docs/tasks/0414-billing-trial-report.md`: files changed, the last 5 lines of each command, §7 ticked, Deviations, Questions.

## Risk list (for the reviewer)

- The billing line asks the database once per host page view (one primary-key read) while billing is on.
- `period_end` moves a period that starts on the 29th–31st to the 1st after a short month.
