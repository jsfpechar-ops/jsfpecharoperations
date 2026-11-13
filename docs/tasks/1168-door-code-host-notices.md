# 1168: tell the host about three door-code problems that were silent (K-DC-ERRCODE)

Status: todo
Depends on: 1165b (kind `lock_setup`, `mail_notify._DOOR_CODE_REASON_KINDS` and the `lock_setup` reason come from 1165 and 1165b) | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1168-door-code-host-notices
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three door-code problems leave the host unaware: (1) a revived code that TTLock never confirms is kept issued, so the guest may see a dead PIN, with only an audit line; (2) a date move that fails with `lock_setup` retries hourly with no mail; (3) the `config` kind tells the host to reconnect TTLock, but it is a UbyHost-side setting. Fix: (1) one warning card and one mail, (2) one mail at the first failure, (3) a new reason `support`; plus the `lock_setup` reason is rewritten as one clause that reads inside "Reason: ...".

## 2. Context

Rules: rule 9 (one explanation in one place, no em dashes); no PIN in any card or mail; no new dependency, no migration. **Tests run on SQLite** (leave `UBYHOST_DATABASE_URL` unset); Postgres is left to CI (local Postgres is unreliable, the brief changes no SQL). Titles of `notification.*.title` are at most 60 characters without placeholders (`tests/test_0280_short_notifications.py`).

The brief was verified in a scratch worktree on HEAD: all scripts below applied cleanly and the commands in §6 passed (87, 154, 375 passed with 2 environment skips for missing playwright, ruff clean, four revert-bites).

What changes:

