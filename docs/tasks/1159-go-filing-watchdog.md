# 1159: Go port of the filing watchdog selection (`at_risk_stays`, `unknown_risk_stays`, `heartbeat_url`), parity-checked against Python

Status: todo
Depends on: 1132, 1153 (merged) | Base commit: 4e56401 | Branch: claude/go-filing-watchdog
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `calendar.AtRiskStays`, `UnknownRiskStays` and `FilingHeartbeatURL`, a Go port of the read-only half of App/app/filing_watchdog.py, plus a golden file written by the real Python so the two cannot drift. GO-DL step D, part 1 of 2 (tier A, filing path); the mails, push, digest and `run()` are brief 1159b (split: both halves do not fit one Haiku session).

**Behind a switch:** nothing calls the new code (no scheduler, `go/cmd/`, job kind, env var or route); brief 1132 §10 E adds the job kind and the switch. Production is unchanged. Files are only added: no failing-first step.

## 2. Context

Rules (AGENTS.md): 1 filing correctness (§8 stops on any mismatch); 2 no new personal-data field, no outbound request (the heartbeat URL is only built); 3 no guest data (fixture: `example.test`); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, as 1153/1157.

**Package `go/internal/calendar`** (next to `watch.go`, `dsr_due.go`). Reused unchanged: `watchAnchor` (`reservation_deadline_anchor`), `deadlines.LocalNow`, `deadlines.ReportingDeadline`, `validation.GuestIsReportable`, `ubyport.ParseStoredUTC` (naive reads as UTC); in the test `dbPool`, `watchSeed`.

**What Python does (App/app/filing_watchdog.py 69-222 and 358-367), and how the Go copies it:**

- `at_risk_stays(now, include_awaiting_retry)`: one query over unfiled guests (not `sent`, nationality set, not archived) of watched stays (active, not archived, property on, not demo), `ORDER BY r.id`, with `submission` and `user_account` (workspace). Non-reportable guests dropped in code; the rest grouped per stay in first-seen order (`unfiled`, `awaiting_retry_guests`). Per stay: anchor (no anchor: skipped), `due = reporting_deadline(anchor)`, skipped when `due - local > 24 h`; `overdue = due < local`; `awaiting_retry = not overdue and awaiting_retry_guests == unfiled`, left out unless `include_awaiting_retry`. Sorted by (deadline, reservation_id). Go: same SQL (`$1 = 'sent'`), same grouping, `sort.SliceStable`.
- `_awaiting_retry`: state `outcome_unknown`, `retried_at` empty, and `0 <= now_utc - finished_at <= RETRY_GRACE`; an unreadable `finished_at` (NULL reads as the string "None") is not awaiting. `RETRY_GRACE = 2 x max(1, int(os.environ.get("UBYHOST_SUBMIT_SWEEP_MINUTES", "10")))` minutes, read at import: unset is 10, a set value `int()` refuses ("abc", and "" too) stops Python from starting. Go: `watchdogRetryGrace(lookupEnv)` (`os.LookupEnv` in production, so unset and empty differ) trims, `strconv.Atoi` (sign allowed), else an error naming the variable, which `AtRiskStays` returns before any query: the run fails loudly. `watchdogAwaitingRetry` is the window. An `auto_resend` batch (WP31) is not special-cased in either: awaiting inside the grace, at risk after.
- `unknown_risk_stays(now)`: watched stays with no live guest, `date_from` between `today - 28 days` and `today` (ISO text comparison; `today` is the Prague date), arrival `date.fromisoformat(date_from[:10])`, kept when the deadline is less than 24 h away and passed at most 7 days ago; `no_guests = True`, `unfiled = 0`. Go: `UnknownRiskStays`, `NoGuests: true`.
- `heartbeat_url(at_risk)`: the URL stripped of spaces and trailing `/`; "", `<url>/fail` or `<url>`.
- `at_risk_mailed_at` is a `*string`: NULL and "" stay distinct (1159b treats both as not mailed, as Python does).

**Parity mechanism** (pattern of 1153/1157): `App/scripts/filing_watchdog_golden.py` seeds a throwaway SQLite database (30 stays, 31 guests, 9 submissions; entities and push devices are for 1159b), asks `at_risk_stays(include_awaiting_retry=True)`, `at_risk_stays()` and `unknown_risk_stays()` at four instants (2026-09-17 10:00, 10:05, 11:00 UTC and 2026-09-20 11:05 UTC), and records `heartbeat_url` for five URL values, into `go/internal/calendar/testdata/filing_watchdog_golden.json`. `filing_watchdog_test.go` seeds a fresh PostgreSQL from that file (skips without `UBYHOST_TEST_DATABASE_URL`; CI sets it) and compares every stay field; `App/tests/test_filing_watchdog_golden.py` fails when the committed file is stale. Cases: 12 h left, overdue, 36 h left (overdue on 09-20); awaiting inside, exactly at (20 min) and after the grace; overdue while awaiting; one guest awaiting, one not; batch resent once; `auto_resend` inside and past the grace; `finished_at` future, naive, NULL; error/blocked/pending counted, sent not; Czech (any case) not counted, a Czech-only stay in neither list (never sets the heartbeat); nationality empty/NULL; anchor from a Czech guest's `stay_from`; no anchor; cancelled, archived, demo, switched-off not watched; unknown risk: no guest, only an archived guest, 6.5 days overdue (kept, dropped at 09-20), over 7 days overdue (dropped), arrives today, not arrived; stamp set, "" and NULL; no owner; a name needing HTML escaping; heartbeat with no, one and two trailing slashes, spaces, empty.

**Verified by the brief writer** on a scratch copy of 4e56401: §4 hashes, deterministic (also with `TZ=America/New_York`), gofmt/vet clean, Go tests ok **on local PostgreSQL 16**, Python test green on SQLite and PostgreSQL; four mutations (grace lower bound, 8-day window, `!Overdue`, archived guests) each failed a test.

