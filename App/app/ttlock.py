"""TTLock Open Platform client. The only module that calls TTLock."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from . import config, db

log = logging.getLogger(__name__)

DOOR_CODE_TERMS_VERSION = "2026-10-08"

ALLOWED_PATHS = frozenset(
    {
        "/oauth2/token",
        "/v3/user/register",
        "/v3/user/delete",
        "/v3/key/list",
        "/v3/lock/listKeyboardPwd",
        "/v3/lock/queryDate",
        "/v3/lock/updateDate",
        "/v3/keyboardPwd/get",
        "/v3/keyboardPwd/change",
        "/v3/keyboardPwd/delete",
    }
)
GATEWAY_PATHS = frozenset(
    {
        "/v3/keyboardPwd/change",
        "/v3/keyboardPwd/delete",
        "/v3/lock/queryDate",
        "/v3/lock/updateDate",
    }
)

LOW, NORMAL, CRITICAL = "low", "normal", "critical"

ERROR_KINDS: Dict[int, str] = {
    10003: "auth",
    10004: "auth",
    10011: "reauth",
    10007: "login",
    10000: "config",
    10001: "config",
    10005: "permission",
    30001: "permission",
    -2018: "permission",
    20002: "permission",
    30006: "rate",
    80000: "clock",
    -2012: "offline",
    -4056: "storage",
    90000: "transient",
    1: "transient",
    -3: "bug",
}

_MS_HOUR = 3_600_000
_ADMIN_STATUS = "110401"
_TOP_ADMIN = "110301"


class TTLockError(Exception):
    def __init__(
        self,
        message: str = "",
        *,
        code: Optional[int] = None,
        kind: str = "transient",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind
        self.message = (message or "")[:200]


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def calls_this_month() -> int:
    row = db.query_one(
        "SELECT calls FROM lock_api_usage WHERE month = ? AND provider = 'ttlock'",
        (_month_key(),),
    )
    return int(row["calls"]) if row and row["calls"] is not None else 0


def _budget_allows(priority: str) -> bool:
    used = calls_this_month()
    limit = config.TTLOCK_MONTHLY_CALLS
    if limit <= 0:
        return True
    ratio = used / limit
    if ratio >= 0.95 and priority in (LOW, NORMAL):
        return False
    if ratio >= 0.80 and priority == LOW:
        return False
    return True


def _count_call() -> None:
    month = _month_key()
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'ttlock', 1) "
        "ON CONFLICT (month, provider) DO UPDATE SET calls = calls + 1",
        (month,),
    )


def _parse_response(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        raise TTLockError("non-json response", kind="network") from None
    if not isinstance(data, dict):
        raise TTLockError("bad json shape", kind="network")
    errcode = data.get("errcode")
    if errcode is not None and int(errcode) != 0:
        code = int(errcode)
        errmsg = str(data.get("errmsg", ""))[:200]
        raise TTLockError(errmsg, code=code, kind=ERROR_KINDS.get(code, "transient"))
    return data


def _post(path: str, data: Dict[str, Any], priority: str) -> Dict[str, Any]:
    if path not in ALLOWED_PATHS:
        raise ValueError(f"path not allowed: {path}")
    if not config.DOOR_CODES_ENABLED:
        raise TTLockError("door codes disabled", kind="disabled")
    if not _budget_allows(priority):
        raise TTLockError("monthly call budget", kind="budget")

    body: Dict[str, Any] = {}
    if path == "/oauth2/token":
        body["clientId"] = config.TTLOCK_CLIENT_ID
        body["clientSecret"] = config.TTLOCK_CLIENT_SECRET
    elif path in ("/v3/user/register", "/v3/user/delete"):
        body["clientId"] = config.TTLOCK_CLIENT_ID
        body["clientSecret"] = config.TTLOCK_CLIENT_SECRET
        body["date"] = _now_ms()
    else:
        body["clientId"] = config.TTLOCK_CLIENT_ID
        body["date"] = _now_ms()
    body.update(data)

    timeout = 35 if path in GATEWAY_PATHS else 5
    _count_call()
    url = config.TTLOCK_API_BASE + path
    try:
        resp = requests.post(url, data=body, timeout=timeout)
    except requests.RequestException as exc:
        log.warning("ttlock path=%s priority=%s network", path, priority)
        raise TTLockError(str(exc), kind="network") from exc

    try:
        out = _parse_response(resp)
    except TTLockError as exc:
        log.warning(
            "ttlock path=%s priority=%s errcode=%s errmsg=%s",
            path,
            priority,
            exc.code,
            exc.message[:120],
        )
        raise
    log.info("ttlock path=%s priority=%s errcode=0", path, priority)
    return out


def _md5_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


def enabled() -> bool:
    """The owner has switched door codes on and set the app's TTLock credentials."""
    return bool(
        config.DOOR_CODES_ENABLED and config.TTLOCK_CLIENT_ID and config.TTLOCK_CLIENT_SECRET
    )


def allowed_for(owner_user_id: Optional[int]) -> bool:
    return enabled() and owner_user_id is not None


