# 0282: Signature locked until Edit; large dialog to draw or type it

Status: todo
Depends on: 0281 | Base commit: a6c532c | Branch: claude/project-thread-j2cl8a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The stay-fee signature pad is open on the page, so a thumb scrolling on a phone scratches it. It becomes a greyed, locked preview with an Edit button; Edit opens a large dialog in the same tab (bottom sheet on phone) where the host draws the signature or types their name, which is drawn in a handwriting font, like Adobe's "type your signature".

## 2. Context

Owner (2026-10-22): "make it lock itself and only be writable when they want to edit it, so grey it out if locked ... open a larger screen (still on the same tab) ... sign it manually or write it normally and UbyHost will paste it in a signature-like style." He named "pdfcart"; no such project exists, and the closest open-source signer (signaturepdf) is AGPL, so nothing is copied. The font is Dancing Script, SIL Open Font License 1.1, self-hosted (no third-party request; it covers Czech and Vietnamese letters).

Server side does not change: the form still posts `signature_drawn` (a PNG data URL, max 300 KB), `signature_file`, `signature_remove`, `signature_name` (`App/app/routes/admin.py` `_signature_payload`). A typed signature is posted as a PNG in `signature_drawn` and the typed text in `signature_name`.

`App/app/templates/_entity_business_fields.html`, the macro to replace (lines from `{% macro signature_fields(prefix, entity, preview='') %}` to its `{% endmacro %}`): it renders `<fieldset class="signature-block" data-host-signature>` with a legend + `help_tip`, a canvas `{{ prefix }}sig-canvas`, the hidden `signature_drawn` (value = preview), Clear, Upload label + file input, the remove checkbox when `preview`, and the `signature_name` field. It is used by `_fee_signature_fields.html` (property settings, Reporting & fees, and the setup wizard stay-fee step).

`App/app/static/host.js` has the pad code in the block that starts `  document.querySelectorAll('[data-host-signature]').forEach(function (block) {` and ends with `    if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);\n  });` (just above the comment `// The demo form opens its POST response in a new tab.`).

Dialog component (MASTER 7.9, `host2.css`): `<dialog class="ui-dialog">` > `.ui-sheet` > `.ui-sheet-handle`, `h2`, actions; on phone it is a bottom sheet. Tabs: `.ui-tabs` with `.ui-tab` buttons.

`App/app/templates/base.html` keys: `host2.css?v=20261022-0281` (after 0281), `host.js?v=20261021-0205`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/fonts/DancingScript.ttf | new | font (download) |
| App/app/static/fonts/LICENSE-DancingScript.txt | new | OFL text (download) |
| App/app/templates/_entity_business_fields.html | edit | macro `signature_fields` |
| App/app/static/host.js | edit | replace the pad block |
| App/app/static/host2.css | append | locked preview, dialog, @font-face |
| App/app/templates/base.html | edit | `?v=` keys of host2.css and host.js |
| App/app/host_i18n.py | edit | new keys EN/CS |
| App/app/host_vi_i18n.py | edit | new keys VI |
| App/tests/test_0282_signature_dialog_browser.py | new | browser test |
| docs/context/decisions.md | append | one line |

No other file may change. If `tests/test_fee_signature_0209.py` or `tests/test_stay_fee_signature.py` asserted the old markup (a visible canvas, the Clear button outside a dialog), update only that assertion and list it under Deviations.

## 4. Steps

1. **Font.** From the repo root:
```
curl -sSfL -o App/app/static/fonts/DancingScript.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf"
curl -sSfL -o App/app/static/fonts/LICENSE-DancingScript.txt "https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/OFL.txt"
ls -l App/app/static/fonts/ | tail -5
```
Expected: the TTF is about 130 KB and the licence starts with `Copyright`. Commit `0282 step 1`.

