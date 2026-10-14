(function () {
  "use strict";

  var SIDEBAR_KEY = "ubyhost-sidebar-collapsed";
  var NAV_BREAKPOINT = 960;
  var manualCopyFormId = 0;
  /* 0099: every clickable list row, table or dashboard card. */
  var ROW_SELECTOR = "tr[data-href], .clickable-row[data-href]";

  document.documentElement.classList.add("has-js");

  function isCompact() {
    return window.innerWidth <= NAV_BREAKPOINT;
  }

  function feedbackRoot() {
    return document.querySelector("[data-host-feedback]");
  }

  function restoreManualCopy(record) {
    var target = record && record.target;
    if (!target) return;
    if (record.removeOnDismiss) {
      target.remove();
    } else {
      if (record.originalParent && record.originalParent.isConnected) {
        if (record.originalNextSibling && record.originalNextSibling.parentNode === record.originalParent) {
          record.originalParent.insertBefore(target, record.originalNextSibling);
        } else {
          record.originalParent.appendChild(target);
        }
      }
      target.classList.toggle("sr-only", !!record.wasSrOnly);
      target.hidden = !!record.wasHidden;
      target.removeAttribute("data-copy-manual-visible");
      if (record.originalTabindex === null) target.removeAttribute("tabindex");
      else if (record.originalTabindex !== undefined) target.setAttribute("tabindex", record.originalTabindex);
    }
    if (!record.removeOnDismiss) {
      if (record.originalFormAttribute === null) target.removeAttribute("form");
      else if (record.originalFormAttribute !== undefined) target.setAttribute("form", record.originalFormAttribute);
    }
    if (record.generatedFormId && record.originalForm && record.originalForm.id === record.generatedFormId) {
      record.originalForm.removeAttribute("id");
    }
    var root = feedbackRoot();
    var recovery = root && root.querySelector("[data-copy-recovery]");
    if (recovery) {
      var records = recovery._copyManualRecords || [];
      recovery._copyManualRecords = records.filter(function (item) { return item !== record; });
      if (!recovery._copyManualRecords.length) recovery.hidden = true;
    }
  }

  function placeManualCopy(record, destination) {
    var target = record && record.target;
    if (!target) return;
    if (record.originalForm) {
      if (!record.originalForm.id) {
        var generatedId;
        do {
          manualCopyFormId += 1;
          generatedId = "ubyhost-manual-copy-form-" + manualCopyFormId;
        } while (document.getElementById(generatedId));
        record.originalForm.id = generatedId;
        record.generatedFormId = generatedId;
      }
      target.setAttribute("form", record.originalForm.id);
    }
    target.classList.remove("sr-only");
    target.hidden = false;
    if (record.originalTabindex !== null && record.originalTabindex !== undefined) target.removeAttribute("tabindex");
    target.setAttribute("data-copy-manual-visible", "");
    destination.appendChild(target);
  }

  function announceFeedback(message, kind) {
    var root = feedbackRoot();
    if (!root) return;
    var target = root.querySelector(kind === "error" || kind === "warning" ? "[data-feedback-alert]" : "[data-feedback-live]");
    if (!target) return;
    // Set the text in this turn. A delayed write left the live region empty
    // for the copy confirmation the host (and the tests) read immediately.
    target.textContent = message;
  }

  function toastKind(toast) {
    return toast.getAttribute("data-toast-kind") || (toast.classList.contains("err") ? "error" : "info");
  }

  function initToastBehavior(toast) {
    if (toast._feedbackReady) return;
    toast._feedbackReady = true;
    var close = toast.querySelector("[data-toast-close]");
    var origin = toast._feedbackOrigin || document.activeElement;
    var kind = toastKind(toast);
    var auto = !toast.hasAttribute("data-toast-sticky") && (kind === "success" || kind === "info");
    var remaining = 7000;
    var started = 0;
    var timer = null;
    var holds = new Set();
    var dismiss = function () {
      window.clearTimeout(timer);
      (toast._copyManualTargets || []).forEach(restoreManualCopy);
      if (toast.contains(document.activeElement) && origin && origin.isConnected && typeof origin.focus === "function") origin.focus();
      toast.remove();
      pumpFeedbackQueue();
    };
    var pause = function (reason) {
      if (!auto || holds.has(reason)) return;
      if (!holds.size) {
        window.clearTimeout(timer);
        remaining = Math.max(0, remaining - (performance.now() - started));
        toast.classList.add("paused");
      }
      holds.add(reason);
    };
    var resume = function (reason) {
      if (!auto || !holds.delete(reason) || holds.size) return;
      toast.classList.remove("paused");
      start();
    };
    var start = function () {
      if (!auto || holds.size || !toast.isConnected) return;
      started = performance.now();
      timer = window.setTimeout(dismiss, remaining);
    };
    if (close) close.addEventListener("click", dismiss);
    toast.addEventListener("mouseenter", function () { pause("hover"); });
    toast.addEventListener("mouseleave", function () { resume("hover"); });
    toast.addEventListener("focusin", function () { pause("focus"); });
    toast.addEventListener("focusout", function (event) {
      if (!toast.contains(event.relatedTarget)) resume("focus");
    });
    toast._toastPause = pause;
    toast._toastResume = resume;
    toast._feedbackDismiss = dismiss;
    toast._feedbackReset = function () {
      window.clearTimeout(timer);
      remaining = 7000;
      if (!holds.size) start();
    };
    if (document.hidden) pause("hidden"); else start();
  }

  var feedbackQueue = [];

  function pumpFeedbackQueue() {
    var root = feedbackRoot();
    var rail = root && root.querySelector("[data-feedback-rail]");
    if (!rail || rail.querySelectorAll("[data-toast]").length >= 3 || !feedbackQueue.length) return;
    var next = feedbackQueue.shift();
    if (next.node) {
      rail.appendChild(next.node);
      initToastBehavior(next.node);
      announceFeedback(next.message, toastKind(next.node));
      return;
    }
    showFeedback(next.title, next.kind, next.detail, next.origin, next.manualTargets, next.announced);
  }

  function showFeedback(title, kind, detail, origin, manualTargets, alreadyAnnounced) {
    var root = feedbackRoot();
    var rail = root && root.querySelector("[data-feedback-rail]");
    if (!rail) return null;
    var signature = [kind, title, detail || ""].join("\u0000");
    var current = Array.prototype.find.call(rail.querySelectorAll("[data-toast]"), function (toast) {
      return toast.getAttribute("data-feedback-signature") === signature;
    });
    if (current) {
      current._feedbackReset && current._feedbackReset();
      announceFeedback(title + (detail ? " " + detail : ""), kind);
      return current;
    }
    if (rail.querySelectorAll("[data-toast]").length >= 3) {
      var queued = feedbackQueue.find(function (item) { return item.signature === signature; });
      if (!queued) {
        queued = { title: title, kind: kind, detail: detail || "", origin: origin, signature: signature, manualTargets: manualTargets || [], announced: true };
        feedbackQueue.push(queued);
        announceFeedback(title + (detail ? " " + detail : ""), kind);
      }
      return null;
    }
    var toast = document.createElement("div");
    toast.className = "toast feedback-card" + (kind === "error" ? " err" : "");
    toast.setAttribute("data-toast", "");
    toast.setAttribute("data-toast-kind", kind);
    toast.setAttribute("data-feedback-signature", signature);
    if (kind === "error" || kind === "warning" || kind === "partial") toast.setAttribute("data-toast-sticky", "");
    var icon = document.createElement("span");
    icon.className = "feedback-card-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = kind === "success" ? "✓" : kind === "error" || kind === "warning" || kind === "partial" ? "!" : "i";
    var body = document.createElement("div");
    body.className = "grow feedback-card-body";
    var heading = document.createElement("strong");
    heading.textContent = title;
    body.appendChild(heading);
    if (detail) {
      var text = document.createElement("p");
      text.textContent = detail;
      body.appendChild(text);
    }
    var close = document.createElement("button");
    close.type = "button";
    close.setAttribute("data-toast-close", "");
    close.setAttribute("aria-label", root.getAttribute("data-dismiss-label") || "Dismiss notification");
    close.textContent = "×";
    toast.appendChild(icon);
    toast.appendChild(body);
    toast.appendChild(close);
    if (origin) toast._feedbackOrigin = origin;
    if (manualTargets && manualTargets.length) {
      toast._copyManualTargets = manualTargets;
      var manualBody = toast.querySelector(".feedback-card-body") || toast;
      manualTargets.forEach(function (item) { placeManualCopy(item, manualBody); });
    }
    rail.appendChild(toast);
    initToastBehavior(toast);
    if (!alreadyAnnounced) announceFeedback(title + (detail ? " " + detail : ""), kind);
    return toast;
  }

  function copyText(text, allowLegacyFallback) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      try {
        return Promise.resolve(navigator.clipboard.writeText(text)).then(function () { return true; }, function () { return false; });
      } catch (error) {
        return Promise.resolve(false);
      }
    }
    if (allowLegacyFallback === false) return Promise.resolve(false);
    try {
      return Promise.resolve(document.execCommand("copy") === true);
    } catch (error) {
      return Promise.resolve(false);
    }
  }

  function copyFailure(target, origin, removeOnDismiss) {
    var root = feedbackRoot();
    if (!root) return;
    var toast = showFeedback(
      root.getAttribute("data-copy-failure") || "Copy failed",
      "error",
      root.getAttribute("data-copy-manual") || "Select the text and copy it manually.",
      origin
    );
    if (!target) return;
    var wasSrOnly = target.classList.contains("sr-only");
    var wasHidden = target.hidden;
    if (wasSrOnly || wasHidden) {
      var record = {
        target: target,
        wasSrOnly: wasSrOnly,
        wasHidden: wasHidden,
        removeOnDismiss: !!removeOnDismiss,
        origin: origin,
        originalParent: target.parentNode,
        originalNextSibling: target.nextSibling,
        originalForm: target.form || null,
        originalFormAttribute: target.getAttribute("form"),
        originalTabindex: target.getAttribute("tabindex")
      };
      if (toast) {
        toast._copyManualTargets = toast._copyManualTargets || [];
        toast._copyManualTargets.push(record);
        placeManualCopy(record, toast.querySelector(".feedback-card-body") || toast);
      } else {
        var signature = ["error", root.getAttribute("data-copy-failure") || "Copy failed", root.getAttribute("data-copy-manual") || "Select the text and copy it manually."].join("\u0000");
        var queued = feedbackQueue.find(function (item) { return item.signature === signature; });
        if (queued) {
          queued.manualTargets = queued.manualTargets || [];
          queued.manualTargets.push(record);
        }
        var recovery = root.querySelector("[data-copy-recovery]");
        var recoverySource = recovery && recovery.querySelector("[data-copy-recovery-source]");
        if (recovery && recoverySource) {
          recovery.hidden = false;
          recovery._copyManualRecords = recovery._copyManualRecords || [];
          recovery._copyManualRecords.push(record);
          placeManualCopy(record, recoverySource);
        }
      }
    }
    if (typeof target.focus === "function") target.focus();
    if (typeof target.select === "function") target.select();
  }

  function copySuccess(button, label) {
    var host = document.body.classList.contains("host-workspace");
    if (!host) return;
    var copiedLabel = label || (feedbackRoot() && feedbackRoot().getAttribute("data-copy-success")) || "Copied";
    prepareCopyControl(button);
    button.classList.add("copied");
    button.classList.add("is-copy-confirmed");
    var slot = button.querySelector("[data-copy-label-slot]");
    if (slot) slot.setAttribute("aria-hidden", "false");
    button.setAttribute("aria-label", copiedLabel);
    var oldTimer = button._copyFeedbackTimer;
    window.clearTimeout(oldTimer);
    button._copyFeedbackTimer = window.setTimeout(function () {
      button.classList.remove("copied");
      button.classList.remove("is-copy-confirmed");
      if (slot) slot.setAttribute("aria-hidden", "true");
      if (button._copyHadAriaLabel) button.setAttribute("aria-label", button._copyOriginalAriaLabel);
      else button.removeAttribute("aria-label");
    }, 1600);
    // The in-place receipt already confirms success. A second flow card would
    // move the copied control and every action below it while focus stays put.
    announceFeedback(copiedLabel, "success");
  }

  function prepareCopyControl(button) {
    if (button._copyPrepared) return;
    button._copyPrepared = true;
    button._copyHadAriaLabel = button.hasAttribute("aria-label");
    button._copyOriginalAriaLabel = button.getAttribute("aria-label") || "";
    var label = button.getAttribute("data-copied-label") || (feedbackRoot() && feedbackRoot().getAttribute("data-copy-success")) || "Copied";
    var slot = button.querySelector("[data-copy-label-slot]");
    if (slot) {
      slot.textContent = label;
      slot.hidden = false;
      slot.classList.add("copy-label-confirmed");
      slot.setAttribute("aria-hidden", "true");
      button.classList.add("is-copy-label-reserved");
    } else {
      var textNodes = Array.prototype.filter.call(button.childNodes, function (node) {
        return node.nodeType === Node.TEXT_NODE && node.nodeValue.trim();
      });
      if (textNodes.length) {
        var stack = document.createElement("span");
        stack.className = "copy-label-stack";
        var normal = document.createElement("span");
        normal.className = "copy-label-default";
        var confirmed = document.createElement("span");
        confirmed.className = "copy-label-confirmed";
        confirmed.textContent = label;
        textNodes.forEach(function (node) { normal.appendChild(node); });
        stack.appendChild(normal);
        stack.appendChild(confirmed);
        button.appendChild(stack);
      }
    }
    var icon = document.createElement("span");
    icon.className = "copy-state-icon";
    icon.setAttribute("data-copy-state-icon", "");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = '<svg viewBox="0 0 24 24" focusable="false"><path d="m5 12 4 4L19 6"/></svg>';
    button.appendChild(icon);
  }

  function initCopy() {
    document.querySelectorAll("[data-copy]").forEach(function (button) {
      prepareCopyControl(button);
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("data-copy"));
        if (!target) return;
        // Works for form fields and for blocks of text such as the portal
        // message, so a host never has to select a paragraph by hand.
        var originalFocus = document.activeElement;
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
        copyText(text).then(function (copied) {
          if (copied) {
            if (originalFocus === button && button.isConnected) button.focus();
            copySuccess(button, button.getAttribute("data-copied-label"));
          } else {
            copyFailure(target, button);
          }
        });
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
    function focusOutsideMenu(trigger, backwards) {
      var selector = "a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex='-1'])";
      var candidates = Array.prototype.filter.call(document.querySelectorAll(selector), function (item) {
        return item.tabIndex >= 0 && !item.classList.contains("sr-only") && item.getClientRects().length > 0 &&
          !item.closest("[hidden]") && getComputedStyle(item).visibility !== "hidden";
      });
      var index = candidates.indexOf(trigger);
      var next = candidates[index + (backwards ? -1 : 1)];
      if (next) { next.focus(); return true; }
      return false;
    }

    var lastOpenAt = 0;

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
          lastOpenAt = Date.now();
          positionRowMenu(trigger, panel);
          trigger.setAttribute("aria-expanded", "true");
          var firstItem = panel.querySelector('[role="menuitem"]');
          if (firstItem && typeof firstItem.focus === "function") firstItem.focus();
        }
      });
      panel.addEventListener("keydown", function (event) {
        var items = Array.prototype.filter.call(panel.querySelectorAll('[role="menuitem"]'), function (item) {
          return !item.hasAttribute("disabled") && item.getClientRects().length > 0;
        });
        var index = items.indexOf(document.activeElement);
        var currentTrigger = rowMenuTrigger(panel);
        if ((event.key === "ArrowDown" || event.key === "ArrowUp") && items.length) {
          event.preventDefault();
          var direction = event.key === "ArrowDown" ? 1 : -1;
          items[(index + direction + items.length) % items.length].focus();
        } else if ((event.key === "Home" || event.key === "End") && items.length) {
          event.preventDefault();
          items[event.key === "Home" ? 0 : items.length - 1].focus();
        } else if (event.key === "Escape") {
          event.preventDefault();
          closeRowMenu(panel);
          if (currentTrigger) currentTrigger.focus();
        } else if (event.key === "Tab" && currentTrigger) {
          closeRowMenu(panel);
          event.preventDefault();
          // Nothing follows the trigger: keep focus on it rather than dropping it to the body.
          if (!focusOutsideMenu(currentTrigger, event.shiftKey)) currentTrigger.focus();
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
    window.addEventListener("scroll", function () {
      // Opening a menu can scroll the page (focus, scroll-into-view); keep it open and follow the trigger.
      if (Date.now() - lastOpenAt < 400) {
        var open = document.querySelector(".row-menu-panel.is-open");
        var openTrigger = open ? rowMenuTrigger(open) : null;
        if (openTrigger) positionRowMenu(openTrigger, open);
        return;
      }
      closeAll();
    }, true);
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

  /* ---- 0098 inline reporting timing (Properties summary) ------------------- */
  // Saves on change (debounced for the hours box) through the same POST the
  // visible Save button sends without JS; shows "Saved" or the server's error.
  function initInlineTiming() {
    document.querySelectorAll("form[data-inline-timing]").forEach(function (form) {
      if (!window.fetch || !window.FormData) return;
      var select = form.querySelector("[data-timing-mode]");
      var hours = form.querySelector("[data-timing-hours-input]");
      var status = form.querySelector("[data-timing-status]");
      var timer = null;
      var seq = 0;
      form.classList.add("is-live");

      function show(text, kind) {
        if (!status) return;
        status.textContent = text;
        status.classList.toggle("is-error", kind === "error");
        status.classList.toggle("is-saved", kind === "saved");
      }

      function save() {
        window.clearTimeout(timer);
        timer = null;
        var mine = ++seq;
        show(form.getAttribute("data-saving") || "", "");
        var meta = document.querySelector('meta[name="csrf-token"]');
        var headers = { "Accept": "application/json" };
        if (meta) headers["X-CSRF-Token"] = meta.getAttribute("content") || "";
        fetch(form.getAttribute("action"), {
          method: "POST",
          body: new FormData(form),
          headers: headers,
          credentials: "same-origin"
        }).then(function (response) {
          return response.json().catch(function () { return { ok: false }; });
        }).then(function (data) {
          if (mine !== seq) return;
          if (data && data.ok) show(form.getAttribute("data-saved") || "", "saved");
          else show((data && data.error) || form.getAttribute("data-failed") || "", "error");
        }).catch(function () {
          if (mine === seq) show(form.getAttribute("data-failed") || "", "error");
        });
      }

      form.addEventListener("submit", function (event) {
        event.preventDefault();
        save();
      });
      if (select) select.addEventListener("change", save);
      if (hours) {
        hours.addEventListener("input", function () {
          window.clearTimeout(timer);
          timer = window.setTimeout(save, 700);
        });
        hours.addEventListener("change", function () {
          if (timer) save();
        });
      }
    });
  }
  /* ---- end 0098 ------------------------------------------------------------- */

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
      var account = (option.getAttribute("data-account") || "").replace(/\s/g, "");
      var parsed = /^(?:(\d{1,6})-)?(\d{2,10})\/(\d{4})$/.exec(account);
      var prefixField = document.getElementById("account_prefix");
      var numberField = document.getElementById("account_number");
      var bankField = document.getElementById("account_bank");
      if (prefixField && numberField && bankField) {
        prefixField.value = parsed && parsed[1] ? parsed[1] : "";
        numberField.value = parsed ? parsed[2] : "";
        bankField.value = parsed ? parsed[3] : "";
      }
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
    var pending = { base: "", params: "", scopeLabel: "" };
    var scope = dialog.querySelector("[data-csv-scope-label]");

    document.querySelectorAll("[data-csv-export]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        pending.base = button.getAttribute("data-csv-export") || "";
        pending.params = button.getAttribute("data-csv-params") || "";
        pending.scopeLabel = button.getAttribute("data-csv-scope-label") || "";
        if (scope && pending.scopeLabel) scope.textContent = pending.scopeLabel;
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
    /* 0099: one behaviour for every list row (table rows and dashboard stay
       rows): click or Enter/Space opens it; controls inside keep their own
       action, and selecting text in a row does not navigate. */
    document.querySelectorAll(ROW_SELECTOR).forEach(function (row) {
      function openRow() {
        if (window.ubyhostSkeleton) window.ubyhostSkeleton.start();
        window.location.assign(row.getAttribute("data-href"));
      }

      row.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.target.closest("a, button, input, select, textarea, label, form, summary, details, dialog, .row-menu, .row-actions, .dashboard-row-actions")) return;
        var selection = window.getSelection ? String(window.getSelection()) : "";
        if (selection && row.contains(window.getSelection().anchorNode)) return;
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
    // 0090: open every <details> around the target (not only the target),
    // then bring it into view, so a returned section is never folded away.
    function openTarget(hash) {
      if (!hash || hash.charAt(0) !== "#") return;
      var id;
      try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
      var target = document.getElementById(id);
      if (!target) return;
      var node = target;
      while (node) {
        if (node.tagName === "DETAILS") node.open = true;
        node = node.parentElement;
      }
      window.requestAnimationFrame(function () {
        target.scrollIntoView({ block: "start", behavior: "auto" });
      });
    }
    document.querySelectorAll("[data-open-details]").forEach(function (link) {
      link.addEventListener("click", function () { openTarget(link.hash); });
    });
    window.addEventListener("hashchange", function () { openTarget(window.location.hash); });
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

  /* Confirmations share the page lane; only transient success/info cards leave on their own. */
  function initToasts() {
    var root = feedbackRoot();
    var rail = root && root.querySelector("[data-feedback-rail]");
    if (!rail) return;
    var recovery = root.querySelector("[data-copy-recovery]");
    var recoveryClose = recovery && recovery.querySelector("[data-copy-recovery-close]");
    if (recoveryClose && !recoveryClose._copyRecoveryBound) {
      recoveryClose._copyRecoveryBound = true;
      recoveryClose.addEventListener("click", function () {
        var records = (recovery._copyManualRecords || []).slice();
        var origin = records.length ? records[0].origin : null;
        var root = feedbackRoot();
        var signature = ["error", root && root.getAttribute("data-copy-failure") || "Copy failed", root && root.getAttribute("data-copy-manual") || "Select the text and copy it manually."].join("\u0000");
        feedbackQueue = feedbackQueue.filter(function (item) { return item.signature !== signature; });
        records.forEach(restoreManualCopy);
        recovery.hidden = true;
        if (origin && origin.isConnected && typeof origin.focus === "function") origin.focus();
      });
    }
    if (!root._feedbackVisibilityBound) {
      root._feedbackVisibilityBound = true;
      document.addEventListener("visibilitychange", function () {
        rail.querySelectorAll("[data-toast]").forEach(function (toast) {
          if (document.hidden) toast._toastPause && toast._toastPause("hidden");
          else toast._toastResume && toast._toastResume("hidden");
        });
      });
    }
    var toasts = Array.prototype.slice.call(rail.querySelectorAll("[data-toast]"));
    toasts.sort(function (a, b) {
      var score = function (toast) {
        return toastKind(toast) === "error" ? 3 : toast.hasAttribute("data-toast-sticky") ? 2 : 1;
      };
      return score(b) - score(a);
    });
    var signatures = new Set();
    toasts.forEach(function (toast, index) {
      var kind = toastKind(toast);
      var messageNode = toast.querySelector(".grow");
      var message = messageNode ? messageNode.textContent.trim() : toast.textContent.trim();
      var signature = [kind, message].join("\u0000");
      if (signatures.has(signature)) {
        toast.remove();
        return;
      }
      signatures.add(signature);
      toast.setAttribute("data-feedback-signature", signature);
      if (!toast.querySelector(".feedback-card-icon")) {
        var icon = document.createElement("span");
        icon.className = "feedback-card-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = kind === "success" ? "✓" : kind === "error" || kind === "warning" || kind === "partial" ? "!" : "i";
        toast.insertBefore(icon, toast.firstChild);
      }
      if (index >= 3) {
        toast.remove();
        feedbackQueue.push({ node: toast, message: message });
        return;
      }
      initToastBehavior(toast);
      announceFeedback(message, kind);
    });
  }

  function initFilterPanels() {
    document.querySelectorAll("[data-filter-panel]").forEach(function (form) {
      var toggle = form.id ? document.querySelector('[data-filter-toggle][aria-controls="' + form.id + '"]') : null;
      var controls = Array.prototype.slice.call(form.querySelectorAll("input, select, textarea"));
      var initial = controls.map(function (control) { return control.value; });
      var initialRange = form.querySelector("[data-range-value]") || form.querySelector('[name="range"]');
      var initialRangeValue = initialRange ? initialRange.value : "";
      var rangeWasEdited = false;
      var setOpen = function (open, focus) {
        form.classList.toggle("is-collapsed", !open);
        if (toggle) {
          toggle.hidden = false;
          toggle.setAttribute("aria-expanded", open ? "true" : "false");
          if (focus) toggle.focus();
        }
      };
      form.classList.add("is-enhanced", "is-collapsed");
      setOpen(false, false);
      if (toggle) toggle.addEventListener("click", function () {
        setOpen(toggle.getAttribute("aria-expanded") !== "true", false);
      });
      var cancel = form.querySelector("[data-filter-cancel]");
      if (cancel) {
        cancel.hidden = false;
        cancel.addEventListener("click", function () {
          controls.forEach(function (control, index) {
            control.value = initial[index];
            control.dispatchEvent(new Event("change", { bubbles: true }));
          });
          rangeWasEdited = false;
          setOpen(false, true);
        });
      }
      form.querySelectorAll("[data-range-from], [data-range-until]").forEach(function (input) {
        input.addEventListener("change", function () { rangeWasEdited = true; });
      });
      form.addEventListener("submit", function (event) {
        var from = form.querySelector("[data-range-from]");
        var until = form.querySelector("[data-range-until]");
        if (from && until && from.value && until.value && from.value > until.value) {
          event.preventDefault();
          var error = form.querySelector("[data-range-error]");
          if (error) { error.hidden = false; error.focus(); }
          return;
        }
        if (initialRange && rangeWasEdited) {
          initialRange.value = "custom";
        } else if (initialRange && !rangeWasEdited && form.dataset.originalRange) {
          initialRange.value = form.dataset.originalRange;
        } else if (initialRange && !rangeWasEdited) {
          initialRange.value = initialRangeValue;
        }
      });
      initDateRanges(form);
      initMonthPickers(form);
    });
  }

  function initDateRanges(form) {
    form.querySelectorAll("[data-date-range]").forEach(function (range) {
      var from = range.querySelector("[data-range-from]");
      var until = range.querySelector("[data-range-until]");
      var trigger = range.querySelector("[data-range-trigger]");
      var popover = range.querySelector("[data-range-popover]");
      var draftFromInput = range.querySelector("[data-range-draft-from]");
      var draftUntilInput = range.querySelector("[data-range-draft-until]");
      var monthLabel = range.querySelector("[data-range-month]");
      var grid = range.querySelector("[data-range-grid]");
      var error = range.querySelector("[data-range-error]");
      if (!from || !until || !trigger || !popover || !grid) return;
      trigger.hidden = false;
      var draftFrom = from.value;
      var draftUntil = until.value;
      var cursor = new Date();
      var activeDraft = "from";
      var pad = function (n) { return String(n).padStart(2, "0"); };
      var iso = function (date) { return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()); };
      var parse = function (value) { var bits = value.split("-").map(Number); return new Date(bits[0], bits[1] - 1, bits[2]); };
      var setCaption = function () {
        var caption = range.querySelector("[data-range-caption]");
        if (!caption) return;
        var formatter = new Intl.DateTimeFormat(document.documentElement.lang || undefined, { day: "numeric", month: "short", year: "numeric" });
        caption.textContent = draftFrom && draftUntil ? formatter.format(parse(draftFrom)) + " – " + formatter.format(parse(draftUntil)) : draftFrom ? formatter.format(parse(draftFrom)) + " →" : draftUntil ? "← " + formatter.format(parse(draftUntil)) : trigger.dataset.allDates || "";
      };
      var render = function () {
        var formatter = new Intl.DateTimeFormat(document.documentElement.lang || undefined, { month: "long", year: "numeric" });
        monthLabel.textContent = formatter.format(cursor);
        grid.textContent = "";
        var weekdayFormatter = new Intl.DateTimeFormat(document.documentElement.lang || undefined, { weekday: "short" });
        for (var weekday = 0; weekday < 7; weekday += 1) {
          var labelDate = new Date(2024, 0, 1 + weekday);
          var label = document.createElement("span");
          label.className = "range-weekday";
          label.setAttribute("role", "columnheader");
          label.textContent = weekdayFormatter.format(labelDate);
          grid.appendChild(label);
        }
        var first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
        var offset = (first.getDay() + 6) % 7;
        var start = new Date(cursor.getFullYear(), cursor.getMonth(), 1 - offset);
        for (var i = 0; i < 42; i += 1) {
          var day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
          var value = iso(day);
          var button = document.createElement("button");
          button.type = "button";
          button.className = "range-day";
          button.textContent = String(day.getDate());
          button.setAttribute("role", "gridcell");
          button.setAttribute("aria-label", new Intl.DateTimeFormat(document.documentElement.lang || undefined, { dateStyle: "full" }).format(day));
          button.dataset.rangeDate = value;
          if (day.getMonth() !== cursor.getMonth()) button.classList.add("outside-month");
          if (value === draftFrom || value === draftUntil) button.classList.add("selected");
          if (draftFrom && draftUntil && value >= draftFrom && value <= draftUntil) button.classList.add("in-range");
          button.addEventListener("click", function (event) {
            var selected = event.currentTarget.dataset.rangeDate;
            if (activeDraft === "from") { draftFrom = selected; if (draftUntil && draftUntil < selected) draftUntil = ""; activeDraft = "until"; }
            else { draftUntil = selected; activeDraft = "from"; }
            draftFromInput.value = draftFrom; draftUntilInput.value = draftUntil;
            validate(); render();
            var focusDate = grid.querySelector('[data-range-date="' + selected + '"]'); if (focusDate) focusDate.focus();
          });
          button.addEventListener("keydown", function (event) {
            var delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : event.key === "ArrowDown" ? 7 : event.key === "ArrowUp" ? -7 : 0;
            if (!delta) return;
            event.preventDefault();
            var next = new Date(parse(event.currentTarget.dataset.rangeDate)); next.setDate(next.getDate() + delta);
            if (next.getMonth() !== cursor.getMonth() || next.getFullYear() !== cursor.getFullYear()) { cursor = new Date(next.getFullYear(), next.getMonth(), 1); render(); }
            var target = grid.querySelector('[data-range-date="' + iso(next) + '"]'); if (target) target.focus();
          });
          grid.appendChild(button);
        }
      };
      var validate = function () {
        var reversed = !!(draftFrom && draftUntil && draftFrom > draftUntil);
        if (error) error.hidden = !reversed;
        var apply = range.querySelector("[data-range-apply]"); if (apply) apply.disabled = reversed;
        return !reversed;
      };
      var close = function (restore) {
        popover.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        if (restore) { draftFrom = from.value; draftUntil = until.value; draftFromInput.value = draftFrom; draftUntilInput.value = draftUntil; validate(); render(); setCaption(); }
        trigger.focus();
      };
      var open = function () {
        draftFrom = from.value; draftUntil = until.value;
        draftFromInput.value = draftFrom; draftUntilInput.value = draftUntil;
        activeDraft = "from";
        setCaption();
        var seed = draftFrom || draftUntil || iso(new Date());
        cursor = parse(seed); cursor.setDate(1);
        popover.hidden = false; trigger.setAttribute("aria-expanded", "true");
        validate(); render();
        var bounds = trigger.getBoundingClientRect();
        var width = Math.min(360, window.innerWidth - 8);
        popover.style.left = Math.max(4, Math.min(bounds.left, window.innerWidth - width - 4)) + "px";
        popover.style.top = Math.min(bounds.bottom + 8, window.innerHeight - popover.offsetHeight - 8) + "px";
        var chosen = grid.querySelector(".selected") || grid.querySelector(".range-day:not(.outside-month)");
        if (chosen) chosen.focus();
      };
      trigger.addEventListener("click", open);
      draftFromInput.addEventListener("focus", function () { activeDraft = "from"; });
      draftUntilInput.addEventListener("focus", function () { activeDraft = "until"; });
      draftFromInput.addEventListener("input", function () { draftFrom = draftFromInput.value; activeDraft = "until"; validate(); render(); });
      draftUntilInput.addEventListener("input", function () { draftUntil = draftUntilInput.value; activeDraft = "from"; validate(); render(); });
      from.addEventListener("change", function () { draftFrom = from.value; draftFromInput.value = draftFrom; validate(); render(); setCaption(); });
      until.addEventListener("change", function () { draftUntil = until.value; draftUntilInput.value = draftUntil; validate(); render(); setCaption(); });
      range.querySelector("[data-range-prev]").addEventListener("click", function () { cursor.setMonth(cursor.getMonth() - 1); render(); });
      range.querySelector("[data-range-next]").addEventListener("click", function () { cursor.setMonth(cursor.getMonth() + 1); render(); });
      range.querySelector("[data-range-clear]").addEventListener("click", function () { draftFrom = ""; draftUntil = ""; draftFromInput.value = ""; draftUntilInput.value = ""; activeDraft = "from"; validate(); render(); });
      range.querySelector("[data-range-apply]").addEventListener("click", function () {
        if (!validate()) return;
        from.value = draftFrom; until.value = draftUntil;
        from.dispatchEvent(new Event("change", { bubbles: true }));
        until.dispatchEvent(new Event("change", { bubbles: true }));
        setCaption(); popover.hidden = true; trigger.setAttribute("aria-expanded", "false"); trigger.focus();
      });
      document.addEventListener("pointerdown", function (event) { if (!range.contains(event.target) && !popover.hidden) close(true); });
      document.addEventListener("keydown", function (event) { if (event.key === "Escape" && !popover.hidden) { event.preventDefault(); close(true); } });
      setCaption(); render();
    });
  }

  function initMonthPickers(form) {
    form.querySelectorAll("[data-month-picker]").forEach(function (picker) {
      var nativeInput = picker.querySelector("[data-month-native]");
      var trigger = picker.querySelector("[data-month-trigger]");
      var panel = picker.querySelector("[data-month-grid-panel]");
      var grid = picker.querySelector("[data-month-grid]");
      var yearLabel = picker.querySelector("[data-month-year]");
      if (!nativeInput || !trigger || !panel || !grid) return;
      trigger.hidden = false;
      var min = picker.dataset.minMonth || "2000-01";
      var max = picker.dataset.maxMonth || "9999-12";
      var year = Number((nativeInput.value || picker.dataset.currentMonth || max).slice(0, 4));
      var selected = nativeInput.value;
      var optional = picker.dataset.monthOptional === "true";
      var monthSteps = Array.prototype.slice.call(picker.querySelectorAll(".month-step"));
      var setCaption = function () {
        var caption = picker.querySelector("[data-month-caption]");
        if (caption) caption.textContent = selected ? new Intl.DateTimeFormat(document.documentElement.lang || undefined, { month: "long", year: "numeric" }).format(new Date(Number(selected.slice(0, 4)), Number(selected.slice(5, 7)) - 1, 1)) : (picker.querySelector("[data-month-all]") || {}).textContent || "";
      };
      var render = function () {
        yearLabel.textContent = String(year);
        grid.querySelectorAll("[data-month-choice]").forEach(function (button) {
          var month = button.dataset.monthChoice.slice(5);
          button.dataset.monthChoice = String(year) + "-" + month;
          button.disabled = button.dataset.monthChoice < min || button.dataset.monthChoice > max;
          button.classList.toggle("selected", button.dataset.monthChoice === selected);
          button.setAttribute("aria-pressed", button.dataset.monthChoice === selected ? "true" : "false");
        });
        var prev = picker.querySelector("[data-year-prev]"); var next = picker.querySelector("[data-year-next]");
        if (prev) prev.disabled = String(year) <= min.slice(0, 4);
        if (next) next.disabled = String(year) >= max.slice(0, 4);
        var anchor = selected || picker.dataset.currentMonth || max;
        var anchorBits = anchor.split("-").map(Number);
        var prior = new Date(anchorBits[0], anchorBits[1] - 2, 1);
        var after = new Date(anchorBits[0], anchorBits[1], 1);
        var priorKey = prior.getFullYear() + "-" + String(prior.getMonth() + 1).padStart(2, "0");
        var afterKey = after.getFullYear() + "-" + String(after.getMonth() + 1).padStart(2, "0");
        var previousStep = picker.querySelector("[data-month-prev]");
        var nextStep = picker.querySelector("[data-month-next]");
        if (previousStep) previousStep.disabled = priorKey < min;
        if (nextStep) nextStep.disabled = afterKey > max;
      };
      monthSteps.forEach(function (step) {
        step.hidden = false;
        step.addEventListener("click", function () {
          var anchor = selected || picker.dataset.currentMonth || max;
          var bits = anchor.split("-").map(Number);
          var delta = step.hasAttribute("data-month-prev") ? -1 : 1;
          var date = new Date(bits[0], bits[1] - 1 + delta, 1);
          var candidate = date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0");
          if (candidate < min || candidate > max) return;
          selected = candidate; nativeInput.value = candidate; setCaption(); render();
        });
      });
      var close = function (restore) { panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); if (restore) selected = nativeInput.value; setCaption(); trigger.focus(); };
      trigger.addEventListener("click", function () {
        selected = nativeInput.value; year = Number((selected || picker.dataset.currentMonth || max).slice(0, 4));
        panel.hidden = false; trigger.setAttribute("aria-expanded", "true"); render();
        var bounds = trigger.getBoundingClientRect();
        var width = Math.min(360, window.innerWidth - 8);
        panel.style.left = Math.max(4, Math.min(bounds.left, window.innerWidth - width - 4)) + "px";
        panel.style.top = Math.min(bounds.bottom + 8, window.innerHeight - panel.offsetHeight - 8) + "px";
        var focused = grid.querySelector(".selected:not([disabled])") || grid.querySelector("[data-month-choice]:not([disabled])"); if (focused) focused.focus();
      });
      picker.querySelectorAll("[data-month-choice]").forEach(function (button) { button.addEventListener("click", function () { selected = button.dataset.monthChoice; nativeInput.value = selected; nativeInput.dispatchEvent(new Event("change", { bubbles: true })); setCaption(); render(); panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); trigger.focus(); }); });
      var prev = picker.querySelector("[data-year-prev]"); var next = picker.querySelector("[data-year-next]");
      if (prev) prev.addEventListener("click", function () { year -= 1; render(); });
      if (next) next.addEventListener("click", function () { year += 1; render(); });
      var all = picker.querySelector("[data-month-all-choice]");
      if (all && optional) all.addEventListener("click", function () { selected = ""; nativeInput.value = ""; nativeInput.dispatchEvent(new Event("change", { bubbles: true })); setCaption(); render(); panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); trigger.focus(); });
      nativeInput.addEventListener("change", function () { selected = nativeInput.value; setCaption(); render(); });
      document.addEventListener("pointerdown", function (event) { if (!picker.contains(event.target) && !panel.hidden) close(true); });
      document.addEventListener("keydown", function (event) { if (event.key === "Escape" && !panel.hidden) { event.preventDefault(); close(true); } });
      setCaption(); render();
    });
  }

  /* Legacy auto-submit remains available only to forms that explicitly opt in. */
  function initAutoFilters() {
    document.querySelectorAll("form[data-auto-submit]").forEach(function (form) {
      form.querySelectorAll("select, input[type=date], input[type=month]").forEach(function (input) {
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
    var proceed = shell && shell.querySelector("[data-confirm-proceed]");
    if (!dialog || !shell) return;
    var pendingForm = null;
    var pendingButton = null;

    function isArchiveConfirmation(form, button) {
      var action = button && (button.getAttribute("formaction") || (button.form && button.form.getAttribute("action")));
      if (!action && form) action = form.getAttribute("action");
      if (!action) return false;
      try {
        return new URL(action, window.location.href).pathname.replace(/\/+$/, "").endsWith("/archive");
      } catch (error) {
        return false;
      }
    }

    function openDialog(message, form, button) {
      pendingForm = form || null;
      pendingButton = button || null;
      if (title) title.textContent = "";
      if (body) body.textContent = message || "";
      if (proceed) {
        proceed.textContent = isArchiveConfirmation(form, button)
          ? proceed.getAttribute("data-confirm-archive-label") || proceed.getAttribute("data-confirm-default-label") || proceed.textContent
          : proceed.getAttribute("data-confirm-default-label") || proceed.textContent;
      }
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
    var commandCopyError = null;
    var commandResultsMaxHeight = null;
    var commandOpener = null;
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

    function clearCommandCopyError() {
      if (commandCopyError) commandCopyError.remove();
      commandCopyError = null;
      if (results && commandResultsMaxHeight !== null) {
        results.style.maxHeight = commandResultsMaxHeight;
        commandResultsMaxHeight = null;
      }
    }

    function showCommandCopyFailure(value) {
      clearCommandCopyError();
      if (!command || !results) return;
      var root = feedbackRoot();
      var notice = document.createElement("div");
      notice.className = "command-copy-error";
      notice.setAttribute("role", "alert");
      var heading = document.createElement("strong");
      heading.textContent = (root && root.getAttribute("data-copy-failure")) || "Copy failed";
      var instructions = document.createElement("p");
      instructions.textContent = (root && root.getAttribute("data-copy-manual")) || "Select the text and copy it manually.";
      var source = document.createElement("textarea");
      source.readOnly = true;
      source.value = value;
      source.setAttribute("aria-label", instructions.textContent);
      notice.append(heading, instructions, source);
      commandResultsMaxHeight = results.style.maxHeight;
      results.style.maxHeight = "min(320px, 40vh)";
      results.insertAdjacentElement("afterend", notice);
      commandCopyError = notice;
      source.focus();
      source.select();
    }

    function runItem(item) {
      var recentId = item.url || item.label;
      recents = [recentId].concat(recents.filter(function (value) { return value !== recentId; })).slice(0, 8);
      try { localStorage.setItem(recentKey, JSON.stringify(recents)); } catch (error) {}
      if (item.copy) {
        clearCommandCopyError();
        copyText(item.copy, false).then(function (copied) {
          if (!copied) {
            showCommandCopyFailure(item.copy);
            return;
          }
          clearCommandCopyError();
          if (results) results.textContent = results.getAttribute("data-copied") || "";
          var feedbackOrigin = commandOpener && commandOpener.isConnected ? commandOpener : document.activeElement;
          showFeedback((feedbackRoot() && feedbackRoot().getAttribute("data-command-copied")) || "Copied", "success", "", feedbackOrigin);
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
      clearCommandCopyError();
      document.dispatchEvent(new Event("host:close-navigation"));
      if (!command.open) {
        commandOpener = document.activeElement;
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
      command.addEventListener("close", clearCommandCopyError);
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
      input.addEventListener("input", function () { clearCommandCopyError(); render(input.value); });
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
      var rows = Array.prototype.slice.call(document.querySelectorAll(ROW_SELECTOR));
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
        var appliedSummary = document.querySelector('[data-filter-summary]');
        var label = appliedSummary ? appliedSummary.textContent.replace(/\s*[·•]\s*/g, " — ").trim() : "";
        if (!label) label = document.title;
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

  /* 0093 help: contextual "?" tips (macro help_tip). Hover/focus/tap open, Esc and outside click close. */
  function initHelpTips() {
    var tips = Array.prototype.slice.call(document.querySelectorAll("[data-help-tip]"));
    if (!tips.length) return;
    var current = null;
    var timer = null;

    function place(tip) {
      var btn = tip.querySelector(".help-tip-btn");
      var body = tip.querySelector(".help-tip-body");
      var margin = 8;
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      body.style.width = Math.min(320, vw - 2 * margin) + "px";
      var r = btn.getBoundingClientRect();
      var w = body.offsetWidth;
      var h = body.offsetHeight;
      var left = Math.max(margin, Math.min(r.left, vw - w - margin));
      var top = r.bottom + 6;
      if (top + h > vh - margin && r.top - 6 - h >= margin) top = r.top - 6 - h;
      top = Math.max(margin, Math.min(top, vh - h - margin));
      body.style.left = left + "px";
      body.style.top = top + "px";
    }
    function close(tip) {
      tip.classList.remove("is-open");
      tip.removeAttribute("data-pinned");
      tip.querySelector(".help-tip-btn").setAttribute("aria-expanded", "false");
      if (current === tip) current = null;
    }
    function open(tip, pinned) {
      if (current && current !== tip) close(current);
      window.clearTimeout(timer);
      current = tip;
      tip.classList.add("is-open");
      tip.querySelector(".help-tip-btn").setAttribute("aria-expanded", "true");
      if (pinned) tip.setAttribute("data-pinned", "1");
      place(tip);
    }
    function closeSoon(tip) {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        if (!tip.hasAttribute("data-pinned") && !tip.contains(document.activeElement)) close(tip);
      }, 150);
    }

    tips.forEach(function (tip) {
      var btn = tip.querySelector(".help-tip-btn");
      tip.setAttribute("data-js", "1");
      tip.addEventListener("pointerenter", function (e) {
        if (e.pointerType === "mouse") open(tip, false);
      });
      tip.addEventListener("pointerleave", function (e) {
        if (e.pointerType === "mouse") closeSoon(tip);
      });
      btn.addEventListener("focus", function () {
        if (btn.matches(":focus-visible")) open(tip, false);
      });
      tip.addEventListener("focusout", function (e) {
        if (!tip.contains(e.relatedTarget)) close(tip);
      });
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (tip.classList.contains("is-open") && tip.hasAttribute("data-pinned")) close(tip);
        else open(tip, true);
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !current) return;
      var tip = current;
      close(tip);
      tip.querySelector(".help-tip-btn").focus();
    });
    document.addEventListener("click", function (e) {
      if (current && !current.contains(e.target)) close(current);
    });
    function reflow() { if (current) place(current); }
    window.addEventListener("resize", reflow);
    window.addEventListener("scroll", reflow, true);
  }

  /* 0094: property Overview / Bookings & calendars / Settings.
     Every view and settings group is already in the page; switching only shows
     another one, so the one settings form keeps whatever the host typed. Links
     carry ?view=&section= (plus a #hash to scroll), history follows, and a dirty form asks before
     the page is left. Without JavaScript the same links reload with ?view=. */
  function initPropertyViews() {
    var root = document.querySelector("[data-property-views]");
    if (!root) return;
    root.setAttribute("data-js", "1");
    var base = root.getAttribute("data-property-base");
    var VIEWS = ["overview", "bookings", "settings"];
    var SECTIONS = ["property", "guests", "reporting", "lock", "automation"];
    var form = root.querySelector("[data-property-settings-form]");
    var returnInput = form && form.querySelector("[data-property-return]");
    var connect = root.querySelector("[data-calendar-connect]");
    // 0096: the setup guide's Continue shows only away from the step's place.
    var guide = document.querySelector("[data-setup-guide]");
    var guideContinue = guide && guide.querySelector("[data-setup-continue]");

    function hashTarget(hash) {
      if (!hash || hash.length < 2) return null;
      try { return document.getElementById(decodeURIComponent(hash.slice(1))); } catch (_) { return null; }
    }

    // Where a URL points: [view, section] of the element the hash names in
    // this page, else ?view/?section (0101: no table of old hashes).
    function destination(url) {
      var target = hashTarget(url.hash);
      if (target && root.contains(target)) {
        var panel = target.closest("[data-property-view]");
        var group = target.closest("[data-settings-group]");
        if (panel) return [panel.getAttribute("data-property-view"), group ? group.getAttribute("data-settings-group") : null];
      }
      var view = url.searchParams.get("view");
      var section = url.searchParams.get("section");
      if (VIEWS.indexOf(view) < 0) view = SECTIONS.indexOf(section) >= 0 ? "settings" : null;
      if (!view) return null;
      return [view, SECTIONS.indexOf(section) >= 0 ? section : null];
    }

    function activeSection() {
      var group = root.querySelector("[data-settings-group].is-active");
      return group ? group.getAttribute("data-settings-group") : "property";
    }

    function activate(view, section) {
      if (VIEWS.indexOf(view) < 0) view = "overview";
      root.querySelectorAll("[data-property-view]").forEach(function (panel) {
        panel.classList.toggle("is-active", panel.getAttribute("data-property-view") === view);
      });
      document.querySelectorAll("[data-property-tab]").forEach(function (tab) {
        if (tab.getAttribute("data-property-tab") === view) tab.setAttribute("aria-current", "page");
        else tab.removeAttribute("aria-current");
      });
      if (section && SECTIONS.indexOf(section) >= 0) {
        root.querySelectorAll("[data-settings-group]").forEach(function (group) {
          group.classList.toggle("is-active", group.getAttribute("data-settings-group") === section);
        });
        root.querySelectorAll("[data-property-section-link]").forEach(function (link) {
          if (link.getAttribute("data-property-section-link") === section) link.setAttribute("aria-current", "true");
          else link.removeAttribute("aria-current");
        });
      }
      if (returnInput) {
        returnInput.value = view === "settings"
          ? base + "?view=settings&section=" + activeSection()
          : base + "?view=" + view;
      }
      if (guideContinue) {
        var stepSection = guide.getAttribute("data-setup-section");
        guideContinue.hidden = view === guide.getAttribute("data-setup-view")
          && (!stepSection || (view === "settings" && activeSection() === stepSection));
      }
    }

    function reveal(url, scroll) {
      var dest = destination(url);
      if (!dest) return false;
      activate(dest[0], dest[1]);
      var target = hashTarget(url.hash);
      if (target && connect && (target === connect || connect.contains(target))) connect.classList.remove("is-collapsed");
      if (url.searchParams.get("add_calendar") === "1" && connect) connect.classList.remove("is-collapsed");
      if (scroll) {
        var into = target && root.contains(target) ? target : root;
        window.requestAnimationFrame(function () { into.scrollIntoView({ block: "start", behavior: "auto" }); });
      }
      return true;
    }

    document.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      var link = event.target.closest && event.target.closest("a[href]");
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      var url;
      try { url = new URL(link.href, window.location.href); } catch (_) { return; }
      if (url.origin !== window.location.origin || url.pathname !== base) return;
      if (!url.search && !url.hash) url.searchParams.set("view", "overview");
      if (!destination(url)) return;
      event.preventDefault();
      var lang = new URLSearchParams(window.location.search).get("lang");
      if (lang && !url.searchParams.get("lang")) url.searchParams.set("lang", lang);
      url.searchParams.delete("created");
      window.history.pushState({ propertyView: true }, "", url.pathname + url.search + url.hash);
      // skeleton.js saw a link click and armed its "page is loading" blank;
      // this one stays in the page, so disarm it (0084 O1 finding).
      if (window.ubyhostSkeleton) window.ubyhostSkeleton.hide();
      reveal(url, true);
    });

    window.addEventListener("popstate", function () {
      var url = new URL(window.location.href);
      if (!reveal(url, false)) activate("overview", null);
    });
    window.addEventListener("hashchange", function () {
      reveal(new URL(window.location.href), true);
    });

    if (form) {
      // A field the browser refuses may sit in a hidden group: show that group
      // first, so the browser can focus the field and say what is wrong.
      var revealing = false;
      form.addEventListener("invalid", function (event) {
        if (revealing) return;
        revealing = true;
        window.setTimeout(function () { revealing = false; }, 0);
        var group = event.target.closest && event.target.closest("[data-settings-group]");
        activate("settings", group ? group.getAttribute("data-settings-group") : null);
      }, true);
      // Unsaved changes: the form carries data-unsaved-guard, so
      // initUnsavedForms (browser prompt) and initUnsavedDialog (0084 O1) own it.
    }

    // A switch says "Not saved yet" until the form is saved; never "Enabled".
    root.querySelectorAll("input[data-switch-saved]").forEach(function (input) {
      var status = document.getElementById((input.getAttribute("aria-describedby") || "").split(" ")[0]);
      if (!status) return;
      input.addEventListener("change", function () {
        var saved = input.getAttribute("data-switch-saved") === "1";
        var text = input.checked === saved
          ? status.getAttribute(input.checked ? "data-on" : "data-off")
          : status.getAttribute("data-unsaved");
        status.textContent = text;
        status.classList.toggle("is-on", input.checked && input.checked === saved);
        status.classList.toggle("is-unsaved", input.checked !== saved);
      });
    });

    reveal(new URL(window.location.href), false);
  }

  /* 0076: a page with several independent forms (the business editor's
     Business details and Invoice details). Saving one form, or leaving the
     page, asks first when another of them holds unsaved changes. */
  function initUnsavedForms() {
    var forms = Array.prototype.slice.call(document.querySelectorAll("form[data-unsaved-guard]"));
    if (!forms.length) return;
    var submitting = null;
    forms.forEach(function (form) {
      var mark = function () { form.setAttribute("data-dirty", "1"); };
      form.addEventListener("input", mark);
      form.addEventListener("change", mark);
      form.addEventListener("submit", function () { submitting = form; });
    });
    window.addEventListener("beforeunload", function (event) {
      var unsaved = forms.some(function (form) {
        return form !== submitting && form.getAttribute("data-dirty") === "1";
      });
      submitting = null;
      if (!unsaved) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  /* ---- 0084 O1: unsaved changes, in-app Save / Discard / Stay ----------------
     A form with data-unsaved-guard that holds changes (data-dirty, set by
     initUnsavedForms) asks before an in-app link leaves it:
       Save    submits that form as usual; the server validates and returns the
               host where the form's return_to / next says (no chained jump: a
               refused save must stay on its error page).
       Discard restores the loaded values, then follows the link.
       Stay    (also Esc) keeps the edits and returns focus to the link.
     Links that keep the draft on screen (property Settings sub-nav, cards and
     anchors into Settings, in-page #anchors) do not ask. Tab close, reload and
     other sites keep the browser's own prompt. Without JavaScript nothing here
     runs and the forms post as before. */
  function initUnsavedDialog() {
    var forms = Array.prototype.slice.call(document.querySelectorAll("form[data-unsaved-guard]"));
    var dialog = document.getElementById("unsaved-dialog");
    if (!forms.length) return;
    var property = document.querySelector("[data-property-views]");
    var propertyBase = property && property.getAttribute("data-property-base");
    var SETTINGS_SECTIONS = ["property", "guests", "reporting", "lock", "automation"];
    var pendingLink = null;

    function isDirty(form) { return form.getAttribute("data-dirty") === "1"; }
    function dirtyForms() { return forms.filter(isDirty); }

    // The "Discard changes" button beside Save shows only while its form is dirty.
    function syncResetButtons() {
      forms.forEach(function (form) {
        form.querySelectorAll("[data-unsaved-reset]").forEach(function (button) {
          button.hidden = !isDirty(form);
        });
      });
    }

    // Back to the loaded values. Switch labels and dependent fields listen for
    // "change", so tell them; then the form is clean again.
    function discard(form) {
      form.reset();
      form.querySelectorAll("select, input[type=checkbox], input[type=radio]").forEach(function (el) {
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });
      form.removeAttribute("data-dirty");
    }

    // True when following this link keeps the draft on screen.
    function keepsDraft(url) {
      var here = window.location;
      if (property && propertyBase && url.pathname === propertyBase) {
        var target = null;
        if (url.hash.length > 1) {
          try { target = document.getElementById(decodeURIComponent(url.hash.slice(1))); } catch (_) { target = null; }
        }
        var panel = target && target.closest("[data-property-view]");
        if (panel) return panel.getAttribute("data-property-view") === "settings";
        var view = url.searchParams.get("view");
        if (view) return view === "settings";
        if (SETTINGS_SECTIONS.indexOf(url.searchParams.get("section")) >= 0) return true;
        return url.search === here.search && !!url.hash;
      }
      return url.pathname === here.pathname && url.search === here.search && !!url.hash;
    }

    forms.forEach(function (form) {
      form.addEventListener("input", syncResetButtons);
      form.addEventListener("change", syncResetButtons);
      form.querySelectorAll("[data-unsaved-reset]").forEach(function (button) {
        button.addEventListener("click", function () {
          discard(form);
          syncResetButtons();
          var save = form.querySelector(".host-property-save [type=submit]") || form.querySelector(".actions [type=submit]");
          if (save) save.focus();
        });
      });
    });
    syncResetButtons();
    // Back/Forward may restore typed values without input events.
    window.addEventListener("pageshow", syncResetButtons);

    if (!dialog || typeof dialog.showModal !== "function") return;
    var stay = dialog.querySelector("[data-unsaved-stay]");
    var discardBtn = dialog.querySelector("[data-unsaved-discard]");
    var save = dialog.querySelector("[data-unsaved-save]");

    function close(returnFocus) {
      if (dialog.open) dialog.close();
      var link = pendingLink;
      pendingLink = null;
      if (returnFocus && link) link.focus();
      return link;
    }

    document.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      var link = event.target.closest && event.target.closest("a[href]");
      if (!link || dialog.contains(link)) return;
      if ((link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      if (!dirtyForms().length) return;
      var url;
      try { url = new URL(link.href, window.location.href); } catch (_) { return; }
      if (url.origin !== window.location.origin || keepsDraft(url)) return;
      event.preventDefault();
      event.stopPropagation();
      pendingLink = link;
      dialog.showModal();
      stay.focus();
    }, true);

    stay.addEventListener("click", function () { close(true); });
    // Esc is Stay.
    dialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      close(true);
    });
    discardBtn.addEventListener("click", function () {
      dirtyForms().forEach(discard);
      syncResetButtons();
      var link = close(false);
      if (link) link.click();
    });
    save.addEventListener("click", function () {
      var form = dirtyForms()[0];
      close(false);
      if (!form) return;
      if (form.requestSubmit) form.requestSubmit();
      else form.submit();
    });
    // Keep Tab inside the dialog.
    dialog.addEventListener("keydown", function (event) {
      if (event.key !== "Tab") return;
      var buttons = [stay, discardBtn, save];
      var at = buttons.indexOf(document.activeElement);
      var next = event.shiftKey ? (at <= 0 ? buttons.length - 1 : at - 1) : (at < 0 || at === buttons.length - 1 ? 0 : at + 1);
      event.preventDefault();
      buttons[next].focus();
    });
  }
  /* ---- end 0084 O1 ---------------------------------------------------------- */

  document.addEventListener("DOMContentLoaded", function () {
    initCopy();
    initUnsavedForms();
    initUnsavedDialog();
    initHelpTips();
    initBirthDateInputs();
    initRowMenus();
    initClickableRows();
    initNavigation();
    initTogglePanels();
    initDismissBanners();
    initNotifications();
    initPropertyViews();
    initDetailsLinks();
    initAutomationFields();
    initInlineTiming();
    initControllerFields();
    initFeeTemplateCopy();
    initCsvExport();
    initHousebookPdfExport();
    initToasts();
    initFilterPanels();
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
