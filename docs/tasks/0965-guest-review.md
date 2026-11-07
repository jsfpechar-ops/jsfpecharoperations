# 0965: Simplify the guest review and the legal acknowledgement (B07: G02, G03, G04)

Status: review (spacing guards fixed in step 10; all checks green, 0 skipped; see docs/tasks/0965-report.md)
Depends on: B01 / 0979 (branch `codex/0959-guest-draft-language`, tip `89772982`; its review decision may still be open, this brief is built on that tip) | Base commit: 89772982 | Branch: codex/0965-b07-guest-review
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the guest signature step the review, the legal fold and the acknowledgement become one calm surface: label / value / one aligned Edit action per fact, a single divider before the legal part, a checked acknowledgement that looks done (green, never the red error look), a short save action ("Save person") with the person progress shown apart, a quiet Back and enough bottom clearance for the sticky action. Legal text, the meaning of the acknowledgement, the signature payload and the filing data do not change.

Not in scope: any other batch, host pages, the step wizard logic, `_legal_notice.html`, the legal wording, the form POST fields, `routes/guest.py`, filing, schema, dependencies.

## 2. Context

Rules: AGENTS.md hard rules 1, 2, 3, 6, 7, 9. Light mode only. Guest rule: bump the `?v=` key of each changed static file in every template that references it. Never print guest data in the report; the test data below is synthetic.

