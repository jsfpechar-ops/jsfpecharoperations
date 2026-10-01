(function () {
  "use strict";

  var SIDEBAR_KEY = "ubyhost-sidebar-collapsed";
  var NAV_BREAKPOINT = 960;

  document.documentElement.classList.add("has-js");

  function isCompact() {
    return window.innerWidth <= NAV_BREAKPOINT;
  }

  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-copy"));
        if (!target) return;
        // Works for form fields and for blocks of text such as the portal
        // message, so a host never has to select a paragraph by hand.
        var text = typeof target.value === "string" ? target.value : target.textContent;
        if (typeof target.select === "function") {
          target.select();
        } else if (window.getSelection && document.createRange) {
          var range = document.createRange();
          range.selectNodeContents(target);
          var selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }
        try {
          var copied = navigator.clipboard
            ? navigator.clipboard.writeText(text)
            : Promise.resolve(document.execCommand("copy"));
          Promise.resolve(copied).then(function () {
            button.classList.add("copied");
            var label = button.getAttribute("data-copied-label");
            var copyLabel = button.getAttribute("data-copy-label") || button.getAttribute("aria-label") || "";
            var original = button.textContent;
            // Icon buttons keep their icon and show the label beside it; writing
            // to textContent would delete the SVG and never bring it back.
            var slot = button.querySelector("[data-copy-label-slot]");
            if (label) {
              if (slot) {
                slot.textContent = label;
                slot.hidden = false;
                button.classList.add("is-labelled");
              } else {
                button.textContent = label;
              }
              button.setAttribute("aria-label", label);
            }
            setTimeout(function () {
              button.classList.remove("copied");
              if (label) {
                if (slot) {
                  slot.textContent = "";
                  slot.hidden = true;
                  button.classList.remove("is-labelled");
                } else {
                  button.textContent = original;
                }
              }
              if (copyLabel) button.setAttribute("aria-label", copyLabel);
            }, 1600);
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
    var width = panel.offsetWidth || 180;
    var left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
    var top = Math.min(rect.bottom + 6, window.innerHeight - panel.offsetHeight - 8);
    panel.style.left = left + "px";
    panel.style.top = top + "px";
  }

  function initBirthDateInputs() {
    function formatDigits(digits) {
      var out = digits.slice(0, 2);
      if (digits.length > 2) out += "." + digits.slice(2, 4);
      if (digits.length > 4) out += "." + digits.slice(4, 8);
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

  function initControllerFields() {
    document.querySelectorAll("[data-controller-same-toggle]").forEach(function (checkbox) {
      var panel = document.getElementById(checkbox.getAttribute("data-controller-target"));
      if (!panel) return;
      var select = panel.querySelector("select");
      function sync() {
        panel.hidden = checkbox.checked;
        if (select) {
          select.disabled = checkbox.checked;
          select.required = !checkbox.checked;
        }
      }
      checkbox.addEventListener("change", sync);
      sync();
    });
  }

  function initFeeTemplateCopy() {
    var source = document.getElementById("fee-copy-source");
    var button = document.getElementById("fee-copy-apply");
    if (!source || !button) return;
    button.addEventListener("click", function () {
      var option = source.options[source.selectedIndex];
      if (!option || !option.value) return;
      var values = {
        stay_fee_rate_czk: option.getAttribute("data-rate"),
        stay_fee_cadence: option.getAttribute("data-cadence"),
        stay_fee_vs: option.getAttribute("data-vs"),
        stay_fee_council_account: option.getAttribute("data-account"),
        stay_fee_authority_name: option.getAttribute("data-authority-name"),
        stay_fee_authority_address: option.getAttribute("data-authority-address"),
        stay_fee_authority_contact: option.getAttribute("data-authority-contact"),
        stay_fee_payee: option.getAttribute("data-payee"),
        stay_fee_instruction: option.getAttribute("data-instruction")
      };
      Object.keys(values).forEach(function (id) {
        var field = document.getElementById(id);
        if (field) field.value = values[id] || "";
      });
    });
  }

  function initHousebookPdfExport() {
    var dialog = document.getElementById("housebook-pdf-dialog");
    if (!dialog) return;
    var form = document.getElementById("housebook-pdf-form");
    document.querySelectorAll("[data-housebook-pdf-export]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var pageFrom = document.getElementById("from");
        var pageTo = document.getElementById("to");
        var pageApt = document.getElementById("apartment");
        var fromInput = document.getElementById("pdf_export_from");
        var toInput = document.getElementById("pdf_export_to");
        var aptInput = document.getElementById("pdf_export_apartment");
        if (pageFrom && fromInput && pageFrom.value) fromInput.value = pageFrom.value;
        if (pageTo && toInput && pageTo.value) toInput.value = pageTo.value;
        if (pageApt && aptInput) aptInput.value = pageApt.value;
        if (typeof dialog.showModal === "function") dialog.showModal();
      });
    });
    dialog.querySelectorAll("[data-housebook-pdf-cancel]").forEach(function (button) {
      button.addEventListener("click", function () { dialog.close(); });
    });
    if (form) {
      form.addEventListener("submit", function () {
        dialog.close();
      });
    }
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
        if (window.ubyhostSkeleton) window.ubyhostSkeleton.start();
        window.location.assign(row.getAttribute("data-href"));
      }

      row.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input, select, textarea, label, form, .row-menu, .row-actions")) return;
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

  /* The menu behaves like a drawer on a phone and like a collapsible rail on a
     desktop, so the same markup serves both without a second navigation. */
  function initNavigation() {
    var collapse = document.querySelector("[data-sidebar-collapse]");
    var expand = document.querySelector("[data-sidebar-expand]");
    var toggles = document.querySelectorAll("[data-nav-toggle]");
    var closers = document.querySelectorAll("[data-nav-close]");

    var sidebar = document.getElementById("app-sidebar");
    var main = document.getElementById("main-content");
    function setDrawer(open) {
      var wasOpen = document.body.classList.contains("nav-open");
      document.body.classList.toggle("nav-open", open);
      if (sidebar) sidebar.inert = isCompact() && !open;
      if (main) main.inert = isCompact() && open;
      if (open && sidebar) {
        var first = sidebar.querySelector("a, button");
        if (first) first.focus();
      } else if (wasOpen && toggles.length) toggles[0].focus();
      toggles.forEach(function (button) {
        button.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    function setCollapsed(collapsed) {
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      if (collapse) {
        collapse.setAttribute("aria-expanded", collapsed ? "false" : "true");
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
    if (stored === "1") document.body.classList.add("sidebar-collapsed");

    if (collapse) collapse.addEventListener("click", function () { setCollapsed(true); });
    if (expand) expand.addEventListener("click", function () { setCollapsed(false); });

    toggles.forEach(function (button) {
      button.addEventListener("click", function () {
        setDrawer(!document.body.classList.contains("nav-open"));
      });
    });
    closers.forEach(function (button) {
      button.addEventListener("click", function () { setDrawer(false); });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
        setDrawer(false);
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Tab" || !sidebar || !document.body.classList.contains("nav-open")) return;
      var focusable = Array.from(sidebar.querySelectorAll("a, button, summary, input, select")).filter(function (el) {
        return !el.disabled && el.getClientRects().length > 0;
      });
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    document.addEventListener("host:close-navigation", function () { setDrawer(false); });
    window.addEventListener("resize", function () { setDrawer(false); });
    setDrawer(false);
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
        if (!open) {
          panel.classList.remove("hidden");
          var focusable = panel.querySelector("input, select, textarea, button");
          if (focusable) focusable.focus({ preventScroll: true });
          panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      });
    });
    document.querySelectorAll("[data-close-panel]").forEach(function (button) {
      button.addEventListener("click", function () {
        var panel = button.closest(".action-panel");
        if (panel) panel.classList.add("hidden");
      });
    });
    if (new URLSearchParams(window.location.search).get("new") === "1") {
      var addPanel = document.getElementById("add-stay-panel");
      if (addPanel) {
        addPanel.classList.remove("hidden");
        var first = addPanel.querySelector("input, select, textarea");
        if (first) first.focus();
      }
    }
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

  function initNotifications() {
    document.querySelectorAll("form[data-notification-dismiss]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var notification = form.closest("[data-notification]");
        var data = new FormData(form);
        fetch(form.action, {
          method: "POST",
          body: data,
          credentials: "same-origin",
          headers: { "X-Requested-With": "fetch" }
        }).then(function (response) {
          if (!response.ok) throw new Error("Dismiss failed");
          if (notification) {
            notification.classList.add("leaving");
            setTimeout(function () { notification.remove(); }, 230);
          }
        }).catch(function () {
          // Keep the ordinary form as a dependable fallback if the network or
          // browser does not support the smooth path.
          form.submit();
        });
      });
    });
  }

  /* Confirmations of something you just did should not push the page down;
     they appear over it and leave on their own. */
  function initToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
      function dismiss() {
        toast.classList.add("leaving");
        setTimeout(function () { toast.remove(); }, 220);
      }
      var close = toast.querySelector("[data-toast-close]");
      if (close) close.addEventListener("click", dismiss);
      if (!toast.hasAttribute("data-toast-sticky")) {
        setTimeout(dismiss, 4200);
      }
    });
  }

  /* Changing a filter is the intent; making you press Apply afterwards is
     a click the app can take on itself. */
  function initAutoFilters() {
    document.querySelectorAll("form[data-auto-submit]").forEach(function (form) {
      form.querySelectorAll("select, input[type=date]").forEach(function (input) {
        input.addEventListener("change", function () {
          if (input.type === "date") {
            var range = form.querySelector('input[name="range"]');
            if (range) range.value = "custom";
          }
          form.requestSubmit ? form.requestSubmit() : form.submit();
        });
      });
    });
  }

  function randomPassword() {
    var chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    var extra = "-_";
    var out = "";
    if (window.crypto && window.crypto.getRandomValues) {
      var bytes = new Uint8Array(20);
      window.crypto.getRandomValues(bytes);
      for (var i = 0; i < bytes.length; i += 1) {
        out += chars.charAt(bytes[i] % chars.length);
      }
      out += extra.charAt(bytes[0] % extra.length);
      out += String((bytes[1] % 9) + 1);
    } else {
      while (out.length < 18) out += chars.charAt(Math.floor(Math.random() * chars.length));
      out += "_7";
    }
    return out;
  }

  function fillGeneratedPassword(input) {
    if (!input) return;
    input.value = randomPassword();
  }

  function initGeneratedPasswords() {
    document.querySelectorAll("[data-generated-password]").forEach(function (input) {
      if (!input.value) fillGeneratedPassword(input);
    });

    document.querySelectorAll("[data-generate-password]").forEach(function (button) {
      button.addEventListener("click", function () {
        var field = button.closest(".password-generate");
        if (!field) return;
        var input = field.querySelector("[data-generated-password]");
        fillGeneratedPassword(input);
        if (input) {
          input.focus();
          input.select();
        }
      });
    });
  }

  function initResetPasswordDialog() {
    var dialog = document.getElementById("reset-password-dialog");
    var form = document.getElementById("reset-password-form");
    var label = document.getElementById("reset-password-label");
    if (!dialog || !form || !label) return;

    document.querySelectorAll("[data-reset-password]").forEach(function (button) {
      button.addEventListener("click", function () {
        var userId = button.getAttribute("data-user-id");
        var userLabel = button.getAttribute("data-user-label") || "this user";
        if (!userId) return;
        form.action = "/admin/users/" + userId + "/password";
        label.textContent = userLabel;
        form.reset();
        var passwordInput = form.querySelector("[data-generated-password]");
        fillGeneratedPassword(passwordInput);
        document.querySelectorAll(".row-menu-panel").forEach(closeRowMenu);
        if (typeof dialog.showModal === "function") dialog.showModal();
      });
    });

    dialog.querySelectorAll("[data-reset-password-cancel]").forEach(function (button) {
      button.addEventListener("click", function () { dialog.close(); });
    });
  }

  function initConfirmDialog() {
    var dialog = document.getElementById("confirm-dialog");
    var shell = document.getElementById("confirm-form");
    var title = document.getElementById("confirm-title");
    var body = document.getElementById("confirm-body");
    if (!dialog || !shell) return;
    var pendingForm = null;
    var pendingButton = null;

    function openDialog(message, form, button) {
      pendingForm = form || null;
      pendingButton = button || null;
      if (title) title.textContent = "";
      if (body) body.textContent = message || "";
      document.querySelectorAll(".row-menu-panel").forEach(closeRowMenu);
      if (typeof dialog.showModal === "function") dialog.showModal();
    }

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        if (form.dataset.confirmBypass === "1") {
          form.dataset.confirmBypass = "";
          return;
        }
        e.preventDefault();
        openDialog(form.getAttribute("data-confirm-message"), form, null);
      });
    });

    document.querySelectorAll("button[data-confirm]").forEach(function (button) {
      button.addEventListener("click", function (e) {
        if (button.dataset.confirmBypass === "1") {
          button.dataset.confirmBypass = "";
          return;
        }
        e.preventDefault();
        openDialog(button.getAttribute("data-confirm-message"), null, button);
      });
    });

    shell.addEventListener("submit", function (e) {
      e.preventDefault();
      dialog.close();
      if (pendingForm) {
        pendingForm.dataset.confirmBypass = "1";
        if (pendingForm.requestSubmit) pendingForm.requestSubmit();
        else pendingForm.submit();
        pendingForm = null;
      } else if (pendingButton) {
        pendingButton.dataset.confirmBypass = "1";
        pendingButton.click();
        pendingButton = null;
      }
    });

    dialog.querySelectorAll("[data-confirm-cancel]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        pendingForm = null;
        pendingButton = null;
        dialog.close();
      });
    });
  }

  function initPowerTools() {
    var command = document.getElementById("command-dialog");
    var input = command ? command.querySelector("[data-command-input]") : null;
    var results = command ? command.querySelector("[data-command-results]") : null;
    var shortcuts = document.getElementById("shortcuts-dialog");
    var items = null;
    var visible = [];
    var selected = 0;
    var goPrefix = false;
    var goTimer = null;
    var recentKey = "ubyhost-command-recents";
    var recents = [];
    try { recents = JSON.parse(localStorage.getItem(recentKey) || "[]"); } catch (error) { recents = []; }

    document.querySelectorAll("[data-command-shortcut]").forEach(function (hint) {
      var platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
      hint.textContent = /mac|iphone|ipad|ipod/i.test(platform) ? "⌘ K" : "Ctrl K";
    });

    function typingTarget(target) {
      return target && (target.matches("input, textarea, select") || target.isContentEditable);
    }

    function submitPost(url) {
      var form = document.createElement("form");
      form.method = "post";
      form.action = url;
      var csrf = document.querySelector('meta[name="csrf-token"]');
      if (csrf) {
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "_csrf";
        input.value = csrf.getAttribute("content") || "";
        form.appendChild(input);
      }
      document.body.appendChild(form);
      if (window.ubyhostSkeleton) window.ubyhostSkeleton.start();
      form.submit();
    }

    function runItem(item) {
      var recentId = item.url || item.label;
      recents = [recentId].concat(recents.filter(function (value) { return value !== recentId; })).slice(0, 8);
      try { localStorage.setItem(recentKey, JSON.stringify(recents)); } catch (error) {}
      if (item.copy) {
        Promise.resolve(navigator.clipboard && navigator.clipboard.writeText(item.copy)).then(function () {
          if (results) results.textContent = results.getAttribute("data-copied") || "";
          setTimeout(function () { if (command.open) command.close(); }, 450);
        });
      } else if (item.method === "post") {
        submitPost(item.url);
      } else if (item.url) {
        if (window.ubyhostSkeleton) window.ubyhostSkeleton.start();
        window.location.assign(item.url);
      }
    }

    function updateSelection() {
      if (!results) return;
      results.querySelectorAll("[role=option]").forEach(function (option, index) {
        option.classList.toggle("is-selected", index === selected);
        option.setAttribute("aria-selected", index === selected ? "true" : "false");
        if (index === selected) option.scrollIntoView({ block: "nearest" });
      });
    }

    function render(query) {
      if (!results || !items) return;
      var words = String(query || "").toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
      function fuzzyScore(haystack, word) {
        var cursor = -1;
        var score = 0;
        for (var i = 0; i < word.length; i += 1) {
          var next = haystack.indexOf(word.charAt(i), cursor + 1);
          if (next < 0) return -1;
          score += next - cursor;
          cursor = next;
        }
        return score;
      }
      visible = items.map(function (item) {
        var haystack = [item.label, item.meta, item.group, item.keywords].join(" ").toLocaleLowerCase();
        var scores = words.map(function (word) { return fuzzyScore(haystack, word); });
        if (scores.some(function (score) { return score < 0; })) return null;
        var id = item.url || item.label;
        return { item: item, score: scores.reduce(function (sum, score) { return sum + score; }, 0), recent: recents.indexOf(id) };
      }).filter(Boolean).sort(function (a, b) {
        if (!words.length) {
          var ar = a.recent < 0 ? 999 : a.recent;
          var br = b.recent < 0 ? 999 : b.recent;
          if (ar !== br) return ar - br;
        }
        return a.score - b.score;
      }).slice(0, 14).map(function (entry) { return entry.item; });
      selected = 0;
      results.textContent = "";
      results.removeAttribute("aria-busy");
      if (!visible.length) {
        var empty = document.createElement("p");
        empty.className = "command-empty";
        empty.textContent = results.getAttribute("data-empty") || "";
        results.appendChild(empty);
        return;
      }
      visible.forEach(function (item, index) {
        var option = document.createElement("button");
        option.type = "button";
        option.className = "command-option";
        option.setAttribute("role", "option");
        if (typeof item.tone === "number") {
          var mark = document.createElement("span");
          mark.className = "property-mark property-tone-" + item.tone;
          mark.textContent = item.label.charAt(0);
          mark.setAttribute("aria-hidden", "true");
          option.appendChild(mark);
        }
        var copy = document.createElement("span");
        copy.className = "command-option-copy";
        var title = document.createElement("strong");
        title.textContent = item.label;
        copy.appendChild(title);
        if (item.meta) {
          var meta = document.createElement("small");
          meta.textContent = item.meta;
          copy.appendChild(meta);
        }
        option.appendChild(copy);
        var group = document.createElement("span");
        group.className = "command-group";
        group.textContent = item.group || "";
        option.appendChild(group);
        option.addEventListener("mouseenter", function () { selected = index; updateSelection(); });
        option.addEventListener("click", function () { runItem(item); });
        results.appendChild(option);
      });
      updateSelection();
    }

    function openCommand() {
      if (!command || !input) return;
      document.dispatchEvent(new Event("host:close-navigation"));
      if (!command.open) {
        if (typeof command.showModal === "function") command.showModal();
        else command.setAttribute("open", "");
      }
      input.value = "";
      window.requestAnimationFrame(function () { input.focus(); });
      if (items) {
        render("");
      } else {
        if (results) {
          results.textContent = "";
          results.setAttribute("aria-busy", "true");
          for (var s = 0; s < 4; s += 1) {
            var placeholder = document.createElement("span");
            placeholder.className = "skeleton skeleton-line command-skeleton";
            placeholder.setAttribute("aria-hidden", "true");
            results.appendChild(placeholder);
          }
        }
        fetch("/api/command-palette", { credentials: "same-origin" })
          .then(function (response) { return response.ok ? response.json() : { items: [] }; })
          .then(function (data) { items = data.items || []; render(input.value); })
          .catch(function () { items = []; render(input.value); });
      }
    }

    function closeCommand() {
      if (!command) return;
      if (typeof command.close === "function") command.close();
      else command.removeAttribute("open");
    }

    document.querySelectorAll("[data-command-open]").forEach(function (button) {
      button.addEventListener("click", openCommand);
    });
    document.querySelectorAll("[data-command-close]").forEach(function (button) {
      button.addEventListener("click", closeCommand);
    });
    if (command) {
      command.addEventListener("click", function (event) {
        if (event.target === command) closeCommand();
      });
    }
    document.querySelectorAll("[data-shortcuts-open]").forEach(function (button) {
      button.addEventListener("click", function () {
        document.dispatchEvent(new Event("host:close-navigation"));
        if (shortcuts && typeof shortcuts.showModal === "function") shortcuts.showModal();
      });
    });
    document.querySelectorAll("[data-shortcuts-close]").forEach(function (button) {
      button.addEventListener("click", function () { if (shortcuts) shortcuts.close(); });
    });

    if (input) {
      input.addEventListener("input", function () { render(input.value); });
      input.addEventListener("keydown", function (event) {
        if ((event.key === "ArrowDown" || event.key === "ArrowUp") && visible.length) {
          event.preventDefault();
          selected = (selected + (event.key === "ArrowDown" ? 1 : -1) + visible.length) % visible.length;
          updateSelection();
        } else if (event.key === "Enter" && visible[selected]) {
          event.preventDefault();
          runItem(visible[selected]);
        }
      });
    }

    document.addEventListener("keydown", function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openCommand();
        return;
      }
      if (typingTarget(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "?" && shortcuts) {
        event.preventDefault();
        document.dispatchEvent(new Event("host:close-navigation"));
        shortcuts.showModal();
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        openCommand();
        return;
      }
      if (event.key === "g") {
        goPrefix = true;
        clearTimeout(goTimer);
        goTimer = setTimeout(function () { goPrefix = false; }, 900);
        return;
      }
      if (goPrefix) {
        var routes = { d: "/", s: "/reservations", r: "/submissions", h: "/housebook" };
        goPrefix = false;
        if (routes[event.key]) {
          event.preventDefault();
          window.location.assign(routes[event.key]);
        }
        return;
      }
      var rows = Array.prototype.slice.call(document.querySelectorAll("tr[data-href]"));
      if (!rows.length) return;
      var current = rows.findIndex(function (row) { return row.classList.contains("row-selected"); });
      if (event.key === "j" || event.key === "k") {
        event.preventDefault();
        if (current >= 0) rows[current].classList.remove("row-selected");
        current = event.key === "j" ? Math.min(current + 1, rows.length - 1) : Math.max(current < 0 ? 0 : current - 1, 0);
        rows[current].classList.add("row-selected");
        rows[current].focus({ preventScroll: true });
        rows[current].scrollIntoView({ block: "nearest" });
      } else if (event.key === "Enter" && current >= 0) {
        window.location.assign(rows[current].getAttribute("data-href"));
      }
    });
  }

  function initSavedViews() {
    var key = "ubyhost-saved-stay-views";
    var container = document.querySelector("[data-saved-views]");
    var button = document.querySelector("[data-save-view]");
    var views = [];
    try { views = JSON.parse(localStorage.getItem(key) || "[]"); } catch (error) { views = []; }

    function render() {
      if (!container) return;
      container.textContent = "";
      if (!views.length) return;
      var label = document.createElement("div");
      label.className = "nav-label";
      label.textContent = container.getAttribute("data-label") || "";
      container.appendChild(label);
      views.forEach(function (view) {
        var link = document.createElement("a");
        link.href = view.url;
        link.textContent = view.label;
        container.appendChild(link);
      });
    }

    if (button) {
      button.addEventListener("click", function () {
        var filter = button.closest("form");
        var apartment = filter && filter.querySelector('[name="apartment"]');
        var status = filter && filter.querySelector('[name="status"]');
        var parts = [];
        if (apartment && apartment.value) parts.push(apartment.options[apartment.selectedIndex].text.trim());
        if (status && status.value !== "active") parts.push(status.options[status.selectedIndex].text.trim());
        var label = parts.join(" · ") || document.title;
        var url = window.location.pathname + window.location.search;
        views = views.filter(function (view) { return view.url !== url; });
        views.unshift({ label: label, url: url });
        views = views.slice(0, 5);
        try { localStorage.setItem(key, JSON.stringify(views)); } catch (error) {}
        button.textContent = button.getAttribute("data-saved-label") || button.textContent;
        render();
      });
    }
    render();
  }

  function initInlineEdit() {
    document.querySelectorAll("form[data-inline-edit]").forEach(function (form) {
      var status = form.querySelector(".inline-edit-status");
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var button = form.querySelector("[type=submit]");
        if (button) button.disabled = true;
        if (status) status.textContent = "";
        fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          headers: { "X-Requested-With": "fetch" }
        }).then(function (response) {
          if (!response.ok) throw new Error("save");
          if (status) status.textContent = form.getAttribute("data-saved") || "";
        }).catch(function () {
          if (status) status.textContent = form.getAttribute("data-error") || "";
        }).finally(function () {
          if (button) button.disabled = false;
        });
      });
    });
  }

  function initSubmitGuard() {
    // A double-click on "Create stay" sent the same stay twice and the second
    // request died on the UNIQUE index with a 500. The uid is collision proof
    // now; this is the visible half of the fix, so a click has one effect.
    document.querySelectorAll(".action-panel form").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        // A confirm dialog or a fetch handler owns this submit and may hand it
        // back, so never disable a button for a submission that did not start.
        if (event.defaultPrevented) return;
        var button = form.querySelector("[type=submit]");
        if (!button || button.disabled) return;
        button.disabled = true;
        button.setAttribute("data-submit-guard", "1");
      });
    });
    // Coming back with the browser's back button restores the button's own
    // disabled state, so clear ours on every restore.
    window.addEventListener("pageshow", function () {
      document.querySelectorAll("[data-submit-guard]").forEach(function (button) {
        button.disabled = false;
        button.removeAttribute("data-submit-guard");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCopy();
    initBirthDateInputs();
    initRowMenus();
    initClickableRows();
    initNavigation();
    initTogglePanels();
    initDismissBanners();
    initNotifications();
    initDetailsLinks();
    initAutomationFields();
    initControllerFields();
    initFeeTemplateCopy();
    initCsvExport();
    initHousebookPdfExport();
    initToasts();
    initAutoFilters();
    initGeneratedPasswords();
    initResetPasswordDialog();
    initConfirmDialog();
    initSubmitGuard();
    initPowerTools();
    initSavedViews();
    initInlineEdit();
  });
})();
