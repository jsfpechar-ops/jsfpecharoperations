# TTLock passcode incident check (owner runbook)

Use this when a guest’s code fails and the TTLock app shows **Incorrect passcode** under a name like `UH-1`.

**Do not paste full PINs into chat, git, or screenshots.** Mask as `1454***`.

Related facts: [TTLOCK.md](TTLOCK.md) (24 h first-use, lock clock, record fields). Product choice today: [ttlock-door-codes plan](plans/ttlock-door-codes.md) item 6 — guest is told the first-use deadline; **no host mail, no poll, no auto re-issue**.

## Hypothesis for UH-1 (2026-10-13)

| Fact | Value |
|---|---|
| Passcode name | `UH-1` |
| Digits (from app) | `1454006` |
| Validity start (app) | `2026-10-12 15:00` |
| First-use deadline | start + 24 h → **2026-10-13 15:00** |
| Failed attempts | ~15:24 and ~15:26 on 2026-10-13 |
| App still shows end | `2026-10-15 12:00` (end date alone does **not** prove the code still works) |

Likely cause: type-3 period code never used before start+24h, so TTLock invalidated it. Confirm with the calls below.

## 0. Prep

1. SSH into the production Lightsail host.
2. Go to the compose directory:

```bash
cd /opt/ubyhost/deploy/lightsail
```

3. Confirm the web container is up: `docker compose ps`
4. Each investigation call counts toward the shared monthly TTLock budget. This script is a handful of calls; fine for one incident.

## 1. Run the investigation script (all useful reads)

Paste this whole block. It loads `UH-1` from UbyHost’s DB, then calls TTLock.

