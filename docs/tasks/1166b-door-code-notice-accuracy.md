# 1166b: door-code notices: mail again for a new target window, and true copy

Status: todo
Depends on: 1166 | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1166b-notice-accuracy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Review of 1166 found four small faults. (1) The `moved_failed` mail is sent once per row forever, so a later failed move to other dates is silent. (2) Its copy says UbyHost retries "until the stay starts", but retries stop when the old code's period starts and pause while the TTLock account is not ok. (3) The `pin_unverified` body blames TTLock for not answering, which we do not know. (4) Czech word order in that body.

## 2. Context

Idempotency key today (`App/app/mail_notify.py`, in `_door_code_notice`): `idempotency_key=f"door_code_notice:{door_code_id}:{variant}",`. The only caller that needs a window is the `moved_failed` call in `App/app/door_codes.py` (`_handle_moves`), where `start_ms` and `end_ms` are the target window. The same failed move retried hourly has the same `start_ms`/`end_ms`, so it still mails once.

Copy rule: one explanation in one place, no em dashes. Target copy:

- en moved_failed: `... The guest still has the old code, which works only for the old dates. UbyHost keeps trying every hour while it still can. If the stay starts and the code is still for the old dates, create a code for the new dates in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost support has a copy of this e-mail.`
- en pin_unverified: `UbyHost could not check with TTLock whether the door code for the stay from %(date)s still exists on the lock. The guest can still see the code, and it may not work. ...` (rest unchanged)

If an "old" excerpt below is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail_notify.py | edit | optional `key_suffix` on `door_code_notice`, `_door_code_notice`, appended to the key |
| App/app/door_codes.py | edit | pass the target window as `key_suffix` for `moved_failed` |
| App/app/host_i18n.py | edit | en and cs: `moved_failed.body`, `pin_unverified.body` |
| App/app/host_vi_i18n.py | edit | vi: same two bodies |
| App/tests/test_door_code_host_notices.py | edit | `_mails` helper pattern, new test |

No other file may change. (Greps for the old wording in other tests found nothing: `tests/test_door_codes_safeguards.py` "keeps trying" belongs to the `delayed` variant and stays.)

## 4. Steps

**1. `App/app/mail_notify.py`**, four one-line edits.

```
-def door_code_notice(door_code_id: int, variant: str) -> Optional[int]:
+def door_code_notice(door_code_id: int, variant: str, key_suffix: str = "") -> Optional[int]:
-        return _door_code_notice(door_code_id, variant)
+        return _door_code_notice(door_code_id, variant, key_suffix)
-def _door_code_notice(door_code_id: int, variant: str) -> Optional[int]:
+def _door_code_notice(door_code_id: int, variant: str, key_suffix: str = "") -> Optional[int]:
-        idempotency_key=f"door_code_notice:{door_code_id}:{variant}",
+        idempotency_key=f"door_code_notice:{door_code_id}:{variant}" + (f":{key_suffix}" if key_suffix else ""),
```

**2. `App/app/door_codes.py`** (`_handle_moves`, the `if kind == ttlock.LOCK_SETUP:` block):

```
-                    # The guest keeps the old code while the hourly retry runs: tell the host
-                    # once (the mail queue's idempotency key per row and variant).
-                    mail_notify.door_code_notice(int(row["id"]), "moved_failed")
+                    # The guest keeps the old code while the retry runs: tell the host once per
+                    # target window (the mail queue's idempotency key), so a later move to other
+                    # dates that fails again mails again.
+                    mail_notify.door_code_notice(
+                        int(row["id"]), "moved_failed", key_suffix=f"{start_ms}-{end_ms}"
+                    )
```

**3. `App/app/host_i18n.py`** (en block, then cs block). Replace each old fragment inside the body string with the new one (each occurs once in the file):