2. **Markup.** Replace the whole `signature_fields` macro with:
```jinja
{% macro signature_fields(prefix, entity, preview='') %}
  {%- set typed = (entity.signature_name or '') if entity else '' -%}
  <fieldset class="signature-block" data-host-signature>
    {#- 0240: the why sits behind "?", not in a paragraph. -#}
    <legend>{{ t('entity.signature.heading') }} {{ help_tip(prefix ~ 'signature-help', t('entity.signature.scope')) }}</legend>
    {#- 0282: locked until Edit, so a scrolling thumb never scratches it. -#}
    <div class="signature-locked">
      <img class="signature-locked-img" data-signature-preview alt="{{ t('entity.signature.locked_alt') }}"{% if preview %} src="{{ preview }}"{% else %} hidden{% endif %}>
      <span class="signature-locked-empty" data-signature-empty{% if preview %} hidden{% endif %}>{{ t('entity.signature.none') }}</span>
    </div>
    <div class="action-group">
      <button class="ui-btn ui-btn-secondary" type="button" data-signature-open hidden>{{ t('entity.signature.edit' if preview else 'entity.signature.add') }}</button>
      <span class="small" role="status" data-signature-status data-unsaved="{{ t('entity.signature.unsaved') }}"></span>
    </div>
    <input type="hidden" id="{{ prefix }}signature" name="signature_drawn" value="{{ preview }}">
    <dialog class="ui-dialog signature-dialog" data-signature-dialog aria-labelledby="{{ prefix }}sig-title">
      <div class="ui-sheet">
        <span class="ui-sheet-handle" aria-hidden="true"></span>
        <h2 id="{{ prefix }}sig-title">{{ t('entity.signature.dialog_title') }}</h2>
        <div class="ui-tabs signature-modes" role="tablist">
          <button class="ui-tab" type="button" role="tab" aria-selected="true" data-signature-mode="draw">{{ t('entity.signature.mode_draw') }}</button>
          <button class="ui-tab" type="button" role="tab" aria-selected="false" data-signature-mode="type">{{ t('entity.signature.mode_type') }}</button>
        </div>
        <div data-signature-panel="draw">
          <canvas id="{{ prefix }}sig-canvas" class="signature-dialog-pad" role="img" aria-label="{{ t('entity.signature.draw_hint') }}"></canvas>
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="button" data-signature-clear>{{ t('entity.signature.clear') }}</button>
        </div>
        <div data-signature-panel="type" hidden>
          <div class="field">
            <label for="{{ prefix }}signature_name">{{ t('entity.signature.type_label') }}</label>
            <input type="text" id="{{ prefix }}signature_name" name="signature_name" maxlength="80" autocomplete="name" value="{{ typed }}" data-signature-typed>
          </div>
          <canvas class="signature-dialog-pad signature-typed-preview" data-signature-typed-canvas aria-hidden="true"></canvas>
        </div>
        <div class="action-group">
          <label class="ui-btn ui-btn-secondary ui-btn-compact" for="{{ prefix }}signature_file">{{ t('entity.signature.upload') }}</label>
          <input class="sr-only" type="file" id="{{ prefix }}signature_file" name="signature_file" accept="image/png,image/jpeg" data-signature-file>
          {% if preview %}<label class="check"><input type="checkbox" name="signature_remove" value="1"> {{ t('entity.signature_remove') }}</label>{% endif %}
        </div>
        <div class="action-group signature-dialog-actions">
          <button class="ui-btn ui-btn-primary" type="button" data-signature-use>{{ t('entity.signature.use') }}</button>
          <button class="ui-btn ui-btn-secondary" type="button" data-signature-cancel>{{ t('entity.signature.cancel') }}</button>
        </div>
      </div>
    </dialog>
  </fieldset>
{% endmacro %}
```
Commit `0282 step 2`.

