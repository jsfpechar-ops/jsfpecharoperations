# 1171b: Watchdog alarm only for failed sends

Status: todo
Depends on: 1171 (applied on this branch) | Base commit: da27d45 | Branch: claude/1171-skip-no-police-stays
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The filing watchdog splits stays at risk into `send_failed` (UbyHost tried and it did not go through, or an open alert says it cannot send) and never sent. Only `send_failed` stays set the heartbeat to `/fail` and appear in the operator digest (owner, 2026-11-13: "i only care if we sent a police report and it didnt go through to ubyport", "either ubyport didnt accept it or there was some critical error"). Host mails, pushes and in-app deadline alerts are unchanged: a never-sent stay and an unknown-risk (no guests) stay still get the host mail ("its their choice"). Python and Go stay in parity.

## 2. Context

- Hard rule 1: a send that went wrong must still page. `send_failed` is true for a stay when at least one unfiled reportable guest has `guest.submission_id` set (UbyPort refused it, `outcome_unknown`; the existing awaiting-retry grace rule is unchanged and still runs first), OR the reservation has an unresolved alert (`resolved_at IS NULL`) whose `dedupe_key` is one of:
  - `ubyport_auth_failed:<apartment_id>` (App/app/reporting.py:1900, go/internal/ubyport/submit.go:258; the sweep stops sending, so guests never get a `submission_id`);
  - `submission_transport:<apartment_id>` (reporting.py:1890, submit.go:250). Needed: a transport error does **not** set `guest.submission_id` (reporting.py:1876-1915 only updates the `submission` row), so without this key a failed delivery would count as never sent;
  - `guest_record_unreadable:<apartment_id>` (sweep, reporting.py:2461, go/internal/ubyport/sweep.go:860: "nothing is being reported for this property");
  - `guest_record_unreadable:reservation:<reservation_id>` (reporting.py:2756, go/internal/calendar/watch.go:90).
  `sweep_failed` is left out on purpose (the dead-man switch covers job failures). The test seeds an open `sweep_failed:1` and a resolved `ubyport_auth_failed:1` to prove neither counts.
