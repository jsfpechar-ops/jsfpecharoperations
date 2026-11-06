# 0973: Leon setup hierarchy (labelled four-step progress, property line, readable terms)

Status: blocked (the shared help button covers the primary button at 390 and 768 px; see docs/tasks/0973-report.md)
Depends on: B03, B08, B14 (run on the base commit anyway; this brief touches none of their files) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0973-b15-leon-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Rebuild the Leon setup wizard head so it shows a labelled four-step progress (current and completed states, no empty numbered items), keeps the property name apart from the page title, and makes the activation step readable: the key terms visible, the rest expandable, the required agreement still visible. Back and Exit say what is kept.

## 2. Context

**Reproduction (orchestrator, base commit, test workspace, Chromium 390/768/1280, EN and CS; no terms accepted by a click, the AI and provider never called).** The owner's state reproduced. On `/apartments/<id>/leon/setup/switch_on` the progress `<ol class="setup-wizard-progress" aria-hidden="true">` holds four empty `<li>`. Its computed `list-style-type` is `decimal` and `display` is `block`, so the page shows an empty list numbered 1 to 4, then "0 of 4 done", then "Step 1 of 4: Switch on", then a small Exit button. The h1 is "Set up Leon for <property name>" and wraps over 4 lines at 390 px. Six warning bullets sit between the question and the agreement.

**Root cause.** `leon_setup/_layout.html` copied the markup of `setup_wizard/_layout.html` but not its root class `wiz-page`. Every `.wiz-page ...` rule in `App/app/static/app2.css` (lines 1284-1310 and 2541-2546: flex head, flex progress, card body, question icon) is therefore not applied. The v2 pages load `app2.css` only (not `host2.css`). The labelled `.fee-stepper` component exists in `app2.css` lines 1065-1072, scoped to `body.v2 .stay-fees-page`. This brief reuses it by wrapping the stepper in `stay-fees-page`, because no CSS file may change here. (Orchestrator note for the owner: a cleaner follow-up is to move those rules to a neutral `.wiz-stepper` class in app2.css.)

**Not changed:** the activation flow, the checkbox `#leon-terms` (`name="terms"`, `required`), the form `#leon-setup-on`, the `/guide#leon-terms` link, every route, `leon-setup.js`, `static_versions.json` (no static file changes, so no version bump), the legal wording (`leon_page.warn1` to `warn6`, `leon_page.accept`, version 2026-10-25 are only re-arranged, not edited).

**Draft behaviour (verified by reading `app/routes/leon_setup.py` and `guest_guide.py`).** Cards and imports are saved server side as the host works, so Back and Exit lose nothing there. The step 1 checkbox is not saved, and Leon stays off until the form is posted. The terms link now opens in a new tab so the ticked box is not lost.

Rules that apply: AGENTS.md hard rules 5 to 7 and 9 (light mode, 0 skipped browser tests, one 390 px screenshot per changed page, no sentence the button already says). Never tick or submit the terms checkbox in a script to get evidence; later steps in tests are reached by setting the sandbox DB flag, as the patch does. Never call the AI or provider.

Quoted anchors (each must be found verbatim in the base files before you apply; if not, STOP):

`App/app/templates/leon_setup/_layout.html`:
```
{% with href='/apartments/' ~ apartment.id ~ '/leon', title=t('leon_setup.title', name=apartment.internal_name) %}{% include "partials/settings_back_header.html" %}{% endwith %}
<div class="setup-wizard" data-leon-setup data-leon-setup-step="{{ step }}">
      <ol class="setup-wizard-progress" aria-hidden="true">
        <li class="is-{{ 'done' if s in done_steps else 'current' if s == step else 'todo' }}"></li>
      <p class="setup-wizard-done-count">{{ t('wizard.done_count', n=done_steps|length, total=total) }}</p>
```
`App/app/templates/leon_setup/switch_on.html`:
```
<h2 class="setup-wizard-section-title">{{ t('leon_page.warn_title') }}</h2>
<ul>{% for n in range(1, 7) %}<li>{{ t('leon_page.warn' ~ n) }}</li>{% endfor %}</ul>
  <label for="leon-terms">{{ t('leon_page.accept') }} <a href="/guide#leon-terms">{{ t('leon_page.terms_link') }}</a></label></div>
```
`App/app/host_i18n.py` (English block, once each): `        "leon_setup.done.back": "Back to the property",` and (Czech block, once): `        "leon_setup.done.back": "Zpět na ubytování",`
`App/app/host_vi_i18n.py` (once): `    "leon_setup.done.back": "Quay lại chỗ ở",`
`App/tests/test_0404_leon_setup_browser.py`: the file ends with the function `test_setup_wizard_in_a_browser` (last lines `    finally:` / `        context.close()`); the patch appends after it.

