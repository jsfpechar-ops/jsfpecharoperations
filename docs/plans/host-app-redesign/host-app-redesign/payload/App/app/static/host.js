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
      var count = alerts.querySelectorAll('[data-notification]').length;
      var label = alerts.querySelector('[data-host-alert-count]');
      if (label && label.textContent !== String(count)) label.textContent = String(count);
      alerts.hidden = count === 0;
    }).observe(alerts, {childList: true, subtree: true});
  }
  // Invalid controls inside closed sections must be visible before the browser
  // moves focus there. Keep every field in the form so partial section edits
  // never clear values in another section.
  document.addEventListener('invalid', function (event) {
    var parent = event.target.closest('details');
    while (parent) { parent.open = true; parent = parent.parentElement.closest('details'); }
  }, true);
})();
