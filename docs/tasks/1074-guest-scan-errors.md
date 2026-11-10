# 1074: Guest form scan (primary button, feedback, smaller photo, nationality prompt) and a date-error example

Status: todo
Tier: B | Depends on: none | Base commit: 2d265364 | Branch: claude/1074-guest-scan-errors
Executor: Opus 5.5 (Tier B owner override, [workflow] decision 2026-11-09) | Fits one session: 30 tool calls, 60k tokens. The Haiku caps do not apply to Opus; command output and file reads stay at 150 lines or fewer.

**Order.** Queue item 1.2 (plan [speed-and-ease](../plans/speed-and-ease.md) section 11, rows S1, S2, S3, S7, S8). Merge order: 1068, then 1074, then 1075 (queue item 1.3, operator prefill). 1068 (`origin/claude/1068-errors-link-fix`) adds one line per language to `App/app/i18n.py` and `App/app/guest_uk_i18n.py` and changes `App/tests/static_versions.json`, all files this brief also edits; so 1074 runs after 1068 merges, or the executor first runs `git merge origin/main` (the anchors below are single lines and survive). `static_versions.json` is never merged by hand: after any merge, regenerate it (step 9). 1071, 1072 and 1069/1070 touch no guest file. 1075 does not exist yet; it edits `_entity_business_fields.html` and probably `i18n.py` and `static_versions.json`, so it also rebases after 1074. Context lint warns on shared files; this paragraph is the answer.

## 1. Objective

Make the guest passport scan clearer without changing how the guest form looks at rest: the scan button becomes the primary button, a busy spinner and "about 10 seconds" text show while it reads, fields it filled carry a "please check" chip, big photos are shrunk on the phone before upload, a scan that cannot read the nationality says so and opens the country picker, and the birth-date format error gets an example. Nothing that is filed changes; the guest still confirms every field.

**Tier.** B is right; no Tier A flag. Nothing changes what is filed: the scan only suggests values the guest edits and submits (`routes/guest.py:2343` stores nothing), validation is untouched (S7 changes wording of one message, not a rule), the server code is not edited, and the nationality is still picked by the guest. HIGH RISK note: S3 changes the pixels the OCR sees (one extra lossy JPEG pass at quality 0.9; the server already caps the long edge at 1568, `doc_ocr.MAX_EDGE`, so resolution is the same). That can only change a suggestion, never a filing, but OCR hit rate on real phone photos is not measured here (see Report, unconfirmed).

## Plan rows checked against the code (verified 2026-11-10 on 2d265364)

| Row | Verdict | Evidence |
|---|---|---|
| S1 | Keep. Not done. The scan label is `g-btn secondary`. | `App/app/templates/guest/_ocr_scan.html:2` |
| S2 | Keep. Only "Reading the document…" exists; no spinner, no chips on filled fields. The `.g-chip` class exists (`guest.css:1177`); the "read-back" under the birth date is a separate hint `div` (`form.html:138`) and is not reused. | `_ocr_scan.html:42`, `i18n.py:415`, `guest.css:1177` |
| S3 | Keep. The browser sends the raw file; only the server shrinks it (`doc_ocr.prepare_image`, `MAX_EDGE = 1568`, greyscale). No client resize anywhere. | `_ocr_scan.html:37-42`, `doc_ocr.py:24,84-103` |
| S7, "jump to the first problem" | **Dropped, already done.** After a failed save the wizard opens the first step with an error (`errorAt`, `signature.js` around line 640), `focusFirstError()` runs on load (`signature.js:555,924`), and every summary line links to its field (`initErrorSummary`, `signature.js:578`). Messages already name the field and the fix ("Date of birth: enter the full date as DD.MM.YYYY."). | `signature.js`, `validation_i18n.py:147-180`, `tests/test_guest_error_summary.py` |
| S7, example in the message | Keep, copy only. The format message has no example. | `validation_i18n.py` `GUEST_EN_MESSAGES`, `GUEST_CS_MESSAGES`, `GUEST_MESSAGES` (de, es, fr), `guest_uk_i18n.py:53` |
| S8 | Keep. `read_document` blanks a nationality that is not in the country list (`doc_ocr.py:326`) and `fillFields` skips empty values, so the select silently stays empty. Nationality is a country combo (`guest-enhancements.js` `initCountryCombos`) whose search input is `#nationality_search`; focusing it opens the list (`input.addEventListener("focus", ... render(""))`). | `_ocr_scan.html:14-22`, `doc_ocr.py:326-327`, `guest-enhancements.js:80-190` |

## 2. Context