- Alert columns (App/app/db.py:295): `dedupe_key TEXT`, `resolved_at TEXT`. The fragment uses `'key:' || CAST(r.apartment_id AS TEXT)`, which runs the same on SQLite and Postgres (hard rule 5). Python selects `CASE WHEN EXISTS ... THEN 1 ELSE 0 END`; Go selects `... END = 1` and `g.submission_id IS NOT NULL` and scans both as `bool`.
- `run()` / Go `WatchdogResult`: `at_risk` = count of `send_failed` stays (it alone decides the heartbeat, in `scheduler._job_deadlines` and `deadlines_job.go`, whose code stays as is); new `not_sent` = the other non-awaiting stays; `unknown_risk`, `awaiting_retry`, `host_mails`, `digest` unchanged in meaning. The digest is called with the failed stays and no unknown list.
- Digest copy: no change. `build_deadline_digest` (App/app/mail_notify.py:2532) and `mail.BuildDeadlineDigest` already render a digest without the unknown section (the run golden's `digest_at_risk_only` builder); `send_operator_digest` keeps its `unknown` parameter. The builders' golden outputs are byte-identical.
- Golden: `stay_record` gains `send_failed`. New seed: apartments 9-11 (full login), stays 244-247 with one pending DEU guest each, alert table rows 9101-9106. In the regenerated `filing_watchdog_golden.json` every existing stay record is unchanged apart from the new `send_failed` key; at T0 `send_failed` is true for 204-208, 226-229, 244-247 and false for 201, 202, 209, 210, 222, 224, 225 and the boundary stays. In `filing_watchdog_run_golden.json` each run's `at_risk` drops by 3 or 4 (into `not_sent`), the 10:05 run has 4 more host mails (244-247), the heartbeats and the builders are unchanged.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/filing_watchdog.py | edit | `SEND_FAILED_ALERT_SQL`; `at_risk_stays` selects `submission_id` and `failed_alert`, sets `send_failed`; `run()` digest and counts; docstrings |
| App/app/scheduler.py | edit | `not_sent` in the log condition and the job-run detail |
| go/internal/calendar/filing_watchdog.go | edit | `watchdogSendFailedAlertSQL`; two columns in `watchdogAtRiskSQL`; `WatchdogStay.SendFailed` |
| go/internal/calendar/filing_watchdog_run.go | edit | `WatchdogResult.NotSent`; digest gets failed stays only |
| go/internal/calendar/deadlines_job.go | edit | log `not_sent` |
| go/internal/calendar/filing_watchdog_test.go | edit | `send_failed` in the stay record |
| go/internal/calendar/filing_watchdog_run_test.go | edit | `not_sent` in the result; new `TestRunFilingWatchdogPagesOnlyForFailedSends` |
| App/scripts/filing_watchdog_golden.py | edit | apartments 9-11, stays 244-247, guests 43-46, alert table, `send_failed` in `stay_record` |
| App/tests/test_filing_watchdog.py | edit | alert cleanup; two old tests get a refused batch; 3 new tests (7 cases) |
| go/internal/calendar/testdata/filing_watchdog_golden.json | regenerate | from the script |
| go/internal/calendar/testdata/filing_watchdog_run_golden.json | regenerate | from `filing_watchdog_run_golden.py` (unchanged; it reuses SEED) |

No other file may change.

## 4. Steps

1. Save the patch in the appendix (between the `~~~diff` fences) to `/tmp/1171b.patch` and apply it: `git apply --check /tmp/1171b.patch && git apply /tmp/1171b.patch 2>&1 | tail -30`. If `--check` fails: STOP (§8). Commit `1171b step 1`.
2. Regenerate the goldens (needs `App/.venv`; if missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):
   `cd App && for s in filing_watchdog_golden filing_watchdog_run_golden; do .venv/bin/python scripts/$s.py 2>&1 | tail -1; done`
   (Logged tracebacks before each `wrote ...` line are expected.) Commit `1171b step 2`.
3. Check every file against §7's sha256 list: `sha256sum <the 11 files> 2>&1 | tail -30`. A mismatch: STOP.
4. Run §6. Commit nothing more unless a step changed a file.

## 5. Do not touch

`App/app/mail_notify.py`, `go/internal/mail/`, `App/app/reporting.py`, `go/internal/calendar/watch.go`, `App/scripts/filing_watchdog_run_golden.py`, `docs/context/status.md`, `docs/context/test-map.md`, anything outside §3. Hard rules 1, 3 (fixture values are synthetic), 5, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog*.py tests/test_police_*.py tests/test_*deadline*.py tests/test_claim_*.py tests/test_endtoend.py tests/test_scheduler*.py -q --tb=short -x 2>&1 | tail -30` → `758 passed, 1 skipped` (the skip is playwright in test_police_letter_flow.py).
- Go needs Postgres. Start one if none: `mkdir -p /var/tmp/pg1171 && chown postgres /var/tmp/pg1171 && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1171 -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1171 -o '-p 55471 -k /tmp' -l /var/tmp/pg1171/log start" 2>&1 | tail -3`
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres go test ./internal/calendar/... ./internal/mail/... 2>&1 | tail -30` → two `ok`; with `-v -run 'MatchesPython|Watchdog|FailedSends' ./internal/calendar/` every test is `--- PASS` (none `SKIP`).
- `cd go && gofmt -l internal/calendar/ && go vet ./internal/calendar/... ./internal/mail/... 2>&1 | tail -30` → no output.
- `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] sha256 of each resulting file:
  - `App/app/filing_watchdog.py` `910bc6356eb7ccb77dbeb5aad065aac954c1a6da27e8fd9a20eb3da0dd9d1cab`
  - `App/app/scheduler.py` `796575a63540c3e66aef322b5a288140fc0fd9ff9730026079a733a77aa73377`
  - `App/scripts/filing_watchdog_golden.py` `ce932478e6bb1d25647511efaafada0a4797a03c56769cae9f3d35ed0e090161`
  - `App/tests/test_filing_watchdog.py` `24c46f1c035982f743a829cf088a3123962a58638e29d5fc810cddcd50dee23a`
  - `go/internal/calendar/deadlines_job.go` `84c77f4da3def25307e31013e93b3101ec3e34571cd0182bf79a4b845ee3addf`
  - `go/internal/calendar/filing_watchdog.go` `543b81f742b9ab017996ef7e1f84f2580b5630b63651a92774322a7f29e1abcb`
  - `go/internal/calendar/filing_watchdog_run.go` `b6c7d4fbeb7243ca30be745b8b20681ee2cde79b9f3ef4ddb4627f7ae8df3ec3`
  - `go/internal/calendar/filing_watchdog_run_test.go` `ab31d5b8182108bcae8c2c36f378b73d45a0e5a9001b254d85641d69418ba4f8`
  - `go/internal/calendar/filing_watchdog_test.go` `03cd97fa0862d1fb3c460bb6d9bbb3710f76c5e2f45b56a6284c3433c8bbb11c`
  - `go/internal/calendar/testdata/filing_watchdog_golden.json` `9ba24dc344d55365a39ff9d7f3d83fe774a60ae7859143b6888abb3617cc9a95`
  - `go/internal/calendar/testdata/filing_watchdog_run_golden.json` `879b86c9c7bb52d42e2d4f1f11104f0fab17c5b8bb0dd61aeb1566e8b979240f`
