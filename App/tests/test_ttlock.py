"""Task 0009: TTLock client."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from app import config, db, ttlock

SCRIPTED: List[Tuple[str, Dict[str, Any]]] = []
RECORDED: List[Tuple[str, Dict[str, Any], float]] = []


def _fake_post(url, data=None, timeout=5, **kwargs):
    RECORDED.append((url, dict(data or {}), timeout))
    if not SCRIPTED:
        raise AssertionError(f"unexpected post {url}")
    path = url.replace(config.TTLOCK_API_BASE, "")
    expected_path, answer = SCRIPTED.pop(0)
    assert path == expected_path
    return _Resp(answer)


class _Resp:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _ttlock_env(monkeypatch):
    db.init_db()
    db.execute("DELETE FROM lock_account")
    db.execute("DELETE FROM lock_api_usage")
    SCRIPTED.clear()
    RECORDED.clear()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(config, "TTLOCK_MONTHLY_CALLS", 100)
    monkeypatch.setattr(ttlock.requests, "post", _fake_post)
    yield


def _queue(*answers: Tuple[str, Dict[str, Any]]) -> None:
    SCRIPTED.extend(answers)


def test_paths_outside_the_allowlist_are_refused():
    with pytest.raises(ValueError):
        ttlock._post("/v3/lock/detail", {}, ttlock.NORMAL)
    assert not RECORDED
    src = Path(__file__).resolve().parents[1] / "app" / "ttlock.py"
    text = src.read_text()
    for forbidden in (
        "lock/detail",
        "key/get",
        "getUnlockLink",
        "key/send",
        "key/authorize",
        "lock/unlock",
    ):
        assert forbidden not in text


def test_kill_switch_sends_nothing(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock._post("/v3/key/list", {}, ttlock.LOW)
    assert exc.value.kind == "disabled"
    assert not RECORDED


def test_timeouts_are_5_seconds_for_cloud_calls_and_35_for_gateway_calls():
    _queue(("/v3/keyboardPwd/get", {"keyboardPwd": "1", "keyboardPwdId": 1}))
    ttlock._post(
        "/v3/keyboardPwd/get",
        {"accessToken": "t", "lockId": 1},
        ttlock.NORMAL,
    )
    assert RECORDED[-1][2] == 5
    _queue(("/v3/keyboardPwd/delete", {"errcode": 0}))
    ttlock._post(
        "/v3/keyboardPwd/delete",
        {"accessToken": "t", "lockId": 1},
        ttlock.CRITICAL,
    )
    assert RECORDED[-1][2] == 35


def test_create_account_registers_once_and_stores_secrets_encrypted(caplog):
    _queue(
        ("/v3/user/register", {"username": "abcd_uhdeadbeef00000001", "errcode": 0}),
        (
            "/oauth2/token",
            {
                "access_token": "acc",
                "refresh_token": "ref",
                "expires_in": 7776000,
            },
        ),
    )
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-owner",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )
    row_id = ttlock.create_account(owner)
    reg = RECORDED[0][1]
    assert re.match(r"^uh[0-9a-f]{16}$", reg["username"])
    assert len(reg["password"]) == 32
    row = db.query_one("SELECT * FROM lock_account WHERE id = ?", (row_id,))
    assert row["username"] == "abcd_uhdeadbeef00000001"
    assert db.decrypt_field(row["password_enc"]) is not None
    assert db.decrypt_field(row["access_token_enc"]) == "acc"
    assert reg["password"] not in caplog.text
    assert db.decrypt_field(row["password_enc"]) not in caplog.text
    ttlock.create_account(owner)
    assert len(RECORDED) == 2


def test_delete_account_removes_the_ttlock_user_and_the_row():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-del",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_del",
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(("/v3/user/delete", {"errcode": 0}))
    ttlock.delete_account(aid)
    assert RECORDED[0][1]["username"] == "abcd_del"
    assert db.query_one("SELECT id FROM lock_account WHERE id = ?", (aid,)) is None


def test_expired_token_refreshes_once_and_retries():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-ref",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_ref",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("old"),
            "refresh_token_enc": db.encrypt_field("r1"),
            "token_expires_at": "2099-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        ("/v3/key/list", {"errcode": 10004, "errmsg": "expired"}),
        (
            "/oauth2/token",
            {
                "access_token": "newacc",
                "refresh_token": "newref",
                "expires_in": 7_776_000,
            },
        ),
        ("/v3/key/list", {"list": [], "pages": 1}),
    )
    ttlock.list_admin_locks(aid)
    assert len(RECORDED) == 3
    row = db.query_one("SELECT token_version FROM lock_account WHERE id = ?", (aid,))
    assert row["token_version"] == 2


def test_a_second_auth_error_is_raised():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-auth2",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_a2",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("old"),
            "refresh_token_enc": db.encrypt_field("r1"),
            "token_expires_at": "2099-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        ("/v3/key/list", {"errcode": 10004, "errmsg": "expired"}),
        (
            "/oauth2/token",
            {
                "access_token": "newacc",
                "refresh_token": "newref",
                "expires_in": 7_776_000,
            },
        ),
        ("/v3/key/list", {"errcode": 10004, "errmsg": "still bad"}),
    )
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock.list_admin_locks(aid)
    assert exc.value.kind == "auth"


def test_dead_refresh_token_logs_in_again():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-10011",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_11",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("old"),
            "refresh_token_enc": db.encrypt_field("r1"),
            "token_expires_at": "2000-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        ("/oauth2/token", {"errcode": 10011, "errmsg": "bad refresh"}),
        (
            "/oauth2/token",
            {
                "access_token": "acc2",
                "refresh_token": "ref2",
                "expires_in": 3600,
            },
        ),
    )
    token = ttlock._refresh(db.query_one("SELECT * FROM lock_account WHERE id = ?", (aid,)))
    assert token == "acc2"
    row = db.query_one("SELECT status FROM lock_account WHERE id = ?", (aid,))
    assert row["status"] == "ok"


def test_failed_relogin_marks_the_account():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-reauth",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_ra",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("old"),
            "refresh_token_enc": db.encrypt_field("r1"),
            "token_expires_at": "2000-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        ("/oauth2/token", {"errcode": 10011, "errmsg": "bad refresh"}),
        ("/oauth2/token", {"errcode": 10011, "errmsg": "bad login"}),
    )
    with pytest.raises(ttlock.TTLockError):
        ttlock._refresh(db.query_one("SELECT * FROM lock_account WHERE id = ?", (aid,)))
    row = db.query_one("SELECT status FROM lock_account WHERE id = ?", (aid,))
    assert row["status"] == "reauth_needed"


def test_refresh_race_keeps_the_winner():
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-race",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_race",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("winner"),
            "refresh_token_enc": db.encrypt_field("r1"),
            "token_expires_at": "2099-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 2,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        (
            "/oauth2/token",
            {
                "access_token": "loser",
                "refresh_token": "ref",
                "expires_in": 3600,
            },
        ),
    )

    real_execute = db.execute

    def _race_execute(sql, params=()):
        if "token_version = ?" in sql and params[-2] == aid and params[-1] == 2:
            real_execute(
                "UPDATE lock_account SET token_version = 3, access_token_enc = ? WHERE id = ?",
                (db.encrypt_field("winner"), aid),
            )
            return 0
        return real_execute(sql, params)

    with patch.object(db, "execute", side_effect=_race_execute):
        token = ttlock._refresh(db.query_one("SELECT * FROM lock_account WHERE id = ?", (aid,)))
    assert token == "winner"


def test_budget_tiers(monkeypatch):
    db.execute("DELETE FROM lock_api_usage")
    RECORDED.clear()
    SCRIPTED.clear()
    monkeypatch.setattr(config, "TTLOCK_MONTHLY_CALLS", 100)
    month = ttlock._month_key()
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'ttlock', 80)",
        (month,),
    )
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock._post("/v3/key/list", {"accessToken": "t"}, ttlock.LOW)
    assert exc.value.kind == "budget"
    _queue(("/v3/key/list", {"list": [], "pages": 1}))
    ttlock._post("/v3/key/list", {"accessToken": "t"}, ttlock.NORMAL)
    db.execute(
        "UPDATE lock_api_usage SET calls = 95 WHERE month = ? AND provider = 'ttlock'",
        (month,),
    )
    with pytest.raises(ttlock.TTLockError):
        ttlock._post("/v3/key/list", {"accessToken": "t"}, ttlock.NORMAL)
    _queue(("/v3/keyboardPwd/delete", {"errcode": 0}))
    ttlock._post("/v3/keyboardPwd/delete", {"accessToken": "t"}, ttlock.CRITICAL)
    assert ttlock.calls_this_month() == 96


def test_stay_window_across_daylight_saving():
    assert ttlock.stay_window("2026-03-28", "2026-03-30", 15, 11) == (
        1774706400000,
        1774861200000,
    )
    assert ttlock.stay_window("2026-10-24", "2026-10-26", 15, 11) == (
        1792846800000,
        1793008800000,
    )
    assert ttlock.stay_window("2026-03-28", "2026-03-30", 15, 11, buffer_hours=1) == (
        1774702800000,
        1774864800000,
    )
    assert ttlock.stay_window("2026-10-24", "2026-10-26", 15, 11, buffer_hours=1) == (
        1792843200000,
        1793012400000,
    )


def test_code_times_must_be_whole_hours():
    with pytest.raises(ValueError):
        ttlock.create_period_code(1, "9", 1, 3_600_000, "UH-1")


def test_pin_keeps_its_leading_zero():
    _queue(("/v3/keyboardPwd/get", {"keyboardPwd": "0563456", "keyboardPwdId": 10236}))
    answer = ttlock._post(
        "/v3/keyboardPwd/get",
        {"accessToken": "t", "lockId": 1, "startDate": 0, "endDate": 3_600_000},
        ttlock.NORMAL,
    )
    assert str(answer["keyboardPwd"]) == "0563456"
    assert str(answer["keyboardPwdId"]) == "10236"


def test_lock_list_keeps_admin_locks_and_drops_secrets(caplog):
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": "ttlock-list",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    aid = db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "abcd_list",
            "password_enc": db.encrypt_field("pw"),
            "access_token_enc": db.encrypt_field("tok"),
            "refresh_token_enc": db.encrypt_field("ref"),
            "token_expires_at": "2099-01-01T00:00:00+00:00",
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _queue(
        (
            "/v3/key/list",
            {
                "list": [
                    {
                        "lockId": 1,
                        "lockAlias": "A",
                        "keyStatus": "110401",
                        "userType": "110301",
                        "electricQuantity": 90,
                        "timezoneRawOffset": 3600000,
                        "lockData": "SECRET1",
                        "noKeyPwd": "SECRET2",
                    },
                    {
                        "lockId": 2,
                        "lockAlias": "B",
                        "keyStatus": "110401",
                        "userType": "110302",
                        "keyRight": 1,
                        "electricQuantity": 80,
                    },
                    {
                        "lockId": 3,
                        "keyStatus": "110401",
                        "userType": "110302",
                        "keyRight": 0,
                    },
                    {"lockId": 4, "keyStatus": "110405", "userType": "110301"},
                ],
                "pages": 1,
            },
        ),
    )
    locks = ttlock.list_admin_locks(aid)
    assert [l["lock_id"] for l in locks] == ["1", "2"]
    stored = db.query_one("SELECT locks_json FROM lock_account WHERE id = ?", (aid,))[
        "locks_json"
    ]
    assert "SECRET1" not in stored
    assert "SECRET2" not in caplog.text


def test_change_sends_the_new_window_through_the_gateway():
    _queue(("/v3/keyboardPwd/change", {"errcode": 0}))
    ttlock._post(
        "/v3/keyboardPwd/change",
        {
            "accessToken": "t",
            "lockId": 1,
            "keyboardPwdId": 9,
            "startDate": 0,
            "endDate": 3_600_000,
            "changeType": 2,
        },
        ttlock.NORMAL,
    )
    body = RECORDED[-1][1]
    assert body["keyboardPwdId"] == 9
    assert body["changeType"] == "2" or body["changeType"] == 2
    assert "newKeyboardPwd" not in body
    assert RECORDED[-1][2] == 35


def test_error_codes_map_to_kinds():
    for code, kind in (
        (-2012, "offline"),
        (80000, "clock"),
        (30006, "rate"),
        (12345, "transient"),
    ):
        with pytest.raises(ttlock.TTLockError) as exc:
            ttlock._parse_response(_Resp({"errcode": code, "errmsg": "x"}))
        assert exc.value.kind == kind
