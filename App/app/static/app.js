(function () {
  "use strict";

  var SIDEBAR_KEY = "ubyhost-sidebar-collapsed";

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
        if (event.target.closest("a, button, input, select, textarea, label, form")) return;
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
    var collapse = document.querySelector("[data-sidebar-collapse]");
    var expand = document.querySelector("[data-sidebar-expand]");
    if (!collapse && !expand) return;

    function setCollapsed(collapsed) {
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      if (collapse) {
        collapse.setAttribute("aria-expanded", collapsed ? "false" : "true");
        collapse.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
      }
      try {
        localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
      } catch (error) {
        // Private browsing may block storage.
      }
    }

    var stored = null;
    try {
      stored = localStorage.getItem(SIDEBAR_KEY);
    } catch (error) {
      stored = null;
    }
    if (stored === "1") {
      setCollapsed(true);
    }

    if (collapse) {
      collapse.addEventListener("click", function () {
        setCollapsed(!document.body.classList.contains("sidebar-collapsed"));
      });
    }
    if (expand) {
      expand.addEventListener("click", function () {
        setCollapsed(false);
      });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !document.body.classList.contains("sidebar-collapsed")) {
        setCollapsed(true);
      }
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
