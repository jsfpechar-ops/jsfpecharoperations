# 1156: tell the host once when a lost door code is made again

Status: todo
Depends on: 1155 | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 after 1155 is merged | Branch: task/1156-door-reissue-notice
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When `_reissue_lost_pin` makes a new door code (the 1149 lost race, and the 1155 revival, both go through it), the host learns nothing today. Add one `info` alert card per stay and one host mail, both saying the old code had stopped working and the guest gets the new code by e-mail, with no PIN. No migration, no dependency, no new state transition.

## 2. Context

Rules: rule 9 (one explanation in one place, no sentence a button already says); host copy in en, cs and vi (`App/app/host_i18n.py`, `App/app/host_vi_i18n.py`); `tests/test_0280_short_notifications.py`: every `notification.*.title` is at most 60 characters after removing `%(x)s` placeholders; no em dashes (`test_no_em_dashes.py`); no PIN in a notice. Anchors are verbatim from HEAD after 1155; if one is missing, STOP (§8).

**Which channel (decided from the code).** The similar door-code events: `door_code_failed` and `door_code_delayed` raise a `warning` alert (`alerts.raise_alert`, `dedupe_key` per stay) and send a host mail through `mail_notify.door_code_notice(row_id, variant)`; `door_code_delayed` also pushes (`push.door_code_missing`), but that push means "the guest has no code", which is not true here. `cancelled_deleted`, `moved_during_stay` and the other variants are mail only. So this brief uses: an alert card (as the owner asked) plus the mail variant `reissued` through `door_code_notice`. No push. Level `info`, not `warning`: the three warning alerts each ask the host to create a code by hand; here nothing is left to do. If the owner wants it louder, change the one word `"info"` in step 3.

**Once.** The card's `dedupe_key` is `door_code_reissued:<reservation id>`, so a second re-issue of the same stay refreshes the open card instead of adding one. The mail's idempotency key is `door_code_notice:<row id>:reissued`, so one row sends it once. The notice runs before `issue()`; if the new code then fails, the existing `door_code_failed` / `door_code_delayed` alerts and mails already cover it.

**Rule 9.** The alert detail and the mail body say the same fact because they reach the host in two places (same as `door_code_failed`: card title plus reason, mail subject plus body). The card says it in one sentence and the mail says it in one sentence; neither repeats the open-stay button.

**Go.** The new keys are not in any `go/internal/*/i18n_keys.txt`, so `test_go_host_i18n.py` needs no regeneration (it is in §6 only to prove that).

Anchor A, `App/app/door_codes.py` (once): `def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:`
Anchor B, `App/app/door_codes.py` (in `_reissue_lost_pin`):
```python
        actor="system",
        owner_user_id=owner_user_id,
    )
    try:
        issue(row_id, allow_gateway=True)
```
Anchor C, `App/tests/test_alert_language.py`:
```python
    "stay_fee_no_pay_way": {"property": "Loft"},
}
```
Anchors D to G for the copy are the lines the two scripts in steps 4 and 5 look for; each script asserts that its anchor line exists exactly once and stops with an `AssertionError` if not.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | one helper, one call |
| App/app/host_i18n.py | edit | en + cs: alert title and detail, mail subject and body (8 lines) |
| App/app/host_vi_i18n.py | edit | vi: the same 4 lines |
| App/tests/test_alert_language.py | edit | one `STORED_KINDS` entry |
| App/tests/test_door_code_reissue_notice.py | create | 9 tests (6 + 3 languages) |
| docs/tasks/1156-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1155 is in: `grep -c "def _lock_code_state" App/app/door_codes.py | tail -30` -> `1` (else STOP). Then `git switch -c task/1156-door-reissue-notice | tail -30`; expected `Switched to a new branch`.

