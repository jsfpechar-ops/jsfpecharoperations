# 1200: Remove the Python deadlines job body

Status: todo
Depends on: none | Base commit: b4ef75e | Branch: claude/1200-remove-python-deadlines-job
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The `deadlines` job (deadline watch, DSR due alerts, filing watchdog, filing heartbeat) runs in Go since 2026-11-12 (`go/internal/calendar/deadlines_job.go`, clean run verified 2026-11-13), so the Python body `scheduler._job_deadlines` is removed, as plan 1132 §10 E says. Python keeps a stub under the same kind that only raises the critical `job_failed:deadlines` alert, so a wrong env never silently drops the deadline watch.

## 2. Context

Tier A (filing path). Hard rule 1: filing correctness beats every other feature.

- The Python worker is still the only enqueuer: `start()` schedules `_target("deadlines")`, which enqueues a job row when `deadlines` is in `UBYHOST_JOB_QUEUE_KINDS`. That stays.
- `start()` raises `RuntimeError` for any `UBYHOST_JOB_QUEUE_KINDS` entry not in `JOB_KINDS`, and production lists `deadlines`, so `JOB_KINDS` keeps a `"deadlines"` key (now the stub).
- `jobqueue.claim` skips kinds in `UBYHOST_GO_JOB_KINDS`, so in production Python never runs the stub. It runs only if someone removes `deadlines` from `UBYHOST_GO_JOB_KINDS`, or on SQLite/non-queued setups with the scheduler on. Then it logs an error naming both env vars, calls `_job_failed("deadlines")` (critical alert) and `_log_run("deadlines", started, False)`, and sends no heartbeat (the external monitor alerts on the missing ping). It never raises.
- Kept untouched: `reporting.check_deadlines`, `dsr.raise_due_alerts`, `filing_watchdog.run`/`heartbeat_url` (golden scripts `App/scripts/*_golden.py`, web pages and tests use them), `job_intervals()["deadlines"]`, `_JOB_LEVELS["deadlines"]`, the APScheduler entry.
- The composite order (watch, then watchdog even if the watch failed, then ping) is covered by `go/internal/calendar/deadlines_job_test.go`.
- The lint warns that brief 1167 also names the two Go files: 1167 is merged (its `Status: todo` line is stale); 1200 goes after it. Ignore that warning.
- CI runs `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`, so the `dsr` and `filing_watchdog` imports in `App/app/scheduler.py` go (no other use there; no test uses `scheduler.dsr` or `scheduler.filing_watchdog` after step 2).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/scheduler.py` | edit | Remove `_job_deadlines` and `_filing_heartbeat`; add the `_job_deadlines_go_only` stub; point `JOB_KINDS["deadlines"]` at it; drop the now unused `dsr` and `filing_watchdog` imports (CI ruff F401); one warning in `start()`. |
| `App/tests/test_filing_watchdog.py` | edit | Heartbeat tests call `filing_watchdog.heartbeat_url` instead of the removed job; drop the `pings` fixture, the two composite tests and the `scheduler` import. |
| `App/tests/test_scheduler.py` | edit | Drop the `deadlines` row from `_JOBS`; second-failure test uses the stub; add the stub test. |
| `App/tests/test_p1_review.py` | edit | Test A drives the stub instead of the removed job. |
| `go/internal/calendar/deadlines_job.go` | edit | Comments only (lines 1 and 34). |
| `go/internal/calendar/deadlines_job_test.go` | edit | Comment only (line 49). |
| `docs/ENVIRONMENT.md` | edit | Line 53: new rollback sentence for `deadlines`. |
| `docs/tasks/1200-report.md` | create | The report. |

No other file may change. Not `docs/context/status.md` (another PR edits it), not `docs/context/test-map.md`.

## 4. Steps

Each step applies one patch block from this brief with `git apply`. The patches were dry-run on the base commit. Run every command from the repo root. If `git apply --check` fails: STOP (§8), do not hand-edit.

Extract-and-apply command for block K (replace K with the step number):

```bash
awk -v k="K" '$0=="<!-- patch:" k " -->"{f=1;next} f&&/^```diff$/{g=1;next} g&&/^```$/{exit} g' docs/tasks/1200-remove-python-deadlines-job.md > /tmp/p1200.diff && git apply --check /tmp/p1200.diff && git apply /tmp/p1200.diff && git diff --stat 2>&1 | tail -5
```

After each step: `git commit -am "1200 step K"`.

### Step 1: scheduler.py

<!-- patch:1 -->
```diff
diff --git a/App/app/scheduler.py b/App/app/scheduler.py
index 8bf175d..3f3a45b 100644
--- a/App/app/scheduler.py
+++ b/App/app/scheduler.py
@@ -19,9 +19,7 @@ from . import (
     config,
     db,
     door_codes,
-    dsr,
     fee_update,
-    filing_watchdog,
     guest_draft,
     guest_guide_import,
     guest_guide_merge,
@@ -220,61 +218,21 @@ def _ping(url: str, job_id: str) -> None:
         log.warning("heartbeat ping for %s failed", job_id, exc_info=True)
 
 
-def _job_deadlines() -> None:
+def _job_deadlines_go_only() -> None:
+    """The deadlines job runs in Go only (1200); reaching Python is a misconfiguration.
+
+    The deadline watch, the filing watchdog and the filing heartbeat are
+    go/internal/calendar/deadlines_job.go. This stub raises the critical
+    job_failed alert and sends no heartbeat, so the external monitor alerts on
+    the missing ping as well.
+    """
     started = time.perf_counter()
-    watch_ok = True
-    raised = due_requests = 0
-    try:
-        raised = reporting.check_deadlines()
-        due_requests = dsr.raise_due_alerts()
-        if raised or due_requests:
-            log.info(
-                "deadline watch raised %s alert(s), %s data-subject request(s) due",
-                raised,
-                due_requests,
-            )
-    except Exception:
-        log.exception("deadline watch failed")
-        _job_failed("deadlines")
-        watch_ok = False
-    # WP23: the filing watchdog runs even when the alert pass above failed,
-    # because its mails and its heartbeat are what reach the owner when the
-    # app itself is not being looked at.
-    try:
-        watchdog = filing_watchdog.run()
-        if (
-            watchdog["at_risk"] or watchdog.get("not_sent") or watchdog.get("unknown_risk") or watchdog.get("awaiting_retry")
-            or watchdog["host_mails"] or watchdog["digest"]
-        ):
-            log.info("filing watchdog: %s", watchdog)
-    except Exception:
-        # No ping at all: the external monitor alerts on the missing ping.
-        log.exception("filing watchdog failed")
-        _job_failed("deadlines")
-        _log_run("deadlines", started, False)
-        return
-    if watch_ok:
-        _job_ok("deadlines")
-    _log_run(
-        "deadlines", started, watch_ok,
-        {
-            "alerts": raised or 0,
-            "requests_due": due_requests or 0,
-            "at_risk": watchdog["at_risk"],
-            "not_sent": watchdog.get("not_sent", 0),
-            "unknown_risk": watchdog.get("unknown_risk", 0),
-            "awaiting_retry": watchdog.get("awaiting_retry", 0),
-            "host_mails": watchdog["host_mails"],
-            "digest": watchdog["digest"],
-        },
+    log.error(
+        "the deadlines job runs in Go only: put deadlines in both "
+        "UBYHOST_JOB_QUEUE_KINDS and UBYHOST_GO_JOB_KINDS (PostgreSQL)"
     )
-    # A failed deadline watch counts as a failure too: nobody is being told.
-    _filing_heartbeat(watchdog["at_risk"] > 0 or not watch_ok)
-
-
-def _filing_heartbeat(at_risk: bool) -> None:
-    """Ping the filing dead-man switch: <url> when all is well, <url>/fail if not."""
-    _ping(filing_watchdog.heartbeat_url(at_risk), "filing")
+    _job_failed("deadlines")
+    _log_run("deadlines", started, False)
 
 
 def _job_mail() -> None:
@@ -553,7 +511,7 @@ def _acquire_single_instance_lock() -> bool:
 JOB_KINDS = {
     "ical": _job_sync_calendars,
     "submit": _job_submit,
-    "deadlines": _job_deadlines,
+    "deadlines": _job_deadlines_go_only,
     "mail": _job_mail,
     "photo_sweep": _job_photo_sweep,
     "meta_capi": _job_meta_capi,
@@ -619,6 +577,8 @@ def start() -> bool:
         )
     if config.JOB_QUEUE_KINDS and config.DB_BACKEND != "postgresql":
         raise RuntimeError("UBYHOST_JOB_QUEUE_KINDS needs PostgreSQL")
+    if config.DB_BACKEND == "postgresql" and "deadlines" not in config.GO_JOB_KINDS:
+        log.warning("deadlines is not in UBYHOST_GO_JOB_KINDS: no deadline watch runs (1200)")
     if config.DB_BACKEND == "postgresql" and set(JOB_KINDS) <= config.JOB_QUEUE_KINDS:
         log.info("every job is on the queue; scheduler.lock not taken")
     elif not _acquire_single_instance_lock():
```

### Step 2: test_filing_watchdog.py

<!-- patch:2 -->
```diff
diff --git a/App/tests/test_filing_watchdog.py b/App/tests/test_filing_watchdog.py
index 2c4ba80..ea8d358 100644
--- a/App/tests/test_filing_watchdog.py
+++ b/App/tests/test_filing_watchdog.py
@@ -15,7 +15,7 @@ from datetime import date, datetime, timedelta, timezone
 import pytest
 from markupsafe import escape
 
-from app import auth, config, db, filing_watchdog, host_i18n, mail, mail_notify, scheduler
+from app import auth, config, db, filing_watchdog, host_i18n, mail, mail_notify
 from tests.test_submission_retry_cap import host as host  # noqa: F401
 
 USERNAME = "filing-watchdog-host"
@@ -295,78 +295,35 @@ def test_the_digest_stamp_is_utc(world, monkeypatch):
 # --- heartbeat ------------------------------------------------------------------
 
 
-@pytest.fixture
-def pings(monkeypatch):
-    calls = []
-    monkeypatch.setattr(scheduler.requests, "get", lambda url, timeout: calls.append(url))
-    monkeypatch.setattr(scheduler.reporting, "check_deadlines", lambda: 0)
-    monkeypatch.setattr(scheduler.dsr, "raise_due_alerts", lambda: 0)
-    return calls
-
-
-def _watchdog_returns(monkeypatch, at_risk):
-    monkeypatch.setattr(
-        filing_watchdog, "run",
-        lambda now=None: {"at_risk": at_risk, "host_mails": 0, "digest": 0},
-    )
-
-
-def test_the_heartbeat_reports_success_when_nothing_is_at_risk(pings, monkeypatch):
-    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc/")
-    _watchdog_returns(monkeypatch, 0)
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc"]
-
-
-def test_the_heartbeat_reports_fail_when_a_stay_is_at_risk(pings, monkeypatch):
-    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
-    _watchdog_returns(monkeypatch, 2)
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
+# The job that pings the URL is go/internal/calendar/deadlines_job.go (1200);
+# these tests pin the URL the watchdog's answer maps to.
 
+URL = "https://hc-ping.example.invalid/abc"
 
-def test_the_heartbeat_reports_fail_when_the_deadline_watch_breaks(pings, monkeypatch):
-    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
-    _watchdog_returns(monkeypatch, 0)
 
-    def boom():
-        raise RuntimeError("deadline watch broke")
+def test_the_heartbeat_reports_success_when_nothing_is_at_risk(monkeypatch):
+    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", URL + "/")
+    assert filing_watchdog.heartbeat_url(False) == URL
 
-    monkeypatch.setattr(scheduler.reporting, "check_deadlines", boom)
-    monkeypatch.setattr(scheduler, "_job_failed", lambda job_id: None)
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
 
+def test_the_heartbeat_reports_fail_when_a_stay_is_at_risk(monkeypatch):
+    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", URL)
+    assert filing_watchdog.heartbeat_url(True) == URL + "/fail"
 
-def test_no_ping_when_the_watchdog_itself_fails(pings, monkeypatch):
-    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
-
-    def boom(now=None):
-        raise RuntimeError("watchdog broke")
 
-    monkeypatch.setattr(filing_watchdog, "run", boom)
-    failed = []
-    monkeypatch.setattr(scheduler, "_job_failed", failed.append)
-    scheduler._job_deadlines()
-    assert pings == []
-    assert failed == ["deadlines"]
-
-
-def test_nothing_is_sent_when_the_url_is_empty(pings, monkeypatch):
+def test_nothing_is_sent_when_the_url_is_empty(monkeypatch):
     monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "")
-    for at_risk in (0, 3):
-        _watchdog_returns(monkeypatch, at_risk)
-        scheduler._job_deadlines()
-    assert pings == []
+    assert filing_watchdog.heartbeat_url(False) == ""
+    assert filing_watchdog.heartbeat_url(True) == ""
 
 
-def test_the_real_watchdog_runs_inside_the_deadline_job(world, pings, monkeypatch):
-    """No stub for run(): the job computes the answer and pings with it."""
-    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
+def test_the_real_watchdog_answer_fails_the_heartbeat(world, monkeypatch):
+    """No stub for run(): its answer maps to the /fail URL."""
+    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", URL)
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
     _refused_batch(world, rid)
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
+    result = filing_watchdog.run()
+    assert filing_watchdog.heartbeat_url(result["at_risk"] > 0) == URL + "/fail"
     assert rid in _mine(filing_watchdog.at_risk_stays(), {rid})
 
 
@@ -509,7 +466,7 @@ def test_a_digest_goes_out_for_stays_without_guests_alone(world, monkeypatch):
     ) not in text
 
 
