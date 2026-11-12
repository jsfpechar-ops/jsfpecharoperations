# 1160b: tell the host after the new door code exists, and say the true thing

Status: review
Depends on: 1160 | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 after 1160 is merged | Branch: task/1160b-door-reissue-notice-fix
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The 1156 notice is sent before `issue()` runs, so the host reads "the guest gets the new code" even when the new code then fails, and it claims the guest is told by e-mail although a stay can have no guest address. Fix: send the notice only after `issue()` returned success, pick the wording by whether the stay has a guest e-mail, and replace the inaccurate "The first code had stopped working" with what happened: the stay was cancelled and came back, so its door code was replaced. English, Czech and Vietnamese.

## 2. Context

Rules: rule 9 (one explanation in one place); host copy in en, cs and vi (`App/app/host_i18n.py`, `App/app/host_vi_i18n.py`); `tests/test_0280_short_notifications.py`: every `notification.*.title` is at most 60 characters after removing `%(x)s` placeholders; no em dashes (`test_no_em_dashes.py`); no PIN in a notice. No migration, no dependency, no new state. Every script below asserts its anchors exist exactly once and stops with an `AssertionError` if not (then STOP, §8). This brief replaces the copy and the call position of 1156; it overlaps 1160 in `door_codes.py` (different functions): 1160 goes first.

**Item 2 (order).** `_reissue_lost_pin` today calls `_tell_host_reissued(row_id, owner_user_id)` and then `issue(row_id, allow_gateway=True)`. `issue()` returns `True` when it issued, `False` when it deferred or failed (state `retrying`, `failed`, or lease lost). New order: `issued = issue(...)`, then `_tell_host_reissued` only `if issued`. A failed `issue()` already raises the existing `door_code_failed` or `door_code_delayed` alert and mail, which tell the host to act. Accepted gap: if the first `issue()` fails and a later retry succeeds, no re-issue notice is sent (the failure alerts resolve themselves); `last_error` cannot mark it because `issue()` overwrites it with the failure reason.

**Item 2 (guest e-mail).** `door_codes._send_code_mail` returns without sending when `reservation_claim.email` is empty or there is no claim row, so a guest who has not registered gets nothing by e-mail; the guest sees the code on the stay page (`door_codes.view` returns `issued` with the PIN). So there are two wordings: with an e-mail "The guest gets the new code by e-mail.", without "The guest sees the new code on their stay page." Mechanism: the alert kind and the mail variant get the suffix `_no_email` (`door_code_reissued_no_email`, `reissued_no_email`), each with its own four keys. The title is the same text under both kinds. The card's `dedupe_key` carries the suffix too, so a second re-issue of the same stay and wording refreshes the open card. `alerts.py` and `mail_notify.py` need no change: the title key is `notification.<kind>.title`, the detail key `notification.<kind>.detail`, the mail keys `mail.door_code_notice.<variant>.subject|body`.

**Item 5 (copy).** Meaning: "The stay was cancelled and came back, so its door code was replaced." plus one guest sentence. "Nothing to do" is dropped (an `info` card, and the button already opens the stay). Titles say "replaced" (cs "nahrazen", vi "thay thế"). Czech and Vietnamese are written for a host, not word for word; a reviewer who reads them should check the sentences in the diff.

Anchors: `door_codes.py` the docstring and query of `_tell_host_reissued`, the `alerts.raise_alert(... "door_code_reissued" ...)` call, the `mail_notify.door_code_notice(row_id, "reissued")` line, and the `_tell_host_reissued(...)` / `issue(...)` pair in `_reissue_lost_pin`; the copy scripts look for the lines starting with the 8 keys `notification.door_code_reissued.title|detail` and `mail.door_code_notice.reissued.subject|body`; `test_alert_language.py` the `door_code_reissued` entry; the reissue-notice test file as listed in the script.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | notice after success; variant by guest e-mail |
| App/app/host_i18n.py | edit | en + cs: 4 keys changed, 4 added per language |
| App/app/host_vi_i18n.py | edit | vi: the same |
| App/tests/test_alert_language.py | edit | one `STORED_KINDS` entry |
| App/tests/test_door_code_reissue_notice.py | edit | guest e-mail in 3 tests, 2 new tests, copy test for both wordings |
| docs/tasks/1160b-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1160 is in: `grep -c "def code_is_listed" App/app/ttlock.py | tail -30` -> `1` (else STOP). Then `git switch -c task/1160b-door-reissue-notice-fix | tail -30`; expected `Switched to a new branch`.