Result at 390 px (orchestrator run after the patch): head is the property name left and Exit right; below it the four labelled steps (Switch on, Import, Cards, Try; CS Start, Import, Karty, Test) with a numbered dot, a tick when done and a coloured bar on top; one line says what Exit keeps; the question card holds the lede, two key points, a closed "More to know" disclosure with the other four points, then the agreement checkbox and the single primary button. Screenshots from that run are in `/tmp/ubyhost-b15/0973-leon-setup/` on the orchestrator's machine only; yours are made in step 5.

Language note: the supported host languages are en, cs and vi (`host_i18n.LANGUAGES`); the patch adds the nine new keys to all three. Short labels are deliberately one word: at 390 px a longer Czech label broke mid-word.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/leon_setup/_layout.html | edit | `wiz-page` root, property line, labelled stepper, exit note, short heading |
| App/app/templates/leon_setup/switch_on.html | edit | key points visible, rest in a disclosure, terms link in a new tab |
| App/app/host_i18n.py | edit | 9 keys in en and cs |
| App/app/host_vi_i18n.py | edit | the same 9 keys in vi |
| App/tests/test_0404_leon_setup_browser.py | append | `test_setup_progress_and_terms_0973` (EN and CS, 390/768/1280) |

No other file may change. Read-only here: `cards.html`, `import.html`, `try.html`, `done.html` (they inherit the new head and need no edit), `leon-setup.js`, `static_versions.json`, all CSS.

## 4. Steps

1. Worktree: `/tmp/ubyhost-b15-worktree` on branch `codex/0973-b15-leon-setup` already exists. From it: `git status --short | tail -5` must show nothing but the brief. Then `ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv` if `App/.venv` is missing (it is gitignored).
2. Check every anchor in section 2 with `grep -n` (one call). Any miss: STOP.
3. Write the patch below to `/tmp/b15.patch` exactly (a quoted heredoc, `cat > /tmp/b15.patch <<'PATCH_EOF'` ... `PATCH_EOF`). Then `git apply --check /tmp/b15.patch && git apply /tmp/b15.patch && git diff --stat | tail -8`. Expected: 5 files, about 142 insertions, 13 deletions. If `--check` fails, STOP.
4. The reproduction is already recorded in section 2; do not revert the patch to re-run it. State in the report that you rely on it.
5. Run the commands in section 6. The new test writes screenshots to `/tmp/ubyhost-b15/0973-leon-setup/`. Open (Read) these and write one sentence per file in the report: `switch_on-en-390.png`, `switch_on-en-390-open.png`, `switch_on-cs-768.png`, `switch_on-en-1280.png`, `import-en-390.png`, `cards-cs-390.png`, `try-en-768.png`, `done-en-390.png`.
6. PASS/FAIL per width and language for each check in section 7 (UX gate). Never silence a finding. A visual problem you cannot fix inside section 3 files: STOP and report it.
7. The existing browser test rewrites the tracked PNGs in `docs/tasks/screenshots-0404/`. After the tests run `git checkout -- docs/tasks/screenshots-0404` so they are not part of the change.
8. Commit nothing unless asked; write the report (section 9).

### The patch

