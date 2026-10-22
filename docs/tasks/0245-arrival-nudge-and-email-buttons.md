# 0245: A day-earlier arrival nudge, and one button in every host email (ideas E and R)

Status: todo
Depends on: 0244 | Base commit: after 0244 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

E: today the host hears about an unopened guest link only on check-in day, when it is often too late. When nobody has opened the guest link by 9:00 the day before arrival, the host gets the reminder then, while there is still a day to send the link. It is the same reminder mail with "tomorrow" wording, and it uses the check-in-day mail's key, so a stay never gets two host reminders (owner rule: no extra host emails, at most one reminder per stay).

R: every host email ends with one exact button. The reminder's button lands on the stay's `#now` panel (where "Copy your own link" is). The door-code notices are plain paragraphs today, with no link at all. They get the branded layout, one "Open the stay" button to `#now`, and the address under it.

## 2. Context

- `claim.sweep_reminders()` runs every few minutes. Its check-in-day branch builds `mail_notify.build_reminder_host(...)` and enqueues `reminder_host` with `idempotency_key=f"reminder_host:{id}:{start}"`; `mail.enqueue` returns the existing row for a known key, so a second call never sends.
- `reservation["claim_state"]` is None when nobody has opened the stay's guest link (no `reservation_claim` row).
- Door-code notices: `mail_notify._door_code_notice` and `door_code_delayed_notice` build `payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", ...}`. Helpers: `_shell(lang=, title=, preheader=, blocks=, footer_lines=)`, `_block_paragraph(text)`, `_block_button(url, label)`, `_block_link(url, label)`, `_guest_text(lang, "mail_link_fallback")`, `_public(path)` (absolute URL).
- Host mail is English (`HOST_MAIL_LANGUAGE`), but EN/CS key parity is enforced, and VI carries the mail keys too.
- No new mail kind, no new table, no new outbound request.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/claim.py` | edit | the earlier reminder (step 1) |
| `App/app/mail_notify.py` | edit | tomorrow wording, door-code button (steps 2, 3) |
| `App/app/host_i18n.py` | edit | EN + CS strings (step 4) |
| `App/app/host_vi_i18n.py` | edit | VI strings (step 4) |
| `App/tests/test_arrival_nudge_0245.py` | create | tests (step 5) |
| `docs/tasks/0245-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. `claim.py`: the earlier reminder

1a. Anchor (exact line, in `sweep_reminders`): `    summary = {"guest": 0, "host": 0, "locked": 0}`
Replace with: `    summary = {"guest": 0, "host": 0, "host_early": 0, "locked": 0}`

1b. Anchor (exact line): `        if start == today and not complete and now_local.hour >= 9:`

Replace with:

```python
        # 0245 (idea E): nobody has opened the guest link by 9:00 the day
        # before arrival, so the host still has a day to send it. The mail key
        # is the check-in-day key, so a stay never gets a second host reminder.
        early = (
            start == today + timedelta(days=1)
            and now_local.hour >= 9
            and not reservation["claim_state"]
            and not complete
            and progress["status"] not in ("reported", "not_required")
            and (reservation["source"] or "") != "demo"
        )
        if early or (start == today and not complete and now_local.hour >= 9):
```

1c. In the same block, replace these exact lines

```python
                    stay_url=(
                        f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                        f"/reservations/{reservation['id']}"
                    ),
                    claimed=reservation["claim_state"] == CLAIMED,
                    filled=progress["filled"],
                    expected=progress["expected"],
                )
```

with

```python
                    stay_url=(
                        f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                        f"/reservations/{reservation['id']}#now"
                    ),
                    claimed=reservation["claim_state"] == CLAIMED,
                    filled=progress["filled"],
                    expected=progress["expected"],
                    tomorrow=early,
                )
```

1d. Anchor (these exact lines, the end of the host `mail.enqueue(...)` call, directly followed by `alerts.raise_alert(`):

```python
                    owner_user_id=reservation["owner_user_id"],
                )
            alerts.raise_alert(
```

Replace with:

```python
                    owner_user_id=reservation["owner_user_id"],
                )
            if early:
                # The check-in-day alert and count belong to check-in day.
                summary["host_early"] += 1
                continue
            alerts.raise_alert(
```

Command: `cd App && .venv/bin/python -c "import app.claim" 2>&1 | tail -5` → no output (the new `tomorrow=` argument only works after step 2; tests run after step 4). Commit `0245 step 1`.

### Step 2. `mail_notify.py`: tomorrow wording

2a. In `build_reminder_host`, anchor (these exact lines):

```python
    filled: int = 0,
    expected: Optional[int] = None,
) -> Dict[str, str]:
    """The check-in-day nudge for the host, in the host's language.
```

Replace with:

```python
    filled: int = 0,
    expected: Optional[int] = None,
    tomorrow: bool = False,
) -> Dict[str, str]:
    """The check-in-day nudge for the host, in the host's language.

    0245: with ``tomorrow`` it is the day-before nudge for a stay whose guest
    link nobody has opened yet (same mail, same key, sent at most once).
```

2b. Anchor (these exact lines):

