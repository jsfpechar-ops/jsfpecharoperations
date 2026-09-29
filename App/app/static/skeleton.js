/* Navigation skeleton.
   UbyHost is server-rendered: every page arrives complete, so nothing here
   renders content. The only wait a user feels is the gap between a click and
   the next page (a feed sync, a police send, a slow filter). If that gap
   passes DELAY_MS, the current page's main content is swapped for static
   placeholder blocks so the click visibly "took". Fast navigations never
   show it. Opt a link or form out with data-no-skeleton. */
(function () {
  "use strict";
  var DELAY_MS = 400;
  var SAFETY_MS = 15000;
  var DOWNLOAD_RE = /\.(pdf|zip|csv|ics|txt)$/i;
  var timer = null;
  var safety = null;

  function placeholder() {
    return document.querySelector("[data-page-skeleton]");
  }

  function show() {
    timer = null;
    var el = placeholder();
    if (!el || !el.parentElement) return;
    el.parentElement.setAttribute("aria-busy", "true");
    el.hidden = false;
    // A download, a 204 or a cancelled navigation leaves us on this page.
    // Never keep the content hidden for longer than this.
    safety = window.setTimeout(hide, SAFETY_MS);
  }

  function hide() {
    window.clearTimeout(timer);
    window.clearTimeout(safety);
    timer = null;
    safety = null;
    var el = placeholder();
    if (!el || !el.parentElement) return;
    el.hidden = true;
    el.parentElement.removeAttribute("aria-busy");
  }

  function start() {
    if (timer || !placeholder()) return;
    timer = window.setTimeout(show, DELAY_MS);
  }

  function isDownload(url) {
    try {
      return DOWNLOAD_RE.test(new URL(url, window.location.href).pathname);
    } catch (error) {
      return true;
    }
  }

  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest ? event.target.closest("a[href]") : null;
    if (!link) return;
    if (link.closest("[data-no-skeleton]") || link.hasAttribute("download")) return;
    if (link.target && link.target !== "_self") return;
    if (link.origin !== window.location.origin) return;
    if (link.hash && link.pathname === window.location.pathname &&
        link.search === window.location.search) return;
    if (isDownload(link.href)) return;
    start();
  });

  // Registered on document, so it runs after every form's own submit
  // handler; a handler that took the submit over has set defaultPrevented.
  document.addEventListener("submit", function (event) {
    if (event.defaultPrevented) return;
    var form = event.target;
    if (!form || form.closest("[data-no-skeleton]") || form.closest("dialog")) return;
    var submitter = event.submitter;
    var target = (submitter && submitter.getAttribute("formtarget")) || form.getAttribute("target");
    if (target && target !== "_self") return;
    var action = (submitter && submitter.getAttribute("formaction")) || form.getAttribute("action") || window.location.href;
    if (isDownload(action)) return;
    start();
  });

  // The back button restores this page from the cache with the placeholder
  // still showing, so always start clean.
  window.addEventListener("pageshow", hide);

  // For navigations started from script (clickable rows, the command palette).
  window.ubyhostSkeleton = { start: start, hide: hide };
})();
