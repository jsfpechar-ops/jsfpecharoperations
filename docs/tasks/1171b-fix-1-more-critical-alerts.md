# 1171b fix 1: More critical alerts page the operator

Status: todo
Depends on: 1171b (applied on this branch) | Base commit: dc03683 | Branch: claude/1171-skip-no-police-stays
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three more open alerts make a stay `send_failed`, so they set the filing heartbeat to `/fail` and appear in the operator digest: `sweep_failed`, `apartment_setup` and `submission_outcome_unknown`. Without them a fully configured property can stop sending while the heartbeat stays green (owner rule: the alarm fires when "ubyport didnt accept it or there was some critical error").

## 2. Context

- Review finding on 1171b: the alert list in `SEND_FAILED_ALERT_SQL` (App/app/filing_watchdog.py) and `watchdogSendFailedAlertSQL` (go/internal/calendar/filing_watchdog.go) misses critical errors that stop a configured property from sending.
- The three keys, all per property (`<apartment_id>`), exactly as raised:
  - `sweep_failed:<apartment_id>`: App/app/reporting.py:2477, go/internal/ubyport/sweep.go:870. The sweep catches each property's exception itself, so the job heartbeat stays green and the dead-man switch does **not** cover it. This reverses 1171b's "left out on purpose".
  - `apartment_setup:<apartment_id>`: reporting.py:2371, sweep.go:298. The sweep validates the decrypted login; `decrypt_secret` returns `""` on a wrong or rotated SECRET_KEY, so every property stops sending. Blank logins are already left out of the watch by 1171.
  - `submission_outcome_unknown:<apartment_id>`: reporting.py:1856 and 2143, go/internal/ubyport/submit.go:232, recover.go:169. Backstop for the crash-resend path, which sets `guest.submission_id = NULL` (reporting.py:2178-2185) before resending.
- The fragment form stays `'key:' || CAST(r.apartment_id AS TEXT)` (hard rule 5, same on SQLite and Postgres).
- Golden seed: row 9106 was an open `sweep_failed:1`, which would now make every apartment-1 stay `send_failed`. It becomes an open, truly unrelated `door_code_failed:201` (reservation 201). In both regenerated JSON files only that seed row changes; every computed output is byte-identical.
- Python test: the never-sent test's "unrelated open alert" becomes `door_code_failed:<rid>`; the failed-send test gains three parametrized cases. Go: `TestRunFilingWatchdogPagesOnlyForFailedSends` gains three cases that insert the alert for stay 201 (apartment 1).
- The golden run script prints a logged `TypeError` traceback from `send_operator_digest` (naive digest stamp seed case); that is existing behaviour and the script still writes the file.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/filing_watchdog.py | edit | 3 keys in `SEND_FAILED_ALERT_SQL`; comment, with the dismiss line |
| go/internal/calendar/filing_watchdog.go | edit | same 3 keys in `watchdogSendFailedAlertSQL`; comment |
| App/tests/test_filing_watchdog.py | edit | unrelated alert is `door_code_failed`; 3 new failure cases |
| go/internal/calendar/filing_watchdog_run_test.go | edit | `alert` field; 3 new cases |
| App/scripts/filing_watchdog_golden.py | edit | seed row 9106 |
| go/internal/calendar/testdata/filing_watchdog_golden.json | regenerate | from the script (seed row only) |
| go/internal/calendar/testdata/filing_watchdog_run_golden.json | regenerate | from the run script (seed row only) |

No other file may change.

## 4. Steps