1. `App/app/door_codes.py` `_revive_one`: after `LOOKUP_MAX_TRIES` unknown lookups the row stays issued and the audit `door_code_pin_unverified` is written. New `_tell_host_unverified(row_id, owner_id)` (same shape as `_tell_host_reissued`) raises the card `door_code_pin_unverified` (warning, dedupe key `door_code_pin_unverified:<reservation id>`, params property and date) and sends the mail variant `pin_unverified` (idempotent per row through the mail queue key `door_code_notice:<row>:pin_unverified`, support in cc). A failure inside is logged and never stops the revival.
2. `App/app/door_codes.py` `_handle_moves`, the `except ttlock.TTLockError` branch: after the hourly retry is scheduled, `kind == ttlock.LOCK_SETUP` sends the new variant `moved_failed` (its reason line is `mail_notify._door_code_reason` of the row's `last_error`, support in cc, idempotent per row). There was no failed-move variant: `failed` says "UbyHost will not try again", which is false for a move. Retrying is unchanged. A busy cloud (`transient`) sends nothing.
3. `App/app/mail_notify.py`: `config` maps to the new reason `support`; the reason text gets `%(support)s` = `config.SUPPORT_EMAIL` (the address already used by the mails' `cc_email`).
4. `lock_setup` reason, one clause (the mail adds "Reason: " before and " [token]." after):

| Lang | Text |
|---|---|
| en | the lock is not fully set up in TTLock, so in the TTLock app check that it is added, connected to a gateway and online |
| cs | zámek není v TTLock úplně nastavený, proto v aplikaci TTLock zkontrolujte, že je přidaný, připojený k bráně a online |
| vi | khóa chưa được thiết lập đầy đủ trong TTLock, vì vậy hãy kiểm tra trong ứng dụng TTLock rằng khóa đã được thêm, kết nối với gateway và đang trực tuyến |

New `support` reason (en): "this is a setting on the UbyHost side, not in your lock or your TTLock account, so please write to %(support)s". The mails already say "UbyHost support has a copy of this e-mail"; the reason does not repeat that.

New card (en): title "%(property)s: door code for %(date)s is not confirmed."; detail "UbyHost could not confirm on the lock that the guest's door code exists. Check in the TTLock app that it is there, or create a code yourself."

New mail `pin_unverified` (en): subject "%(property)s: check the door code in the TTLock app"; body "TTLock did not answer when UbyHost checked whether the door code for the stay from %(date)s still exists on the lock, so UbyHost could not confirm it. The guest can still see the code, and it may not work. In the TTLock app (open the lock, tap Passcodes), check that the guest's code is there. If it is not, create a code by hand and send it to the guest. UbyHost support has a copy of this e-mail."

New mail `moved_failed` (en): subject "%(property)s: door code not yet moved to the new dates"; body "The stay from %(date)s changed its dates or hours, and UbyHost could not move its door code yet. Reason: %(reason)s. The guest still has the old code, which works only for the old dates. UbyHost tries again every hour until the stay starts. If this is not fixed by then, create a code for the new dates in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost support has a copy of this e-mail."

cs and vi are in the scripts below (they are the copy this brief owns).

Anchors (in the scripts; each must be found exactly once, else STOP): in `mail_notify.py` the lines `"lock_setup",` then `)` and the line `"config": "no_account",` with its comment, `if variant == "failed":`, the `_SUPPORT_COPY_VARIANTS = (...)` line, the `_text(lang, f"mail.door_code_reason.{key}")` line; in `door_codes.py` the `if unverified:` audit line, the `def _reissue_lost_pin(` line and the `(_iso(_now() + timedelta(minutes=delay)), ...` execute call in `_handle_moves`; in `host_i18n.py` (en and cs) and `host_vi_i18n.py` the `mail.door_code_reason.lock_setup`, `notification.door_code_reissued_no_email.detail` and `mail.door_code_notice.reissued_no_email.body` lines; in the tests and docs the lines quoted in the scripts.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail_notify.py | edit | reason `support`, `config` maps to it, `support` param, variants `moved_failed`/`pin_unverified` |
| App/app/door_codes.py | edit | `_tell_host_unverified` and its call, `moved_failed` mail on a `lock_setup` move failure |
| App/app/host_i18n.py | edit | en and cs: reasons, card, two mails |
| App/app/host_vi_i18n.py | edit | vi: the same keys |
| App/tests/test_door_code_host_notices.py | create | 9 test functions (15 cases) for the three behaviours and the copy |
| App/tests/test_ttlock_lock_setup.py | edit | four assertions follow the new wording |
| App/tests/test_alert_language.py | edit | one `STORED_KINDS` entry |
| docs/TTLOCK.md | edit | the `lock_setup` and `config` rows |
| docs/plans/ttlock-door-codes.md | edit | the move wording and the `config` sentence |
| docs/tasks/1168-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30` and `grep -c "mail.door_code_reason.lock_setup" App/app/host_i18n.py | tail -30`; the second must print `2` (1165b is in), else STOP. Then `git switch -c task/1168-door-code-host-notices | tail -30`; expected `Switched to a new branch`.

**Step 2. Code.** Write the script to `/tmp/1166_code.py` (ends at `PYEOF`), run it from the repo root with `python3 /tmp/1166_code.py | tail -30` (no output means success), then `git diff --stat | tail -30`; expected `door_codes.py` and `mail_notify.py` changed.
```bash
cat > /tmp/1166_code.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

MN = "App/app/mail_notify.py"
swap(MN, '''    "budget",
    "lock_setup",
)
# TTLock error kinds''', '''    "budget",
    "lock_setup",
    "support",
)
# TTLock error kinds''')
swap(MN, '''    # The account or the server's TTLock setting is wrong: the connection is set up again.
    "config": "no_account",
''', '''    # An operator or server setting (API base, account delete): only UbyHost support can fix it.
    "config": "support",
''')
swap(MN, '''    if variant == "failed":
        params["reason"] =''', '''    if variant in ("failed", "moved_failed"):
        params["reason"] =''')
swap(MN, '''_SUPPORT_COPY_VARIANTS = ("failed", "delayed", "period_taken", "period_shared", "moved_not_deleted")''',
     '''_SUPPORT_COPY_VARIANTS = (
    "failed",
    "delayed",
    "period_taken",
    "period_shared",
    "moved_not_deleted",
    "moved_failed",
    "pin_unverified",
)''')
swap(MN, '''    text = _text(lang, f"mail.door_code_reason.{key}")
    return f"{text} [{reason}]"''', '''    text = _text(lang, f"mail.door_code_reason.{key}", support=config.SUPPORT_EMAIL)
    return f"{text} [{reason}]"''')

DC = "App/app/door_codes.py"
swap(DC, '''    if unverified:
        db.audit("door_code_pin_unverified", f"door_code={row_id}", actor="system", owner_user_id=owner_id)
    elif verdict == PIN_GONE:''', '''    if unverified:
        db.audit("door_code_pin_unverified", f"door_code={row_id}", actor="system", owner_user_id=owner_id)
        _tell_host_unverified(row_id, owner_id)
    elif verdict == PIN_GONE:''')
swap(DC, '''def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:''',
'''def _tell_host_unverified(row_id: int, owner_user_id: int) -> None:
    """Tell the host once that a revived code could not be confirmed on the lock.

    Called when the lookup stayed unknown for LOOKUP_MAX_TRIES and the row is kept issued: the
    guest may be shown a PIN the lock no longer has. One warning card per stay (dedupe key) and
    one mail per row (idempotency key in the mail queue); neither carries the PIN. A failure
    here is logged and never stops the revival.
    """
    try:
        info = db.query_one(
            "SELECT a.id AS apartment_id, a.internal_name, r.id AS reservation_id, r.date_from "
            "FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
            "JOIN reservation r ON r.id = dc.reservation_id WHERE dc.id = ?",
            (row_id,),
        )
        if not info:
            return
        alerts.raise_alert(
            "warning",
            "door_code_pin_unverified",
            "Door code could not be confirmed on the lock",
            dedupe_key=f"door_code_pin_unverified:{info['reservation_id']}",
            apartment_id=info["apartment_id"],
            reservation_id=info["reservation_id"],
            owner_user_id=owner_user_id,
            params={"property": info["internal_name"], "date": info["date_from"]},
        )
        mail_notify.door_code_notice(row_id, "pin_unverified")
    except Exception:
        log.exception("door code %s: host notice about an unverified code failed", row_id)


def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:''')
swap(DC, '''                    (_iso(_now() + timedelta(minutes=delay)), last_error, now_iso, row["id"]),
                )
''', '''                    (_iso(_now() + timedelta(minutes=delay)), last_error, now_iso, row["id"]),
                )
                if kind == ttlock.LOCK_SETUP:
                    # The guest keeps the old code while the hourly retry runs: tell the host
                    # once (the mail queue's idempotency key per row and variant).
                    mail_notify.door_code_notice(int(row["id"]), "moved_failed")
                    mail.drain(limit=4)
''')
PYEOF
```

**Step 3. Copy.** Write the script to `/tmp/1166_copy.py`, run `python3 /tmp/1166_copy.py | tail -30` (no output means success), then `git diff --stat | tail -30`; expected two more files (`host_i18n.py`, `host_vi_i18n.py`).
```bash
cat > /tmp/1166_copy.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

HI = "App/app/host_i18n.py"
VI = "App/app/host_vi_i18n.py"

# 1. The lock_setup reason as one clause that reads inside "Reason: %(reason)s." and the new support reason.
swap(HI, '''        "mail.door_code_reason.lock_setup": "the lock's own TTLock setup is incomplete: it has no gateway or network, or it does not support this. In the TTLock app, check that the lock is added, connected to a gateway and online",
        "mail.door_code_reason.other": "TTLock's cloud refused the request or did not answer",
''', '''        "mail.door_code_reason.lock_setup": "the lock is not fully set up in TTLock, so in the TTLock app check that it is added, connected to a gateway and online",
        "mail.door_code_reason.support": "this is a setting on the UbyHost side, not in your lock or your TTLock account, so please write to %(support)s",
        "mail.door_code_reason.other": "TTLock's cloud refused the request or did not answer",
''')
swap(HI, '''        "mail.door_code_reason.lock_setup": "zámek nemá v TTLock dokončené nastavení: chybí mu brána nebo síť, nebo tuto funkci nepodporuje. V aplikaci TTLock zkontrolujte, že je zámek přidaný, připojený k bráně a online",
        "mail.door_code_reason.other": "cloud TTLock požadavek odmítl nebo neodpověděl",
''', '''        "mail.door_code_reason.lock_setup": "zámek není v TTLock úplně nastavený, proto v aplikaci TTLock zkontrolujte, že je přidaný, připojený k bráně a online",
        "mail.door_code_reason.support": "jde o nastavení na straně UbyHost, ne ve vašem zámku ani v účtu TTLock, proto prosím napište na %(support)s",
        "mail.door_code_reason.other": "cloud TTLock požadavek odmítl nebo neodpověděl",
''')
swap(VI, '''    "mail.door_code_reason.lock_setup": "khóa chưa được thiết lập xong trong TTLock: thiếu gateway hoặc mạng, hoặc khóa không hỗ trợ chức năng này. Trong ứng dụng TTLock, hãy kiểm tra khóa đã được thêm, kết nối với gateway và đang trực tuyến",
    "mail.door_code_reason.other":''', '''    "mail.door_code_reason.lock_setup": "khóa chưa được thiết lập đầy đủ trong TTLock, vì vậy hãy kiểm tra trong ứng dụng TTLock rằng khóa đã được thêm, kết nối với gateway và đang trực tuyến",
    "mail.door_code_reason.support": "đây là một thiết lập phía UbyHost, không phải trong khóa hay tài khoản TTLock của bạn, vì vậy vui lòng viết tới %(support)s",
    "mail.door_code_reason.other":''')

# 2. Alert cards (title is 60 characters at most without placeholders).
swap(HI, '''        "notification.door_code_reissued_no_email.detail": "The stay was cancelled and came back, so its door code was replaced. The guest sees the new code on their stay page.",
''', '''        "notification.door_code_reissued_no_email.detail": "The stay was cancelled and came back, so its door code was replaced. The guest sees the new code on their stay page.",
        "notification.door_code_pin_unverified.title": "%(property)s: door code for %(date)s is not confirmed.",
        "notification.door_code_pin_unverified.detail": "UbyHost could not confirm on the lock that the guest's door code exists. Check in the TTLock app that it is there, or create a code yourself.",
''')
swap(HI, '''        "notification.door_code_reissued_no_email.detail": "Pobyt byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen. Host uvidí nový kód na stránce svého pobytu.",
''', '''        "notification.door_code_reissued_no_email.detail": "Pobyt byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen. Host uvidí nový kód na stránce svého pobytu.",
        "notification.door_code_pin_unverified.title": "%(property)s: kód ke dveřím pro pobyt od %(date)s není ověřen.",
        "notification.door_code_pin_unverified.detail": "UbyHost na zámku nemohl ověřit, že kód ke dveřím pro hosta existuje. V aplikaci TTLock zkontrolujte, že tam je, nebo vytvořte kód sami.",
''')
swap(VI, '''    "notification.door_code_reissued_no_email.detail": "Lượt lưu trú đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới. Khách sẽ thấy mã mới trên trang lưu trú của họ.",
''', '''    "notification.door_code_reissued_no_email.detail": "Lượt lưu trú đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới. Khách sẽ thấy mã mới trên trang lưu trú của họ.",
    "notification.door_code_pin_unverified.title": "%(property)s: chưa xác nhận được mã cửa cho lượt lưu trú từ %(date)s.",
    "notification.door_code_pin_unverified.detail": "UbyHost không xác nhận được trên khóa rằng mã cửa của khách còn tồn tại. Hãy kiểm tra trong ứng dụng TTLock xem mã có ở đó không, hoặc tự tạo một mã.",
''')

# 3. The two new host mails.
swap(HI, '''        "mail.door_code_notice.reissued_no_email.body": "The stay from %(date)s was cancelled and came back, so its door code was replaced. The guest sees the new code on their stay page.",
''', '''        "mail.door_code_notice.reissued_no_email.body": "The stay from %(date)s was cancelled and came back, so its door code was replaced. The guest sees the new code on their stay page.",
        "mail.door_code_notice.pin_unverified.subject": "%(property)s: check the door code in the TTLock app",
        "mail.door_code_notice.pin_unverified.body": "TTLock did not answer when UbyHost checked whether the door code for the stay from %(date)s still exists on the lock, so UbyHost could not confirm it. The guest can still see the code, and it may not work. In the TTLock app (open the lock, tap Passcodes), check that the guest's code is there. If it is not, create a code by hand and send it to the guest. UbyHost support has a copy of this e-mail.",
        "mail.door_code_notice.moved_failed.subject": "%(property)s: door code not yet moved to the new dates",
        "mail.door_code_notice.moved_failed.body": "The stay from %(date)s changed its dates or hours, and UbyHost could not move its door code yet. Reason: %(reason)s. The guest still has the old code, which works only for the old dates. UbyHost tries again every hour until the stay starts. If this is not fixed by then, create a code for the new dates in the TTLock app (open the lock, tap Passcodes) and send it to the guest. UbyHost support has a copy of this e-mail.",
''')
swap(HI, '''        "mail.door_code_notice.reissued_no_email.body": "Pobyt od %(date)s byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen. Host uvidí nový kód na stránce svého pobytu.",
''', '''        "mail.door_code_notice.reissued_no_email.body": "Pobyt od %(date)s byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen. Host uvidí nový kód na stránce svého pobytu.",
        "mail.door_code_notice.pin_unverified.subject": "%(property)s: zkontrolujte kód ke dveřím v aplikaci TTLock",
        "mail.door_code_notice.pin_unverified.body": "TTLock neodpověděl, když UbyHost ověřoval, zda kód ke dveřím pro pobyt od %(date)s stále existuje na zámku, a proto ho nemohl potvrdit. Host kód nadále vidí, ale nemusí fungovat. V aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) zkontrolujte, že kód hosta tam je. Pokud ne, vytvořte kód ručně a pošlete ho hostovi. Podpora UbyHost má kopii tohoto e-mailu.",
        "mail.door_code_notice.moved_failed.subject": "%(property)s: kód ke dveřím ještě nemá nový termín",
        "mail.door_code_notice.moved_failed.body": "Pobyt od %(date)s změnil termín nebo hodiny a UbyHost zatím nemohl přesunout jeho kód ke dveřím. Důvod: %(reason)s. Host má zatím starý kód, který platí jen pro původní termín. UbyHost to zkouší znovu každou hodinu, dokud pobyt nezačne. Pokud se to do té doby nespraví, vytvořte kód pro nový termín v aplikaci TTLock (otevřete zámek, klepněte na Kódy / Passcodes) a pošlete ho hostovi. Podpora UbyHost má kopii tohoto e-mailu.",
''')
swap(VI, '''    "mail.door_code_notice.reissued_no_email.body": "Lượt lưu trú từ %(date)s đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới. Khách sẽ thấy mã mới trên trang lưu trú của họ.",
''', '''    "mail.door_code_notice.reissued_no_email.body": "Lượt lưu trú từ %(date)s đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới. Khách sẽ thấy mã mới trên trang lưu trú của họ.",
    "mail.door_code_notice.pin_unverified.subject": "%(property)s: hãy kiểm tra mã cửa trong ứng dụng TTLock",
    "mail.door_code_notice.pin_unverified.body": "TTLock không phản hồi khi UbyHost kiểm tra xem mã cửa của lượt lưu trú từ %(date)s còn trên khóa hay không, nên UbyHost không xác nhận được. Khách vẫn thấy mã này và mã có thể không dùng được. Trong ứng dụng TTLock (mở khóa, bấm Passcodes), hãy kiểm tra mã của khách có ở đó không. Nếu không có, hãy tự tạo mã và gửi cho khách. Bộ phận hỗ trợ UbyHost có bản sao email này.",
    "mail.door_code_notice.moved_failed.subject": "%(property)s: mã cửa chưa được chuyển sang ngày mới",
    "mail.door_code_notice.moved_failed.body": "Lượt lưu trú từ %(date)s đã đổi ngày hoặc giờ, và UbyHost chưa chuyển được mã cửa của lượt này. Lý do: %(reason)s. Khách vẫn giữ mã cũ, mã này chỉ dùng được cho ngày cũ. UbyHost thử lại mỗi giờ cho đến khi lượt lưu trú bắt đầu. Nếu đến lúc đó vẫn chưa xử lý được, hãy tạo mã cho ngày mới trong ứng dụng TTLock (mở khóa, bấm Passcodes) và gửi cho khách. Bộ phận hỗ trợ UbyHost có bản sao email này.",
''')
PYEOF
```

**Step 4. Tests.** Write the script to `/tmp/1166_tests.py`, run `python3 /tmp/1166_tests.py | tail -30` (no output means success). Then from `App/`: `.venv/bin/python -m pytest tests/test_door_code_host_notices.py tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30`; expected `87 passed`. Then from the repo root `git add -A && git commit -m "1168: host notices for door codes (code, copy, tests)" | tail -30`.
```bash
cat > /tmp/1166_tests.py <<'PYEOF'
import re

def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

# Existing tests that pinned the old wording.
swap("App/tests/test_ttlock_lock_setup.py",
     '''    assert "gateway" in reason("en", "lock_setup:-3034") and "TTLock app" in reason("en", "lock_setup:-3034")''',
     '''    assert "gateway" in reason("en", "lock_setup:-3034") and "TTLock app" in reason("en", "lock_setup:-3034")
    assert reason("en", "lock_setup:-3034").startswith("the lock is not fully set up in TTLock")''')
swap("App/tests/test_ttlock_lock_setup.py",
     '''    assert reason("en", "config:-4063").startswith("the TTLock connection needs to be set up again")''',
     '''    assert reason("en", "config:-4063").startswith("this is a setting on the UbyHost side")''')
swap("App/tests/test_ttlock_lock_setup.py",
     '''    assert reason("en", "period_taken:lock_setup:-4037").startswith("the lock's own TTLock setup")''',
     '''    assert reason("en", "period_taken:lock_setup:-4037").startswith("the lock is not fully set up in TTLock")''')
swap("App/tests/test_ttlock_lock_setup.py",
     '''        assert reason(lang, "config:-4063").split(" [")[0] == reason(lang, "reauth").split(" [")[0]''',
     '''        assert reason(lang, "config:-4063") != reason(lang, "reauth")''')
swap("App/tests/test_alert_language.py",
     '''    "door_code_reissued_no_email": {"property": "Loft", "date": "2026-09-11"},
}''', '''    "door_code_reissued_no_email": {"property": "Loft", "date": "2026-09-11"},
    "door_code_pin_unverified": {"property": "Loft", "date": "2026-09-11"},
}''')

open("App/tests/test_door_code_host_notices.py", "w", encoding="utf-8").write('''"""1168: three door-code problems that left the host in the dark now tell the host, once, without the PIN.

An unconfirmed revived code (warning card, one mail), a date move that cannot reach the lock
(one mail, the hourly retry goes on) and the config kind (the reason sends the host to support).
"""
from __future__ import annotations

import json

import pytest

from app import alerts, config, db, door_codes, host_i18n, mail_notify, ttlock
from tests.test_door_code_ambiguous_delete import _delete_then, _tick, world  # noqa: F401
from tests.test_door_code_lost_pin import _expire_lease, _revive, _row
from tests.test_door_codes_safeguards import _env  # noqa: F401
from tests.test_ttlock_lock_setup import _code_row, _moved_stay, _refuse

REAL_NOTICE = mail_notify.door_code_notice  # the world fixture replaces it with a no-op
KIND = "door_code_pin_unverified"
PIN = "4821937"


def _cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind = ? AND reservation_id = ? AND resolved_at IS NULL", (KIND, stay)
    )


def _mails(stay, variant):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND idempotency_key LIKE ?",
        (stay, f"%:{variant}"),
    )


def _unverified(world, monkeypatch):  # noqa: F811
    """A delete timed out, the stay is back and every lookup fails: three ticks give up."""
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    _expire_lease(row)
    _tick()
    return lock, stay, row


@pytest.fixture
def notices(monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        door_codes.mail_notify, "door_code_notice", lambda row_id, variant: seen.append((row_id, variant))
    )
    return seen


def test_a_code_that_stays_unconfirmed_raises_one_warning_card_and_one_notice(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    assert _cards(stay) == [] and notices == []  # two failed lookups: still held back
    _expire_lease(row)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "warning"
    assert cards[0]["dedupe_key"] == f"{KIND}:{stay}"
    assert notices == [(row, "pin_unverified")]


def test_a_lookup_that_works_in_time_tells_the_host_nothing(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    lock.lookup_error = None
    lock.pins["pid-1"] = PIN
    _expire_lease(row)
    _tick()
    assert _cards(stay) == [] and notices == []


def test_the_card_and_the_mail_hold_no_pin_and_the_mail_is_idempotent(world, monkeypatch):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    _expire_lease(row)
    _tick()
    mails = _mails(stay, "pin_unverified")
    assert len(mails) == 1 and mails[0]["cc_email"] == config.SUPPORT_EMAIL
    everything = json.dumps(dict(mails[0]), default=str) + json.dumps(dict(_cards(stay)[0]), default=str)
    assert PIN not in everything and "TTLock app" in everything
    mail_notify.door_code_notice(row, "pin_unverified")
    assert len(_mails(stay, "pin_unverified")) == 1
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


def test_a_failing_notice_does_not_stop_the_revival(world, monkeypatch):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("alert table locked")

    monkeypatch.setattr(alerts, "raise_alert", boom)
    _expire_lease(row)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED


def test_a_lock_setup_failure_on_a_move_mails_the_host_once_and_keeps_retrying(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(-3034))
    door_codes.reconcile()
    first = _mails(stay, "moved_failed")
    assert len(first) == 1 and first[0]["cc_email"] == config.SUPPORT_EMAIL
    assert "lock_setup:-3034" in json.dumps(dict(first[0]), default=str)
    assert _code_row(stay)["next_attempt_at"] is not None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()  # the hourly retry fails again
    assert len(_mails(stay, "moved_failed")) == 1
    row = _code_row(stay)
    assert row["last_error"] == "lock_setup:-3034" and row["next_attempt_at"] is not None
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


def test_a_busy_cloud_on_a_move_sends_no_mail(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    monkeypatch.setattr(
        ttlock, "create_period_code",
        lambda *a, **k: (_ for _ in ()).throw(ttlock.TTLockError("busy", kind="transient")),
    )
    door_codes.reconcile()
    assert _mails(stay, "moved_failed") == [] and _code_row(stay)["next_attempt_at"] is not None


@pytest.mark.parametrize("lang,word", [("en", "UbyHost side"), ("cs", "straně UbyHost"), ("vi", "phía UbyHost")])
def test_the_config_kind_sends_the_host_to_support(lang, word):
    for token in ("config:-4063", "config:30008", "period_taken:config:30008"):
        text = mail_notify._door_code_reason(lang, token)
        assert word in text and config.SUPPORT_EMAIL in text and text.endswith(f"[{token}]")
        assert text != mail_notify._door_code_reason(lang, "reauth")


@pytest.mark.parametrize("lang,gateway", [("en", "gateway"), ("cs", "bráně"), ("vi", "gateway")])
def test_the_lock_setup_reason_is_one_clause_inside_the_reason_template(lang, gateway):
    text = mail_notify._door_code_reason(lang, "lock_setup:-3034").split(" [")[0]
    assert ". " not in text and ":" not in text and text[0].islower()
    assert "TTLock" in text and gateway in text
    body = host_i18n.translate(lang, "mail.door_code_notice.failed.body", date="d", reason=text)
    assert text in body


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_new_copy_exists_in_every_host_language(lang):
    for key in (
        "notification.door_code_pin_unverified.title",
        "notification.door_code_pin_unverified.detail",
        "mail.door_code_notice.pin_unverified.subject",
        "mail.door_code_notice.pin_unverified.body",
        "mail.door_code_notice.moved_failed.subject",
        "mail.door_code_notice.moved_failed.body",
        "mail.door_code_reason.support",
    ):
        text = host_i18n.translate(lang, key, property="Loft", date="11.09.2026", reason="r", support="s@x.test")
        assert text != key and "%(" not in text and "\\u2014" not in text, key
        if lang != "en":
            assert text != host_i18n.translate("en", key, property="Loft", date="11.09.2026", reason="r", support="s@x.test")
''')
PYEOF
```

**Step 5. Revert-bite.** Write the script to `/tmp/1166_bite.py` and run it from the repo root: `python3 /tmp/1166_bite.py 2>&1 | tail -30`. Expected exactly four lines `BITES unverified notice`, `BITES move mail`, `BITES config reason`, `BITES lock_setup copy`, each ending `1 failed` (the script restores `App/app` by `git checkout`). Then `git status --short | tail -30`; expected empty.
```bash
cat > /tmp/1166_bite.py <<'PYEOF'
import subprocess

def run(*files):
    cmd = [".venv/bin/python", "-m", "pytest", *files, "-q", "--tb=no", "-x"]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd="App").stdout.strip().splitlines()
    return out[-1] if out else "no output"

def bite(name, path, old, new, tests):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (name, old[:60])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))
    try:
        result = run(*tests)
    finally:
        subprocess.run(["git", "checkout", "--", "App/app"], check=True)
    assert "failed" in result, (name, result)
    print("BITES", name, "|", result)

