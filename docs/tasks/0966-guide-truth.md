# 0966: Guide completion and empty questions tell the truth (B08, L02, L04)

Status: todo
Depends on: none (B03, B07 assumed merged upstream) | Base commit: 7b0355c45ccdd2557a28edfcfe228aa1dc766e36 | Branch: codex/0966-b08-guide-truth
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The Quick answers completion page says what is true. An all-skipped flow says no answers were added and the guide is not yet available to guests, and offers Back to the guide. Saved-but-unpublished, partly open and fully available guides each get their own message. The Questions page, when empty, shows one empty state with one next step.

## 2. Context

- Availability is the existing `guest_guide.progress(apartment_id)["live"]` (App/app/guest_guide.py, `progress`; the same gate `for_guest` uses). Saved answers are the non-empty `answered` list the route already builds from `guide_facts.lines`. No new flag, no AI or provider call; opening the page publishes nothing.
- States, computed once in `guide_quick_done` (App/app/routes/guest_guide.py): `none` (no answers), `saved` (answers, not live), `partial` (answers, live, cards still open), `live` (answers, live, nothing open).
- Copy lives in `_GUIDE_QUICK_STRINGS` in App/app/host_i18n.py (only `en` and `cs` exist there). `done_lede` and `no_answers` are replaced by `done_none`, `done_saved`, `done_partial`, `done_live`; no other file or test uses the old two.
- Questions page: App/app/templates/guest_questions.html (route `questions_index` is unchanged). It showed a summary value card plus an empty state with its body hidden behind a help tip. Now: no value card when empty, one `ui_empty` with visible body and one button.
- Rules: light mode only, no em dashes, one explanation in one place, no new dependency. "Back to the guide" is the existing key `guest_guide.quick.back`.
- Anchors that must exist before you patch (else STOP, section 8):
  - guest_guide_quick_done.html: `{{ ui_banner('neutral', t('guest_guide.quick.done_lede')) }}`
  - guest_guide.py: `open_cards=[r for r in rows if r["state"] in ("missing", "check")],`
  - guest_questions.html: `{% if not questions %}`
  - host_i18n.py: `"guest_guide.quick.done_lede": "Thank you. Guests now see`

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/guest_guide.py | edit | `guide_quick_done` passes `guide_state` |
| App/app/templates/guest_guide_quick_done.html | edit | state banner; answers section only when answered; no "Write the next card" when `none` |
| App/app/templates/guest_questions.html | edit | one empty state, no summary card when empty |
| App/app/host_i18n.py | edit | 4 keys added, 2 removed, en and cs |
| App/tests/test_quick_answers_browser.py | append | 2 tests, plus `guide_facts` in the import |

No other file may change. guest_guide.html and App/tests/static_versions.json stay untouched (no static file changes).

## 4. Steps

Work in the existing worktree /tmp/ubyhost-b08-worktree. If it is missing, STOP.

1. Link the venv and check the four anchors (each grep must print a line):
   ```
   cd /tmp/ubyhost-b08-worktree/App && ln -sfn /tmp/ubyhost-0958-worktree/App/.venv .venv
   grep -nF "{{ ui_banner('neutral', t('guest_guide.quick.done_lede')) }}" app/templates/guest_guide_quick_done.html | tail -3
   grep -nF 'open_cards=[r for r in rows if r["state"] in ("missing", "check")],' app/routes/guest_guide.py | tail -3
   grep -nF "{% if not questions %}" app/templates/guest_questions.html | tail -3
   grep -nF '"guest_guide.quick.done_lede": "Thank you. Guests now see' app/host_i18n.py | tail -3
   ```
