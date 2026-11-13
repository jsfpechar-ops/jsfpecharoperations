# 1171: Skip stays of properties without police (UbyPort) details

Status: todo
Depends on: none | Base commit: 142f89a | Branch: task/1171-skip-no-police-stays
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A property whose `apartment.uby_idub`, `uby_ws_user` or `uby_ws_password_enc` is NULL or blank after trim files no police report from UbyHost (owner decision 2026-11-13), so its stays get no in-app `deadline` alert (an open one is resolved by the run), are in neither `at_risk` nor `unknown_risk`, get no host mail, no digest line and never set the heartbeat to `/fail`. A property with all three fields behaves exactly as today; Python and Go (Go runs the deadlines job in prod) stay in parity. This is part 1; part 2 is brief 1171b and is out of scope.

## 2. Context

- Hard rule 1: UbyPort filing correctness beats every other feature. A fully configured property must still be watched: the golden JSON outputs for every existing case stay identical (only the seed and the new cases change).
- Hard rule 5: SQL only through `App/app/db.py` helpers, Postgres-portable. The fragment uses `COALESCE(TRIM(x), '') != ''` on TEXT columns (`App/app/db.py:149 uby_idub TEXT`), valid on SQLite and Postgres. Python selects it as `CASE ... THEN 1 ELSE 0 END` (int on both engines); Go selects `CASE ... END = 1` (boolean) and scans into `bool`.
- `headcount_mismatch`, `guest_incomplete_checkin` (raised in `App/app/claim.py`, not here) and `guest_record_unreadable` keep running for such properties: the new check sits after them in `check_deadlines` / `watchStay`, at the existing `if settled` branch.
- Golden seeds are recorded in the JSON and the Go tests seed from the JSON, so the Go test files need no change. The golden fixtures get the three fields on every existing apartment (any non-blank value: the queries only test non-blank) and new apartments missing one field each.
- Test fixtures `world` (test_filing_watchdog.py) and `_stay_with_guests` (test_deadlines.py) get the three fields (password via `db.encrypt_secret`); without them 24 existing tests fail.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | `FILES_WITH_UBYHOST_SQL`; `check_deadlines` selects `files_with_ubyhost`, resolves the deadline card when it is 0 |
| App/app/filing_watchdog.py | edit | fragment in `at_risk_stays` and `unknown_risk_stays`; docstring paragraph |
| go/internal/calendar/watch.go | edit | `filesWithUbyhostSQL`; selected and scanned in `watchStays`; `watchStay` resolves the card |
| go/internal/calendar/progress.go | edit | `stayRow.filesWithUbyhost` |
| go/internal/calendar/filing_watchdog.go | edit | fragment in `watchdogAtRiskSQL` and `watchdogUnknownSQL` |
| App/scripts/check_deadlines_golden.py | edit | `UBY_LOGIN`, login columns, apartments 4-6, stays 121-123, guests 12-13, alert 9017 |
| App/scripts/filing_watchdog_golden.py | edit | `UBY_LOGIN`, login columns, apartments 6-8, stays 241-243, guests 41-42 |
| go/internal/calendar/testdata/check_deadlines_golden.json | regenerate | from the script |
| go/internal/calendar/testdata/filing_watchdog_golden.json | regenerate | from the script |
| go/internal/calendar/testdata/filing_watchdog_run_golden.json | regenerate | from `filing_watchdog_run_golden.py` (unchanged; it reuses the base SEED) |
| App/tests/test_deadlines.py | edit | login in `_stay_with_guests`; 3 new tests (11 cases) |
| App/tests/test_filing_watchdog.py | edit | login in `world`; 1 new test (9 cases) |

No other file may change.

## 4. Steps

