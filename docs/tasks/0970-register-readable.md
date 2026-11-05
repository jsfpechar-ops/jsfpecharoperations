# 0970: make the house book readable without touching statutory output

Status: blocked
Depends on: B11 (run on the base commit below; files are narrow) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0970-b12-register
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Worktree: /tmp/ubyhost-b12-worktree (already created)

## 1. Objective

The on-screen house book (`/housebook`, desktop table) shows 11 columns and needs sideways scrolling; it also prints Czech purpose and country text in an English interface. This brief cuts the table to four operational columns plus one Details button, moves the other stored facts into a same-page popover on the existing page, and localises the labels. The CSV, the PDF forms and every stored value stay byte-for-byte as they are.

## 2. Context

Findings H01 (11 columns too wide) and H02 (English register mixes Czech labels). Rules that apply: AGENTS.md hard rules 1 (filing correctness first), 2 (no new personal-data field, no new outbound request), 5, 6, 7, 9, 10. No route is added, no access control changes, and no stored mandatory field is removed from any export.

Facts already checked (do not re-explore):

- Under 1024 px the page already swaps the table for stacked cards (`.stays-phone`, CSS in app2.css, untouched). Each card shows surname, first name, stay, property and the reporting pill together and links to the existing guest page `/guests/<id>`. So phones never scroll sideways; this brief does not touch them.
- At 1024 px and wider the table (`.stays-desk .housebook-table`) is shown. It lives in `App/app/templates/housebook.html`.
- Row values come from `housebook.housebook_rows()` -> `_housebook_export_row()` in `App/app/housebook.py`. The CSV writer (`iter_housebook_csv_rows`) reads only the keys listed in `HOUSEBOOK_COLUMNS`, so keys starting with an underscore never reach it. `row.purpose` there is the Czech label (the statutory CSV value) and `row.residence` is the Czech composed string. The page cannot translate those, so the patch adds four underscore keys with the raw values (`_purpose_code`, `_res_street`, `_res_city`, `_res_country`). Nothing else in `housebook.py` changes.
- Presentation helpers, already registered as template globals in `App/app/templating.py` (not edited): `purpose_label(code, lang)` = `validation.purpose_label`, and `country_name(code, lang)` = `validation.country_name`. `lang` is the interface language (en, cs, vi). `validation.country_name` has no Vietnamese list and falls back to English; that is accepted.
- New keys `housebook.details` and `housebook.details_for` are added to the three host language tables: English and Czech in `App/app/host_i18n.py`, Vietnamese in `App/app/host_vi_i18n.py`. Every supported host language gets both keys.
- The Details control is a `button` with `popovertarget` and a `popover` card in the same cell: native, no JavaScript, no CSS file change, no route. The row click handler in `app.js` ignores clicks on buttons, so the row link still works elsewhere. Esc closes the popover and returns focus to the button.
- The `td` of the guest cell no longer carries the class `col-name`, because the existing rule `td.col-name{max-width:0;white-space:nowrap;text-overflow:ellipsis}` cut long surnames to "Surn..." on screen. The header cell keeps its class.
- A first design with `<details>` inside the cell failed the repo layout lint (`table-squeezed`: the lint counts the collapsed content lines). Do not switch back to `<details>` or edit `tests/layout_lint.js`.
- Known and accepted: at exactly 1024 px the five-column table plus Details can still scroll inside its own card for very wide rows; the test only requires no sideways scrolling at 1280 px and no page-level overflow at any width.

Baseline for the export check: the test records the CSV on the unchanged code to `/tmp/ubyhost-b12/export-before.csv` (Step 2) and compares byte for byte after the change (Step 4). The seeded data is fixed, so the bytes are deterministic.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_0970_register_readable_browser.py | create | Step 1 patch: export byte comparison, label tests, Chromium checks at 390/768/1024/1280, EN and CS |
| App/app/templates/housebook.html | edit | Step 3 patch: five-column table, Details popover, localised labels |
| App/app/housebook.py | edit | Step 3 patch: four underscore keys on the on-screen row (CSV and PDF unaffected) |
| App/app/host_i18n.py | edit | Step 3 patch: `housebook.details`, `housebook.details_for` (en, cs) |
| App/app/host_vi_i18n.py | edit | Step 3 patch: the same two keys (vi) |
| docs/tasks/0970-report.md | create | Step 6 |

No other file may change. No static file changes, so `App/tests/static_versions.json` stays as it is (`python3 scripts/context_lint.py` and `tests/test_static_versions.py` must stay green; do not edit the json).
Note for the orchestrator: `housebook.py` and the new test file are outside the original file list; both are needed (the page has no raw purpose code otherwise, and the list had no register browser test to append to). If the owner rejects this, stop at Step 1 and hand back.