T = ["tests/test_door_code_host_notices.py"]
bite("unverified notice", "App/app/door_codes.py",
     "        _tell_host_unverified(row_id, owner_id)\n", "", T)
bite("move mail", "App/app/door_codes.py",
     '                    mail_notify.door_code_notice(int(row["id"]), "moved_failed")\n', "                    pass\n", T)
bite("config reason", "App/app/mail_notify.py", '"config": "support",', '"config": "no_account",', T)
bite("lock_setup copy", "App/app/host_i18n.py",
     "the lock is not fully set up in TTLock, so in the TTLock app check that it is added, connected to a gateway and online",
     "the lock's own TTLock setup is incomplete: it has no gateway or network. In the TTLock app, check that it is added, connected to a gateway and online", T)
PYEOF
```

**Step 6. Docs.** Write the script to `/tmp/1166_docs.py`, run `python3 /tmp/1166_docs.py | tail -30` (no output means success), then `git diff --stat | tail -30`; expected `docs/TTLOCK.md` and `docs/plans/ttlock-door-codes.md`. Commit: `git add -A && git commit -m "1168: docs" | tail -30`.
```bash
cat > /tmp/1166_docs.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("docs/plans/ttlock-door-codes.md",
     "move: hourly until the stay starts, no mail;",
     "move: hourly until the stay starts, host mail `moved_failed` at the first failure;")