1. Save the patch in the appendix (between the `~~~diff` fences) to `/tmp/1171.patch` and apply it: `git apply --check /tmp/1171.patch && git apply /tmp/1171.patch 2>&1 | tail -30`. If `--check` fails: STOP (§8). Commit `1171 step 1`.
2. Regenerate the goldens (needs `App/.venv`; if missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):
   `cd App && for s in check_deadlines_golden filing_watchdog_golden filing_watchdog_run_golden; do .venv/bin/python scripts/$s.py 2>&1 | tail -1; done`
   (Logged tracebacks before each `wrote ...` line are expected: seeded bad tokens and a naive timestamp.) Commit `1171 step 2`.
3. Check every file against §7's sha256 list: `sha256sum <the 12 files> 2>&1 | tail -30`. A mismatch: STOP.
4. Run §6. Commit nothing more unless a step changed a file.

## 5. Do not touch

`docs/context/status.md`, `docs/context/test-map.md`, the Go `*_test.go` files, `App/scripts/filing_watchdog_run_golden.py`, `go/internal/calendar/testdata/dsr_due_golden.json`, anything outside §3. Hard rules 1, 3 (fixture values are synthetic: `IDUB-TEST`, `ws-test`, `enc-test`), 5, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_*deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30` → `733 passed, 1 skipped` (the skip is playwright in test_police_letter_flow.py).
- Go needs Postgres. Start one if none: `mkdir -p /var/tmp/pg1171 && chown postgres /var/tmp/pg1171 && su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1171 -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1171 -o '-p 55471 -k /tmp' -l /var/tmp/pg1171/log start" 2>&1 | tail -3`
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres go test ./internal/calendar/... 2>&1 | tail -30` → `ok`; with `-v -run 'MatchesPython|Watchdog'` every test is `--- PASS` (none `SKIP`).
- `cd go && go vet ./internal/calendar/... 2>&1 | tail -30` → no output.
- `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] sha256 of each resulting file:
  - `App/app/filing_watchdog.py` `d26732d3e2395a2c20c21b8416abd98167e3eb341bf7bc0085b5682e31fe0556`
  - `App/app/reporting.py` `08ca760a939f2e692c1fd8b2e293f6b40e381353e1dde2f544afcc77b95193ec`
  - `App/scripts/check_deadlines_golden.py` `1086a8ef3134726de495f30b39d4152a38ed573e0711e612b741872c62c1ccef`
  - `App/scripts/filing_watchdog_golden.py` `d79dfc58d5f89fddc852274137b29c38076e5be6f2ceed14100f136a58adfaa7`
  - `App/tests/test_deadlines.py` `5c92bf24381849c2611efee62a02c37694fbaf2770040fe593c92774e86e8083`
  - `App/tests/test_filing_watchdog.py` `4304663095a89ca9e425e58db476817380b45b0735701e412de39eef1dd85dec`
  - `go/internal/calendar/filing_watchdog.go` `7cb59eb69d54510586bd6bea7e2085c25000f42485e4aca9ef397b0cb3417588`
  - `go/internal/calendar/progress.go` `5c17075575572585d625f386db1eca99bf47167068fe72c8ad39ca30fbefd27d`
  - `go/internal/calendar/testdata/check_deadlines_golden.json` `7230998e3b3d3d6d844c9ad8978fb9bed8fdd59dd00a9cd61ddc903a382ce681`
  - `go/internal/calendar/testdata/filing_watchdog_golden.json` `3eb280cbe5a91a79085a97ea20f40ae21afe2f25912f8c992f67750a935e463d`
  - `go/internal/calendar/testdata/filing_watchdog_run_golden.json` `7ee2e99ed0abdd84b480b09e1efbe3ea6af00111baca45b8823613f9b99d9d86`
  - `go/internal/calendar/watch.go` `e94995af4144b126e10564f00a6347d04153cb87d8d741ee0b495fe0ed4f22cb`
