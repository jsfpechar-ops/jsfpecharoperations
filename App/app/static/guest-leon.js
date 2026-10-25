/* 0352: the Leon (AI) chat on the guest guide (stay link and QR page).
 *
 * Progressive enhancement: the guide works without this file. The form is
 * hidden in the HTML and shown here, so a browser without JavaScript never
 * posts to the JSON endpoint. GET <data-leon-url> returns
 * {"messages": [{"role", "kind", "text", "at"}], "open_questions": n};
 * POST it with the form field "message" returns {"kind", "text", "asked_host"}.
 * All text is set with textContent, never parsed as HTML. No storage, no cookies,
 * no third-party requests. While a question waits for the host, the history is
 * fetched again every 60 seconds while the page is visible, at most 30 times.
 * Kinds (0350): answer, ask_host, refuse, about_me, emergency, unclear,
 * smalltalk, passed, too_long, slow_down, paused, busy. "emergency" (112 and the
 * host's emergency card) gets an urgent block and is announced at once;
 * "ask_host" and "passed" get the "asked your host" accent; the rest are plain.
 * One request in flight per page (owner, 2026-10-24): while Leon is answering,
 * the textarea stays usable and Send queues the text (shown at once as the
 * guest's bubble, marked "sending after Leon's reply"). When the reply arrives,
 * the queued texts go as ONE message, joined with a newline: whole texts only,
 * as many as fit in MAX characters; the rest wait for the next reply. "busy"
 * (another device of this chat is waiting for Leon, 0350) puts the texts back
 * and retries every RETRY_MS, at most RETRY_MAX times. Each batch carries a
 * random client_id that it keeps on every retry, so a retry after a lost or
 * timed-out response (TIMEOUT_MS) gets the stored reply, never a second turn.
 * A failed batch stays queued; the next Send (even with an empty box) resends it.
 * After each reply the history is fetched again (other devices of the stay);
 * while it says "answering" (a reload mid-reply) it is fetched every ANSWER_MS.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-leon]");
  if (!root || !window.fetch || !window.FormData || !window.FormData.prototype.set) return;

  var url = root.getAttribute("data-leon-url");
  var log = root.querySelector("[data-leon-log]");
  var waiting = root.querySelector("[data-leon-waiting]");
  var form = root.querySelector("[data-leon-form]");
  var input = root.querySelector("[data-leon-input]");
  var count = root.querySelector("[data-leon-count]");
  var error = root.querySelector("[data-leon-error]");
  var jump = document.querySelector("[data-leon-jump]");
  var meta = document.querySelector('meta[name="csrf-token"]');
  var MAX = parseInt(input.getAttribute("maxlength"), 10) || 500;
  var POLL_MS = 60000;
  var POLL_MAX = 30;
  var polls = 0;
  var timer = null;
  var RETRY_MS = 4000;
  var RETRY_MAX = 20;
  var TIMEOUT_MS = 50000; // above the server's worst case (0310: 20 s timeout, one retry)
  var ANSWER_MS = 3000;
  var ANSWER_MAX = 20;
  var retries = 0;
  var answerPolls = 0;
  var batch = null; // {id, items: [{text, node}]}: the message on its way, or waiting to be resent
  var inFlight = false;
  var queue = []; // [{text, node}] typed while a reply is pending
  var stale = false; // a history render was skipped (or another device spoke): fetch it after the reply

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
    if (inFlight) {
      stale = true;
      return;
    }
    while (log.firstChild) log.removeChild(log.firstChild);
    (data.messages || []).forEach(function (m) {
      bubble(m.role, m.kind, m.text);
    });
    (batch ? batch.items : []).concat(queue).forEach(function (item) {
      log.appendChild(item.node);
    });
    log.hidden = !log.firstChild;
    setWaiting((data.open_questions || 0) > 0);
    if (data.answering && answerPolls < ANSWER_MAX) {
      answerPolls += 1;
      window.setTimeout(function () { history().catch(function () {}); }, ANSWER_MS);
    }
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

  function updateCount() {
    var n = input.value.length;
    count.textContent = n + " / " + MAX;
    count.classList.toggle("g-leon-count--near", n > MAX - 50);
    count.hidden = n <= MAX - 50;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 132) + "px";
  }

  function mark(item, state) {
    // state: "sending", "queued" or "" (sent and answered)
    var note = item.node.querySelector("[data-leon-note]");
    if (!state) {
      if (note) item.node.removeChild(note);
      return;
    }
    if (!note) {
      note = document.createElement("p");
      note.className = "g-leon-queued";
      item.node.appendChild(note);
    }
    note.setAttribute("data-leon-note", state);
    note.textContent = state === "sending" ? text("text-sending") : text("text-queued");
  }

  function newId() {
    var bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (var i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
    return Array.prototype.map.call(bytes, function (b) { return (b + 256).toString(16).slice(1); }).join("");
  }

  function take() {
    // Whole texts from the front of the queue, joined with a newline, while they fit in MAX.
    var items = [queue.shift()];
    var length = items[0].text.length;
    while (queue.length && length + 1 + queue[0].text.length <= MAX) {
      length += 1 + queue[0].text.length;
      items.push(queue.shift());
    }
    return { id: newId(), items: items };
  }

  function markAll(state) {
    batch.items.forEach(function (item) { mark(item, state); });
  }

  function flush() {
    if (inFlight) return;
    if (!batch) {
      if (!queue.length) return;
      batch = take();
    }
    inFlight = true;
    markAll("sending");
    root.setAttribute("aria-busy", "true");
    var body = new FormData(form);
    body.set("message", batch.items.map(function (item) { return item.text; }).join("\n"));
    body.set("client_id", batch.id);
    var abort = window.AbortController ? new window.AbortController() : null;
    var timeout = abort ? window.setTimeout(function () { abort.abort(); }, TIMEOUT_MS) : null;
    fetch(url, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      signal: abort ? abort.signal : undefined,
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
        inFlight = false;
        if (reply.kind === "busy") {
          // Another device of this chat is waiting for Leon: same batch, same id, a little later.
          markAll("queued");
          retries += 1;
          if (retries > RETRY_MAX) {
            retries = 0;
            showError(text("text-error"));
          } else {
            window.setTimeout(flush, RETRY_MS);
          }
          return;
        }
        retries = 0;
        markAll("");
        batch = null;
        var last = bubble("leon", reply.kind, reply.text || "");
        if (reply.asked_host) setWaiting(true);
        if (last.scrollIntoView) last.scrollIntoView({ block: "nearest" });
        if (queue.length) {
          stale = true;
          flush();
        } else {
          stale = false;
          answerPolls = 0;
          history().catch(function () {});
        }
      })
      .catch(function (problem) {
        inFlight = false;
        markAll("queued");
        showError(problem && problem.message === "reload" ? text("text-reload") : text("text-error"));
      })
      .then(function () {
        if (timeout) window.clearTimeout(timeout);
        if (!inFlight) root.setAttribute("aria-busy", "false");
        if (!inFlight && stale && !queue.length && !batch) {
          stale = false;
          history().catch(function () {});
        }
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var message = input.value.trim();
    if (!message && !queue.length && !batch) return;
    showError("");
    if (message) {
      var item = { text: message, node: bubble("guest", "", message) };
      if (inFlight || batch) mark(item, "queued");
      queue.push(item);
      input.value = "";
      updateCount();
      if (item.node.scrollIntoView) item.node.scrollIntoView({ block: "nearest" });
    }
    retries = 0;
    flush();
    input.focus();
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