3. **Script.** Replace the old pad block in `host.js` (from its first line to its closing `  });`, see §2) with:
```js
  // 0282: the stay-fee signature is locked until the host presses Edit. Edit
  // opens a large dialog to draw it, or to type a name that is drawn in a
  // handwriting font. Nothing reaches the form until "Use this signature".
  var SIGNATURE_INK = '#20201e';
  var SIGNATURE_FONT = '"UbyHost Signature", cursive';
  document.querySelectorAll('[data-host-signature]').forEach(function (block) {
    var dialog = block.querySelector('[data-signature-dialog]');
    var canvas = block.querySelector('[data-signature-panel="draw"] canvas');
    var typedCanvas = block.querySelector('[data-signature-typed-canvas]');
    var typed = block.querySelector('[data-signature-typed]');
    var hidden = block.querySelector('input[name="signature_drawn"]');
    var preview = block.querySelector('[data-signature-preview]');
    var empty = block.querySelector('[data-signature-empty]');
    var status = block.querySelector('[data-signature-status]');
    var openButton = block.querySelector('[data-signature-open]');
    var file = block.querySelector('[data-signature-file]');
    var remove = block.querySelector('input[name="signature_remove"]');
    if (!dialog || !canvas || !hidden || !openButton || typeof dialog.showModal !== 'function') return;
    var mode = 'draw';
    var draft = '';
    var drawing = false;
    var inked = false;
    openButton.hidden = false;

    function fit(target) {
      var rect = target.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      var ratio = window.devicePixelRatio || 1;
      target.width = Math.round(rect.width * ratio);
      target.height = Math.round(rect.height * ratio);
      var ctx = target.getContext('2d');
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      return { ctx: ctx, width: rect.width, height: rect.height };
    }
    function paintDraft() {
      var box = fit(canvas);
      if (!box) return;
      box.ctx.lineWidth = 2.6;
      box.ctx.lineCap = 'round';
      box.ctx.lineJoin = 'round';
      box.ctx.strokeStyle = SIGNATURE_INK;
      if (!draft) return;
      var image = new Image();
      image.onload = function () { box.ctx.drawImage(image, 0, 0, box.width, box.height); };
      image.src = draft;
    }
    function writeName(ctx, width, height) {
      var text = (typed.value || '').trim();
      ctx.clearRect(0, 0, width, height);
      if (!text) return false;
      var size = height * 0.55;
      ctx.font = size + 'px ' + SIGNATURE_FONT;
      var measured = ctx.measureText(text).width;
      if (measured > width * 0.9) {
        size = size * width * 0.9 / measured;
        ctx.font = size + 'px ' + SIGNATURE_FONT;
      }
      ctx.fillStyle = SIGNATURE_INK;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, width / 2, height / 2);
      return true;
    }
    function paintTyped() {
      var box = fit(typedCanvas);
      if (box) writeName(box.ctx, box.width, box.height);
    }
    function fontReady() {
      if (!document.fonts || !document.fonts.load) return Promise.resolve();
      return document.fonts.load('48px "UbyHost Signature"').catch(function () {});
    }
    function setMode(next) {
      mode = next;
      block.querySelectorAll('[data-signature-mode]').forEach(function (tab) {
        tab.setAttribute('aria-selected', tab.getAttribute('data-signature-mode') === next ? 'true' : 'false');
      });
      block.querySelectorAll('[data-signature-panel]').forEach(function (panel) {
        panel.hidden = panel.getAttribute('data-signature-panel') !== next;
      });
      if (next === 'draw') paintDraft(); else fontReady().then(paintTyped);
    }
    function showPreview(src) {
      if (src) { preview.src = src; preview.hidden = false; empty.hidden = true; }
      else { preview.removeAttribute('src'); preview.hidden = true; empty.hidden = false; }
      if (status) status.textContent = status.getAttribute('data-unsaved') || '';
    }
    function point(event) {
      var rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }
    canvas.addEventListener('pointerdown', function (event) {
      drawing = true;
      inked = false;
      canvas.setPointerCapture(event.pointerId);
      var start = point(event);
      var ctx = canvas.getContext('2d');
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!drawing) return;
      var next = point(event);
      var ctx = canvas.getContext('2d');
      ctx.lineTo(next.x, next.y);
      ctx.stroke();
      inked = true;
    });
    function endStroke() {
      if (!drawing) return;
      drawing = false;
      if (inked) draft = canvas.toDataURL('image/png');
    }
    canvas.addEventListener('pointerup', endStroke);
    canvas.addEventListener('pointercancel', endStroke);
    block.querySelector('[data-signature-clear]').addEventListener('click', function () {
      draft = '';
      paintDraft();
    });
    block.querySelectorAll('[data-signature-mode]').forEach(function (tab) {
      tab.addEventListener('click', function () { setMode(tab.getAttribute('data-signature-mode')); });
    });
    if (typed) typed.addEventListener('input', function () { fontReady().then(paintTyped); });
    openButton.addEventListener('click', function () {
      draft = hidden.value.indexOf('data:image/') === 0 ? hidden.value : '';
      dialog.showModal();
      window.requestAnimationFrame(function () { setMode(mode); });
    });
    block.querySelector('[data-signature-cancel]').addEventListener('click', function () { dialog.close(); });
    if (file) file.addEventListener('change', function () {
      var chosen = file.files && file.files[0];
      if (!chosen) return;
      var reader = new FileReader();
      reader.onload = function () { showPreview(String(reader.result)); dialog.close(); };
      reader.readAsDataURL(chosen);
    });
    block.querySelector('[data-signature-use]').addEventListener('click', function () {
      if (remove && remove.checked) {
        hidden.value = '';
        showPreview('');
      } else if (mode === 'type') {
        var out = document.createElement('canvas');
        out.width = 900;
        out.height = 240;
        if (writeName(out.getContext('2d'), out.width, out.height)) {
          hidden.value = out.toDataURL('image/png');
          showPreview(hidden.value);
        }
      } else if (draft) {
        hidden.value = draft;
        showPreview(draft);
      }
      dialog.close();
    });
    if (window.ResizeObserver) new ResizeObserver(function () {
      if (dialog.open && !drawing) setMode(mode);
    }).observe(canvas);
  });
```
In `base.html` change `host.js?v=20261021-0205` to `host.js?v=20261022-0282`. Commit `0282 step 3`.