## 4. Steps

Work in the worktree: `cd /tmp/ubyhost-b12-worktree`. It is on branch `codex/0970-b12-register`; do not switch branches. Save each patch below to a file (use the Write tool, exact text) before applying it.

### Step 0. Set up (no commit)

```
cd /tmp/ubyhost-b12-worktree && git status --short | tail -5 && git log --oneline -1 | tail -1
ln -s /tmp/ubyhost-0958-worktree/App/.venv /tmp/ubyhost-b12-worktree/App/.venv
mkdir -p /tmp/ubyhost-b12
```
Expected: no modified files (the brief itself is committed already), and `.venv/bin/python` exists. If `.venv` already exists as a symlink, skip the `ln`. If the symlink target is missing, STOP.

### Step 1. Add the test file

Anchor: `ls App/tests/test_0970_register_readable_browser.py` must say "No such file". Save the patch below as `/tmp/ubyhost-b12/test.patch`, then:

```
cd /tmp/ubyhost-b12-worktree && git apply --check /tmp/ubyhost-b12/test.patch && git apply /tmp/ubyhost-b12/test.patch && git add -A App/tests && git commit -q -m "0970 step 1" 2>&1 | tail -3
```

```diff
diff --git a/App/tests/test_0970_register_readable_browser.py b/App/tests/test_0970_register_readable_browser.py
new file mode 100644
index 00000000..ddef19fc
--- /dev/null
+++ b/App/tests/test_0970_register_readable_browser.py
@@ -0,0 +1,280 @@
+"""0970: the house book is readable and its statutory output is untouched.
+
+Browser checks (Chromium, 0 skipped with UBYHOST_REQUIRE_BROWSER=1) for the populated register at
+390, 768, 1024 and 1280 px in English and Czech, plus a byte-for-byte check of the CSV export
+against a copy recorded on the unchanged code (UBYHOST_B12_RECORD=1 records, no value compares).
+"""
+from __future__ import annotations
+
+import hashlib
+import os
+import secrets
+import socket
+import threading
+import time
+from pathlib import Path
+
+import pytest
+
+REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
+if REQUIRE_BROWSER:
+    import playwright.sync_api as sync_api
+else:
+    sync_api = pytest.importorskip("playwright.sync_api")
+
+import uvicorn
+from fastapi.testclient import TestClient
+
+from app import auth, db, validation
+from app.main import app
+from tests.browser_support import chromium_launch_kwargs, settle_motion
+from tests.conftest import login_as
+from tests.v2_mockup import geometry_findings
+
+PREFIX = "reg-0970-"
+SIGNATURE = "data:image/png;base64,AAAA"
+SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b12")
+GOLDEN = Path(os.environ.get("UBYHOST_B12_EXPORT_GOLDEN") or "/tmp/ubyhost-b12/export-before.csv")
+LONG_SURNAME = "Kowalczyk-Nowakowska"
+LONG_PROPERTY = "Rooftop Suite Vinohrady Residence"
+
+
+def _cleanup():
+    db.init_db()
+    for user in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
+        owner_id = user["id"]
+        apartments = "(SELECT id FROM apartment WHERE owner_user_id = ?)"
+        db.execute(
+            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN "
+            + apartments + ")",
+            (owner_id,),
+        )
+        db.execute("DELETE FROM reservation WHERE apartment_id IN " + apartments, (owner_id,))
+        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
+        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
+        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
+        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
+        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
+
+
+def _guest(reservation_id, **fields):
+    now = db.utcnow()
+    db.insert("guest", {"reservation_id": reservation_id, "created_at": now, "updated_at": now, **fields})
+
+
+@pytest.fixture(scope="module")
+def reg():
+    _cleanup()
+    tag = secrets.token_hex(4)
+    username = f"{PREFIX}{tag}"
+    owner_id = auth.create_account(f"{username}@example.test", "Register Host", role="host", username=username)
+    now = db.utcnow()
+    apartment_id = db.insert("apartment", {
+        "internal_name": LONG_PROPERTY, "owner_user_id": owner_id, "permalink_token": f"reg0970-{tag}",
+        "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": now,
+    })
+    rid = db.insert("reservation", {
+        "apartment_id": apartment_id, "source": "manual", "uid": f"reg0970-{tag}",
+        "date_from": "2026-03-10", "date_to": "2026-03-15", "status": "active",
+        "created_at": now, "updated_at": now,
+    })
+    # Complete, long name, tourism, filed.
+    _guest(rid, first_name="Maximilian Alexander", surname=LONG_SURNAME, birth_date="15031985",
+           nationality="DEU", doc_number="C01X00T47", res_street="Hauptstrasse 12", res_city="Berlin",
+           res_country="DEU", purpose="10", signature_png=SIGNATURE, submit_state="sent",
+           submitted_at="2026-03-16T09:00:00+00:00", stay_from="2026-03-10", stay_to="2026-03-15")
+    # Incomplete: no document, no residence, not signed, not sent.
+    _guest(rid, first_name="Ann", surname="Short", birth_date="01011990", nationality="USA",
+           purpose="01", submit_state="pending", stay_from="2026-03-10", stay_to="2026-03-15")
+    # Visa holder, business, rejected.
+    _guest(rid, first_name="Olivia", surname="Smith", birth_date="02022000", nationality="GBR",
+           doc_number="P1234567", visa_number="V998877", res_street="High Street 1", res_city="London",
+           res_country="GBR", purpose="03", signature_png=SIGNATURE, submit_state="error",
+           stay_from="2026-03-10", stay_to="2026-03-15")
+    client = TestClient(app)
+    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
+    try:
+        yield {"client": client, "cookie": client.cookies.get(auth.SESSION_COOKIE), "apartment": apartment_id}
+    finally:
+        _cleanup()
+
+
+@pytest.fixture(scope="module")
+def base(reg):
+    with socket.socket() as sock:
+        sock.bind(("127.0.0.1", 0))
+        port = sock.getsockname()[1]
+    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
+    thread = threading.Thread(target=server.run, daemon=True)
+    thread.start()
+    deadline = time.time() + 15
+    while not server.started and time.time() < deadline:
+        time.sleep(0.05)
+    if not server.started:
+        pytest.fail("the 0970 test server did not start")
+    yield f"http://127.0.0.1:{port}"
+    server.should_exit = True
+    thread.join(timeout=5)
+
+
+def _launch(playwright):
+    try:
+        return playwright.chromium.launch(**chromium_launch_kwargs())
+    except Exception:
+        if REQUIRE_BROWSER:
+            raise
+        pytest.skip("chromium is not available")
+
+
+def _open(browser, base_url, reg, width, lang):
+    context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
+    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": reg["cookie"], "url": base_url + "/"}])
+    context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
+    page = context.new_page()
+    page.goto(f"{base_url}/housebook?apartment={reg['apartment']}&lang={lang}")
+    page.wait_for_load_state("networkidle")
+    later = page.locator("#security-prompt [data-security-prompt-later]")
+    if later.is_visible():
+        later.click()
+    page.evaluate("window.scrollTo(0, 0)")
+    return context, page
+
+
+def _shot(page, name):
+    SHOTS.mkdir(parents=True, exist_ok=True)
+    page.screenshot(path=str(SHOTS / name), full_page=True)
+
+
+# ---------------------------------------------------------------- export
+
+def test_csv_export_is_byte_identical_to_the_recorded_baseline(reg):
+    """Statutory output: the CSV must be the same bytes before and after this change."""
+    response = reg["client"].get(f"/housebook.csv?apartment={reg['apartment']}")
+    assert response.status_code == 200
+    body = response.content
+    text = body.decode("utf-8-sig")
+    # The statutory values stay in Czech and as codes, whatever the interface language.
+    assert "Turistika" in text and "Obchodní" not in text.split("Short")[0]
+    assert ";DEU;" in text and ";USA;" in text and "DEU-" in text
+    if os.environ.get("UBYHOST_B12_RECORD") == "1":
+        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
+        GOLDEN.write_bytes(body)
+        print("recorded", len(body), hashlib.sha256(body).hexdigest())
+        return
+    assert GOLDEN.exists(), f"record the baseline first with UBYHOST_B12_RECORD=1 ({GOLDEN})"
+    assert body == GOLDEN.read_bytes(), "the CSV export changed"
+
+
+def test_register_rows_keep_every_export_column(reg):
+    """The on-screen helper keys must not leak into the export columns."""
+    from app import housebook
+
+    rows = housebook.housebook_rows(reg["apartment"])
+    assert len(rows) == 3
+    for row in rows:
+        for key, _label in housebook.HOUSEBOOK_COLUMNS:
+            assert not key.startswith("_") and key in row
+    assert [key for key, _ in housebook.HOUSEBOOK_COLUMNS][:4] == ["apartment", "idub", "stay_from", "stay_to"]
+
+
+# ---------------------------------------------------------------- labels
+
+def test_presentation_labels_follow_the_interface_language(reg):
+    client = reg["client"]
+    en = client.get(f"/housebook?apartment={reg['apartment']}&lang=en").text
+    assert "Tourism" in en and "Germany (DEU)" in en and "Visiting family or friends" in en
+    for czech in ("Turistika", "Obchodní", "Návštěva rodiny", "Německo"):
+        assert czech not in en, czech
+    cs = client.get(f"/housebook?apartment={reg['apartment']}&lang=cs").text
+    assert "Turistika" in cs and "Podrobnosti" in cs and "Německo (DEU)" in cs
+    assert "Tourism" not in cs
+    vi = client.get(f"/housebook?apartment={reg['apartment']}&lang=vi").text
+    assert validation.purpose_label("10", "vi") in vi and "(DEU)" in vi
+
+
+# ---------------------------------------------------------------- browser
+
+@pytest.mark.parametrize("lang", ["en", "cs"])
+@pytest.mark.parametrize("width", [390, 768, 1024, 1280])
+def test_register_is_readable(width, lang, base, reg):
+    with sync_api.sync_playwright() as playwright:
+        browser = _launch(playwright)
+        context, page = _open(browser, base, reg, width, lang)
+        try:
+            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
+            assert overflow <= 0, f"page overflows by {overflow}px at {width}px"
+            _shot(page, f"register-{width}-{lang}.png")
+            assert geometry_findings(page, width) == []
+            if width < 1024:
+                # Phones and tablets: stacked cards, no table at all, so nothing scrolls sideways.
+                assert not page.locator(".housebook-scroll").is_visible()
+                cards = page.locator(".stays-phone .card.stay")
+                assert cards.count() == 3
+                for i in range(3):
+                    card = cards.nth(i)
+                    assert card.is_visible()
+                    box = card.bounding_box()
+                    assert box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5
+                    # Identity and reporting status are readable together in the same card.
+                    name_box = card.locator(".in b").bounding_box()
+                    pill_box = card.locator(".pill").bounding_box()
+                    for inner in (name_box, pill_box):
+                        assert inner["height"] > 0
+                        assert box["y"] <= inner["y"] and inner["y"] + inner["height"] <= box["y"] + box["height"] + 0.5
+                        assert inner["x"] + inner["width"] <= width + 0.5
+            else:
+                assert page.locator(".housebook-scroll").is_visible()
+                assert page.locator(".housebook-table thead th").count() == 6
+                if width >= 1280:  # 1024 keeps the card's own sideways scroll for very wide rows
+                    scroll = page.evaluate(
+                        "() => { const e = document.querySelector('.housebook-scroll'); return e.scrollWidth - e.clientWidth; }")
+                    assert scroll <= 1, f"the register table scrolls sideways by {scroll}px at {width}px"
+                rows = page.locator(".housebook-table tbody tr")
+                assert rows.count() == 3
+                for i in range(3):
+                    row = rows.nth(i)
+                    name_box = row.locator(".col-guest strong").bounding_box()
+                    pill_box = row.locator(".col-reported .pill").bounding_box()
+                    assert name_box["x"] + name_box["width"] <= width and pill_box["x"] + pill_box["width"] <= width
+                # Keyboard: Tab from the first row reaches its Details button, Enter opens the facts.
+                first = rows.first
+                first.focus()
+                reached = False
+                for _ in range(10):
+                    page.keyboard.press("Tab")
+                    if page.evaluate("() => document.activeElement.matches('.col-more > button[popovertarget]')"):
+                        reached = True
+                        break
+                assert reached, "Details was not reachable with Tab"
+                page.keyboard.press("Enter")
+                opened = page.locator(".housebook-facts:popover-open")
+                opened.wait_for(state="visible")
+                assert "/housebook" in page.url and "/guests/" not in page.url
+                text = opened.inner_text()
+                for needle in (LONG_SURNAME, "15.03.1985", "C01X00T47", "Hauptstrasse 12"):
+                    assert needle in text, needle
+                if lang == "en":
+                    assert "Tourism" in text and "Germany (DEU)" in text and "Date of birth" in text
+                    for czech in ("Turistika", "Německo"):
+                        assert czech not in text
+                else:
+                    assert "Turistika" in text and "Německo (DEU)" in text and "Datum narození" in text
+                assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
+                _shot(page, f"register-{width}-{lang}-open.png")
+                # Escape closes it and puts focus back on the button.
+                page.keyboard.press("Escape")
+                assert page.locator(".housebook-facts:popover-open").count() == 0
+                assert page.evaluate("() => document.activeElement.matches('.col-more > button[popovertarget]')")
+                # Every record's facts are complete and follow the interface language.
+                for i in range(3):
+                    rows.nth(i).locator(".col-more > button[popovertarget]").click()
+                    shown = page.locator(".housebook-facts:popover-open")
+                    shown.wait_for(state="visible")
+                    body = shown.inner_text()
+                    if lang == "en":
+                        for czech in ("Turistika", "Obchodní", "Návštěva rodiny", "Německo", "Spojené"):
+                            assert czech not in body, czech
+                    page.keyboard.press("Escape")
+        finally:
+            context.close()
+            browser.close()
```