**Step 2. Code.** From `App/` run:
```bash
python3 - <<'EOF'
path = "app/door_codes.py"
s = open(path, encoding="utf-8").read()

def swap(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)

swap('''    """Tell the host once that a lost door code was made again: one info card, one mail.

    The card key is per stay, so a second re-issue refreshes the open card; the mail key
    is per row and variant, so it goes out once. Neither carries the PIN. A failure here
    is logged and never stops the re-issue.
    """''', '''    """Tell the host once that a lost door code was replaced: one info card, one mail.

    Called only after issue() made the new code. The wording says how the guest gets it:
    by e-mail when the stay has a guest address, else on the stay page (kind and variant
    end in _no_email). The card key is per stay and wording, so a second re-issue refreshes
    the open card; the mail key is per row and variant, so it goes out once. Neither
    carries the PIN. A failure here is logged and never stops the re-issue.
    """''')
swap('''            "SELECT a.id AS apartment_id, a.internal_name, r.id AS reservation_id, r.date_from "
            "FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
            "JOIN reservation r ON r.id = dc.reservation_id WHERE dc.id = ?",''', '''            "SELECT a.id AS apartment_id, a.internal_name, r.id AS reservation_id, r.date_from, "
            "c.email AS guest_email FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
            "JOIN reservation r ON r.id = dc.reservation_id "
            "LEFT JOIN reservation_claim c ON c.reservation_id = r.id WHERE dc.id = ?",''')
swap('''        alerts.raise_alert(
            "info",
            "door_code_reissued",
            "Door code was made again",
            dedupe_key=f"door_code_reissued:{info['reservation_id']}",''', '''        suffix = "" if (info["guest_email"] or "").strip() else "_no_email"
        alerts.raise_alert(
            "info",
            f"door_code_reissued{suffix}",
            "Door code was replaced",
            dedupe_key=f"door_code_reissued{suffix}:{info['reservation_id']}",''')
swap('''        mail_notify.door_code_notice(row_id, "reissued")''', '''        mail_notify.door_code_notice(row_id, f"reissued{suffix}")''')
swap('''    _tell_host_reissued(row_id, owner_user_id)
    try:
        issue(row_id, allow_gateway=True)
    except Exception:
        log.exception("door code %s: re-issue after a lost revoke failed", row_id)
''', '''    try:
        issued = issue(row_id, allow_gateway=True)
    except Exception:
        log.exception("door code %s: re-issue after a lost revoke failed", row_id)
        return
    if issued:
        _tell_host_reissued(row_id, owner_user_id)
''')
swap('''row goes issued -> pending and issue() runs at once, so a success leaves no pending
    row for _alert_delayed. A failure is handled by issue() and the retry loop: their
    host alerts and mails are reused, no new alert.''', '''row goes issued -> pending and issue() runs at once, so a success leaves no pending
    row for _alert_delayed; only then is the host told (_tell_host_reissued). A failure is
    handled by issue() and the retry loop: their host alerts and mails are reused, and a
    code that a later retry makes sends no re-issue notice.''')
open(path, "w", encoding="utf-8").write(s)
EOF
```
Command: `.venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 3. Copy.** From `App/` run (English and Czech in `host_i18n.py`, Vietnamese in `host_vi_i18n.py`):
```bash
python3 - <<'EOF'
def edit(path, pad, rows, which, total):
    lines = open(path, encoding="utf-8").read().split("\n")
    for key, new in rows:
        start = pad + '"' + key + '": '
        hits = [i for i, line in enumerate(lines) if line.startswith(start)]
        assert len(hits) == total, (path, key, hits)
        lines[hits[which]:hits[which] + 1] = [pad + '"' + k + '": "' + v + '",' for k, v in new]
    open(path, "w", encoding="utf-8").write("\n".join(lines))

N, M = "notification.door_code_reissued", "mail.door_code_notice.reissued"
NE, ME = "notification.door_code_reissued_no_email", "mail.door_code_notice.reissued_no_email"

def rows(title, same, mail_subject, mail_lead, by_mail, by_page):
    detail = same + " "
    return [
        (N + ".title", [(N + ".title", title)]),
        (N + ".detail", [(N + ".detail", detail + by_mail), (NE + ".title", title), (NE + ".detail", detail + by_page)]),
        (M + ".subject", [(M + ".subject", mail_subject), (ME + ".subject", mail_subject)]),
        (M + ".body", [(M + ".body", mail_lead + " " + by_mail), (ME + ".body", mail_lead + " " + by_page)]),
    ]