Anchors that must exist verbatim (step 0):
- `func watchAnchor(ctx context.Context, pool *pgxpool.Pool, stay stayRow) (time.Time, bool, error) {` in go/internal/calendar/watch.go
- `func watchSeed(t *testing.T, pool *pgxpool.Pool, g watchGolden) map[int64]bool {` in go/internal/calendar/watch_test.go
- `func dbPool(t *testing.T) *pgxpool.Pool {` in go/internal/calendar/handler_test.go
- `func ParseStoredUTC(v string) (time.Time, bool) { return parseStoredUTC(v) }` in go/internal/ubyport/collect.go
- `func ReportingDeadline(checkIn time.Time) time.Time {` and `func LocalNow(now time.Time) time.Time {` in go/internal/deadlines/deadlines.go
- `func GuestIsReportable(nationality string) bool {` in go/internal/validation/validation.go
- `def at_risk_stays(`, `def unknown_risk_stays(now: Optional[datetime] = None) -> List[Dict[str, Any]]:` and `def heartbeat_url(at_risk: bool) -> str:` in App/app/filing_watchdog.py

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/filing_watchdog_golden.py` | create | seeds fixed rows, runs the real selection, writes the golden file |
| `go/internal/calendar/testdata/filing_watchdog_golden.json` | create (generated by the script) | seed + expected stays per instant + heartbeat URLs |
| `go/internal/calendar/filing_watchdog.go` | create | `AtRiskStays`, `UnknownRiskStays`, `FilingHeartbeatURL`, the port |
| `go/internal/calendar/filing_watchdog_test.go` | create | Go vs golden on PostgreSQL, plus unit tests without a database |
| `App/tests/test_filing_watchdog_golden.py` | create | fails when the golden file is stale |
| `docs/tasks/1159-report.md` | create | the report (§9) |
| `docs/tasks/1159-go-filing-watchdog.md` | edit (1 line) | `Status: review` |

No other file may change. No test-map or status edit: both are at their token cap; §6 names the commands.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/go-filing-watchdog` (if not: `git checkout claude/go-filing-watchdog`); `ls App/scripts/filing_watchdog_golden.py go/internal/calendar/filing_watchdog.go go/internal/calendar/filing_watchdog_test.go App/tests/test_filing_watchdog_golden.py go/internal/calendar/testdata/filing_watchdog_golden.json 2>&1 | tail -30` says "No such file" five times; `grep -cF` of each anchor in §2 in its file prints 1. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Any anchor missing or file present: STOP (§8). Last, write the helper that copies code block k of a brief byte for byte (pasting by hand is allowed too; the hash decides):

```bash
cat > /tmp/extract_block.py <<'EOF'
import re, sys
src, k, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = open(src, encoding='utf-8').read()
blocks = re.findall(r'^```(?:python|go)\n(.*?)^```$', text, re.S | re.M)
open(dest, 'w', encoding='utf-8').write(blocks[k - 1])
EOF
```

