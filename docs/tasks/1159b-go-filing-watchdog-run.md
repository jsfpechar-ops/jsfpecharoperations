# 1159b: Go port of the filing watchdog actions (`notify_hosts`, `send_operator_digest`, `run`) and its two mails, parity-checked against Python

Status: todo
Depends on: 1159 and 1159-fix-1 (merged) | Base commit: the main commit that merged 1159 | Branch: claude/go-filing-watchdog-run
Report: docs/tasks/1159b-report.md
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `calendar.RunFilingWatchdog` (with `NotifyHosts` and `SendOperatorDigest`) and `mail.BuildDeadlineAtRisk` / `mail.BuildDeadlineDigest`, a Go port of the acting half of App/app/filing_watchdog.py and of the two WP23 mails in App/app/mail_notify.py, plus a golden file written by the real Python `run()` over ten consecutive runs so the two cannot drift. This is GO-DL step D, part 2 of 2 (tier A, highest risk: it writes host mails, pushes and the at-risk stamp); part 1 (brief 1159) ported the selection this builds on.

**Behind a switch, by construction:** nothing calls the new code. No scheduler, no `go/cmd/`, no job kind, no env var, no route. Brief 1132 §10 E adds the `deadlines` job kind, the Python/Go switch and the heartbeat ping; until then production runs only the Python watchdog. This brief adds files only and changes no existing code.

## 2. Context

Rules that apply (AGENTS.md): 1 filing correctness (the watchdog is what tells a host a police deadline is about to be missed: §8 stops on any mismatch); 2 no new personal-data field and no outbound request (rows are only queued in `email_outbox` / `push_outbox`, which the existing senders deliver; the digest names no guest; the fixture uses `example.test`); 3 no guest data in the repo; 4 no new dependency; 5 plain PostgreSQL through `pgxpool`.

**Reused, unchanged:** from 1159 `AtRiskStays`, `UnknownRiskStays`, `FilingHeartbeatURL`, `WatchdogStay`, `watchdogGetenv`, `watchdogJSON` (go/internal/calendar); `ubyport.EnqueueMail` (`mail.enqueue`: existing key returns its id, payload `{"text", "html", "lang": "en"}` with ensure_ascii), `ubyport.QueuePush` (`push.notify`: one row per device, key `<kind>:<key>:<device>`, off when `UBYHOST_WEB_PUSH` is 0/false/no or there is no owner), `ubyport.AlertParams` (go/internal/ubyport/notify.go, effects.go); `shell`, `blockHeading`, `blockParagraph`, `blockButton`, `blockSection`, `blockNote`, `esc`, `normaliseLanguage` and the colour constants (go/internal/mail/submission_problem.go); in the test `dbPool`, `watchSeed`. **Newly ported:** `mail_notify.build_deadline_at_risk`, `build_deadline_digest`, `_digest_section`, `_block_fact`, `_block_link`, `_block_table`, `_deadline_text`, `_entity_contact_email`, `push.deadline_at_risk`, `filing_watchdog.notify_hosts`, `send_operator_digest`, `run`. The English strings are copied from `host_i18n.STRINGS["en"]` (`mail.deadline_at_risk.*`, `mail.deadline_digest.*`) and the guest catalogue's `mail_link_fallback`; like the other Go mails, only `en` is ported (`HOST_MAIL_LANGUAGE` is `en`).

**What Python does (App/app/filing_watchdog.py 224-355), and how the Go copies it:**