```bash
docker compose exec -T ubyhost python - <<'PY'
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import time
import requests

from app import config, db, ttlock

TZ = ZoneInfo(config.TIMEZONE)
NAME = "UH-1"  # change if needed

def mask(pin: str) -> str:
    pin = str(pin or "")
    if len(pin) <= 4:
        return "***"
    return pin[:4] + "***"

def ms_to_local(ms) -> str:
    if ms is None:
        return ""
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

# --- A. Local door_code row ---
# UH-{id} → id is door_code.id
door_id = int(NAME.split("-", 1)[1])
row = db.query_one("SELECT * FROM door_code WHERE id = ?", (door_id,))
if not row:
    # fallback: newest issued on any lock
    row = db.query_one(
        "SELECT * FROM door_code WHERE state = 'issued' ORDER BY id DESC LIMIT 1"
    )
    print("WARN: exact id not found; using newest issued row id=", row and row["id"])
assert row, "no door_code row"

apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
owner_id = apt["owner_user_id"]
account = ttlock.account_for(owner_id)
assert account, "no lock_account for property owner"

pin = db.decrypt_field(row["pin_enc"]) if row["pin_enc"] else None
valid_from = row["valid_from"]
valid_to = row["valid_to"]
# valid_from is ISO UTC text from UbyHost
vf = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
if vf.tzinfo is None:
    vf = vf.replace(tzinfo=timezone.utc)
first_use_by = vf + timedelta(hours=24)
now = datetime.now(timezone.utc)

print("=== A. UbyHost door_code ===")
print("id:", row["id"], "name:", f"UH-{row['id']}")
print("state:", row["state"], "code_kind:", row["code_kind"])
print("lock_id:", row["lock_id"])
print("provider_code_id:", row["provider_code_id"])
print("pin_masked:", mask(pin))
print("valid_from:", valid_from, "→ local", vf.astimezone(TZ))
print("valid_to:", valid_to)
print("first_use_by (UTC):", first_use_by.isoformat())
print("first_use_by (local):", first_use_by.astimezone(TZ))
print("now_utc:", now.isoformat())
print("past_first_use_deadline:", now > first_use_by)
print("issued_at:", row["issued_at"], "notified_at:", row["notified_at"])
print("last_error:", row["last_error"])
print("ttlock_username:", account["username"], "status:", account["status"])

lock_id = str(row["lock_id"])
account_id = int(account["id"])
token = ttlock._access_token(account_id)
base = config.TTLOCK_API_BASE
cid = config.TTLOCK_CLIENT_ID
date_ms = int(time.time() * 1000)

def post(path, extra, timeout=35):
    body = {"clientId": cid, "accessToken": token, "date": date_ms}
    body.update(extra)
    r = requests.post(base + path, data=body, timeout=timeout)
    try:
        return r.json()
    except Exception:
        return {"_http": r.status_code, "_text": r.text[:500]}

# --- B. listKeyboardPwd for this name ---
print("\n=== B. listKeyboardPwd searchStr=%s ===" % f"UH-{row['id']}")
listed = post(
    "/v3/lock/listKeyboardPwd",
    {
        "lockId": int(lock_id),
        "searchStr": f"UH-{row['id']}",
        "orderBy": 1,
        "pageNo": 1,
        "pageSize": 20,
    },
    timeout=10,
)
print(json.dumps(listed, indent=2, default=str)[:4000])
for item in listed.get("list") or []:
    if str(item.get("keyboardPwdName")) != f"UH-{row['id']}":
        continue
    print("--- matched UH row ---")
    print("keyboardPwdId:", item.get("keyboardPwdId"))
    print("keyboardPwd_masked:", mask(item.get("keyboardPwd")))
    print("keyboardPwdType:", item.get("keyboardPwdType"), "isCustom:", item.get("isCustom"))
    print("startDate:", item.get("startDate"), ms_to_local(item.get("startDate")))
    print("endDate:", item.get("endDate"), ms_to_local(item.get("endDate")))
    print("sendDate:", item.get("sendDate"), ms_to_local(item.get("sendDate")))
    print(
        "READ: isCustom=0/false usually means never successfully typed "
        "(random not yet turned into a custom code on the lock)."
    )

# --- C. lock clock (needs gateway / Wi-Fi) ---
print("\n=== C. lock/queryDate ===")
clock = post("/v3/lock/queryDate", {"lockId": int(lock_id)}, timeout=35)
print(json.dumps(clock, indent=2, default=str)[:2000])
if "date" in clock:
    lock_dt = datetime.fromtimestamp(int(clock["date"]) / 1000, tz=timezone.utc)
    drift_s = abs((lock_dt - now).total_seconds())
    print("lock_time_utc:", lock_dt.isoformat())
    print("drift_from_utc_seconds:", int(drift_s))
    print("READ: drift over ~120s can make a valid window fail on the lock.")

# --- D. unlock records for the incident day (not used by UbyHost normally) ---
# Window: local calendar day of the failures, as UTC ms
day = datetime(2026, 10, 13, tzinfo=TZ)
start_ms = int(day.astimezone(timezone.utc).timestamp() * 1000)
end_ms = int((day + timedelta(days=1)).astimezone(timezone.utc).timestamp() * 1000)
print("\n=== D. lockRecord/list ===")
print("start_ms", start_ms, ms_to_local(start_ms), "end_ms", end_ms, ms_to_local(end_ms))
records = post(
    "/v3/lockRecord/list",
    {
        "lockId": int(lock_id),
        "startDate": start_ms,
        "endDate": end_ms,
        "pageNo": 1,
        "pageSize": 100,
    },
    timeout=15,
)
# Redact digits in printed copy
raw = json.dumps(records, indent=2, default=str)
for item in records.get("list") or []:
    kp = str(item.get("keyboardPwd") or "")
    if kp:
        raw = raw.replace(kp, mask(kp))
print(raw[:6000])
print(
    "READ: look for recordType passcode unlocks, success true/false, "
    "username UH-1 vs raw digits, lockDate vs serverDate."
)

# --- E. key/list row for this lock (battery, rights, timezone offset) ---
print("\n=== E. key/list (find this lockId) ===")
keys = post(
    "/v3/key/list",
    {"pageNo": 1, "pageSize": 100},
    timeout=10,
)
for k in keys.get("list") or []:
    if str(k.get("lockId")) != lock_id:
        continue
    safe = {
        "lockId": k.get("lockId"),
        "lockAlias": k.get("lockAlias"),
        "keyRight": k.get("keyRight"),
        "keyStatus": k.get("keyStatus"),
        "electricQuantity": k.get("electricQuantity"),
        "timezoneRawOffset": k.get("timezoneRawOffset"),
        "remoteEnable": k.get("remoteEnable"),
    }
    print(json.dumps(safe, indent=2))
    print("READ: timezoneRawOffset should be 3600000 for Prague standard; other values warn.")

print("\n=== DONE ===")
print("Paste sections A–E back (PINs already masked). Do not paste access tokens.")
PY
```

If `UH-1` is not `door_code.id = 1` on this server, edit `NAME = "UH-1"` is fine — the script derives the id from the suffix. If that row is gone, it falls back to the newest issued code (script prints a WARN).

