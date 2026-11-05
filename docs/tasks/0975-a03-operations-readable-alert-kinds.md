# 0975-a03: Operations alerts: readable label first, raw code kept

Status: todo
Depends on: B01 to B16 merged (master plan B17) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: task/0975-a03
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
In the operator Operations page, the open-alerts table shows a plain-language label for eight common alert kinds, with the raw code kept beside it in a code element. Unmapped kinds show the raw code exactly as today.

## 2. Context

Finding A03 is an "Opportunity" in the review (not a confirmed defect). Rules: one explanation lives in one place; no new dependency; no behaviour change; light mode only.
Anchor: `admin_operations.html`, the open-alerts table row `<td data-label="{{ t('ops.col.kind') }}" class="ui-mono">{{ row.kind }}</td>` followed by the `ops.col.level` cell (the same `row.kind` td also exists in the mail and Havel tables; those stay untouched). `t()` returns the key itself when a key is missing (`host_i18n.lookup`), which the template uses as the fallback test. Existing test asserts `"ops." not in html`; the patch never prints a key. Keys go EN and CS (parity test `test_host_i18n.py` requires both); VI falls back to English. Kinds without a label (the other ~23) keep the raw code; a later brief can add more.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/admin_operations.html | edit | label + raw code in the alerts table only |
| App/app/host_i18n.py | edit | 8 keys `ops.alert_kind.*` in EN and CS |
| App/tests/test_admin_operations.py | edit | one new test, one import |
No other file may change.

## 4. Steps

1. Save the patch below to `/tmp/0975-a03.patch` (exact text), run `git apply --check /tmp/0975-a03.patch`. If it fails, STOP (anchor moved; brief §8).
2. `git apply /tmp/0975-a03.patch`, then commit `0975 step 1`.
3. Run §6, one test row at a time. Commit `0975 step 2` if you changed anything to fix a first failure (once only).

```diff
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..56f68628 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -6829,6 +6829,14 @@ _ADMIN_OPERATIONS_STRINGS = {
         "ops.col.last_ok": "Last success",
         "ops.col.mail": "Message",
         "ops.col.kind": "Kind",
+        "ops.alert_kind.deadline": "Report deadline at risk",
+        "ops.alert_kind.headcount_mismatch": "Guest forms missing",
+        "ops.alert_kind.guest_incomplete_checkin": "Guest check-in incomplete",
+        "ops.alert_kind.submission_stuck": "Filing stuck",
+        "ops.alert_kind.submission_rejected": "Filing rejected",
+        "ops.alert_kind.job_failed": "Background job failed",
+        "ops.alert_kind.mail_failed": "Email not sent",
+        "ops.alert_kind.feed_error": "Calendar feed error",
         "ops.col.attempts": "Attempts",
         "ops.col.level": "Level",
         "ops.col.count": "Count",
@@ -6896,6 +6904,14 @@ _ADMIN_OPERATIONS_STRINGS = {
         "ops.col.last_ok": "Poslední úspěch",
         "ops.col.mail": "Zpráva",
         "ops.col.kind": "Druh",
+        "ops.alert_kind.deadline": "Hrozí termín hlášení",
+        "ops.alert_kind.headcount_mismatch": "Chybí formuláře hostů",
+        "ops.alert_kind.guest_incomplete_checkin": "Neúplná registrace hosta",
+        "ops.alert_kind.submission_stuck": "Hlášení uvízlo",
+        "ops.alert_kind.submission_rejected": "Hlášení odmítnuto",
+        "ops.alert_kind.job_failed": "Selhala úloha na pozadí",
+        "ops.alert_kind.mail_failed": "E-mail se neodeslal",
+        "ops.alert_kind.feed_error": "Chyba kalendářového feedu",
         "ops.col.attempts": "Pokusy",
         "ops.col.level": "Úroveň",
         "ops.col.count": "Počet",
diff --git a/App/app/templates/admin_operations.html b/App/app/templates/admin_operations.html
index a4efa386..3d3ad8d0 100644
--- a/App/app/templates/admin_operations.html
+++ b/App/app/templates/admin_operations.html
@@ -131,7 +131,8 @@
     <tbody>
     {% for row in ops.alerts.rows %}
       <tr>
-        <td data-label="{{ t('ops.col.kind') }}" class="ui-mono">{{ row.kind }}</td>
+        {% set kind_key = 'ops.alert_kind.' ~ row.kind %}{% set kind_label = t(kind_key) %}
+        <td data-label="{{ t('ops.col.kind') }}">{% if kind_label != kind_key %}{{ kind_label }} {% endif %}<code class="ui-mono ui-sub">{{ row.kind }}</code></td>
         <td data-label="{{ t('ops.col.level') }}">{{ row.level }}</td>
         <td data-label="{{ t('ops.col.count') }}">{{ row.count }}</td>
         <td data-label="{{ t('ops.col.oldest') }}">{{ age(row.age_minutes) }}</td>
diff --git a/App/tests/test_admin_operations.py b/App/tests/test_admin_operations.py
index 8702fa0c..4f2abdaf 100644
--- a/App/tests/test_admin_operations.py
+++ b/App/tests/test_admin_operations.py
@@ -12,7 +12,7 @@ from datetime import datetime, timedelta, timezone
 import pytest
 from fastapi.testclient import TestClient
 
-from app import admin_ops, auth, config, db, demo, reporting, scheduler
+from app import admin_ops, alerts, auth, config, db, demo, reporting, scheduler
 from app.main import app
 from tests.conftest import login_as
 
@@ -103,6 +103,23 @@ def test_admin_sees_every_section_and_no_guest_identity(monkeypatch):
     assert "Hlášení vyžadující pozornost" in czech
 
 
+def test_alert_kinds_read_in_plain_words_with_the_raw_code_kept(monkeypatch):
+    _account("admin", "admin")
+    db.execute("DELETE FROM alert WHERE dedupe_key LIKE 'wp10-ops-%'")
+    for kind in ("headcount_mismatch", "unmapped_kind_zz"):
+        alerts.raise_alert("warning", kind, "x", dedupe_key=f"wp10-ops-{kind}")
+    try:
+        client = _login("admin")
+        english = client.get("/admin/operations?lang=en").text
+        assert "Guest forms missing" in english
+        assert "<code" in english and "headcount_mismatch" in english  # raw code stays
+        assert "unmapped_kind_zz" in english  # no label: the code is all there is
+        assert "ops.alert_kind" not in english
+        assert "Chybí formuláře hostů" in client.get("/admin/operations?lang=cs").text
+    finally:
+        db.execute("DELETE FROM alert WHERE dedupe_key LIKE 'wp10-ops-%'")
+
+
 def test_filings_are_one_row_per_stay_with_the_worst_state():
     host_id = _account("filings", "host")
     now = db.utcnow()
```