- `notify_hosts(stays + unknown, now)`: per stay not mailed yet (`mailed_at` truthy: skip; NULL and "" are both "not mailed"), first `push.deadline_at_risk` (params property, date DD.MM.YYYY, deadline "DD.MM.YYYY HH:MM", each cut to 120 characters; key = reservation id; URL `/reservations/<id>`; never raises), then in a try block: the entity contact address (`legal_entity.contact_email` through `mail.normalise_email`; none: next stay, no stamp), the mail content, `mail.enqueue(kind deadline_at_risk, key deadline_at_risk:<id>, reservation, apartment, owner)`; no outbox id (mail backend not console/ses): next stay, no stamp; else `UPDATE reservation SET at_risk_mailed_at = <now UTC, seconds, +00:00> WHERE id = ? AND at_risk_mailed_at IS NULL` and count it. Any exception is logged and the loop goes on. Go: `NotifyHosts`, `watchdogPush`, `watchdogMailStay`; errors are logged with the reservation id only (no address, no text) and the loop goes on. Addresses: `normalise_email` is `email.utils.parseaddr` plus a regex. parseaddr is a full RFC 2822 parser (comments, quoted names, groups: `mailto:a@b.test` reads as `a@b.test`) whose strict mode changed between Python releases (CI and the image run 3.12, dev 3.13), so a 1:1 port is not feasible. Go's `watchdogAddress` reads exactly two forms, a plain address and `Name <address>` with a name free of `"()<>[]:;@\,.`, and for those gives Python's result (no difference in 200,000 generated strings on Python 3.11, 3.12 and 3.13). Any other value that is not blank returns "" flagged unreadable: `slog.Error` with the reservation id (for the operator address, the variable name), the stay stays unmailed (no stamp) and is retried every run. Go never mails an address Python would not. The existing `ubyport.NormaliseEmail` is not used: the golden showed it mails `mailto:a@b.test` as written and accepts `a@b.test>`, which Python refuses.
- A stay whose stamp is "" is counted again on every run (the UPDATE never matches) but the idempotency key stops a second mail: the golden has that case (stay 229) and Go keeps the quirk.
- `send_operator_digest(stays, now, unknown)`: nothing when both lists are empty; `to = normalise(OPERATOR_EMAIL)` (env `UBYHOST_OPERATOR_EMAIL`, stripped, default `support@ubyhost.com`; Go: `watchdogAddress`), none: False; reads setting `filing_watchdog_digest_sent_at`; a readable aware stamp with `0 <= now - stamp < 72 h` blocks it (a future stamp does not, an unreadable one counts as none, a stamp without an offset raises in Python: Go returns an error, which `run` logs); builds the digest; enqueues kind `deadline_digest`, key `deadline_digest:<stamp>`, no reservation/apartment/owner; no outbox id: False; else stores the stamp and returns True.
- `run(now)`: `at_risk_stays(include_awaiting_retry=True)` (its failure, or an unreadable `UBYHOST_SUBMIT_SWEEP_MINUTES`, is the only error returned; Go's `RunFilingWatchdog` takes `lookupEnv`, `os.LookupEnv` in production), split into stays and awaiting; `unknown_risk_stays` failure logged and treated as empty (it must not silence the real check or its heartbeat); `notify_hosts`; digest failure logged, digest 0. Returns at_risk, unknown_risk, awaiting_retry, host_mails, digest. Only at_risk decides the heartbeat (the scheduler's `at_risk > 0 or not watch_ok` is brief E's job).
- Base URLs: links use `UBYHOST_APP_BASE_URL`, else `UBYHOST_PUBLIC_BASE_URL`; the logo uses `UBYHOST_PUBLIC_BASE_URL`, both without a trailing slash (as cancelled_notify.go reads them).

**Parity mechanism:** `App/scripts/filing_watchdog_run_golden.py` imports `SEED` and `_seed` from 1159's script, then calls the real `filing_watchdog.run` ten times in order (each run sees what the previous wrote), changing before some runs the digest setting, the mail backend and the operator address as config would read them from the environment. After each run it records the result, `heartbeat_url(at_risk > 0)`, the `email_outbox` rows the run added (every column but timestamps; the payload as its sha256 plus the readable text), the `push_outbox` rows added (params compared as values), every stay's `at_risk_mailed_at` and the digest setting; plus two digest renders no run reaches, and `normalise_email` for 29 contact forms (`CONTACTS`; each result the same on Python 3.11, 3.12 and 3.13). `filing_watchdog_run_test.go` replays the same on PostgreSQL and compares; `App/tests/test_filing_watchdog_run_golden.py` fails when the committed file is stale. Cases covered: mail switched off (pushes queued, no mail, no stamp, no digest, no setting); mail on (host mails, stamps, first digest); stays awaiting the resend get no mail until the grace is over; already mailed (no mail, no push); no legal entity and an entity without address (push only, no stamp, retried next run); no owner (mail, no push); a property name needing HTML escaping and non-ASCII (`Byt <Žižkov> & "Co"`); the no-guests variant of the host mail; digest within 72 h (none), after 73 h, exactly at 72 h (sent), future stamp (sent), naive stamp (digest failed, 0, setting kept), unreadable stamp (sent), unusable operator address (none), empty operator variable (sent to support@ubyhost.com); heartbeat `/fail` while known reportable stays are at risk; the digest with 51 and 52 rows ("And 1 more stays." / "And 2 more stays.") and with unknown stays only; contact forms: plain, spaced upper case, `Name <a>`, `<a>`, a non-ASCII name, `+` and `'` in the local part, 254 and 255 characters (7 read like Python), and 20 forms Go flags (quoted or commented names, `mailto:`, a dot in the name, an unclosed `<`, a non-ASCII local part, two addresses, no dot in the domain, a domain literal, trailing text); blank values (neither); a bad `UBYHOST_SUBMIT_SWEEP_MINUTES` failing the run.

**Verified by the brief writer** on a scratch copy of 4e56401 with 1159's files applied: the files below with the sha256 values in §4, generation deterministic (same hash with `TZ=America/New_York`), `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/calendar/ ./internal/mail/` ok **with a local PostgreSQL 16** (`--- PASS: TestRunFilingWatchdogMatchesPython`, `--- PASS: TestBuildDeadlineDigestMatchesPython`), the Python test green on SQLite and on PostgreSQL, and these mutations each made a Go test fail: digest window without the `age >= 0` bound, `<=` instead of `<` 72 h, naive stamp read as none, the mail-off check removed, "" stamp counted as mailed, a wrong push date, one style in `blockFact`, 51 digest rows, the fallback label, unknown stays not notified, `watchdogAddress` replaced by `ubyport.NormaliseEmail`.

Anchors that must exist verbatim (step 0):
- the 1159 files with these sha256: `App/scripts/filing_watchdog_golden.py` `d751ed495c29245c040402b06e7e644aa19b6026663058ae577edaa48d97317f`, `go/internal/calendar/filing_watchdog.go` `b61e9aefa8214498ff911309f13babe1321fb5908d34d15bd132c5596e7f2b74`, `go/internal/calendar/filing_watchdog_test.go` `6e64ea523cde046c7a5e70006d1ffcac1f41797a2b3e08290c83ed6e7f358cff`
- `func EnqueueMail(ctx context.Context, pool *pgxpool.Pool, m OutboxMail) (int64, error) {`, `func QueuePush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,` in go/internal/ubyport/notify.go
- `func shell(publicBaseURL, pageTitle, preheader string, blocks, footerLines []string) string {`, `func blockNote(label, body string) string {` and `func blockSection(label, body string) string {` in go/internal/mail/submission_problem.go
- `def notify_hosts(stays: List[Dict[str, Any]], now: Optional[datetime] = None) -> int:`, `def send_operator_digest(` and `def run(now: Optional[datetime] = None) -> Dict[str, int]:` in App/app/filing_watchdog.py; `def build_deadline_at_risk(` and `def build_deadline_digest(` in App/app/mail_notify.py

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/filing_watchdog_run_golden.py` | create | ten real `run()` calls on 1159's seed, writes the golden file |
| `go/internal/calendar/testdata/filing_watchdog_run_golden.json` | create (generated by the script) | per run: result, heartbeat, new outbox rows, stamps, setting; digest renders |
| `go/internal/mail/deadline_at_risk.go` | create | `BuildDeadlineAtRisk`, `BuildDeadlineDigest`, `DigestRow` and the three new blocks |
| `go/internal/calendar/filing_watchdog_run.go` | create | `RunFilingWatchdog`, `NotifyHosts`, `SendOperatorDigest`, the port |
| `go/internal/calendar/filing_watchdog_run_test.go` | create | Go vs golden on PostgreSQL; digest renders without a database |
| `App/tests/test_filing_watchdog_run_golden.py` | create | fails when the golden file is stale |
| `docs/tasks/1159b-report.md` | create | the report (§9) |
| `docs/tasks/1159b-go-filing-watchdog-run.md` | edit (1 line) | `Status: review` |

No other file may change. No test-map or status edit: both are at their token cap; §6 names the commands.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/go-filing-watchdog-run` (if not: `git checkout -b claude/go-filing-watchdog-run origin/main`); `git log --oneline -1 -- go/internal/calendar/filing_watchdog.go | tail -3` shows a commit (1159 is merged); `ls` of the six §3 code paths says "No such file" six times; `sha256sum` of the three 1159 files prints the values in §2; `grep -cF` of each other anchor prints 1. Venv missing: as in 1159 step 0. Any check failing: STOP (§8). Last, write the helper that copies code block k of a brief byte for byte (pasting by hand is allowed too; the hash decides):

```bash
cat > /tmp/extract_block.py <<'EOF'
import re, sys
src, k, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = open(src, encoding='utf-8').read()
blocks = re.findall(r'^```(?:python|go)\n(.*?)^```$', text, re.S | re.M)
open(dest, 'w', encoding='utf-8').write(blocks[k - 1])
EOF
```

1. Create `App/scripts/filing_watchdog_run_golden.py` (sha256 `b44e624cba20b45e95ffb18db2fa8a6d1fbd937e1d5bee31ca2b1a4d8cb910d8`) = block 1 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159b-go-filing-watchdog-run.md 1 App/scripts/filing_watchdog_run_golden.py && sha256sum App/scripts/filing_watchdog_run_golden.py | tail -3`.
```python
"""Write go/internal/calendar/testdata/filing_watchdog_run_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/filing_watchdog_run_golden.py

It seeds a throwaway SQLite database with SEED from filing_watchdog_golden.py
(brief 1159) and calls filing_watchdog.run once per entry in RUNS, in order, so
each run sees what the one before wrote. Before a run it may change the digest
setting, the mail backend and the operator address. After each run it records
the result, the heartbeat URL, the email_outbox and push_outbox rows the run
added, every stay's at_risk_mailed_at and the digest setting. BUILDERS renders
the digest for inputs no run reaches (more than 50 rows, unknown only), and
CONTACTS records normalise_email for each address form.
go/internal/calendar/filing_watchdog_run_test.go replays the same and compares.
App/tests/test_filing_watchdog_run_golden.py fails when this file is stale.
Timestamps the outbox writes (created_at, next_attempt_at) are not recorded;
a payload and a builder's HTML are recorded as their sha256 (UTF-8).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import date, datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "filing_watchdog_run_golden.json"


def _base():
    spec = importlib.util.spec_from_file_location(
        "filing_watchdog_golden", Path(__file__).resolve().parent / "filing_watchdog_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _base()
SEED = BASE.SEED
ENV = dict(BASE.GOLDEN_ENV, UBYHOST_HEARTBEAT_FILING_URL="https://hc.example.test/ping/abc/")
UNSET = "-"  # "setting": UNSET deletes the digest setting before the run

# (instant, before). "before" keys: setting (value, or UNSET), mail_backend,
# operator_email: the environment values, applied as config reads them.
RUNS = [
    # Mail off: pushes only, no stamp, no digest, no setting.
    ("2026-09-17T10:00:00+00:00", {"mail_backend": "disabled"}),
    # Mail on: host mails and stamps; the first digest.
    ("2026-09-17T10:05:00+00:00", {"mail_backend": "console"}),
    # 204 and 227 are past the resend grace now; digest within 72 h: none.
    ("2026-09-17T11:00:00+00:00", {}),
    # Sunday: 203 overdue now; 73 h after the last digest: a new one.
    ("2026-09-20T11:05:00+00:00", {}),
    # A stamp in the future does not block the digest.
    ("2026-09-20T11:10:00+00:00", {"setting": "2026-12-01T00:00:00+00:00"}),
    # A stamp without an offset: Python raises, run() logs it, digest 0.
    ("2026-09-20T11:15:00+00:00", {"setting": "2026-09-20T11:10:00"}),
    # An unreadable stamp counts as none.
    ("2026-09-20T11:20:00+00:00", {"setting": "garbage"}),
    # No usable operator address: no digest.
    ("2026-09-20T11:25:00+00:00", {"setting": UNSET, "operator_email": "no-at-sign"}),
    # Exactly 72 h after the last digest: due again.
    ("2026-09-20T11:30:00+00:00", {"setting": "2026-09-17T11:30:00+00:00",
                                   "operator_email": "ops@example.test"}),
    # Empty variable: config falls back to support@ubyhost.com.
    ("2026-09-20T11:35:00+00:00", {"setting": UNSET, "operator_email": ""}),
]


def _builder_stay(i, *, unknown=False):
    stay = {
        "workspace": f"ws{i}@example.test",
        "property": f"Byt {i} <&>",
        "arrival": date(2026, 9, 1 + i % 20),
        "deadline": datetime(2026, 9, 3 + i % 20, 23, 59, 59),
        "unfiled": i % 4 + 1,
    }
    if unknown:
        stay["unfiled"] = 0
        stay["no_guests"] = True
    return stay


# Digest inputs no run reaches: 51 at-risk and 52 unknown rows (both "and N
# more" lines), and an unknown-only digest.
BUILDERS = [
    {"name": "digest_overflow", "stays": 51, "unknown": 52},
    {"name": "digest_unknown_only", "stays": 0, "unknown": 2},
]


# Contact addresses as legal_entity.contact_email may hold them, each with what
# mail.normalise_email (the parseaddr rule) makes of it; every result here is
# the same on Python 3.11, 3.12 and 3.13. Go must give the same address, or
# none and flag the value (logged at error level, the stay left unmailed).
CONTACTS = [
    "host@example.test", "  Host@Example.TEST  ", "Host One <host@example.test>",
    "<host@example.test>", "Jiří Novák <host@example.test>", "o'neil+tag@mail.example-host.test",
    "'host@example.test'", "x" * 241 + "@example.test", "x" * 242 + "@example.test",
    '"Host, One" <host@example.test>', "host@example.test (Host One)", "J. Doe <host@example.test>",
    "mailto:host@example.test", "host@ex ample.test", "<host@example.test",
    "Host <host@example.test", "hé@example.test", "Host One host@example.test",
    "a@b.test, c@d.test", "host@example", "no-at-sign", "Name <host@example.test> trailing",
    "host@example.test>", "Host <a@b.test> <c@d.test>", "host@[127.0.0.1]",
    "Host (x <host@example.test>", '"Host <host@example.test>', "", "   ",
]


def _apply(config, db, before) -> None:
    if "setting" in before:
        if before["setting"] == UNSET:
            db.execute("DELETE FROM settings WHERE key = ?", ("filing_watchdog_digest_sent_at",))
        else:
            db.set_setting("filing_watchdog_digest_sent_at", before["setting"])
    if "mail_backend" in before:
        config.MAIL_BACKEND = before["mail_backend"].strip().lower()
    if "operator_email" in before:
        config.OPERATOR_EMAIL = before["operator_email"].strip() or "support@ubyhost.com"


EMAIL_COLUMNS = ["idempotency_key", "kind", "reservation_id", "apartment_id", "owner_user_id",
                 "to_email", "cc_email", "subject", "payload", "state", "attempts"]
PUSH_COLUMNS = ["idempotency_key", "subscription_id", "user_account_id", "kind", "params", "url",
                "state", "attempts"]


def _emails(db, seen) -> list:
    out = []
    for row in db.query(
        f"SELECT {', '.join(EMAIL_COLUMNS)} FROM email_outbox ORDER BY idempotency_key"
    ):
        if row["idempotency_key"] in seen:
            continue
        seen.add(row["idempotency_key"])
        record = {key: row[key] for key in EMAIL_COLUMNS}
        # The payload carries the HTML part: keep its hash and the readable text.
        payload = row["payload"]
        record["payload"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        record["text"] = json.loads(payload)["text"]
        out.append(record)
    return out


def _pushes(db, seen) -> list:
    out = []
    for row in db.query(
        f"SELECT {', '.join(PUSH_COLUMNS)} FROM push_outbox ORDER BY idempotency_key"
    ):
        if row["idempotency_key"] in seen:
            continue
        seen.add(row["idempotency_key"])
        record = {key: row[key] for key in PUSH_COLUMNS}
        # Go writes the params keys sorted, Python in insertion order: compare values.
        record["params"] = json.loads(row["params"])
        out.append(record)
    return out


def render() -> str:
    """Seed a fresh database, run the watchdog per RUNS, return the golden JSON text."""
    from app import config, db, filing_watchdog, mail, mail_notify

    saved = {name: getattr(config, name) for name in (
        "APP_BASE_URL", "PUBLIC_BASE_URL", "MAIL_BACKEND", "OPERATOR_EMAIL", "WEB_PUSH",
        "HEARTBEAT_FILING_URL")}
    try:
        config.APP_BASE_URL = ENV["UBYHOST_APP_BASE_URL"]
        config.PUBLIC_BASE_URL = ENV["UBYHOST_PUBLIC_BASE_URL"]
        config.MAIL_BACKEND = ENV["UBYHOST_MAIL_BACKEND"]
        config.OPERATOR_EMAIL = ENV["UBYHOST_OPERATOR_EMAIL"]
        config.WEB_PUSH = True
        config.HEARTBEAT_FILING_URL = ENV["UBYHOST_HEARTBEAT_FILING_URL"]
        db.init_db()
        BASE._seed(db)
        seen_mail, seen_push = set(), set()
        runs = []
        for at, before in RUNS:
            _apply(config, db, before)
            result = filing_watchdog.run(datetime.fromisoformat(at))
            stamps = db.query("SELECT id, at_risk_mailed_at FROM reservation ORDER BY id")
            runs.append({
                "at": at,
                "before": before,
                "result": result,
                "heartbeat": filing_watchdog.heartbeat_url(result["at_risk"] > 0),
                "emails": _emails(db, seen_mail),
                "pushes": _pushes(db, seen_push),
                "mailed": {str(r["id"]): r["at_risk_mailed_at"] for r in stamps},
                "setting": db.get_setting("filing_watchdog_digest_sent_at"),
            })
        builders = []
        for case in BUILDERS:
            stays = [_builder_stay(i) for i in range(case["stays"])]
            unknown = [_builder_stay(i, unknown=True) for i in range(case["unknown"])]
            content = mail_notify.build_deadline_digest(stays, lang="en", unknown=unknown)
            builders.append({
                "name": case["name"],
                "stays": [_builder_record(s) for s in stays],
                "unknown": [_builder_record(s) for s in unknown],
                "subject": content["subject"],
                "text": content["text"],
                "html_sha256": hashlib.sha256(content["html"].encode("utf-8")).hexdigest(),
            })
    finally:
        for name, value in saved.items():
            setattr(config, name, value)
    contacts = [{"raw": raw, "python": mail.normalise_email(raw)} for raw in CONTACTS]
    golden = {"env": ENV, "unset": UNSET, "seed": SEED, "runs": runs, "builders": builders,
              "contacts": contacts}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _builder_record(stay) -> dict:
    return {
        "workspace": stay["workspace"],
        "property": stay["property"],
        "arrival": stay["arrival"].strftime("%d.%m.%Y"),
        "deadline": stay["deadline"].strftime("%d.%m.%Y %H:%M"),
        "unfiled": stay["unfiled"],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    BASE.prepare_env()
    main()
```

   From `App/`: `.venv/bin/python scripts/filing_watchdog_run_golden.py 2>&1 | tail -3` ends with `wrote .../go/internal/calendar/testdata/filing_watchdog_run_golden.json` (a `TypeError: can't subtract offset-naive and offset-aware datetimes` traceback above it is expected: that is run 6, logged by `run()`). Then from the repo root `sha256sum App/scripts/filing_watchdog_run_golden.py go/internal/calendar/testdata/filing_watchdog_run_golden.json | tail -30` must print `b44e624cba20b45e95ffb18db2fa8a6d1fbd937e1d5bee31ca2b1a4d8cb910d8` and `7a5da39c99440d6815f20aaf05cc4b5b1469f18aae8868b9563bdb8c3f5180fe`. A different script hash: fix your paste from the block above (never edit the JSON by hand). Commit "1159b step 1" (both files).

2. Create `go/internal/mail/deadline_at_risk.go` (sha256 `472daf4cc68b7d8632e6f672d254adcb087402ba1ba7ef8d8397b5d2205f70b5`) = block 2 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159b-go-filing-watchdog-run.md 2 go/internal/mail/deadline_at_risk.go && sha256sum go/internal/mail/deadline_at_risk.go | tail -3`.
```go
package mail

// Port of App/app/mail_notify.py build_deadline_at_risk and
// build_deadline_digest (the WP23 filing watchdog mails), with the blocks they
// add to the shared ones (_block_fact, _block_link, _block_table). The English
// strings are copied from host_i18n.STRINGS["en"] and the guest catalogue's
// mail_link_fallback. Golden: App/scripts/filing_watchdog_run_golden.py writes
// the rendered parts into go/internal/calendar/testdata/filing_watchdog_run_golden.json.

import (
	"strconv"
	"strings"
)

const (
	strRiskSubject           = "Not reported to the police yet: %(property)s, deadline %(deadline)s"
	strRiskPreheader         = "Guests not filed with UbyPort yet: %(count)s"
	strRiskHeading           = "This stay may miss its police deadline"
	strRiskIntro             = "%(property)s, arrival %(arrival)s: foreign guests of this stay are not reported to the police yet. The deadline is %(deadline)s."
	strRiskPropertyLabel     = "Property"
	strRiskArrivalLabel      = "Arrival"
	strRiskUnfiledLabel      = "Guests not filed yet"
	strRiskDeadlineLabel     = "Deadline"
	strRiskNextLabel         = "What to do next"
	strRiskNextSteps         = "Open the stay, complete what is missing and send it."
	strRiskManualLabel       = "If UbyHost cannot file in time"
	strRiskManual            = "Sign in to the UbyPort web application with your own access, enter the guests by hand and keep the receipt. Then open the stay in UbyHost and choose \"I filed this stay by hand in UbyPort\", so UbyHost never sends it again. The duty to report stays with you as the host."
	strRiskAction            = "Open the stay"
	strRiskFooter            = "You get this e-mail once per stay, when its police deadline is less than 24 hours away or has passed and the stay is still not reported."
	strRiskNoGuestsSubject   = "No guest details yet: %(property)s, police deadline %(deadline)s"
	strRiskNoGuestsPreheader = "UbyHost cannot tell whether this stay must be reported."
	strRiskNoGuestsHeading   = "No guest details for this stay yet"
	strRiskNoGuestsIntro     = "%(property)s, arrival %(arrival)s: no guest details are entered yet, so UbyHost cannot tell whether the stay must be reported to the police. If any guest is not a Czech citizen, the deadline is %(deadline)s."
	strRiskNoGuestsNext      = "Open the stay and enter the guests, or send the guest link again. If all guests are Czech citizens, enter them for the house book; nothing has to be reported."
	strRiskNoGuestsFooter    = "You get this e-mail once per stay, when the guests have arrived, the police deadline is less than 24 hours away or has passed, and no guest details are entered yet."
	strLinkFallback          = "If the button does not work, copy this address into your browser:"

	strDigestSubject        = "Filing watchdog: stays at risk (%(count)s)"
	strDigestSubjectUnknown = "Filing watchdog: stays at risk (%(count)s), without guest details (%(unknown)s)"
	strDigestHeading        = "Stays that may miss the police deadline"
	strDigestIntro          = "Each stay below has foreign guests that UbyPort has not accepted yet, and its deadline is less than 24 hours away or has passed. This digest is sent at most every 3 days while any stay is at risk."
	strDigestColWorkspace   = "Workspace"
	strDigestColProperty    = "Property"
	strDigestColArrival     = "Arrival"
	strDigestColDeadline    = "Deadline"
	strDigestColUnfiled     = "Not filed"
	strDigestMore           = "And %(count)s more stays."
	strDigestFooter         = "Sent to UBYHOST_OPERATOR_EMAIL by the deadline job. It contains no guest names."
	strDigestUnknownHeading = "Stays without guest details (status unknown)"
	strDigestUnknownIntro   = "No guest is entered for these stays. The arrival has passed and the deadline is less than 24 hours away or has passed. If the guests are Czech citizens nothing has to be reported, so these stays do not set the filing heartbeat to failed."

	// DeadlineDigestMaxRows is DEADLINE_DIGEST_MAX_ROWS: the rest are counted.
	DeadlineDigestMaxRows = 50
)

// DigestRow is one stay of the operator digest, already formatted: Arrival is
// DD.MM.YYYY and Deadline is "DD.MM.YYYY HH:MM", as _digest_section prints them.
type DigestRow struct {
	Workspace string
	Property  string
	Arrival   string
	Deadline  string
	Unfiled   int
}

// sub is the "%" pass of host_i18n.lookup for these keys: each %(name)s is
// replaced. None of these templates contains %% or another placeholder.
func sub(tmpl string, pairs ...string) string {
	return strings.NewReplacer(pairs...).Replace(tmpl)
}

// blockFact is _block_fact.
func blockFact(label, value string) string {
	return `<tr><td style="padding:20px 24px 0 24px;"><div style="font:600 14px/1.4 ` + fontStack +
		`;color:` + colInk + `;padding:0 0 6px 0;">` + esc(label) + `</div>` +
		`<div style="font:400 15px/1.5 ` + fontStack + `;color:` + colInk + `;">` + esc(value) + `</div>` +
		`</td></tr>`
}

// blockLink is _block_link: the full address under a button.
func blockLink(url, label string) string {
	return `<tr><td style="padding:14px 24px 0 24px;"><div style="font:400 13px/1.6 ` + fontStack +
		`;color:` + colInkMuted + `;">` + esc(label) + `</div>` +
		`<div style="font:400 13px/1.6 ` + fontStack + `;color:` + colInkSecondary +
		`;word-break:break-all;"><a href="` + esc(url) + `" style="color:` + colBrandAction +
		`;text-decoration:underline;">` + esc(url) + `</a></div></td></tr>`
}

// blockTable is _block_table.
func blockTable(header []string, rows [][]string) string {
	cell := "padding:6px 8px;border-bottom:1px solid " + colLine + ";text-align:left;"
	var head, body strings.Builder
	for _, h := range header {
		head.WriteString(`<th style="` + cell + `font:600 13px/1.4 ` + fontStack + `;color:` + colInk + `;">` + esc(h) + `</th>`)
	}
	for _, row := range rows {
		body.WriteString("<tr>")
		for _, v := range row {
			body.WriteString(`<td style="` + cell + `font:400 13px/1.4 ` + fontStack + `;color:` + colInkSecondary + `;">` + esc(v) + `</td>`)
		}
		body.WriteString("</tr>")
	}
	return `<tr><td style="padding:20px 24px 0 24px;">` +
		`<table role="presentation" width="100%" cellpadding="0" cellspacing="0" ` +
		`border="0" style="border-collapse:collapse;">` +
		`<tr>` + head.String() + `</tr>` + body.String() + `</table></td></tr>`
}

// BuildDeadlineAtRisk is build_deadline_at_risk: the host's one warning that a
// stay may miss its police deadline. arrival is DD.MM.YYYY, deadline is
// "DD.MM.YYYY HH:MM" (_deadline_text), stayURL the absolute stay link.
// publicBaseURL carries the logo. noGuests is the variant for a stay with no
// guest on file, which has no "Guests not filed yet" fact.
func BuildDeadlineAtRisk(publicBaseURL, lang, propertyName, arrival, deadline string, unfiled int, stayURL string, noGuests bool) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	subject, preheader, heading, intro := strRiskSubject, strRiskPreheader, strRiskHeading, strRiskIntro
	nextSteps, footer := strRiskNextSteps, strRiskFooter
	if noGuests {
		subject, preheader, heading, intro = strRiskNoGuestsSubject, strRiskNoGuestsPreheader, strRiskNoGuestsHeading, strRiskNoGuestsIntro
		nextSteps, footer = strRiskNoGuestsNext, strRiskNoGuestsFooter
	}
	count := strconv.Itoa(unfiled)
	subject = sub(subject, "%(property)s", propertyName, "%(deadline)s", deadline)
	preheader = sub(preheader, "%(count)s", count)
	intro = sub(intro, "%(property)s", propertyName, "%(arrival)s", arrival, "%(deadline)s", deadline)
	facts := [][2]string{{strRiskPropertyLabel, propertyName}, {strRiskArrivalLabel, arrival}}
	if !noGuests {
		facts = append(facts, [2]string{strRiskUnfiledLabel, count})
	}
	facts = append(facts, [2]string{strRiskDeadlineLabel, deadline})

	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockButton(stayURL, strRiskAction),
		blockLink(stayURL, strLinkFallback),
	}
	for _, f := range facts {
		blocks = append(blocks, blockFact(f[0], f[1]))
	}
	blocks = append(blocks, blockSection(strRiskNextLabel, nextSteps), blockNote(strRiskManualLabel, strRiskManual))

	lines := []string{intro, ""}
	for _, f := range facts {
		lines = append(lines, f[0]+": "+f[1])
	}
	lines = append(lines,
		"",
		strRiskNextLabel+": "+nextSteps,
		"",
		strRiskManualLabel+": "+strRiskManual,
		"",
		strRiskAction+": "+stayURL,
		"",
		"--",
		"UbyHost",
		footer,
	)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    shell(publicBaseURL, propertyName, preheader, blocks, []string{"UbyHost", footer}),
	}, nil
}

// digestSection is _digest_section: header, at most DeadlineDigestMaxRows rows,
// and the "and N more" line ("" when nothing is hidden).
func digestSection(rows []DigestRow, withUnfiled bool) ([]string, [][]string, string) {
	header := []string{strDigestColWorkspace, strDigestColProperty, strDigestColArrival, strDigestColDeadline}
	if withUnfiled {
		header = append(header, strDigestColUnfiled)
	}
	shown := rows
	if len(shown) > DeadlineDigestMaxRows {
		shown = shown[:DeadlineDigestMaxRows]
	}
	var out [][]string
	for _, r := range shown {
		values := []string{r.Workspace, r.Property, r.Arrival, r.Deadline}
		if withUnfiled {
			values = append(values, strconv.Itoa(r.Unfiled))
		}
		out = append(out, values)
	}
	more := ""
	if hidden := len(rows) - len(shown); hidden > 0 {
		more = sub(strDigestMore, "%(count)s", strconv.Itoa(hidden))
	}
	return header, out, more
}

// BuildDeadlineDigest is build_deadline_digest: the operator's digest of every
// stay at risk across all workspaces, without guest names. unknown (stays with
// no guest on file) is a section of its own, without a count column.
func BuildDeadlineDigest(publicBaseURL, lang string, stays, unknown []DigestRow) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	var subject string
	if len(unknown) > 0 {
		subject = sub(strDigestSubjectUnknown, "%(count)s", strconv.Itoa(len(stays)), "%(unknown)s", strconv.Itoa(len(unknown)))
	} else {
		subject = sub(strDigestSubject, "%(count)s", strconv.Itoa(len(stays)))
	}
	blocks := []string{blockHeading(strDigestHeading)}
	var lines []string
	if len(stays) > 0 {
		header, rows, more := digestSection(stays, true)
		blocks = append(blocks, blockParagraph(strDigestIntro, false), blockTable(header, rows))
		if more != "" {
			blocks = append(blocks, blockParagraph(more, true))
		}
		lines = append(lines, strDigestIntro, "", strings.Join(header, " | "))
		for _, r := range rows {
			lines = append(lines, strings.Join(r, " | "))
		}
		if more != "" {
			lines = append(lines, "", more)
		}
	}
	if len(unknown) > 0 {
		header, rows, more := digestSection(unknown, false)
		blocks = append(blocks,
			blockHeading(strDigestUnknownHeading),
			blockParagraph(strDigestUnknownIntro, false),
			blockTable(header, rows))
		if more != "" {
			blocks = append(blocks, blockParagraph(more, true))
		}
		if len(lines) > 0 {
			lines = append(lines, "")
		}
		lines = append(lines, strDigestUnknownHeading, strDigestUnknownIntro, "", strings.Join(header, " | "))
		for _, r := range rows {
			lines = append(lines, strings.Join(r, " | "))
		}
		if more != "" {
			lines = append(lines, "", more)
		}
	}
	lines = append(lines, "", "--", "UbyHost", strDigestFooter)
	preheader := strDigestUnknownIntro
	if len(stays) > 0 {
		preheader = strDigestIntro
	}
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    shell(publicBaseURL, strDigestHeading, preheader, blocks, []string{"UbyHost", strDigestFooter}),
	}, nil
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` is clean. Commit "1159b step 2".

3. Create `go/internal/calendar/filing_watchdog_run.go` (sha256 `7b6eca2f5f39b280cdcf056f58ecd81e7ab8bbf70231f974399dad232ce01c8d`) = block 3 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159b-go-filing-watchdog-run.md 3 go/internal/calendar/filing_watchdog_run.go && sha256sum go/internal/calendar/filing_watchdog_run.go | tail -3`.
```go
// filing_watchdog_run.go is the acting half of App/app/filing_watchdog.py
// (WP23): notify_hosts (push.deadline_at_risk and the deadline_at_risk host
// mail), send_operator_digest and run. The selection half is filing_watchdog.go
// (brief 1159). Nothing calls this yet: brief 1132 §10 E adds the job kind and
// the Python/Go switch. testdata/filing_watchdog_run_golden.json, written by
// App/scripts/filing_watchdog_run_golden.py, is the parity check.
package calendar

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	// watchdogDigestInterval is DIGEST_INTERVAL.
	watchdogDigestInterval = 72 * time.Hour
	// watchdogDigestSetting is DIGEST_SETTING.
	watchdogDigestSetting = "filing_watchdog_digest_sent_at"
	// watchdogOperatorDefault is config.OPERATOR_EMAIL when the variable is empty.
	watchdogOperatorDefault = "support@ubyhost.com"
	// watchdogPushParamMax is push._PARAM_MAX.
	watchdogPushParamMax = 120
)

// errWatchdogNaiveStamp is Python's TypeError on an offset-less digest stamp.
var errWatchdogNaiveStamp = errors.New("filing watchdog: digest stamp has no UTC offset")

// WatchdogResult is the dict run() returns.
type WatchdogResult struct {
	AtRisk        int
	UnknownRisk   int
	AwaitingRetry int
	HostMails     int
	Digest        int
}

// watchdogMailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND console or ses.
func watchdogMailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

// watchdogBases is (config.PUBLIC_BASE_URL, config.app_base_url()), without a
// trailing slash, as cancelled_notify.go reads them.
func watchdogBases(getenv func(string) string) (string, string) {
	public := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	app := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if app == "" {
		app = public
	}
	return public, app
}

// watchdogStamp is _utc(now).replace(microsecond=0).isoformat().
func watchdogStamp(at time.Time) string {
	return at.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// watchdogDeadlineText is mail_notify._deadline_text: "DD.MM.YYYY HH:MM".
func watchdogDeadlineText(deadline time.Time) string {
	return deadline.Format("02.01.2006 15:04")
}

// watchdogAddrSpec is a plain addr-spec: a dot-atom local part and a dotted
// domain of letters, digits and hyphens.
const watchdogAddrSpec = `[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+)*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+`

var (
	watchdogAddrPlain = regexp.MustCompile(`^(` + watchdogAddrSpec + `)$`)
	watchdogAddrAngle = regexp.MustCompile(`^[^"()<>\[\]:;@\\,.\t\r\n]*<(` + watchdogAddrSpec + `)>$`)
)

// watchdogAddress is mail.normalise_email for the forms it can read: a plain
// address, or "<address>" after a display name with no special characters.
// For those it gives exactly what Python gives (lower case, at most 254
// characters). Python's parseaddr is a full RFC 2822 parser whose results for
// other forms (comments, quotes, groups, "mailto:") differ between Python
// releases, so it is not ported; any other value that is not blank returns ""
// with unreadable true: the caller logs it at error level and the stay stays
// unmailed (no stamp), so it is never skipped silently and is retried each run.
func watchdogAddress(raw string) (addr string, unreadable bool) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return "", false
	}
	m := watchdogAddrPlain.FindStringSubmatch(s)
	if m == nil {
		m = watchdogAddrAngle.FindStringSubmatch(s)
	}
	if m == nil || len(m[1]) > 254 {
		return "", true
	}
	return strings.ToLower(m[1]), false
}

// watchdogContactEmail is mail_notify._entity_contact_email: the legal
// entity's contact address, normalised, or "" (see watchdogAddress).
func watchdogContactEmail(ctx context.Context, pool *pgxpool.Pool, entity *int64) (string, bool, error) {
	if entity == nil || *entity == 0 {
		return "", false, nil
	}
	var contact *string
	err := pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *entity).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	if contact == nil {
		return "", false, nil
	}
	addr, unreadable := watchdogAddress(*contact)
	return addr, unreadable, nil
}

// watchdogPush is push.deadline_at_risk: one push per device of the owner,
// key deadline_at_risk:<reservation>:<device>. Python never raises here; the
// error is returned for the caller to log.
func watchdogPush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stay WatchdogStay) error {
	if stay.OwnerUserID == nil || *stay.OwnerUserID == 0 {
		return nil
	}
	id := fmt.Sprintf("%d", stay.ReservationID)
	params := ubyport.AlertParams{
		"property": watchdogCut(stay.Property),
		"date":     watchdogCut(stay.Arrival.Format("02.01.2006")),
		"deadline": watchdogCut(watchdogDeadlineText(stay.Deadline)),
	}
	_, err := ubyport.QueuePush(ctx, pool, getenv, *stay.OwnerUserID, "deadline_at_risk", id,
		"/reservations/"+id, params)
	return err
}

// watchdogCut is push._clean_params: a value cut to 120 characters.
func watchdogCut(s string) string {
	r := []rune(s)
	if len(r) > watchdogPushParamMax {
		return string(r[:watchdogPushParamMax])
	}
	return s
}

// watchdogMailStay queues the host mail for one stay and stamps
// at_risk_mailed_at. It reports whether a mail was queued.
func watchdogMailStay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stay *WatchdogStay, at time.Time) (bool, error) {
	to, unreadable, err := watchdogContactEmail(ctx, pool, stay.LegalEntityID)
	if err != nil {
		return false, err
	}
	if unreadable {
		slog.Error("deadline_at_risk host not mailed: contact address unreadable", "reservation_id", stay.ReservationID)
	}
	if to == "" {
		return false, nil
	}
	public, app := watchdogBases(getenv)
	stayURL := fmt.Sprintf("%s/reservations/%d", app, stay.ReservationID)
	content, err := mail.BuildDeadlineAtRisk(public, "en", stay.Property, stay.Arrival.Format("02.01.2006"),
		watchdogDeadlineText(stay.Deadline), stay.Unfiled, stayURL, stay.NoGuests)
	if err != nil {
		return false, err
	}
	if !watchdogMailEnabled(getenv) {
		// Mail is switched off: try again on the next run rather than marking
		// a warning nobody got.
		return false, nil
	}
	reservation, apartment := stay.ReservationID, stay.ApartmentID
	outboxID, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          "deadline_at_risk",
		Key:           fmt.Sprintf("deadline_at_risk:%d", stay.ReservationID),
		ReservationID: &reservation,
		ApartmentID:   &apartment,
		OwnerUserID:   stay.OwnerUserID,
		To:            to,
		Subject:       content.Subject,
		Text:          content.Text,
		HTML:          content.HTML,
	})
	if err != nil {
		return false, err
	}
	if outboxID == 0 {
		return false, nil
	}
	stamp := watchdogStamp(at)
	if _, err := pool.Exec(ctx,
		`UPDATE reservation SET at_risk_mailed_at = $1 WHERE id = $2 AND at_risk_mailed_at IS NULL`,
		stamp, stay.ReservationID); err != nil {
		return false, err
	}
	stay.MailedAt = &stamp
	return true, nil
}

// NotifyHosts is notify_hosts: the push and the host mail for each stay not
// warned yet, once per stay whichever variant comes first. It returns how many
// mails were queued. A failure on one stay is logged and the next stay goes
// on, as in Python. The push is queued even when there is no address to mail.
func NotifyHosts(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stays []WatchdogStay, at time.Time) int {
	queued := 0
	for i := range stays {
		stay := &stays[i]
		if stay.MailedAt != nil && *stay.MailedAt != "" {
			continue
		}
		if err := watchdogPush(ctx, pool, getenv, *stay); err != nil {
			slog.Error("push_deadline_failed", "reservation_id", stay.ReservationID)
		}
		ok, err := watchdogMailStay(ctx, pool, getenv, stay, at)
		if err != nil {
			slog.Error("deadline_at_risk mail failed", "reservation_id", stay.ReservationID)
			continue
		}
		if ok {
			queued++
		}
	}
	return queued
}

// watchdogDigestRows is the digest's view of the stays: no guest names.
func watchdogDigestRows(stays []WatchdogStay) []mail.DigestRow {
	rows := make([]mail.DigestRow, 0, len(stays))
	for _, s := range stays {
		rows = append(rows, mail.DigestRow{
			Workspace: s.Workspace,
			Property:  s.Property,
			Arrival:   s.Arrival.Format("02.01.2006"),
			Deadline:  watchdogDeadlineText(s.Deadline),
			Unfiled:   s.Unfiled,
		})
	}
	return rows
}

// watchdogLastDigest reads the digest stamp: ok false when it is missing or
// unreadable (Python's None: the digest may go out). A stamp without an
// offset is Python's TypeError and returns errWatchdogNaiveStamp.
func watchdogLastDigest(raw string) (time.Time, bool, error) {
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02 15:04:05.999999999Z07:00"} {
		if t, err := time.Parse(layout, raw); err == nil {
			return t, true, nil
		}
	}
	for _, layout := range []string{"2006-01-02T15:04:05.999999999", "2006-01-02 15:04:05.999999999", "2006-01-02"} {
		if _, err := time.Parse(layout, raw); err == nil {
			return time.Time{}, false, errWatchdogNaiveStamp
		}
	}
	return time.Time{}, false, nil
}

// SendOperatorDigest is send_operator_digest: the operator digest, unless one
// went out in the last 72 hours. A stamp in the future (a clock set back)
// does not block it. It reports whether a digest was queued.
func SendOperatorDigest(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stays, unknown []WatchdogStay, at time.Time) (bool, error) {
	if len(stays) == 0 && len(unknown) == 0 {
		return false, nil
	}
	operator := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if operator == "" {
		operator = watchdogOperatorDefault
	}
	to, unreadable := watchdogAddress(operator)
	if unreadable {
		slog.Error("deadline digest not sent: UBYHOST_OPERATOR_EMAIL unreadable")
	}
	if to == "" {
		return false, nil
	}
	current := at.UTC().Truncate(time.Second)
	var lastRaw *string
	err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, watchdogDigestSetting).Scan(&lastRaw)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	if lastRaw != nil && *lastRaw != "" {
		last, ok, err := watchdogLastDigest(*lastRaw)
		if err != nil {
			return false, err
		}
		if ok {
			age := current.Sub(last)
			if age >= 0 && age < watchdogDigestInterval {
				return false, nil
			}
		}
	}
	public, _ := watchdogBases(getenv)
	content, err := mail.BuildDeadlineDigest(public, "en", watchdogDigestRows(stays), watchdogDigestRows(unknown))
	if err != nil {
		return false, err
	}
	if !watchdogMailEnabled(getenv) {
		return false, nil
	}
	stamp := watchdogStamp(current)
	outboxID, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:    "deadline_digest",
		Key:     "deadline_digest:" + stamp,
		To:      to,
		Subject: content.Subject,
		Text:    content.Text,
		HTML:    content.HTML,
	})
	if err != nil {
		return false, err
	}
	if outboxID == 0 {
		return false, nil
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2)
		ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
		watchdogDigestSetting, stamp); err != nil {
		return false, err
	}
	return true, nil
}

// RunFilingWatchdog is filing_watchdog.run: one watchdog pass. It fails only
// when the at-risk query fails. AtRisk counts only stays with known reportable
// guests and alone decides the heartbeat (FilingHeartbeatURL); UnknownRisk and
// AwaitingRetry do not. The unknown-risk query and the digest are isolated: a
// failure is logged and the pass goes on, so neither silences the real check.
// lookupEnv is os.LookupEnv in production; an unreadable
// UBYHOST_SUBMIT_SWEEP_MINUTES fails the pass, as Python refuses to start.
func RunFilingWatchdog(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time) (WatchdogResult, error) {
	getenv := func(name string) string {
		v, _ := lookupEnv(name)
		return v
	}
	every, err := AtRiskStays(ctx, pool, lookupEnv, at, true)
	if err != nil {
		return WatchdogResult{}, err
	}
	var stays []WatchdogStay
	for _, s := range every {
		if !s.AwaitingRetry {
			stays = append(stays, s)
		}
	}
	unknown, err := UnknownRiskStays(ctx, pool, at)
	if err != nil {
		// The weaker check must not silence the real one or its heartbeat.
		slog.Error("unknown-risk query failed")
		unknown = nil
	}
	both := make([]WatchdogStay, 0, len(stays)+len(unknown))
	both = append(both, stays...)
	both = append(both, unknown...)
	hostMails := NotifyHosts(ctx, pool, getenv, both, at)
	digest, err := SendOperatorDigest(ctx, pool, getenv, stays, unknown, at)
	if err != nil {
		slog.Error("deadline digest failed")
		digest = false
	}
	result := WatchdogResult{
		AtRisk:        len(stays),
		UnknownRisk:   len(unknown),
		AwaitingRetry: len(every) - len(stays),
		HostMails:     hostMails,
	}
	if digest {
		result.Digest = 1
	}
	return result, nil
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` is clean. Commit "1159b step 3".

4. Create `go/internal/calendar/filing_watchdog_run_test.go` (sha256 `125918c335daf7d7437f8cc703677444e22f4ebc1ceb658beafe2e785c812720`) = block 4 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159b-go-filing-watchdog-run.md 4 go/internal/calendar/filing_watchdog_run_test.go && sha256sum go/internal/calendar/filing_watchdog_run_test.go | tail -3`.
```go
package calendar

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

type watchdogRunEmail struct {
	IdempotencyKey string  `json:"idempotency_key"`
	Kind           string  `json:"kind"`
	ReservationID  *int64  `json:"reservation_id"`
	ApartmentID    *int64  `json:"apartment_id"`
	OwnerUserID    *int64  `json:"owner_user_id"`
	ToEmail        string  `json:"to_email"`
	CCEmail        *string `json:"cc_email"`
	Subject        string  `json:"subject"`
	Payload        string  `json:"payload"`
	Text           string  `json:"text"`
	State          string  `json:"state"`
	Attempts       int64   `json:"attempts"`
}

type watchdogRunPush struct {
	IdempotencyKey string            `json:"idempotency_key"`
	SubscriptionID int64             `json:"subscription_id"`
	UserAccountID  int64             `json:"user_account_id"`
	Kind           string            `json:"kind"`
	Params         map[string]string `json:"params"`
	URL            string            `json:"url"`
	State          string            `json:"state"`
	Attempts       int64             `json:"attempts"`
}

type watchdogRunResult struct {
	AtRisk        int `json:"at_risk"`
	UnknownRisk   int `json:"unknown_risk"`
	AwaitingRetry int `json:"awaiting_retry"`
	HostMails     int `json:"host_mails"`
	Digest        int `json:"digest"`
}

type watchdogRunStep struct {
	At        string             `json:"at"`
	Before    map[string]string  `json:"before"`
	Result    watchdogRunResult  `json:"result"`
	Heartbeat string             `json:"heartbeat"`
	Emails    []watchdogRunEmail `json:"emails"`
	Pushes    []watchdogRunPush  `json:"pushes"`
	Mailed    map[string]*string `json:"mailed"`
	Setting   *string            `json:"setting"`
}

type watchdogBuilderRow struct {
	Workspace string `json:"workspace"`
	Property  string `json:"property"`
	Arrival   string `json:"arrival"`
	Deadline  string `json:"deadline"`
	Unfiled   int    `json:"unfiled"`
}

type watchdogBuilder struct {
	Name       string               `json:"name"`
	Stays      []watchdogBuilderRow `json:"stays"`
	Unknown    []watchdogBuilderRow `json:"unknown"`
	Subject    string               `json:"subject"`
	Text       string               `json:"text"`
	HTMLSHA256 string               `json:"html_sha256"`
}

type watchdogRunGolden struct {
	Env      map[string]string `json:"env"`
	Unset    string            `json:"unset"`
	Seed     []watchSeedTable  `json:"seed"`
	Runs     []watchdogRunStep `json:"runs"`
	Builders []watchdogBuilder `json:"builders"`
	Contacts []struct {
		Raw    string `json:"raw"`
		Python string `json:"python"`
	} `json:"contacts"`
}

func loadWatchdogRunGolden(t *testing.T) watchdogRunGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/filing_watchdog_run_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchdogRunGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) < 10 || len(g.Seed) == 0 || len(g.Builders) < 2 {
		t.Fatal("golden file has too few runs or builders, or no seed")
	}
	return g
}

func sha256Hex(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

// watchdogApply is the golden script's _apply: the digest setting and the
// environment the run reads.
func watchdogApply(t *testing.T, pool *pgxpool.Pool, env map[string]string, unset string, before map[string]string) {
	t.Helper()
	ctx := context.Background()
	if v, ok := before["setting"]; ok {
		var err error
		if v == unset {
			_, err = pool.Exec(ctx, `DELETE FROM settings WHERE key = $1`, watchdogDigestSetting)
		} else {
			_, err = pool.Exec(ctx, `INSERT INTO settings (key, value) VALUES ($1, $2)
				ON CONFLICT(key) DO UPDATE SET value = excluded.value`, watchdogDigestSetting, v)
		}
		if err != nil {
			t.Fatal(err)
		}
	}
	if v, ok := before["mail_backend"]; ok {
		env["UBYHOST_MAIL_BACKEND"] = v
	}
	if v, ok := before["operator_email"]; ok {
		env["UBYHOST_OPERATOR_EMAIL"] = v
	}
}

func watchdogNewEmails(t *testing.T, pool *pgxpool.Pool, seen map[string]bool) []watchdogRunEmail {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email,
		cc_email, subject, payload, state, attempts FROM email_outbox ORDER BY idempotency_key`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []watchdogRunEmail{}
	for rows.Next() {
		var e watchdogRunEmail
		if err := rows.Scan(&e.IdempotencyKey, &e.Kind, &e.ReservationID, &e.ApartmentID, &e.OwnerUserID,
			&e.ToEmail, &e.CCEmail, &e.Subject, &e.Payload, &e.State, &e.Attempts); err != nil {
			t.Fatal(err)
		}
		if seen[e.IdempotencyKey] {
			continue
		}
		seen[e.IdempotencyKey] = true
		var payload struct {
			Text string `json:"text"`
		}
		if err := json.Unmarshal([]byte(e.Payload), &payload); err != nil {
			t.Fatal(err)
		}
		e.Text = payload.Text
		e.Payload = sha256Hex(e.Payload)
		out = append(out, e)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogNewPushes(t *testing.T, pool *pgxpool.Pool, seen map[string]bool) []watchdogRunPush {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT idempotency_key, subscription_id, user_account_id, kind, params, url, state, attempts
		FROM push_outbox ORDER BY idempotency_key`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []watchdogRunPush{}
	for rows.Next() {
		var p watchdogRunPush
		var params string
		if err := rows.Scan(&p.IdempotencyKey, &p.SubscriptionID, &p.UserAccountID, &p.Kind, &params,
			&p.URL, &p.State, &p.Attempts); err != nil {
			t.Fatal(err)
		}
		if seen[p.IdempotencyKey] {
			continue
		}
		seen[p.IdempotencyKey] = true
		if err := json.Unmarshal([]byte(params), &p.Params); err != nil {
			t.Fatal(err)
		}
		out = append(out, p)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogMailed(t *testing.T, pool *pgxpool.Pool) map[string]*string {
	t.Helper()
	rows, err := pool.Query(context.Background(), `SELECT id, at_risk_mailed_at FROM reservation ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := map[string]*string{}
	for rows.Next() {
		var id int64
		var stamp *string
		if err := rows.Scan(&id, &stamp); err != nil {
			t.Fatal(err)
		}
		out[strconv.FormatInt(id, 10)] = stamp
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogSetting(t *testing.T, pool *pgxpool.Pool) *string {
	t.Helper()
	var v *string
	err := pool.QueryRow(context.Background(), `SELECT value FROM settings WHERE key = $1`, watchdogDigestSetting).Scan(&v)
	if err != nil {
		return nil
	}
	return v
}

func watchdogDiff(t *testing.T, label string, got, want any) {
	t.Helper()
	a, b := watchdogJSON(t, got), watchdogJSON(t, want)
	if a != b {
		t.Errorf("%s differs from Python\n got:\n%s\nwant:\n%s", label, a, b)
	}
}

// TestRunFilingWatchdogMatchesPython seeds the golden rows and replays every
// golden run in order: the result, the heartbeat URL, the mail and push rows
// each run added (payload by sha256), every at_risk_mailed_at and the digest
// setting must be what filing_watchdog.run left.
func TestRunFilingWatchdogMatchesPython(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	env := map[string]string{}
	for k, v := range g.Env {
		env[k] = v
	}
	getenv := watchdogGetenv(env)
	lookup := watchdogLookup(env)
	pool := dbPool(t)
	watchSeed(t, pool, watchGolden{Seed: g.Seed})
	seenMail, seenPush := map[string]bool{}, map[string]bool{}
	for i, run := range g.Runs {
		label := run.At
		watchdogApply(t, pool, env, g.Unset, run.Before)
		at, err := time.Parse(time.RFC3339, run.At)
		if err != nil {
			t.Fatal(err)
		}
		res, err := RunFilingWatchdog(context.Background(), pool, lookup, at)
		if err != nil {
			t.Fatalf("run %d (%s): %v", i+1, label, err)
		}
		got := watchdogRunResult{res.AtRisk, res.UnknownRisk, res.AwaitingRetry, res.HostMails, res.Digest}
		watchdogDiff(t, label+" result", got, run.Result)
		if hb := FilingHeartbeatURL(getenv, res.AtRisk > 0); hb != run.Heartbeat {
			t.Errorf("%s heartbeat %q, Python %q", label, hb, run.Heartbeat)
		}
		wantEmails := run.Emails
		if wantEmails == nil {
			wantEmails = []watchdogRunEmail{}
		}
		watchdogDiff(t, label+" emails", watchdogNewEmails(t, pool, seenMail), wantEmails)
		wantPushes := run.Pushes
		if wantPushes == nil {
			wantPushes = []watchdogRunPush{}
		}
		watchdogDiff(t, label+" pushes", watchdogNewPushes(t, pool, seenPush), wantPushes)
		if m := watchdogMailed(t, pool); !reflect.DeepEqual(m, run.Mailed) {
			watchdogDiff(t, label+" at_risk_mailed_at", m, run.Mailed)
		}
		watchdogDiff(t, label+" digest setting", watchdogSetting(t, pool), run.Setting)
	}
}

func watchdogBuilderRows(in []watchdogBuilderRow) []mail.DigestRow {
	out := []mail.DigestRow{}
	for _, r := range in {
		out = append(out, mail.DigestRow{Workspace: r.Workspace, Property: r.Property,
			Arrival: r.Arrival, Deadline: r.Deadline, Unfiled: r.Unfiled})
	}
	return out
}

// TestBuildDeadlineDigestMatchesPython needs no database: the digest for
// inputs no run reaches (more than 50 rows, unknown stays only).
func TestBuildDeadlineDigestMatchesPython(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	names := []string{}
	for _, b := range g.Builders {
		names = append(names, b.Name)
		c, err := mail.BuildDeadlineDigest(g.Env["UBYHOST_PUBLIC_BASE_URL"], "en",
			watchdogBuilderRows(b.Stays), watchdogBuilderRows(b.Unknown))
		if err != nil {
			t.Fatal(err)
		}
		if c.Subject != b.Subject {
			t.Errorf("%s subject %q, Python %q", b.Name, c.Subject, b.Subject)
		}
		if c.Text != b.Text {
			t.Errorf("%s text differs\n got:\n%s\nwant:\n%s", b.Name, c.Text, b.Text)
		}
		if h := sha256Hex(c.HTML); h != b.HTMLSHA256 {
			t.Errorf("%s html sha256 %s, Python %s", b.Name, h, b.HTMLSHA256)
		}
	}
	sort.Strings(names)
	if strings.Join(names, ",") != "digest_overflow,digest_unknown_only" {
		t.Errorf("builder cases %v", names)
	}
}

// TestWatchdogAddressNeverDivergesSilently needs no database: for every
// contact form in the golden, Go gives Python's address, or none with the value
// flagged unreadable (logged at error level, the stay left unmailed). Go never
// mails an address Python would not, and a blank value is not flagged.
func TestWatchdogAddressNeverDivergesSilently(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	if len(g.Contacts) < 25 {
		t.Fatal("golden file has too few contact forms")
	}
	same, flagged := 0, 0
	for _, c := range g.Contacts {
		got, unreadable := watchdogAddress(c.Raw)
		blank := strings.TrimSpace(c.Raw) == ""
		switch {
		case got != "" && got == c.Python && !unreadable:
			same++
		case got == "" && unreadable && !blank:
			flagged++
		case got == "" && c.Python == "" && blank && !unreadable:
		default:
			t.Errorf("contact %q: Go %q (unreadable %v), Python %q", c.Raw, got, unreadable, c.Python)
		}
	}
	if same != 7 || flagged != 20 {
		t.Errorf("%d forms read like Python and %d flagged, want 7 and 20", same, flagged)
	}
	t.Logf("%d forms read like Python, %d flagged and logged", same, flagged)
}

// TestRunFilingWatchdogRefusesBadSweepMinutes needs no database: Python's
// int() refuses the value at start-up, so the Go pass fails before any query.
func TestRunFilingWatchdogRefusesBadSweepMinutes(t *testing.T) {
	env := map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": "abc"}
	_, err := RunFilingWatchdog(context.Background(), nil, watchdogLookup(env), time.Now())
	if err == nil || !strings.Contains(err.Error(), "UBYHOST_SUBMIT_SWEEP_MINUTES") {
		t.Fatalf("got %v, want an error naming UBYHOST_SUBMIT_SWEEP_MINUTES", err)
	}
}
```

   From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ ./internal/mail/ -count=1 2>&1 | tail -30` is ok (the DB test skips here; step 6 runs it; `TestBuildDeadlineDigestMatchesPython` runs here and must pass). Commit "1159b step 4".

5. Create `App/tests/test_filing_watchdog_run_golden.py` (sha256 `38a35a45e34d2a9e0f9b3077a6c6c3c4f53ad368150164b5b26d0ac090436589`) = block 5 below.

   Run `python3 /tmp/extract_block.py docs/tasks/1159b-go-filing-watchdog-run.md 5 App/tests/test_filing_watchdog_run_golden.py && sha256sum App/tests/test_filing_watchdog_run_golden.py | tail -3`.
```python
"""go/internal/calendar/filing_watchdog_run_test.go reads go/internal/calendar/testdata/filing_watchdog_run_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "filing_watchdog_run_golden", APP_DIR / "scripts" / "filing_watchdog_run_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filing_watchdog_run_golden_matches_python_run(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "filing-watchdog-run-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"idempotency_key"') >= 40
```

   From `App/`: `.venv/bin/python -m pytest tests/test_filing_watchdog_run_golden.py tests/test_filing_watchdog_golden.py tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30` passes. Commit "1159b step 5".

6. Go DB test locally (3 calls at most; if PostgreSQL cannot start, say "CI only" with the reason in the report). As root with PostgreSQL 16 installed:

```bash
P=/var/tmp/pg1159b && mkdir -p $P && chown postgres $P && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $P/data -A trust -U postgres" >/dev/null && su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $P/data -o '-p 55440 -k $P' -l $P/log -w start" 2>&1 | tail -3
```

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres go test ./internal/calendar/ -run 'Watchdog|FilingHeartbeat|DeadlineDigest' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

   Expected: eight `--- PASS` lines (incl. `TestRunFilingWatchdogMatchesPython`, `TestWatchdogAddressNeverDivergesSilently` and `TestWatchdogStaysMatchPython`) and `ok`; `level=ERROR` log lines are expected (runs 6 and 8, the unreadable stamp and operator address). A `--- SKIP` means the variable was not seen. A FAIL: STOP (§8), paste the first 30 lines of the diff into the report. Then write the report (§9), set this brief's `Status: review`, commit "1159b step 6".

## 5. Do not touch

`App/app/` (all of it), `App/migrations_pg/`, every existing file in `go/internal/` (1159's files included: `filing_watchdog.go`, `filing_watchdog_test.go`, the 1159 golden and script), `go/cmd/` (incl. `go/cmd/ubyhost-web/main.go`), `go/go.mod`, `go/go.sum`, `docs/ENVIRONMENT.md`, `docs/context/`, `.github/`, every file not in §3. No job kind, env var, route, migration or new dependency. Hard rules 1-5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ ./internal/mail/ -count=1 2>&1 | tail -30` (the DB tests skip without `UBYHOST_TEST_DATABASE_URL`; step 6 runs them).
From `App/` (Filing row of the [test-map](../context/test-map.md), narrowed to the watchdog): `.venv/bin/python -m pytest tests/test_filing_watchdog_run_golden.py tests/test_filing_watchdog_golden.py tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30`.
Golden freshness: from `App/`, `.venv/bin/python scripts/filing_watchdog_run_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after step 1's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The six sha256 values in steps 1-5 match, and the three 1159 hashes in §2 still match.
- [ ] From `go/`: gofmt empty, `go vet ./...` clean, `go test ./internal/calendar/ ./internal/mail/ -count=1` ok.
- [ ] Step 6: the eight tests PASS on local PostgreSQL, or "CI only" with the reason.
- [ ] From `App/`: the three pytest files pass and the freshness command leaves `git status --short ../go` empty.
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat origin/main..HEAD | tail -30` lists only the §3 paths.
- [ ] Six commits "1159b step 1" to "1159b step 6" on `claude/go-filing-watchdog-run`; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- a check in step 0 fails (1159 not merged, a 1159 hash differs, an anchor is missing, a §3 file exists);
- the generated golden hash differs while the script hash matches (the Python behaviour moved: never edit the JSON, the Python or the Go to make it match);
- any Go/Python parity test fails (`TestRunFilingWatchdogMatchesPython`, `TestBuildDeadlineDigestMatchesPython`, `TestWatchdogStaysMatchPython`): a mismatch in who is mailed, what the mail says, the stamp or the digest is a filing-correctness question for the orchestrator, never fixed by the executor; or any test fails twice;
- a change to Python behaviour, a migration, or SQL that is not plain PostgreSQL seems needed;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a new dependency seems needed, or a file outside §3 needs a change;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1159b-report.md` (600 tokens at most) and set this brief's `Status: review`. It has: 1. `git diff --stat origin/main..HEAD | tail -10`; 2. each §6 command and step 6 with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (none expected: nothing is wired).

## Risk list (for the reviewer)

Read `go/internal/calendar/filing_watchdog_run.go` against App/app/filing_watchdog.py 224-355 line by line: skip on truthy `mailed_at` only; push before the address check and outside the error path; no address or mail off: no stamp; stamp format and the `IS NULL` guard; per-stay errors logged and the loop going on; the digest's empty-lists exit, operator default and `watchdogAddress`, the 72 h window `0 <= age < 72 h`, the naive-stamp error, the key `deadline_digest:<stamp>`, setting written only after a queued mail; in `RunFilingWatchdog` the isolation of the unknown-risk query and the digest (neither can fail the pass) and that only the at-risk query fails it. Then `go/internal/mail/deadline_at_risk.go` against App/app/mail_notify.py 2386-2589 and the English catalogue (host_i18n.py 1075-1110), the golden script (each §2 case is in RUNS or BUILDERS), and that the test does not skip in CI (`--- PASS: TestRunFilingWatchdogMatchesPython` in the Go job log).

Known and accepted (not ported 1:1):
- The error-isolation paths (unknown-risk query failure, a failing per-stay mail, a digest failure other than the naive stamp) are mirrored in code but the golden cannot inject those faults; the reviewer checks them by reading.
- Addresses (§2): a form outside the two Go reads is not mailed by Go but by Python; it is never silent (error log, no stamp). Brief E should list production `legal_entity.contact_email` values Go flags before switching.
- Push params are written with sorted keys (`QueuePush`, existing behaviour), Python in insertion order; the values are identical and delivery reads them by key.
- `UBYHOST_PUBLIC_BASE_URL` unset: Python defaults to `http://127.0.0.1:8080`, Go to "" (as the other Go mails); production sets it. The digest-stamp parser reads the forms `isoformat()` writes; a rarer form Python accepts counts as unreadable (digest sent).
- `EnqueueMail` never returns id 0 without an error, so the "no outbox id" branch is kept for parity but is not reachable in Go.

## Owner steps

None for this brief. Before brief E switches production to Go, the orchestrator asks the owner for nothing new here: E carries its own owner steps.