-def test_stays_without_guests_never_fail_the_heartbeat(world, pings, monkeypatch):
+def test_stays_without_guests_never_fail_the_heartbeat(world, monkeypatch):
     """Czech guests owe no report, so an empty stay is no reason to page anyone."""
     monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
     # Only this test's stays: the shared database may hold other tests' stays.
@@ -526,8 +483,7 @@ def test_stays_without_guests_never_fail_the_heartbeat(world, pings, monkeypatch
     result = filing_watchdog.run()
     assert result["at_risk"] == 0 and result["unknown_risk"] >= 1
     assert rid in _mine(filing_watchdog.unknown_risk_stays(), {rid})
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc"]
+    assert filing_watchdog.heartbeat_url(result["at_risk"] > 0) == URL
 
 
 def test_a_broken_unknown_risk_query_does_not_silence_the_watchdog(world, monkeypatch):
@@ -784,7 +740,7 @@ def _mail_on(monkeypatch):
     monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
 
 
-def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeypatch):
+def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, monkeypatch):
     _mail_on(monkeypatch)
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
     # A resolved login alert and an unrelated open one do not count.
@@ -799,8 +755,7 @@ def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeyp
     )
     assert len(_outbox("deadline_at_risk", rid)) == 1
     assert _outbox("deadline_digest") == []
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc"]
+    assert filing_watchdog.heartbeat_url(result["at_risk"] > 0) == URL
 
 
 @pytest.mark.parametrize(
@@ -811,7 +766,7 @@ def test_a_stay_never_sent_mails_the_host_but_pages_nobody(world, pings, monkeyp
     ],
 )
 def test_a_failed_send_on_a_configured_property_pages_and_is_in_the_digest(
-    world, pings, monkeypatch, failure
+    world, monkeypatch, failure
 ):
     _mail_on(monkeypatch)
     rid = world["add_stay"]([("DEU", "pending")], arrival=date.today() - timedelta(days=10))