2. Write the patch to /tmp/ubyhost-b08-0966.patch exactly as below, check it, apply it, commit:
   ```
   cat > /tmp/ubyhost-b08-0966.patch <<'PATCH_EOF'
diff --git a/App/app/host_i18n.py b/App/app/host_i18n.py
index b265a7d7..39db678c 100644
--- a/App/app/host_i18n.py
+++ b/App/app/host_i18n.py
@@ -10206,9 +10206,11 @@ _GUIDE_QUICK_STRINGS = {
         "guest_guide.quick.finish": "Save and finish",
         "guest_guide.quick.skip": "Skip this step",
         "guest_guide.quick.done_title": "Your guide",
-        "guest_guide.quick.done_lede": "Thank you. Guests now see these answers inside the right cards, and Leon can use them.",
+        "guest_guide.quick.done_none": "No answers were added, so the guide is not yet available to guests. Go back to answer a step or write a card.",
+        "guest_guide.quick.done_saved": "Your answers are saved. Guests cannot see them yet: the guide opens once the essential cards are written.",
+        "guest_guide.quick.done_partial": "Your answers are saved and guests can see them. Some cards still need your words.",
+        "guest_guide.quick.done_live": "Your answers are saved and guests can see them inside the right cards.",
         "guest_guide.quick.answers_title": "Your quick answers",
-        "guest_guide.quick.no_answers": "No answers yet. You can come back any time.",
         "guest_guide.quick.missing_title": "Still to write",
         "guest_guide.quick.missing_lede": "These cards still need a few words from you. The grey example in each field shows what guests find useful.",
         "guest_guide.quick.all_done": "Every card is answered. Nice work.",
@@ -10261,9 +10263,11 @@ _GUIDE_QUICK_STRINGS = {
         "guest_guide.quick.finish": "Uložit a dokončit",
         "guest_guide.quick.skip": "Tento krok přeskočit",
         "guest_guide.quick.done_title": "Váš průvodce",
-        "guest_guide.quick.done_lede": "Děkujeme. Hosté teď odpovědi uvidí ve správných kartách a Leon je může použít.",
+        "guest_guide.quick.done_none": "Nebyly přidány žádné odpovědi, takže průvodce zatím hosté nevidí. Vraťte se a odpovězte na krok nebo napište kartu.",
+        "guest_guide.quick.done_saved": "Odpovědi jsou uložené. Hosté je zatím nevidí: průvodce se otevře, až budou napsané základní karty.",
+        "guest_guide.quick.done_partial": "Odpovědi jsou uložené a hosté je vidí. Některé karty ještě potřebují vaše slova.",
+        "guest_guide.quick.done_live": "Odpovědi jsou uložené a hosté je vidí ve správných kartách.",
         "guest_guide.quick.answers_title": "Vaše rychlé odpovědi",
-        "guest_guide.quick.no_answers": "Zatím žádné odpovědi. Vrátit se můžete kdykoli.",
         "guest_guide.quick.missing_title": "Ještě dopsat",
         "guest_guide.quick.missing_lede": "Tyto karty ještě potřebují pár vašich slov. Šedý příklad v každém poli ukazuje, co hostům pomáhá.",
         "guest_guide.quick.all_done": "Všechny karty jsou vyřízené. Skvělá práce.",
diff --git a/App/app/routes/guest_guide.py b/App/app/routes/guest_guide.py
index 70e5c893..62e21611 100644
--- a/App/app/routes/guest_guide.py
+++ b/App/app/routes/guest_guide.py
@@ -258,10 +258,19 @@ def guide_quick_done(request: Request, apartment_id: int):
         (host_i18n.translate(lang, f"guest_guide.kind.{r['kind']}.title"), " ".join(lines[r["kind"]]))
         for r in rows if r["kind"] in lines
     ]
+    open_cards = [r for r in rows if r["state"] in ("missing", "check")]
+    progress = guest_guide.progress(apartment_id)
+    # 0966: what guests can see comes from progress["live"] (the same gate as for_guest).
+    if not answered:
+        guide_state = "none"
+    elif not progress["live"]:
+        guide_state = "saved"
+    else:
+        guide_state = "partial" if open_cards else "live"
     return _render(
         request, "guest_guide_quick_done.html", apartment=apartment, answered=answered,
-        open_cards=[r for r in rows if r["state"] in ("missing", "check")],
-        progress=guest_guide.progress(apartment_id), next_id=_next_open(apartment_id, 0),
+        open_cards=open_cards, guide_state=guide_state,
+        progress=progress, next_id=_next_open(apartment_id, 0),
         first_step=guide_facts.STEPS[0],
     )
 
diff --git a/App/app/templates/guest_guide_quick_done.html b/App/app/templates/guest_guide_quick_done.html
index 08d7dff1..b8fac2d8 100644
--- a/App/app/templates/guest_guide_quick_done.html
+++ b/App/app/templates/guest_guide_quick_done.html
@@ -14,16 +14,14 @@
 {% block primary_action %}{% endblock %}
 {% block body %}
 <div class="guide-page">
-<div class="head guide-hd"><div><a class="guide-back" href="{{ base_url }}">{{ t('guest_guide.title') }}</a><h1 class="big">{{ t('guest_guide.quick.done_title') }}</h1><p class="sub">{{ t('guest_guide.progress', answered=progress.answered, total=progress.cards) }}</p></div><div class="guide-acts"><a class="btn line" href="{{ base_url ~ '/quick/' ~ first_step }}">{{ t('guest_guide.quick.edit') }}</a>{% if next_id %}<a class="btn" href="{{ base_url ~ '/' ~ next_id }}">{{ t('guest_guide.quick.write') }}</a>{% else %}<a class="btn" href="{{ base_url }}">{{ t('guest_guide.quick.back') }}</a>{% endif %}</div></div>
-{{ ui_banner('neutral', t('guest_guide.quick.done_lede')) }}
-{% call ui_section(t('guest_guide.quick.answers_title'), id='quick-answers') %}
+<div class="head guide-hd"><div><a class="guide-back" href="{{ base_url }}">{{ t('guest_guide.title') }}</a><h1 class="big">{{ t('guest_guide.quick.done_title') }}</h1><p class="sub">{{ t('guest_guide.progress', answered=progress.answered, total=progress.cards) }}</p></div><div class="guide-acts"><a class="btn line" href="{{ base_url ~ '/quick/' ~ first_step }}">{{ t('guest_guide.quick.edit') }}</a>{% if next_id and guide_state != 'none' %}<a class="btn" href="{{ base_url ~ '/' ~ next_id }}">{{ t('guest_guide.quick.write') }}</a>{% else %}<a class="btn" href="{{ base_url }}">{{ t('guest_guide.quick.back') }}</a>{% endif %}</div></div>
+{{ ui_banner('attention' if guide_state in ('none', 'saved') else 'neutral', t('guest_guide.quick.done_' ~ guide_state)) }}
 {% if answered %}
+{% call ui_section(t('guest_guide.quick.answers_title'), id='quick-answers') %}
 {% set pairs = [] %}{% for title, text in answered %}{% set _ = pairs.append((title, text | e)) %}{% endfor %}
 {{ ui_facts(pairs) }}
-{% else %}
-<p class="ui-sub">{{ t('guest_guide.quick.no_answers') }}</p>
-{% endif %}
 {% endcall %}
+{% endif %}
 {% call ui_section(t('guest_guide.quick.missing_title'), id='quick-missing') %}
 {% if open_cards %}
 {{ help_tip('guide-quick-missing-help', t('guest_guide.quick.missing_lede')) }}
diff --git a/App/app/templates/guest_questions.html b/App/app/templates/guest_questions.html
index f429a77b..c7059d5a 100644
--- a/App/app/templates/guest_questions.html
+++ b/App/app/templates/guest_questions.html
@@ -13,10 +13,10 @@
 {% block body %}
 <div class="settings-lane">
 {% with href=base_url, title=t('guest_questions.title') %}{% include "partials/settings_back_header.html" %}{% endwith %}
-{% with label=t('guest_questions.title'), value=(t('guest_questions.open', n=open_count) if open_count else t('guest_questions.none_open')) %}{% include "partials/settings_value_card.html" %}{% endwith %}
 {% if not questions %}
-{{ ui_empty(t('guest_questions.empty.title'), '', t('guest_guide.title'), base_url, primary=false, tip=help_tip('guest-questions-empty', t('guest_questions.empty.body'))) }}
+{{ ui_empty(t('guest_questions.empty.title'), t('guest_questions.empty.body'), t('guest_guide.title'), base_url) }}
 {% else %}
+{% with label=t('guest_questions.title'), value=(t('guest_questions.open', n=open_count) if open_count else t('guest_questions.none_open')) %}{% include "partials/settings_value_card.html" %}{% endwith %}
 {{ ui_table_begin([(t('guest_questions.col.question'), ''), (t('guest_questions.col.state'), '')], label=t('guest_questions.title')) }}
 {% for q in questions %}
 {% set q_url = base_url ~ '/questions/' ~ q.id %}
diff --git a/App/tests/test_quick_answers_browser.py b/App/tests/test_quick_answers_browser.py
index 52b98a15..3deff247 100644
--- a/App/tests/test_quick_answers_browser.py
+++ b/App/tests/test_quick_answers_browser.py
@@ -10,7 +10,7 @@ from pathlib import Path
 
 from fastapi.testclient import TestClient
 
-from app import auth, db, guest_guide
+from app import auth, db, guest_guide, guide_facts
 from app.main import app
 from tests.conftest import login_as
 from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401
@@ -69,3 +69,108 @@ def test_the_chips_are_big_full_width_and_show_their_state(base):  # noqa: F811
         context.close()
         browser.close()
     assert db.query_one("SELECT value FROM guide_fact WHERE apartment_id = ? AND fact = 'pets'", (apt_id,))["value"] == "no"
+
+
+# ---- 0966: the completion message tells the truth about saved answers and guest availability ----
+STATE_TEXT = {
+    "none": ("No answers were added", "Nebyly přidány žádné odpovědi"),
+    "saved": ("Guests cannot see them yet", "Hosté je zatím nevidí"),
+    "partial": ("Some cards still need your words", "Některé karty ještě potřebují"),
+    "live": ("guests can see them inside the right cards", "hosté je vidí ve správných kartách"),
+}
+OVERFLOW = r"""() => {
+  const clipped = [...document.querySelectorAll('.ui-banner, .ui-banner *, [data-empty-state], [data-empty-state] *')]
+    .filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
+  return {sideways: document.documentElement.scrollWidth > window.innerWidth, clipped: clipped.length};
+}"""
+
+
+def _host(prefix):
+    db.init_db()
+    user = f"{prefix}-{secrets.token_hex(3)}"
+    owner = auth.create_account(f"{user}@example.test", "Truth Host", role="host", username=user)
+    apt_id = db.insert("apartment", {
+        "owner_user_id": owner, "internal_name": "Truth flat", "active": 1, "created_at": db.utcnow(),
+        "automation_mode": "manual",
+    })
+    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
+    client = TestClient(app)
+    login_as(client, user, url="/login?lang=en")
+    return apt_id, client
+
+
+def _fixture(apt_id, state):
+    """none: every step skipped. saved: answers, guide not live. partial: live, cards open. live: no card open."""
+    if state == "none":
+        for step in guide_facts.STEPS:
+            guide_facts.mark_seen(apt_id, step)
+        return
+    guide_facts.save_step(apt_id, "rules", {"pets": "no", "smoking": "no", "parties": "", "quiet_hours_from": "22:00", "quiet_hours_to": "07:00"})
+    if state == "saved":
+        return
+    for row in guest_guide.items(apt_id):
+        if state == "live" or row["kind"] in guest_guide.MUST_HAVE:
+            guest_guide.save(apt_id, row["id"], {"steps": f"How to {row['kind']}"})
+
+
+def test_completion_message_matches_each_state_without_http_browser(base):  # noqa: F811
+    for state, (en, cs) in STATE_TEXT.items():
+        apt_id, client = _host(f"truth-{state}")
+        _fixture(apt_id, state)
+        english = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en").text
+        czech = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=cs").text
+        assert en in english and cs in czech, state
+        assert "guest_guide." not in english and "guest_guide." not in czech
+        for other, (other_en, _cs) in STATE_TEXT.items():
+            if other != state:
+                assert other_en not in english, (state, other)
+    # all-skipped: an honest empty page, a way back, no promise, no "write the next card" push
+    apt_id, client = _host("truth-skip")
+    _fixture(apt_id, "none")
+    page = client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en").text
+    assert "Back to the guide" in page and "Change answers" in page
+    assert "Write the next card" not in page and 'id="quick-answers"' not in page
+    assert "Guests now see" not in page and "can see them" not in page
+    # the page only reads: nothing was published or changed by opening it
+    before = guest_guide.progress(apt_id)
+    client.get(f"/apartments/{apt_id}/guide/quick/done?lang=en")
+    assert guest_guide.progress(apt_id) == before and not before["live"]
+
+
+def test_completion_and_empty_questions_in_chromium(base):  # noqa: F811
+    SHOTS.mkdir(parents=True, exist_ok=True)
+    with sync_api.sync_playwright() as playwright:
+        browser = playwright.chromium.launch(**chromium_launch_kwargs())
+        for state, texts in STATE_TEXT.items():
+            apt_id, client = _host(f"truthb-{state}")
+            _fixture(apt_id, state)
+            for lang, expected in zip(("en", "cs"), texts):
+                for width in (390, 768, 1280):
+                    context = browser.new_context(viewport={"width": width, "height": 900})
+                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
+                    page = context.new_page()
+                    page.goto(f"{base}/apartments/{apt_id}/guide/quick/done?lang={lang}")
+                    assert expected in page.locator(".ui-banner").inner_text(), (state, lang, width)
+                    assert page.locator(".ui-banner").count() == 1
+                    probe = page.evaluate(OVERFLOW)
+                    assert not probe["sideways"] and probe["clipped"] == 0, (state, lang, width, probe)
+                    page.screenshot(path=str(SHOTS / f"0966-done-{state}-{lang}-{width}.png"), full_page=True)
+                    if state == "none":
+                        assert page.get_by_role("link", name="Back to the guide" if lang == "en" else "Zpět na průvodce").count() >= 1
+                    context.close()
+        apt_id, client = _host("truthb-questions")
+        for lang, title in (("en", "No questions yet"), ("cs", "Zatím žádné dotazy")):
+            for width in (390, 768, 1280):
+                context = browser.new_context(viewport={"width": width, "height": 900})
+                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
+                page = context.new_page()
+                page.goto(f"{base}/apartments/{apt_id}/guide/questions?lang={lang}")
+                assert page.locator("[data-empty-state]").count() == 1, (lang, width)
+                assert page.locator(".settings-value-card").count() == 0, (lang, width)
+                assert page.get_by_text(title).count() == 1, (lang, width)
+                assert page.locator("[data-empty-state] a.ui-btn").count() == 1, (lang, width)  # one next step
+                probe = page.evaluate(OVERFLOW)
+                assert not probe["sideways"] and probe["clipped"] == 0, (lang, width, probe)
+                page.screenshot(path=str(SHOTS / f"0966-questions-empty-{lang}-{width}.png"), full_page=True)
+                context.close()
+        browser.close()
PATCH_EOF
   cd /tmp/ubyhost-b08-worktree && git apply --check /tmp/ubyhost-b08-0966.patch 2>&1 | tail -30
   git apply /tmp/ubyhost-b08-0966.patch 2>&1 | tail -30
   git status --short | tail -10
   git add App && git commit -m "0966 step 1" 2>&1 | tail -3
   ```
   `git apply --check` failing: STOP. `git status` must list exactly the 5 files of section 3.