4. **Styles.** Append to `App/app/static/host2.css`:
```css
/* 0282: stay-fee signature: greyed locked preview, large signing dialog, and
   the self-hosted handwriting font (Dancing Script, SIL OFL 1.1). */
@font-face { font-family: "UbyHost Signature"; src: url("/static/fonts/DancingScript.ttf?v=20261022-0282") format("truetype"); font-weight: 400 700; font-display: swap; }
.host-workspace .signature-locked { display: flex; align-items: center; justify-content: center; min-height: calc(var(--control-h) * 2); padding: var(--space-3); border: 1px solid var(--line-strong); border-radius: var(--radius-2); background: var(--surface-2); }
.host-workspace .signature-locked-img { max-width: 100%; max-height: calc(var(--control-h) * 2.5); filter: grayscale(1); opacity: 0.6; }
.host-workspace .signature-locked-empty { color: var(--ink-3); font-size: var(--size-14); }
.host-workspace .ui-dialog.signature-dialog { width: min(calc(var(--dialog-w) * 1.5), calc(100vw - var(--space-8))); }
.host-workspace .signature-dialog .signature-dialog-pad { display: block; width: 100%; height: clamp(calc(var(--control-h) * 3.5), 40vh, calc(var(--control-h) * 7)); margin: var(--space-3) 0; border: 1px solid var(--line-strong); border-radius: var(--radius-2); background: var(--surface); touch-action: none; }
.host-workspace .signature-dialog .signature-typed-preview { touch-action: auto; }
.host-workspace .signature-dialog-actions { justify-content: flex-end; }
@media (max-width: 767px) {
  .host-workspace .ui-dialog.signature-dialog { width: 100vw; }
  .host-workspace .ui-dialog.signature-dialog .ui-sheet { max-height: 100dvh; }
  .host-workspace .signature-dialog-actions { flex-direction: column; align-items: stretch; }
}
```
If `grep -c -- "--control-h:" App/app/static/tokens.css` is 0, STOP. In `base.html` change `host2.css?v=20261022-0281` to `host2.css?v=20261022-0282`. Commit `0282 step 4`.

5. **Strings.** Add `entity.signature.*` keys. In `App/app/host_i18n.py`, directly above `STRINGS["vi"] = dict(_VI_STRINGS)`:
```python
# 0282: the locked signature and its signing dialog.
_SIGNATURE_0282_STRINGS = {
    "en": {
        "entity.signature.add": "Add signature",
        "entity.signature.edit": "Edit signature",
        "entity.signature.none": "No signature yet",
        "entity.signature.locked_alt": "Saved signature",
        "entity.signature.dialog_title": "Your signature",
        "entity.signature.mode_draw": "Draw",
        "entity.signature.mode_type": "Type",
        "entity.signature.draw_hint": "Sign here with a finger or the mouse",
        "entity.signature.type_label": "Your name",
        "entity.signature.use": "Use this signature",
        "entity.signature.cancel": "Cancel",
        "entity.signature.unsaved": "Press Save to keep it.",
    },
    "cs": {
        "entity.signature.add": "Přidat podpis",
        "entity.signature.edit": "Upravit podpis",
        "entity.signature.none": "Zatím bez podpisu",
        "entity.signature.locked_alt": "Uložený podpis",
        "entity.signature.dialog_title": "Váš podpis",
        "entity.signature.mode_draw": "Nakreslit",
        "entity.signature.mode_type": "Napsat",
        "entity.signature.draw_hint": "Podepište se prstem nebo myší",
        "entity.signature.type_label": "Vaše jméno",
        "entity.signature.use": "Použít tento podpis",
        "entity.signature.cancel": "Zrušit",
        "entity.signature.unsaved": "Uložte, aby se zachoval.",
    },
}
for _lang, _strings in _SIGNATURE_0282_STRINGS.items():
    STRINGS[_lang].update(_strings)

```
At the end of `App/app/host_vi_i18n.py`:
```python

# 0282: the locked signature and its signing dialog.
STRINGS.update({
    "entity.signature.add": "Thêm chữ ký",
    "entity.signature.edit": "Sửa chữ ký",
    "entity.signature.none": "Chưa có chữ ký",
    "entity.signature.locked_alt": "Chữ ký đã lưu",
    "entity.signature.dialog_title": "Chữ ký của bạn",
    "entity.signature.mode_draw": "Vẽ",
    "entity.signature.mode_type": "Gõ tên",
    "entity.signature.draw_hint": "Ký bằng ngón tay hoặc chuột",
    "entity.signature.type_label": "Tên của bạn",
    "entity.signature.use": "Dùng chữ ký này",
    "entity.signature.cancel": "Hủy",
    "entity.signature.unsaved": "Nhấn Lưu để giữ lại.",
})
```
Commit `0282 step 5`.