```python
    subject = _text(
        lang,
        "mail.reminder_host.subject"
        if expected is not None
        else "mail.reminder_host.subject_unclaimed",
```

Replace with:

```python
    subject = _text(
        lang,
        "mail.reminder_host.subject_tomorrow"
        if tomorrow
        else "mail.reminder_host.subject"
        if expected is not None
        else "mail.reminder_host.subject_unclaimed",
```

2c. Replace these exact lines

```python
    intro = _text(lang, "mail.reminder_host.intro", property=property_name, date=date)
    preheader = _text(lang, "mail.reminder_host.preheader")
```

with

```python
    when = "_tomorrow" if tomorrow else ""
    intro = _text(lang, f"mail.reminder_host.intro{when}", property=property_name, date=date)
    preheader = _text(lang, f"mail.reminder_host.preheader{when}")
```

2d. Replace these exact lines

```python
    next_steps = _text(
        lang,
        "mail.reminder_host.next_steps_claimed"
        if claimed
        else "mail.reminder_host.next_steps_unclaimed",
```

with

```python
    next_steps = _text(
        lang,
        "mail.reminder_host.next_steps_tomorrow"
        if tomorrow
        else "mail.reminder_host.next_steps_claimed"
        if claimed
        else "mail.reminder_host.next_steps_unclaimed",
```

2e. Replace the exact line `    footer = _text(lang, "mail.reminder_host.footer")` (inside `build_reminder_host`; check with `grep -n 'footer = _text(lang, "mail.reminder_host.footer")' app/mail_notify.py` that it is one line) with `    footer = _text(lang, f"mail.reminder_host.footer{when}")`.

Commit `0245 step 2` (strings come in step 4; do not run tests yet).

### Step 3. `mail_notify.py`: door-code notices get one button

3a. Insert directly BEFORE the line `def _door_code_notice(door_code_id: int, variant: str) -> Optional[int]:`:

```python
def _door_code_payload(lang: str, subject: str, body: str, reservation_id: int) -> Dict[str, Any]:
    """0245 (idea R): the notice in the branded layout, ending with one button to the stay."""
    stay_url = _public(f"/reservations/{reservation_id}#now")
    action = _text(lang, "mail.door_code_notice.action")
    blocks = [
        _block_paragraph(body),
        _block_button(stay_url, action),
        _block_link(stay_url, _guest_text(lang, "mail_link_fallback")),
    ]
    return {
        "text": f"{body}\n\n{action}: {stay_url}",
        "html": _shell(lang=lang, title=subject, preheader=subject, blocks=blocks, footer_lines=["UbyHost"]),
        "lang": lang,
    }


```

3b. In `_door_code_notice`, replace the exact line
`    payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}`
with
`    payload = _door_code_payload(lang, subject, body, reservation["id"])`

3c. In `door_code_delayed_notice`, replace the exact line (8 spaces of indent)
`        payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}`
with
`        payload = _door_code_payload(lang, subject, body, reservation_id)`

3d. If `html.` is no longer used anywhere in `mail_notify.py` (`grep -c 'html\.escape\|html\.unescape' app/mail_notify.py` is 0), remove `import html` (ruff F401). Otherwise keep it.

Commit `0245 step 3`.

### Step 4. Strings

4a. `host_i18n.py`. Anchor (these exact lines):

```python
for _lang, _strings in _HEALTH_0244_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert directly AFTER them:

```python

# 0245 (ideas E and R): the day-before reminder and the door-code button.
_MAIL_0245_STRINGS = {
    "en": {
        "mail.reminder_host.subject_tomorrow": "Arriving tomorrow, guest link not opened yet: %(property)s",
        "mail.reminder_host.preheader_tomorrow": "Send the guest link today so the guest can register before arrival.",
        "mail.reminder_host.intro_tomorrow": "%(property)s has a check-in tomorrow (%(date)s) and nobody has opened the guest registration yet.",
        "mail.reminder_host.next_steps_tomorrow": "Open the stay, copy its own link and send it to the guest in the booking chat.",
        "mail.reminder_host.footer_tomorrow": "You get this at most once per stay: the day before check-in, only when nobody has opened the guest link.",
        "mail.door_code_notice.action": "Open the stay",
    },
    "cs": {
        "mail.reminder_host.subject_tomorrow": "Zítra příjezd, odkaz pro hosty zatím nikdo neotevřel: %(property)s",
        "mail.reminder_host.preheader_tomorrow": "Pošlete hostovi odkaz ještě dnes, ať se stihne zaregistrovat před příjezdem.",
        "mail.reminder_host.intro_tomorrow": "%(property)s má zítra příjezd (%(date)s) a registraci hostů zatím nikdo neotevřel.",
        "mail.reminder_host.next_steps_tomorrow": "Otevřete pobyt, zkopírujte jeho vlastní odkaz a pošlete ho hostovi v konverzaci k rezervaci.",
        "mail.reminder_host.footer_tomorrow": "Tento e-mail dostanete u pobytu nejvýš jednou: den před příjezdem, a jen když odkaz pro hosty nikdo neotevřel.",
        "mail.door_code_notice.action": "Otevřít pobyt",
    },
}
for _lang, _strings in _MAIL_0245_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