- [ ] In each regenerated JSON only `seed` and the new cases differ from base: check_deadlines `runs` gains exactly `deadline:121` (seeded, resolved by the run), `headcount_mismatch:121` and `headcount_mismatch:123` per run, `raised` stays 6/7/9; filing_watchdog outputs are identical apart from `seed`; filing_watchdog_run gains only `"241"/"242"/"243": null` entries (never mailed).
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

Write `docs/tasks/1171-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/reporting.py` and `go/internal/calendar/watch.go`: the `if settled or not files_with_ubyhost` branch must only fire on a missing/blank field; a fully configured property must reach `deadlines.urgency` as before.
- `App/app/filing_watchdog.py`, `go/internal/calendar/filing_watchdog.go`: the fragment is ANDed into both queries, identical text in both languages.
- The JSON diffs: no existing alert, stay or mail may disappear.
- Risk: a property whose password is stored but decrypts badly still counts as configured (the check is non-blank only), which errs toward watching.

## Owner steps

1. After the PR is green, merge it with `scripts/merge-pr-on-green.sh`.
2. Before merge, check on the server that every property you expect UbyHost to file for has IDUB, web-service user and password filled in: from that moment, a property missing any of them gets no deadline alert and no filing-watchdog mail or page.

## Appendix: the patch (code, scripts, tests; the JSON is regenerated in step 2)

~~~diff
diff --git a/App/app/filing_watchdog.py b/App/app/filing_watchdog.py
index f7e8a2f..f520efb 100644
--- a/App/app/filing_watchdog.py
+++ b/App/app/filing_watchdog.py
@@ -39,6 +39,11 @@ report is due, because Czech guests owe none. Such a stay gets the host mail
 once ("no guest details yet") and a section of the operator digest, but it
 never sets the heartbeat to ``/fail``: that is kept for guests known to be
 reportable, so a stay of Czech guests nobody typed in does not page anyone.
