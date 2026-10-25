// 0404: the Leon setup import step reloads itself while the listing is being fetched.
(function () {
  if (!document.querySelector("[data-leon-import-wait]")) return;
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    if (tries > 30) { clearInterval(timer); return; }
    if (document.hidden) return;
    window.location.reload();
  }, 10000);
})();

// 0405: the test chat posts by fetch and appends bubbles; without JS the form posts the page.
(function () {
  var box = document.querySelector("[data-leon-try]");
  if (!box) return;
  var form = box.querySelector("[data-leon-try-form]");
  var log = box.querySelector("[data-leon-try-log]");
  var input = form.querySelector("input[name=message]");
  function bubble(cls, role, text, note) {
    var li = document.createElement("li");
    li.className = cls;
    li.setAttribute("data-role", role);
    li.textContent = text;
    if (note) {
      var p = document.createElement("p");
      p.className = "ui-sub";
      p.textContent = note;
      li.appendChild(p);
    }
    log.appendChild(li);
    li.scrollIntoView({ block: "nearest" });
  }
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    var body = new FormData(form);
    body.set("message", text);
    bubble("havel-bubble", "host", text);
    input.value = "";
    input.disabled = true;
    fetch(box.getAttribute("data-leon-try-url"), {
      method: "POST",
      body: body,
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        bubble("havel-answer", "leon", d.text, d.note);
        input.disabled = d.left <= 0;
        if (d.cap) {
          var cap = document.createElement("p");
          cap.className = "ui-sub"; cap.setAttribute("data-leon-try-cap", ""); cap.textContent = d.cap;
          box.appendChild(cap);
        }
        if (!input.disabled) input.focus();
      })
      .catch(function () { input.disabled = false; });
  });
})();