Rules that apply (AGENTS.md): the form keeps its look; light mode; no tracking, no new script, no new stored field (the photo is never saved; the chip text lives only in the page); no new dependency; rule 7 (browser and geometry tests with 0 skipped, a 390 px screenshot per changed page, here 390, 768 and 1280 by the owner's request); rule 9 (one explanation in one place; write "no tracking cookies", never "no cookies"; the new texts below do not mention cookies).

The look-change that IS requested: S1 turns one button from the secondary to the primary style. That is the only resting-state visual change. The spinner, chips and error text appear only after a scan or an error. Nothing else may move: if the 390/768/1280 resting screenshots differ from main anywhere except that button's fill and colour, stop (section 8).

Current code, verbatim:

`App/app/templates/guest/_ocr_scan.html`, line 2:
```html
  <label class="g-btn secondary" for="ocr-scan-file">{{ t('ocr_scan_button') }}</label>
```

`App/app/templates/guest/_ocr_scan.html`, lines 9-13 and 15-27 (start of the script and `fillFields`):
```js
(function () {
  var fileInput = document.getElementById('ocr-scan-file');
  var scanStatus = document.getElementById('ocr-scan-status');
  if (!fileInput) return;
  var form = fileInput.form;

  function fillFields(values) {
    var map = { surname: 'surname', first_name: 'first_name', birth_date: 'birth_date',
                nationality: 'nationality', doc_number: 'doc_number' };
    Object.keys(map).forEach(function (k) {
      var el = document.getElementById(map[k]);
      if (!el || !values[k]) return;
      el.value = k === 'birth_date'
        ? values[k].replace(/(\d{2})(\d{2})(\d{4})/, '$1.$2.$3')
        : values[k];
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }
```

`App/app/templates/guest/_ocr_scan.html`, lines 29-60 (`showStatus` through the end of the change handler; the handler is lines 35-60):
```js
  function showStatus(text) {
    if (!scanStatus) return;
    scanStatus.textContent = text;
    scanStatus.hidden = false;
  }

  fileInput.addEventListener('change', function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file || !form) return;
    var body = new FormData();
    body.append('passport_photo', file);
    body.append('_csrf', form.elements._csrf.value);
    fileInput.disabled = true;
    showStatus({{ t('ocr_scan_working') | tojson }});
    fetch(form.getAttribute('action').replace(/\/save\?/, '/scan?'), {
      method: 'POST',
      body: body,
      headers: { Accept: 'application/json' }
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (data.kind === 'values') {
        fillFields(data.values);
        showStatus({{ t('ocr_scan_done') | tojson }});
      } else {
        showStatus(data.message || {{ t('ocr_unavailable') | tojson }});
      }
    }).catch(function () {
      showStatus({{ t('ocr_unavailable') | tojson }});
    }).then(function () {
      fileInput.disabled = false;
      fileInput.value = '';
    });
  });
```

The existing test that pins the old class: `App/tests/test_doc_ocr.py:316` (`assert '<label class="g-btn secondary" for="ocr-scan-file">' in part`). The existing geometry test `App/tests/test_guest_ocr_geometry_browser.py` has the fixtures (`base`, `world`, `browser`, `scan_world_on`, `_page`, `_goto_form`) the new test file imports.

If an excerpt is not found verbatim, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/_ocr_scan.html` | edit | Primary class; spinner; chips; shrink; nationality prompt |
| `App/app/static/guest.css` | edit | `.g-spin` and `.g-scan-chip` rules (append at the end) |
| `App/app/templates/guest/base.html` | edit | Bump the `guest.css` `?v=` |
| `App/tests/static_versions.json` | regenerate | Only via `test_static_versions.py --write` |
| `App/app/i18n.py` | edit | `ocr_scan_working` text; new `ocr_filled_chip`, `ocr_nationality_missing` (en, cs, de, es, fr) |
| `App/app/guest_uk_i18n.py` | edit | The same three keys (uk); the birth-date format message |
| `App/app/validation_i18n.py` | edit | Birth-date format message with an example (en, cs, de, es, fr) |
| `App/tests/test_doc_ocr.py` | edit | Line 316 expects the primary class |
| `App/tests/test_guest_dob_separator.py` | edit | Lines 47 and 50 expect the new message |
| `App/tests/test_guest_scan_feedback_browser.py` | new | Behaviour tests and screenshots (matches the guest test-map row `test_guest_*.py`) |
| `docs/tasks/screenshots-1074/` | new | Before and after PNGs (step 11) |
| `docs/tasks/1074-report.md` | new | The report (section 9) |

No other file may change. Not edited on purpose: `App/app/routes/guest.py`, `App/app/doc_ocr.py`, `App/app/validation.py`, `App/app/retention.py`, `signature.js`, `guest-enhancements.js`.

## 4. Steps

Work in the worktree for branch `claude/1074-guest-scan-errors`. All commands run from `App/` unless a step says otherwise. Commit after steps 3, 4, 5, 6, 7 and 10.

**Step 1: write the test file's first part and take the "before" screenshots on unchanged code.** Create `App/tests/test_guest_scan_feedback_browser.py` with exactly:

```python
"""1074: guest scan feedback, smaller photo, nationality prompt, error example.

Browser tests stub the /scan answer, so they need no OCR engine. They reuse the
fixtures of test_guest_ocr_geometry_browser.py (Max property, claimed form).
Skipped without Playwright unless UBYHOST_REQUIRE_BROWSER=1.
"""
import io
import json
import os
import re
import tempfile
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

from app import i18n, validation_i18n
from tests.browser_support import settle_motion
from tests.test_guest_ocr_geometry_browser import (  # noqa: F401  (fixtures)
    _goto_form,
    _page,
    base,
    browser,
    scan_world_on,
    world,
)

SCAN = re.compile(r"/scan\?")
JSON = "application/json"
VALUES = {
    "surname": "MUSTERMANN",
    "first_name": "ERIKA",
    "birth_date": "12081964",
    "nationality": "DEU",
    "doc_number": "C01X00T47",
}
TINY = {"name": "passport.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xd9"}
NO_SIDEWAYS = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "1074"
LABEL = os.environ.get("SHOT_LABEL", "run")


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_first_step_screenshot(base, world, browser, width):
    OUT.mkdir(parents=True, exist_ok=True)
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        settle_motion(page)
        assert page.evaluate(NO_SIDEWAYS) <= 1
        page.screenshot(path=str(OUT / f"{LABEL}-form-{width}.png"), full_page=True)
    finally:
        context.close()
```
Command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots1074 SHOT_LABEL=before .venv/bin/python -m pytest tests/test_guest_scan_feedback_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
Expected: `3 passed`, no "skipped"; files `/tmp/shots1074/1074/before-form-{390,768,1280}.png` exist (`ls /tmp/shots1074/1074 | tail -30`). Open each PNG and note what the first step looks like (scan button grey with border; Next button green/primary). Commit the test file.

**Step 2: baseline for the tests that will be touched.** Command: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_doc_ocr.py tests/test_guest_dob_separator.py tests/test_guest_ocr_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
Expected: all pass, 0 skipped. (If they already fail on main, STOP.)

**Step 3: S1, the primary button.** In `App/app/templates/guest/_ocr_scan.html` line 2, replace
```html
  <label class="g-btn secondary" for="ocr-scan-file">{{ t('ocr_scan_button') }}</label>
```
with
```html
  <label class="g-btn" for="ocr-scan-file">{{ t('ocr_scan_button') }}</label>
```
In `App/tests/test_doc_ocr.py` line 316 replace `assert '<label class="g-btn secondary" for="ocr-scan-file">' in part` with `assert '<label class="g-btn" for="ocr-scan-file">' in part`.
Command: `.venv/bin/python -m pytest tests/test_doc_ocr.py -q --tb=short -x 2>&1 | tail -30`
Expected: passes.

**Step 4: i18n texts, by script.** Create `/tmp/i18n1074.py` (outside the repo; do not commit) with exactly:

```python
import sys
from pathlib import Path

APP = Path("app")
NEW = {
    "en": ("Reading the document…", "Reading your document. This takes about 10 seconds.",
           "Please check",
           "We could not read your nationality. Please choose it from the list."),
    "cs": ("Čteme doklad…", "Čteme váš doklad. Trvá to asi 10 sekund.",
           "Zkontrolujte, prosím",
           "Státní občanství jsme nepřečetli. Vyberte ho, prosím, ze seznamu."),
    "de": ("Dokument wird gelesen…", "Ihr Dokument wird gelesen. Das dauert etwa 10 Sekunden.",
           "Bitte prüfen",
           "Ihre Staatsangehörigkeit konnten wir nicht lesen. Bitte wählen Sie sie aus der Liste."),
    "es": ("Leyendo el documento…", "Leyendo su documento. Tarda unos 10 segundos.",
           "Compruébelo, por favor",
           "No pudimos leer su nacionalidad. Elíjala de la lista, por favor."),
    "fr": ("Lecture du document…", "Lecture de votre document. Cela prend environ 10 secondes.",
           "À vérifier",
           "Nous n'avons pas pu lire votre nationalité. Choisissez-la dans la liste."),
    "uk": ("Читаємо документ…", "Читаємо ваш документ. Це триває близько 10 секунд.",
           "Перевірте, будь ласка",
           "Ми не змогли прочитати ваше громадянство. Виберіть його зі списку."),
}
DONE = {  # the existing ocr_scan_done line each new pair goes under
    "en": "Filled from the photo. Check every field before you send.",
    "cs": "Předvyplněno z fotografie. Před odesláním zkontrolujte všechna pole.",
    "de": "Aus dem Foto ausgefüllt. Prüfen Sie jedes Feld, bevor Sie senden.",
    "es": "Rellenado a partir de la foto. Compruebe todos los campos antes de enviar.",
    "fr": "Prérempli depuis la photo. Vérifiez chaque champ avant d'envoyer.",
    "uk": "Заповнено з фото. Перевірте кожне поле перед надсиланням.",
}
for lang, (old, new, chip, nat) in NEW.items():
    path, indent = (APP / "guest_uk_i18n.py", "    ") if lang == "uk" else (APP / "i18n.py", "        ")
    text = path.read_text(encoding="utf-8")
    old_w = f'{indent}"ocr_scan_working": "{old}",\n'
    done = f'{indent}"ocr_scan_done": "{DONE[lang]}",\n'
    if text.count(old_w) != 1 or text.count(done) != 1:
        sys.exit(f"anchor not found exactly once for {lang}")
    text = text.replace(old_w, f'{indent}"ocr_scan_working": "{new}",\n')
    text = text.replace(
        done,
        done + f'{indent}"ocr_filled_chip": "{chip}",\n{indent}"ocr_nationality_missing": "{nat}",\n',
    )
    path.write_text(text, encoding="utf-8")
print("ok")
```
Command: `python3 /tmp/i18n1074.py && git diff --stat | tail -30`
Expected: `ok`; `app/i18n.py` shows 15 insertions/5 deletions, `app/guest_uk_i18n.py` 3 insertions/1 deletion. If "anchor not found" (1068 or another merge moved a line), fix only that language's old string from `grep -n 'ocr_scan_working' app/i18n.py app/guest_uk_i18n.py | tail -30`; if the text itself differs, STOP.
Command: `.venv/bin/python -c "from app import i18n; [print(l, i18n.STRINGS[l]['ocr_filled_chip']) for l in ('en','cs','de','es','fr','uk')]" 2>&1 | tail -30`
Expected: six lines, one per language, none a KeyError.

**Step 5: S7, the date-format example, by script.** Create `/tmp/date1074.py` (outside the repo) with exactly:

```python
import sys
from pathlib import Path

EDITS = [
    ("app/validation_i18n.py",
     '"Date of birth: enter the full date as DD.MM.YYYY."',
     '"Date of birth: enter the full date as DD.MM.YYYY, for example 14.03.1961."'),
    ("app/validation_i18n.py",
     '"Datum narození: zadejte celé datum ve formátu DD.MM.RRRR."\n    ),\n    "Year must',
     '"Datum narození: zadejte celé datum ve formátu DD.MM.RRRR, například 14.03.1961."\n    ),\n    "Year must'),
    ("app/validation_i18n.py",
     '"Geburtsdatum: Geben Sie das vollständige Datum als TT.MM.JJJJ ein."',
     '"Geburtsdatum: Geben Sie das vollständige Datum als TT.MM.JJJJ ein, zum Beispiel 14.03.1961."'),
    ("app/validation_i18n.py",
     '"Fecha de nacimiento: introduzca la fecha completa como DD.MM.AAAA."',
     '"Fecha de nacimiento: introduzca la fecha completa como DD.MM.AAAA, por ejemplo 14.03.1961."'),
    ("app/validation_i18n.py",
     '"Date de naissance : saisissez la date complète au format JJ.MM.AAAA."',
     '"Date de naissance : saisissez la date complète au format JJ.MM.AAAA, par exemple 14.03.1961."'),
    ("app/guest_uk_i18n.py",
     '"Дата народження: введіть повну дату у форматі ДД.ММ.РРРР."',
     '"Дата народження: введіть повну дату у форматі ДД.ММ.РРРР, наприклад 14.03.1961."'),
]
for name, old, new in EDITS:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        sys.exit(f"anchor not found exactly once in {name}: {old[:50]}")
    path.write_text(text.replace(old, new), encoding="utf-8")
print("ok")
```
Then in `App/tests/test_guest_dob_separator.py` replace line 47 `"Date of birth: enter the full date as DD.MM.YYYY."` with `"Date of birth: enter the full date as DD.MM.YYYY, for example 14.03.1961."` and line 50 `"Datum narození: zadejte celé datum ve formátu DD.MM.RRRR."` with `"Datum narození: zadejte celé datum ve formátu DD.MM.RRRR, například 14.03.1961."` (the host line 44, `CS_MESSAGES`, stays as it is).
Command: `python3 /tmp/date1074.py && .venv/bin/python -m pytest tests/test_guest_dob_separator.py tests/test_guest_error_summary.py -q --tb=short -x 2>&1 | tail -30`
Expected: `ok`, then all pass. Note the `uk` table also holds the sentence for the host (`VALIDATION`, keyed the same way); if `grep -rn "введіть повну дату" app | tail` shows a second copy, STOP and ask.

**Step 6: CSS and cache key.** Append to the end of `App/app/static/guest.css` (check `tail -5 app/static/guest.css` first; add a blank line before):
```css

/* 1074: scan feedback. The spinner shows only while a document is being read;
   the chip marks a field the scan filled until the guest edits it. */
.g-spin {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 8px;
  border: 2px solid var(--g-line-2);
  border-top-color: var(--brand-action);
  border-radius: 50%;
  vertical-align: -2px;
  animation: g-spin 0.8s linear infinite;
}
@keyframes g-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .g-spin { animation: none; border-top-color: var(--g-line-2); }
}
.g-chip.g-scan-chip {
  display: block;
  width: fit-content;
  max-width: 100%;
  margin: 6px 0 0;
  white-space: normal;
}
```
The reduced-motion rule is needed: the global rule at `guest.css:1454` shortens durations to 0.01 ms, which would make an infinite spinner flicker.
In `App/app/templates/guest/base.html` line 14 replace `/static/guest.css?v=20261109-1063a` with `/static/guest.css?v=20261110-1074a`. If the line already holds another value after a merge, use `20261110-1074a` anyway.
Command: `grep -n 'guest.css' app/templates/guest/base.html | tail -3`
Expected: shows `?v=20261110-1074a`.

**Step 7: the script in `_ocr_scan.html`.** Four edits, in this order, to `App/app/templates/guest/_ocr_scan.html`.

7a. Replace the whole `fillFields` function (lines 15-27 shown in section 2) with this version, which keeps the same field map and events, drops old chips first and adds a chip per filled field (the chip goes away when the guest edits that field):
```js
  var chipText = {{ t('ocr_filled_chip') | tojson }};

  function clearChips() {
    Array.prototype.forEach.call(document.querySelectorAll('.g-scan-chip'), function (chip) {
      chip.parentNode.removeChild(chip);
    });
  }

  function addChip(el) {
    var box = el.closest('.g-field');
    if (!box) return;
    var chip = document.createElement('span');
    chip.className = 'g-chip g-scan-chip';
    chip.textContent = chipText;
    box.appendChild(chip);
    function drop() { if (chip.parentNode) chip.parentNode.removeChild(chip); }
    el.addEventListener('input', drop, { once: true });
    el.addEventListener('change', drop, { once: true });
  }

  function fillFields(values) {
    var map = { surname: 'surname', first_name: 'first_name', birth_date: 'birth_date',
                nationality: 'nationality', doc_number: 'doc_number' };
    clearChips();
    Object.keys(map).forEach(function (k) {
      var el = document.getElementById(map[k]);
      if (!el || !values[k]) return;
      el.value = k === 'birth_date'
        ? values[k].replace(/(\d{2})(\d{2})(\d{4})/, '$1.$2.$3')
        : values[k];
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      addChip(el);
    });
  }