def locks_of(account: Optional[dict]) -> List[dict]:
    if not account:
        return []
    return json.loads(account["locks_json"] or "[]")


def account_for(owner_user_id: int) -> Optional[dict]:
    return db.query_one(
        "SELECT * FROM lock_account WHERE owner_user_id = ? AND provider = 'ttlock'",
        (owner_user_id,),
    )


def receiver_name(account: dict) -> str:
    return str(account["username"])


def create_account(owner_user_id: int) -> int:
    existing = account_for(owner_user_id)
    if existing:
        return int(existing["id"])
    username = "uh" + secrets.token_hex(8)
    password = secrets.token_urlsafe(18)
    answer = _post(
        "/v3/user/register",
        {
            "username": username,
            "password": _md5_password(password),
        },
        NORMAL,
    )
    prefixed = str(answer["username"])
    now = db.utcnow()
    row_id = db.insert(
        "lock_account",
        {
            "owner_user_id": owner_user_id,
            "provider": "ttlock",
            "username": prefixed,
            "password_enc": db.encrypt_field(password),
            "status": "ok",
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    _login(row_id)
    return row_id


def _login(account_id: int) -> str:
    account = db.query_one("SELECT * FROM lock_account WHERE id = ?", (account_id,))
    if not account:
        raise TTLockError("missing account", kind="config")
    password = db.decrypt_field(account["password_enc"])
    if not password:
        raise TTLockError("missing password", kind="config")
    data = _post(
        "/oauth2/token",
        {
            "username": account["username"],
            "password": _md5_password(password),
        },
        NORMAL,
    )
    expires = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 0)))
    expires_iso = expires.replace(microsecond=0).isoformat()
    db.execute(
        "UPDATE lock_account SET access_token_enc = ?, refresh_token_enc = ?, "
        "token_expires_at = ?, token_version = token_version + 1, updated_at = ? "
        "WHERE id = ?",
        (
            db.encrypt_field(str(data["access_token"])),
            db.encrypt_field(str(data["refresh_token"])),
            expires_iso,
            db.utcnow(),
            account_id,
        ),
    )
    return str(data["access_token"])


def _refresh(account: dict) -> str:
    version = int(account["token_version"])
    refresh = db.decrypt_field(account["refresh_token_enc"])
    if not refresh:
        raise TTLockError("missing refresh token", kind="reauth")
    try:
        data = _post(
            "/oauth2/token",
            {"grant_type": "refresh_token", "refresh_token": refresh},
            NORMAL,
        )
    except TTLockError as exc:
        if exc.kind == "reauth":
            try:
                return _login(int(account["id"]))
            except TTLockError:
                db.execute(
                    "UPDATE lock_account SET status = 'reauth_needed', updated_at = ? WHERE id = ?",
                    (db.utcnow(), account["id"]),
                )
                raise
        raise

    expires = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 0)))
    expires_iso = expires.replace(microsecond=0).isoformat()
    updated = db.execute(
        "UPDATE lock_account SET access_token_enc = ?, refresh_token_enc = ?, "
        "token_expires_at = ?, token_version = ?, updated_at = ? "
        "WHERE id = ? AND token_version = ?",
        (
            db.encrypt_field(str(data["access_token"])),
            db.encrypt_field(str(data["refresh_token"])),
            expires_iso,
            version + 1,
            db.utcnow(),
            account["id"],
            version,
        ),
    )
    if updated == 0:
        account = db.query_one("SELECT * FROM lock_account WHERE id = ?", (account["id"],))
        token = db.decrypt_field(account["access_token_enc"])
        if not token:
            raise TTLockError("missing access token", kind="reauth")
        return token
    return str(data["access_token"])


def _access_token(account_id: int) -> str:
    account = db.query_one("SELECT * FROM lock_account WHERE id = ?", (account_id,))
    if not account:
        raise TTLockError("missing account", kind="config")
    if account["status"] != "ok":
        raise TTLockError("reauth needed", kind="reauth")
    expires_at = account["token_expires_at"]
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc) + timedelta(days=7):
                return _refresh(account)
        except ValueError:
            return _refresh(account)
    token = db.decrypt_field(account["access_token_enc"])
    if not token:
        return _refresh(account)
    return token


def _call(account_id: int, path: str, data: Dict[str, Any], priority: str) -> Dict[str, Any]:
    token = _access_token(account_id)
    payload = {**data, "accessToken": token}
    try:
        return _post(path, payload, priority)
    except TTLockError as exc:
        if exc.kind != "auth":
            raise
        account = db.query_one("SELECT * FROM lock_account WHERE id = ?", (account_id,))
        if not account:
            raise
        _refresh(account)
        token = _access_token(account_id)
        payload = {**data, "accessToken": token}
        try:
            return _post(path, payload, priority)
        except TTLockError as retry_exc:
            if retry_exc.kind == "auth":
                raise TTLockError(retry_exc.message, code=retry_exc.code, kind="auth") from retry_exc
            raise