### Step 2. Record the export baseline on the UNCHANGED code

Anchor: `grep -c "_purpose_code" App/app/housebook.py` must print 0 (the code patch is not applied yet). Run from `App/`:

```
cd /tmp/ubyhost-b12-worktree/App && UBYHOST_B12_RECORD=1 UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0970_register_readable_browser.py -q --tb=short -x -s -k csv_export 2>&1 | tail -30
```
Expected: a line `recorded 740 <sha256>` and `1 passed`. Write the sha256 into the report. Do not commit anything (the baseline lives in /tmp). If the byte count is not 740, still go on, but report the number you got.

### Step 3. Apply the code patch

Anchors, each must print exactly one line before you patch (else STOP):

```
cd /tmp/ubyhost-b12-worktree/App
grep -nF "The register is eleven columns of legal record" app/templates/housebook.html
grep -nF '"stamp": stamp,' app/housebook.py
grep -nF '"housebook.visa": "visa %(number)s",' app/host_i18n.py
grep -nF '"housebook.visa": "vízum %(number)s",' app/host_i18n.py
grep -nF '"housebook.visa": "thị thực %(number)s",' app/host_vi_i18n.py
```

Save the patch below as `/tmp/ubyhost-b12/code.patch`, then:

```
cd /tmp/ubyhost-b12-worktree && git apply --check /tmp/ubyhost-b12/code.patch && git apply /tmp/ubyhost-b12/code.patch && git add -A App/app && git commit -q -m "0970 step 3" 2>&1 | tail -3
```
If `--check` fails, STOP (§8). Do not hand-edit to make it fit.