1. Save the Appendix patch to `/tmp/1171b-fix-1.patch` (or use `/tmp/claude-0/1171b-fix-1.patch` if it exists). From the repo root: `git apply --check /tmp/1171b-fix-1.patch 2>&1 | tail -30`, then `git apply /tmp/1171b-fix-1.patch 2>&1 | tail -30`. Any error: STOP (§8).
2. Regenerate the goldens from `App/`: `.venv/bin/python scripts/filing_watchdog_golden.py 2>&1 | tail -3` and `.venv/bin/python scripts/filing_watchdog_run_golden.py 2>&1 | tail -3` (each ends `wrote ...`). `git diff --stat go/internal/calendar/testdata 2>&1 | tail -5` shows 3 insertions, 3 deletions per file.
3. Check: `sha256sum App/app/filing_watchdog.py App/scripts/filing_watchdog_golden.py App/tests/test_filing_watchdog.py go/internal/calendar/filing_watchdog.go go/internal/calendar/filing_watchdog_run_test.go go/internal/calendar/testdata/filing_watchdog_golden.json go/internal/calendar/testdata/filing_watchdog_run_golden.json 2>&1 | tail -30` matches:

```
479ad67c6294f2524a47177ccafe1dd2c7c0f3a68998016e60868503460f2717  App/app/filing_watchdog.py
fc3d1f59169deb3fc9b33dc72d61ff35901387ce1b5b7f3db96aaf766b5937a4  App/scripts/filing_watchdog_golden.py
012c863b24b9d3a8ee1fbcc09508483184ebe514d7866d715f1943e9d7d592b1  App/tests/test_filing_watchdog.py
7ef036937cb8b576e99529341227990a7a9487da95dcdfdfdb483549b8a1df00  go/internal/calendar/filing_watchdog.go
af1687e01af5e9c807830f739e3cd66f75bbe4001dc7614cfd3f0cdc48698585  go/internal/calendar/filing_watchdog_run_test.go
1c6a631079499d001c204ef2d4c3fe192acc7c8335da00d603d1e1f32aa14c58  go/internal/calendar/testdata/filing_watchdog_golden.json
012d42535a052ce28e5fa7718ca40be88c5763f7449db16292f6017c92186ac1  go/internal/calendar/testdata/filing_watchdog_run_golden.json
```

4. Run §6. Commit `1171b-fix-1 step 1`.

## 5. Do not touch

Everything outside §3, in particular `App/app/reporting.py`, `go/internal/ubyport/`, `App/app/scheduler.py` and the digest builders. Hard rules 1, 5 and 8 (no push, no merge).

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30` → `58 passed`.
- The test-map row "Filing, UbyPort, claim" without the watchdog file: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_police_*.py tests/test_*deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30` → `685 passed, 1 skipped` (the whole row including the watchdog file was run this way at brief time).

Go (needs Postgres 16; start it as the postgres user, stop it after):
- `su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1171x -o '-p 55432 -k /tmp' -l /tmp/pg1171x.log start -w" 2>&1 | tail -3`
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/calendar/... 2>&1 | tail -30` → `ok`.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres go test ./internal/calendar/ -count=1 -run TestRunFilingWatchdogPagesOnlyForFailedSends -v 2>&1 | grep -E 'SKIP|PASS|FAIL' | tail -10` → 6 subtests PASS, no SKIP.
- `cd go && go vet ./internal/calendar/... 2>&1 | tail -5` and `gofmt -l internal/ 2>&1 | tail -5` → no output.
- `su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1171x stop" 2>&1 | tail -1`

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] §4 step 3 hashes match.
- [ ] `grep -c "sweep_failed:\|apartment_setup:\|submission_outcome_unknown:" App/app/filing_watchdog.py go/internal/calendar/filing_watchdog.go` gives at least 3 per file.
- [ ] All §6 commands give the expected output; the Go subtests `sweep_crashed`, `login_invalid`, `outcome_unknown` pass, not skipped.
- [ ] `git diff --stat HEAD~1` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- the patch does not apply or a hash differs;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1171b-fix-1-report.md` (600 tokens at most) and set `Status: review`. The report has: the files changed (`git diff --stat`); each command with the last 5 lines of its output; §7 ticked; deviations; questions; owner steps left.

## Risk list (for the reviewer)

- App/app/filing_watchdog.py and go/internal/calendar/filing_watchdog.go: the two key lists must match line for line.
- `apartment_setup` is raised for any validation error on the property settings, not only the password. A configured login with, say, an invalid IDUB or address now pages; that is a property that cannot send, so it fits the rule, but expect the alarm for setup mistakes too.
- `sweep_failed` is raised for any exception in one property's sweep, including a bug unrelated to filing that still stops that property's sends; that is the point.
- `submission_outcome_unknown` stays open until a later send succeeds or the host files by hand; a stay already counted via `submission_id` is not double-counted (it is one boolean).
- A host can dismiss any of these alerts, which pauses paging until the next sweep raises it again.

## Owner steps

None beyond the usual review of draft PR #959.

## Appendix: the patch

```diff
diff --git a/App/app/filing_watchdog.py b/App/app/filing_watchdog.py
index 0415335..493064f 100644
--- a/App/app/filing_watchdog.py
+++ b/App/app/filing_watchdog.py
@@ -80,13 +80,21 @@ UNKNOWN_RISK_MAX_OVERDUE = timedelta(days=7)
 RETRY_GRACE = timedelta(minutes=2 * max(1, config.SUBMIT_SWEEP_MINUTES))
 # 1171b: an open alert that means UbyHost could not send for this stay
 # (``r`` reservation): the police login refused, a batch that never reached
