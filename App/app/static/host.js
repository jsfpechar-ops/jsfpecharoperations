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

  document.querySelectorAll('[data-host-signature]').forEach(function (block) {
    var canvas = block.querySelector('canvas');
    var hidden = block.querySelector('input[name="signature_drawn"]');
    var clear = block.querySelector('[data-signature-clear]');
    if (!canvas || !hidden) return;
    var ctx = canvas.getContext('2d');
    var drawing = false;
    function resize() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var ratio = window.devicePixelRatio || 1;
      var width = Math.round(rect.width * ratio);
      var height = Math.round(rect.height * ratio);
      if (canvas.width === width && canvas.height === height) return;
      var snapshot = hidden.value && hidden.value.indexOf('data:image/') === 0 ? hidden.value : '';
      canvas.width = width;
      canvas.height = height;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.lineWidth = 2.2;
      ctx.lineCap = 'round';
      ctx.strokeStyle = '#20201e';
      if (snapshot) {
        var image = new Image();
        image.onload = function () { ctx.drawImage(image, 0, 0, rect.width, rect.height); };
        image.src = snapshot;
      }
    }
    function point(event) {
      var rect = canvas.getBoundingClientRect();
      var source = event.touches ? event.touches[0] : event;
      return { x: source.clientX - rect.left, y: source.clientY - rect.top };
    }
    canvas.addEventListener('pointerdown', function (event) {
      drawing = true;
      canvas.setPointerCapture(event.pointerId);
      var start = point(event);
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!drawing) return;
      var next = point(event);
      ctx.lineTo(next.x, next.y);
      ctx.stroke();
    });
    canvas.addEventListener('pointerup', function () {
      if (!drawing) return;
      drawing = false;
      hidden.value = canvas.toDataURL('image/png');
    });
    if (clear) clear.addEventListener('click', function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      hidden.value = '';
    });
    resize();
    if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);
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
})();
