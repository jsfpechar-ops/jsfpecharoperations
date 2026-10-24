/* 0302: the Leon (AI) chat on the guest guide (stay link and QR page).
 *
 * Progressive enhancement: the guide works without this file. The form is
 * hidden in the HTML and shown here, so a browser without JavaScript never
 * posts to the JSON endpoint. GET <data-leon-url> returns
 * {"messages": [{"role", "kind", "text", "at"}], "open_questions": n};
 * POST it with the form field "message" returns {"kind", "text", "asked_host"}.
 * All text is set with textContent, never parsed as HTML. No storage, no cookies,
 * no third-party requests. While a question waits for the host, the history is
 * fetched again every 60 seconds while the page is visible, at most 30 times.
 * Kinds (0300): answer, ask_host, refuse, about_me, emergency, unclear,
 * smalltalk, passed, too_long, slow_down, paused. "emergency" (112 and the
 * host's emergency card) gets an urgent block and is announced at once;
 * "ask_host" and "passed" get the "asked your host" accent; the rest are plain.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-leon]");
  if (!root || !window.fetch || !window.FormData) return;

  var url = root.getAttribute("data-leon-url");
  var log = root.querySelector("[data-leon-log]");
  var waiting = root.querySelector("[data-leon-waiting]");
  var form = root.querySelector("[data-leon-form]");
  var input = root.querySelector("[data-leon-input]");
  var count = root.querySelector("[data-leon-count]");
  var send = root.querySelector("[data-leon-send]");
  var error = root.querySelector("[data-leon-error]");
  var jump = document.querySelector("[data-leon-jump]");
  var meta = document.querySelector('meta[name="csrf-token"]');
  var MAX = parseInt(input.getAttribute("maxlength"), 10) || 500;
  var POLL_MS = 60000;
  var POLL_MAX = 30;
  var polls = 0;
  var timer = null;
  var busy = false;

  function text(name) {
    return root.getAttribute("data-" + name) || "";
  }

  function bubble(role, kind, body) {
    var item = document.createElement("div");
    var extra = "";
    if (role === "leon" && kind === "emergency") extra = " g-leon-msg--emergency";
    else if (role === "leon" && (kind === "ask_host" || kind === "passed")) extra = " g-leon-msg--asked";
    item.className = "g-leon-msg g-leon-msg--" + role + extra;
    item.setAttribute("data-leon-msg", role);
    item.setAttribute("data-leon-kind", kind || "");
    if (extra === " g-leon-msg--emergency") item.setAttribute("role", "alert");
    var who = document.createElement("p");
    who.className = "g-leon-who";
    who.textContent = role === "guest" ? text("label-you") : role === "host" ? text("label-host") : text("label-leon");
    var said = document.createElement("p");
    said.className = "g-leon-text";
    said.textContent = body;
    item.appendChild(who);
    item.appendChild(said);
    log.appendChild(item);
    log.hidden = false;
    return item;
  }

  function setWaiting(on) {
    waiting.hidden = !on;
    if (on && !timer && polls < POLL_MAX) {
      timer = window.setInterval(poll, POLL_MS);
    } else if (!on && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function render(data) {
    while (log.firstChild) log.removeChild(log.firstChild);
    (data.messages || []).forEach(function (m) {
      bubble(m.role, m.kind, m.text);
    });
    log.hidden = !log.firstChild;
    setWaiting((data.open_questions || 0) > 0);
  }

  function history() {
    return fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then(render);
  }

  function poll() {
    if (document.hidden) return;
    polls += 1;
    if (polls >= POLL_MAX) setWaiting(false);
    history().catch(function () {});
  }

  function setBusy(on) {
    busy = on;
    input.disabled = on;
    send.disabled = on;
    send.textContent = on ? text("text-sending") : text("text-send");
    root.setAttribute("aria-busy", on ? "true" : "false");
  }

  function updateCount() {
    var n = input.value.length;
    count.textContent = n + " / " + MAX;
    count.classList.toggle("g-leon-count--near", n > MAX - 50);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var message = input.value.trim();
    if (busy || !message) return;
    showError("");
    var body = new FormData(form);
    body.set("message", message);
    setBusy(true);
    fetch(url, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-CSRF-Token": meta ? meta.getAttribute("content") : "" },
    })
      .then(function (response) {
        var json = (response.headers.get("content-type") || "").indexOf("application/json") === 0;
        if (!response.ok || !json) {
          var expired = response.status === 403 || response.status === 404 || (response.ok && !json);
          throw new Error(expired ? "reload" : "error");
        }
        return response.json();
      })
      .then(function (reply) {
        bubble("guest", "", message);
        var last = bubble("leon", reply.kind, reply.text || "");
        input.value = "";
        updateCount();
        if (reply.asked_host) setWaiting(true);
        if (last.scrollIntoView) last.scrollIntoView({ block: "nearest" });
      })
      .catch(function (problem) {
        showError(problem && problem.message === "reload" ? text("text-reload") : text("text-error"));
      })
      .then(function () {
        setBusy(false);
        input.focus();
      });
  });

  input.addEventListener("input", updateCount);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && timer) history().catch(function () {});
  });

  form.hidden = false;
  if (jump) jump.hidden = false;
  updateCount();
  history().catch(function () {});
})();
