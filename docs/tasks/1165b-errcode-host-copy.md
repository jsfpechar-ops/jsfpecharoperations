# 1165b: host mail copy for the new TTLock kinds and the docs (K-DC-ERRCODE)

Status: todo
Depends on: 1165 (kind `lock_setup` and `test_ttlock_lock_setup.py` come from it) | Base commit: HEAD of branch task/1165-errcode-review-fixes after 1165 | Branch: task/1165b-errcode-host-copy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host mail for a failed door code says what to do for a kind, through `mail_notify._DOOR_CODE_REASON_KINDS`. It lacks `config`, `bug`, `code_missing` and the new `lock_setup` (1165), so those hosts read the generic "TTLock's cloud refused the request". Fix: `config` reuses the existing `no_account` text, `bug` and `code_missing` are named explicitly onto the generic `other` text, and `lock_setup` gets one new reason sentence in English, Czech and Vietnamese. The docs table rows follow 1165.

## 2. Context

Rules: rule 9 (one explanation in one place, no em dashes); no new dependency, no migration. **Tests run on SQLite** (leave `UBYHOST_DATABASE_URL` unset). The reason text is built by `mail_notify._door_code_reason` from the first token of `last_error` (`lock_setup:-3034` -> `lock_setup`; `period_taken:lock_setup:-4037` -> `lock_setup`) and always ends with the raw token in brackets for support. It is used by the "failed" and "delayed" door-code mails only (both cc support).

What each kind says after this brief: `lock_setup` -> new copy `mail.door_code_reason.lock_setup`; `config` -> `no_account` ("the TTLock connection needs to be set up again"; 30008 is an operator setting, support has the cc); `bug`, `code_missing` -> `other` (generic text plus the raw token).

New copy (this brief owns it): en "the lock's own TTLock setup is incomplete: it has no gateway or network, or it does not support this. In the TTLock app, check that the lock is added, connected to a gateway and online"; cs and vi are in the script below.

Anchors (in the scripts): `mail_notify.py` the end of `_DOOR_CODE_REASONS` (`"budget",` then `)`) and the end of `_DOOR_CODE_REASON_KINDS` (`"budget": "budget",` then `}`); the `mail.door_code_reason.other` line in `host_i18n.py` (en and cs) and `host_vi_i18n.py`; in the docs the rows and sentences quoted in `docs.py` below.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/mail_notify.py | edit | `lock_setup` reason key; `config`, `bug`, `code_missing` entries |
| App/app/host_i18n.py | edit | `mail.door_code_reason.lock_setup` en and cs |
| App/app/host_vi_i18n.py | edit | `mail.door_code_reason.lock_setup` vi |
| App/tests/test_ttlock_lock_setup.py | edit | mail reason test (appended) |
| docs/plans/ttlock-door-codes.md | edit | section 3.1: five rows `lock_setup`, kind sentence, `-1007` paragraph |
| docs/TTLOCK.md | edit | `-1007` row, the `config` row split into `lock_setup` and `config` |
| docs/tasks/1165b-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `task/1165-errcode-review-fixes`. Run `grep -c "LOCK_SETUP" App/app/ttlock.py | tail -30` (expected `2`, else STOP: 1165 is not in). Then `git switch -c task/1165b-errcode-host-copy | tail -30`; expected `Switched to a new branch`.

