(function () {
  "use strict";
  var KEY = "ubyhost-theme";

  function current() {
    try { return localStorage.getItem(KEY) || "system"; }
    catch (error) { return "system"; }
  }

  function apply(value) {
    if (value === "light" || value === "dark") {
      document.documentElement.dataset.theme = value;
    } else {
      document.documentElement.removeAttribute("data-theme");
      value = "system";
    }
    try { localStorage.setItem(KEY, value); } catch (error) {}
    document.querySelectorAll("[data-theme-value]").forEach(function (button) {
      var selected = button.getAttribute("data-theme-value") === value;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(current());
    document.querySelectorAll("[data-theme-value]").forEach(function (button) {
      button.addEventListener("click", function () {
        apply(button.getAttribute("data-theme-value"));
      });
    });
  });
})();