-# UbyPort, or a guest record that cannot be decrypted. The dedupe keys are
+# UbyPort, a guest record that cannot be decrypted, the property's sweep
+# crashed (the job heartbeat stays green, so the dead-man switch misses it),
+# the saved login fails validation (a rotated SECRET_KEY decrypts it to ""),
+# or a crash-interrupted batch whose outcome is unknown. The dedupe keys are
 # the ones reporting.py raises; the Go copy is watchdogSendFailedAlertSQL.
+# Hosts can dismiss these alerts, which pauses paging until the next sweep
+# raises them again.
 SEND_FAILED_ALERT_SQL = (
     "EXISTS (SELECT 1 FROM alert al WHERE al.resolved_at IS NULL AND al.dedupe_key IN ("
     "'ubyport_auth_failed:' || CAST(r.apartment_id AS TEXT), "
     "'submission_transport:' || CAST(r.apartment_id AS TEXT), "
     "'guest_record_unreadable:' || CAST(r.apartment_id AS TEXT), "
+    "'sweep_failed:' || CAST(r.apartment_id AS TEXT), "
+    "'apartment_setup:' || CAST(r.apartment_id AS TEXT), "
+    "'submission_outcome_unknown:' || CAST(r.apartment_id AS TEXT), "
     "'guest_record_unreadable:reservation:' || CAST(r.id AS TEXT)))"
 )
 
diff --git a/App/scripts/filing_watchdog_golden.py b/App/scripts/filing_watchdog_golden.py
index 2295006..710884d 100644
--- a/App/scripts/filing_watchdog_golden.py
+++ b/App/scripts/filing_watchdog_golden.py
@@ -229,7 +229,8 @@ SEED = [
              "guest_record_unreadable:reservation:247", "x", STAMP, None],
             [9105, "critical", "ubyport_auth_failed", 1, None, "ubyport_auth_failed:1",
              "x", STAMP, "2026-09-16T00:00:00+00:00"],