**Step 2. Mail map, copy, test.** Write the script to `/tmp/1165b_mail.py` (ends at `PYEOF`), run it from the repo root with `python3 /tmp/1165b_mail.py | tail -30` (no output means success). Then from `App/`: `.venv/bin/python -m pytest tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30`; expected `72 passed`.
```bash
cat > /tmp/1165b_mail.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

MN = "App/app/mail_notify.py"
swap(MN, '''    "storage",
    "budget",
)
# TTLock error kinds''', '''    "storage",
    "budget",
    "lock_setup",
)
# TTLock error kinds''')
swap(MN, '''    "storage": "storage",
    "budget": "budget",
}
# Reasons where nothing is retried''', '''    "storage": "storage",
    "budget": "budget",
    # The account or the server's TTLock setting is wrong: the connection is set up again.
    "config": "no_account",
    # A refused request or a code the lock does not have: the generic text and the raw token.
    "bug": "other",
    "code_missing": "other",
}
# Reasons where nothing is retried''')
swap("App/app/host_i18n.py",
     '''        "mail.door_code_reason.other": "TTLock's cloud refused the request or did not answer",
''',
     '''        "mail.door_code_reason.lock_setup": "the lock's own TTLock setup is incomplete: it has no gateway or network, or it does not support this. In the TTLock app, check that the lock is added, connected to a gateway and online",
        "mail.door_code_reason.other": "TTLock's cloud refused the request or did not answer",
''')
swap("App/app/host_i18n.py",
     '''        "mail.door_code_reason.other": "cloud TTLock požadavek odmítl nebo neodpověděl",
''',
     '''        "mail.door_code_reason.lock_setup": "zámek nemá v TTLock dokončené nastavení: chybí mu brána nebo síť, nebo tuto funkci nepodporuje. V aplikaci TTLock zkontrolujte, že je zámek přidaný, připojený k bráně a online",
        "mail.door_code_reason.other": "cloud TTLock požadavek odmítl nebo neodpověděl",
''')
swap("App/app/host_vi_i18n.py",
     '''    "mail.door_code_reason.other": "đám mây TTLock từ chối yêu cầu hoặc không phản hồi",
''',
     '''    "mail.door_code_reason.lock_setup": "khóa chưa được thiết lập xong trong TTLock: thiếu gateway hoặc mạng, hoặc khóa không hỗ trợ chức năng này. Trong ứng dụng TTLock, hãy kiểm tra khóa đã được thêm, kết nối với gateway và đang trực tuyến",
    "mail.door_code_reason.other": "đám mây TTLock từ chối yêu cầu hoặc không phản hồi",
''')
with open("App/tests/test_ttlock_lock_setup.py", "a", encoding="utf-8") as f:
    f.write('''

def test_host_mails_say_what_to_do_for_the_new_kinds():
    from app import mail_notify

    def reason(lang, text):
        return mail_notify._door_code_reason(lang, text)

    assert "gateway" in reason("en", "lock_setup:-3034") and "TTLock app" in reason("en", "lock_setup:-3034")
    assert reason("en", "lock_setup:-3034").endswith("[lock_setup:-3034]")
    assert reason("en", "config:-4063").startswith("the TTLock connection needs to be set up again")
    assert reason("en", "bug:-3006").startswith("TTLock's cloud refused")
    assert reason("en", "code_missing").startswith("TTLock's cloud refused")
    assert reason("en", "period_taken:lock_setup:-4037").startswith("the lock's own TTLock setup")
    for lang in ("cs", "vi"):
        assert reason(lang, "lock_setup:-3034") != reason("en", "lock_setup:-3034")
        assert reason(lang, "config:-4063").split(" [")[0] == reason(lang, "reauth").split(" [")[0]
''')
PYEOF
```

**Step 3. Docs.** Write the script to `/tmp/1165b_docs.py` (ends at `PYEOF`), run it from the repo root with `python3 /tmp/1165b_docs.py | tail -30` (no output means success). Then `grep -c "lock_setup" docs/plans/ttlock-door-codes.md docs/TTLOCK.md | tail -30`; expected `docs/plans/ttlock-door-codes.md:6` and `docs/TTLOCK.md:1`.
```bash
cat > /tmp/1165b_docs.py <<'PYEOF'
import re

def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

P = "docs/plans/ttlock-door-codes.md"
s = open(P, encoding="utf-8").read()
for code in ("-4043", "-4067", "-3034", "-4037", "-1003"):
    pat = re.compile(r"^(\| " + re.escape(code) + r" \|.*\|) config \|$", re.M)
    assert len(pat.findall(s)) == 1, code
    s = pat.sub(r"\1 lock_setup |", s)
open(P, "w", encoding="utf-8").write(s)
swap(P, "`code_missing` retries like them after one list call; `config`, `permission`",
     "`code_missing` retries like them after one list call; `lock_setup` (the lock's own setup: gateway, network, support) retries like them but slowly (issue: twice, then the host mail; delete: 1, 15, 60 minutes until `valid_to`, host mail at try 3; move: hourly until the stay starts, no mail; clock check: alert, next try in 7 days); `config`, `permission`")
swap(P, "A list that itself answers `-1007` on page 1 is an empty list. Otherwise the delete is retried.",
     "A list that itself answers `-1007` (any page) is unknown, never empty: it is not independent evidence after a delete said `-1007`, and a cleaning issue retry would add a second code. The delete is then retried until `valid_to`, then `revoke_failed` with the host mail (a lock with no codes at all answering `-1007` ends there too: the safe side). A `last_error` of `code_missing` leaves a delete's result open, so a revived row is checked on the lock before it is shown (`AMBIGUOUS_DELETE_ERRORS`).")
T = "docs/TTLOCK.md"
swap(T, "then revoked (kind `code_missing`); a list answering `-1007` is an empty list |",
     "then revoked (kind `code_missing`); a list answering `-1007` is unknown, never empty (the delete is retried) |")
s = open(T, encoding="utf-8").read()
old = [l for l in s.split("\n") if l.startswith("| `-1003`, `-4043`")]
assert len(old) == 1
new = ("| `-1003`, `-4043`, `-4037`, `-3034`, `-4067` | Lock missing, function not supported, gateway missing, network not configured, NB device not registered | Kind `lock_setup`: retried slowly like a transient answer (a delete until `valid_to`), host mail at the usual threshold; the host fixes the lock setup in the TTLock app |\n"
       "| `-4063`, `30008` | Delete locks first (account delete), wrong region host | Kind `config`: no retry, host mail (`30008` is the server's API base setting) |")
open(T, "w", encoding="utf-8").write(s.replace(old[0], new))
PYEOF
```