+
+1171: a stay on a property without its UbyPort login (IDUB, web-service user
+or password blank, ``reporting.FILES_WITH_UBYHOST_SQL``) is in neither list.
+UbyHost files nothing for that property, so it gets no host mail, no digest
+line and never sets the heartbeat to ``/fail``.
 """
 from __future__ import annotations
 
@@ -114,6 +119,7 @@ def at_risk_stays(
         "LEFT JOIN user_account u ON u.id = a.owner_user_id "
         "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
         "AND COALESCE(r.source, '') != 'demo' "  # 0100: the setup guide's demo stay
+        "AND " + reporting.FILES_WITH_UBYHOST_SQL + " "
         "AND g.archived_at IS NULL AND g.submit_state != ? "
         "AND g.nationality IS NOT NULL AND g.nationality != '' "
         "ORDER BY r.id",
@@ -185,6 +191,7 @@ def unknown_risk_stays(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
         "LEFT JOIN user_account u ON u.id = a.owner_user_id "
         "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
         "AND COALESCE(r.source, '') != 'demo' "  # 0100: the setup guide's demo stay
+        "AND " + reporting.FILES_WITH_UBYHOST_SQL + " "
         "AND r.date_from <= ? AND r.date_from >= ? "
         "AND NOT EXISTS (SELECT 1 FROM guest g "
         "WHERE g.reservation_id = r.id AND g.archived_at IS NULL) "
diff --git a/App/app/reporting.py b/App/app/reporting.py
index 3358b00..2c31d25 100644
--- a/App/app/reporting.py
+++ b/App/app/reporting.py
@@ -2682,6 +2682,19 @@ def reservation_deadline_anchor(
     return validation.parse_iso_date(reservation["date_from"])
 
 
+# 1171: a property files through UbyHost only when it has the three UbyPort
+# login fields (validation.validate_apartment). A property without them files
+# no police report from UbyHost, so its stays get no deadline alert and are not
+# watched by filing_watchdog. Applied with the apartment alias ``a``. The one
+# place for this rule in Python; go/internal/calendar/watch.go
+# filesWithUbyhostSQL is the Go copy and must match it.
+FILES_WITH_UBYHOST_SQL = (
+    "(COALESCE(TRIM(a.uby_idub), '') != '' "
+    "AND COALESCE(TRIM(a.uby_ws_user), '') != '' "
+    "AND COALESCE(TRIM(a.uby_ws_password_enc), '') != '')"
+)
+
+
 def check_deadlines(
     now: Optional[datetime] = None, owner_user_id: Optional[int] = None
 ) -> int:
@@ -2710,7 +2723,9 @@ def check_deadlines(
     )
     # 0100: a demo stay has no deadline to chase.
     rows = db.query(
-        "SELECT r.*, a.internal_name FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
+        "SELECT r.*, a.internal_name, "
+        f"CASE WHEN {FILES_WITH_UBYHOST_SQL} THEN 1 ELSE 0 END AS files_with_ubyhost "
+        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
         "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
         "AND COALESCE(r.source, '') != 'demo' "
         "AND (? IS NULL OR a.owner_user_id = ?)",
@@ -2774,7 +2789,9 @@ def check_deadlines(
             )
         else:
             alerts.resolve(mismatch_key)
-        if settled:
+        # 1171: no UbyPort login on the property, so UbyHost files nothing
+        # here and no deadline alert is due; an open one is cleared.
+        if settled or not reservation["files_with_ubyhost"]:
             alerts.resolve(key)
             continue
         level = deadlines.urgency(start, now)
diff --git a/App/scripts/check_deadlines_golden.py b/App/scripts/check_deadlines_golden.py
index 3e884eb..6d89f7e 100644
--- a/App/scripts/check_deadlines_golden.py
+++ b/App/scripts/check_deadlines_golden.py
@@ -32,6 +32,8 @@ OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "check_deadline
 SEED_CREATED = "2026-09-01T00:00:00+00:00"
 SEED_RESOLVED = "2026-09-02T00:00:00+00:00"
 STAMP = "2026-09-01T00:00:00+00:00"
+# Any non-blank value: the deadline watch only checks the three fields are set.
+UBY_LOGIN = ["IDUB-TEST", "ws-test", "enc-test"]
 BAD_TOKEN = "not-a-token"
 
 _GUEST_COLUMNS = [
@@ -83,11 +85,17 @@ SEED = [
     {
         "table": "apartment",
         "columns": ["id", "owner_user_id", "internal_name", "city_en", "uby_name",
-                    "permalink_token", "active", "created_at"],
+                    "permalink_token", "active", "created_at", "uby_idub", "uby_ws_user",
+                    "uby_ws_password_enc"],
         "rows": [
-            [1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP],
-            [2, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP],
-            [3, 2, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP],
+            [1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP, *UBY_LOGIN],
+            [2, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP, *UBY_LOGIN],
+            [3, 2, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP, *UBY_LOGIN],
+            # 1171: one UbyPort login field missing or blank: UbyHost files nothing.
+            [4, 1, "Bez IDUB", "Brno", "UBY", "tok4", 1, STAMP, None, "ws-test", "enc-test"],
+            [5, 1, "Bez uzivatele", "Brno", "UBY", "tok5", 1, STAMP, "IDUB-TEST", "   ",
+             "enc-test"],
+            [6, 1, "Bez hesla", "Brno", "UBY", "tok6", 1, STAMP, "IDUB-TEST", "ws-test", ""],
         ],
     },
     {
@@ -116,6 +124,9 @@ SEED = [
             _stay(118, 1, "bad", "2026-09-20", declared=1),  # no check-in date
             _stay(119, 1, "2026-09-15", "2026-09-17", declared=1),  # fee reason unreadable
             _stay(120, 1, "2026-09-10", "2026-09-12", declared=3, reduced=1),
+            _stay(121, 4, "2026-09-10", "2026-09-14", declared=2),  # 1171: shortfall only
+            _stay(122, 5, "2026-09-15", "2026-09-18"),  # 1171: would be urgent: nothing
+            _stay(123, 6, "2026-09-16", "2026-09-20", declared=1),  # 1171: headcount alert only
         ],
     },
     {
@@ -135,6 +146,9 @@ SEED = [
             _guest(9, 118, complete=False, surname="Bad", stay_from="2026-09-10"),
             _guest(10, 119, fee_enc=BAD_TOKEN),
             _guest(11, 120),
+            _guest(12, 121),
+            _guest(13, 123, complete=False, surname="Early", stay_from="2026-09-11",
+                   stay_to="2026-09-20"),
         ],
     },
     {
@@ -165,6 +179,7 @@ SEED = [
                    dismissed=1),
             _alert(9016, "warning", "headcount_mismatch", 1, 104, 1, "headcount_mismatch:104",
                    dismissed=1),
+            _alert(9017, "critical", "deadline", 4, 121, 1, "deadline:121"),  # 1171: resolved
         ],
     },
 ]
diff --git a/App/scripts/filing_watchdog_golden.py b/App/scripts/filing_watchdog_golden.py
index d11e63e..2055a0d 100644
--- a/App/scripts/filing_watchdog_golden.py
+++ b/App/scripts/filing_watchdog_golden.py
@@ -39,6 +39,8 @@ GOLDEN_ENV = {
 }
 
 STAMP = "2026-09-01T00:00:00+00:00"
+# Any non-blank value: the watchdog only checks the three fields are set.
+UBY_LOGIN = ["IDUB-TEST", "ws-test", "enc-test"]
 
 _GUEST_COLUMNS = ["id", "reservation_id", "surname", "nationality", "submit_state",
                   "submission_id", "stay_from", "is_lead", "archived_at",
@@ -85,13 +87,20 @@ SEED = [
     {
         "table": "apartment",
         "columns": ["id", "owner_user_id", "legal_entity_id", "internal_name", "city_en",
-                    "uby_name", "permalink_token", "active", "created_at"],
+                    "uby_name", "permalink_token", "active", "created_at", "uby_idub",
+                    "uby_ws_user", "uby_ws_password_enc"],
         "rows": [
-            [1, 1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP],
-            [2, 1, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP],
-            [3, 2, None, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP],
-            [4, 1, 1, 'Byt <Žižkov> & "Co"', "Praha", "UBY", "tok4", 1, STAMP],
-            [5, None, 2, "", "Brno", "UBY", "tok5", 1, STAMP],
+            [1, 1, 1, "Byt Dole", "Brno", "UBY", "tok1", 1, STAMP, *UBY_LOGIN],
+            [2, 1, 1, "Byt Vypnuty", "Brno", "UBY", "tok2", 0, STAMP, *UBY_LOGIN],
+            [3, 2, None, "Cizi byt", "Brno", "UBY", "tok3", 1, STAMP, *UBY_LOGIN],
+            [4, 1, 1, 'Byt <Žižkov> & "Co"', "Praha", "UBY", "tok4", 1, STAMP, *UBY_LOGIN],
+            [5, None, 2, "", "Brno", "UBY", "tok5", 1, STAMP, *UBY_LOGIN],
+            # 1171: one UbyPort login field missing or blank: UbyHost files nothing.
+            [6, 1, 1, "Bez IDUB", "Brno", "UBY", "tok6", 1, STAMP, "  ", "ws-test", "enc-test"],
+            [7, 1, 1, "Bez uzivatele", "Brno", "UBY", "tok7", 1, STAMP, "IDUB-TEST", None,
+             "enc-test"],
+            [8, 1, 1, "Bez hesla", "Brno", "UBY", "tok8", 1, STAMP, "IDUB-TEST", "ws-test",
+             None],
         ],
     },
     {
@@ -146,6 +155,9 @@ SEED = [
             _stay(228, 1, "2026-09-15"),  # finished_at NULL: not awaiting
             _stay(229, 1, "2026-09-15", mailed=""),  # empty stamp counts as not mailed
             _stay(230, 3, "2026-09-12"),  # no guests, owner 2, overdue: unknown risk
+            _stay(241, 6, "2026-09-15"),  # 1171: would be at risk: neither list
+            _stay(242, 7, "2026-09-10"),  # 1171: would be overdue: neither list
+            _stay(243, 8, "2026-09-12"),  # 1171: no guests, would be unknown risk: neither
         ],
     },
     {
@@ -183,6 +195,8 @@ SEED = [
             _guest(29, 227, submission=307),
             _guest(30, 228, submission=308),
             _guest(31, 229, submission=309, state="error"),
+            _guest(41, 241),
+            _guest(42, 242, "USA", state="error"),
         ],
     },
     {
diff --git a/App/tests/test_deadlines.py b/App/tests/test_deadlines.py
index eb3ffe1..b6beb67 100644
--- a/App/tests/test_deadlines.py
+++ b/App/tests/test_deadlines.py
@@ -1,5 +1,7 @@
 from datetime import date, datetime, timedelta, timezone
 
+import pytest
+
 from app import deadlines as d
 
 
@@ -216,8 +218,12 @@ def test_deadline_watch_uses_czech_time_and_keeps_old_compliance_debt(monkeypatc
 
 # --- the anchor the deadline actually runs from --------------------------
 
-def _stay_with_guests(monkeypatch, tmp_path, name, *, date_from, date_to, guests):
-    """One reservation plus guest rows carrying their own stay dates."""
+def _stay_with_guests(monkeypatch, tmp_path, name, *, date_from, date_to, guests,
+                      login=None):
+    """One reservation plus guest rows carrying their own stay dates.
+
+    The property has its UbyPort login (1171) unless ``login`` overrides fields.
+    """
     from app import config, db
 
     monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
@@ -230,6 +236,10 @@ def _stay_with_guests(monkeypatch, tmp_path, name, *, date_from, date_to, guests
             "automation_mode": "manual",
             "active": 1,
             "created_at": now,
+            "uby_idub": "IDUB-TEST",
+            "uby_ws_user": "ws-test",
+            "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
+            **(login or {}),
         },
     )
     reservation_id = db.insert(
@@ -381,6 +391,65 @@ def test_the_deadline_alert_runs_from_the_guest_arrival(monkeypatch, tmp_path):
     assert "Po termínu o 2 dny" in alerts.present(alert[0], "cs")["display_detail"]
 
 
+# --- 1171: a property without its UbyPort login files nothing ---------------
+
+_OVERDUE_STAY = {"date_from": "2026-09-09", "date_to": "2026-09-14",
+                 "guests": [("2026-09-09", "2026-09-14", None)]}
+
+
+def _run_watch(monkeypatch):
+    from app import reporting
+
+    monkeypatch.setattr(
+        reporting.deadlines, "local_now", lambda _now=None: datetime(2026, 9, 14, 12, 0)
+    )
+    return reporting.check_deadlines(datetime(2026, 9, 14, 12, 0))
+
+
+@pytest.mark.parametrize("field", ["uby_idub", "uby_ws_user", "uby_ws_password_enc"])
+@pytest.mark.parametrize("blank", [None, "", "   "])
+def test_a_property_without_its_ubyport_login_gets_no_deadline_alert(
+    monkeypatch, tmp_path, field, blank
+):
+    from app import alerts, db
+
+    reservation = _stay_with_guests(
+        monkeypatch, tmp_path, "no-login.sqlite3", login={field: blank}, **_OVERDUE_STAY
+    )
+    # An open card from before the property lost its login is cleared.
+    key = f"deadline:{reservation['id']}"
+    alerts.raise_alert("critical", "deadline", "old", "old", dedupe_key=key,
+                       reservation_id=reservation["id"])
+
+    assert _run_watch(monkeypatch) == 0
+    row = db.query_one("SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,))
+    assert row["resolved_at"] is not None
+    assert not [a for a in alerts.open_alerts() if a["kind"] == "deadline"]
+
+
+def test_a_fully_configured_property_is_still_deadline_alerted(monkeypatch, tmp_path):
+    from app import alerts
+
+    _stay_with_guests(monkeypatch, tmp_path, "with-login.sqlite3", **_OVERDUE_STAY)
+
+    assert _run_watch(monkeypatch) == 1
+    assert [a["level"] for a in alerts.open_alerts() if a["kind"] == "deadline"] == ["critical"]
+
+
+def test_a_property_without_its_login_still_gets_the_headcount_alert(monkeypatch, tmp_path):
+    from app import alerts, db
+
+    reservation = _stay_with_guests(
+        monkeypatch, tmp_path, "no-login-headcount.sqlite3", login={"uby_idub": None},
+        **_OVERDUE_STAY,
+    )
+    db.execute("UPDATE reservation SET declared_guests = 2 WHERE id = ?", (reservation["id"],))
+
+    _run_watch(monkeypatch)
+
+    assert [a["kind"] for a in alerts.open_alerts()] == ["headcount_mismatch"]
+
+
 def test_scheduled_send_is_pulled_forward_to_the_deadline_margin():
     from app import db, reporting
 
diff --git a/App/tests/test_filing_watchdog.py b/App/tests/test_filing_watchdog.py
index 5e08fd4..2ff048c 100644
--- a/App/tests/test_filing_watchdog.py
+++ b/App/tests/test_filing_watchdog.py
@@ -82,6 +82,9 @@ def world():
             "automation_mode": "manual",
             "active": 1,
             "created_at": now,
+            "uby_idub": "IDUB-TEST",
+            "uby_ws_user": "ws-test",
+            "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
         },
     )
     counter = {"n": 0}
@@ -368,6 +371,22 @@ def test_the_real_watchdog_runs_inside_the_deadline_job(world, pings, monkeypatc
 # --- stays with no guest on file ("unknown risk") --------------------------------
 
 
+@pytest.mark.parametrize("field", ["uby_idub", "uby_ws_user", "uby_ws_password_enc"])
+@pytest.mark.parametrize("blank", [None, "", "   "])
+def test_a_property_without_its_ubyport_login_is_not_watched(world, field, blank):
+    """1171: UbyHost files nothing there, so no stay of it is at risk or unknown risk."""
+    at_risk = world["add_stay"]([("SVK", "pending")])
+    unknown = world["add_stay"]([])
+    now = datetime(2026, 9, 30, 8, 0)
+    assert at_risk in _mine(filing_watchdog.at_risk_stays(now), {at_risk})
+    assert unknown in _mine(filing_watchdog.unknown_risk_stays(now), {unknown})
+
+    db.execute(f"UPDATE apartment SET {field} = ? WHERE id = ?", (blank, world["apartment_id"]))
+
+    assert not _mine(filing_watchdog.at_risk_stays(now), {at_risk})
+    assert not _mine(filing_watchdog.unknown_risk_stays(now), {unknown})
+
+
 def test_a_stay_without_guests_is_unknown_risk_once_the_guests_have_arrived(world):
     rid = world["add_stay"]([])
 
diff --git a/go/internal/calendar/filing_watchdog.go b/go/internal/calendar/filing_watchdog.go
index f50f8c9..280974b 100644
--- a/go/internal/calendar/filing_watchdog.go
+++ b/go/internal/calendar/filing_watchdog.go
@@ -46,6 +46,7 @@ const watchdogAtRiskSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
 	LEFT JOIN user_account u ON u.id = a.owner_user_id
 	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
 	AND COALESCE(r.source, '') != 'demo'
+	AND ` + filesWithUbyhostSQL + `
 	AND g.archived_at IS NULL AND g.submit_state != $1
 	AND g.nationality IS NOT NULL AND g.nationality != ''
 	ORDER BY r.id`
@@ -60,6 +61,7 @@ const watchdogUnknownSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
 	LEFT JOIN user_account u ON u.id = a.owner_user_id
 	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
 	AND COALESCE(r.source, '') != 'demo'
+	AND ` + filesWithUbyhostSQL + `
 	AND r.date_from <= $1 AND r.date_from >= $2
 	AND NOT EXISTS (SELECT 1 FROM guest g
 	WHERE g.reservation_id = r.id AND g.archived_at IS NULL)
diff --git a/go/internal/calendar/progress.go b/go/internal/calendar/progress.go
index f3ba5e9..6ebe4f1 100644
--- a/go/internal/calendar/progress.go
+++ b/go/internal/calendar/progress.go
@@ -38,6 +38,8 @@ type stayRow struct {
 	declared         *int64
 	override         *int64
 	reduced          *int64
+	// filesWithUbyhost is set by watchStays only (1171).
+	filesWithUbyhost bool
 }
 
 // progressResult is the part of reporting.reservation_progress the calendar needs.
diff --git a/go/internal/calendar/watch.go b/go/internal/calendar/watch.go
index a527861..399a8b2 100644
--- a/go/internal/calendar/watch.go
+++ b/go/internal/calendar/watch.go
@@ -34,10 +34,19 @@ const watchClearSQL = `UPDATE alert SET resolved_at = $1, user_dismissed = 0 WHE
 	AND (r.status != 'active' OR r.archived_at IS NOT NULL)
 	AND ($2::bigint IS NULL OR a.owner_user_id = $2::bigint))`
 
+// filesWithUbyhostSQL is reporting.FILES_WITH_UBYHOST_SQL (1171): the property
+// has the three UbyPort login fields, so UbyHost files its stays. Applied with
+// the apartment alias a. The one place for this rule in Go; keep it equal to
+// the Python fragment.
+const filesWithUbyhostSQL = `(COALESCE(TRIM(a.uby_idub), '') != '' ` +
+	`AND COALESCE(TRIM(a.uby_ws_user), '') != '' ` +
+	`AND COALESCE(TRIM(a.uby_ws_password_enc), '') != '')`
+
 // watchStaysSQL is the stays the watch reads: live, on an active apartment,
 // not the demo stay (0100). The order only makes runs repeatable.
 const watchStaysSQL = `SELECT r.id, r.apartment_id, a.internal_name, r.date_from, r.date_to,
-	r.declared_guests, r.expected_guests_override, r.lead_reduced_guests
+	r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
+	CASE WHEN ` + filesWithUbyhostSQL + ` THEN 1 ELSE 0 END = 1
 	FROM reservation r JOIN apartment a ON a.id = r.apartment_id
 	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
 	AND COALESCE(r.source, '') != 'demo'
@@ -109,7 +118,7 @@ func watchStays(ctx context.Context, pool *pgxpool.Pool, owner *int64) ([]stayRo
 	for rows.Next() {
 		var s stayRow
 		if err := rows.Scan(&s.id, &s.propertyID, &s.property, &s.dateFrom, &s.dateTo,
-			&s.declared, &s.override, &s.reduced); err != nil {
+			&s.declared, &s.override, &s.reduced, &s.filesWithUbyhost); err != nil {
 			return nil, err
 		}
 		out = append(out, s)
@@ -206,7 +215,9 @@ func watchStay(ctx context.Context, pool *pgxpool.Pool, stay stayRow, p progress
 	} else if err := ubyport.ResolveAlert(ctx, pool, mismatchKey); err != nil {
 		return 0, err
 	}
-	if settled {
+	// 1171: no UbyPort login on the property, so UbyHost files nothing here
+	// and no deadline alert is due; an open one is cleared.
+	if settled || !stay.filesWithUbyhost {
 		return 0, ubyport.ResolveAlert(ctx, pool, key)
 	}
 	level := deadlines.Urgency(start, now)
~~~