edit("app/host_i18n.py", " " * 8, rows(
    "%(property)s: door code for %(date)s was replaced.",
    "The stay was cancelled and came back, so its door code was replaced.",
    "%(property)s: new door code for the stay from %(date)s",
    "The stay from %(date)s was cancelled and came back, so its door code was replaced.",
    "The guest gets the new code by e-mail.", "The guest sees the new code on their stay page.",
), 0, 2)
edit("app/host_i18n.py", " " * 8, rows(
    "%(property)s: kód ke dveřím pro pobyt od %(date)s byl nahrazen.",
    "Pobyt byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen.",
    "%(property)s: nový kód ke dveřím pro pobyt od %(date)s",
    "Pobyt od %(date)s byl zrušen a znovu obnoven, proto byl jeho kód ke dveřím nahrazen.",
    "Host dostane nový kód e-mailem.", "Host uvidí nový kód na stránce svého pobytu.",
), 1, 2)
edit("app/host_vi_i18n.py", " " * 4, rows(
    "%(property)s: mã cửa cho lượt lưu trú từ %(date)s đã được thay thế.",
    "Lượt lưu trú đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới.",
    "%(property)s: mã cửa mới cho lượt lưu trú từ %(date)s",
    "Lượt lưu trú từ %(date)s đã bị hủy rồi được khôi phục, nên mã cửa của lượt này đã được thay bằng mã mới.",
    "Khách sẽ nhận mã mới qua e-mail.", "Khách sẽ thấy mã mới trên trang lưu trú của họ.",
), 0, 1)
EOF
```
Command: `grep -c 'door_code_reissued\|door_code_notice.reissued' app/host_i18n.py app/host_vi_i18n.py | tail -30` -> `app/host_i18n.py:16` and `app/host_vi_i18n.py:8`. Also `git diff --stat | tail -30` -> 3 files changed.

**Step 4. Tests.** From `App/` run:
```bash
python3 - <<'EOF'
path = "tests/test_door_code_reissue_notice.py"
s = open(path, encoding="utf-8").read()

def swap(old, new, count=1):
    global s
    assert s.count(old) == count, (s.count(old), old)
    s = s.replace(old, new)

swap('"""1156: the host is told once, without the PIN, when a lost door code is made again."""',
     '"""1156, 1160b: the host is told once, without the PIN, after a lost door code is replaced."""')
swap('''def _open_cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind = ? AND reservation_id = ? AND resolved_at IS NULL",
        (KIND, stay),
    )
''', '''def _open_cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind LIKE ? AND reservation_id = ? AND resolved_at IS NULL",
        (KIND + "%", stay),
    )


def _guest_email(stay, email="guest@example.test"):
    """The guest has registered with an e-mail address (the re-issued code goes there)."""
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {"reservation_id": stay, "state": "claimed", "email": email, "token_version": 0,
         "claimed_at": now, "created_at": now, "updated_at": now},
    )
''')
swap('''    lock, stay, row, sent = world
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "info"''', '''    lock, stay, row, sent = world
    _guest_email(stay)
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "info" and cards[0]["kind"] == KIND''')
swap('''    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    assert len(_open_cards(stay)) == 1''', '''    lock, stay, row, sent = world
    _guest_email(stay)
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    assert len(_open_cards(stay)) == 1''')
swap('''    lock, stay, row, sent = world
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))''', '''    lock, stay, row, sent = world
    _guest_email(stay)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))''')
swap('''@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_copy_exists_in_every_host_language(lang):
    for key in (
        "notification.door_code_reissued.title",
        "notification.door_code_reissued.detail",
        "mail.door_code_notice.reissued.subject",
        "mail.door_code_notice.reissued.body",
    ):
        text = host_i18n.translate(lang, key, property="Loft", date="11.09.2026")
        assert text != key and "%(" not in text and "—" not in text
    assert "Loft" in host_i18n.translate(lang, "notification.door_code_reissued.title", property="Loft", date="d")
''', '''def test_a_failed_new_code_sends_no_notice(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _guest_email(stay)
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    lock.fail_create = ttlock.TTLockError("cloud down", kind="transient")
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    assert _row(row)["state"] != door_codes.ISSUED and lock.made == 0
    assert _open_cards(stay) == [] and notices == []


def test_a_stay_without_a_guest_email_says_the_guest_sees_the_code_on_the_stay_page(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["kind"] == KIND + "_no_email"
    assert notices == [(row, "reissued_no_email")]


@pytest.mark.parametrize("lang,mailed", [("en", "e-mail"), ("cs", "e-mailem"), ("vi", "e-mail")])
def test_the_copy_exists_in_every_host_language(lang, mailed):
    for suffix in ("", "_no_email"):
        for key in (
            f"notification.door_code_reissued{suffix}.title",
            f"notification.door_code_reissued{suffix}.detail",
            f"mail.door_code_notice.reissued{suffix}.subject",
            f"mail.door_code_notice.reissued{suffix}.body",
        ):
            text = host_i18n.translate(lang, key, property="Loft", date="11.09.2026")
            assert text != key and "%(" not in text and "—" not in text
            if key.endswith((".detail", ".body")):
                assert (mailed in text) == (suffix == ""), key
    title = host_i18n.translate(lang, "notification.door_code_reissued.title", property="Loft", date="d")
    assert "Loft" in title
''')
open(path, "w", encoding="utf-8").write(s)