-            [9106, "warning", "sweep_failed", 1, None, "sweep_failed:1", "x", STAMP, None],
+            [9106, "warning", "door_code_failed", 1, 201, "door_code_failed:201", "x", STAMP,
+             None],
         ],
     },
     {
diff --git a/App/tests/test_filing_watchdog.py b/App/tests/test_filing_watchdog.py
index 21d5176..2c4ba80 100644
--- a/App/tests/test_filing_watchdog.py
+++ b/App/tests/test_filing_watchdog.py
@@ -789,7 +789,7 @@ def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeyp
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
     # A resolved login alert and an unrelated open one do not count.
     _open_alert(world, f"ubyport_auth_failed:{world['apartment_id']}", resolved=True)
-    _open_alert(world, f"sweep_failed:{world['apartment_id']}")
+    _open_alert(world, f"door_code_failed:{rid}", reservation_id=rid)
     _only(monkeypatch, {rid})
     stay = _mine(filing_watchdog.at_risk_stays(), {rid})[rid]
     assert stay["send_failed"] is False
@@ -804,7 +804,11 @@ def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeyp
 
 
 @pytest.mark.parametrize(
-    "failure", ["refused", "auth", "transport", "unreadable_property", "unreadable_stay"]
+    "failure",
+    [
+        "refused", "auth", "transport", "unreadable_property", "unreadable_stay",
+        "sweep_failed", "apartment_setup", "outcome_unknown",
+    ],
 )
 def test_a_failed_send_on_a_configured_property_pages_and_is_in_the_digest(
     world, pings, monkeypatch, failure
@@ -820,6 +824,9 @@ def test_a_failed_send_on_a_configured_property_pages_and_is_in_the_digest(
             "transport": f"submission_transport:{apartment_id}",
             "unreadable_property": f"guest_record_unreadable:{apartment_id}",
             "unreadable_stay": f"guest_record_unreadable:reservation:{rid}",
+            "sweep_failed": f"sweep_failed:{apartment_id}",
+            "apartment_setup": f"apartment_setup:{apartment_id}",
+            "outcome_unknown": f"submission_outcome_unknown:{apartment_id}",
         }[failure]
         _open_alert(world, key, reservation_id=rid if failure == "unreadable_stay" else None)
     _only(monkeypatch, {rid})
diff --git a/go/internal/calendar/filing_watchdog.go b/go/internal/calendar/filing_watchdog.go
index e96fd20..10d39bf 100644
--- a/go/internal/calendar/filing_watchdog.go
+++ b/go/internal/calendar/filing_watchdog.go
@@ -33,12 +33,18 @@ const (
 )
 
 // watchdogSendFailedAlertSQL is SEND_FAILED_ALERT_SQL (1171b): an open alert
-// that means UbyHost could not send for the stay r. The dedupe keys are the
-// ones App/app/reporting.py and go/internal/ubyport raise.
+// that means UbyHost could not send for the stay r, including a crashed
+// property sweep, a login that fails validation and a crash-interrupted batch
+// with an unknown outcome. The dedupe keys are the ones App/app/reporting.py
+// and go/internal/ubyport raise. A host can dismiss these alerts, which pauses
+// paging until the next sweep raises them again.
 const watchdogSendFailedAlertSQL = `EXISTS (SELECT 1 FROM alert al WHERE al.resolved_at IS NULL AND al.dedupe_key IN (
 	'ubyport_auth_failed:' || CAST(r.apartment_id AS TEXT),
 	'submission_transport:' || CAST(r.apartment_id AS TEXT),
 	'guest_record_unreadable:' || CAST(r.apartment_id AS TEXT),
+	'sweep_failed:' || CAST(r.apartment_id AS TEXT),
+	'apartment_setup:' || CAST(r.apartment_id AS TEXT),
+	'submission_outcome_unknown:' || CAST(r.apartment_id AS TEXT),
 	'guest_record_unreadable:reservation:' || CAST(r.id AS TEXT)))`
 
 // watchdogAtRiskSQL is the unfiled guests with a nationality on watched stays.
diff --git a/go/internal/calendar/filing_watchdog_run_test.go b/go/internal/calendar/filing_watchdog_run_test.go
index 5b45a94..a05b6ea 100644
--- a/go/internal/calendar/filing_watchdog_run_test.go
+++ b/go/internal/calendar/filing_watchdog_run_test.go
@@ -378,7 +378,9 @@ func TestRunFilingWatchdogRefusesBadSweepMinutes(t *testing.T) {
 // with all other stays archived: a stay UbyHost never sent (201) gets the host
 // mail but no digest and the heartbeat stays green; a refused batch (229) or
 // an open ubyport_auth_failed alert on a fully configured property (244)
-// fails the heartbeat and goes in the digest.
+// fails the heartbeat and goes in the digest, and so does stay 201 once its
+// property has an open sweep_failed, apartment_setup or
+// submission_outcome_unknown alert (1171b fix 1).
 func TestRunFilingWatchdogPagesOnlyForFailedSends(t *testing.T) {
 	g := loadWatchdogRunGolden(t)
 	at, err := time.Parse(time.RFC3339, "2026-09-17T11:00:00+00:00")
@@ -388,13 +390,17 @@ func TestRunFilingWatchdogPagesOnlyForFailedSends(t *testing.T) {
 	cases := []struct {
 		name            string
 		stay            int64
+		alert           string
 		atRisk, notSent int
 		digest          int
 		ping            string
 	}{
-		{"never sent", 201, 0, 1, 0, "https://hc.example.test/ping/abc"},
-		{"refused batch", 229, 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
-		{"login refused", 244, 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"never sent", 201, "", 0, 1, 0, "https://hc.example.test/ping/abc"},
+		{"refused batch", 229, "", 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"login refused", 244, "", 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"sweep crashed", 201, "sweep_failed:1", 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"login invalid", 201, "apartment_setup:1", 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
+		{"outcome unknown", 201, "submission_outcome_unknown:1", 1, 0, 1, "https://hc.example.test/ping/abc/fail"},
 	}
 	for _, c := range cases {
 		t.Run(c.name, func(t *testing.T) {
@@ -408,6 +414,14 @@ func TestRunFilingWatchdogPagesOnlyForFailedSends(t *testing.T) {
 				`UPDATE reservation SET archived_at = '2026-09-16' WHERE id != $1`, c.stay); err != nil {
 				t.Fatal(err)
 			}
+			if c.alert != "" {
+				if _, err := pool.Exec(context.Background(),
+					`INSERT INTO alert (id, level, kind, apartment_id, dedupe_key, message, created_at)
+					VALUES (9201, 'critical', split_part($1, ':', 1), 1, $1, 'x', '2026-09-16T00:00:00+00:00')`,
+					c.alert); err != nil {
+					t.Fatal(err)
+				}
+			}
 			res, err := RunFilingWatchdog(context.Background(), pool, watchdogLookup(env), at)
 			if err != nil {
 				t.Fatal(err)
diff --git a/go/internal/calendar/testdata/filing_watchdog_golden.json b/go/internal/calendar/testdata/filing_watchdog_golden.json
index 41e03d1..ef5c2dd 100644
--- a/go/internal/calendar/testdata/filing_watchdog_golden.json
+++ b/go/internal/calendar/testdata/filing_watchdog_golden.json
@@ -5777,10 +5777,10 @@
     [
      9106,
      "warning",
-     "sweep_failed",
+     "door_code_failed",
      1,
-     null,
-     "sweep_failed:1",
+     201,
+     "door_code_failed:201",
      "x",
      "2026-09-01T00:00:00+00:00",
      null
diff --git a/go/internal/calendar/testdata/filing_watchdog_run_golden.json b/go/internal/calendar/testdata/filing_watchdog_run_golden.json
index d6ea015..1b10b76 100644
--- a/go/internal/calendar/testdata/filing_watchdog_run_golden.json
+++ b/go/internal/calendar/testdata/filing_watchdog_run_golden.json
@@ -3621,10 +3621,10 @@
     [
      9106,
      "warning",
-     "sweep_failed",
+     "door_code_failed",
      1,
-     null,
-     "sweep_failed:1",
+     201,
+     "door_code_failed:201",
      "x",
      "2026-09-01T00:00:00+00:00",
      null
```
