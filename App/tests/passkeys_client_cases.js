/* Deterministic regressions for passkeys.js. WebAuthn, fetch and time are
   controlled; pass realDocument to exercise the rendered controls in a browser. */
"use strict";
const PASSKEY_CASES = [
  "late-capability", "late-options", "late-conditional-credential",
  "stalled-fetch", "stalled-body", "stalled-sheet", "stalled-login-post", "html-challenge", "null-credential",
  "redirected-response", "invalid-json", "missing-challenge", "missing-redirect", "rate-limit",
  "cancel-and-retry", "duplicate-click", "capability-unavailable", "success", "add-timeout"
];

async function runPasskeyClientCase(source, name, realDocument) {
  function assert(ok, message) { if (!ok) throw new Error(name + ": " + message); }
  function deferred() {
    var resolve, reject;
    var promise = new Promise(function (yes, no) { resolve = yes; reject = no; });
    return { promise: promise, resolve: resolve, reject: reject };
  }
  async function flush() { for (var i = 0; i < 60; i++) await Promise.resolve(); }
  var timers = new Map(), nextTimer = 0;
  function later(fn, ms) { var id = ++nextTimer; timers.set(id, { fn: fn, ms: ms }); return id; }
  function clear(id) { timers.delete(id); }
  async function advance(ms) {
    for (var entry of Array.from(timers.entries())) {
      if (entry[1].ms <= ms && timers.has(entry[0])) {
        timers.delete(entry[0]); entry[1].fn();
      }
    }
    await flush();
  }
  // The standalone V8 runner has no DOM globals. Browser/Node runs use their
  // native abort implementation; this tiny fallback is only for that runner.
  class FallbackAbortController {
    constructor() {
      var listeners = new Set();
      this.signal = {
        aborted: false,
        addEventListener: function (_event, fn) { listeners.add(fn); },
        removeEventListener: function (_event, fn) { listeners.delete(fn); }
      };
      this.abort = function () {
        if (this.signal.aborted) return;
        this.signal.aborted = true;
        for (var fn of Array.from(listeners)) fn();
      };
    }
  }
  var Abort = typeof AbortController === "undefined" ? FallbackAbortController : AbortController;
  var DomError = typeof DOMException === "undefined" ? class extends Error {
    constructor(message, kind) { super(message); this.name = kind; }
  } : DOMException;
  function mockButton() {
    var listeners = {};
    return { disabled: false, hidden: false,
      addEventListener: function (event, fn) { listeners[event] = fn; },
      click: function () { if (!this.disabled && listeners.click) listeners.click(); },
      getAttribute: function () { return ""; },
      closest: function () { return scope; }
    };
  }
  var login = mockButton(), add = mockButton();
  var error = { hidden: true, textContent: "", getAttribute: function () { return "Please try again."; } };
  var scope = { hidden: true, querySelector: function () { return error; } };
  var form = { querySelector: function () { return { value: "/stays?view=today" }; } };
  var meta = { getAttribute: function () { return "test-csrf"; } };
  var doc = {
    readyState: "complete", getElementById: function () { return null; },
    querySelector: function (selector) {
      return ({
        'meta[name="csrf-token"]': meta, "[data-passkey-login]": scope,
        "[data-passkey-login-button]": login, "[data-login-form]": form,
        "[data-passkey-error]": error
      })[selector] || null;
    },
    querySelectorAll: function (selector) {
      return selector === "[data-passkey-supported]" ? [scope] :
        selector === "[data-passkey-add]" && name === "add-timeout" ? [add] : [];
    }
  };
  if (realDocument) {
    doc = realDocument;
    login = doc.querySelector("[data-passkey-login-button]");
    scope = doc.querySelector("[data-passkey-login]");
    error = doc.querySelector("[data-passkey-error]");
    doc.querySelector('[data-login-form] input[name="next"]').value = "/stays?view=today";
    if (name === "add-timeout") {
      add = doc.createElement("button");
      add.setAttribute("data-passkey-add", "");
      add.textContent = "Add passkey";
      doc.body.appendChild(add);
    }
  }
  var calls = [], gets = [], creates = [], redirects = [];
  var cap = deferred(), delayed = deferred(), sheet = deferred();
  var conditionalCredential = deferred(), attempts = 0, completions = 0;
  var credential = { toJSON: function () { return { id: "test-credential", type: "public-key" }; } };
  function response(data, status, kind, redirected) {
    return {
      ok: !status || status < 400, redirected: !!redirected,
      headers: { get: function () { return kind || "application/json; charset=utf-8"; } },
      json: function () { return Promise.resolve(data); }
    };
  }
  var PublicKey = {
    parseRequestOptionsFromJSON: function (json) {
      if (!json.challenge) throw new TypeError("Missing challenge");
      return json;
    },
    parseCreationOptionsFromJSON: function (json) { return json; },
    isConditionalMediationAvailable: function () {
      if (name === "capability-unavailable") return Promise.reject(new Error("No autofill"));
      return name === "late-capability" ? cap.promise : Promise.resolve(
        name === "late-options" || name === "late-conditional-credential"
      );
    }
  };
  var nav = { credentials: {
    create: function (options) { creates.push(options); return Promise.resolve(credential); },
    get: function (options) {
      gets.push(options);
      if (options.mediation === "conditional") return conditionalCredential.promise;
      if (name === "stalled-sheet" && gets.filter(function (g) { return !g.mediation; }).length === 1) return sheet.promise;
      if (name === "cancel-and-retry" && gets.length === 1) return Promise.reject(new DomError("", "NotAllowedError"));
      if (name === "duplicate-click") return sheet.promise;
      if (name === "null-credential" && gets.length === 1) return Promise.resolve(null);
      return Promise.resolve(credential);
    }
  } };
  function fetchMock(url, options) {
    calls.push({ url: url, options: options });
    if (url === "/login/passkey") {
      completions++;
      if (name === "stalled-login-post" && completions === 1) return delayed.promise;
      if (name === "missing-redirect" && completions === 1) return Promise.resolve(response({}));
      return Promise.resolve(response({ redirect: "/stays?view=today" }));
    }
    if (url === "/account/passkeys/options") return delayed.promise;
    attempts++;
    var first = attempts === 1;
    if (name === "late-options" && first) return delayed.promise;
    if (name === "stalled-fetch" && first) return delayed.promise;
    if (name === "stalled-body" && first) {
      var body = response({});
      body.json = function () { return delayed.promise; };
      return Promise.resolve(body);
    }
    if (name === "html-challenge" && first) return Promise.resolve(response({}, 403, "text/html"));
    if (name === "redirected-response" && first) return Promise.resolve(response({ challenge: "AQ" }, 200, null, true));
    if (name === "invalid-json" && first) {
      var invalid = response({});
      invalid.json = function () { return Promise.reject(new SyntaxError("invalid JSON")); };
      return Promise.resolve(invalid);
    }
    if (name === "missing-challenge" && first) return Promise.resolve(response({}));
    if (name === "rate-limit" && first) return Promise.resolve(response({ error: "Wait a moment." }, 429));
    return Promise.resolve(response({ challenge: "AQ", timeout: 60000 }));
  }
  var win = { PublicKeyCredential: PublicKey, location: { assign: function (url) { redirects.push(url); } } };
  new Function("window", "document", "navigator", "PublicKeyCredential", "fetch",
    "AbortController", "DOMException", "setTimeout", "clearTimeout", source)(
      win, doc, nav, PublicKey, fetchMock, Abort, DomError, later, clear);
  await flush();
  function loginPosts() { return calls.filter(function (c) { return c.url === "/login/passkey"; }); }
  function manualGets() { return gets.filter(function (g) { return !g.mediation; }); }
  function retryable(visible) {
    assert(!login.disabled, "login button stayed disabled");
    assert(redirects.length === 0, "unexpected navigation");
    if (visible) assert(!error.hidden && error.textContent, "no recovery message");
  }
  async function retry() {
    login.click(); await flush();
    assert(redirects.length === 1, "retry did not log in");
    assert(!login.disabled, "success left a disabled button for Back navigation");
  }
  if (name === "add-timeout") {
    add.click(); await flush(); assert(add.disabled, "add did not start");
    await advance(15000);
    assert(!add.disabled, "add button stayed disabled after network timeout");
    return name;
  }
  if (name === "capability-unavailable") assert(error.hidden, "unsupported autofill showed an error");
  login.click(); await flush();
  if (name === "late-capability") {
    cap.resolve(true); await flush();
    assert(gets.length === 1 && !gets[0].mediation, "late autofill competed with the button");
    assert(attempts === 1, "late capability check spent another options request");
  } else if (name === "late-options") {
    delayed.resolve(response({ challenge: "AQ" })); await flush();
    assert(gets.length === 1 && !gets[0].mediation, "cancelled options started another ceremony");
    assert(loginPosts().length === 1, "cancelled options submitted a credential");
    assert(calls[0].options.signal.aborted, "cancelled options fetch was not aborted");
  } else if (name === "late-conditional-credential") {
    conditionalCredential.resolve(credential); await flush();
    assert(loginPosts().length === 1, "cancelled autofill logged in with a late credential");
    assert(gets[0].signal.aborted, "autofill was not aborted");
  } else if (name === "stalled-fetch" || name === "stalled-body") {
    assert(login.disabled, "login did not start");
    await advance(15000); retryable(true);
    assert(calls[0].options.signal.aborted, "timed-out fetch was not aborted");
    delayed.resolve(name === "stalled-fetch" ? response({ challenge: "AQ" }) : { challenge: "AQ" });
    await flush(); assert(gets.length === 0, "timed-out response started a stale ceremony");
    await retry();
  } else if (name === "stalled-login-post") {
    await advance(15000); retryable(true);
    assert(loginPosts()[0].options.signal.aborted, "login submission was not aborted");
    delayed.resolve(response({ redirect: "/stale" })); await flush();
    assert(redirects.length === 0, "late login submission navigated");
    await retry();
  } else if (name === "missing-redirect" || name === "null-credential") {
    retryable(true); await retry();
  } else if (name === "stalled-sheet") {
    await advance(90000); retryable(true);
    assert(gets[0].signal.aborted, "timed-out system sheet was not aborted");
    sheet.resolve(credential); await flush();
    assert(loginPosts().length === 0, "late system sheet submitted a stale credential");
    await retry();
  } else if (["html-challenge", "redirected-response", "invalid-json", "missing-challenge", "rate-limit"].includes(name)) {
    retryable(true); assert(gets.length === 0, "bad response opened a system sheet");
    if (name === "rate-limit") assert(error.textContent === "Wait a moment.", "server error was lost");
    assert(attempts === 1, "failure automatically spent another options request");
    await retry(); assert(error.hidden, "retry kept a stale error visible");
  } else if (name === "cancel-and-retry") {
    retryable(false); assert(error.hidden, "cancelling was reported as a failure"); await retry();
  } else if (name === "duplicate-click") {
    login.click(); await flush();
    assert(attempts === 1 && manualGets().length === 1, "duplicate tap started two logins");
    sheet.resolve(credential); await flush();
    assert(loginPosts().length === 1, "duplicate login completion");
  }
  if (!["stalled-fetch", "stalled-body", "stalled-sheet", "stalled-login-post", "add-timeout"].includes(name)) {
    assert(redirects.length === 1, "login did not complete exactly once");
    assert(!login.disabled, "success left the button disabled");
  }
  var posted = loginPosts()[0];
  assert(posted && JSON.parse(posted.options.body).next === "/stays?view=today", "next destination was lost");
  assert(posted.options.headers["X-CSRF-Token"], "CSRF proof was lost");
  assert(posted.options.credentials === "same-origin", "same-origin credentials were lost");
  assert(timers.size === 0, "settled operations leaked timers");
  return name;
}
if (typeof module !== "undefined") module.exports = { PASSKEY_CASES, runPasskeyClientCase };