## 5. Do not touch
App/app/admin_ops.py, alerts.py, static files, the mail and Havel tables, `host_vi_i18n.py`. No contrast or target-size claim without a measurement. Never push or merge.

## 6. Commands

From `App/`; every command ends `2>&1 | tail -30`. `export UBYHOST_SHOTS_DIR=/tmp/ubyhost-b17` first (create it with `mkdir -p`).

```
.venv/bin/python -m pytest tests/test_admin_operations.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_0894_admin_airbnb_billing_ops_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```
0 skipped in every browser file. (Rows: operator customer dashboard; copy and translations; host pages; v2 pages.)

Screenshots: `test_layout_lint_browser.py` writes 390/768/1280 PNGs of host pages to `$UBYHOST_SHOTS_DIR/layout-lint`. Seed one alert of a mapped kind and one unmapped kind in a throwaway local database before opening the page, or the table is empty. Open the /admin/operations (open alerts table) PNGs at 390, 768 and 1280 once each. Repeat the visual check with `?lang=cs` (EN and CS, Chromium). If no PNG for the page exists after the run, STOP and report `blocked`; do not write a new screenshot script.

## 7. Acceptance

- [ ] Mapped kind shows label then the raw code in `<code>`; unmapped kind shows only the code; mail and Havel tables unchanged.
- [ ] Czech page shows Czech labels; the raw code is the same in both languages and stays selectable/copyable.
- [ ] No horizontal scroll at 390/768/1280 (stacked table labels intact at 390).
- [ ] All §6 commands green, 0 skipped; one line per page in the PR on what you saw (UX gate).

## 8. Stop and ask

Stop and write the report (`docs/tasks/0975-a03-report.md`, `Status: review` or `blocked`) if: the patch does not apply; a test fails twice; a test is skipped; a file outside §3 needs a change; 25 tool calls or about 50k tokens are reached; push, merge or deploy would be needed (hand to the owner).

## 9. Report

Files changed (`git diff --stat`), each command's last 5 lines, §7 ticked, deviations, questions, owner steps left.