- [ ] The regenerated JSON differs from base only as §2 "Golden" says.
- [ ] All §6 commands pass as stated.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found or `git apply --check` fails;
- a test fails twice;
- a sha256 in §7 does not match;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1171b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/filing_watchdog.py`, `go/internal/calendar/filing_watchdog.go`: the alert fragment has identical keys in both languages and matches the keys reporting.py and go/internal/ubyport raise; a renamed dedupe key there silently turns failures into `not_sent`.
- A guest whose send stopped mid-flight (the stale-submission reaper) keeps `submission_id`, so it counts as failed: correct. A guest the sweep never picked up (incomplete, retry cap reached without a `submission_id`, `automation_mode` manual) is `not_sent`: the host mail still goes out, the operator is not paged.
- Risk: the retry cap (`SUBMISSION_MAX_AUTO_ATTEMPTS`) is only reached after real attempts, which set `submission_id`; if some path clears `submission_id` after a failure (the auto-resend frees it briefly in `reporting.py:2304` and puts it back in a `finally`), a run that lands in that window sees the stay as `not_sent` for one pass only.
- `run()`/`WatchdogResult`: `at_risk` now means failed sends only; nothing else reads it but the heartbeat and the logs.

## Owner steps

1. After the PR is green, merge it with `scripts/merge-pr-on-green.sh`.
2. From then on the filing heartbeat and the 72-hour digest only fire when UbyHost tried to send and it failed (refused, no connection, login refused, unreadable guest record). Hosts who file elsewhere still get their own warning mail.

## Appendix: the patch (code, scripts, tests; the JSON is regenerated in step 2)

~~~diff
diff --git a/App/app/filing_watchdog.py b/App/app/filing_watchdog.py
index f520efb..0415335 100644
--- a/App/app/filing_watchdog.py
+++ b/App/app/filing_watchdog.py
@@ -44,6 +44,15 @@ reportable, so a stay of Czech guests nobody typed in does not page anyone.
 or password blank, ``reporting.FILES_WITH_UBYHOST_SQL``) is in neither list.
 UbyHost files nothing for that property, so it gets no host mail, no digest
 line and never sets the heartbeat to ``/fail``.
+
+1171b: the alarm is for sends that went wrong, not for hosts who file
+elsewhere. A stay at risk is ``send_failed`` when UbyHost tried and it did not
+go through: an unfiled reportable guest has a ``submission_id`` (UbyPort
+refused it, the transport failed or the answer was unclear), or an open alert
+says UbyHost cannot send (``SEND_FAILED_ALERT_SQL``). Only those stays decide
+the heartbeat and appear in the operator digest (``at_risk``). A stay with no
+attempt (``not_sent``) and an unknown-risk stay still get the host mail, but
+the operator is not paged or mailed about them.
 """
 from __future__ import annotations
 
@@ -69,6 +78,17 @@ UNKNOWN_RISK_MAX_OVERDUE = timedelta(days=7)
 # resent yet is treated as "awaiting the automatic resend" rather than at risk:
 # two sweep intervals, so one missed sweep run does not raise the alarm.
 RETRY_GRACE = timedelta(minutes=2 * max(1, config.SUBMIT_SWEEP_MINUTES))
+# 1171b: an open alert that means UbyHost could not send for this stay
+# (``r`` reservation): the police login refused, a batch that never reached
+# UbyPort, or a guest record that cannot be decrypted. The dedupe keys are
+# the ones reporting.py raises; the Go copy is watchdogSendFailedAlertSQL.
+SEND_FAILED_ALERT_SQL = (
+    "EXISTS (SELECT 1 FROM alert al WHERE al.resolved_at IS NULL AND al.dedupe_key IN ("
+    "'ubyport_auth_failed:' || CAST(r.apartment_id AS TEXT), "
+    "'submission_transport:' || CAST(r.apartment_id AS TEXT), "
+    "'guest_record_unreadable:' || CAST(r.apartment_id AS TEXT), "
+    "'guest_record_unreadable:reservation:' || CAST(r.id AS TEXT)))"
+)
 
 
 def _awaiting_retry(row, current_utc: datetime) -> bool:
@@ -100,7 +120,8 @@ def at_risk_stays(
 
     A stay whose every unfiled guest is awaiting the automatic resend and whose
     deadline has not passed is left out, unless ``include_awaiting_retry``;
-    it then carries ``awaiting_retry=True``.
+    it then carries ``awaiting_retry=True``. ``send_failed`` is the 1171b
+    split (see the module docstring).
     """
     local = deadlines.local_now(now)
     current_utc = _utc(now)
@@ -111,7 +132,8 @@ def at_risk_stays(
         "r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id, "
         "u.username AS workspace, g.nationality, "
         "s.state AS sub_state, s.retried_at AS sub_retried_at, "
-        "s.finished_at AS sub_finished_at "
+        "s.finished_at AS sub_finished_at, g.submission_id, "
+        "CASE WHEN " + SEND_FAILED_ALERT_SQL + " THEN 1 ELSE 0 END AS failed_alert "
         "FROM reservation r "
         "JOIN apartment a ON a.id = r.apartment_id "
         "JOIN guest g ON g.reservation_id = r.id "
@@ -142,8 +164,11 @@ def at_risk_stays(
                 "mailed_at": row["at_risk_mailed_at"],
                 "unfiled": 0,
                 "awaiting_retry_guests": 0,
+                "send_failed": False,
             }
         stay["unfiled"] += 1
+        if row["submission_id"] or row["failed_alert"]:
+            stay["send_failed"] = True
         if _awaiting_retry(row, current_utc):
             stay["awaiting_retry_guests"] += 1
     found: List[Dict[str, Any]] = []
@@ -332,8 +357,11 @@ def send_operator_digest(
 def run(now: Optional[datetime] = None) -> Dict[str, int]:
     """One watchdog pass. Raises only if the at-risk query itself fails.
 
-    ``at_risk`` counts only stays with known reportable guests; it alone
-    decides the heartbeat. ``unknown_risk`` (no guest on file) does not.
+    ``at_risk`` counts only stays with known reportable guests whose send
+    failed (``send_failed``); it alone decides the heartbeat, and only those
+    stays go in the operator digest. ``not_sent`` counts the other stays with
+    reportable guests: UbyHost never tried, so they get the host mail only.
+    ``unknown_risk`` (no guest on file) gets the host mail only too.
     ``awaiting_retry`` counts the stays left out because their one automatic
     resend is still due (see the module docstring); they do not decide the
     heartbeat and get no mail yet.
@@ -347,14 +375,16 @@ def run(now: Optional[datetime] = None) -> Dict[str, int]:
         # The weaker check must not silence the real one or its heartbeat.
         log.exception("unknown-risk query failed")
         unknown = []
+    failed = [stay for stay in stays if stay["send_failed"]]
     host_mails = notify_hosts(stays + unknown, now)
     try:
-        digest = send_operator_digest(stays, now, unknown=unknown)
+        digest = send_operator_digest(failed, now)
     except Exception:
         log.exception("deadline digest failed")
         digest = False
     return {
-        "at_risk": len(stays),
+        "at_risk": len(failed),
+        "not_sent": len(stays) - len(failed),
         "unknown_risk": len(unknown),
         "awaiting_retry": awaiting,
         "host_mails": host_mails,
diff --git a/App/app/scheduler.py b/App/app/scheduler.py
index 86acf85..8bf175d 100644
--- a/App/app/scheduler.py
+++ b/App/app/scheduler.py
@@ -243,7 +243,7 @@ def _job_deadlines() -> None:
     try:
         watchdog = filing_watchdog.run()
         if (
-            watchdog["at_risk"] or watchdog.get("unknown_risk") or watchdog.get("awaiting_retry")
+            watchdog["at_risk"] or watchdog.get("not_sent") or watchdog.get("unknown_risk") or watchdog.get("awaiting_retry")
             or watchdog["host_mails"] or watchdog["digest"]
         ):
             log.info("filing watchdog: %s", watchdog)
@@ -261,6 +261,7 @@ def _job_deadlines() -> None:
             "alerts": raised or 0,
             "requests_due": due_requests or 0,
             "at_risk": watchdog["at_risk"],
+            "not_sent": watchdog.get("not_sent", 0),
             "unknown_risk": watchdog.get("unknown_risk", 0),
             "awaiting_retry": watchdog.get("awaiting_retry", 0),
             "host_mails": watchdog["host_mails"],
diff --git a/App/scripts/filing_watchdog_golden.py b/App/scripts/filing_watchdog_golden.py
index 2055a0d..2295006 100644
--- a/App/scripts/filing_watchdog_golden.py
+++ b/App/scripts/filing_watchdog_golden.py
@@ -101,6 +101,10 @@ SEED = [
              "enc-test"],
             [8, 1, 1, "Bez hesla", "Brno", "UBY", "tok8", 1, STAMP, "IDUB-TEST", "ws-test",
              None],
+            # 1171b: full login, but an open alert says UbyHost cannot send.
+            [9, 1, 1, "Odmitnute heslo", "Brno", "UBY", "tok9", 1, STAMP, *UBY_LOGIN],
+            [10, 1, 1, "Bez spojeni", "Brno", "UBY", "tok10", 1, STAMP, *UBY_LOGIN],
+            [11, 1, 1, "Necitelny host", "Brno", "UBY", "tok11", 1, STAMP, *UBY_LOGIN],
         ],
     },
     {
@@ -158,6 +162,11 @@ SEED = [
             _stay(241, 6, "2026-09-15"),  # 1171: would be at risk: neither list
             _stay(242, 7, "2026-09-10"),  # 1171: would be overdue: neither list
             _stay(243, 8, "2026-09-12"),  # 1171: no guests, would be unknown risk: neither
+            # 1171b: send_failed by an open alert although no guest was sent.
+            _stay(244, 9, "2026-09-15"),  # ubyport_auth_failed:9 open
+            _stay(245, 10, "2026-09-15"),  # submission_transport:10 open
+            _stay(246, 11, "2026-09-15"),  # guest_record_unreadable:11 open (sweep)
+            _stay(247, 1, "2026-09-15"),  # guest_record_unreadable:reservation:247 open
         ],
     },
     {
@@ -197,6 +206,30 @@ SEED = [
             _guest(31, 229, submission=309, state="error"),
             _guest(41, 241),
             _guest(42, 242, "USA", state="error"),
+            _guest(43, 244),
+            _guest(44, 245),
+            _guest(45, 246),
+            _guest(46, 247),
+        ],
+    },
+    {
+        # 1171b: open alerts that make a stay send_failed, a resolved one and
+        # an unrelated open one that must not (201 stays not_sent).
+        "table": "alert",
+        "columns": ["id", "level", "kind", "apartment_id", "reservation_id", "dedupe_key",
+                    "message", "created_at", "resolved_at"],
+        "rows": [
+            [9101, "critical", "ubyport_auth_failed", 9, None, "ubyport_auth_failed:9",
+             "x", STAMP, None],
+            [9102, "critical", "submission_transport", 10, None, "submission_transport:10",
+             "x", STAMP, None],
+            [9103, "critical", "guest_record_unreadable", 11, None,
+             "guest_record_unreadable:11", "x", STAMP, None],
+            [9104, "critical", "guest_record_unreadable", 1, 247,
+             "guest_record_unreadable:reservation:247", "x", STAMP, None],
+            [9105, "critical", "ubyport_auth_failed", 1, None, "ubyport_auth_failed:1",
+             "x", STAMP, "2026-09-16T00:00:00+00:00"],
+            [9106, "warning", "sweep_failed", 1, None, "sweep_failed:1", "x", STAMP, None],
         ],
     },
     {
@@ -298,6 +331,7 @@ def stay_record(stay: dict) -> dict:
         "unfiled": stay["unfiled"],
         "awaiting_retry_guests": stay.get("awaiting_retry_guests", 0),
         "awaiting_retry": bool(stay.get("awaiting_retry")),
+        "send_failed": bool(stay.get("send_failed")),
         "no_guests": bool(stay.get("no_guests")),
         "arrival": stay["arrival"].isoformat(),
         "deadline": stay["deadline"].isoformat(),
diff --git a/App/tests/test_filing_watchdog.py b/App/tests/test_filing_watchdog.py
index 2ff048c..21d5176 100644
--- a/App/tests/test_filing_watchdog.py
+++ b/App/tests/test_filing_watchdog.py
@@ -48,6 +48,7 @@ def _cleanup() -> None:
         )
         db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
         db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
+        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
         db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
         if apartment["legal_entity_id"]:
             db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
@@ -363,6 +364,7 @@ def test_the_real_watchdog_runs_inside_the_deadline_job(world, pings, monkeypatc
     """No stub for run(): the job computes the answer and pings with it."""
     monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
+    _refused_batch(world, rid)
     scheduler._job_deadlines()
     assert pings == ["https://hc-ping.example.invalid/abc/fail"]
     assert rid in _mine(filing_watchdog.at_risk_stays(), {rid})
@@ -534,6 +536,7 @@ def test_a_broken_unknown_risk_query_does_not_silence_the_watchdog(world, monkey
 
     monkeypatch.setattr(filing_watchdog, "unknown_risk_stays", boom)
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
+    _refused_batch(world, rid)
     result = filing_watchdog.run()
     assert result["at_risk"] >= 1 and result["unknown_risk"] == 0
     assert rid in _mine(filing_watchdog.at_risk_stays(), {rid})
@@ -714,3 +717,134 @@ def test_a_stay_held_on_an_unclear_automatic_resend_is_at_risk_after_the_grace(w
     # No later resend can move the finish time on, so it stays at risk.
     much_later = WEDNESDAY_MORNING + 5 * filing_watchdog.RETRY_GRACE
     assert rid in _mine(filing_watchdog.at_risk_stays(much_later), {rid})
+
+
+# 1171b: only a send that went wrong pages the operator. A stay UbyHost never
+# tried to send (the host files elsewhere, or the guest is not complete) gets
+# the host mail and nothing else.
+
+
+def _refused_batch(world, reservation_id):
+    """Put every guest of the stay on a batch UbyPort refused."""
+    guest_ids = [
+        row["id"]
+        for row in db.query("SELECT id FROM guest WHERE reservation_id = ?", (reservation_id,))
+    ]
+    stamp = db.utcnow()
+    submission_id = db.insert(
+        "submission",
+        {
+            "apartment_id": world["apartment_id"],
+            "created_at": stamp,
+            "finished_at": stamp,
+            "mode": "auto",
+            "state": "error",
+            "guest_ids": json.dumps(guest_ids),
+            "error_text": "refused",
+        },
+    )
+    for guest_id in guest_ids:
+        db.update("guest", guest_id, {"submission_id": submission_id, "submit_state": "error"})
+    return submission_id
+
+
+def _open_alert(world, dedupe_key, *, reservation_id=None, resolved=False):
+    stamp = db.utcnow()
+    db.insert(
+        "alert",
+        {
+            "level": "critical",
+            "kind": dedupe_key.split(":")[0],
+            "apartment_id": world["apartment_id"],
+            "reservation_id": reservation_id,
+            "dedupe_key": dedupe_key,
+            "message": "test",
+            "created_at": stamp,
+            "resolved_at": stamp if resolved else None,
+        },
+    )
+
+
+def _only(monkeypatch, ids):
+    """Keep run() to this test's stays: the shared database may hold others."""
+    at_risk, unknown = filing_watchdog.at_risk_stays, filing_watchdog.unknown_risk_stays
+    monkeypatch.setattr(
+        filing_watchdog, "at_risk_stays",
+        lambda now=None, **kw: [s for s in at_risk(now, **kw) if s["reservation_id"] in ids],
+    )
+    monkeypatch.setattr(
+        filing_watchdog, "unknown_risk_stays",
+        lambda now=None: [s for s in unknown(now) if s["reservation_id"] in ids],
+    )
+
+
+def _mail_on(monkeypatch):
+    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
+    monkeypatch.setattr(config, "OPERATOR_EMAIL", "operator@example.invalid")
+    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
+
+
+def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeypatch):
+    _mail_on(monkeypatch)
+    rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
+    # A resolved login alert and an unrelated open one do not count.
+    _open_alert(world, f"ubyport_auth_failed:{world['apartment_id']}", resolved=True)
+    _open_alert(world, f"sweep_failed:{world['apartment_id']}")
+    _only(monkeypatch, {rid})
+    stay = _mine(filing_watchdog.at_risk_stays(), {rid})[rid]
+    assert stay["send_failed"] is False
+    result = filing_watchdog.run()
+    assert (result["at_risk"], result["not_sent"], result["host_mails"], result["digest"]) == (
+        0, 1, 1, 0
+    )
+    assert len(_outbox("deadline_at_risk", rid)) == 1
+    assert _outbox("deadline_digest") == []
+    scheduler._job_deadlines()
+    assert pings == ["https://hc-ping.example.invalid/abc"]
+
+
+@pytest.mark.parametrize(
+    "failure", ["refused", "auth", "transport", "unreadable_property", "unreadable_stay"]
+)
+def test_a_failed_send_on_a_configured_property_pages_and_is_in_the_digest(
+    world, pings, monkeypatch, failure
+):
+    _mail_on(monkeypatch)
+    rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
+    apartment_id = world["apartment_id"]
+    if failure == "refused":
+        _refused_batch(world, rid)
+    else:
+        key = {
+            "auth": f"ubyport_auth_failed:{apartment_id}",
+            "transport": f"submission_transport:{apartment_id}",
+            "unreadable_property": f"guest_record_unreadable:{apartment_id}",
+            "unreadable_stay": f"guest_record_unreadable:reservation:{rid}",
+        }[failure]
+        _open_alert(world, key, reservation_id=rid if failure == "unreadable_stay" else None)
+    _only(monkeypatch, {rid})
+    assert _mine(filing_watchdog.at_risk_stays(), {rid})[rid]["send_failed"] is True
+    result = filing_watchdog.run()
+    assert (result["at_risk"], result["not_sent"], result["host_mails"], result["digest"]) == (
+        1, 0, 1, 1
+    )
+    text = json.loads(_outbox("deadline_digest")[0]["payload"])["text"]
+    assert "Watchdog Loft" in text and GUEST_SURNAME not in text
+    scheduler._job_deadlines()
+    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
+
+
+def test_a_stay_without_guests_is_not_in_the_digest(world, monkeypatch):
+    _mail_on(monkeypatch)
+    local = filing_watchdog.deadlines.local_now()
+    arrival = next(
+        date.today() - timedelta(days=back)
+        for back in range(0, 14)
+        if filing_watchdog.deadlines.reporting_deadline(date.today() - timedelta(days=back))
+        - local <= filing_watchdog.AT_RISK_WINDOW
+    )
+    rid = world["add_stay"]([], arrival=arrival)
+    _only(monkeypatch, {rid})
+    result = filing_watchdog.run()
+    assert (result["unknown_risk"], result["host_mails"], result["digest"]) == (1, 1, 0)
+    assert _outbox("deadline_digest") == []
diff --git a/go/internal/calendar/deadlines_job.go b/go/internal/calendar/deadlines_job.go
index 7f8cfca..904feef 100644
--- a/go/internal/calendar/deadlines_job.go
+++ b/go/internal/calendar/deadlines_job.go
@@ -87,7 +87,7 @@ func runDeadlines(s deadlinesSteps) (DeadlinesSummary, error) {
 	}
 	sum.Watchdog = w
 	if w != (WatchdogResult{}) {
-		slog.Info("filing watchdog", "at_risk", w.AtRisk, "unknown_risk", w.UnknownRisk,
+		slog.Info("filing watchdog", "at_risk", w.AtRisk, "not_sent", w.NotSent, "unknown_risk", w.UnknownRisk,
 			"awaiting_retry", w.AwaitingRetry, "host_mails", w.HostMails, "digest", w.Digest)
 	}
 	// A failed deadline watch counts as a failure too: nobody is being told.
diff --git a/go/internal/calendar/filing_watchdog.go b/go/internal/calendar/filing_watchdog.go
index 280974b..e96fd20 100644
--- a/go/internal/calendar/filing_watchdog.go
+++ b/go/internal/calendar/filing_watchdog.go
@@ -32,13 +32,25 @@ const (
 	watchdogSweepMinutesDefault = 10
 )
 
+// watchdogSendFailedAlertSQL is SEND_FAILED_ALERT_SQL (1171b): an open alert
+// that means UbyHost could not send for the stay r. The dedupe keys are the
+// ones App/app/reporting.py and go/internal/ubyport raise.
+const watchdogSendFailedAlertSQL = `EXISTS (SELECT 1 FROM alert al WHERE al.resolved_at IS NULL AND al.dedupe_key IN (
+	'ubyport_auth_failed:' || CAST(r.apartment_id AS TEXT),
+	'submission_transport:' || CAST(r.apartment_id AS TEXT),
+	'guest_record_unreadable:' || CAST(r.apartment_id AS TEXT),
+	'guest_record_unreadable:reservation:' || CAST(r.id AS TEXT)))`
+
 // watchdogAtRiskSQL is the unfiled guests with a nationality on watched stays.
 // nationality and submit_state are plain columns: nothing is decrypted. $1 is
-// reporting.SENT. The submission columns feed _awaiting_retry.
+// reporting.SENT. The submission columns feed _awaiting_retry; the last two
+// feed SendFailed (1171b).
 const watchdogAtRiskSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
 	r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id,
 	COALESCE(u.username, ''), g.nationality,
-	COALESCE(s.state, ''), COALESCE(s.retried_at, ''), COALESCE(s.finished_at, '')
+	COALESCE(s.state, ''), COALESCE(s.retried_at, ''), COALESCE(s.finished_at, ''),
+	g.submission_id IS NOT NULL,
+	CASE WHEN ` + watchdogSendFailedAlertSQL + ` THEN 1 ELSE 0 END = 1
 	FROM reservation r
 	JOIN apartment a ON a.id = r.apartment_id
 	JOIN guest g ON g.reservation_id = r.id
@@ -82,10 +94,14 @@ type WatchdogStay struct {
 	Unfiled             int
 	AwaitingRetryGuests int
 	AwaitingRetry       bool
-	NoGuests            bool
-	Arrival             time.Time
-	Deadline            time.Time
-	Overdue             bool
+	// SendFailed is send_failed (1171b): UbyHost tried and it did not go
+	// through, or an open alert says it cannot send. Only such stays decide
+	// the heartbeat and go in the operator digest.
+	SendFailed bool
+	NoGuests   bool
+	Arrival    time.Time
+	Deadline   time.Time
+	Overdue    bool
 }
 
 // watchdogIntUnderscores is an integer literal with digit-group underscores,
@@ -164,9 +180,10 @@ func AtRiskStays(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string)
 	for rows.Next() {
 		var s WatchdogStay
 		var nationality, subState, subRetried, subFinished string
+		var hasSubmission, failedAlert bool
 		if err := rows.Scan(&s.ReservationID, &s.DateFrom, &s.MailedAt, &s.ApartmentID, &s.Property,
 			&s.LegalEntityID, &s.OwnerUserID, &s.Workspace, &nationality,
-			&subState, &subRetried, &subFinished); err != nil {
+			&subState, &subRetried, &subFinished, &hasSubmission, &failedAlert); err != nil {
 			rows.Close()
 			return nil, err
 		}
@@ -180,6 +197,9 @@ func AtRiskStays(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string)
 			order = append(order, s.ReservationID)
 		}
 		stay.Unfiled++
+		if hasSubmission || failedAlert {
+			stay.SendFailed = true
+		}
 		if watchdogAwaitingRetry(subState, subRetried, subFinished, current, grace) {
 			stay.AwaitingRetryGuests++
 		}
diff --git a/go/internal/calendar/filing_watchdog_run.go b/go/internal/calendar/filing_watchdog_run.go
index 64569c1..93382ab 100644
--- a/go/internal/calendar/filing_watchdog_run.go
+++ b/go/internal/calendar/filing_watchdog_run.go
@@ -40,6 +40,7 @@ var errWatchdogNaiveStamp = errors.New("filing watchdog: digest stamp has no UTC
 // WatchdogResult is the dict run() returns.
 type WatchdogResult struct {
 	AtRisk        int
+	NotSent       int
 	UnknownRisk   int
 	AwaitingRetry int
 	HostMails     int
@@ -352,8 +353,10 @@ func SendOperatorDigest(ctx context.Context, pool *pgxpool.Pool, getenv func(str
 
 // RunFilingWatchdog is filing_watchdog.run: one watchdog pass. It fails only
 // when the at-risk query fails. AtRisk counts only stays with known reportable
-// guests and alone decides the heartbeat (FilingHeartbeatURL); UnknownRisk and
-// AwaitingRetry do not. The unknown-risk query and the digest are isolated: a
+// guests whose send failed (SendFailed, 1171b); it alone decides the heartbeat
+// (FilingHeartbeatURL) and only those stays go in the operator digest. NotSent
+// (UbyHost never tried) and UnknownRisk get the host mail only; AwaitingRetry
+// gets nothing yet. The unknown-risk query and the digest are isolated: a
 // failure is logged and the pass goes on, so neither silences the real check.
 // lookupEnv is os.LookupEnv in production; an unreadable
 // UBYHOST_SUBMIT_SWEEP_MINUTES fails the pass, as Python refuses to start.
@@ -378,17 +381,24 @@ func RunFilingWatchdog(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(s
 		slog.Error("unknown-risk query failed", "err", err)
 		unknown = nil
 	}
+	var failed []WatchdogStay
+	for _, s := range stays {
+		if s.SendFailed {
+			failed = append(failed, s)
+		}
+	}
 	both := make([]WatchdogStay, 0, len(stays)+len(unknown))
 	both = append(both, stays...)
 	both = append(both, unknown...)
 	hostMails := NotifyHosts(ctx, pool, getenv, both, at)
-	digest, err := SendOperatorDigest(ctx, pool, getenv, stays, unknown, at)
+	digest, err := SendOperatorDigest(ctx, pool, getenv, failed, nil, at)
 	if err != nil {
 		slog.Error("deadline digest failed", "err", err)
 		digest = false
 	}
 	result := WatchdogResult{
-		AtRisk:        len(stays),
+		AtRisk:        len(failed),
+		NotSent:       len(stays) - len(failed),
 		UnknownRisk:   len(unknown),
 		AwaitingRetry: len(every) - len(stays),
 		HostMails:     hostMails,
diff --git a/go/internal/calendar/filing_watchdog_run_test.go b/go/internal/calendar/filing_watchdog_run_test.go
index 0b41f5c..5b45a94 100644
--- a/go/internal/calendar/filing_watchdog_run_test.go
+++ b/go/internal/calendar/filing_watchdog_run_test.go
@@ -47,6 +47,7 @@ type watchdogRunPush struct {
 
 type watchdogRunResult struct {
 	AtRisk        int `json:"at_risk"`
+	NotSent       int `json:"not_sent"`
 	UnknownRisk   int `json:"unknown_risk"`
 	AwaitingRetry int `json:"awaiting_retry"`
 	HostMails     int `json:"host_mails"`
@@ -275,7 +276,7 @@ func TestRunFilingWatchdogMatchesPython(t *testing.T) {
 		if err != nil {
 			t.Fatalf("run %d (%s): %v", i+1, label, err)
 		}
-		got := watchdogRunResult{res.AtRisk, res.UnknownRisk, res.AwaitingRetry, res.HostMails, res.Digest}
+		got := watchdogRunResult{res.AtRisk, res.NotSent, res.UnknownRisk, res.AwaitingRetry, res.HostMails, res.Digest}
 		watchdogDiff(t, label+" result", got, run.Result)
 		if hb := FilingHeartbeatURL(getenv, res.AtRisk > 0); hb != run.Heartbeat {
 			t.Errorf("%s heartbeat %q, Python %q", label, hb, run.Heartbeat)
@@ -372,3 +373,52 @@ func TestRunFilingWatchdogRefusesBadSweepMinutes(t *testing.T) {
 		t.Fatalf("got %v, want an error naming UBYHOST_SUBMIT_SWEEP_MINUTES", err)
 	}
 }
+
+// TestRunFilingWatchdogPagesOnlyForFailedSends pins 1171b on the golden seed
+// with all other stays archived: a stay UbyHost never sent (201) gets the host
+// mail but no digest and the heartbeat stays green; a refused batch (229) or
+// an open ubyport_auth_failed alert on a fully configured property (244)
+// fails the heartbeat and goes in the digest.
+func TestRunFilingWatchdogPagesOnlyForFailedSends(t *testing.T) {
+	g := loadWatchdogRunGolden(t)
+	at, err := time.Parse(time.RFC3339, "2026-09-17T11:00:00+00:00")
+	if err != nil {
+		t.Fatal(err)
+	}
+	cases := []struct {
+		name            string
+		stay            int64
+		atRisk, notSent int
+		digest          int
+		ping            string
+	}{
+		{"never sent", 201, 0, 1, 0, "https://hc.example.test/ping/abc"},
+		{"refused batch", 229, 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"login refused", 244, 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+	}
+	for _, c := range cases {
+		t.Run(c.name, func(t *testing.T) {
+			env := map[string]string{}
+			for k, v := range g.Env {
+				env[k] = v
+			}
+			pool := dbPool(t)
+			watchSeed(t, pool, watchGolden{Seed: g.Seed})
+			if _, err := pool.Exec(context.Background(),
+				`UPDATE reservation SET archived_at = '2026-09-16' WHERE id != $1`, c.stay); err != nil {
+				t.Fatal(err)
+			}
+			res, err := RunFilingWatchdog(context.Background(), pool, watchdogLookup(env), at)
+			if err != nil {
+				t.Fatal(err)
+			}
+			if res.AtRisk != c.atRisk || res.NotSent != c.notSent || res.HostMails != 1 || res.Digest != c.digest {
+				t.Fatalf("result %+v, want at_risk %d not_sent %d host_mails 1 digest %d",
+					res, c.atRisk, c.notSent, c.digest)
+			}
+			if got := FilingHeartbeatURL(watchdogGetenv(env), res.AtRisk > 0); got != c.ping {
+				t.Fatalf("heartbeat %q, want %q", got, c.ping)
+			}
+		})
+	}
+}
diff --git a/go/internal/calendar/filing_watchdog_test.go b/go/internal/calendar/filing_watchdog_test.go
index 69a1eaa..e60bb5c 100644
--- a/go/internal/calendar/filing_watchdog_test.go
+++ b/go/internal/calendar/filing_watchdog_test.go
@@ -24,6 +24,7 @@ type watchdogStayRecord struct {
 	Unfiled             int     `json:"unfiled"`
 	AwaitingRetryGuests int     `json:"awaiting_retry_guests"`
 	AwaitingRetry       bool    `json:"awaiting_retry"`
+	SendFailed          bool    `json:"send_failed"`
 	NoGuests            bool    `json:"no_guests"`
 	Arrival             string  `json:"arrival"`
 	Deadline            string  `json:"deadline"`
@@ -96,6 +97,7 @@ func watchdogRecord(s WatchdogStay) watchdogStayRecord {
 		Unfiled:             s.Unfiled,
 		AwaitingRetryGuests: s.AwaitingRetryGuests,
 		AwaitingRetry:       s.AwaitingRetry,
+		SendFailed:          s.SendFailed,
 		NoGuests:            s.NoGuests,
 		Arrival:             s.Arrival.Format("2006-01-02"),
 		Deadline:            s.Deadline.Format("2006-01-02T15:04:05"),
~~~