```
7b. Replace `showStatus` (lines 29-33) with a version that can show the spinner, and add the shrink helper right after it:
```js
  function showStatus(text, busy) {
    if (!scanStatus) return;
    scanStatus.textContent = '';
    if (busy) {
      var spin = document.createElement('span');
      spin.className = 'g-spin';
      spin.setAttribute('aria-hidden', 'true');
      scanStatus.appendChild(spin);
    }
    scanStatus.appendChild(document.createTextNode(text));
    scanStatus.hidden = false;
  }

  // The server shrinks to 1568 px on the long edge anyway (doc_ocr.MAX_EDGE), so
  // doing it here sends less data. The image is resampled here by the browser
  // instead of by the server, plus one JPEG pass (unconfirmed for OCR, see the
  // 1074 report). Any failure (old browser, odd file) falls back to the original.
  var MAX_EDGE = 1568;
  function shrink(file) {
    if (!window.createImageBitmap || !/^image\/(jpeg|png|webp)$/.test(file.type)) {
      return Promise.resolve(file);
    }
    return createImageBitmap(file, { imageOrientation: 'from-image' }).then(function (bmp) {
      var longest = Math.max(bmp.width, bmp.height);
      if (longest <= MAX_EDGE && file.size <= 1500000) { bmp.close(); return file; }
      var scale = Math.min(1, MAX_EDGE / longest);
      var canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bmp.width * scale));
      canvas.height = Math.max(1, Math.round(bmp.height * scale));
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
      bmp.close();
      return new Promise(function (resolve) {
        canvas.toBlob(function (blob) {
          resolve(blob && blob.size < file.size
            ? new File([blob], 'scan.jpg', { type: 'image/jpeg' }) : file);
        }, 'image/jpeg', 0.9);
      });
    }).catch(function () { return file; });
  }