```diff
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..c1d3262c 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -4187,6 +4187,8 @@ _INTERFACE_STRINGS = {
         "housebook.signed": "Signed",
         "housebook.reported": "Reported",
         "housebook.visa": "visa %(number)s",
+        "housebook.details": "Details",
+        "housebook.details_for": "Details for %(name)s",
         "housebook.signed_yes": "Signed",
         "housebook.signed_no": "Not signed",
         "housebook.not_sent": "Not yet sent",
@@ -5022,6 +5024,8 @@ _INTERFACE_STRINGS = {
         "housebook.signed": "Podepsáno",
         "housebook.reported": "Nahlášeno",
         "housebook.visa": "vízum %(number)s",
+        "housebook.details": "Podrobnosti",
+        "housebook.details_for": "Podrobnosti: %(name)s",
         "housebook.signed_yes": "Podepsáno",
         "housebook.signed_no": "Bez podpisu",
         "housebook.not_sent": "Dosud neodesláno",
diff --git a/App/app/host_vi_i18n.py b/App/app/host_vi_i18n.py
index 28f23a46..815896b8 100644
--- a/App/app/host_vi_i18n.py
+++ b/App/app/host_vi_i18n.py
@@ -1682,6 +1682,8 @@ STRINGS: Dict[str, str] = {
     "housebook.signed": "Đã ký",
     "housebook.reported": "Đã khai báo",
     "housebook.visa": "thị thực %(number)s",
+    "housebook.details": "Chi tiết",
+    "housebook.details_for": "Chi tiết của %(name)s",
     "housebook.signed_yes": "Đã ký",
     "housebook.signed_no": "Chưa ký",
     "housebook.not_sent": "Chưa gửi",
diff --git a/App/app/housebook.py b/App/app/housebook.py
index 9572c4d4..e70b8051 100644
--- a/App/app/housebook.py
+++ b/App/app/housebook.py
@@ -164,6 +164,12 @@ def _housebook_export_row(row: Dict[str, Any]) -> Dict[str, Any]:
         "reported": reported,
         "reported_at": (row["manual_filed_at"] if by_hand else row["submitted_at"]) or "",
         "stamp": stamp,
+        # 0970: raw values for the on-screen register only. The CSV reads
+        # HOUSEBOOK_COLUMNS and never sees keys that start with an underscore.
+        "_purpose_code": row["purpose"] or "",
+        "_res_street": row["res_street"] or "",
+        "_res_city": row["res_city"] or "",
+        "_res_country": (row["res_country"] or "").upper(),
         "_guest_id": row["id"],
         "_apartment_id": row["apartment_id"],
     }
diff --git a/App/app/templates/housebook.html b/App/app/templates/housebook.html
index 8786edac..f9a4baa3 100644
--- a/App/app/templates/housebook.html
+++ b/App/app/templates/housebook.html
@@ -81,37 +81,49 @@
 </form>
 
 {% if rows %}
-{# The register is eleven columns of legal record. It keeps every word whole
-   and scrolls sideways inside its own card when the viewport is narrower
-   than the row; the shaded edge shows there is more to the right. #}
+{# 0970: the table keeps four operational columns and a Details column. The other
+   stored facts sit in a same-page popover opened from that cell; the CSV and the PDF
+   forms are built elsewhere and still carry every column. The labels follow
+   the interface language; the stored codes are only shown beside them. #}
 <div class="card stays-desk housebook-scroll scroll-x" tabindex="0" role="region" aria-label="{{ t('housebook.title') }}">
   <table class="housebook-table">
     <thead>
       <tr>
-        <th class="col-stay">{{ t('housebook.stay') }}</th><th class="col-property">{{ t('housebook.apartment') }}</th><th class="col-name">{{ t('housebook.guest') }}</th><th class="col-born">{{ t('housebook.born') }}</th><th>{{ t('housebook.nationality') }}</th>
-        <th class="col-doc">{{ t('housebook.document') }}</th><th class="col-address">{{ t('housebook.residence') }}</th>
-        <th class="col-purpose">{{ t('housebook.purpose') }}</th><th>{{ t('housebook.signed') }}</th>
-        <th class="col-reported">{{ t('housebook.reported') }}</th><th><span class="sr-only">{{ t('common.actions') }}</span></th>
+        <th class="col-stay">{{ t('housebook.stay') }}</th><th class="col-property">{{ t('housebook.apartment') }}</th><th class="col-name">{{ t('housebook.guest') }}</th>
+        <th class="col-reported">{{ t('housebook.reported') }}</th><th class="col-more">{{ t('housebook.details') }}</th><th><span class="sr-only">{{ t('common.actions') }}</span></th>
       </tr>
     </thead>
     <tbody>
     {% for row in rows %}
+      {% set nationality_text = (country_name(row.nationality, lang) ~ ' (' ~ row.nationality ~ ')') if row.nationality else '—' %}
+      {% set res_parts = [] %}
+      {% if row._res_street %}{% set _ = res_parts.append(row._res_street) %}{% endif %}
+      {% if row._res_city %}{% set _ = res_parts.append(row._res_city) %}{% endif %}
+      {% if row._res_country %}{% set _ = res_parts.append(country_name(row._res_country, lang) ~ ' (' ~ row._res_country ~ ')') %}{% endif %}
       <tr class="clickable-row" data-href="/guests/{{ row._guest_id }}?return_to=/housebook" tabindex="0" role="link">
         <td class="nowrap small" data-label="{{ t('housebook.stay') }}">{{ row.stay_from | date_cz }}<br>{{ row.stay_to | date_cz }}</td>
         <td class="small col-property" data-label="{{ t('housebook.apartment') }}">{{ property_identity(row._apartment_id, row.apartment, true, truncate=true) }}</td>
-        {# Two deliberate lines beat three ragged ones in a column this narrow. #}
-        <td class="col-name" data-label="{{ t('housebook.guest') }}"><strong>{{ row.surname }}</strong><br>
+        {# Two deliberate lines. No col-name class on the cell: that rule clips a long surname to an ellipsis, and the register must show it whole. #}
+        <td class="col-guest" data-label="{{ t('housebook.guest') }}"><strong>{{ row.surname }}</strong><br>
           <span class="small">{{ row.first_name }}</span></td>
-        <td class="nowrap small" data-label="{{ t('housebook.born') }}">{{ row.birth_date | date_cz }}</td>
-        <td class="small" data-label="{{ t('housebook.nationality') }}">{{ row.nationality }}</td>
-        <td class="mono small" data-label="{{ t('housebook.document') }}">{{ guest_identifier(row.doc_number, row._guest_id) }}{% if row.visa_number %}<br>{{ t('housebook.visa', number=guest_identifier(row.visa_number, row._guest_id)) }}{% endif %}</td>
-        <td class="small col-address" data-label="{{ t('housebook.residence') }}">{{ row.residence or '—' }}</td>
-        <td class="small col-purpose" data-label="{{ t('housebook.purpose') }}">{{ row.purpose }}</td>
-        <td class="small nowrap" data-label="{{ t('housebook.signed') }}">{% if row.signed == 'yes' %}<span class="pill p-ok">{{ t('housebook.signed_yes') }}</span>
-          {% else %}<span class="pill p-warn">{{ t('housebook.signed_no') }}</span>{% endif %}</td>
         {# The stored values double as the CSV column, which the importer reads
            back, so they stay as they are and only the label changes here. #}
         <td class="small col-reported" data-label="{{ t('housebook.reported') }}">{{ reported_pill(row, true) }}</td>
+        <td class="small col-more" data-label="{{ t('housebook.details') }}">
+          {% set facts_id = 'housebook-facts-' ~ row._guest_id %}
+          {% set full_name = ((row.first_name or '') ~ ' ' ~ (row.surname or '')) | trim %}
+          <button class="ui-btn ui-btn-quiet ui-btn-compact" type="button" popovertarget="{{ facts_id }}" aria-label="{{ t('housebook.details_for', name=full_name) }}">{{ t('housebook.details') }}</button>
+          <div id="{{ facts_id }}" class="card housebook-facts" popover>
+            <p><strong>{{ full_name }}</strong></p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.born') }}:</span> {{ row.birth_date | date_cz }}</p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.nationality') }}:</span> {{ nationality_text }}</p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.document') }}:</span> <span class="mono">{{ guest_identifier(row.doc_number, row._guest_id) }}{% if row.visa_number %}, {{ t('housebook.visa', number=guest_identifier(row.visa_number, row._guest_id)) }}{% endif %}</span></p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.residence') }}:</span> {{ res_parts | join(', ') or '—' }}</p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.purpose') }}:</span> {{ purpose_label(row._purpose_code, lang) or '—' }}</p>
+            <p class="small housebook-fact"><span class="muted">{{ t('housebook.signed') }}:</span> {% if row.signed == 'yes' %}<span class="pill p-ok">{{ t('housebook.signed_yes') }}</span>{% else %}<span class="pill p-warn">{{ t('housebook.signed_no') }}</span>{% endif %}</p>
+            <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" popovertarget="{{ facts_id }}" popovertargetaction="hide">{{ t('common.close') }}</button>
+          </div>
+        </td>
         <td class="nowrap row-actions" data-label="">{{ row_open('/guests/' ~ row._guest_id ~ '?return_to=/housebook') }}
           {{ row_menu_begin() }}
             <a class="row-menu-item" href="/guests/{{ row._guest_id }}?return_to=/housebook" role="menuitem">{{ t('common.edit') }}</a>
```