Findings (from the review report):
- G02: after ticking the acknowledgement the whole row kept a red outline and pink fill (it is the coral brand colour from `.checkline:has(input:checked)`). Fix: neutral until ticked, then quietly green; red only after an attempted submit with the box empty; a visible focus ring that is neither.
- G03: the long label "Save and continue to the next person" wrapped; the sticky action covered review/legal content; Back was as big as the primary action. Fix: short label, person progress as a line above, Back as a quiet text action, scroll clearance for the sticky bar.
- G04: review rows wrapped into a ragged stack, "Change" links dropped to separate lines, and the legal notice added a second rounded frame inside the step card. Fix: one fact-row pattern, one surface (the step's own `.g-card`), a divider.

Decisions already taken (do not reopen):
1. The Edit action keeps the existing key `review_edit` (its text is "Change" in English; existing tests read `data-edit-label="Change"`).
2. The save label keeps the key `save_continue_next` and gets a shorter value in all six guest languages (en, cs, de, es, fr in `App/app/i18n.py`, uk in `App/app/guest_uk_i18n.py`). The person progress reuses the existing key `person_progress` (all six languages already have it). No new key.
3. Red for the acknowledgement is set by `.is-invalid` (added by `signature.js` on the browser's `invalid` event, removed when ticked) or by the server's own `.err` inside `.legal-ack`. The visible error text for an attempted submit is the browser's own bubble; the server error text is unchanged.
4. Cache keys: `guest.css` and `signature.js` get key `20261105-0965a` in `App/app/templates/guest/base.html` and `App/app/templates/_signature_script.html`. Those two templates are not in the allowlist of the batch plan but the cache-key rule and `test_static_versions.py` require them; they are in section 3.
5. The birth-date row missing from the 390 px Czech review (seen in 0979, cause never found, code identical to base) IS covered by this batch because every row is rebuilt here. It is an explicit acceptance item (section 7): the test asserts the row exists with value `01.01.1980` at 390, 768 and 1280, in English and Czech. Hypothesis, unverified: a sticky bar covered the row in a full-page screenshot. If the test finds the row really absent from the DOM, STOP (section 8); do not fix the grouping code.

### Current anchors (each must be found verbatim before its step, else STOP)

`App/app/templates/guest/form.html`:
```
    <div class="g-review" data-wizard-review
         data-edit-label="{{ t('review_edit') }}" hidden>
      <dl class="g-summary-list g-review-list"></dl>
    {% include "guest/_legal_notice.html" %}
    <button class="g-btn" type="submit">
      {{ t(save_action_key) }}
```
`App/app/templates/guest/_legal_notice.html` (read only, do not edit; the CSS flattens it): `<div class="g-card g-legal-notice" id="legal-notice">`, `<details class="g-legal-text">`, `<div class="g-field legal-ack">`, `<label class="checkline" for="legal_ack">`.

`App/app/static/signature.js`: `dd.appendChild(document.createTextNode(row.value));`, `list.appendChild(dt);`, `function focusFirstError() {`, `initGuestReview();` (inside `DOMContentLoaded`).

`App/app/static/guest.css`: `.g-review-list { margin-bottom: 0; row-gap: 12px; }`, `.g-legal-notice .checkline span { font-size: 14px; line-height: 1.5; }`, and in the `@media (max-width: 560px)` block `[data-guest-step] > .g-btn[type="submit"] {` followed by `position: sticky;` and `bottom: 12px;`.

`App/app/i18n.py` / `guest_uk_i18n.py`: the six `"save_continue_next": "..."` lines (old values are in the patch).

`App/tests/test_guest_browser_e2e.py`: ends with `test_0979_discard_warning_cancel_keeps_draft` (954 lines); the patch appends after its last line. Helpers it uses and must find: `def _seed(`, `class Guest:`, `def pick_country`, `def sign(self)`, `def next(self)`, `def step(self)`.

Structure facts the CSS relies on (do not change): the signature step is a `.g-card[data-guest-step]` holding `.g-review`, `.g-legal-notice`, the submit button and (appended by `signature.js`) `.g-wizard-nav` with the Back button, in that order.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/guest/form.html | edit | person progress line above the save button |
| App/app/i18n.py | edit | `save_continue_next` shorter in en, cs, de, es, fr |
| App/app/guest_uk_i18n.py | edit | `save_continue_next` shorter in uk |
| App/app/static/guest.css | edit | fact rows, flattened legal part, neutral/green/red acknowledgement, quiet Back, sticky clearance |
| App/app/static/signature.js | edit | review rows as label/value/Edit, `.is-invalid` handling for the acknowledgement |
| App/app/templates/guest/base.html | edit | `?v=` key of guest.css and signature.js |
| App/app/templates/_signature_script.html | edit | `?v=` key of signature.js |
| App/tests/static_versions.json | edit | written by the script in step 5 |
| App/tests/test_guest_browser_e2e.py | edit | append 0965 tests only |
| docs/tasks/0965-report.md | create | the report |

No other file may change. Screenshots go to `/tmp/ubyhost-b07` only, never into the repo.

## 4. Steps

This file is long (about 800 lines) because the exact patches are in the Appendix at the end. A hook blocks whole-file reads over 350 lines: read this file in ranges of 150 lines or fewer, and NEVER read the Appendix; the commands below extract each patch with `awk` (markers `PATCH-pN-BEGIN` / `PATCH-pN-END`) and apply it with `git apply` untouched.

Work in `/tmp/ubyhost-b07-worktree` (branch `codex/0965-b07-guest-review`, already created from `89772982`). Each step: check the anchors with `grep -nF`, apply, run its command, commit `0965 step N`. Every command ends with `2>&1 | tail -30`.

### Step 0. Base and environment (one command)

```
cd /tmp/ubyhost-b07-worktree && git rev-parse --short=8 HEAD && git status --short | head -5 && ln -sfn /tmp/ubyhost-0958-worktree/App/.venv App/.venv && App/.venv/bin/python -c "import playwright; print('playwright ok')" 2>&1 | tail -30
```
Expected: `89772982`, no changed files, `playwright ok`. If `HEAD` is not `89772982` and is not a descendant of it that only touches `docs/`, STOP.

### Step 1. Template and the shorter save label

Anchors: the form.html lines above, and `grep -nF '"save_continue_next"' App/app/i18n.py App/app/guest_uk_i18n.py` (6 hits). Apply, then check and commit:
```
cd /tmp/ubyhost-b07-worktree && F=docs/tasks/0965-guest-review.md; awk '/^PATCH-p1-BEGIN$/{f=1;next}/^PATCH-p1-END$/{f=0}f' $F > /tmp/0965-p1.patch && git apply --check /tmp/0965-p1.patch && git apply /tmp/0965-p1.patch
git diff --stat | tail -5 && cd App && .venv/bin/python -m pytest tests/test_guest_navigation.py -q --tb=short -x -k "review_list or submit_registration or save_continue" 2>&1 | tail -30 && cd .. && git add -A App/app && git commit -q -m "0965 step 1" -m "Shorter save label in six languages, person progress line." -m "Co-authored-by: Codex <noreply@openai.com>"
```
(`git apply` is run from the repo root; the patch paths start with `App/`.)

### Step 2. CSS

Anchors: the three guest.css lines above. Apply and commit:
```
cd /tmp/ubyhost-b07-worktree && F=docs/tasks/0965-guest-review.md; awk '/^PATCH-p2-BEGIN$/{f=1;next}/^PATCH-p2-END$/{f=0}f' $F > /tmp/0965-p2.patch && git apply --check /tmp/0965-p2.patch && git apply /tmp/0965-p2.patch
git diff --stat | tail -5 && git add -A App/app && git commit -q -m "0965 step 2" -m "Fact rows, one surface, neutral acknowledgement, quiet Back, sticky clearance." -m "Co-authored-by: Codex <noreply@openai.com>"
```

### Step 3. signature.js

Anchors: the four signature.js lines above. Apply, syntax-check, commit:
```
cd /tmp/ubyhost-b07-worktree && F=docs/tasks/0965-guest-review.md; awk '/^PATCH-p3-BEGIN$/{f=1;next}/^PATCH-p3-END$/{f=0}f' $F > /tmp/0965-p3.patch && git apply --check /tmp/0965-p3.patch && git apply /tmp/0965-p3.patch
node --check App/app/static/signature.js && git diff --stat | tail -5 && git add -A App/app && git commit -q -m "0965 step 3" -m "Review rows and acknowledgement error state." -m "Co-authored-by: Codex <noreply@openai.com>"
```
If `node` is missing, skip `node --check` (the browser tests cover it).

### Step 4. Cache keys and manifest (one command)

```
cd /tmp/ubyhost-b07-worktree/App && sed -i 's/guest.css?v=20261105-0959b/guest.css?v=20261105-0965a/; s/signature.js?v=20261105-0959b/signature.js?v=20261105-0965a/' app/templates/guest/base.html app/templates/_signature_script.html && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30 && git diff --stat | tail -8 && .venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30 && git add -A app tests && git commit -q -m "0965 step 4" -m "Cache keys 20261105-0965a and manifest." -m "Co-authored-by: Codex <noreply@openai.com>"
```
Expected diff: base.html (2 lines), `_signature_script.html` (1 line), `static_versions.json` (guest.css and signature.js only). Anything else changed: STOP.

### Step 5. Tests (append only)

Anchor: `grep -c "def test_0979" App/tests/test_guest_browser_e2e.py` is 3, and the file ends at line 954. Apply and commit:
```
cd /tmp/ubyhost-b07-worktree && F=docs/tasks/0965-guest-review.md; awk '/^PATCH-p5-BEGIN$/{f=1;next}/^PATCH-p5-END$/{f=0}f' $F > /tmp/0965-p5.patch && git apply --check /tmp/0965-p5.patch && git apply /tmp/0965-p5.patch
python3 -m py_compile App/tests/test_guest_browser_e2e.py && git diff --stat | tail -5 && git add -A App/tests && git commit -q -m "0965 step 5" -m "Browser tests for review, acknowledgement, sticky bar, Edit." -m "Co-authored-by: Codex <noreply@openai.com>"
```

### Step 6. Run the 0965 tests, then the guest rows

```
cd /tmp/ubyhost-b07-worktree/App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b07 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q --tb=short -x -rs -k 0965 2>&1 | tail -30
```
Expected: `19 passed`, 0 skipped. A failure: read the last 30 lines, fix once inside section 3 files (CSS or JS only; never loosen a test threshold or delete an assertion), rerun; a second failure is a STOP. A failed `birth_date` assertion in the rows test is STOP (decision 5).

Then the guest baseline, and the lint:
```
cd /tmp/ubyhost-b07-worktree/App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b07 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
cd /tmp/ubyhost-b07-worktree && python3 scripts/context_lint.py 2>&1 | tail -30 && git diff --check 2>&1 | tail -30
```
Expected: all pass, 0 skipped. If a test other than the 0965 ones fails because it reads the old label or the old review markup, STOP and report the test name (do not edit other tests).

### Step 7. Look at the screenshots (once each, do not retake)

Files in `/tmp/ubyhost-b07` are named `0965-<lang>-<width>-<name>.png`. Open exactly these and write one sentence per file in the report (what you saw, not "ok"):
1. `0965-en-390-review-legal-closed.png` and `0965-cs-390-review-legal-closed.png`: five rows each (name, birth date, nationality, document, address), label above value, Edit at the same right edge, long name/address wrap inside the row, no frame around the legal line, one divider; the Czech birth-date row is visible.
2. `0965-en-390-review-legal-open.png`: legal text open inside the same card; no second rounded border.
3. `0965-en-390-ack-attempted-invalid.png`: red row after the blocked submit.
4. `0965-en-390-ack-checked-legal-open.png` and `0965-cs-390-ack-checked-legal-open.png`: green, no red or pink anywhere on the row.
5. `0965-en-390-ack-focus-empty.png` and `0965-en-390-ack-focus-checked.png`: a dark focus ring is visible.
6. `0965-en-390-bottom-legal-open.png` and `0965-cs-390-bottom-legal-closed.png`: the action sits below the acknowledgement, text not covered, Back is a small text link under it.
7. `0965-en-768-review-legal-closed.png`, `0965-cs-1280-review-legal-closed.png`: rows aligned, nothing clipped.
8. `0965-en-390-saved.png`: the saved strip shows, no error colour.
If anything looks wrong (overlap, clipped value, red on a ticked row, a second frame), say so in Deviations and STOP; do not call it passed.

### Step 8. Report

Write `docs/tasks/0965-report.md` (section 9), set Status in this file to `review`, commit `0965 report` with the trailer `Co-authored-by: Codex <noreply@openai.com>`. No push, no PR.

## 5. Do not touch

`App/app/templates/guest/_legal_notice.html` and every legal key, `routes/guest.py`, `App/app/static/app*.css`, host templates, other tests, `docs/` other than the report and this file's Status, `.env`, secrets, servers, deploy. The signature value, `legal_ack` field name and value, form action and POST fields stay as they are. No new dependency, no new i18n key, no tracking.

## 6. Commands

All in section 4. Summary, from `App/`, each ending `2>&1 | tail -30`:
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b07 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q --tb=short -x -rs -k 0965` (19 passed, 0 skipped)
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b07 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_host_geometry.py -q --tb=short -x -rs` (0 skipped)
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x`
- from the repo root: `python3 scripts/context_lint.py | tail -30`, `git diff --check | tail -30`

## 7. Acceptance

- [x] Review: five fact rows at 390, 768 and 1280, English and Czech, long names and addresses wrap inside the row, no sideways scroll, Edit right edges align (test measured).
- [x] The birth-date row is present at 390 in Czech and English with value `01.01.1980` (decision 5).
- [x] One surface: no nested `.g-card` frame around the legal part, one 1 px divider between review and legal (test measured, legal open and closed).
- [x] Acknowledgement: unchecked neutral, checked green, focus ring visible and not red, red only after the blocked submit (and cleared by ticking); `legal_ack` value and legal text unchanged.
- [x] Save label is the short value in all six languages, one line, with `Person 1 of 3` (translated) as a separate line; Back is a quiet text action.
- [x] The sticky action never overlaps the last fact row, the legal text or the Tab-focused control; `scroll-padding-bottom` is at least 96 px at 390 (test measured).
- [x] Every Edit returns to the right step, focus lands on the field, every typed value and the signature are kept, the review is the same afterwards.
- [x] Final submission with synthetic data saves in the test database (manual mode, no filing); the saved strip appears.
- [x] Step 4 diff touches only the two cache keys and two manifest entries; `git diff --stat 89772982` lists only section 3 files.
- [x] Screenshots viewed (step 7), one described sentence each in the report.

## 8. Stop and ask

Stop, and write the report, if:
- an anchor is not found verbatim, or `git apply` fails (do not edit the patch by hand);
- HEAD is not `89772982` at the start;
- a test fails twice, or the birth-date row is absent from the DOM;
- a test outside the 0965 tests fails because of the changed label or markup;
- you reach 25 tool calls or about 50k tokens (report `blocked`, `Done: steps 1 to k. Left: steps k+1 to n.`, see executor.md);
- a file outside section 3 needs a change, or section 5 would be touched, or a new dependency or i18n key seems needed;
- a screenshot shows overlap, clipping, a red ticked row or a second frame;
- you need push, merge, secrets, SSH or deploy (hand it to the owner).

## 9. Report

Write `docs/tasks/0965-report.md` (600 tokens at most): 1. `git diff --stat 89772982`. 2. Each command with the last 5 lines of output, and the skipped count. 3. Section 7 ticked. 4. Screenshot notes (step 7, one sentence each, no guest data). 5. Deviations. 6. Questions. 7. Owner steps left. Then Status `review`.

## Risk list (for the reviewer)

Read the diff of: `guest.css` (the `[data-guest-step] > .g-legal-notice` block, the `.legal-ack` colours, the sticky block in the 560 px media query), `signature.js` (`initLegalAck`, the row builder in `initGuestReview`), `form.html` (the `.g-save-note` line). The tests were written without being run: check that no threshold was loosened.

## Owner steps

1. Nothing to do until the review passes. After the orchestrator's review, merge only with `scripts/merge-pr-on-green.sh`; deploy is manual.


## Appendix: exact patches (do not read; applied by the awk commands in section 4)

### Patch 1: i18n and form.html

```diff
PATCH-p1-BEGIN
diff --git a/App/app/guest_uk_i18n.py b/App/app/guest_uk_i18n.py
index 9fde8830..a38450ed 100644
--- a/App/app/guest_uk_i18n.py
+++ b/App/app/guest_uk_i18n.py
@@ -240,7 +240,7 @@ STRINGS: Dict[str, str] = {
     "previous_step": "Назад",
     "guest_save_changes": "Зберегти зміни",
     "guest_save_details": "Зберегти дані",
-    "save_continue_next": "Зберегти й перейти до наступної особи",
+    "save_continue_next": "Зберегти особу",
     "submit_registration": "Надіслати реєстрацію",
     "person_saved": "Попередню особу збережено.",
     "add_person": "Додати особу",
diff --git a/App/app/i18n.py b/App/app/i18n.py
index 57fa8aa2..505b3f45 100644
--- a/App/app/i18n.py
+++ b/App/app/i18n.py
@@ -272,7 +272,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "previous_step": "Back",
         "guest_save_changes": "Save changes",
         "guest_save_details": "Save details",
-        "save_continue_next": "Save and continue to the next person",
+        "save_continue_next": "Save person",
         "submit_registration": "Submit registration",
         "person_saved": "Previous guest saved.",
         "add_person": "Add a person",
@@ -991,7 +991,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "previous_step": "Zpět",
         "guest_save_changes": "Uložit změny",
         "guest_save_details": "Uložit údaje",
-        "save_continue_next": "Uložit a pokračovat k další osobě",
+        "save_continue_next": "Uložit osobu",
         "submit_registration": "Odeslat registraci",
         "person_saved": "Předchozí osoba je uložená.",
         "add_person": "Přidat osobu",
@@ -1668,7 +1668,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "previous_step": "Zurück",
         "guest_save_changes": "Änderungen speichern",
         "guest_save_details": "Angaben speichern",
-        "save_continue_next": "Speichern und mit der nächsten Person fortfahren",
+        "save_continue_next": "Person speichern",
         "submit_registration": "Registrierung absenden",
         "person_saved": "Vorherige Person gespeichert.",
         "add_person": "Person hinzufügen",
@@ -2160,7 +2160,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "previous_step": "Atrás",
         "guest_save_changes": "Guardar cambios",
         "guest_save_details": "Guardar datos",
-        "save_continue_next": "Guardar y continuar con la siguiente persona",
+        "save_continue_next": "Guardar persona",
         "submit_registration": "Enviar el registro",
         "person_saved": "Persona anterior guardada.",
         "add_person": "Añadir persona",
@@ -2652,7 +2652,7 @@ STRINGS: Dict[str, Dict[str, str]] = {
         "previous_step": "Retour",
         "guest_save_changes": "Enregistrer les modifications",
         "guest_save_details": "Enregistrer les informations",
-        "save_continue_next": "Enregistrer et continuer avec la personne suivante",
+        "save_continue_next": "Enregistrer la personne",
         "submit_registration": "Envoyer l’inscription",
         "person_saved": "Personne précédente enregistrée.",
         "add_person": "Ajouter une personne",
diff --git a/App/app/templates/guest/form.html b/App/app/templates/guest/form.html
index 410cfdb3..ca65090a 100644
--- a/App/app/templates/guest/form.html
+++ b/App/app/templates/guest/form.html
@@ -311,6 +311,9 @@
 
     {% if fee_estimate %}{% include "guest/_fee_estimate.html" %}{% endif %}
 
+    {% if person_number and expected_people %}
+      <p class="g-save-note">{{ t('person_progress', current=person_number, total=expected_people) }}</p>
+    {% endif %}
     <button class="g-btn" type="submit">
       {{ t(save_action_key) }}
     </button>
PATCH-p1-END
```

### Patch 2: guest.css

```diff
PATCH-p2-BEGIN
diff --git a/App/app/static/guest.css b/App/app/static/guest.css
index 5e8e5443..b8ab2dc5 100644
--- a/App/app/static/guest.css
+++ b/App/app/static/guest.css
@@ -1220,6 +1220,70 @@ details.g-head-help > .g-intro { margin: 10px 0 0; }
 }
 .g-legal-notice .checkline span { font-size: 14px; line-height: 1.5; }
 
+/* 0965: on the signature step the review, the legal fold and the
+   acknowledgement share the step's one card. The legal notice loses its own
+   frame and is set off by a single divider. */
+[data-guest-step] > .g-legal-notice {
+  border: 0;
+  border-top: 1px solid var(--g-line);
+  border-radius: 0;
+  background: none;
+  box-shadow: none;
+  margin: 18px 0 16px;
+  padding: 4px 0 0;
+}
+[data-guest-step] > .g-review[hidden] + .g-legal-notice {
+  border-top: 0;
+  margin-top: 16px;
+  padding-top: 0;
+}
+[data-guest-step] > .g-legal-notice .g-legal-text > summary {
+  border-top: 0;
+  margin-top: 0;
+  padding-top: 0;
+}
+/* The acknowledgement is neutral until ticked, then quietly positive (green,
+   the colour reserved for "done"). Red belongs to an attempted submit with the
+   box empty (.is-invalid from signature.js, or the server's own .err). */
+.g-legal-notice .legal-ack { border-top: 0; padding-top: 0; }
+.g-legal-notice .legal-ack .checkline {
+  background: var(--g-surface);
+  border-color: var(--g-line-2);
+}
+.g-legal-notice .legal-ack .checkline input[type=checkbox] { accent-color: var(--g-ok); }
+.g-legal-notice .legal-ack:not(.is-invalid) .checkline:has(input:checked) {
+  background: var(--g-ok-soft);
+  border-color: color-mix(in srgb, var(--g-ok) 45%, var(--g-line));
+}
+.g-legal-notice .legal-ack .checkline:has(input:focus-visible) {
+  outline: 2px solid var(--g-ink);
+  outline-offset: 2px;
+}
+.g-legal-notice .legal-ack.is-invalid .checkline,
+.g-legal-notice .legal-ack:has(> .err) .checkline {
+  background: var(--g-bad-soft);
+  border-color: var(--g-bad);
+}
+
+/* The person progress sits above the action, so the button needs only a verb. */
+.g-save-note { margin: 14px 0 8px; color: var(--g-muted); font-size: 13.5px; font-weight: 600; text-align: center; }
+/* Back on the step that submits: a quiet text action under the primary one. */
+[data-guest-step] > .g-btn[type="submit"] ~ .g-wizard-nav { margin-top: 6px; justify-content: center; }
+[data-guest-step] > .g-btn[type="submit"] ~ .g-wizard-nav .g-btn.secondary {
+  flex: 0 0 auto;
+  width: auto;
+  min-height: 44px;
+  padding: 8px 14px;
+  background: none;
+  border-color: transparent;
+  color: var(--g-muted);
+  font-size: 14.5px;
+  font-weight: 600;
+  text-decoration: underline;
+  text-underline-offset: 2px;
+}
+[data-guest-step] > .g-btn[type="submit"] ~ .g-wizard-nav .g-btn.secondary:hover { background: none; color: var(--g-ink); }
+
 /* --- footer / misc ----------------------------------------------------- */
 
 .g-foot { font-size: 12.5px; color: var(--g-muted); text-align: center; margin-top: 26px; }
@@ -1300,8 +1364,20 @@ details.g-summary > .g-summary-body { padding: 16px 20px 18px; }
 
 /* Last look at the answers before they are locked. The "Change" control is a
    quiet text button so it never competes with "Submit my details" below. */
-.g-review-list { margin-bottom: 0; row-gap: 12px; }
-.g-review-list dd { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
+.g-review-list { display: block; margin-bottom: 0; }
+/* 0965: one fact per row: the label above, the value and one aligned Edit
+   action on the line below, a hairline between rows. */
+.g-review-row { padding: 10px 0; border-top: 1px solid var(--g-line); }
+.g-review-row:first-child { border-top: 0; padding-top: 0; }
+.g-review-row dt { margin: 0 0 2px; color: var(--g-muted); font-size: 13px; font-weight: 600; }
+.g-review-row dd {
+  display: grid;
+  grid-template-columns: minmax(0, 1fr) auto;
+  align-items: center;
+  gap: 12px;
+  margin: 0;
+}
+.g-review-value { min-width: 0; overflow-wrap: anywhere; font-size: 16px; line-height: 1.4; }
 /* 0896: 12 px or more between the signature pad's Clear button and the review title */
 .g-review { margin-top: 18px; }
 .g-review-change {
@@ -1358,9 +1434,14 @@ details.g-summary > .g-summary-body { padding: 16px 20px 18px; }
 /* The submit button is the whole point of the page; on a phone it should
    never be the thing you have to scroll to find. */
 @media (max-width: 560px) {
+  /* 0965: the sticky action is about 52 px plus its 12 px offset and the
+     home-indicator inset. Anything focused or scrolled to is kept clear of
+     it, and the page ends with the same room, so no text, error or control
+     is left underneath. */
+  html { scroll-padding-bottom: calc(96px + env(safe-area-inset-bottom, 0px)); }
   [data-guest-step] > .g-btn[type="submit"] {
     position: sticky;
-    bottom: 12px;
+    bottom: calc(12px + env(safe-area-inset-bottom, 0px));
     box-shadow: 0 1px 2px rgba(22, 25, 27, 0.1), 0 10px 28px rgba(22, 25, 27, 0.2);
   }
 }
PATCH-p2-END
```

### Patch 3: signature.js

```diff
PATCH-p3-BEGIN
diff --git a/App/app/static/signature.js b/App/app/static/signature.js
index f3bba49a..9ecd5aa6 100644
--- a/App/app/static/signature.js
+++ b/App/app/static/signature.js
@@ -373,10 +373,17 @@ function initSignature() {
       list.textContent = "";
       if (!rows.length) { card.hidden = true; return; }
       rows.forEach(function (row) {
+        // One row per fact: the label above, the value and its Edit action
+        // on one line below. A div around a dt/dd pair is valid in a dl.
+        var item = document.createElement("div");
+        item.className = "g-review-row";
         var dt = document.createElement("dt");
         dt.textContent = row.label;
         var dd = document.createElement("dd");
-        dd.appendChild(document.createTextNode(row.value));
+        var value = document.createElement("span");
+        value.className = "g-review-value";
+        value.textContent = row.value;
+        dd.appendChild(value);
         var button = document.createElement("button");
         button.type = "button";
         button.className = "g-review-change";
@@ -389,8 +396,9 @@ function initSignature() {
           row.target.scrollIntoView({ behavior: "smooth", block: "center" });
         });
         dd.appendChild(button);
-        list.appendChild(dt);
-        list.appendChild(dd);
+        item.appendChild(dt);
+        item.appendChild(dd);
+        list.appendChild(item);
       });
       card.hidden = false;
     }
@@ -399,6 +407,25 @@ function initSignature() {
     build();
   }
 
+  /* A ticked acknowledgement is a finished answer, not a mistake. The red
+     look is kept for an attempted submit with the box still empty: the browser
+     fires "invalid" on it then, and ticking the box clears the mark again. */
+  function initLegalAck() {
+    var box = document.getElementById("legal_ack");
+    if (!box) return;
+    var wrap = box.closest(".legal-ack");
+    if (!wrap) return;
+    box.addEventListener("invalid", function () {
+      wrap.classList.add("is-invalid");
+      box.setAttribute("aria-invalid", "true");
+    });
+    box.addEventListener("change", function () {
+      if (!box.checked) return;
+      wrap.classList.remove("is-invalid");
+      box.removeAttribute("aria-invalid");
+    });
+  }
+
   function focusFirstError() {
     var first = document.querySelector(".g-field .bad, .g-sign .err:not(:empty)");
     if (!first) return;
@@ -717,6 +744,7 @@ function initSignature() {
     initCheckinRail();
     initErrorSummary();
     initGuestReview();
+    initLegalAck();
     focusFirstError();
   });
 })();
PATCH-p3-END
```

### Patch 5: tests

```diff
PATCH-p5-BEGIN
diff --git a/App/tests/test_guest_browser_e2e.py b/App/tests/test_guest_browser_e2e.py
index e8ad7548..c549fd15 100644
--- a/App/tests/test_guest_browser_e2e.py
+++ b/App/tests/test_guest_browser_e2e.py
@@ -952,3 +952,335 @@ def test_0979_discard_warning_cancel_keeps_draft(live_server, browser, monkeypat
         assert page.is_checked("#legal_ack")
     finally:
         page.close()
+
+
+# --- 0965 (B07): the review, the legal acknowledgement and the save action ---
+
+_B07_LONG = {
+    "first": "Maximiliana-Alexandra",
+    "surname": "Hohenzollern-Sigmaringen-Vondrackova",
+    "doc": "SYN0965LONGDOCUMENT27",
+    "street": "Nábřeží Svobodného Československa 1234/56",
+    "city": "Dolní Lhota u Dlouhého Města nad Labem",
+}
+
+_B07_GEOMETRY_JS = r"""
+() => {
+  const R = el => el.getBoundingClientRect();
+  const step = document.querySelector('[data-guest-step]:not([hidden])');
+  const rows = [...step.querySelectorAll('.g-review-row')].map(row => {
+    const dt = row.querySelector('dt'), value = row.querySelector('.g-review-value');
+    const edit = row.querySelector('.g-review-change'), r = R(row);
+    return {
+      label: dt.textContent.trim(), value: value.textContent.trim(),
+      dtBottom: R(dt).bottom, dtLeft: R(dt).left,
+      valueTop: R(value).top, valueLeft: R(value).left, valueRight: R(value).right,
+      editLeft: R(edit).left, editRight: R(edit).right, editH: R(edit).height,
+      rowRight: r.right,
+    };
+  });
+  const legal = step.querySelector('.g-legal-notice'), review = step.querySelector('.g-review');
+  const cs = getComputedStyle(legal);
+  return {
+    rows,
+    overflow: document.documentElement.scrollWidth - window.innerWidth,
+    legalBorders: [cs.borderLeftWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderTopWidth],
+    legalRadius: cs.borderTopLeftRadius, legalShadow: cs.boxShadow,
+    reviewBottom: R(review).bottom, legalTop: R(legal).top,
+    nestedCards: [...step.querySelectorAll('.g-card')].filter(c => !c.classList.contains('g-legal-notice')).length,
+  };
+}
+"""
+
+_B07_ACK_JS = r"""
+() => {
+  const rgb = value => {
+    const nums = (value.match(/-?[\d.]+/g) || []).map(Number);
+    return value.startsWith('color(') ? nums.slice(0, 3).map(n => n * 255) : nums.slice(0, 3);
+  };
+  const wrap = document.querySelector('.legal-ack');
+  const cs = getComputedStyle(document.querySelector('#legal_ack').closest('.checkline'));
+  return {
+    border: rgb(cs.borderTopColor), background: rgb(cs.backgroundColor),
+    outlineStyle: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth), outline: rgb(cs.outlineColor),
+    invalidClass: wrap.classList.contains('is-invalid'),
+    ariaInvalid: document.querySelector('#legal_ack').getAttribute('aria-invalid'),
+  };
+}
+"""
+
+_B07_STICKY_JS = r"""
+() => {
+  const R = el => el.getBoundingClientRect();
+  const step = document.querySelector('[data-guest-step]:not([hidden])');
+  const btn = step.querySelector(':scope > .g-btn[type=submit]');
+  const rows = [...step.querySelectorAll('.g-review-row')];
+  const legal = [...step.querySelectorAll('.g-legal-text > summary, .g-legal-text[open] p, .legal-ack .checkline')];
+  const active = document.activeElement;
+  return {
+    position: getComputedStyle(btn).position, btnTop: R(btn).top, btnBottom: R(btn).bottom,
+    btnHeight: R(btn).height, viewport: window.innerHeight,
+    pad: parseFloat(getComputedStyle(document.documentElement).scrollPaddingBottom) || 0,
+    lastRowBottom: R(rows[rows.length - 1]).bottom,
+    legalBottoms: legal.map(e => R(e).bottom),
+    activeTop: R(active).top, activeBottom: R(active).bottom, activeId: active.id || '',
+  };
+}
+"""
+
+
+def _b07_redder(color, margin):
+    return color[0] - max(color[1], color[2]) >= margin
+
+
+def _b07_greener(color, margin):
+    return color[1] - max(color[0], color[2]) >= margin
+
+
+def _b07_shot(page, lang, width, name):
+    shots = os.environ.get("UBYHOST_SHOTS_DIR")
+    if not shots:
+        return
+    Path(shots).mkdir(parents=True, exist_ok=True)
+    page.screenshot(path=str(Path(shots) / f"0965-{lang}-{width}-{name}.png"), full_page=False)
+
+
+def _b07_open_review(live_server, browser, monkeypatch, token, lang, width):
+    """Person 1 of 3, long synthetic answers, on the signature step with a drawn signature."""
+    from app import config
+
+    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
+    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
+    stay = _seed(token)
+    db.update("reservation", stay, {"expected_guests_override": 3})
+    page = browser.new_page(viewport={"width": width, "height": 812})
+    guest = Guest(page, width, lang)
+    page.goto(f"{live_server}/l/{token}/{stay}/new?lang=en")
+    page.fill("#first_name", _B07_LONG["first"])
+    page.fill("#surname", _B07_LONG["surname"])
+    page.click("#birth_date")
+    page.keyboard.type("01011980")
+    guest.pick_country("nationality", "DEU")
+    page.fill("#doc_number", _B07_LONG["doc"])
+    guest.next()
+    page.fill("#res_street", _B07_LONG["street"])
+    page.fill("#res_city", _B07_LONG["city"])
+    guest.next()
+    if lang != "en":
+        # The language menu keeps the draft and the step (0979).
+        page.locator("[data-lang-menu] summary").click()
+        with page.expect_navigation():
+            page.locator(f'[data-lang-draft][lang="{lang}"]').click()
+        assert page.get_attribute("html", "lang") == lang
+    assert guest.step() == i18n.translator(lang)("signature")
+    guest.sign()
+    return page, guest, stay
+
+
+@pytest.mark.parametrize(("lang", "width"), [(l, w) for l in ("en", "cs") for w in (390, 768, 1280)])
+def test_0965_review_is_one_surface_with_aligned_fact_rows(live_server, browser, monkeypatch, lang, width):
+    """G04 + G03: one card, label / value / aligned Edit rows, a divider before the legal part,
+    a short save action with the person progress apart, a quiet Back."""
+    t = i18n.translator(lang)
+    page, guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-rows-{lang}-{width}", lang, width)
+    try:
+        page.locator(".g-review").scroll_into_view_if_needed()
+        geo = page.evaluate(_B07_GEOMETRY_JS)
+        rows = geo["rows"]
+        assert len(rows) == 5, [r["label"] for r in rows]
+        # The birth-date row missing at 390 px in Czech (seen in 0979) is an acceptance item here.
+        birth = [r for r in rows if t("birth_date").strip() in r["label"]]
+        assert len(birth) == 1 and birth[0]["value"] == "01.01.1980", rows
+        assert rows[0]["value"] == f"{_B07_LONG['first']} {_B07_LONG['surname']}"
+        assert rows[-1]["value"].startswith(_B07_LONG["street"]) and _B07_LONG["city"] in rows[-1]["value"]
+        assert geo["overflow"] <= 1, f"the page scrolls sideways by {geo['overflow']}px"
+        for row in rows:
+            assert row["dtBottom"] <= row["valueTop"] + 1, f"label is not above the value: {row['label']}"
+            assert abs(row["dtLeft"] - row["valueLeft"]) <= 1, row["label"]
+            assert row["valueRight"] <= row["editLeft"] + 0.5, f"value runs under Edit: {row['label']}"
+            assert row["editRight"] <= row["rowRight"] + 0.5, row["label"]
+            assert row["editH"] >= 44, row["label"]
+        edges = [row["editRight"] for row in rows]
+        assert max(edges) - min(edges) <= 1, f"Edit actions are not aligned: {edges}"
+        # One outer surface: the legal part has no frame of its own, only a divider.
+        assert geo["legalBorders"][:3] == ["0px", "0px", "0px"], geo["legalBorders"]
+        assert geo["legalBorders"][3] == "1px", geo["legalBorders"]
+        assert geo["legalRadius"] == "0px" and geo["legalShadow"] == "none"
+        assert geo["reviewBottom"] <= geo["legalTop"] + 1
+        assert geo["nestedCards"] == 0, "a card sits inside the step card"
+        _b07_shot(page, lang, width, "review-legal-closed")
+
+        # The short action and the person progress, apart.
+        submit = page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]")
+        assert submit.inner_text().strip() == t("save_continue_next")
+        assert submit.evaluate("el => el.getBoundingClientRect().height") <= 64, "the action wraps"
+        note = page.locator("[data-guest-step]:not([hidden]) > .g-save-note")
+        assert note.inner_text().strip() == t("person_progress", current=1, total=3)
+        back = page.locator("[data-guest-step]:not([hidden]) .g-wizard-nav .g-btn.secondary")
+        assert back.count() == 1
+        sizes = page.evaluate(
+            "([b, s]) => [document.querySelector(b), document.querySelector(s)].map(e => e.getBoundingClientRect().width)",
+            ["[data-guest-step]:not([hidden]) .g-wizard-nav .g-btn.secondary",
+             "[data-guest-step]:not([hidden]) > .g-btn[type=submit]"],
+        )
+        assert sizes[0] < sizes[1] * 0.6, f"Back is as wide as the action: {sizes}"
+        assert back.evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
+        assert back.evaluate("el => el.getBoundingClientRect().height") >= 44
+
+        # Legal open: still no frame, nothing sideways.
+        page.locator(".g-legal-text > summary").click()
+        assert page.locator(".g-legal-text").evaluate("el => el.open")
+        assert page.evaluate(_B07_GEOMETRY_JS)["overflow"] <= 1
+        _b07_shot(page, lang, width, "review-legal-open")
+    finally:
+        page.close()
+
+
+@pytest.mark.parametrize(("lang", "width"), [(l, w) for l in ("en", "cs") for w in (390, 768, 1280)])
+def test_0965_acknowledgement_is_neutral_then_positive_and_red_only_after_a_failed_submit(
+    live_server, browser, monkeypatch, lang, width
+):
+    """G02: unchecked neutral, focus ring visible, attempted-invalid red, checked green, never red."""
+    page, _guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-ack-{lang}-{width}", lang, width)
+    try:
+        page.locator("#legal_ack").scroll_into_view_if_needed()
+        idle = page.evaluate(_B07_ACK_JS)
+        assert not idle["invalidClass"] and idle["ariaInvalid"] is None
+        assert not _b07_redder(idle["border"], 30) and not _b07_greener(idle["border"], 8), idle
+        assert not _b07_redder(idle["background"], 5) and not _b07_greener(idle["background"], 5), idle
+
+        # Attempted submit with the box empty: the browser blocks it, the row turns red.
+        page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]").click()
+        assert "/save" not in page.url
+        bad = page.evaluate(_B07_ACK_JS)
+        assert bad["invalidClass"] and bad["ariaInvalid"] == "true", bad
+        assert _b07_redder(bad["border"], 30) and _b07_redder(bad["background"], 5), bad
+        _b07_shot(page, lang, width, "ack-attempted-invalid")
+
+        # Ticked: the error look is gone and the row is quietly positive.
+        page.check("#legal_ack")
+        page.mouse.move(2, 2)
+        ok = page.evaluate(_B07_ACK_JS)
+        assert not ok["invalidClass"] and ok["ariaInvalid"] is None, ok
+        assert _b07_greener(ok["border"], 8) and _b07_greener(ok["background"], 5), ok
+        assert not _b07_redder(ok["border"], 30) and not _b07_redder(ok["background"], 5), ok
+        page.locator(".g-legal-text > summary").click()
+        assert page.evaluate(_B07_ACK_JS)["border"] == ok["border"], "opening the legal text changed the tick"
+        _b07_shot(page, lang, width, "ack-checked-legal-open")
+
+        # Keyboard focus: a visible ring that is not the error colour, on a ticked and an empty box.
+        for ticked in (True, False):
+            if not ticked:
+                page.uncheck("#legal_ack")
+            page.focus(".g-review-change")
+            for _ in range(24):
+                page.keyboard.press("Tab")
+                if page.evaluate("() => document.activeElement.id") == "legal_ack":
+                    break
+            assert page.evaluate("() => document.activeElement.id") == "legal_ack"
+            ring = page.evaluate(_B07_ACK_JS)
+            assert ring["outlineStyle"] != "none" and ring["outlineWidth"] >= 2, ring
+            assert not _b07_redder(ring["outline"], 30), ring
+            if ticked:
+                assert not _b07_redder(ring["border"], 30), ring
+            _b07_shot(page, lang, width, f"ack-focus-{'checked' if ticked else 'empty'}")
+        page.check("#legal_ack")
+
+        # Success: the same synthetic data saves (disposable test database, manual mode, no filing).
+        page.locator("[data-guest-step]:not([hidden]) > .g-btn[type=submit]").click()
+        page.wait_for_load_state()
+        assert "/save" not in page.url, page.inner_text(".g-err") if page.locator(".g-err").count() else page.url
+        strip = page.locator(".g-saved-strip")
+        assert strip.count() == 1 and i18n.translator(lang)("person_saved") in strip.inner_text()
+        _b07_shot(page, lang, width, "saved")
+    finally:
+        page.close()
+
+
+@pytest.mark.parametrize(("lang", "width"), [("en", 390), ("cs", 390), ("en", 768), ("en", 1280)])
+def test_0965_sticky_action_never_covers_review_legal_text_or_focus(live_server, browser, monkeypatch, lang, width):
+    """G03: measured with getBoundingClientRect at the bottom of the page and after Tab."""
+    page, _guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-sticky-{lang}-{width}", lang, width)
+    try:
+        for legal_open in (False, True):
+            if legal_open:
+                page.locator(".g-legal-text > summary").click()
+            page.evaluate("() => window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
+            page.wait_for_timeout(250)
+            m = page.evaluate(_B07_STICKY_JS)
+            if width <= 560:
+                assert m["position"] == "sticky", m
+                assert m["pad"] >= 96, f"no scroll padding for the sticky action: {m['pad']}"
+            assert m["btnBottom"] <= m["viewport"] + 1, "the action is cut off at the bottom"
+            assert m["lastRowBottom"] <= m["btnTop"] + 1 or m["lastRowBottom"] < 0, "the action covers the last fact row"
+            for bottom in m["legalBottoms"]:
+                assert bottom <= m["btnTop"] + 1, f"the action covers legal text (legal_open={legal_open}): {m}"
+            _b07_shot(page, lang, width, f"bottom-legal-{'open' if legal_open else 'closed'}")
+        # Tab from the top of the review to the acknowledgement: the focused control stays clear of the bar.
+        page.evaluate("() => document.querySelector('.g-review').scrollIntoView({block: 'start', behavior: 'instant'})")
+        page.focus(".g-review-change")
+        seen = []
+        for _ in range(24):
+            page.keyboard.press("Tab")
+            page.wait_for_timeout(60)
+            m = page.evaluate(_B07_STICKY_JS)
+            seen.append(m["activeId"])
+            overlap = m["activeTop"] < m["btnBottom"] and m["activeBottom"] > m["btnTop"]
+            assert not overlap, f"the sticky action covers the focused control {m['activeId']!r}: {m}"
+            if m["activeId"] == "legal_ack":
+                break
+        assert seen[-1] == "legal_ack", seen
+    finally:
+        page.close()
+
+
+@pytest.mark.parametrize("lang", ["en", "cs"])
+def test_0965_every_edit_returns_to_its_step_and_keeps_the_data(live_server, browser, monkeypatch, lang):
+    """Edit from the review lands on the owning step, focus on the field, nothing typed is lost."""
+    t = i18n.translator(lang)
+    page, guest, _stay = _b07_open_review(live_server, browser, monkeypatch, f"b07-edit-{lang}", lang, 390)
+    try:
+        signature = page.eval_on_selector("#signature", "e => e.value")
+        assert signature.startswith("data:image/png")
+        before = page.evaluate("() => [...document.querySelectorAll('.g-review-row')].map(r => r.textContent)")
+        owners = [t("your_details")] * 4 + [t("residence_title")]
+        focus_ids = ["first_name", "birth_date", "", "doc_number", "res_street"]
+        assert len(before) == 5
+        for index in range(5):
+            page.locator(".g-review-change").nth(index).scroll_into_view_if_needed()
+            page.locator(".g-review-change").nth(index).click()
+            page.wait_for_timeout(900)
+            assert guest.step() == owners[index], (index, guest.step())
+            if focus_ids[index]:
+                assert page.evaluate("() => document.activeElement.id") == focus_ids[index], index
+            assert page.input_value("#first_name") == _B07_LONG["first"]
+            assert page.input_value("#surname") == _B07_LONG["surname"]
+            assert page.input_value("#birth_date") == "01.01.1980"
+            assert page.input_value("#nationality") == "DEU"
+            assert page.input_value("#doc_number") == _B07_LONG["doc"]
+            assert page.input_value("#res_street") == _B07_LONG["street"]
+            assert page.input_value("#res_city") == _B07_LONG["city"]
+            assert page.eval_on_selector("#signature", "e => e.value") == signature
+            while guest.step() != t("signature"):
+                guest.next()
+            assert page.evaluate("() => [...document.querySelectorAll('.g-review-row')].map(r => r.textContent)") == before
+    finally:
+        page.close()
+
+
+def test_0965_shortened_save_action_exists_in_all_six_guest_languages():
+    """The one action key is short in every language and no longer says "continue to the next person"."""
+    old = {
+        "en": "Save and continue to the next person",
+        "cs": "Uložit a pokračovat k další osobě",
+        "de": "Speichern und mit der nächsten Person fortfahren",
+        "es": "Guardar y continuar con la siguiente persona",
+        "fr": "Enregistrer et continuer avec la personne suivante",
+        "uk": "Зберегти й перейти до наступної особи",
+    }
+    assert set(old) == set(i18n.LANGUAGES)
+    for lang, previous in old.items():
+        label = i18n.STRINGS[lang]["save_continue_next"]
+        assert label and label != previous, lang
+        assert len(label) <= 26, (lang, label)
+    assert len({i18n.STRINGS[lang]["save_continue_next"] for lang in old}) == 6
PATCH-p5-END
```