**Step 2. Helper.** Replace Anchor A with the function below, two blank lines, then the same `def _reissue_lost_pin(...)` line again:
```python
def _tell_host_reissued(row_id: int, owner_user_id: int) -> None:
    """Tell the host once that a lost door code was made again: one info card, one mail.

    The card key is per stay, so a second re-issue refreshes the open card; the mail key
    is per row and variant, so it goes out once. Neither carries the PIN. A failure here
    is logged and never stops the re-issue.
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
            "info",
            "door_code_reissued",
            "Door code was made again",
            dedupe_key=f"door_code_reissued:{info['reservation_id']}",
            apartment_id=info["apartment_id"],
            reservation_id=info["reservation_id"],
            owner_user_id=owner_user_id,
            params={"property": info["internal_name"], "date": info["date_from"]},
        )
        mail_notify.door_code_notice(row_id, "reissued")
    except Exception:
        log.exception("door code %s: host notice after a re-issue failed", row_id)
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 3. Call.** Replace Anchor B with
```python
        actor="system",
        owner_user_id=owner_user_id,
    )
    _tell_host_reissued(row_id, owner_user_id)
    try:
        issue(row_id, allow_gateway=True)
```
Command: `grep -c "_tell_host_reissued" App/app/door_codes.py | tail -30` -> `2`.

**Step 4. English and Czech copy.** From the repo root run this script (it inserts after the line that starts with each quoted prefix):
```python
python3 - <<'EOF'
path = "App/app/host_i18n.py"
def ins(startswith, lines):
    rows = open(path, encoding="utf-8").read().split("\n")
    hits = [i for i, row in enumerate(rows) if row.startswith(startswith)]
    assert len(hits) == 1, (startswith, hits)
    rows[hits[0] + 1:hits[0] + 1] = lines
    open(path, "w", encoding="utf-8").write("\n".join(rows))
pad = " " * 8
ins(pad + '"notification.reason.door_code_delayed": "UbyHost keeps retrying.', [
    pad + '"notification.door_code_reissued.title": "%(property)s: door code for %(date)s was made again.",',
    pad + '"notification.door_code_reissued.detail": "The first code had stopped working. The guest gets the new code by e-mail. Nothing to do.",',
])
ins(pad + '"notification.reason.door_code_delayed": "UbyHost to stále zkouší.', [
    pad + '"notification.door_code_reissued.title": "%(property)s: kód ke dveřím pro pobyt od %(date)s byl vytvořen znovu.",',
    pad + '"notification.door_code_reissued.detail": "První kód přestal fungovat. Host dostane nový kód e-mailem. Nemusíte nic dělat.",',
])
ins(pad + '"mail.door_code_notice.moved_during_stay.body": "The stay from %(date)s changed', [
    pad + '"mail.door_code_notice.reissued.subject": "%(property)s: a new door code for the stay from %(date)s",',
    pad + '"mail.door_code_notice.reissued.body": "The door code of the stay from %(date)s had stopped working, so UbyHost made a new one. The guest gets it by e-mail. You do not need to do anything.",',
])
ins(pad + '"mail.door_code_notice.moved_during_stay.body": "Pobyt od %(date)s změnil', [
    pad + '"mail.door_code_notice.reissued.subject": "%(property)s: nový kód ke dveřím pro pobyt od %(date)s",',
    pad + '"mail.door_code_notice.reissued.body": "Kód ke dveřím pro pobyt od %(date)s přestal fungovat, proto UbyHost vytvořil nový. Host ho dostane e-mailem. Nemusíte nic dělat.",',
])
EOF
```
Command: `grep -c 'door_code_reissued\|door_code_notice.reissued' App/app/host_i18n.py | tail -30` -> `8`.

**Step 5. Vietnamese copy.** From the repo root:
```python
python3 - <<'EOF'
path = "App/app/host_vi_i18n.py"
def ins(startswith, lines):
    rows = open(path, encoding="utf-8").read().split("\n")
    hits = [i for i, row in enumerate(rows) if row.startswith(startswith)]
    assert len(hits) == 1, (startswith, hits)
    rows[hits[0] + 1:hits[0] + 1] = lines
    open(path, "w", encoding="utf-8").write("\n".join(rows))
