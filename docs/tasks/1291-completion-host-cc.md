# 1291: Restore host CC on the guest completion receipt

Status: review
Depends on: none | Base commit: 91d5d4024 | Branch: task/1291-completion-host-cc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Put the host back on CC of the guest registration receipt (`completion`), and restore the quiet “host only” stay link in that mail, so the host can see that the guest was mailed without opening a separate channel. Keep `guest_details_host` for optional guest PII; do not put DOB, home address or full document fields into the shared receipt.

## 2. Context

Owner decision (2026-11-13): after stay 198, SES sent `completion` to the guest and the host never got a copy (1121 removed CC). Bring back the pre-1121 CC + host link on the receipt. Sensitive guest data stays only in `guest_details_host` (1121), not in the CC’d body beyond what the receipt already shows (counts, door code, fee, 1122 “what you sent” names / masked doc).

**Recovered from git:** parent of `5e2d908ba` (PR #923, “Guest details in host mail…”) — `git show 5e2d908ba^:App/app/claim.py`. That commit’s own summary: “claim.py: drop cc_email from receipt; … drop host_url from build_completion call”. Restore those two lines only; keep today’s `sent_details=True` and the `host_guest_details` call that 1121 added.

Hard rules: AGENTS privacy (no new personal-data fields), mail rules (`CLAIM_SECRET_MARKER` / door-code markers unchanged), no new dependency.

Pre-1121 enqueue (restore `cc_email` + its comment):

```python
    outbox_id = mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        # The host is copied on the receipt as well as being the reply address,
        # so the guest's own record of the stay reaches them either way.
        cc_email=payload.get("reply_to", ""),
        subject=content["subject"],
        payload=payload,
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
```

Pre-1121 composer call (restore `host_url`; keep `sent_details=True` from 1122):

```python
        if kind == "completion":
            return mail_notify.build_completion(
                lang=lang,
                property_name=property_name,
                dates=dates,
                stay_url=stay_url or "",
                host=host,
                door_code=door_code,
                filled=filled,
                expected=expected,
                host_url=f"{config.app_base_url()}/reservations/{reservation['id']}",
                fee=_completion_fee(apartment, reservation),
                sent_details=True,
                **_completion_facts(apartment, reservation, lang),
            )
```

`build_completion` already renders `host_url` when passed (`mail_completion_host_action`). `payload["reply_to"]` from `guest_payload` is still the entity contact. Keep the `host_guest_details(...)` call that follows enqueue.

Test that pins “no CC” today: `App/tests/test_host_guest_details_mail.py::test_the_receipt_is_not_copied_to_the_host_and_the_host_gets_their_own` (asserts `receipt["cc_email"] is None` and `"(host only)" not in payload["text"]`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/claim.py` | edit | Restore `cc_email` on completion enqueue; pass `host_url` into `build_completion` |
| `App/tests/test_host_guest_details_mail.py` | edit | Expect CC + host-only line; host details mail still queued |
| `docs/tasks/1291-report.md` | create | Report |

No other file may change.

## 4. Steps

1. In `App/app/claim.py`, in `_guest_mail_content` for `kind == "completion"`, restore the pre-1121 `host_url=` line (exact text from `5e2d908ba^`), keeping `sent_details=True`:

```python
        if kind == "completion":
            return mail_notify.build_completion(
                lang=lang,
                property_name=property_name,
                dates=dates,
                stay_url=stay_url or "",
                host=host,
                door_code=door_code,
                filled=filled,
                expected=expected,
                host_url=f"{config.app_base_url()}/reservations/{reservation['id']}",
                fee=_completion_fee(apartment, reservation),
                sent_details=True,
                **_completion_facts(apartment, reservation, lang),
            )
```

Command: `grep -n 'host_url=' App/app/claim.py | head -5`. Expected: one line with `reservations/`.

2. In `maybe_notify_completion`, restore the pre-1121 `cc_email` block (exact comment + kwarg from `5e2d908ba^`). Replace only the enqueue kwargs that 1121 changed:

```python
    outbox_id = mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        # The host is copied on the receipt as well as being the reply address,
        # so the guest's own record of the stay reaches them either way.
        cc_email=payload.get("reply_to", ""),
        subject=content["subject"],
        payload=payload,
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
```

Leave the `try` / `host_guest_details` block unchanged. Command: `grep -n 'cc_email' App/app/claim.py | head -5`. Expected: one line near the completion enqueue.

3. In `App/tests/test_host_guest_details_mail.py`, rename and flip the receipt assertions. Replace `test_the_receipt_is_not_copied_to_the_host_and_the_host_gets_their_own` with:

```python
def test_the_receipt_is_copied_to_the_host_and_the_host_still_gets_details(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda *a, **k: {"expected": 2, "filled": 2, "incomplete": []},
    )
    monkeypatch.setattr(door_codes, "completion_door_code", lambda *a, **k: ("none", None, None))
    seed = _seed()
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    for _ in range(2):
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
        claim.maybe_notify_completion(reservation, apartment)
    (receipt,) = _rows(seed["stay"], "completion")
    assert receipt["to_email"] == LEAD
    assert receipt["cc_email"] == HOST
    payload = json.loads(receipt["payload"])
    assert payload["reply_to"] == HOST
    assert "(host only)" in payload["text"]
    assert f"/reservations/{seed['stay']}" in payload["text"]
    (host_mail,) = _rows(seed["stay"], "guest_details_host")
    assert host_mail["to_email"] == HOST
```

If any other assert in that file requires `receipt["cc_email"] is None`, change it the same way (CC equals `HOST`). Command: `grep -n 'cc_email is None' App/tests/test_host_guest_details_mail.py | head -5`. Expected: only the `guest_details_host` row assert (host mail itself is not CC’d), not the completion receipt.

4. Run the commands in §6. Write `docs/tasks/1291-report.md` and set this brief’s Status to `review`.

## 5. Do not touch

`App/app/mail_notify.py` (`build_completion`, `host_guest_details`, `render_receipt_details`), `App/app/mail.py`, door-code mail, `fee_update` / `completion_update`, i18n catalogues, templates, migrations, Go code. Do not remove `guest_details_host`. Do not add dependencies. Do not print guest emails, PINs or document numbers in the report.

## 6. Commands

From `App/`:

```bash
.venv/bin/python -m pytest tests/test_host_guest_details_mail.py tests/test_guest_mail.py tests/test_claim_mail.py tests/test_completion_fee_mail_1077.py -q --tb=short -x 2>&1 | tail -30
```

From repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Acceptance

- [ ] `grep -n 'cc_email=payload.get("reply_to"' App/app/claim.py` shows one hit in `maybe_notify_completion`.
- [ ] `grep -n 'host_url=' App/app/claim.py` shows the reservations URL on the completion composer call.
- [ ] `tests/test_host_guest_details_mail.py` asserts completion `cc_email == HOST` and `"(host only)"` in the text; `guest_details_host` still queued.
- [ ] §6 pytest line is green (0 failed).
- [ ] `host_guest_details` is still called after the completion enqueue (`grep -n 'host_guest_details' App/app/claim.py`).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1291-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/claim.py`
- `App/tests/test_host_guest_details_mail.py`

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh <pr>`.
2. Deploy production (GitHub Actions → Deploy production → `force_confirm=DEPLOY`).
3. On the next completed registration, confirm the host inbox has a CC of the guest receipt (From UbyHost, guest in To) and still has `guest_details_host` when that path runs.
4. No backfill for stay 198; host can still share the door code from the stay page.