```
en pin_unverified
-TTLock did not answer when UbyHost checked whether the door code for the stay from %(date)s still exists on the lock, so UbyHost could not confirm it. The guest
+UbyHost could not check with TTLock whether the door code for the stay from %(date)s still exists on the lock. The guest
en moved_failed
-UbyHost tries again every hour until the stay starts. If this is not fixed by then, create a code for the new dates
+UbyHost keeps trying every hour while it still can. If the stay starts and the code is still for the old dates, create a code for the new dates
cs pin_unverified
-TTLock neodpověděl, když UbyHost ověřoval, zda kód ke dveřím pro pobyt od %(date)s stále existuje na zámku, a proto ho nemohl potvrdit. Host
+UbyHost nemohl u TTLock ověřit, zda kód ke dveřím pro pobyt od %(date)s stále existuje na zámku. Host
cs pin_unverified (word order)
-že kód hosta tam je
+že tam kód hosta je
cs moved_failed
-UbyHost to zkouší znovu každou hodinu, dokud pobyt nezačne. Pokud se to do té doby nespraví, vytvořte kód pro nový termín
+UbyHost to zkouší každou hodinu, dokud to jde. Pokud pobyt začne a kód bude stále platit jen pro původní termín, vytvořte kód pro nový termín
```

**4. `App/app/host_vi_i18n.py`**:

```
vi pin_unverified
-TTLock không phản hồi khi UbyHost kiểm tra xem mã cửa của lượt lưu trú từ %(date)s còn trên khóa hay không, nên UbyHost không xác nhận được. Khách
+UbyHost không kiểm tra được với TTLock xem mã cửa của lượt lưu trú từ %(date)s còn trên khóa hay không. Khách
vi moved_failed
-UbyHost thử lại mỗi giờ cho đến khi lượt lưu trú bắt đầu. Nếu đến lúc đó vẫn chưa xử lý được, hãy tạo mã cho ngày mới
+UbyHost thử lại mỗi giờ chừng nào còn có thể. Nếu lượt lưu trú bắt đầu mà mã vẫn chỉ dùng được cho ngày cũ, hãy tạo mã cho ngày mới
```

**5. `App/tests/test_door_code_host_notices.py`.** Add `from datetime import datetime, timedelta` after `import json`. In `_mails` the keys now carry a suffix, so change `(stay, f"%:{variant}"),` to `(stay, f"%:{variant}%"),`. Insert before `def test_a_busy_cloud_on_a_move_sends_no_mail`:

```python
def test_a_failed_move_mails_again_only_for_a_different_target_window(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(-3034))
    door_codes.reconcile()
    assert len(_mails(stay, "moved_failed")) == 1
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()  # the same window retried: still one mail
    assert len(_mails(stay, "moved_failed")) == 1
    res = db.query_one("SELECT date_to FROM reservation WHERE id = ?", (stay,))
    later = (datetime.fromisoformat(res["date_to"]).date() + timedelta(days=1)).isoformat()
    db.execute("UPDATE reservation SET date_to = ? WHERE id = ?", (later, stay))
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()  # a new target window that fails too: a second mail
    assert len(_mails(stay, "moved_failed")) == 2
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
```

**6. Revert-bite.** Run the new test, then `git stash push App/app/door_codes.py App/app/mail_notify.py`, run it again (it must fail with `assert 1 == 2`), then `git stash pop`.

## 5. Do not touch

Templates, CSS, migrations, any other notice variant, the `notification.*` copy. Hard rules 1, 3, 5, 9 apply (no em dashes; one explanation in one place).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

```
.venv/bin/python -m pytest tests/test_door_code_host_notices.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30
```

Expected: 16 passed; about 319 passed, 1 skipped (the skip is a pre-existing browser test, not one you touched); `All checks passed!`. From the repo root: `python3 scripts/context_lint.py | tail -3` OK.

## 7. Acceptance

- [ ] Two different target windows give two `moved_failed` mails; the same window retried gives one (new test green, and red under the revert-bite).
- [ ] The three en/cs/vi `moved_failed` and `pin_unverified` bodies match §4; `grep -rn "every hour until the stay\|did not answer when UbyHost\|kód hosta tam je" App/app | tail -5` prints nothing.
- [ ] §6 commands pass; no em dashes.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, you reach 25 tool calls, a file outside §3 needs a change, or you need push, merge or deploy (hand it to the owner).

## 9. Report

Write `docs/tasks/1166b-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations.