pad = " " * 4
ins(pad + '"notification.reason.door_code_delayed": "UbyHost vẫn', [
    pad + '"notification.door_code_reissued.title": "%(property)s: mã cửa cho lượt lưu trú từ %(date)s đã được tạo lại.",',
    pad + '"notification.door_code_reissued.detail": "Mã đầu tiên đã ngừng hoạt động. Khách sẽ nhận mã mới qua e-mail. Bạn không cần làm gì.",',
])
ins(pad + '"mail.door_code_notice.moved_during_stay.body": "Lượt lưu trú từ', [
    pad + '"mail.door_code_notice.reissued.subject": "%(property)s: mã cửa mới cho lượt lưu trú từ %(date)s",',
    pad + '"mail.door_code_notice.reissued.body": "Mã cửa của lượt lưu trú từ %(date)s đã ngừng hoạt động, nên UbyHost đã tạo mã mới. Khách sẽ nhận mã qua e-mail. Bạn không cần làm gì.",',
])
EOF
```
Command: `grep -c 'door_code_reissued\|door_code_notice.reissued' App/app/host_vi_i18n.py | tail -30` -> `4`; then from `App/`: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_0280_short_notifications.py tests/test_no_em_dashes.py tests/test_go_host_i18n.py -q --tb=short 2>&1 | tail -30` -> all pass.

**Step 6. Alert-language test.** Replace Anchor C with
```python
    "stay_fee_no_pay_way": {"property": "Loft"},
    "door_code_reissued": {"property": "Loft", "date": "2026-09-11"},
}
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_alert_language.py -q --tb=short 2>&1 | tail -30` -> all pass.

**Step 7. Create `App/tests/test_door_code_reissue_notice.py`** with exactly:
```python
"""1156: the host is told once, without the PIN, when a lost door code is made again."""
from __future__ import annotations

import json

import pytest

from app import alerts, db, door_codes, host_i18n, mail_notify, ttlock
from tests.test_door_code_ambiguous_delete import _delete_then, _tick, world  # noqa: F401
from tests.test_door_code_lost_pin import _revive, _revive_after_lease, _row

KIND = "door_code_reissued"
REAL_NOTICE = mail_notify.door_code_notice  # the world fixture replaces it with a no-op


def _open_cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind = ? AND reservation_id = ? AND resolved_at IS NULL",
        (KIND, stay),
    )


def _owner(row):
    return db.query_one(
        "SELECT a.owner_user_id FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
        "WHERE dc.id = ?",
        (row,),
    )["owner_user_id"]


@pytest.fixture
def notices(monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        door_codes.mail_notify, "door_code_notice", lambda row_id, variant: seen.append((row_id, variant))
    )
    return seen


def test_a_lost_race_re_issue_tells_the_host_once(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "info"
    assert cards[0]["dedupe_key"] == f"{KIND}:{stay}"
    assert notices == [(row, "reissued")]
    assert sent == [row]


def test_an_ambiguous_delete_re_issue_tells_the_host_once(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    assert len(_open_cards(stay)) == 1
    assert notices == [(row, "reissued")]


def test_no_re_issue_means_no_notice(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))  # the stay is still cancelled
    assert _row(row)["state"] == door_codes.ISSUED
    assert _open_cards(stay) == [] and notices == []


def test_a_second_re_issue_keeps_one_open_card(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    owner = _owner(row)
    door_codes._reissue_lost_pin(row, "pid-1", owner)
    new_id = _row(row)["provider_code_id"]
    door_codes._reissue_lost_pin(row, new_id, owner)
    assert len(_open_cards(stay)) == 1
    assert _row(row)["state"] == door_codes.ISSUED


def test_a_failing_notice_does_not_stop_the_re_issue(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world

    def boom(*a, **k):
        raise RuntimeError("alert table locked")

    monkeypatch.setattr(alerts, "raise_alert", boom)
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    assert _row(row)["state"] == door_codes.ISSUED and lock.made == 1


def test_the_card_and_the_mail_never_hold_the_pin(world, monkeypatch):  # noqa: F811
    lock, stay, row, sent = world
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    card = json.dumps(dict(_open_cards(stay)[0]), default=str)
    mails = db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND idempotency_key LIKE ?",
        (stay, "%:reissued"),
    )
    assert len(mails) == 1
    everything = card + json.dumps(dict(mails[0]), default=str)
    assert "4821937" not in everything and "5550000" not in everything
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
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
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_reissue_notice.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_lost_pin.py -q --tb=short 2>&1 | tail -30` -> `23 passed`.