```
7c. Replace the change handler (from `fileInput.addEventListener('change', function () {` to its closing `});`, lines 35-60 shown in section 2) with:
```js
  fileInput.addEventListener('change', function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file || !form) return;
    var csrf = form.elements._csrf.value;
    fileInput.disabled = true;
    showStatus({{ t('ocr_scan_working') | tojson }}, true);
    shrink(file).then(function (photo) {
      var body = new FormData();
      body.append('passport_photo', photo, photo.name || file.name);
      body.append('_csrf', csrf);
      return fetch(form.getAttribute('action').replace(/\/save\?/, '/scan?'), {
        method: 'POST',
        body: body,
        headers: { Accept: 'application/json' }
      });
    }).then(function (res) { return res.json(); }).then(function (data) {
      if (data.kind === 'values') {
        fillFields(data.values);
        var nat = document.getElementById('nationality');
        var natError = document.getElementById('nationality_error');
        if (!data.values.nationality) {
          // The scan could not read the nationality: say so, also under the picker
          // so it stays in view, and open the picker when it is empty (a value from
          // an earlier scan is kept). The guest chooses it; nothing is filled for them.
          var missing = {{ t('ocr_nationality_missing') | tojson }};
          showStatus({{ t('ocr_scan_done') | tojson }} + ' ' + missing);
          if (natError) {
            natError.textContent = missing;
            natError.setAttribute('data-ocr', '1');
            natError.hidden = false;
          }
          if (nat && !nat.value) (document.getElementById('nationality_search') || nat).focus();
        } else {
          if (natError && natError.hasAttribute('data-ocr')) {
            natError.removeAttribute('data-ocr');
            natError.hidden = true;
          }
          showStatus({{ t('ocr_scan_done') | tojson }});
        }
      } else {
        showStatus(data.message || {{ t('ocr_unavailable') | tojson }});
      }
    }).catch(function () {
      showStatus({{ t('ocr_unavailable') | tojson }});
    }).then(function () {
      fileInput.disabled = false;
      fileInput.value = '';
    });
  });