```diff
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..14ec2f84 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -9929,6 +9929,15 @@ _GUIDE_IMPORT_STRINGS = {
         "leon_setup.done.title": "Leon is ready",
         "leon_setup.done.text": "Guests can now ask Leon on the stay page and the QR guide page. Anything he does not know comes to you.",
         "leon_setup.done.back": "Back to the property",
+        "leon_setup.heading": "Set up Leon",
+        "leon_setup.short.switch_on": "Switch on",
+        "leon_setup.short.import": "Import",
+        "leon_setup.short.cards": "Cards",
+        "leon_setup.short.try": "Try",
+        "leon_setup.step_done": "(done)",
+        "leon_setup.exit_note.switch_on": "Leon stays off until you switch him on.",
+        "leon_setup.exit_note.later": "Saved cards and imports stay. Continue from the property's Leon page.",
+        "leon_setup.terms_more": "More to know before you switch Leon on",
         "leon_page.title": "Leon (AI)",
         "leon_page.what": "Leon is an optional AI chat for your guests. He answers their questions on the stay page and the QR guide page from your guide cards marked Done, and passes anything he does not know to you.",
         "leon_page.what_title": "What Leon does",
@@ -10030,6 +10039,15 @@ _GUIDE_IMPORT_STRINGS = {
         "leon_setup.done.title": "Leon je připravený",
         "leon_setup.done.text": "Hosté se teď mohou Leona ptát na stránce pobytu a na stránce průvodce z QR kódu. Co neví, přijde vám.",
         "leon_setup.done.back": "Zpět na ubytování",
+        "leon_setup.heading": "Nastavení Leona",
+        "leon_setup.short.switch_on": "Start",
+        "leon_setup.short.import": "Import",
+        "leon_setup.short.cards": "Karty",
+        "leon_setup.short.try": "Test",
+        "leon_setup.step_done": "(hotovo)",
+        "leon_setup.exit_note.switch_on": "Leon zůstane vypnutý, dokud ho nezapnete.",
+        "leon_setup.exit_note.later": "Uložené karty a importy zůstanou. Pokračujte na stránce Leon u ubytování.",
+        "leon_setup.terms_more": "Co ještě vědět, než Leona zapnete",
         "leon_page.title": "Leon (AI)",
         "leon_page.what": "Leon je volitelný AI chat pro vaše hosty. Odpovídá na jejich otázky na stránce pobytu a na stránce průvodce z QR kódu podle karet označených Hotovo a vše, co neví, předá vám.",
         "leon_page.what_title": "Co Leon dělá",
diff --git a/App/app/host_vi_i18n.py b/App/app/host_vi_i18n.py
index 28f23a46..68d06be7 100644
--- a/App/app/host_vi_i18n.py
+++ b/App/app/host_vi_i18n.py
@@ -248,6 +248,15 @@ STRINGS: Dict[str, str] = {
     "leon_setup.done.title": "Leon đã sẵn sàng",
     "leon_setup.done.text": "Khách giờ có thể hỏi Leon trên trang lưu trú và trang hướng dẫn qua mã QR. Điều gì Leon không biết sẽ được chuyển đến bạn.",
     "leon_setup.done.back": "Quay lại chỗ ở",
+    "leon_setup.heading": "Thiết lập Leon",
+    "leon_setup.short.switch_on": "Bật",
+    "leon_setup.short.import": "Nhập",
+    "leon_setup.short.cards": "Thẻ",
+    "leon_setup.short.try": "Thử",
+    "leon_setup.step_done": "(xong)",
+    "leon_setup.exit_note.switch_on": "Leon vẫn tắt cho đến khi bạn bật.",
+    "leon_setup.exit_note.later": "Các thẻ và phần nhập đã lưu vẫn còn. Tiếp tục từ trang Leon của chỗ nghỉ.",
+    "leon_setup.terms_more": "Cần biết thêm trước khi bật Leon",
     "leon_page.title": "Leon (AI)",
     "leon_page.what": "Leon là trợ lý AI tùy chọn cho khách của bạn. Anh ấy trả lời câu hỏi của khách trên trang lưu trú và trang hướng dẫn QR, dựa trên các thẻ hướng dẫn bạn đánh dấu Xong, và chuyển cho bạn những gì anh ấy không biết.",
     "leon_page.what_title": "Leon làm gì",
diff --git a/App/app/templates/leon_setup/_layout.html b/App/app/templates/leon_setup/_layout.html
index a14a73ec..1e6f5bcd 100644
--- a/App/app/templates/leon_setup/_layout.html
+++ b/App/app/templates/leon_setup/_layout.html
@@ -8,20 +8,24 @@
 {% block meta %}{% endblock %}
 {% block body %}
 <div class="settings-lane">
-{% with href='/apartments/' ~ apartment.id ~ '/leon', title=t('leon_setup.title', name=apartment.internal_name) %}{% include "partials/settings_back_header.html" %}{% endwith %}
-<div class="setup-wizard" data-leon-setup data-leon-setup-step="{{ step }}">
+{% with href='/apartments/' ~ apartment.id ~ '/leon', title=t('leon_setup.heading') %}{% include "partials/settings_back_header.html" %}{% endwith %}
+<div class="setup-wizard wiz-page" data-leon-setup data-leon-setup-step="{{ step }}">
   <div class="setup-wizard-head">
-    <div class="setup-wizard-meter">
-      <ol class="setup-wizard-progress" aria-hidden="true">
-        {% for s in steps %}
-        <li class="is-{{ 'done' if s in done_steps else 'current' if s == step else 'todo' }}"></li>
-        {% endfor %}
-      </ol>
-      <p class="setup-wizard-done-count">{{ t('wizard.done_count', n=done_steps|length, total=total) }}</p>
-      {% if number %}<div class="setup-wizard-count">{{ t('leon_setup.count', n=number, total=total, step=t('leon_setup.step.' ~ step)) }}</div>{% endif %}
-    </div>
+    <p class="ui-sub" data-leon-setup-property>{{ apartment.internal_name }}</p>
     <div class="setup-wizard-exit"><a class="ui-btn ui-btn-secondary" href="/apartments/{{ apartment.id }}">{{ t('wizard.exit') }}</a></div>
   </div>
+  <div class="setup-wizard-meter stay-fees-page">
+    <ol class="fee-stepper" data-leon-stepper aria-label="{% if number %}{{ t('leon_setup.count', n=number, total=total, step=t('leon_setup.step.' ~ step)) }}{% else %}{{ t('leon_setup.done.title') }}{% endif %}">
+      {% for s in steps %}
+      {% set s_state = 'done' if step == 'done' else 'current' if s == step else 'done' if s in done_steps else 'todo' %}
+      <li class="fee-stepper-item" data-state="{{ s_state }}"{% if s_state == 'current' %} aria-current="step"{% endif %}>
+        <span class="fee-stepper-dot" aria-hidden="true">{% if s_state == 'done' %}&#10003;{% else %}{{ loop.index }}{% endif %}</span>
+        <span class="fee-stepper-label">{{ t('leon_setup.short.' ~ s) }}{% if s_state == 'done' %}<span class="sr-only"> {{ t('leon_setup.step_done') }}</span>{% endif %}</span>
+      </li>
+      {% endfor %}
+    </ol>
+    {% if step != 'done' %}<p class="ui-sub" data-leon-exit-note>{{ t('leon_setup.exit_note.switch_on' if step == 'switch_on' else 'leon_setup.exit_note.later') }}</p>{% endif %}
+  </div>
   <div class="setup-wizard-body">
     {% set step_icons = {'switch_on': 'message-circle-question', 'import': 'download', 'cards': 'book-open', 'try': 'send'} %}
     {% set step_tones = {'switch_on': 'blue', 'import': 'teal', 'cards': 'purple', 'try': 'blue'} %}
diff --git a/App/app/templates/leon_setup/switch_on.html b/App/app/templates/leon_setup/switch_on.html
index 29e121ad..b57d874e 100644
--- a/App/app/templates/leon_setup/switch_on.html
+++ b/App/app/templates/leon_setup/switch_on.html
@@ -4,13 +4,17 @@
 {% if state == 'terms' %}{{ ui_banner('attention', t('leon_page.terms_updated')) }}{% endif %}
 {% if state in ('off', 'terms') %}
 <h2 class="setup-wizard-section-title">{{ t('leon_page.warn_title') }}</h2>
-<ul>{% for n in range(1, 7) %}<li>{{ t('leon_page.warn' ~ n) }}</li>{% endfor %}</ul>
+<ul data-leon-terms-key>{% for n in (1, 5) %}<li>{{ t('leon_page.warn' ~ n) }}</li>{% endfor %}</ul>
+<details class="setup-wizard-more" data-leon-terms-more>
+  <summary>{{ t('leon_setup.terms_more') }}</summary>
+  <ul>{% for n in (2, 3, 4, 6) %}<li>{{ t('leon_page.warn' ~ n) }}</li>{% endfor %}</ul>
+</details>
 <form method="post" action="/apartments/{{ apartment.id }}/leon" id="leon-setup-on">
 <input type="hidden" name="_csrf" value="{{ csrf_token }}">
 <input type="hidden" name="action" value="on">
 <input type="hidden" name="next" value="setup">
 <div class="checkline"><input type="checkbox" id="leon-terms" name="terms" value="1" required>
-  <label for="leon-terms">{{ t('leon_page.accept') }} <a href="/guide#leon-terms">{{ t('leon_page.terms_link') }}</a></label></div>
+  <label for="leon-terms">{{ t('leon_page.accept') }} <a href="/guide#leon-terms" target="_blank" rel="noopener">{{ t('leon_page.terms_link') }}</a></label></div>
 </form>
 {% else %}
 <div class="setup-wizard-instruction">{{ t('leon_setup.switch_on.already') }}</div>
diff --git a/App/tests/test_0404_leon_setup_browser.py b/App/tests/test_0404_leon_setup_browser.py
index 6637ab11..b23cc84e 100644
--- a/App/tests/test_0404_leon_setup_browser.py
+++ b/App/tests/test_0404_leon_setup_browser.py
@@ -130,3 +130,97 @@ def test_setup_wizard_in_a_browser(live_server, browser, host, base, leon_offere
         page.screenshot(path=str(OUT / "done-390.png"), full_page=True)
     finally:
         context.close()
+
+
+# --- 0973: the labelled four-step progress, the property line apart from the title, the terms ---
+import os  # noqa: E402
+import tempfile  # noqa: E402
+
+OUT_0973 = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "0973-leon-setup"
+LONG_NAME = "Penthouse Vinohrady with a very long property name above the river Vltava"
+STEPS_0973 = ("import", "cards", "try", "done")
+
+
+def _stepper(page):
+    return page.evaluate(
+        """() => {
+          const ol = document.querySelector('[data-leon-stepper]');
+          const items = [...ol.querySelectorAll(':scope > li')];
+          const box = ol.getBoundingClientRect();
+          return {
+            states: items.map(li => li.getAttribute('data-state')),
+            labels: items.map(li => li.querySelector('.fee-stepper-label').textContent.trim()),
+            current: items.filter(li => li.getAttribute('aria-current') === 'step').length,
+            listStyle: getComputedStyle(items[0]).listStyleType,
+            clipped: items.some(li => { const l = li.querySelector('.fee-stepper-label'); return l.scrollWidth > l.clientWidth + 1; }),
+            inView: box.left >= 0 && box.right <= window.innerWidth,
+            display: getComputedStyle(ol).display,
+            broken: items.some(li => {
+              const l = li.querySelector('.fee-stepper-label');
+              const name = l.firstChild.textContent.trim();
+              if (name.includes(' ')) return false;
+              const r = document.createRange(); r.selectNodeContents(l.firstChild);
+              return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size > 1;
+            }),
+          };
+        }"""
+    )
+
+
+@pytest.mark.parametrize("lang", ["en", "cs"])
+def test_setup_progress_and_terms_0973(live_server, browser, host, base, leon_offered, monkeypatch, lang):  # noqa: F811
+    OUT_0973.mkdir(parents=True, exist_ok=True)
+    apt = leon_offered
+    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (LONG_NAME, apt))
+    monkeypatch.setattr(guest_guide, "progress", _progress(False))
+    for width in (390, 768, 1280):
+        context = _context(browser, base, host, width, 900)
+        try:
+            page = context.new_page()
+            db.execute("UPDATE apartment SET leon_enabled = 0, leon_terms_version = NULL WHERE id = ?", (apt,))
+            page.goto(f"{base}/apartments/{apt}/leon/setup/switch_on?lang={lang}")
+            _settle(page)
+            st = _stepper(page)
+            assert st["states"] == ["current", "todo", "todo", "todo"], st
+            assert st["current"] == 1 and st["listStyle"] == "none" and st["display"] == "flex", st
+            assert all(st["labels"]) and len(st["labels"]) == 4 and not st["clipped"] and not st["broken"] and st["inView"], st
+            # The page title is the setup heading; the property name is its own line outside the heading.
+            assert page.locator("h1").inner_text().strip() not in ("", LONG_NAME)
+            assert LONG_NAME not in page.locator("h1").inner_text()
+            assert page.locator("[data-leon-setup-property]").inner_text().strip() == LONG_NAME
+            assert page.locator("[data-leon-setup-property]").evaluate("e => !e.closest('h1')")
+            assert page.locator("[data-leon-exit-note]").is_visible()
+            # One primary action; the agreement stays visible and required; the extra terms expand.
+            assert page.locator(".ui-btn-primary").count() == 1
+            assert page.locator("#leon-terms").is_visible() and page.locator("#leon-terms").get_attribute("required") is not None
+            more = page.locator("[data-leon-terms-more]")
+            assert more.evaluate("e => e.open") is False
+            page.screenshot(path=str(OUT_0973 / f"switch_on-{lang}-{width}.png"), full_page=True)
+            more.locator("summary").click()
+            assert more.evaluate("e => e.open") is True and more.locator("li").count() == 4
+            assert page.locator("#leon-terms").is_visible()
+            assert _no_overflow(page)
+            page.screenshot(path=str(OUT_0973 / f"switch_on-{lang}-{width}-open.png"), full_page=True)
+            # Nothing is accepted here: the box stays unticked and the form is not submitted.
+            assert not page.locator("#leon-terms").is_checked()
+
+            # The later steps are reached by setting the sandbox workspace's own flag, not by accepting terms.
+            db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?", (leon.LEON_TERMS_VERSION, apt))
+            for step in STEPS_0973:
+                page.goto(f"{base}/apartments/{apt}/leon/setup/{step}?lang={lang}")
+                _settle(page)
+                st = _stepper(page)
+                if step == "done":
+                    assert st["states"] == ["done"] * 4 and st["current"] == 0, st
+                else:
+                    at = STEPS_0973.index(step) + 1
+                    assert st["states"][at] == "current" and st["current"] == 1 and st["states"][0] == "done", (step, st)
+                    assert "current" not in st["states"][:at] + st["states"][at + 1:], (step, st)
+                assert all(st["labels"]) and not st["clipped"] and not st["broken"] and st["inView"] and st["listStyle"] == "none", (step, st)
+                assert _no_overflow(page)
+                assert page.locator("a.ui-btn-secondary", has_text=page.locator(".setup-wizard-exit a").inner_text()).count() >= 1
+                if step != "done":
+                    assert page.locator("[data-leon-exit-note]").is_visible()
+                page.screenshot(path=str(OUT_0973 / f"{step}-{lang}-{width}.png"), full_page=True)
+        finally:
+            context.close()
PATCH_EOF
```