@@ -837,8 +792,7 @@ def test_a_failed_send_on_a_configured_property_pages_and_is_in_the_digest(
     )
     text = json.loads(_outbox("deadline_digest")[0]["payload"])["text"]
     assert "Watchdog Loft" in text and GUEST_SURNAME not in text
-    scheduler._job_deadlines()
-    assert pings == ["https://hc-ping.example.invalid/abc/fail"]
+    assert filing_watchdog.heartbeat_url(result["at_risk"] > 0) == URL + "/fail"
 
 
 def test_a_stay_without_guests_is_not_in_the_digest(world, monkeypatch):
```

### Step 3: test_scheduler.py

<!-- patch:3 -->
```diff
diff --git a/App/tests/test_scheduler.py b/App/tests/test_scheduler.py
index c569d85..d253a59 100644
--- a/App/tests/test_scheduler.py
+++ b/App/tests/test_scheduler.py
@@ -88,12 +88,6 @@ _JOBS = [
         "target": (reporting, "sweep"),
         "level": "critical",
     },
-    {
-        "id": "deadlines",
-        "run": scheduler._job_deadlines,
-        "target": (reporting, "check_deadlines"),
-        "level": "critical",
-    },
     {
         "id": "mail",
         "run": scheduler._job_mail,
@@ -154,12 +148,8 @@ def test_a_failing_job_alerts_the_host_and_the_next_success_resolves_it(
 def test_a_second_failure_refreshes_one_card(monkeypatch, tmp_path):
     _private_db(monkeypatch, tmp_path)
 
-    def boom(*_args, **_kwargs):
-        raise RuntimeError("job blew up")
-
-    monkeypatch.setattr(reporting, "check_deadlines", boom)
-    scheduler._job_deadlines()
-    scheduler._job_deadlines()
+    scheduler._job_deadlines_go_only()
+    scheduler._job_deadlines_go_only()
 
     rows = db.query(
         "SELECT id FROM alert WHERE dedupe_key = ?", ("job_failed:deadlines",)
@@ -167,6 +157,25 @@ def test_a_second_failure_refreshes_one_card(monkeypatch, tmp_path):
     assert len(rows) == 1
 
 
+def test_the_python_deadlines_stub_only_raises_the_alert(monkeypatch, tmp_path):
+    """1200: deadlines runs in Go; Python reaching it alerts and pings nothing."""
+    _private_db(monkeypatch, tmp_path)
+    monkeypatch.setattr(config, "HEARTBEAT_FILING_URL", "https://hc-ping.example.invalid/abc")
+    calls = []
+    monkeypatch.setattr(scheduler.requests, "get", lambda *args, **kwargs: calls.append(args))
+    monkeypatch.setattr(reporting, "check_deadlines", lambda: calls.append("check_deadlines"))
+
+    scheduler.JOB_KINDS["deadlines"]()
+
+    alert = db.query_one(
+        "SELECT * FROM alert WHERE dedupe_key = ?", ("job_failed:deadlines",)
+    )
+    assert alert is not None
+    assert alert["level"] == "critical"
+    assert alert["resolved_at"] is None
+    assert calls == []
+
+
 def test_a_successful_submission_sweep_pings_the_heartbeat(monkeypatch, tmp_path):
     _private_db(monkeypatch, tmp_path)
     monkeypatch.setattr(config, "HEARTBEAT_URL", "https://heartbeat.example/ping")
```

### Step 4: test_p1_review.py

<!-- patch:4 -->
```diff
diff --git a/App/tests/test_p1_review.py b/App/tests/test_p1_review.py
index 8576787..b24ac72 100644
--- a/App/tests/test_p1_review.py
+++ b/App/tests/test_p1_review.py
@@ -49,8 +49,7 @@ def test_A_job_failed_alert_is_visible_to_owner(monkeypatch, tmp_path):
     from app.main import app
     _db(monkeypatch, tmp_path, "a.db")
     uid = auth.create_account("hostadmin@example.test", "H", role="admin", username="hostadmin")
-    monkeypatch.setattr(reporting, "check_deadlines", lambda *a, **k: 1 / 0)
-    scheduler._job_deadlines()
+    scheduler._job_deadlines_go_only()  # 1200: the Python deadlines job only alerts
     assert len(alerts.open_alerts()) == 1                 # exists
     assert len(alerts.open_alerts(uid)) == 1              # and the host sees it
     c = TestClient(app)
```

### Step 5: deadlines_job.go (comments)

<!-- patch:5 -->
```diff
diff --git a/go/internal/calendar/deadlines_job.go b/go/internal/calendar/deadlines_job.go
index 904feef..65d421a 100644
--- a/go/internal/calendar/deadlines_job.go
+++ b/go/internal/calendar/deadlines_job.go
@@ -1,4 +1,4 @@
-// The deadlines job: App/app/scheduler.py _job_deadlines in Go. It runs the
+// The deadlines job: the former Python _job_deadlines (removed in 1200). It runs the
 // deadline watch (check_deadlines, then raise_due_alerts), then the filing
 // watchdog even when the watch failed, then pings the filing heartbeat.
 package calendar
@@ -31,7 +31,7 @@ type deadlinesSteps struct {
 	getenv      func(string) string
 }
 
-// RunDeadlinesJob is _job_deadlines for the Go job queue. at is the instant of
+// RunDeadlinesJob is the deadlines job (the former Python _job_deadlines, removed in 1200). at is the instant of
 // the run; ping GETs the filing heartbeat URL (jobs.Ping in production). A
 // failed watch or watchdog raises the critical job_failed alert at once, as
 // Python's _job_failed does, and returns an error so the queue does not record
```

### Step 6: deadlines_job_test.go (comment)

<!-- patch:6 -->
```diff
diff --git a/go/internal/calendar/deadlines_job_test.go b/go/internal/calendar/deadlines_job_test.go
index c40adba..e150aa4 100644
--- a/go/internal/calendar/deadlines_job_test.go
+++ b/go/internal/calendar/deadlines_job_test.go
@@ -46,7 +46,7 @@ func (f *deadlinesFake) steps() deadlinesSteps {
 	}
 }
 
-// TestRunDeadlinesOrderMatchesPython walks every branch of _job_deadlines.
+// TestRunDeadlinesOrderMatchesPython walks every branch of the former Python _job_deadlines (removed in 1200).
 func TestRunDeadlinesOrderMatchesPython(t *testing.T) {
 	boom := errors.New("boom")
 	cases := []struct {
```

### Step 7: ENVIRONMENT.md

<!-- patch:7 -->
```diff
diff --git a/docs/ENVIRONMENT.md b/docs/ENVIRONMENT.md
index a911fe8..1622470 100644
--- a/docs/ENVIRONMENT.md
+++ b/docs/ENVIRONMENT.md
@@ -50,7 +50,7 @@ Optional host subdomain: [deployment, exact values and rollback](APP_SUBDOMAIN.m
 | Variable | Default | Notes |
 | --- | --- | --- |
 | `UBYHOST_JOB_QUEUE_KINDS` | empty | PostgreSQL only. Comma list of scheduler job ids that go through the job table instead of running directly; unknown ids stop the worker. An open row unclaimed past twice its interval (Python or Go consumer missing) raises the `job_failed` alert for that job. |
-| `UBYHOST_GO_JOB_KINDS` | empty | PostgreSQL only. Kinds the Go service runs instead of Python; each must also be in `UBYHOST_JOB_QUEUE_KINDS`. Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi` and `deadlines` (the Go service reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`). `deadlines` is the deadline watch plus the filing watchdog and its heartbeat; to hand it back to Python, remove it from this list (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`. |
+| `UBYHOST_GO_JOB_KINDS` | empty | PostgreSQL only. Kinds the Go service runs instead of Python; each must also be in `UBYHOST_JOB_QUEUE_KINDS`. Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi` and `deadlines` (the Go service reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`). `deadlines` is the deadline watch plus the filing watchdog and its heartbeat; it must stay in both lists, because Python no longer has this job (1200): without Go it only raises the `job_failed` alert. Rollback: `git revert` the 1200 PR, merge and deploy, then remove `deadlines` from this list (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`. |
 | `UBYHOST_ENABLE_SCHEDULER` | `1` | `0` stops **all** background work: calendar polling, automatic submission, the deadline watch, the guest e-mail outbox, claim-hold expiry and the passport-photo sweep. |
 | `UBYHOST_ROLE` | `web` | What the process runs (WP06). `web`: HTTP only, never starts the scheduler (the Docker image, two uvicorn workers). `worker`: only the background jobs, started with `python -m app.worker` (the Lightsail `worker` container). `all`: both in one process (`run.sh` and `render_start.sh` default to it). Only one scheduler can run per data directory: it holds `DATA_DIR/scheduler.lock`. |
 | `UBYHOST_WEB_WORKERS` | `2` | uvicorn workers in the Docker image's web process (WP32). `4` on the 8 GB / 2 vCPU production server. `docker-entrypoint.sh` and `preflight.sh` refuse anything but 1 to 16. |
```

### Step 8: verify and test

Run §6 in order. Then check the hashes:

```bash
sha256sum App/app/scheduler.py App/tests/test_filing_watchdog.py App/tests/test_scheduler.py App/tests/test_p1_review.py go/internal/calendar/deadlines_job.go go/internal/calendar/deadlines_job_test.go docs/ENVIRONMENT.md 2>&1 | tail -10
```

Expected:

```
b1fac61ecb024ace8f397878d9d72ac7f418c266f207220766e81f4a005a76dc  App/app/scheduler.py
90e96bb504225466879d1d962a89b0175725d0c0809ddc53710988b55d93df89  App/tests/test_filing_watchdog.py
6ff9bb1d83a5f07ab588686669d6b86f399fda0af75791bd847d2e1d0c21bd58  App/tests/test_scheduler.py
bad5e18ee05d35310097e02a09b9ba13115189e231dba5a41ef8c8a5ca012c94  App/tests/test_p1_review.py
9dd22eaed7967b090197c5b71b570d7eb7b58e525527de2515941359e0a198dc  go/internal/calendar/deadlines_job.go
cfb3458c344d0435f7d588549a69a07c94f2dada60cae449445dcd1a79e5b123  go/internal/calendar/deadlines_job_test.go
cb3ec6398a565cb24b2d87429b46ace057f9d3924c4a68f30d236b0c397fd1e0  docs/ENVIRONMENT.md
```

A mismatch: STOP and report.

## 5. Do not touch

- Everything in `App/app/` except `App/app/scheduler.py`; in particular `reporting.py`, `dsr.py`, `filing_watchdog.py`, `jobqueue.py`, `config.py`.
- Go code (only the three comment lines in step 5 and 6). `docs/context/status.md`, `docs/context/test-map.md`, `docs/DISASTER_RECOVERY.md`, `.env`, deploy files.
- AGENTS.md hard rules 1 (filing first), 3 (public repo), 8 (never push to main; draft PR).

## 6. Commands

```bash
cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_*deadline*.py tests/test_claim_*.py tests/test_endtoend.py tests/test_scheduler.py tests/test_p1_review.py tests/test_job_queue.py -q --tb=short -x -rs 2>&1 | tail -30
```

Expected (dry run, SQLite): `773 passed, 18 skipped`; the skips are `test_police_letter_flow.py` (no playwright) and the PostgreSQL-only `test_job_queue.py` tests. With `UBYHOST_DATABASE_URL=postgresql://...@.../<name containing test>` the job-queue tests run too (dry run: all pass). A skip elsewhere in these files is a STOP.

```bash
cd App && .venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
cd go && go vet ./... 2>&1 | tail -5 && go test ./internal/calendar/ -count=1 2>&1 | tail -5
python3 scripts/context_lint.py 2>&1 | tail -5
grep -rn "_job_deadlines\b\|_filing_heartbeat" App/app App/tests App/scripts 2>&1 | tail -5
```

Expected: `All checks passed!`; `ok .../internal/calendar`; `context lint: OK`; the grep prints nothing (it must not match `_job_deadlines_go_only`).

## 7. Acceptance

- [ ] `git diff --stat main` lists exactly the §3 files.
- [ ] The step 8 hashes match.
- [ ] §6 tests pass, ruff clean, Go vet and calendar tests pass, lint OK, grep empty.
- [ ] `grep -n '"deadlines": _job_deadlines_go_only' App/app/scheduler.py` prints one line.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found or `git apply --check` fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1200-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/scheduler.py`: the stub must never ping the filing heartbeat or raise; `JOB_KINDS` keeps `deadlines`; the `start()` warning is a log line only, no `RuntimeError`.
- `App/tests/test_filing_watchdog.py`: coverage moved from the job to `heartbeat_url`; dropped only the two composite tests (watch breaks, watchdog breaks) that Go covers.
- `docs/ENVIRONMENT.md` line 53.

## Rollback after this PR

After this merges, Python can no longer run the deadline watch. If the Go deadlines job breaks, keeping or removing `deadlines` from `UBYHOST_GO_JOB_KINDS` alone does not help: Python would only raise the "deadline watch failed" alert. To get the Python job back: revert this PR (`git revert <merge sha>`, open a PR, merge, let it deploy), then remove `deadlines` from `UBYHOST_GO_JOB_KINDS` (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`.

## Owner steps

1. Before merging, check on the server that `deadlines` is in both lists (both lines must name it):

```bash
grep -n 'UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS' .env
```

2. Merge the PR when CI is green; it deploys on its own.
3. Within an hour, open the admin Operations page: the `deadlines` job shows a recent success and there is no "deadline watch failed" alert; the filing heartbeat monitor (healthchecks.io) shows a ping within the last 30 minutes.
