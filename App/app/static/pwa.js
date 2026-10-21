/* Installable app (brief 0203): registers the service worker, keeps its
   offline page in the page's language, and drives Settings > Phone app and the
   login page hint. Without JavaScript, Settings still says how to add the app. */
(function () {
  "use strict";

  var standalone = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  var ua = navigator.userAgent || "";
  // iPadOS reports itself as a Mac; the touch screen tells them apart.
  var ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var installed = standalone;
  var deferredPrompt = null;

  function show(selector, visible) {
    document.querySelectorAll(selector).forEach(function (el) {
      el.hidden = !visible;
    });
  }

  // --- service worker ------------------------------------------------------

  var workerReady = "serviceWorker" in navigator
    ? navigator.serviceWorker.register("/sw.js", { scope: "/" }).then(function () {
      return navigator.serviceWorker.ready;
    })
    : Promise.reject(new Error("no service worker"));

  workerReady.then(function (registration) {
    if (registration.active) {
      registration.active.postMessage({ type: "lang", lang: document.documentElement.lang || "en" });
    }
  }).catch(function () {
    /* The app works without it; only the offline page and alerts need it. */
  });

  // --- Settings > Phone app --------------------------------------------------

  function paintInstall() {
    if (!document.querySelector("[data-pwa-install-row]")) return;
    show("[data-pwa-installed]", installed);
    show("[data-pwa-ios]", !installed && ios);
    show("[data-pwa-install]", !installed && !ios && !!deferredPrompt);
    show("[data-pwa-other]", !installed && !ios && !deferredPrompt);
  }

  window.addEventListener("beforeinstallprompt", function (event) {
    // Settings offers the button, so the browser's own install bar stays away.
    event.preventDefault();
    deferredPrompt = event;
    paintInstall();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    installed = true;
    paintInstall();
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest("[data-pwa-install]") : null;
    if (!button || !deferredPrompt) return;
    var prompt = deferredPrompt;
    deferredPrompt = null;
    prompt.prompt();
    prompt.userChoice.then(paintInstall, paintInstall);
  });

  // Login page: inside the installed app an e-mail link opens the browser instead.
  show("[data-pwa-standalone]", standalone);

  paintInstall();
})();