3. Run the commands of section 6, then take the screenshots check in section 7, then write the report.

## 5. Do not touch

Any other file. Not `guest_guide.html`, not `progress()` or `for_guest` (no change to who sees what), not static files, not the AI/Leon code. Hard rules: no publishing side effects, no provider calls, no new dependency, light mode only, never push, merge or touch main.

## 6. Commands

All from /tmp/ubyhost-b08-worktree/App. Export once: `export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b08`. Each ends `2>&1 | tail -30`. `-rs` shows skips: any skip is a failure.

```
.venv/bin/python -m pytest tests/test_quick_answers_browser.py tests/test_quick_answers.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_guest_guide*.py tests/test_guide.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30
cd /tmp/ubyhost-b08-worktree && git status --short | tail -10
```

Expected: all green with 0 skipped. The geometry and guest-guide tests can overwrite tracked screenshots under docs/tasks/. If `git status` shows any path other than the 5 files, run `git checkout -- <that path>` for it (never commit it). A test fails twice: STOP.

Browser coverage of the new test (already in the patch): fixtures all-skipped, saved, partial, live; EN and CS; 390, 768, 1280; banner text matches the state, exactly one banner, no sideways scroll, no clipped banner or empty-state text; the empty Questions page has exactly one `[data-empty-state]`, no `.settings-value-card`, one button. It writes 0966-done-<state>-<lang>-<width>.png and 0966-questions-empty-<lang>-<width>.png under /tmp/ubyhost-b08 (screenshots stay outside the repo).

