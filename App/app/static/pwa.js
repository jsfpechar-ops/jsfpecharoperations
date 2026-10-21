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

  // --- Settings > urgent alerts (brief 0206) --------------------------------

  var pushRow = document.querySelector("[data-push-row]");
  var pushSupported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var pageLang = document.documentElement.lang || "en";

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": csrfMeta ? csrfMeta.getAttribute("content") : ""
      },
      body: JSON.stringify(body || {})
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.error || "");
        return data;
      });
    });
  }

  function keyBytes(value) {
    var b64 = String(value || "").replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4) b64 += "=";
    var raw = atob(b64);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  // A subscription made for an older server key cannot receive alerts any more.
  function sameKey(subscription, key) {
    var have = subscription.options && subscription.options.applicationServerKey;
    if (!have) return true;
    var a = new Uint8Array(have);
    var b = keyBytes(key);
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  function currentSubscription() {
    return workerReady.then(function (registration) {
      return registration.pushManager.getSubscription();
    });
  }

  function paintPush(state) {
    show("[data-push-on]", state === "off");
    show("[data-push-state-on]", state === "on");
    show("[data-push-controls]", state === "on");
    show("[data-push-ios-first]", state === "ios");
    show("[data-push-unsupported]", state === "unsupported");
    show("[data-push-denied]", state === "denied");
  }

  function pushMessage(selector, text) {
    show("[data-push-status]", false);
    show("[data-push-error]", false);
    var el = document.querySelector(selector);
    if (!el) return;
    el.textContent = text || el.getAttribute("data-generic") || "";
    el.hidden = false;
  }

  function initPush() {
    if (!pushRow) return;
    if (ios && !standalone) return paintPush("ios");
    if (!pushSupported) return paintPush("unsupported");
    if (Notification.permission === "denied") return paintPush("denied");
    paintPush("off");
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      if (!sameKey(subscription, pushRow.getAttribute("data-push-key"))) {
        return subscription.unsubscribe();
      }
      return post("/account/push/refresh", { endpoint: subscription.endpoint, lang: pageLang }).then(function (data) {
        // Removed in Settings on another device: this browser stops too.
        if (!data.known) return subscription.unsubscribe();
        paintPush("on");
        return null;
      });
    }).catch(function () {
      paintPush("off");
    });
  }

  function turnOn() {
    // requestPermission must run inside the click, or Safari refuses.
    Notification.requestPermission().then(function (permission) {
      if (permission !== "granted") {
        paintPush(permission === "denied" ? "denied" : "off");
        return null;
      }
      return workerReady.then(function (registration) {
        return registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: keyBytes(pushRow.getAttribute("data-push-key"))
        });
      }).then(function (subscription) {
        return post("/account/push/subscribe", { subscription: subscription.toJSON(), lang: pageLang }).then(function () {
          return post("/account/push/test", { endpoint: subscription.endpoint }).catch(function () { return null; });
        });
      }).then(function () {
        window.location.reload();
      });
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  function sendTest() {
    currentSubscription().then(function (subscription) {
      if (!subscription) throw new Error("");
      return post("/account/push/test", { endpoint: subscription.endpoint });
    }).then(function (data) {
      pushMessage("[data-push-status]", data.message);
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  function turnOff() {
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      var endpoint = subscription.endpoint;
      return post("/account/push/unsubscribe", { endpoint: endpoint }).then(function () {
        return subscription.unsubscribe();
      });
    }).then(function () {
      window.location.reload();
    }).catch(function (error) {
      pushMessage("[data-push-error]", error && error.message);
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target.closest ? event.target.closest("[data-push-on], [data-push-test], [data-push-off]") : null;
    if (!target || !pushRow) return;
    if (target.hasAttribute("data-push-on")) turnOn();
    else if (target.hasAttribute("data-push-test")) sendTest();
    else turnOff();
  });

  // Logging out turns alerts off on this device, so a shared computer stops
  // showing the host's alerts. The logout itself never waits more than 1.5 s.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || form.getAttribute("action") !== "/logout" || form.hasAttribute("data-push-cleared")) return;
    if (!pushSupported || Notification.permission !== "granted") return;
    event.preventDefault();
    form.setAttribute("data-push-cleared", "");
    var sent = false;
    function leave() {
      if (sent) return;
      sent = true;
      form.submit();
    }
    var timer = setTimeout(leave, 1500);
    currentSubscription().then(function (subscription) {
      if (!subscription) return null;
      return post("/account/push/unsubscribe", { endpoint: subscription.endpoint }).catch(function () {
        return null;
      }).then(function () {
        return subscription.unsubscribe();
      });
    }).catch(function () {
      return null;
    }).then(function () {
      clearTimeout(timer);
      leave();
    });
  });

  initPush();
})();
