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
            button.classList.add("copied");
            button.setAttribute("aria-label", "Copied");
            setTimeout(function () {
              button.classList.remove("copied");
              button.setAttribute("aria-label", "Copy");
            }, 1400);
          });
        } catch (error) {
          // The field stays selected so it can still be copied manually.
        }
      });
    });
  }

  function rowMenuHome(panel) {
    if (!panel._rowMenuHome) {
      panel._rowMenuHome = panel.parentElement;
    }
    return panel._rowMenuHome;
  }

  function rowMenuTrigger(panel) {
    if (panel._rowMenuTrigger) return panel._rowMenuTrigger;
    var home = rowMenuHome(panel);
    return home ? home.querySelector(".row-menu-trigger") : null;
  }

  function closeRowMenu(panel) {
    panel.hidden = true;
    panel.classList.remove("is-open");
    panel.style.position = "";
    panel.style.left = "";
    panel.style.top = "";
    panel.style.zIndex = "";
    var home = rowMenuHome(panel);
    if (home && panel.parentElement !== home) {
      home.appendChild(panel);
    }
    var trigger = rowMenuTrigger(panel);
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    panel._rowMenuTrigger = null;
  }

  function positionRowMenu(trigger, panel) {
    rowMenuHome(panel);
    panel._rowMenuTrigger = trigger;
    if (panel.parentElement !== document.body) {
      document.body.appendChild(panel);
    }
    panel.hidden = false;
    panel.classList.add("is-open");
    panel.style.position = "fixed";
    panel.style.zIndex = "10000";
    var rect = trigger.getBoundingClientRect();
    var width = panel.offsetWidth || 168;
    var left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
    var top = Math.min(rect.bottom + 4, window.innerHeight - panel.offsetHeight - 8);
    panel.style.left = left + "px";
    panel.style.top = top + "px";
  }

  function initBirthDateInputs() {
    function formatDigits(digits) {
      var out = digits.slice(0, 2);
      if (digits.length > 2) out += "/" + digits.slice(2, 4);
      if (digits.length > 4) out += "/" + digits.slice(4, 8);
      return out;
    }

    document.querySelectorAll("[data-birth-date]").forEach(function (input) {
      function apply(value) {
        var digits = String(value || "").replace(/\D/g, "").slice(0, 8);
        var formatted = formatDigits(digits);
        if (input.value !== formatted) input.value = formatted;
      }

      input.addEventListener("input", function () { apply(input.value); });
      input.addEventListener("paste", function (event) {
        event.preventDefault();
        var text = (event.clipboardData || window.clipboardData).getData("text");
        apply(text);
      });
      apply(input.value);
    });
  }

  function initRowMenus() {
    function closeAll() {
      document.querySelectorAll(".row-menu-panel").forEach(closeRowMenu);
    }

    document.querySelectorAll(".row-menu-trigger").forEach(function (trigger) {
      var panel = trigger.parentElement.querySelector(".row-menu-panel");
      if (!panel) return;
      trigger.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var wasOpen = panel.classList.contains("is-open");
        closeAll();
        if (!wasOpen) {
          positionRowMenu(trigger, panel);
          trigger.setAttribute("aria-expanded", "true");
        }
      });
    });

    document.addEventListener("click", function (event) {
      if (event.target.closest(".row-menu, .row-menu-panel")) return;
      closeAll();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeAll();
    });
    window.addEventListener("resize", closeAll);
    window.addEventListener("scroll", closeAll, true);
  }

  function syncAutomationHours(select) {
    var hoursId = select.getAttribute("data-hours-target");
    if (!hoursId) return;
    var hours = document.getElementById(hoursId);
    var field = hours ? hours.closest(".field") : null;
    if (!hours || !field) return;
    var scheduled = select.value === "scheduled";
    hours.disabled = !scheduled;
    field.classList.toggle("field-disabled", !scheduled);
  }

  function initAutomationFields() {
    document.querySelectorAll("[data-automation-mode]").forEach(function (select) {
      syncAutomationHours(select);
      select.addEventListener("change", function () { syncAutomationHours(select); });
    });
  }

  function initCsvExport() {
    var dialog = document.getElementById("csv-export-dialog");
    if (!dialog) return;
    var form = document.getElementById("csv-export-form");
    var pending = { base: "", params: "" };

    document.querySelectorAll("[data-csv-export]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        pending.base = button.getAttribute("data-csv-export") || "";
        pending.params = button.getAttribute("data-csv-params") || "";
        if (typeof dialog.showModal === "function") dialog.showModal();
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var from = form.querySelector('[name="from"]').value;
      var to = form.querySelector('[name="to"]').value;
      if (!from || !to) return;
      var url = pending.base + "?from=" + encodeURIComponent(from) + "&to=" + encodeURIComponent(to);
      if (pending.params) url += (url.indexOf("?") >= 0 ? "&" : "?") + pending.params;
      window.location.assign(url);
      dialog.close();
    });

    dialog.querySelectorAll("[data-csv-cancel]").forEach(function (button) {
      button.addEventListener("click", function () { dialog.close(); });
    });
  }

  function initClickableRows() {
    document.querySelectorAll("tr[data-href]").forEach(function (row) {
      function openRow() {
        window.location.assign(row.getAttribute("data-href"));
      }

      row.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input, select, textarea, label, form, .row-menu")) return;
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

  function initTogglePanels() {
    document.querySelectorAll("[data-toggle-panel]").forEach(function (button) {
      button.addEventListener("click", function () {
        var panelId = button.getAttribute("data-toggle-panel");
        var panel = document.getElementById(panelId);
        if (!panel) return;
        var open = !panel.classList.contains("hidden");
        document.querySelectorAll(".action-panel").forEach(function (item) {
          item.classList.add("hidden");
        });
        if (!open) panel.classList.remove("hidden");
      });
    });
    document.querySelectorAll("[data-close-panel]").forEach(function (button) {
      button.addEventListener("click", function () {
        var panel = button.closest(".action-panel");
        if (panel) panel.classList.add("hidden");
      });
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

  function initDismissBanners() {
    document.querySelectorAll("[data-dismiss-banner]").forEach(function (button) {
      button.addEventListener("click", function () {
        var banner = button.closest(".dismissible-banner, .banner");
        if (banner) banner.remove();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCopy();
    initBirthDateInputs();
    initRowMenus();
    initClickableRows();
    initSidebar();
    initTogglePanels();
    initDismissBanners();
    initDetailsLinks();
    initAutomationFields();
    initCsvExport();
  });
})();