## 7. Acceptance

- [ ] `git diff --stat 7b0355c4..HEAD` lists exactly the 5 files of section 3.
- [ ] All section 6 commands green, 0 skipped.
- [ ] Open and describe in the report (one line each): 0966-done-none-en-390.png (warning banner says no answers added and guide not yet available; buttons Change answers and Back to the guide; no "Write the next card"; no answers section), 0966-done-saved-cs-390.png, 0966-done-partial-en-768.png, 0966-done-live-en-1280.png, 0966-questions-empty-en-390.png and -cs-1280.png (one centred empty state, one button, no summary card above it). No clipped copy.
- [ ] Opening the completion page changes nothing (the new test checks `progress` before and after).
- [ ] No em dash in the diff: `git diff 7b0355c4..HEAD | grep -c '—'` prints 0.

## 8. Stop and ask

Stop, and write the report, if: an anchor is missing; `git apply --check` fails; a test fails twice; a skipped test appears; 25 tool calls or about 50k tokens are reached (report as `blocked`, see executor.md); a file outside section 3 needs a change; the live fixture does not reach the `live` state (do not edit `progress`; report it); a step is unclear; push, merge, secrets or deploy would be needed.

## 9. Report

Write docs/tasks/0966-report.md (600 tokens at most): git diff --stat, each command with its last 5 lines, section 7 ticked, the screenshot descriptions, Deviations, Questions, owner steps left (none expected). Set `Status: review` in this brief and commit report plus status as `0966 report`. Do not push or open a PR; hand that to the orchestrator.

## Risk list (for the reviewer)

- App/app/routes/guest_guide.py `guide_quick_done`: state logic. Edge not covered: a built-in card with `host`-only visibility still counts as "answered" though guests would not see that fact line.
- App/app/host_i18n.py: Czech wording of the four messages (owner should read once).
- Done page sub line still counts skipped cards as "answered" (existing `progress.answered`); out of scope.

## Owner steps

1. Review the PR the orchestrator opens; merge only with `scripts/merge-pr-on-green.sh`. Deploy is yours.