4b. `host_vi_i18n.py`: append at the very end of the file:

```python

# 0245 (ideas E and R): the day-before reminder and the door-code button.
STRINGS.update({
    "mail.reminder_host.subject_tomorrow": "Khách đến ngày mai, chưa ai mở liên kết cho khách: %(property)s",
    "mail.reminder_host.preheader_tomorrow": "Hãy gửi liên kết cho khách ngay hôm nay để khách kịp đăng ký trước khi đến.",
    "mail.reminder_host.intro_tomorrow": "%(property)s có khách nhận phòng ngày mai (%(date)s) và chưa ai mở trang đăng ký.",
    "mail.reminder_host.next_steps_tomorrow": "Mở lượt lưu trú, sao chép liên kết riêng của lượt đó và gửi cho khách trong cuộc trò chuyện đặt phòng.",
    "mail.reminder_host.footer_tomorrow": "Bạn nhận email này tối đa một lần cho mỗi lượt lưu trú: một ngày trước khi nhận phòng, và chỉ khi chưa ai mở liên kết cho khách.",
    "mail.door_code_notice.action": "Mở lượt lưu trú",
})
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_i18n.py tests/test_guest_mail.py -q --tb=short 2>&1 | tail -10` → pass. Commit `0245 step 4`.

### Step 5. Create `App/tests/test_arrival_nudge_0245.py` with exactly this content

```python
"""0245: the host hears about an unopened guest link the day before arrival, once."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app import claim, db, mail, mail_notify
from tests.test_claim_mail import _cleanup, _seed


def _clock(monkeypatch, day, hour=10):
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    moment = [datetime.combine(day, time(hour, 0))]
    monkeypatch.setattr(claim.deadlines, "local_now", lambda now=None: now if now is not None else moment[0])
    monkeypatch.setattr(claim, "prague_today", lambda: moment[0].date())
    return moment


def _host_reminders(reservation_id):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind = 'reminder_host'", (reservation_id,)
    )


def test_an_unopened_link_reminds_the_host_the_day_before_and_only_once(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    arrival = db.query_one("SELECT date_from FROM reservation WHERE id = ?", (current,))["date_from"]
    day_before = datetime.fromisoformat(arrival).date() - timedelta(days=1)
    try:
        moment = _clock(monkeypatch, day_before, hour=8)
        assert claim.sweep_reminders()["host_early"] == 0  # not before 9:00
        moment[0] = datetime.combine(day_before, time(10, 0))
        assert claim.sweep_reminders()["host_early"] == 1
        rows = _host_reminders(current)
        assert len(rows) == 1
        mail_log = db.query_one("SELECT * FROM console_mail_log WHERE subject LIKE 'Arriving tomorrow,%'")
        assert mail_log
        assert f"/reservations/{current}#now" in mail_log["body_text"]
        assert "check-in tomorrow" in mail_log["body_text"]
        # Check-in day: the same key, so no second host mail.
        moment[0] = datetime.combine(day_before + timedelta(days=1), time(10, 0))
        claim.sweep_reminders()
        assert len(_host_reminders(current)) == 1
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (current,))
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_reminder_and_door_code_notice_each_end_with_one_button():
    content = mail_notify.build_reminder_host(
        property_name="Flat", date="01.11.2026", assigned="", stay_url="https://example.test/reservations/5#now",
        claimed=False, tomorrow=True,
    )
    assert content["subject"].startswith("Arriving tomorrow, guest link not opened yet")
    assert content["html"].count('href="https://example.test/reservations/5#now"') >= 1
    payload = mail_notify._door_code_payload("en", "Flat: code late", "The code is late.", 5)
    assert "/reservations/5#now" in payload["text"]
    assert payload["html"].count("Open the stay") == 1
    assert "<p>The code is late.</p>" not in payload["html"]
```

Command: `cd App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_arrival_nudge_0245.py -q --tb=short 2>&1 | tail -15` → pass. If the first test fails because `_seed()`'s current stay does not arrive on a date you can step back from, or because `_seed` is not importable, report the error and stop; do not edit `test_claim_mail.py`. Commit `0245 step 5`.

## 5. Do not touch

Everything outside §3. No new mail kind, no weekly mail, no change to guest mails.

## 6. Commands

From `App/`, `tests/test_alert_stack.py` first:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_arrival_nudge_0245.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py tests/test_host_i18n.py tests/test_pii_encryption.py tests/test_retention_job.py -q --tb=short 2>&1 | tail -20`
2. `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5` (or `python3 -m ruff`; say if neither exists)
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

A test that expected no host mail for an unclaimed stay arriving tomorrow: report it with the file and line and stop; do not change it.

## 7. Acceptance

- [ ] §6 commands 1 and 2 pass.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0245-report.md` (600 tokens at most) with the last lines of each command, and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

`App/app/claim.py` (`sweep_reminders`: who gets a host mail and when), `App/app/mail_notify.py` (door-code notice HTML).

## Owner steps

None.
