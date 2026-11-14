# 1630: Stop the separate "guest details" mail to the host after completion

Status: todo
Depends on: none | Base commit: e90d2412a | Branch: cursor/1630-stop-host-guest-details-mail-4527
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When a stay completes, stop `maybe_notify_completion` from queuing the `guest_details_host` mail ("Your guests have registered"); only the `completion` mail ("You're all set", host in CC) may be sent. The host opens the stay in the app for the full guest data, and two mails at once (seen for Vivus Apartment 15.11.-19.11.2026) is noise.

## 2. Context

Owner decision 2026-11-14 (supersedes the 2026-11-13 decision that kept both mails after task 1291): only mail 1 (`completion`, TO guest, CC host) exists after a completed stay. Tier B (mail): guest-facing receipt behaviour must stay exactly as it is.

Scope is minimal. Dead code stays for a later cleanup brief: do NOT delete `mail_notify.host_guest_details`, `build_host_guest_details`, the `guest_details_host` kind in `mail.KINDS`, i18n strings, the settings switch or `guest_mail_pref`. Only the call from `claim.py` goes.

Excerpt 1, `App/app/claim.py`, inside `maybe_notify_completion` (about lines 864-887 on `e90d2412a`). Find it with `grep -n "host_guest_details" App/app/claim.py` (expect one hit near line 879):

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
    try:
        fee_now = _completion_fee(apartment, reservation)
        mail_notify.host_guest_details(
            apartment,
            reservation,
            filled=progress["filled"],
            expected=expected,
            fee_total=fee_now["total"] if fee_now else None,
        )
    except Exception:  # the host mail must never cost the guest their receipt
        log.exception("host guest details not queued reservation_id=%s", reservation["id"])
    db.execute(
```

Followed by (keep untouched): the `UPDATE reservation_claim SET completion_notified_at`, the `door_code.notified_at` update, and the `if outbox_id:` fee baseline block that calls `_completion_fee` again itself.

Excerpt 2, `App/tests/test_host_guest_details_mail.py` (about lines 177-199):

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

(The function ends after the `host_mail["to_email"]` line, the last line of the file; confirm with `sed -n 175,200p` and replace every `host_mail` line.)

Note: `App/tests/test_claim_mail.py` line ~1821 lists `"guest_details_host"` inside the `mail.KINDS` pin test. That is the kind list, not a send expectation; it stays because the kind stays. If grep finds any other `guest_details_host` in that file, check whether it follows `maybe_notify_completion` and expects an outbox row; flip those to expect zero rows.

If an excerpt is not found verbatim, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/claim.py` | edit | Remove the try/except that calls `mail_notify.host_guest_details` in `maybe_notify_completion` |
| `App/tests/test_host_guest_details_mail.py` | edit | Rename one test, flip its host-mail asserts to "no row" |
| `App/tests/test_claim_mail.py` | edit only if needed | Only if a completion path expects a `guest_details_host` row (expected: no change) |
| `docs/tasks/1630-report.md` | create | The report (section 9) |
| `docs/tasks/1630-stop-host-guest-details-mail.md` | edit | Set `Status: review` at the end |

No other file may change.

## 4. Steps

1. Stay on branch `cursor/1630-stop-host-guest-details-mail-4527` (already created from base `e90d2412a`). Check: `git rev-parse --short HEAD` starts with `e90d2412a` or the branch tip includes the brief commit (else STOP). Do not create a second branch.
2. In `App/app/claim.py`, delete the whole `try:` ... `except Exception:` ... `log.exception(...)` block shown in excerpt 1 (the 11 lines from `    try:` through the `log.exception("host guest details not queued ...")` line). After the edit the code is the `mail.enqueue(...)` call, then immediately `    db.execute(` for `completion_notified_at`. Leave `_completion_fee`, `mail_notify` and `log` imports alone (still used elsewhere in the file; do not remove imports).
3. Verify: `grep -n "host_guest_details" App/app/claim.py` returns nothing, and `sed -n 864,885p App/app/claim.py` shows enqueue followed directly by `db.execute(`.
4. In `App/tests/test_host_guest_details_mail.py`: rename `test_the_receipt_is_copied_to_the_host_and_the_host_still_gets_details` to `test_the_receipt_is_copied_to_the_host_and_no_separate_host_details_mail`. Keep every assert on the `completion` row (`to_email == LEAD`, `cc_email == HOST`, `reply_to == HOST`, `"(host only)"`, the `/reservations/{id}` stay URL). Replace the `(host_mail,) = _rows(seed["stay"], "guest_details_host")` line and all following `host_mail` asserts with exactly:

   ```python
       assert _rows(seed["stay"], "guest_details_host") == []
   ```

   Keep the `for _ in range(2)` loop (it proves idempotence). Do not touch the other tests in that file: they call `mail_notify.host_guest_details` directly and must still pass.
5. In the module docstring of that test file, nothing changes.
6. `grep -n "guest_details_host" App/tests/test_claim_mail.py`. If only the `mail.KINDS` pin (about line 1821) appears, make no change to that file. Otherwise flip completion-path expectations to zero rows.
7. Run the commands in section 6. Fix only failures caused by this change. A test fails twice: STOP.
8. Write `docs/tasks/1630-report.md`, set `Status: review` in this brief, then `git add` the changed files and commit `1630: stop host guest details mail after completion`. Do not push or merge (owner step).

## 5. Do not touch

- `App/app/mail_notify.py` (builders, `host_guest_details`, `build_host_guest_details`), `App/app/mail.py` (kinds), `App/app/host_i18n.py` and any i18n, `App/app/guest_mail_pref.py`, settings, templates, `App/migrations_pg/`, Go code.
- The `completion` enqueue arguments, `cc_email`, `completion_notified_at`, door-code `notified_at`, the fee baseline block.
- AGENTS.md hard rules that apply: 1 (UbyPort filing untouched), 2 (no new personal data, no new outbound request: this removes one), 3 (no secrets), 4 (no dependency), 8 (never push to `main`; no merge).
- No status/decisions/known-issues edits: the orchestrator does those.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_host_guest_details_mail.py tests/test_guest_mail.py tests/test_claim_mail.py tests/test_completion_fee_mail_1077.py tests/test_guest_receipt_sent_mail.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass, 0 failed. (`test_guest_receipt_sent_mail.py` imports fixtures from the edited test file, so it is included.)

From the repo root:

```
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: no errors.

```
grep -n "host_guest_details" App/app/claim.py | tail -5
git diff --stat | tail -10
```

Expected: first command prints nothing; the diff shows only `claim.py` and `test_host_guest_details_mail.py` (plus the brief and report).

## 7. Acceptance

- [ ] `grep -n "host_guest_details" App/app/claim.py` prints nothing.
- [ ] In `maybe_notify_completion`, `mail.enqueue(kind="completion", ... cc_email=payload.get("reply_to", "") ...)` is immediately followed by `db.execute(` for `completion_notified_at`.
- [ ] `test_the_receipt_is_copied_to_the_host_and_no_separate_host_details_mail` exists, keeps the completion asserts, and asserts `_rows(seed["stay"], "guest_details_host") == []`.
- [ ] The old test name no longer appears: `grep -rn "still_gets_details" App/tests` prints nothing.
- [ ] The section 6 pytest command passes with 0 failed.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat` touches only files from section 3.
- [ ] No template, CSS or guest-page change, so no screenshot is needed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1630-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/claim.py`, `maybe_notify_completion`: the guest receipt (`completion`, host CC) and the `completion_notified_at` update must be unchanged; only the host-details try/except is gone.
- `App/tests/test_host_guest_details_mail.py`: the renamed test must still assert the receipt TO/CC/reply_to and now assert zero `guest_details_host` rows; the other tests there must be unchanged.
- Follow-up (not this brief): a cleanup brief for the dead `host_guest_details` path, the `guest_details_host` kind, i18n, the settings switch and `guest_mail_pref`.

## Owner steps

1. Open the pull request for branch `cursor/1630-stop-host-guest-details-mail-4527` and wait until the checks are green.
2. Keep it a draft until you want it live, because green merges auto-deploy.
3. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
4. After the next stay completes, check the host inbox: only "You're all set" arrives, with no "Your guests have registered".