def stay_window(
    date_from: str,
    date_to: str,
    checkin_hour: int,
    checkout_hour: int,
    buffer_hours: int = 0,
) -> Tuple[int, int]:
    if buffer_hours < 0:
        raise ValueError("buffer_hours")
    if not (0 <= checkin_hour <= 23 and 0 <= checkout_hour <= 23):
        raise ValueError("hour")
    tz = ZoneInfo(config.TIMEZONE)
    start_day = datetime.fromisoformat(date_from).date()
    end_day = datetime.fromisoformat(date_to).date()
    start = datetime(
        start_day.year,
        start_day.month,
        start_day.day,
        checkin_hour,
        0,
        0,
        tzinfo=tz,
    ) - timedelta(hours=buffer_hours)
    end = datetime(
        end_day.year,
        end_day.month,
        end_day.day,
        checkout_hour,
        0,
        0,
        tzinfo=tz,
    ) + timedelta(hours=buffer_hours)
    if end <= start:
        raise ValueError("window")
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _whole_hour(ms: int) -> None:
    if ms % _MS_HOUR != 0:
        raise ValueError("whole hour")


def list_admin_locks(account_id: int) -> List[dict]:
    page_no = 1
    items: List[dict] = []
    while True:
        answer = _call(
            account_id,
            "/v3/key/list",
            {"pageNo": page_no, "pageSize": 1000},
            LOW,
        )
        page_list = answer.get("list") or []
        for raw in page_list:
            status = str(raw.get("keyStatus", ""))
            if status != _ADMIN_STATUS:
                continue
            user_type = str(raw.get("userType", ""))
            key_right = raw.get("keyRight")
            if user_type != _TOP_ADMIN and int(key_right or 0) != 1:
                continue
            items.append(
                {
                    "lock_id": str(raw["lockId"]),
                    "alias": raw.get("lockAlias") or raw.get("lockName") or "",
                    "battery": raw.get("electricQuantity"),
                    "tz_offset_ms": raw.get("timezoneRawOffset"),
                    "key_end": raw.get("endDate"),
                }
            )
        pages = int(answer.get("pages") or 1)
        if page_no >= pages:
            break
        page_no += 1
    now = db.utcnow()
    db.execute(
        "UPDATE lock_account SET locks_json = ?, locks_fetched_at = ?, updated_at = ? WHERE id = ?",
        (json.dumps(items), now, now, account_id),
    )
    return items


def create_period_code(
    account_id: int,
    lock_id: str,
    start_ms: int,
    end_ms: int,
    name: str,
    priority: str = NORMAL,
) -> Tuple[str, str]:
    _whole_hour(start_ms)
    _whole_hour(end_ms)
    answer = _call(
        account_id,
        "/v3/keyboardPwd/get",
        {
            "lockId": int(lock_id),
            "keyboardPwdType": 3,
            "keyboardPwdName": name,
            "startDate": start_ms,
            "endDate": end_ms,
        },
        priority,
    )
    return str(answer["keyboardPwd"]), str(answer["keyboardPwdId"])


def find_code_by_name(
    account_id: int,
    lock_id: str,
    name: str,
) -> Optional[Tuple[str, str]]:
    answer = _call(
        account_id,
        "/v3/lock/listKeyboardPwd",
        {
            "lockId": int(lock_id),
            "searchStr": name,
            "orderBy": 1,
            "pageNo": 1,
            "pageSize": 20,
        },
        NORMAL,
    )
    for raw in answer.get("list") or []:
        if str(raw.get("keyboardPwdName")) == name:
            return str(raw["keyboardPwd"]), str(raw["keyboardPwdId"])
    return None


def change_code_period(
    account_id: int,
    lock_id: str,
    code_id: str,
    start_ms: int,
    end_ms: int,
    priority: str = NORMAL,
) -> None:
    _whole_hour(start_ms)
    _whole_hour(end_ms)
    _call(
        account_id,
        "/v3/keyboardPwd/change",
        {
            "lockId": int(lock_id),
            "keyboardPwdId": int(code_id),
            "startDate": start_ms,
            "endDate": end_ms,
            "changeType": 2,
        },
        priority,
    )


def delete_code(account_id: int, lock_id: str, code_id: str, priority: str = CRITICAL) -> None:
    _call(
        account_id,
        "/v3/keyboardPwd/delete",
        {
            "lockId": int(lock_id),
            "keyboardPwdId": int(code_id),
            "deleteType": 2,
        },
        priority,
    )


def query_lock_time(account_id: int, lock_id: str) -> int:
    answer = _call(account_id, "/v3/lock/queryDate", {"lockId": int(lock_id)}, LOW)
    return int(answer["date"])


def adjust_lock_time(account_id: int, lock_id: str) -> int:
    answer = _call(account_id, "/v3/lock/updateDate", {"lockId": int(lock_id)}, NORMAL)
    return int(answer["date"])


def delete_account(account_id: int) -> None:
    account = db.query_one("SELECT * FROM lock_account WHERE id = ?", (account_id,))
    if not account:
        return
    err: Optional[BaseException] = None
    try:
        _post("/v3/user/delete", {"username": account["username"]}, NORMAL)
    except Exception as exc:
        err = exc
    db.execute("DELETE FROM lock_account WHERE id = ?", (account_id,))
    if err:
        raise err