(The last line of the patch block, `PATCH_EOF`, is the heredoc terminator and not part of the diff. Do not copy the code fences.)

**Orchestrator verification status:** after the patch these passed on the orchestrator run: `test_0404_leon_setup*.py`, `test_0405_leon_try.py`, `test_0396_leon_opt_in*.py`, `test_guide_coverage.py`, `test_static_versions.py`, `test_wp07_cache_heartbeats.py`, `test_leon.py` (95 passed). The group `test_layout_lint_browser.py test_host_geometry.py test_0710_v2_mockup_match_browser.py test_guide_browser.py` ran in one call that hit a 590 s timeout (no failure seen, no summary line): NOT verified, so run it as split in command 4.

## 5. Do not touch

- Any CSS, `static_versions.json`, `leon-setup.js`, `cards.html`, `import.html`, `try.html`, `done.html`, routes, `app/leon.py`, other languages' catalogs, the existing 0404 test function.
- Activation and legal flow: no change to who can switch Leon on, the terms version, the checkbox, the POST target or the redirect. The legal wording keys are only re-ordered in the view.
- No AI or provider call. Never tick or submit `#leon-terms` yourself outside what the patch's test does (it only unticked-asserts). No push, merge, PR, deploy.

## 6. Commands

All from `/tmp/ubyhost-b15-worktree/App`, each ending `| tail -30`. Set once per command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b15`.

1. New and existing Leon setup browser test (expect `3 passed`, 0 skipped):
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b15 .venv/bin/python -m pytest tests/test_0404_leon_setup_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
2. Leon rows (expect all pass):
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b15 .venv/bin/python -m pytest tests/test_0404_leon_setup.py tests/test_0405_leon_try.py tests/test_0396_leon_opt_in.py tests/test_0396_leon_opt_in_browser.py tests/test_leon.py tests/test_guide_coverage.py -q --tb=short -x -rs 2>&1 | tail -30`
3. Static and cache row (no static file changed, expect pass):
   `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`
