(function () {
  "use strict";

  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-copy"));
        if (!target) return;
        target.select();
        try {
          var copied = navigator.clipboard
            ? navigator.clipboard.writeText(target.value)
            : Promise.resolve(document.execCommand("copy"));
          Promise.resolve(copied).then(function () {
            var original = button.textContent;
            button.textContent = "Copied";
            setTimeout(function () { button.textContent = original; }, 1400);
          });
        } catch (error) {
          // The field stays selected so it can still be copied manually.
        }
      });
    });
  }

  function initClickableRows() {
    document.querySelectorAll("tr[data-href]").forEach(function (row) {
      function openRow() {
        window.location.assign(row.getAttribute("data-href"));
      }

      row.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input, select, textarea, label")) return;
        openRow();
      });

      row.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        if (event.target !== row) return;
        event.preventDefault();
        openRow();
      });
    });
  }

  function initSidebar() {
    var toggle = document.querySelector("[data-sidebar-toggle]");
    var close = document.querySelector("[data-sidebar-close]");
    if (!toggle) return;

    function setOpen(open) {
      document.body.classList.toggle("sidebar-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }

    toggle.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("sidebar-open"));
    });
    if (close) close.addEventListener("click", function () { setOpen(false); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });
  }

  function initDetailsLinks() {
    function openTarget(hash) {
      if (!hash || hash.charAt(0) !== "#") return;
      var target = document.getElementById(hash.slice(1));
      if (target && target.tagName === "DETAILS") target.open = true;
    }
    document.querySelectorAll("[data-open-details]").forEach(function (link) {
      link.addEventListener("click", function () { openTarget(link.hash); });
    });
    openTarget(window.location.hash);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCopy();
    initClickableRows();
    initSidebar();
    initDetailsLinks();
  });
})();
