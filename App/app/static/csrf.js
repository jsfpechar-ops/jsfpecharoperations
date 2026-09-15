(function () {
  "use strict";

  var meta = document.querySelector('meta[name="csrf-token"]');
  var token = meta ? meta.getAttribute("content") : "";
  if (!token) return;

  function isProtected(form) {
    var method = (form.getAttribute("method") || "get").toLowerCase();
    if (method === "get") return false;
    try {
      var action = new URL(form.getAttribute("action") || window.location.href, window.location.href);
      return action.origin === window.location.origin && action.pathname.indexOf("/l/") !== 0;
    } catch (error) {
      return false;
    }
  }

  function attach(form) {
    if (!isProtected(form)) return;
    var input = form.querySelector('input[name="_csrf"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = "_csrf";
      form.appendChild(input);
    }
    input.value = token;
  }

  document.querySelectorAll("form").forEach(attach);
  document.addEventListener("submit", function (event) {
    attach(event.target);
  }, true);
})();
