# 0070: Door-code host mails: a true "late" mail, plain reasons that name TTLock

Status: todo
Depends on: 0069 (run it first; both edit the same files, on different lines) | Base commit: 0e8e468 | Branch: task/0070-door-code-host-mails
Executor: Cursor local agent (composer) | Fits one session

## 1. Objective

Five minutes after the last guest registers without a code, the host gets the "failed" mail, which says "UbyHost will not try again". That is false at that point: the code is still retrying. The host then makes their own code and the guest gets two mails. This brief gives that case its own mail. It also rewrites the failure reasons so a layman reads the real cause, and so TTLock is named when the failure is on TTLock's side (cloud not answering, gateway offline, access removed, lock memory full, monthly limit).

## 2. Context

- Owner decision 2026-10-12: when TTLock is the cause, the mail says so in plain words. When the cause is a UbyHost setting (no lock, no check-in hour, bad period), the mail says that instead, never TTLock.
- The late mail goes out only while the code is still `pending`, `issuing` or `retrying` (`door_codes._alert_delayed`). For a stay that can never get a code (`not_set_up`, `not_eligible`, `bad_window`), the "failed" text stays, because nothing is retried.
- Reasons come from `door_code.last_error`: `kind` or `kind:code` (kinds in `ttlock.ERROR_KINDS`), sometimes prefixed `period_taken:`. The raw token stays in brackets for support.
- Rule 9. No template, CSS, guest-page or schema change. English and Czech only (host mails).

Anchor A, `App/app/mail_notify.py`, found verbatim once:

```python
_DOOR_CODE_REASONS = ("waiting", "not_set_up", "no_account", "not_eligible", "bad_window")


def _door_code_reason(lang: str, reason: str) -> str:
    """The reason as a sentence a host can act on, with the raw token for support."""
    key = reason if reason in _DOOR_CODE_REASONS else "other"
```

Anchor B, `App/app/mail_notify.py`, in `door_code_delayed_notice`, found verbatim once:

```python
        subject = _text(lang, "mail.door_code_notice.failed.subject", **params)
        body = _text(lang, "mail.door_code_notice.failed.body", **params)
        payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}
        return mail.enqueue(
            kind="door_code_notice",
            idempotency_key=f"door_code_notice:stay{reservation_id}:delayed",
```

Anchor C, `App/app/host_i18n.py`, `en`, found verbatim once each:

```python
        "mail.door_code_notice.failed.body": "We are sorry: UbyHost could not create the door code for the stay from %(date)s. Reason: %(reason)s. UbyHost support has been told. Please create a code in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost will not try again, so the guest gets only your code. The guest was not told about the problem.",
        "mail.door_code_reason.waiting": "UbyHost is still waiting for TTLock to create it",
```

```python
        "mail.door_code_reason.other": "TTLock refused or did not answer",
```

Anchor D, `App/app/host_i18n.py`, `cs`, found verbatim once each:

```python
        "mail.door_code_notice.failed.body": "Omlouváme se: UbyHost nemohl vytvořit kód ke dveřím pro pobyt od %(date)s. Důvod: %(reason)s. Podpora UbyHost o tom ví. Vytvořte prosím kód v aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) a pošlete ho hostovi. UbyHost to už znovu nezkusí, host tedy dostane jen váš kód. Host o problému neví.",
        "mail.door_code_reason.waiting": "UbyHost stále čeká, až TTLock kód vytvoří",
```

```python
        "mail.door_code_reason.other": "TTLock kód odmítl nebo neodpověděl",
```

Anchor E, `App/tests/test_door_codes_safeguards.py`, found verbatim once each:

```python
from app import config, db, deadlines, door_codes, ttlock
```

```python
    assert "TTLock refused or did not answer [transient:-1026]" in body
```

If any anchor is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/mail_notify.py` | edit | Steps 1, 2 |
| `App/app/host_i18n.py` | edit | Steps 3, 4 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 5 |

No other file may change.

## 4. Steps

1. `mail_notify.py`: replace anchor A with:

```python
_DOOR_CODE_REASONS = (
    "waiting",
    "not_set_up",
    "no_account",
    "not_eligible",
    "bad_window",
    "cloud",
    "offline",
    "permission",
    "storage",
    "budget",
)
# TTLock error kinds (ttlock.ERROR_KINDS) as the reason a host reads.
_DOOR_CODE_REASON_KINDS = {
    "transient": "cloud",
    "network": "cloud",
    "rate": "cloud",
    "auth": "cloud",
    "offline": "offline",
    "permission": "permission",
    "reauth": "no_account",
    "storage": "storage",
    "budget": "budget",
}
# Reasons where nothing is retried: the late mail keeps the "failed" text.
_DOOR_CODE_NO_RETRY = ("not_set_up", "not_eligible", "bad_window")