path = "tests/test_alert_language.py"
s = open(path, encoding="utf-8").read()
swap('''    "door_code_reissued": {"property": "Loft", "date": "2026-09-11"},
''', '''    "door_code_reissued": {"property": "Loft", "date": "2026-09-11"},
    "door_code_reissued_no_email": {"property": "Loft", "date": "2026-09-11"},
''')
open(path, "w", encoding="utf-8").write(s)
EOF
```
Command: `.venv/bin/python -m pytest tests/test_door_code_reissue_notice.py tests/test_alert_language.py tests/test_0280_short_notifications.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30` -> `66 passed` (the notice file alone is 11: 8 tests, one of them for en, cs and vi).

**Step 5. Commit.** `git add App/app/door_codes.py App/app/host_i18n.py App/app/host_vi_i18n.py App/tests/test_alert_language.py App/tests/test_door_code_reissue_notice.py && git commit -m "1160b: tell the host after the new door code exists, and say the true thing" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 6. Revert-bite, four runs.** Each run, from the repo root: apply the `sed`, run `T`, expect the named result, then `git checkout App/app | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_reissue_notice.py -q --tb=no -rf 2>&1 | tail -30`. After each `sed`, `git diff --stat | tail -30` must show `1 file changed, 1 insertion(+), 1 deletion(-)`.
- (a) Notice even when the new code failed: `sed -i '/^def _reissue_lost_pin/,/^def _revoke_one/ s/^    if issued:$/    if True:/' App/app/door_codes.py` then `T`: `1 failed, 10 passed` (`failed_new_code_sends_no_notice`).
- (b) Always the e-mail wording: `sed -i 's/^        suffix = "" if (info\["guest_email"\] or "").strip() else "_no_email"$/        suffix = ""/' App/app/door_codes.py` then `T`: `1 failed, 10 passed` (`stay_without_a_guest_email`).
- (c) Always the stay-page wording: `sed -i 's/^        suffix = "" if (info\["guest_email"\] or "").strip() else "_no_email"$/        suffix = "_no_email"/' App/app/door_codes.py` then `T`: `3 failed, 8 passed` (`lost_race_re_issue`, `ambiguous_delete_re_issue`, `never_hold_the_pin`).
- (d) Wrong sentence in the stay-page copy: `sed -i '0,/The guest sees the new code on their stay page\./s//The guest gets the new code by e-mail./' App/app/host_i18n.py` then `T`: `1 failed, 10 passed` (`copy_exists_in_every_host_language[en-e-mail]`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 7. Door-codes row, copy tests, lint.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py tests/test_sm_reservation_claim_state.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; only the two `playwright` skips. Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 8. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_reissue_notice.py tests/test_door_code_lookup_pages.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 9. Report.** Write `docs/tasks/1160b-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`go/` (the new keys are in no `i18n_keys.txt`, so `test_go_host_i18n.py` needs no regeneration), `docs/context/*`, migrations, `App/app/alerts.py`, `App/app/mail_notify.py`, `ttlock.py`, the 1160 functions. Hard rules: 2 (no new personal data: the notice holds property name and date only; the guest e-mail is read to choose the wording and never printed), 3, 4, 9.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 2 to 8 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] `test_door_code_reissue_notice.py` is 11 passed; step 4 shows `66 passed`.
- [ ] The four revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The door-codes row and copy tests pass with only the two `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] No old sentence remains in the reissue keys: `grep -n 'door_code_reissued\|door_code_notice.reissued' App/app/host_i18n.py App/app/host_vi_i18n.py | grep -c 'stopped working\|přestal fungovat\|ngừng hoạt động' | tail -30` prints `0`.
- [ ] No UI template or CSS changed, so rule 7 and the UX gate (rule 10) do not apply: the card reuses the existing alert component. State this in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (an `AssertionError` from a script), or 1160 is not in the tree;
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1160b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py` `_reissue_lost_pin` (notice only `if issued`) and `_tell_host_reissued` (the `_no_email` suffix); the cs and vi sentences in `host_i18n.py` / `host_vi_i18n.py` (read them).

## Owner steps

1. Open the pull request for `task/1160b-door-reissue-notice-fix` as a draft after 1160 is merged.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8).
3. A reader of Czech and Vietnamese should check the new sentences in the diff of `host_i18n.py` and `host_vi_i18n.py`.