6. **Test.** Write `App/tests/test_0282_signature_dialog_browser.py` (Playwright Chromium; copy the server, seed and login fixture pattern from `App/tests/test_0252_touch_sweep_browser.py`, reading only its fixtures; the page is `/apartments/<demo apartment id>?view=settings&section=reporting&lang=en`, as in `tests/test_fee_signature_0209.py` line 62). For widths 390 (touch, `has_touch=True`, `is_mobile=True`) and 1280:
   - before Edit no canvas is visible (`canvas` inside `[data-host-signature]` has `is_visible() == False`) and `[data-signature-open]` is visible;
   - click Edit: `dialog[data-signature-dialog]` has the `open` attribute; at 390 the draw canvas is at least 340 px wide and 160 px tall; at 1280 at least 600 px wide;
   - Type tab, fill `Nguyễn Thu Phương`, click Use: the dialog closes, `input[name=signature_drawn]` value starts with `data:image/png;base64,`, `[data-signature-preview]` is visible, and `document.fonts.check('48px "UbyHost Signature"')` is true;
   - draw: open again, Draw tab, mouse/touch drag across the canvas (`page.mouse` down, move in 5 steps, up), Use: the hidden value changed again;
   - submit the form's Save button and reload: `[data-signature-preview]` has a `src` that starts with `data:image/`.
   Commit `0282 step 6`.

7. **Shots.** From `App/`: `.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out /mnt/project-files/notify-sign/0282 --pages "/apartments/1?view=settings&section=reporting" --widths 390,820,1280,2000 2>&1 | tail -3` (use the demo apartment id from the seed if 1 is wrong). Then add, inside your test file or a one-off script under `/tmp`, screenshots of the open dialog in Type mode at 390 and 1280 to `/mnt/project-files/notify-sign/0282/dialog-type-390.png` and `dialog-type-1280.png`. Look at each once.

8. **Decision line.** Append to `docs/context/decisions.md`: `- 2026-10-22 [deps] Typed signatures use the self-hosted Dancing Script font (SIL OFL 1.1, App/app/static/fonts/) and our own canvas code; no JS library. "pdfcart" does not exist and signaturepdf is AGPL, so no code was copied (owner asked for the feature).` Commit `0282 step 8`.

## 5. Do not touch

`App/app/routes/admin.py`, the guest signature (`signature.js`, guest templates), PDF code. Hard rules 2 (no third-party request: the font is local), 3, 6, 7.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_0282_signature_dialog_browser.py tests/test_fee_signature_0209.py tests/test_stay_fee_signature.py tests/test_static_versions.py tests/test_design_lint.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped)
- `.venv/bin/python -m pytest tests/test_onboarding_wizard*.py tests/test_design_setup_wizard_browser.py -q --tb=short -x -rs 2>&1 | tail -15` (skip a glob that matches nothing)
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] Locked, greyed preview on the page; no live canvas outside the dialog.
- [ ] Edit opens a same-tab dialog: wide on desktop, a tall sheet on phone; Draw and Type both save a PNG.
- [ ] The font loads from `/static/fonts/`, no outside request.
- [ ] Shots in `/mnt/project-files/notify-sign/0282/`.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0282-report.md`, as in TEMPLATE §9.

## Risk list (for the reviewer)

`host.js` block, the macro, `host2.css` tail, the font licence file.

## Owner steps

1. After deploy, on the phone open a property, Settings, Reporting & fees: the signature is grey; tap Edit signature, try Type, press Use, then Save.
