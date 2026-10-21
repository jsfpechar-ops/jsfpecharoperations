/* UbyHost service worker (brief 0219). Served from /sw.js so its scope is the
   whole app.

   It stores exactly one response: the offline page, in the host's language.
   App pages are never stored (they are no-store and carry guest data), and
   /static files are never stored either: they are versioned with ?v= and the
   browser caches them already, so a deploy can never hide behind an old copy
   here. Bump VERSION whenever this file changes. */
"use strict";

var VERSION = "20261021-0203";
var CACHE = "ubyhost-offline-" + VERSION;
var OFFLINE_URL = "/offline";
var LANGS = ["en", "cs", "vi"];
var ICON = "/static/icons/icon-192.png?v=20261021-0203";
var BADGE = "/static/icons/badge-96.png?v=20261021-0203";

function storeOffline(lang) {
  var url = LANGS.indexOf(lang) >= 0 ? OFFLINE_URL + "?lang=" + lang : OFFLINE_URL;
  return fetch(url, { cache: "reload", credentials: "same-origin" }).then(function (response) {
    if (!response.ok) return undefined;
    return caches.open(CACHE).then(function (cache) {
      return cache.put(OFFLINE_URL, response);
    });
  });
}

self.addEventListener("install", function (event) {
  event.waitUntil(storeOffline("").then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.indexOf("ubyhost-") === 0 && key !== CACHE;
    }).map(function (key) {
      return caches.delete(key);
    }));
  }).then(function () {
    if (self.registration.navigationPreload) {
      return self.registration.navigationPreload.enable();
    }
    return undefined;
  }).then(function () {
    return self.clients.claim();
  }));
});

// Page loads go to the network as always; only a failed one gets the offline page.
self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.mode !== "navigate" || req.method !== "GET") return;
  var url = new URL(req.url);
  // Guest links (/l/...) belong to the guest, never to the host's app.
  if (url.origin !== self.location.origin || url.pathname === "/l" || url.pathname.indexOf("/l/") === 0) return;
  event.respondWith(Promise.resolve(event.preloadResponse).then(function (preloaded) {
    return preloaded || fetch(req);
  }).catch(function () {
    return caches.open(CACHE).then(function (cache) {
      return cache.match(OFFLINE_URL);
    }).then(function (offline) {
      return offline || Response.error();
    });
  }));
});

// pwa.js tells the worker the page language, so the offline page matches it.
self.addEventListener("message", function (event) {
  var data = event.data || {};
  if (data.type !== "lang" || LANGS.indexOf(data.lang) < 0) return;
  event.waitUntil(caches.open(CACHE).then(function (cache) {
    return cache.match(OFFLINE_URL);
  }).then(function (stored) {
    if (stored && stored.headers.get("Content-Language") === data.lang) return undefined;
    return storeOffline(data.lang);
  }));
});

// Urgent alerts (0204-0206). Every push shows a notification: Safari stops
// delivering to a site that pushes silently. A rotated subscription needs no
// pushsubscriptionchange handler: pwa.js sends the current one on every visit.
self.addEventListener("push", function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = {};
  }
  event.waitUntil(self.registration.showNotification(data.title || "UbyHost", {
    body: data.body || "",
    tag: data.tag || "",
    renotify: !!data.tag,
    lang: data.lang || "",
    icon: ICON,
    badge: BADGE,
    data: { url: data.url || "/" }
  }));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin);
  // Only ever open this app's own pages.
  if (target.origin !== self.location.origin) target = new URL("/", self.location.origin);
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windows) {
    for (var i = 0; i < windows.length; i++) {
      var client = windows[i];
      if (client.url.indexOf(self.location.origin) === 0 && "navigate" in client) {
        return client.focus().then(function (focused) {
          return (focused || client).navigate(target.href);
        }).catch(function () {
          return self.clients.openWindow(target.href);
        });
      }
    }
    return self.clients.openWindow(target.href);
  }));
});