4. Host, geometry, guide and v2 rows (browser, 0 skipped; slow, run each file group in its own call, `timeout 500`):
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b15 timeout 500 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30`
   `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b15 timeout 500 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_guide_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
5. `cd /tmp/ubyhost-b15-worktree && git checkout -- docs/tasks/screenshots-0404 && git status --short | tail -10` (expect only the 5 files of section 3).
6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

If the layout lint or the v2 mockup test fails on a Leon setup page, STOP and report the finding (do not edit CSS, do not silence it). A failure in an unrelated page that also fails on the base commit: report it as pre-existing with the test name.

## 7. Acceptance (UX gate: pass or fail per item, per width 390/768/1280 and per language EN/CS)

- [ ] No empty numbered list: the stepper has 4 items, each with text; `list-style` is `none` (the new test asserts it).
- [ ] The current step is marked (`aria-current="step"`, filled dot); completed steps show a tick; on `done` all four are complete.
- [ ] Progress visible at all widths, no label clipped, no label broken mid-word (test asserts `clipped`/`broken` false), nothing wider than the viewport.
- [ ] H1 is "Set up Leon" / "Nastavení Leona"; the property name is its own line outside the H1 and wraps (a 70-character name used).
- [ ] One primary button (`.ui-btn-primary` count 1 on switch_on); the question "Do you want Leon to answer your guests?" is the card heading.
- [ ] Two key points visible, four more inside the closed disclosure, the disclosure opens; the checkbox stays visible and `required`; the terms link still reaches `/guide#leon-terms` (new tab).
- [ ] Exit is a clearly labelled secondary button; the line under the stepper says what is kept (step 1: Leon stays off; later steps: saved cards and imports stay).
- [ ] One 390 px screenshot per changed page (`switch_on`, `import`, `cards`, `try`, `done`) opened and described in the report.
- [ ] Commands 1 to 6 green, 0 skipped. `git status` shows only the 5 files.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in section 2 is not found, or `git apply --check` fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a screenshot shows clipping, a mid-word break, a hidden stepper or overflow that needs CSS or a file outside section 3;
- a file outside section 3 needs a change, or section 5 would be touched;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0973-report.md` (600 tokens at most) and set `Status: review` in this file. It has: 1. `git diff --stat` (5 files); 2. each command with the last 5 lines of output; 3. section 7 ticked per width and language, one sentence per screenshot opened; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/leon_setup/_layout.html`: adds `wiz-page` (this restyles all four step pages and `done`: card body, max width 720 px) and reuses `.fee-stepper` through a `stay-fees-page` wrapper. Check that the wrapper's other rules (`.ui-btn` min-height 44 px only inside it) touch nothing else, and decide if a neutral CSS class should replace it.
- `App/app/templates/leon_setup/switch_on.html`: the six warnings are split 2 visible and 4 in a disclosure; the legal copy is unchanged. A lawyer-minded reviewer should confirm that splitting is acceptable next to an unchanged checkbox text.
- `host_i18n.py` and `host_vi_i18n.py`: 9 new keys; the old keys `leon_setup.count` (now the stepper's aria-label) and `wizard.done_count` (no longer used here) remain.

## Owner steps

1. Open the pull request when the reviewer says so, wait for the green checks, then merge with `scripts/merge-pr-on-green.sh`.
2. Deploy yourself when you want it live. On the sandbox workspace open a property, Leon, Set up, and look at the four steps. Do not tick the terms unless you really want Leon on.