1. Create `App/scripts/filing_watchdog_golden.py` (sha256 `4b162294c0ee7823f519d28fe713cef2197add024e15a104ccc04a24fc099172`) = block 1 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159-go-filing-watchdog.md 1 App/scripts/filing_watchdog_golden.py && sha256sum App/scripts/filing_watchdog_golden.py | tail -3`.
```python
"""Write go/internal/calendar/testdata/filing_watchdog_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/filing_watchdog_golden.py

It seeds a throwaway SQLite database with the fixed rows in SEED and, for each
instant in INSTANTS, records what filing_watchdog.at_risk_stays (with the
stays awaiting the automatic resend) and unknown_risk_stays return. It also
records heartbeat_url for each URL in HEARTBEATS. Nothing is written to the
database after the seed, so the instants are independent.
go/internal/calendar/filing_watchdog_test.go seeds PostgreSQL from the same
file and compares. App/tests/test_filing_watchdog_golden.py fails when this
file is stale. Brief 1159b's run golden imports SEED and _seed from here.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "filing_watchdog_golden.json"

# filing_watchdog reads these at import time (RETRY_GRACE is 2 x 10 minutes).
GOLDEN_ENV = {
    "UBYHOST_SUBMIT_SWEEP_MINUTES": "10",
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_OPERATOR_EMAIL": "ops@example.test",
    "UBYHOST_WEB_PUSH": "1",
    "UBYHOST_HEARTBEAT_FILING_URL": "",
}

STAMP = "2026-09-01T00:00:00+00:00"

_GUEST_COLUMNS = ["id", "reservation_id", "surname", "nationality", "submit_state",
                  "submission_id", "stay_from", "is_lead", "archived_at",
                  "created_at", "updated_at"]


def _guest(gid, rid, nationality="DEU", state="pending", submission=None,
           stay_from=None, archived=None):
    return [gid, rid, "Test", nationality, state, submission, stay_from, 0, archived,
            STAMP, STAMP]


def _stay(rid, apt, date_from, *, status="active", source="host", archived=None,
          mailed=None):
    return [rid, apt, f"u{rid}", date_from, "2026-09-30", status, source, archived,
            mailed, STAMP, STAMP]


def _sub(sid, state, finished, *, retried=None, mode="auto"):
    return [sid, 1, STAMP, mode, state, finished, retried]


# T0 is 2026-09-17 10:00 UTC, 12:00 in Prague (a Thursday). The deadline of an
# arrival on 09-15 is 09-17 23:59:59 (12 h left at T0), of 09-16 is 09-18
# 23:59:59 (36 h, not yet at risk), of 09-14 is 09-16 23:59:59 (overdue). The
# comment on each stay says what T0 must do with it.
SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "created_at"],
        "rows": [
            [1, "host-one@example.test", "x", "host", STAMP],
            [2, "host-two@example.test", "x", "host", STAMP],
        ],
    },
    {
        "table": "legal_entity",
        "columns": ["id", "name", "contact_email", "created_at"],
        "rows": [
            [1, "Entity One", " Contact.One@Example.TEST ", STAMP],
            [2, "Entity Blank", None, STAMP],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "legal_entity_id", "internal_name", "city_en",
                    "uby_name", "permalink_token", "active", "created_at"],
        "rows": [
            [1, 1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP],
            [2, 1, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP],
            [3, 2, None, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP],
            [4, 1, 1, 'Byt <Žižkov> & "Co"', "Praha", "UBY", "tok4", 1, STAMP],
            [5, None, 2, "", "Brno", "UBY", "tok5", 1, STAMP],
        ],
    },
    {
        "table": "submission",
        "columns": ["id", "apartment_id", "created_at", "mode", "state", "finished_at",
                    "retried_at"],
        "rows": [
            _sub(301, "outcome_unknown", "2026-09-17T09:45:00+00:00"),
            _sub(302, "outcome_unknown", "2026-09-17T09:55:00+00:00"),
            _sub(303, "outcome_unknown", "2026-09-17T09:50:00+00:00", mode="auto_resend"),
            _sub(304, "outcome_unknown", "2026-09-17T09:50:00+00:00",
                 retried="2026-09-17T09:58:00+00:00"),
            _sub(305, "outcome_unknown", "2026-09-17T09:30:00+00:00", mode="auto_resend"),
            _sub(306, "outcome_unknown", "2026-09-17T10:30:00+00:00"),
            _sub(307, "outcome_unknown", "2026-09-17T09:55:00"),
            _sub(308, "outcome_unknown", None),
            _sub(309, "error", "2026-09-17T09:55:00+00:00"),
        ],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "uid", "date_from", "date_to", "status", "source",
                    "archived_at", "at_risk_mailed_at", "created_at", "updated_at"],
        "rows": [
            _stay(201, 1, "2026-09-15"),  # at risk, 1 unfiled (lower-case cze not counted)
            _stay(202, 1, "2026-09-10"),  # overdue, 1 unfiled (CZE pending, DEU sent)
            _stay(203, 1, "2026-09-16"),  # 36 h left: not yet; overdue on 09-20
            _stay(204, 1, "2026-09-15"),  # awaiting resend until 10:05, at risk at 11:00
            _stay(205, 1, "2026-09-14"),  # overdue: awaiting does not hide it
            _stay(206, 1, "2026-09-15"),  # one guest awaiting, one not: at risk
            _stay(207, 1, "2026-09-15"),  # batch already resent once: at risk
            _stay(208, 1, "2026-09-15"),  # auto_resend batch past the grace: at risk
            _stay(209, 1, "2026-09-15", mailed="2026-09-16T08:00:00+00:00"),  # mailed before
            _stay(210, 3, "2026-09-15"),  # owner 2, no legal entity
            _stay(211, 1, "2026-09-15", status="cancelled"),  # not watched
            _stay(212, 1, "2026-09-15", archived="2026-09-16"),  # not watched
            _stay(213, 1, "2026-09-15", source="demo"),  # not watched
            _stay(214, 2, "2026-09-15"),  # property switched off
            _stay(215, 1, "2026-09-15"),  # only an archived guest: unknown risk
            _stay(216, 1, "2026-09-15"),  # Czech only: neither list
            _stay(217, 1, "2026-09-08"),  # no guests, 6.5 days overdue: unknown risk
            _stay(218, 1, "2026-09-07"),  # no guests, over 7 days overdue: dropped
            _stay(219, 1, "2026-09-17"),  # no guests, arrives today, 4 days left: no
            _stay(220, 1, "2026-09-18"),  # no guests, not arrived: no
            _stay(221, 1, "2026-09-15"),  # nationality empty and NULL: neither list
            _stay(222, 1, "2026-09-16"),  # anchor from a guest's stay_from (09-14): overdue
            _stay(223, 1, "bad"),  # no anchor: skipped
            _stay(224, 4, "2026-09-15"),  # property name needs escaping
            _stay(225, 5, "2026-09-15"),  # no owner, entity without address
            _stay(226, 1, "2026-09-15"),  # finished in the future: not awaiting
            _stay(227, 1, "2026-09-15"),  # naive finished_at reads as UTC: awaiting
            _stay(228, 1, "2026-09-15"),  # finished_at NULL: not awaiting
            _stay(229, 1, "2026-09-15", mailed=""),  # empty stamp counts as not mailed
            _stay(230, 3, "2026-09-12"),  # no guests, owner 2, overdue: unknown risk
        ],
    },
    {
        "table": "guest",
        "columns": _GUEST_COLUMNS,
        "rows": [
            _guest(1, 201, "deu"),
            _guest(2, 201, "cze"),
            _guest(3, 202, "USA", state="error"),
            _guest(4, 202, "CZE"),
            _guest(5, 202, "DEU", state="sent"),
            _guest(6, 203),
            _guest(7, 204, submission=301),
            _guest(8, 205, submission=302),
            _guest(9, 206, submission=303),
            _guest(10, 206, "FRA", state="blocked"),
            _guest(11, 207, submission=304),
            _guest(12, 208, submission=305),
            _guest(13, 209),
            _guest(14, 210, "UKR"),
            _guest(15, 211),
            _guest(16, 212),
            _guest(17, 213),
            _guest(18, 214),
            _guest(19, 215, archived="2026-09-16"),
            _guest(20, 216, "CZE"),
            _guest(21, 221, ""),
            _guest(22, 221, None),
            _guest(23, 222),
            _guest(24, 222, "CZE", state="sent", stay_from="2026-09-14"),
            _guest(25, 223),
            _guest(26, 224, "ITA"),
            _guest(27, 225, "ESP"),
            _guest(28, 226, submission=306),
            _guest(29, 227, submission=307),
            _guest(30, 228, submission=308),
            _guest(31, 229, submission=309, state="error"),
        ],
    },
    {
        "table": "push_subscription",
        "columns": ["id", "user_account_id", "endpoint_hash", "endpoint_enc", "p256dh_enc",
                    "auth_enc", "lang", "device", "created_at", "last_seen_at"],
        "rows": [
            [501, 1, "h501", "x", "x", "x", "en", "phone", STAMP, STAMP],
            [502, 2, "h502", "x", "x", "x", "en", "phone", STAMP, STAMP],
            [503, 2, "h503", "x", "x", "x", "en", "laptop", STAMP, STAMP],
        ],
    },
]

# T0, T0 + 5 min (204's batch exactly at the 20-minute grace), T0 + 1 h (past
# the grace), and Sunday 2026-09-20 13:05 in Prague (09-16 arrivals overdue).
INSTANTS = [
    "2026-09-17T10:00:00+00:00",
    "2026-09-17T10:05:00+00:00",
    "2026-09-17T11:00:00+00:00",
    "2026-09-20T11:05:00+00:00",
]

HEARTBEATS = [
    "https://hc.example.test/ping/abc",
    "https://hc.example.test/ping/abc/",
    "  https://hc.example.test/ping/abc//  ",
    "",
    "   ",
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def stay_record(stay: dict) -> dict:
    """One stay as the golden records it; the Go test builds the same map."""
    return {
        "reservation_id": stay["reservation_id"],
        "date_from": stay["date_from"],
        "apartment_id": stay["apartment_id"],
        "property": stay["property"],
        "legal_entity_id": stay["legal_entity_id"],
        "owner_user_id": stay["owner_user_id"],
        "workspace": stay["workspace"],
        "mailed_at": stay["mailed_at"],
        "unfiled": stay["unfiled"],
        "awaiting_retry_guests": stay.get("awaiting_retry_guests", 0),
        "awaiting_retry": bool(stay.get("awaiting_retry")),
        "no_guests": bool(stay.get("no_guests")),
        "arrival": stay["arrival"].isoformat(),
        "deadline": stay["deadline"].isoformat(),
        "overdue": bool(stay["overdue"]),
    }


def render() -> str:
    """Seed a fresh database, ask both questions per instant, return the JSON text."""
    from app import config, db, filing_watchdog

    db.init_db()
    _seed(db)
    instants = []
    for at in INSTANTS:
        now = datetime.fromisoformat(at)
        every = filing_watchdog.at_risk_stays(now, include_awaiting_retry=True)
        instants.append({
            "at": at,
            "at_risk": [stay_record(s) for s in every],
            "at_risk_default": [s["reservation_id"] for s in filing_watchdog.at_risk_stays(now)],
            "unknown_risk": [stay_record(s) for s in filing_watchdog.unknown_risk_stays(now)],
        })
    saved = config.HEARTBEAT_FILING_URL
    heartbeats = []
    try:
        for url in HEARTBEATS:
            config.HEARTBEAT_FILING_URL = url
            for at_risk in (False, True):
                heartbeats.append({
                    "url": url,
                    "at_risk": at_risk,
                    "ping": filing_watchdog.heartbeat_url(at_risk),
                })
    finally:
        config.HEARTBEAT_FILING_URL = saved
    golden = {
        "env": GOLDEN_ENV,
        "retry_grace_minutes": int(filing_watchdog.RETRY_GRACE.total_seconds() // 60),
        "seed": SEED,
        "instants": instants,
        "heartbeats": heartbeats,
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def prepare_env() -> None:
    """The process environment both golden scripts need, before ``app`` is imported."""
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "filing_watchdog_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.update(GOLDEN_ENV)
    sys.path.insert(0, str(APP))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    prepare_env()
    main()
```

   From `App/`: `.venv/bin/python scripts/filing_watchdog_golden.py 2>&1 | tail -3` ends with `wrote .../go/internal/calendar/testdata/filing_watchdog_golden.json`. Then from the repo root `sha256sum App/scripts/filing_watchdog_golden.py go/internal/calendar/testdata/filing_watchdog_golden.json | tail -30` must print `4b162294c0ee7823f519d28fe713cef2197add024e15a104ccc04a24fc099172` and `f181775bbc3d18927806c6870f7c19ad41e497335c985e6d0adaf0409882067a`. A different script hash: your paste differs; fix it from the block above (never edit the JSON by hand). Commit "1159 step 1" (both files).

2. Create `go/internal/calendar/filing_watchdog.go` (sha256 `21884e766b0b5d700f40c8581960b4ee590e36328d273821ce56f2dfd9ef4978`) = block 2 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159-go-filing-watchdog.md 2 go/internal/calendar/filing_watchdog.go && sha256sum go/internal/calendar/filing_watchdog.go | tail -3`.
```go
// filing_watchdog.go is the selection half of App/app/filing_watchdog.py (WP23):
// which stays may miss their police deadline (at_risk_stays, with
// _awaiting_retry and RETRY_GRACE), which empty stays are an unknown risk
// (unknown_risk_stays), and the dead-man switch URL (heartbeat_url). The mail,
// push and digest half is brief 1159b. Nothing calls this yet: brief 1132 §10 E
// adds the job kind and the Python/Go switch. testdata/filing_watchdog_golden.json,
// written by App/scripts/filing_watchdog_golden.py, is the parity check.
package calendar

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// watchdogAtRiskWindow is AT_RISK_WINDOW.
	watchdogAtRiskWindow = 24 * time.Hour
	// watchdogUnknownMaxOverdue is UNKNOWN_RISK_MAX_OVERDUE.
	watchdogUnknownMaxOverdue = 7 * 24 * time.Hour
	// watchdogSweepMinutesDefault is config.SUBMIT_SWEEP_MINUTES's default.
	watchdogSweepMinutesDefault = 10
)

// watchdogAtRiskSQL is the unfiled guests with a nationality on watched stays.
// nationality and submit_state are plain columns: nothing is decrypted. $1 is
// reporting.SENT. The submission columns feed _awaiting_retry.
const watchdogAtRiskSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
	r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id,
	COALESCE(u.username, ''), g.nationality,
	COALESCE(s.state, ''), COALESCE(s.retried_at, ''), COALESCE(s.finished_at, '')
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	JOIN guest g ON g.reservation_id = r.id
	LEFT JOIN submission s ON s.id = g.submission_id
	LEFT JOIN user_account u ON u.id = a.owner_user_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND g.archived_at IS NULL AND g.submit_state != $1
	AND g.nationality IS NOT NULL AND g.nationality != ''
	ORDER BY r.id`

// watchdogUnknownSQL is the watched stays with no live guest that arrived
// between $2 and $1 (ISO dates, compared as text as Python does).
const watchdogUnknownSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
	r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id,
	COALESCE(u.username, '')
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	LEFT JOIN user_account u ON u.id = a.owner_user_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND r.date_from <= $1 AND r.date_from >= $2
	AND NOT EXISTS (SELECT 1 FROM guest g
	WHERE g.reservation_id = r.id AND g.archived_at IS NULL)
	ORDER BY r.id`

// WatchdogStay is one stay dict of filing_watchdog.py. Arrival is a date at
// midnight UTC; Deadline is the naive Prague deadline (deadlines.ReportingDeadline).
// MailedAt is at_risk_mailed_at (nil when NULL; "" counts as not mailed too).
type WatchdogStay struct {
	ReservationID       int64
	DateFrom            string
	ApartmentID         int64
	Property            string
	LegalEntityID       *int64
	OwnerUserID         *int64
	Workspace           string
	MailedAt            *string
	Unfiled             int
	AwaitingRetryGuests int
	AwaitingRetry       bool
	NoGuests            bool
	Arrival             time.Time
	Deadline            time.Time
	Overdue             bool
}

// watchdogRetryGrace is RETRY_GRACE: two sweep intervals of
// UBYHOST_SUBMIT_SWEEP_MINUTES, at least one minute each. Like Python's
// int(os.environ.get(name, "10")): unset means 10; a set value is stripped and
// must be an integer (an optional sign is allowed), else it is an error, as
// Python refuses to start. A set but empty value is an error too (int("")).
func watchdogRetryGrace(lookupEnv func(string) (string, bool)) (time.Duration, error) {
	minutes := watchdogSweepMinutesDefault
	if raw, ok := lookupEnv("UBYHOST_SUBMIT_SWEEP_MINUTES"); ok {
		n, err := strconv.Atoi(strings.TrimSpace(raw))
		if err != nil {
			return 0, fmt.Errorf("UBYHOST_SUBMIT_SWEEP_MINUTES is not an integer: %w", err)
		}
		minutes = n
	}
	if minutes < 1 {
		minutes = 1
	}
	return time.Duration(2*minutes) * time.Minute, nil
}

// watchdogAwaitingRetry is _awaiting_retry: the guest is on an outcome_unknown
// batch not resent yet, which finished no more than grace ago (and not in the
// future). A naive finished_at reads as UTC; an unreadable one is not awaiting.
func watchdogAwaitingRetry(state, retriedAt, finishedAt string, current time.Time, grace time.Duration) bool {
	if state != "outcome_unknown" || retriedAt != "" {
		return false
	}
	finished, ok := ubyport.ParseStoredUTC(finishedAt)
	if !ok {
		return false
	}
	age := current.Sub(finished)
	return age >= 0 && age <= grace
}

// sortWatchdogStays is found.sort(key=(deadline, reservation_id)).
func sortWatchdogStays(stays []WatchdogStay) {
	sort.SliceStable(stays, func(i, j int) bool {
		if !stays[i].Deadline.Equal(stays[j].Deadline) {
			return stays[i].Deadline.Before(stays[j].Deadline)
		}
		return stays[i].ReservationID < stays[j].ReservationID
	})
}

// AtRiskStays is at_risk_stays: every stay with a reportable guest UbyPort has
// not accepted whose deadline is less than 24 hours away or passed, soonest
// deadline first. A stay whose every unfiled guest awaits the automatic resend
// and whose deadline has not passed carries AwaitingRetry and is left out
// unless includeAwaitingRetry. at is the instant of the run. lookupEnv is
// os.LookupEnv in production; an unreadable sweep interval fails the call.
func AtRiskStays(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time, includeAwaitingRetry bool) ([]WatchdogStay, error) {
	grace, err := watchdogRetryGrace(lookupEnv)
	if err != nil {
		return nil, fmt.Errorf("filing watchdog: %w", err)
	}
	local := deadlines.LocalNow(at)
	current := at.UTC()
	rows, err := pool.Query(ctx, watchdogAtRiskSQL, "sent")
	if err != nil {
		return nil, err
	}
	var order []int64
	grouped := map[int64]*WatchdogStay{}
	for rows.Next() {
		var s WatchdogStay
		var nationality, subState, subRetried, subFinished string
		if err := rows.Scan(&s.ReservationID, &s.DateFrom, &s.MailedAt, &s.ApartmentID, &s.Property,
			&s.LegalEntityID, &s.OwnerUserID, &s.Workspace, &nationality,
			&subState, &subRetried, &subFinished); err != nil {
			rows.Close()
			return nil, err
		}
		if !validation.GuestIsReportable(nationality) {
			continue
		}
		stay, ok := grouped[s.ReservationID]
		if !ok {
			stay = &s
			grouped[s.ReservationID] = stay
			order = append(order, s.ReservationID)
		}
		stay.Unfiled++
		if watchdogAwaitingRetry(subState, subRetried, subFinished, current, grace) {
			stay.AwaitingRetryGuests++
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var found []WatchdogStay
	for _, id := range order {
		stay := grouped[id]
		// The deadline runs from the earliest guest arrival, as everywhere else.
		anchor, ok, err := watchAnchor(ctx, pool, stayRow{id: stay.ReservationID, dateFrom: stay.DateFrom})
		if err != nil {
			return nil, err
		}
		if !ok {
			continue
		}
		due := deadlines.ReportingDeadline(anchor)
		if due.Sub(local) > watchdogAtRiskWindow {
			continue
		}
		stay.Arrival = anchor
		stay.Deadline = due
		stay.Overdue = due.Before(local)
		stay.AwaitingRetry = !stay.Overdue && stay.AwaitingRetryGuests == stay.Unfiled
		if stay.AwaitingRetry && !includeAwaitingRetry {
			continue
		}
		found = append(found, *stay)
	}
	sortWatchdogStays(found)
	return found, nil
}

// UnknownRiskStays is unknown_risk_stays: watched stays with no live guest
// whose guests have arrived (arrival today or earlier in Prague) and whose
// deadline, run from the stay's own arrival, is less than 24 hours away or
// passed at most seven days ago. Soonest deadline first; NoGuests is set.
func UnknownRiskStays(ctx context.Context, pool *pgxpool.Pool, at time.Time) ([]WatchdogStay, error) {
	local := deadlines.LocalNow(at)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
	// The deadline is at most a few working days after arrival; this bounds the scan.
	earliest := today.AddDate(0, 0, -7-21)
	rows, err := pool.Query(ctx, watchdogUnknownSQL, today.Format("2006-01-02"), earliest.Format("2006-01-02"))
	if err != nil {
		return nil, err
	}
	var found []WatchdogStay
	for rows.Next() {
		var s WatchdogStay
		if err := rows.Scan(&s.ReservationID, &s.DateFrom, &s.MailedAt, &s.ApartmentID, &s.Property,
			&s.LegalEntityID, &s.OwnerUserID, &s.Workspace); err != nil {
			rows.Close()
			return nil, err
		}
		head := s.DateFrom
		if len(head) > 10 {
			head = head[:10]
		}
		arrival, err := time.Parse("2006-01-02", head)
		if err != nil {
			continue
		}
		due := deadlines.ReportingDeadline(arrival)
		if due.Sub(local) > watchdogAtRiskWindow || local.Sub(due) > watchdogUnknownMaxOverdue {
			continue
		}
		s.NoGuests = true
		s.Arrival = arrival
		s.Deadline = due
		s.Overdue = due.Before(local)
		found = append(found, s)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	sortWatchdogStays(found)
	return found, nil
}

// FilingHeartbeatURL is heartbeat_url: the URL to ping for this run, or ""
// when UBYHOST_HEARTBEAT_FILING_URL is empty. healthchecks.io semantics: the
// base URL reports success, <url>/fail reports a failure.
func FilingHeartbeatURL(getenv func(string) string, atRisk bool) string {
	url := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_HEARTBEAT_FILING_URL")), "/")
	if url == "" {
		return ""
	}
	if atRisk {
		return url + "/fail"
	}
	return url
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` is clean. Commit "1159 step 2".

3. Create `go/internal/calendar/filing_watchdog_test.go` (sha256 `21f36464acd80ad07ed1027c69e0ed01fa8f20c8de1755c5a8298c04b90ff011`) = block 3 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159-go-filing-watchdog.md 3 go/internal/calendar/filing_watchdog_test.go && sha256sum go/internal/calendar/filing_watchdog_test.go | tail -3`.
```go
package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

// watchdogStayRecord is one stay as App/scripts/filing_watchdog_golden.py
// stay_record writes it.
type watchdogStayRecord struct {
	ReservationID       int64   `json:"reservation_id"`
	DateFrom            string  `json:"date_from"`
	ApartmentID         int64   `json:"apartment_id"`
	Property            string  `json:"property"`
	LegalEntityID       *int64  `json:"legal_entity_id"`
	OwnerUserID         *int64  `json:"owner_user_id"`
	Workspace           string  `json:"workspace"`
	MailedAt            *string `json:"mailed_at"`
	Unfiled             int     `json:"unfiled"`
	AwaitingRetryGuests int     `json:"awaiting_retry_guests"`
	AwaitingRetry       bool    `json:"awaiting_retry"`
	NoGuests            bool    `json:"no_guests"`
	Arrival             string  `json:"arrival"`
	Deadline            string  `json:"deadline"`
	Overdue             bool    `json:"overdue"`
}

type watchdogInstant struct {
	At            string               `json:"at"`
	AtRisk        []watchdogStayRecord `json:"at_risk"`
	AtRiskDefault []int64              `json:"at_risk_default"`
	UnknownRisk   []watchdogStayRecord `json:"unknown_risk"`
}

type watchdogHeartbeat struct {
	URL    string `json:"url"`
	AtRisk bool   `json:"at_risk"`
	Ping   string `json:"ping"`
}

type watchdogGolden struct {
	Env               map[string]string   `json:"env"`
	RetryGraceMinutes int                 `json:"retry_grace_minutes"`
	Seed              []watchSeedTable    `json:"seed"`
	Instants          []watchdogInstant   `json:"instants"`
	Heartbeats        []watchdogHeartbeat `json:"heartbeats"`
}

func loadWatchdogGolden(t *testing.T) watchdogGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/filing_watchdog_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchdogGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Instants) < 4 || len(g.Seed) == 0 || len(g.Heartbeats) == 0 {
		t.Fatal("golden file has too few instants, no seed or no heartbeats")
	}
	return g
}

// watchdogGetenv serves the golden's environment, as the Python process saw it.
func watchdogGetenv(env map[string]string) func(string) string {
	return func(k string) string { return env[k] }
}

// watchdogLookup is os.LookupEnv over the same map: a missing key is unset.
func watchdogLookup(env map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := env[k]
		return v, ok
	}
}

// watchdogRecord is stay_record for a Go stay.
func watchdogRecord(s WatchdogStay) watchdogStayRecord {
	return watchdogStayRecord{
		ReservationID:       s.ReservationID,
		DateFrom:            s.DateFrom,
		ApartmentID:         s.ApartmentID,
		Property:            s.Property,
		LegalEntityID:       s.LegalEntityID,
		OwnerUserID:         s.OwnerUserID,
		Workspace:           s.Workspace,
		MailedAt:            s.MailedAt,
		Unfiled:             s.Unfiled,
		AwaitingRetryGuests: s.AwaitingRetryGuests,
		AwaitingRetry:       s.AwaitingRetry,
		NoGuests:            s.NoGuests,
		Arrival:             s.Arrival.Format("2006-01-02"),
		Deadline:            s.Deadline.Format("2006-01-02T15:04:05"),
		Overdue:             s.Overdue,
	}
}

func watchdogJSON(t *testing.T, v any) string {
	t.Helper()
	b, err := json.MarshalIndent(v, "", " ")
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// TestWatchdogStaysMatchPython seeds the golden rows and compares AtRiskStays
// (with and without the stays awaiting the resend) and UnknownRiskStays with
// what filing_watchdog.py returned for the same rows at every golden instant.
func TestWatchdogStaysMatchPython(t *testing.T) {
	g := loadWatchdogGolden(t)
	lookup := watchdogLookup(g.Env)
	grace, err := watchdogRetryGrace(lookup)
	if err != nil || int(grace/time.Minute) != g.RetryGraceMinutes {
		t.Fatalf("retry grace %v (%v), Python %d min", grace, err, g.RetryGraceMinutes)
	}
	pool := dbPool(t)
	watchSeed(t, pool, watchGolden{Seed: g.Seed})
	ctx := context.Background()
	for _, in := range g.Instants {
		at, err := time.Parse(time.RFC3339, in.At)
		if err != nil {
			t.Fatal(err)
		}
		every, err := AtRiskStays(ctx, pool, lookup, at, true)
		if err != nil {
			t.Fatalf("%s at risk: %v", in.At, err)
		}
		got := []watchdogStayRecord{}
		for _, s := range every {
			got = append(got, watchdogRecord(s))
		}
		want := in.AtRisk
		if want == nil {
			want = []watchdogStayRecord{}
		}
		if a, b := watchdogJSON(t, got), watchdogJSON(t, want); a != b {
			t.Errorf("%s at-risk stays differ from Python\n got:\n%s\nwant:\n%s", in.At, a, b)
		}
		plain, err := AtRiskStays(ctx, pool, lookup, at, false)
		if err != nil {
			t.Fatalf("%s at risk (default): %v", in.At, err)
		}
		ids := []int64{}
		for _, s := range plain {
			ids = append(ids, s.ReservationID)
		}
		wantIDs := in.AtRiskDefault
		if wantIDs == nil {
			wantIDs = []int64{}
		}
		if a, b := watchdogJSON(t, ids), watchdogJSON(t, wantIDs); a != b {
			t.Errorf("%s at-risk ids without awaiting differ: got %s want %s", in.At, a, b)
		}
		unknown, err := UnknownRiskStays(ctx, pool, at)
		if err != nil {
			t.Fatalf("%s unknown risk: %v", in.At, err)
		}
		gotU := []watchdogStayRecord{}
		for _, s := range unknown {
			gotU = append(gotU, watchdogRecord(s))
		}
		wantU := in.UnknownRisk
		if wantU == nil {
			wantU = []watchdogStayRecord{}
		}
		if a, b := watchdogJSON(t, gotU), watchdogJSON(t, wantU); a != b {
			t.Errorf("%s unknown-risk stays differ from Python\n got:\n%s\nwant:\n%s", in.At, a, b)
		}
	}
}

// TestFilingHeartbeatURLMatchesPython needs no database.
func TestFilingHeartbeatURLMatchesPython(t *testing.T) {
	g := loadWatchdogGolden(t)
	for _, h := range g.Heartbeats {
		env := map[string]string{"UBYHOST_HEARTBEAT_FILING_URL": h.URL}
		if got := FilingHeartbeatURL(watchdogGetenv(env), h.AtRisk); got != h.Ping {
			t.Errorf("heartbeat %q at_risk=%v: got %q, Python %q", h.URL, h.AtRisk, got, h.Ping)
		}
	}
}

// TestWatchdogRetryGrace is RETRY_GRACE = 2 x max(1, int(SUBMIT_SWEEP_MINUTES))
// minutes: unset is 10; a set value Python's int() refuses is an error.
func TestWatchdogRetryGrace(t *testing.T) {
	ok := map[string]time.Duration{
		"10": 20 * time.Minute, " 7 ": 14 * time.Minute, "+3": 6 * time.Minute,
		"0": 2 * time.Minute, "-5": 2 * time.Minute,
	}
	for raw, want := range ok {
		got, err := watchdogRetryGrace(watchdogLookup(map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": raw}))
		if err != nil || got != want {
			t.Errorf("sweep %q: grace %v (%v), want %v", raw, got, err, want)
		}
	}
	if got, err := watchdogRetryGrace(watchdogLookup(map[string]string{})); err != nil || got != 20*time.Minute {
		t.Errorf("unset: grace %v (%v), want 20m", got, err)
	}
	for _, raw := range []string{"abc", "", "  ", "1.5", "10m"} {
		env := map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": raw}
		if _, err := watchdogRetryGrace(watchdogLookup(env)); err == nil {
			t.Errorf("sweep %q: want an error, as Python int() raises", raw)
		}
		// AtRiskStays refuses before it touches the database.
		_, err := AtRiskStays(context.Background(), nil, watchdogLookup(env), time.Now(), true)
		if err == nil || !strings.Contains(err.Error(), "UBYHOST_SUBMIT_SWEEP_MINUTES") {
			t.Errorf("sweep %q: AtRiskStays error %v, want one naming the variable", raw, err)
		}
	}
}

// TestWatchdogAwaitingRetry pins the grace window ends without a database.
func TestWatchdogAwaitingRetry(t *testing.T) {
	now := time.Date(2026, 9, 17, 10, 0, 0, 0, time.UTC)
	grace := 20 * time.Minute
	cases := []struct {
		state, retried, finished string
		want                     bool
	}{
		{"outcome_unknown", "", "2026-09-17T09:40:00+00:00", true},
		{"outcome_unknown", "", "2026-09-17T09:39:59+00:00", false},
		{"outcome_unknown", "", "2026-09-17T10:00:00+00:00", true},
		{"outcome_unknown", "", "2026-09-17T10:00:01+00:00", false},
		{"outcome_unknown", "", "2026-09-17T11:50:00+02:00", true},
		{"outcome_unknown", "", "2026-09-17 09:50:00", true},
		{"outcome_unknown", "2026-09-17T09:55:00+00:00", "2026-09-17T09:50:00+00:00", false},
		{"error", "", "2026-09-17T09:50:00+00:00", false},
		{"outcome_unknown", "", "", false},
		{"outcome_unknown", "", "None", false},
	}
	for _, c := range cases {
		if got := watchdogAwaitingRetry(c.state, c.retried, c.finished, now, grace); got != c.want {
			t.Errorf("%+v: got %v", c, got)
		}
	}
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ -count=1 2>&1 | tail -30` is ok (the DB test skips here; step 5 runs it). Commit "1159 step 3".

4. Create `App/tests/test_filing_watchdog_golden.py` (sha256 `5eff8eba372153fa6a11815a34c274d0afbb70def093c2063e4612e4b0fd3dab`) = block 4 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159-go-filing-watchdog.md 4 App/tests/test_filing_watchdog_golden.py && sha256sum App/tests/test_filing_watchdog_golden.py | tail -3`.
```python
"""go/internal/calendar/filing_watchdog_test.go reads go/internal/calendar/testdata/filing_watchdog_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "filing_watchdog_golden", APP_DIR / "scripts" / "filing_watchdog_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filing_watchdog_golden_matches_python_watchdog(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "filing-watchdog-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"reservation_id"') >= 60
```

   From `App/`: `.venv/bin/python -m pytest tests/test_filing_watchdog_golden.py tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30` passes. Commit "1159 step 4".

5. Go DB test locally (3 calls at most; if PostgreSQL cannot start, say "CI only" with the reason in the report). As root with PostgreSQL 16 installed:

```bash
P=/var/tmp/pg1159 && mkdir -p $P && chown postgres $P && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $P/data -A trust -U postgres" >/dev/null && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $P/data -o '-p 55439 -k $P' -l $P/log -w start" 2>&1 | tail -3
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres go test ./internal/calendar/ -run 'Watchdog|FilingHeartbeat' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

   Expected: four `--- PASS` lines (stays, heartbeat, retry grace, awaiting) and `ok`. A `--- SKIP` means the variable was not seen. A FAIL: STOP (§8), paste the first 30 lines of the diff into the report. Then write the report (§9), set this brief's `Status: review`, commit "1159 step 5".