**Step 4. Revert-bite.** Write the script to `/tmp/1165b_bite.py` (ends at `PYEOF`), run it from `App/` with `python3 /tmp/1165b_bite.py | tail -30`. Expected: two lines starting `BITES`, none `NO BITE`; afterwards `git diff --stat | tail -30` is unchanged.
```bash
cat > /tmp/1165b_bite.py <<'PYEOF'
import subprocess

CASES = [
    ("reason key lock_setup known", "app/mail_notify.py", '    "budget",\n    "lock_setup",\n)', '    "budget",\n)'),
    ("config reads as no_account", "app/mail_notify.py", '    "config": "no_account",\n', ""),
]
for label, path, old, new in CASES:
    text = open(path, encoding="utf-8").read()
    assert text.count(old) == 1, (label, old)
    try:
        open(path, "w", encoding="utf-8").write(text.replace(old, new))
        out = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "tests/test_ttlock_lock_setup.py", "-q", "--tb=no", "-p", "no:cacheprovider"],
            capture_output=True, text=True,
        ).stdout
    finally:
        open(path, "w", encoding="utf-8").write(text)
    failed = [line for line in out.splitlines() if line.startswith("FAILED")]
    print("BITES" if failed else "NO BITE", len(failed), label)
PYEOF
```

## 5. Do not touch

`ttlock.py`, `door_codes.py`, `cleaning_codes.py` (1165), any other i18n key, `docs/context/*` (the orchestrator adds the decision and known-issues lines), any template or CSS.

## 6. Commands

From `App/` (SQLite):
1. `.venv/bin/python -m pytest tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30` -> `72 passed`.
2. Door-code mail tests: `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_reissue_notice.py tests/test_door_code_handover.py tests/test_door_code_lost_pin.py tests/test_mail_golden.py tests/test_mail_failed_alert.py -q --tb=short -x 2>&1 | tail -30` -> no failures.
3. Test-map row "Door codes, TTLock": `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30` -> no failures.
4. `.venv/bin/python -m ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30` -> `All checks passed!`.
5. `git status --short | tail -30`: delete a stray `App/config` (22 bytes) if it shows.
From the repo root: `python3 scripts/context_lint.py | tail -3` -> `context lint: OK`.

## 7. Acceptance

- [ ] Step 4 prints two `BITES` lines.
- [ ] `_door_code_reason("en", "lock_setup:-3034")` names the gateway and the TTLock app; cs and vi differ from en.
- [ ] `config:-4063` reads as the `no_account` text; `bug:-3006` and `code_missing` read as the generic text; each ends with its raw token.
- [ ] No em dash in the new copy (`test_no_em_dashes.py` passes).
- [ ] Commands 1 to 5 of §6 pass; `git diff --stat` shows only the files of §3.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (a script prints an `AssertionError`);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1165b-report.md` (600 tokens at most) and set `Status: review` at the top of this brief. The report has: 1. `git diff --stat`. 2. Each command with the last 5 lines of its output. 3. §7 ticked. 4. Deviations. 5. Questions. 6. Owner steps left.

## Risk list (for the reviewer)

The new `lock_setup` sentence in three languages (a native reader should check cs and vi); `_DOOR_CODE_REASON_KINDS` in `mail_notify.py`.

## Owner steps

1. After CI is green on the PR holding 1165 and 1165b, merge with `scripts/merge-pr-on-green.sh <PR number>`.