**Step 8. Commit.** `git add App/app/door_codes.py App/app/host_i18n.py App/app/host_vi_i18n.py App/tests/test_alert_language.py App/tests/test_door_code_reissue_notice.py && git commit -m "1156: tell the host once when a lost door code is made again" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 9. Revert-bite, four runs.** Each run, from the repo root: apply the command, run `T`, expect the named result, then `git checkout App/app/door_codes.py | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_reissue_notice.py -q --tb=no 2>&1 | tail -30`. After each change, `git diff --stat | tail -30` must show `1 file changed, 1 insertion(+), 1 deletion(-)`.
- (a) No notice: `sed -i 's/^    _tell_host_reissued(row_id, owner_user_id)$/    pass/' App/app/door_codes.py` then `T`: `4 failed, 5 passed` (`lost_race_re_issue`, `ambiguous_delete_re_issue`, `second_re_issue_keeps_one_open_card`, `never_hold_the_pin`).
- (b) One card per call: `sed -i "s/dedupe_key=f\"door_code_reissued:{info\['reservation_id'\]}\",/dedupe_key=f\"door_code_reissued:{id(info)}\",/" App/app/door_codes.py` then `T`: `2 failed, 7 passed` (`lost_race_re_issue`, `second_re_issue_keeps_one_open_card`).
- (c) A failing notice stops the re-issue: `sed -i '/^def _tell_host_reissued/,/^def _reissue_lost_pin/ s/^    except Exception:$/    except KeyError:/' App/app/door_codes.py` then `T`: `1 failed, 8 passed` (`failing_notice_does_not_stop_the_re_issue`).
- (d) No mail: `sed -i 's/^        mail_notify.door_code_notice(row_id, "reissued")$/        pass/' App/app/door_codes.py` then `T`: `3 failed, 6 passed` (`lost_race_re_issue`, `ambiguous_delete_re_issue`, `never_hold_the_pin`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 10. Door-codes row and copy tests.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; only the two `playwright` skips.

**Step 11. Lint.** From `App/`: `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 12. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_reissue_notice.py tests/test_door_code_lost_pin.py tests/test_door_code_ambiguous_delete.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 13. Report.** Write `docs/tasks/1156-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`go/`, `docs/context/*`, migrations, `App/app/alerts.py` (the card renders through the existing stored-kind path and the default open-stay button), `App/app/mail_notify.py` (the variant needs only the two copy keys). Hard rules: 2 (no new personal data: the notice holds property name and date only), 3, 4, 9.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 2 to 12 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] `test_door_code_reissue_notice.py` is 9 passed (6 tests, one of them run for en, cs, vi).
- [ ] The four revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] `test_0280_short_notifications.py`, `test_alert_language.py`, `test_host_i18n.py`, `test_go_host_i18n.py`, `test_no_em_dashes.py` pass; the door-codes row passes with only the two `playwright` skips; ruff passes.
- [ ] No PIN appears in the card or the mail (`test_the_card_and_the_mail_never_hold_the_pin`).
- [ ] No UI template changed, so rule 7 and the UX gate (rule 10) do not apply: the card reuses the existing alert component. State this in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or a script anchor is not found;
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1156-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py` `_tell_host_reissued` (the swallow-all `except`, the alert level) and the three languages of copy in `host_i18n.py` / `host_vi_i18n.py` (read the cs and vi sentences).

## Owner steps

1. Open the pull request for `task/1156-door-reissue-notice` as a draft after 1155 is merged.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8).
3. Decide if the card should be `warning` instead of `info` (one word, step 3); a reviewer who reads Czech and Vietnamese should check the new sentences.