## 5. Do not touch

`App/app/`, `App/migrations_pg/`, every existing file in `go/internal/`, `go/cmd/` (incl. `go/cmd/ubyhost-web/main.go`), `go/go.mod`, `go/go.sum`, `docs/ENVIRONMENT.md`, `docs/context/`, `.github/`, every file not in §3. No job kind, env var, route, migration or dependency. Hard rules 1-5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ -count=1 2>&1 | tail -30` (the DB test skips without `UBYHOST_TEST_DATABASE_URL`; step 5 runs it).
From `App/` (Filing row of the [test-map](../context/test-map.md), narrowed to the watchdog): `.venv/bin/python -m pytest tests/test_filing_watchdog_golden.py tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30`.
Golden freshness: from `App/`, `.venv/bin/python scripts/filing_watchdog_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 1's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The five sha256 values in steps 1-4 match.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, `go test ./internal/calendar/ -count=1` ok.
- [ ] Step 5: the four tests PASS on local PostgreSQL, or "CI only" with the reason.
- [ ] From `App/`: the two pytest files pass and the freshness command leaves `git status --short ../go` empty.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat 4e56401..HEAD | tail -30`: only §3 paths and brief 1159b.
- [ ] Five commits "1159 step 1" to "1159 step 5" on `claude/go-filing-watchdog`; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor in step 0 is not found, or a §3 file already exists;
- the generated golden hash differs while the script hash matches (the Python behaviour moved: never edit the JSON, the Python or the Go to make it match);
- any Go/Python parity test fails (`TestWatchdogStaysMatchPython`, `TestFilingHeartbeatURLMatchesPython`): a mismatch is a filing-correctness question for the orchestrator, never fixed by the executor; or any test fails twice;
- a change to Python behaviour, a migration, or SQL that is not plain PostgreSQL seems needed;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1159-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat 4e56401..HEAD | tail -10`; 2. each §6 command and step 5 with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none expected: nothing is wired).

## Risk list (for the reviewer)

Read `go/internal/calendar/filing_watchdog.go` against App/app/filing_watchdog.py 57-222 and 358-367 line by line: both WHERE clauses and date bounds, the reportable filter, grouping, counts, the 24 h window (`>` skips), the 7-day drop (unknown risk only), strict `<` for overdue, `awaiting_retry` only when not overdue and all unfiled await, `0 <= age <= grace`, the sweep-minutes error, the sort, the heartbeat strip. Then the golden script (seed covers each §2 case) and that the test does not skip in CI (`--- PASS: TestWatchdogStaysMatchPython` in the Go job log).

Known and accepted (not 1:1; unreachable with what the app writes):
- `int()` also takes `1_0` and non-ASCII digits; Go refuses them (loudly).
- `finished_at`: `fromisoformat` reads a few more forms than `ParseStoredUTC`; `db.utcnow()` output both read. Unreadable = at risk at once in Go (never later).
- Python accepts a naive `now` as Prague time; the Go functions take an instant. Brief E passes `time.Now()`.

## Owner steps

None: nothing calls the new code until brief 1132 §10 E.