def _door_code_reason(lang: str, reason: str) -> str:
    """The reason as a sentence a host can act on, with the raw token for support."""
    parts = reason.split(":")
    kind = parts[1] if parts[0] == "period_taken" and len(parts) > 1 else parts[0]
    key = _DOOR_CODE_REASON_KINDS.get(kind, kind)
    if key not in _DOOR_CODE_REASONS:
        key = "other"
```

(The two lines after it, `text = ...` and `return f"{text} [{reason}]"`, stay.)

2. `mail_notify.py`: replace anchor B with:

```python
        variant = "failed" if (reason or "waiting") in _DOOR_CODE_NO_RETRY else "delayed"
        subject = _text(lang, f"mail.door_code_notice.{variant}.subject", **params)
        body = _text(lang, f"mail.door_code_notice.{variant}.body", **params)
        payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}
        return mail.enqueue(
            kind="door_code_notice",
            idempotency_key=f"door_code_notice:stay{reservation_id}:delayed",
```

3. `host_i18n.py`, `en`: replace the two lines of the first anchor C block with these, in this order:

```python
        "mail.door_code_notice.failed.body": "We are sorry: the door code for the stay from %(date)s could not be created. Reason: %(reason)s. UbyHost support has a copy of this e-mail. Please create a code in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost will not try again, so the guest gets only your code. The guest was not told about the problem.",
        "mail.door_code_notice.delayed.subject": "%(property)s: the door code for the stay from %(date)s is late",
        "mail.door_code_notice.delayed.body": "The guests of the stay from %(date)s have registered, but their door code is not ready yet. Reason: %(reason)s. UbyHost keeps trying and e-mails the code to the guest as soon as TTLock creates it. If the guest arrives soon, you can create a code in the TTLock app (open the lock, tap Passcodes) and send it to them. If UbyHost's code arrives later, both codes work. UbyHost support has a copy of this e-mail.",
        "mail.door_code_reason.waiting": "TTLock's cloud has not created the code yet",
        "mail.door_code_reason.cloud": "TTLock's cloud server is not responding or returned an error. This is a problem on TTLock's side, not with your lock or your settings",
        "mail.door_code_reason.offline": "TTLock could not reach the lock, because the TTLock gateway at the property (the small box that connects the lock to the internet) is offline. Check that it has power and Wi-Fi",
        "mail.door_code_reason.permission": "TTLock no longer lets UbyHost manage this lock. Share the lock with UbyHost again as Authorized Admin in the TTLock app",
        "mail.door_code_reason.storage": "TTLock reports that the lock's memory is full. Delete old passcodes in the TTLock app",
        "mail.door_code_reason.budget": "TTLock's monthly limit of requests has been reached. It resets at the start of next month",
```

Then replace the second anchor C line with:

```python
        "mail.door_code_reason.other": "TTLock's cloud refused the request or did not answer",
```

4. `host_i18n.py`, `cs`: replace the two lines of the first anchor D block with:

```python
        "mail.door_code_notice.failed.body": "Omlouváme se: kód ke dveřím pro pobyt od %(date)s se nepodařilo vytvořit. Důvod: %(reason)s. Podpora UbyHost má kopii tohoto e-mailu. Vytvořte prosím kód v aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) a pošlete ho hostovi. UbyHost to už znovu nezkusí, host tedy dostane jen váš kód. Host o problému neví.",
        "mail.door_code_notice.delayed.subject": "%(property)s: kód ke dveřím pro pobyt od %(date)s se zpožďuje",
        "mail.door_code_notice.delayed.body": "Hosté pobytu od %(date)s se zaregistrovali, ale jejich kód ke dveřím ještě není hotový. Důvod: %(reason)s. UbyHost to zkouší dál a pošle kód hostovi e-mailem, jakmile ho TTLock vytvoří. Pokud host brzy dorazí, můžete vytvořit kód v aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) a poslat mu ho. Pokud kód od UbyHost přijde později, budou fungovat oba. Podpora UbyHost má kopii tohoto e-mailu.",
        "mail.door_code_reason.waiting": "cloud TTLock kód zatím nevytvořil",
        "mail.door_code_reason.cloud": "server cloudu TTLock neodpovídá nebo vrátil chybu. Jde o problém na straně TTLock, ne o váš zámek ani vaše nastavení",
        "mail.door_code_reason.offline": "TTLock se nemohl spojit se zámkem, protože brána TTLock v ubytování (malá krabička, která připojuje zámek k internetu) je offline. Zkontrolujte, že má proud a Wi-Fi",
        "mail.door_code_reason.permission": "TTLock už UbyHost nedovoluje tento zámek spravovat. V aplikaci TTLock zámek UbyHost znovu nasdílejte jako pověřenému správci",
        "mail.door_code_reason.storage": "TTLock hlásí, že paměť zámku je plná. Smažte staré kódy v aplikaci TTLock",
        "mail.door_code_reason.budget": "byl vyčerpán měsíční limit požadavků u TTLock. Obnoví se na začátku příštího měsíce",
```

Then replace the second anchor D line with:

```python
        "mail.door_code_reason.other": "cloud TTLock požadavek odmítl nebo neodpověděl",
```

5. `test_door_codes_safeguards.py`:
   - Replace the import line of anchor E with `from app import config, db, deadlines, door_codes, mail_notify, ttlock`.
   - Replace the assert line of anchor E with:

```python
    assert "TTLock's cloud server is not responding or returned an error. This is a problem on TTLock's side, not with your lock or your settings [transient:-1026]" in body
```

   - Append at the end of the file:

```python


def test_host_mails_name_the_cause_in_plain_words():
    def en(reason):
        return mail_notify._door_code_reason("en", reason)

    assert en("transient:90000").startswith("TTLock's cloud server is not responding")
    assert en("network").startswith("TTLock's cloud server is not responding")
    assert "gateway" in en("offline:-2012")
    assert "gateway" in en("period_taken:offline:-2012")
    assert "Authorized Admin" in en("permission:-2018")
    assert "memory is full" in en("storage:-4056")
    assert "monthly limit" in en("budget")
    assert en("not_set_up").startswith("this property has no lock")
    assert en("something_new").startswith("TTLock's cloud refused")
    assert en("transient:90000").endswith("[transient:90000]")


def test_the_late_code_mail_says_ubyhost_keeps_trying():
    _, apartment, stay = _stay(registered_minutes_ago=15)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, last_error = ?, next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, "transient:90000", "2999-01-01T00:00:00+00:00", row_id),
    )
    door_codes._alert_delayed()
    notices = db.query(
        "SELECT payload, cc_email FROM email_outbox "
        "WHERE reservation_id = ? AND idempotency_key LIKE '%:delayed'",
        (stay,),
    )
    assert len(notices) == 1
    body = json.loads(notices[0]["payload"])["text"]
    assert "keeps trying" in body
    assert "will not try again" not in body
    assert "TTLock's cloud server is not responding" in body
    assert notices[0]["cc_email"] == "support@ubyhost.com"
```

6. Run the commands in §6.

## 5. Do not touch

Every template, `App/app/i18n.py` (guest copy), `App/app/door_codes.py`, every other i18n key, `App/tests/test_door_code_handover.py`. Hard rules 2, 3, 8, 9 apply.

## 6. Commands

From `App/`:

```
grep -c 'mail.door_code_notice.delayed' app/host_i18n.py      # expect 4
.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py -q   # expect all pass
.venv/bin/python -m pytest tests -q                              # expect all pass
```

From the repo root: `python3 scripts/context_lint.py` (expect OK).

## 7. Acceptance

- [ ] The grep gives 4.
- [ ] Both new tests and the door-code test files pass.
- [ ] The full suite passes, or only failures that also fail on `main` remain (name them; CI decides).
- [ ] `git diff --stat` lists only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0070-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/mail_notify.py`: reason mapping (`period_taken:` prefix, unknown kinds fall to `other`), the late-mail variant choice.
- `App/app/host_i18n.py`: placeholders `%(property)s`, `%(date)s`, `%(reason)s` intact in both languages.

## Owner steps

1. Open the PR the executor pushed and check that CI is green.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`.