### Step 4. Run the new tests (includes the byte comparison)

```
cd /tmp/ubyhost-b12-worktree/App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b12 .venv/bin/python -m pytest tests/test_0970_register_readable_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```
Expected: `11 passed`, 0 skipped. `test_csv_export_is_byte_identical_to_the_recorded_baseline` is the export proof. A failure there means the statutory output changed: STOP at once, do not edit the test or the baseline.

### Step 5. Regression rows (run each; each ends with `| tail -30`)

All from `/tmp/ubyhost-b12-worktree/App` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b12`. The commands below are the test-map rows for host pages, copy and translations, the geometry row, and the export regressions. They were run clean on the finished patch (timings in brackets; use `timeout` 600000 ms on the long ones).

```
A) .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_wide_geometry_browser.py tests/test_0890_speed_pages_browser.py -q --tb=short -x -rs 2>&1 | tail -30      [about 4 min]
B) .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x -rs -k every_host_page 2>&1 | tail -30      [about 3.5 min; this is the UX gate lint, rule 10]
C) .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_copy_corrections.py tests/test_host_i18n.py -q --tb=short -x -rs 2>&1 | tail -30      [about 4 min]
D) .venv/bin/python -m pytest tests/test_housebook_presets_0889.py tests/test_stay_labels_cs.py tests/test_csv_safety.py tests/test_filed_by_hand.py tests/test_restriction.py tests/test_demo_stay_exclusion.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x -rs 2>&1 | tail -30
E) .venv/bin/python -m pytest tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30      [alone: it shares one database and fails when run after the geometry files, which is not caused by this change]
F) cd /tmp/ubyhost-b12-worktree && python3 scripts/context_lint.py 2>&1 | tail -30
```
Also run `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (no static file changed, must pass unchanged). Other `tests/test_host_*.py` files are left to CI; say so in the report.
A test fails: read the last 30 lines, fix it once if the cause is in this brief's files, rerun; fails again: STOP. Do not loosen an assertion and do not touch `layout_lint.js`.