## 2. Optional single curls (same token)

Only if you prefer one call at a time. First print a short-lived token inside the container (do **not** save it to a file in the repo):

```bash
docker compose exec -T ubyhost python - <<'PY'
from app import db, ttlock
acc = db.query_one("SELECT * FROM lock_account WHERE provider='ttlock' LIMIT 1")
print(ttlock._access_token(int(acc["id"])))
print("clientId=", __import__("app.config", fromlist=["TTLOCK_CLIENT_ID"]).TTLOCK_CLIENT_ID)
print("base=", __import__("app.config", fromlist=["TTLOCK_API_BASE"]).TTLOCK_API_BASE)
PY
```

Then on the host (replace placeholders; `date` = current ms):

```bash
DATE=$(date +%s000)
# B — passcodes named UH-1
curl -sS -X POST "$BASE/v3/lock/listKeyboardPwd" \
  -d "clientId=$CID&accessToken=$TOKEN&date=$DATE&lockId=$LOCK_ID&searchStr=UH-1&orderBy=1&pageNo=1&pageSize=20"

# C — lock clock
curl -sS -X POST "$BASE/v3/lock/queryDate" \
  -d "clientId=$CID&accessToken=$TOKEN&date=$DATE&lockId=$LOCK_ID"

# D — records that day
curl -sS -X POST "$BASE/v3/lockRecord/list" \
  -d "clientId=$CID&accessToken=$TOKEN&date=$DATE&lockId=$LOCK_ID&startDate=$START_MS&endDate=$END_MS&pageNo=1&pageSize=100"
```

## 3. How to read the answers

| Signal | Means |
|---|---|
| `past_first_use_deadline: True` and no successful UH-1 unlock in records | Strong support for 24 h first-use void |
| `isCustom` false / 0 on the UH-1 row | Code was never successfully typed on the lock (still “random” in TTLock’s model) |
| `isCustom` true | Someone unlocked with it at least once; failure then is something else (clock, deleted, wrong digits) |
| Records: `success: false`, username `UH-1` | Digits matched that stored passcode; lock still refused |
| Records: username = raw digits | Typed number matched no named passcode |
| `queryDate` drift large | Lock clock wrong; calibrate in TTLock app (Settings → Lock Time) or unlock once over Bluetooth |
| `listKeyboardPwd` empty for `UH-1` | Code removed from TTLock’s list (deleted / never created on this lock) |
| App shows end date in the future | **Not** proof it works; TTLock still displays the scheduled end after first-use kill |

## 4. What not to call while investigating

- **`keyboardPwd/delete`** — kills the code for good.
- **`keyboardPwd/change`** — can alter the live code; `-3008` would mean unused, but a success rewrites the passcode. Skip unless you intend to fix it.
- **`keyboardPwd/get`** for the same period — may return the same void code; does not revive a first-use-expired type-3 code.
- **`lock/detail`** — returns the super passcode; UbyHost never calls it; you should not either.

## 5. Immediate guest fix (ops, not API proof)

1. In the TTLock app, create a **new** timed passcode for the remaining stay (custom timed codes have **no** 24 h first-use rule).
2. Send the guest the **digits**, never the label `UH-1`.
3. Optionally delete the dead `UH-1` row in the app so records stay clear.

## 6. Paste-back template (for chat / later doc)

```
A door_code: id= state= kind= valid_from= first_use_by= past_deadline=
B listKeyboardPwd: keyboardPwdId= type= isCustom= start= end= pin=1454***
C queryDate: lock_time= drift_s=
D records: (times, username, success, masked pin) …
E key: battery= tz_offset= keyStatus=
```

## 7. Safeguards to decide later (not built)

Today’s plan explicitly skips host notify and re-issue. Possible later options (need an owner decision line in `docs/context/decisions.md` before a brief):

1. **Host mail** when `now > valid_from + 24h`, code still `issued`, and no unlock record for that `provider_code_id` (requires enabling record fetch or callback — privacy trade-off: PINs + arrival times).
2. **Guest page banner** after the first-use deadline: “This code may no longer work; contact the host.”
3. **Host button** “Issue replacement code” (custom `add`) after first-use expiry.
4. **Weekly `queryDate`** + alert on drift (already sketched in TTLOCK.md; not on for all locks).
5. Keep current behaviour; only improve host guide copy.

After you paste results from §1, append a short “Findings” subsection under this file or open a task brief for the chosen safeguard.
