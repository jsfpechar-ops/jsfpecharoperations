/* Progressive enhancement only: native links, forms and details work without JS. */
(function () {
  'use strict';
  function revealTarget() {
    var id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (_) { return; }
    var target = id && document.getElementById(id);
    if (!target) return;
    var parent = target;
    while (parent) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
    target.scrollIntoView({block: 'start'});
  }
  window.addEventListener('hashchange', revealTarget);
  revealTarget();
  document.addEventListener('click', function (event) {
    document.querySelectorAll('[data-host-account], .host-tools').forEach(function (menu) {
      if (!menu.contains(event.target)) menu.open = false;
    });
    var anchor = event.target.closest('a[href^="#"]');
    if (anchor && anchor.hash === window.location.hash) revealTarget();
  });
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('[data-host-account][open], .host-tools[open]').forEach(function (menu) {
      menu.open = false;
      menu.querySelector('summary').focus();
    });
  });
  var alerts = document.querySelector('[data-host-alerts]');
  if (alerts) {
    new MutationObserver(function () {
      alerts.hidden = alerts.querySelectorAll('[data-notification]').length === 0;
    }).observe(alerts, {childList: true, subtree: true});
  }
  // Invalid controls inside closed sections must be visible before the browser
  // moves focus there. Keep every field in the form so partial section edits
  // never clear values in another section.
  document.addEventListener('invalid', function (event) {
    var parent = event.target.closest('details');
    while (parent) { parent.open = true; parent = parent.parentElement.closest('details'); }
  }, true);

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

  // The demo form opens its POST response in a new tab. Refresh this step
  // when the host comes back so the registration result is visible.
  var wizardDemo = document.querySelector('[data-wizard-demo]');
  if (wizardDemo) {
    var demoOpened = false;
    wizardDemo.addEventListener('submit', function () { demoOpened = true; });
    function refreshDemo() {
      if (!demoOpened) return;
      demoOpened = false;
      window.location.reload();
    }
    window.addEventListener('focus', refreshDemo);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') refreshDemo();
    });
  }

  // 0203: while the demo stay waits for its registration, coming back to this
  // tab reloads the step, so a finished demo shows "Continue" at once.
  // Only on a tab switch: a reload on load or focus could loop.
  if (document.querySelector('[data-wizard-demo-wait]')) {
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') window.location.reload();
    });
  }

  // 0205: a whole account pasted into any of the three boxes splits itself:
  // 19-2000145399/0800, 2000145399/0800 or a Czech IBAN.
  document.querySelectorAll('[data-account-parts]').forEach(function (group) {
    var prefix = group.querySelector('[name="account_prefix"]');
    var number = group.querySelector('[name="account_number"]');
    var bank = group.querySelector('[name="account_bank"]');
    if (!prefix || !number || !bank) return;
    function strip(digits) { return digits.replace(/^0+/, ''); }
    function split(text) {
      var plain = text.replace(/\s+/g, '').toUpperCase();
      var local = plain.match(/^(?:(\d{1,6})-)?(\d{2,10})\/(\d{4})$/);
      if (local) return [local[1] || '', local[2], local[3]];
      var iban = plain.match(/^CZ\d{2}(\d{4})(\d{6})(\d{10})$/);
      if (iban) return [strip(iban[2]), strip(iban[3]), iban[1]];
      return null;
    }
    [prefix, number, bank].forEach(function (input) {
      input.addEventListener('paste', function (event) {
        var text = event.clipboardData ? event.clipboardData.getData('text') : '';
        var parts = split(text || '');
        if (!parts) return;
        event.preventDefault();
        prefix.value = parts[0];
        number.value = parts[1];
        bank.value = parts[2];
        [prefix, number, bank].forEach(function (field) {
          field.dispatchEvent(new Event('input', { bubbles: true }));
        });
      });
    });
  });

  // 0205: the police abbreviation follows the web-service login as it is
  // typed (UBY-WS_ABCDE gives ABCDE), the rule of validation.mark_from_ws_user.
  // A value the host typed themselves is never replaced.
  var wsUser = document.getElementById('uby_ws_user');
  var ubyMark = document.getElementById('uby_mark');
  if (wsUser && ubyMark) {
    var markFrom = function (login) {
      var value = (login || '').trim();
      var lower = value.toLowerCase();
      if (lower.indexOf('uby-tws') === 0) return '';
      if (lower.indexOf('uby-ws_') === 0) return value.slice(7).toUpperCase().slice(0, 6);
      if (lower.indexOf('uby-ws') === 0) return value.slice(6).toUpperCase().slice(0, 6);
      return '';
    };
    var autoMark = !ubyMark.value || ubyMark.value === markFrom(wsUser.value);
    ubyMark.addEventListener('input', function (event) {
      if (event.isTrusted) autoMark = !ubyMark.value;
    });
    wsUser.addEventListener('input', function () {
      if (!autoMark) return;
      ubyMark.value = markFrom(wsUser.value);
      ubyMark.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  document.querySelectorAll('[data-phone-country-code]').forEach(function (input) {
    function digits(value) { return value.replace(/\D/g, '').slice(0, 3); }
    input.addEventListener('input', function () { input.value = digits(input.value); });
    input.addEventListener('paste', function (event) {
      if (!event.clipboardData) return;
      event.preventDefault();
      input.value = digits(event.clipboardData.getData('text'));
      input.dispatchEvent(new Event('input', {bubbles: true}));
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === '+') event.preventDefault();
    });
  });

  var adjustMode = document.getElementById('adjust-mode');
  if (adjustMode) {
    var syncAdjust = function () {
      var people = adjustMode.value === 'people';
      document.querySelectorAll('[data-adjust-people]').forEach(function (field) { field.hidden = !people; });
      document.querySelectorAll('[data-adjust-days]').forEach(function (field) { field.hidden = people; });
    };
    adjustMode.addEventListener('change', syncAdjust);
    syncAdjust();
  }
  // Preview the same buffered wall-clock hours used when the code is issued.
  function updateDoorCodeWindows() {
    document.querySelectorAll('[data-door-code-window]').forEach(function (preview) {
      var cin = document.querySelector('select[name="checkin_hour"]');
      var cout = document.querySelector('select[name="checkout_hour"]');
      var from = cin ? cin.value : preview.dataset.checkin;
      var until = cout ? cout.value : preview.dataset.checkout;
      var complete = from !== '' && until !== '' &&
        Number.isInteger(Number(from)) && Number.isInteger(Number(until)) &&
        Number(from) >= 0 && Number(from) <= 23 && Number(until) >= 0 && Number(until) <= 23;
      preview.querySelector('[data-window-values]').hidden = !complete;
      preview.querySelector('[data-window-missing]').hidden = complete;
      if (!complete) return;
      var buffer = Number(preview.dataset.buffer);
      var start = Number(from) - buffer;
      var end = Number(until) + buffer;
      var clock = function (hour) { return String(((hour % 24) + 24) % 24).padStart(2, '0') + ':00'; };
      preview.querySelector('[data-window-start]').textContent =
        clock(start) + ' · ' + (start < 0 ? preview.dataset.previous : preview.dataset.arrival);
      preview.querySelector('[data-window-end]').textContent =
        clock(end) + ' · ' + (end >= 24 ? preview.dataset.next : preview.dataset.departure);
    });
  }
  document.addEventListener('change', function (event) {
    if (event.target.matches('select[name="checkin_hour"], select[name="checkout_hour"]')) updateDoorCodeWindows();
  });
  updateDoorCodeWindows();
})();