### Step 6. Screenshots, review and report

The run writes screenshots to `/tmp/ubyhost-b12`: `register-{390,768,1024,1280}-{en,cs}.png` (closed) and `register-{390,768,1024,1280}-{en,cs}-open.png` (only for 1024 and 1280: the Details popover open). Open each of these once, do not retake: `register-390-en.png`, `register-390-cs.png`, `register-768-en.png`, `register-1280-en.png`, `register-1280-cs.png`, `register-1280-en-open.png`, `register-1280-cs-open.png` (seven in all; the other files exist for the tests). For each, write ONE line in the report: what you saw and pass or fail on these four points: (a) no sideways table scroll, (b) surname and reporting status readable together, (c) Details reachable by keyboard (proved by the test; say pass if the test passed), (d) English page has English labels.
What a pass looks like: 390 and 768 show stacked cards (surname + first name, dates, property, status line "Reported"/"Not yet sent"/"Rejected") with no table; 1280 shows columns Stay, Property, Guest, Reported, Details, then the row buttons, all inside the card; the open popover shows name, date of birth, citizenship as "Germany (DEU)" (cs: "Německo (DEU)"), document, residence, purpose ("Tourism" / "Turistika"), signed.
Then write `docs/tasks/0970-report.md` (600 tokens at most, per §9), set `Status: review` at the top of the brief file, commit `0970 step 6` (these two files only). Do not push, do not open a pull request, do not merge: hand the branch name to the owner.