swap("docs/plans/ttlock-door-codes.md",
     "`config`, `permission`",
     "`config` (reads as \"a UbyHost setting, write to support\" in the host mail), `permission`")
swap("docs/TTLOCK.md",
     "Kind `config`: no retry, host mail (`30008` is the server's API base setting) |",
     "Kind `config`: no retry, host mail that sends the host to support (`30008` is the server's API base setting) |")
swap("docs/TTLOCK.md",
     "Kind `lock_setup`: retried slowly like a transient answer (a delete until `valid_to`), host mail at the usual threshold;",
     "Kind `lock_setup`: retried slowly like a transient answer (a delete until `valid_to`), host mail at the usual threshold (a move: at the first failure);")
PYEOF
```

## 5. Do not touch

`App/app/ttlock.py` (kinds and errcode map stay), `App/app/alerts.py`, any template or CSS, `App/app/migrations/`, `docs/context/` (the orchestrator updates status, decisions and known-issues at review). Hard rules 2 (no PIN in a card or mail; no new outbound request) and 9.

## 6. Commands

From `App/` (SQLite):
1. The step 4 command -> `87 passed`.
2. Door-code mail tests: `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_reissue_notice.py tests/test_door_code_handover.py tests/test_door_code_lost_pin.py tests/test_mail_golden.py tests/test_mail_failed_alert.py -q --tb=short -x 2>&1 | tail -30` -> `154 passed`.
3. Test-map row "Door codes, TTLock": `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30` -> `375 passed, 2 skipped` (the two skips are `No module named 'playwright'`; the count grows only by other briefs).
4. `.venv/bin/python -m ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30` -> `All checks passed!`.
5. `git status --short | tail -30`: delete a stray `App/config` (22 bytes) if it shows.
From the repo root: `python3 scripts/context_lint.py | tail -3` -> `context lint: OK`.
CI runs the Postgres leg; this brief changes no SQL.

## 7. Acceptance

- [ ] Step 5 printed four `BITES` lines.
- [ ] A code unconfirmed after three lookups gives one warning card and one `pin_unverified` mail, neither with the PIN; a lookup that works in time gives none.
- [ ] The first `lock_setup` move failure gives one `moved_failed` mail (support in cc, reason shown); later failures give none; the hourly retry still runs; a busy cloud gives none.
- [ ] `config:-4063` and `config:30008` read as the `support` reason (names `support@ubyhost.com`) in en, cs and vi.
- [ ] The `lock_setup` reason has no colon or second sentence in en, cs and vi and still names the TTLock app.
- [ ] No em dash in the new copy; card titles are 60 characters or fewer without placeholders.
- [ ] Commands 1 to 5 pass; `git diff --stat` shows only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a script `assert` fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1168-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py`: `_tell_host_unverified` (raises inside a try, called after the row is kept issued) and the `moved_failed` call (inside the non-permission retry branch; relies on the mail queue's idempotency key for "once per row").
- `App/app/mail_notify.py`: `config` now reads as `support`; the `support=` argument is passed to every reason text.
- The cs and vi copy of the two reasons, the card and the two mails: a native reader should check them.
- Known limit: the mail is once per row, so a second date move of the same row that fails again is silent (the card of the first is long gone); the `pin_unverified` card stays open until the host dismisses it.

## Owner steps

1. Push the branch and open a draft PR (not done by Haiku).
2. After CI is green (including the Postgres leg), merge with `scripts/merge-pr-on-green.sh <PR number>`.