```
7d. Leave the closing `})();` and `</script>` as they are.
Command: `.venv/bin/python -m pytest tests/test_doc_ocr.py tests/test_guest_ocr_geometry_browser.py -q --tb=short -x 2>&1 | tail -30`
Expected: pass (markup test only needs the class; geometry tests still pass).

**Step 8: add the behaviour tests.** Append to `App/tests/test_guest_scan_feedback_browser.py` exactly:

```python


def _answer(route, payload, status=200):
    route.fulfill(status=status, content_type=JSON, body=json.dumps(payload))


def test_scan_button_is_primary_like_next(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        label = page.locator("#ocr-scan label[for='ocr-scan-file']")
        assert "secondary" not in (label.get_attribute("class") or "")
        fill = "(el) => getComputedStyle(el).backgroundColor"
        nxt = page.locator(".g-wizard-nav .g-btn:not(.secondary)").first
        assert label.evaluate(fill) == nxt.evaluate(fill)
        assert page.locator("#ocr-scan-hint").is_visible()
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_working_text_spinner_then_chips_that_go_when_edited(base, world, browser, width):
    OUT.mkdir(parents=True, exist_ok=True)
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        held = []
        page.route(SCAN, lambda route: held.append(route))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_selector("#ocr-scan-status .g-spin")
        status = page.locator("#ocr-scan-status")
        assert "10 seconds" in status.inner_text()
        assert page.locator("#ocr-scan-file").is_disabled()
        held[0].fulfill(status=200, content_type=JSON,
                        body=json.dumps({"kind": "values", "values": VALUES}))
        page.wait_for_selector(".g-scan-chip")
        assert page.locator("#ocr-scan-status .g-spin").count() == 0
        assert page.locator(".g-scan-chip").count() == 5
        assert page.locator("#surname").input_value() == "MUSTERMANN"
        assert page.locator("#birth_date").input_value() == "12.08.1964"
        chips = page.locator(".g-scan-chip")
        assert chips.first.inner_text() == "Please check"
        assert "Please check" not in i18n.STRINGS["en"]["ocr_scan_done"]
        card = page.locator("[data-guest-step]").first.bounding_box()
        for i in range(chips.count()):
            if chips.nth(i).is_visible():
                box = chips.nth(i).bounding_box()
                assert box["x"] >= card["x"] - 0.5
                assert box["x"] + box["width"] <= card["x"] + card["width"] + 0.5
        assert page.evaluate(NO_SIDEWAYS) <= 1
        assert page.evaluate("document.activeElement && document.activeElement.id") != "nationality_search"
        page.wait_for_timeout(300)
        assert page.locator(".g-scan-chip").count() == 5, "a chip must stay until the guest edits"
        settle_motion(page)
        page.screenshot(path=str(OUT / f"{LABEL}-scanned-{width}.png"), full_page=True)
        page.fill("#surname", "MUSTERMANN2")
        assert page.locator(".g-scan-chip").count() == 4
    finally:
        context.close()


def test_unreadable_nationality_says_so_and_opens_the_picker(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        values = {k: v for k, v in VALUES.items() if k != "nationality"}
        page.route(SCAN, lambda route: _answer(route, {"kind": "values", "values": values}))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function(
            "document.activeElement && document.activeElement.id === 'nationality_search'"
        )
        assert page.locator("#nationality_list").is_visible()
        assert "choose it from the list" in page.locator("#ocr-scan-status").inner_text()
        assert page.locator("#nationality_error").is_visible()
        assert "choose it from the list" in page.locator("#nationality_error").inner_text()
        assert page.locator("#nationality").input_value() == ""
        assert page.locator("#nationality").locator(
            "xpath=ancestor::div[contains(@class,'g-field')][1]//span[contains(@class,'g-scan-chip')]"
        ).count() == 0
        assert page.locator(".g-scan-chip").count() == 4
    finally:
        context.close()


def test_unread_nationality_is_said_even_when_an_earlier_scan_filled_it(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        answers = [VALUES, {k: v for k, v in VALUES.items() if k != "nationality"}]
        page.route(SCAN, lambda route: _answer(route, {"kind": "values", "values": answers.pop(0)}))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_selector(".g-scan-chip")
        page.wait_for_function("!document.querySelector('#ocr-scan-file').disabled")
        page.locator("#surname").focus()
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function(
            "document.querySelector('#ocr-scan-status').textContent.includes('choose it from the list')"
        )
        assert page.locator("#nationality").input_value() == "DEU"
        assert page.locator("#nationality_error").is_visible()
        assert "choose it from the list" in page.locator("#nationality_error").inner_text()
        assert page.evaluate("document.activeElement && document.activeElement.id") != "nationality_search"
        assert page.locator(".g-scan-chip").count() == 4
        page.wait_for_function("!document.querySelector('#ocr-scan-file').disabled")
        assert page.locator("#nationality_error").is_visible(), "clearing chips must keep the prompt"
    finally:
        context.close()


def _photo(size, orientation=None):
    from PIL import Image

    image = Image.effect_noise(size, 80).convert("RGB")
    out = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(out, "JPEG", quality=92, exif=exif)
    else:
        image.save(out, "JPEG", quality=92)
    return out.getvalue()


def test_big_photo_is_shrunk_upright_before_upload(base, world, browser):
    from PIL import Image

    original = _photo((3200, 2400), orientation=6)  # a phone held upright
    seen = []

    def grab(route):
        seen.append(route.request.post_data_buffer)
        _answer(route, {"kind": "error", "message": "stub"}, 422)

    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        page.route(SCAN, grab)
        page.set_input_files("#ocr-scan-file",
                             {"name": "big.jpg", "mimeType": "image/jpeg", "buffer": original})
        page.wait_for_function("document.querySelector('#ocr-scan-status').textContent.includes('stub')")
    finally:
        context.close()
    body = seen[0]
    assert len(body) < len(original) * 0.6
    sent = Image.open(io.BytesIO(body[body.index(b"\xff\xd8"):]))
    assert max(sent.size) <= 1568
    assert sent.size[1] > sent.size[0], "orientation 6 must come out upright (portrait)"


def test_unreadable_image_is_sent_as_it_was(base, world, browser):
    seen = []

    def grab(route):
        seen.append(route.request.post_data_buffer)
        _answer(route, {"kind": "error", "message": "stub"}, 422)

    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        page.route(SCAN, grab)
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function("document.querySelector('#ocr-scan-status').textContent.includes('stub')")
    finally:
        context.close()
    assert b"\xff\xd8\xff\xd9" in seen[0]


@pytest.mark.parametrize("lang", ["en", "cs", "de", "es", "fr", "uk"])
def test_birth_date_format_error_gives_an_example(lang):
    message = validation_i18n.guest_localize("Enter the full date as DD.MM.YYYY.", lang)
    assert "14.03.1961" in message


@pytest.mark.parametrize("lang", ["en", "cs", "de", "es", "fr", "uk"])
def test_scan_texts_exist_in_every_guest_language(lang):
    table = i18n.STRINGS[lang]
    for key in ("ocr_scan_working", "ocr_filled_chip", "ocr_nationality_missing"):
        assert table[key].strip()
    assert "10" in table["ocr_scan_working"]
```
Command: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots1074 SHOT_LABEL=after .venv/bin/python -m pytest tests/test_guest_scan_feedback_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
Expected: `23 passed` (3 screenshots, 8 browser behaviours of which the chip test runs at 390, 768 and 1280, 6 error-example, 6 language checks) and no "skipped". Files `after-form-{390,768,1280}.png` and `after-scanned-{390,768,1280}.png` exist.
If the shrink test fails on orientation (landscape comes out), do not weaken it: this means `imageOrientation: 'from-image'` is not honoured; STOP and report. If the nationality test fails because the list is not visible, check `#nationality_list` has `hidden` after focus; STOP and report instead of changing `guest-enhancements.js`.

**Step 9: regenerate the version manifest.** Command: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` then `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
Expected: the json changes only the `guest.css` entry (`git diff --stat tests/static_versions.json | tail -3` shows 1 file, 2 changed lines); the test passes. Never hand-edit the json.

**Step 10: screenshots, by eye.** Open and compare, against the `before-` set: `after-form-390.png`, `after-form-768.png`, `after-form-1280.png`, plus `after-scanned-390.png`, `after-scanned-768.png`, `after-scanned-1280.png` (chips inside the card at each width). Copy all nine PNGs and the `before-` ones into `docs/tasks/screenshots-1074/` (`mkdir -p` first; names kept). For each page size write down what you saw. The look is unchanged if: same card, same title, same field order and sizes, same spacing, same Next button; the only difference is the scan button now filled in the brand colour with white text (the Next button below keeps its own fill). If anything else moved (heights, wrapping, field positions), STOP (section 8). Commit.

**Step 11: the full check for this area.** Commands, each ending as shown:
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs 2>&1 | tail -30` (the test-map row for guest pages). Expected: all pass and the last lines show no `SKIPPED`.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_privacy_first.py tests/test_cookie_inventory.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30` (no new script, no new cookie). Expected: pass.
3. From the repo root: `python3 scripts/context_lint.py | tail -3`. Expected: no new error line from this brief.
If a test fails twice, STOP.

## 5. Do not touch

`App/app/routes/guest.py`, `App/app/doc_ocr.py`, `App/app/validation.py` (host wording and every rule stay), `App/app/retention.py`, `App/app/static/signature.js`, `App/app/static/guest-enhancements.js`, any host template or CSS, the field order, colours, fonts, copy other than the three scan keys and the format message, the adult signature, the legal tick, `docs/plans/speed-and-ease.md`. No new dependency, no new script tag, no new request (the shrink uses the browser's own `createImageBitmap` and canvas; the same `/scan` request is sent, with a smaller file). No new stored field, so no `retention.py` line; the photo is still never saved. AGENTS.md rules 1 to 9 apply; push, merge and deploy are the owner's.

## 6. Commands

All are in section 4. Tests: the guest row of the [test-map](../context/test-map.md) (step 11), the new file, `test_doc_ocr.py`, `test_guest_dob_separator.py`, `test_guest_error_summary.py`, `test_guest_ocr_geometry_browser.py`, `test_static_versions.py`, `test_privacy_first.py`. Never the full suite.

## 7. Acceptance

- [ ] `grep -n 'g-btn secondary' app/templates/guest/_ocr_scan.html | tail -3` prints nothing; the label is `g-btn`.
- [ ] The new test file passes with 0 skipped under `UBYHOST_REQUIRE_BROWSER=1`, and the guest row of the test-map passes with 0 skipped.
- [ ] `git diff --stat origin/main | tail -20` shows only the files in section 3 (plus the screenshots and report).
- [ ] `git diff origin/main -- App/app/routes App/app/doc_ocr.py App/app/validation.py | wc -l` prints `0`.
- [ ] Screenshots of the guest form step 1 at 390, 768 and 1280 px, before and after, are in `docs/tasks/screenshots-1074/`, each checked by eye; the PR text says, per width, what was seen ("390: ...; 768: ...; 1280: ...") and names the scan button as the only resting-state change. Screenshots of the scanned state (chips) at 390, 768 and 1280 px are included, and the chip-inside-card check runs at each width.
- [ ] No sideways scroll at any of the three widths (asserted in the tests).
- [ ] The chip, spinner and nationality texts exist in en, cs, de, es, fr, uk (asserted).
- [ ] Context lint clean for this brief.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or script anchor is not found (after at most the one-language fix in step 4);
- a test fails twice;
- the resting screenshots differ from main in anything but the scan button's fill (layout shift, wrapping, new spacing);
- the shrink test shows the orientation is wrong, or the nationality list does not open on focus;
- you reach 25 tool calls or about 50k tokens;
- a new dependency seems needed;
- a file outside section 3 needs a change (including `routes/guest.py`, `guest-enhancements.js`, `signature.js`);
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1074-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.
7. For the PR text: per width, "390: ...; 768: ...; 1280: ..." as seen, and the unconfirmed list below.

**Unconfirmed, to say plainly in the report:** (a) whether the browser's resampling (canvas, `imageSmoothingQuality = 'high'`) and the one extra JPEG pass at quality 0.9 change the OCR hit rate on real phone photos; only stub and synthetic images were tested, and the guest checks every filled field; (b) behaviour in iOS Safari and WebKit was not run (`createImageBitmap` options need Safari 15 or later; older versions fall back to the original file); (c) how long a real scan takes ("about 10 seconds" is the plan's wording; the worst case with only a text line is about 45 s, noted in the plan under "Bugs and oddities").

## Risk list (for the reviewer)

Read the diff of: `App/app/templates/guest/_ocr_scan.html` (the whole script), `App/app/static/guest.css` (the appended block), the six edited lines in `validation_i18n.py` and `guest_uk_i18n.py` (copy only), and the screenshots. Everything else is text or a test. Confirm `routes/guest.py`, `doc_ocr.py` and `validation.py` are untouched.

## Owner steps

1. Open the pull request when the report says `review`. Read the per-width screenshot notes in its text.
2. On a real phone (an iPhone and an Android if you can), open a guest link of a Max property, tap "Scan your passport or ID" with a real passport photo, and check three things: the spinner and the "about 10 seconds" line show, the filled fields show "Please check", and nothing looks different before the tap except the scan button now being filled in.
3. Merge with `scripts/merge-pr-on-green.sh` when the checks are green.
4. Deploy by hand as usual.