## 5. Do not touch

- Any CSV, PDF or export code: `iter_housebook_csv_rows`, `housebook_csv`, `HOUSEBOOK_COLUMNS`, `registration_form_pdf`, `build_housebook_pdfs_zip`, `app/routes/exports.py`.
- Routes, access control, `app/routes/admin.py`, `app/templating.py`, `app/validation.py`, any `.css`/`.js` file, `tests/layout_lint.js`, `tests/static_versions.json`, `app/retention.py` (no new personal-data field is stored; the four keys re-read existing guest columns for display only).
- The phone card list (`.stays-phone`) and the archived-guests table in `housebook.html`.
- Hard rules: no new dependency, no secrets, no guest data printed, never push to main, no deploy.

## 6. Commands

Exactly the commands in Steps 2 to 5, each ending `2>&1 | tail -30`, run from `App/` with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b12`. Never the full suite.

## 7. Acceptance

- [ ] Step 4 prints `11 passed` and `-rs` shows 0 skipped.
- [ ] The CSV bytes after the change equal the baseline recorded in Step 2 (same test, passes).
- [ ] Table has six header cells (Stay, Property, Guest, Reported, Details, actions) and no sideways scroll at 1280 px; no page-level overflow at 390, 768, 1024, 1280.
- [ ] Surname and reporting status readable together at all four widths, English and Czech.
- [ ] Details reachable with Tab, opens with Enter, closes with Esc; no navigation to a guest page.
- [ ] English page has no Czech purpose or country text; Czech page shows Czech.
- [ ] Rows A to F of Step 5 green, 0 skipped in the browser files.
- [ ] Seven screenshots viewed once, one line each in the report (390 px for each changed page).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, or `git apply --check` fails;
- the byte comparison fails (statutory output changed);
- a test fails twice, or the layout lint reports any finding;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md; Steps 5A to 5C are the slowest, use `timeout` 600000);
- a new route, a new dependency, a CSS/JS change, or a change to any file outside §3 seems needed (a detail page of its own is a separate brief: STOP and say so);
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0970-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat 7b0355c..HEAD`), each command with the last 5 lines of its output, the baseline sha256 and byte count, §7 ticked, the seven screenshot lines, Deviations, Questions, owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/housebook.html`: the whole register markup; check the five columns, popover ids (`housebook-facts-<guest id>`) and that no stored field vanished (born, citizenship, document, visa, residence, purpose, signed all appear in the popover).
- `App/app/housebook.py`: four underscore keys only; confirm the CSV code path is untouched.
- `App/tests/test_0970_register_readable_browser.py`: the baseline is recorded outside the repo; reviewer re-runs Step 2 on the base commit if in doubt.
- The popover is a native `popover` element: supported in current Chromium, Safari 17+, Firefox 125+. Older browsers show nothing on Details; the guest page (row click, Open button) stays the fallback.

## Owner steps

1. In the worktree `/tmp/ubyhost-b12-worktree`, check that the report says all rows green.
2. Open `/housebook` on a populated test account at a desktop width and press Tab to a Details button, Enter to open, Esc to close.
3. Merge only with `scripts/merge-pr-on-green.sh` after a PR is opened by the owner; deploy is yours.
