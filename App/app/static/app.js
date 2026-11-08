// Turbo ignores reduced motion; without startViewTransition it swaps pages without a fade.
if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches && document.startViewTransition) { document.startViewTransition = undefined; }
(function () {
  "use strict";

  var SIDEBAR_KEY = "ubyhost-sidebar-collapsed";
  var NAV_BREAKPOINT = 960;
  var manualCopyFormId = 0;
  /* 0099: every clickable list row, table or dashboard card. */
  var ROW_SELECTOR = "tr[data-href], .clickable-row[data-href]";

  var hostBindings = {};
  var navState = { railWasCollapsed: false, animateTimer: null, tabletRail: null };
  function claimNode(node, key) {
    var keys = node._ubyBound || (node._ubyBound = {});
    if (keys[key]) return false;
    keys[key] = true;
    return true;
  }
  function visitBinding(root, selector) {
    if (!root || !root.querySelectorAll) return;
    var attach = hostBindings[selector];
    if (root.matches && root.matches(selector) && claimNode(root, selector)) attach(root);
    root.querySelectorAll(selector).forEach(function (node) {
      if (claimNode(node, selector)) attach(node);
    });
  }
  function bindHostNodes(selector, attach) {
    hostBindings[selector] = attach;
    visitBinding(document, selector);
  }
  document.addEventListener("ubyhost:content-updated", function (event) {
    var root = event.detail && event.detail.root;
    if (!root || !root.isConnected) return;
    Object.keys(hostBindings).forEach(function (selector) { visitBinding(root, selector); });
  });

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
    target.textContent = "";
    window.setTimeout(function () { target.textContent = message; }, 20);
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
    // 0971: no badge over the button; the label swaps to "Copied" in place and keeps the button's size.
  }

  function initCopy() {
    bindHostNodes("[data-copy]", function (button) {
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
    if (panel.classList.contains("ui-menu-panel") && window.matchMedia("(max-width: 1023px)").matches) {
      return; // 0151: below 1024 px the panel is the bottom sheet of host2.css; CSS places it
    }
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
      if (!claimNode(input, "initBirthDateInputs")) return;
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

  var rowMenuLastOpenAt = 0;
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

    function closeAll() {
      document.querySelectorAll(".row-menu-panel").forEach(closeRowMenu);
    }

    bindHostNodes(".row-menu-trigger", function (trigger) {
      var panel = trigger.parentElement.querySelector(".row-menu-panel");
      if (!panel) return;
      trigger.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var wasOpen = panel.classList.contains("is-open");
        closeAll();
        if (!wasOpen) {
          rowMenuLastOpenAt = Date.now();
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

    if (claimNode(document, "initRowMenus")) {
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
        if (Date.now() - rowMenuLastOpenAt < 400) {
          var open = document.querySelector(".row-menu-panel.is-open");
          var openTrigger = open ? rowMenuTrigger(open) : null;
          if (openTrigger) positionRowMenu(openTrigger, open);
          return;
        }
        closeAll();
      }, true);
    }
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
      if (!claimNode(select, "initAutomationFields")) return;
      syncAutomationHours(select);
      select.addEventListener("change", function () { syncAutomationHours(select); });
    });
  }

  function initControllerFields() {
    document.querySelectorAll("[data-controller-same-toggle]").forEach(function (checkbox) {
      if (!claimNode(checkbox, "initControllerFields")) return;
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
    if (!claimNode(button, "initFeeTemplateCopy")) return;
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
      var oneBox = document.getElementById("stay_fee_council_account");
      if (oneBox) oneBox.value = account;
      var prefixField = document.getElementById("account_prefix");
      var numberField = document.getElementById("account_number");
      var bankField = document.getElementById("account_bank");
      if (!oneBox && prefixField && numberField && bankField) {
        prefixField.value = parsed && parsed[1] ? parsed[1] : "";
        numberField.value = parsed ? parsed[2] : "";
        bankField.value = parsed ? parsed[3] : "";
      }
    });
  }

  function initHousebookPdfExport() {
    var dialog = document.getElementById("housebook-pdf-dialog");
    if (!dialog) return;
    if (!claimNode(dialog, "initHousebookPdfExport")) return;
    var form = document.getElementById("housebook-pdf-form");
    document.querySelectorAll("[data-housebook-pdf-export]").forEach(function (button) {
      if (!claimNode(button, "initHousebookPdfExport")) return;
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
    if (!claimNode(dialog, "initCsvExport")) return;
    var form = document.getElementById("csv-export-form");
    var pending = { base: "", params: "", scopeLabel: "" };
    var scope = dialog.querySelector("[data-csv-scope-label]");

    document.querySelectorAll("[data-csv-export]").forEach(function (button) {
      if (!claimNode(button, "initCsvExport")) return;
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
    bindHostNodes(ROW_SELECTOR, function (row) {
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

    function setDrawer(open) {
      var sidebar = document.getElementById("app-sidebar");
      var main = document.getElementById("main-content");
      var toggles = document.querySelectorAll("[data-nav-toggle]");
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

    // 0377: only a click slides the rail; restore and resize stay instant.
    function animateRail() {
      document.body.classList.add("sidebar-animating");
      clearTimeout(navState.animateTimer);
      navState.animateTimer = setTimeout(function () { document.body.classList.remove("sidebar-animating"); }, 280);
    }
    function setCollapsed(collapsed, animate) {
      var collapse = document.querySelector("[data-sidebar-collapse]");
      if (animate && collapsed !== document.body.classList.contains("sidebar-collapsed")) animateRail();
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      if (collapse) {
        collapse.setAttribute("aria-expanded", collapsed ? "false" : "true");
        collapse.setAttribute("aria-label", collapsed ? collapse.dataset.labelShow : collapse.dataset.labelHide);
      }
      try {
        localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
      } catch (error) {
        // Private browsing may block storage.
      }
    }

    // 0251: 1024-1279 px always shows the rail (host2.css); there the button
    // opens the full menu over the page instead, never stored.
    var tabletRail = navState.tabletRail || (navState.tabletRail = window.matchMedia("(min-width: 1024px) and (max-width: 1279px)"));
    function syncRailButton() {
      var collapse = document.querySelector("[data-sidebar-collapse]");
      if (!collapse || !tabletRail.matches) return;
      var open = document.body.classList.contains("sidebar-expanded");
      collapse.setAttribute("aria-expanded", open ? "true" : "false");
      collapse.setAttribute("aria-label", open ? collapse.dataset.labelHide : collapse.dataset.labelShow);
    }
    function setExpanded(open, animate) {
      var body = document.body;
      var collapse = document.querySelector("[data-sidebar-collapse]");
      if (open === body.classList.contains("sidebar-expanded")) return;
      if (animate) animateRail();
      if (open) {
        navState.railWasCollapsed = body.classList.contains("sidebar-collapsed");
        body.classList.remove("sidebar-collapsed");
      } else if (navState.railWasCollapsed) {
        body.classList.add("sidebar-collapsed");
      }
      body.classList.toggle("sidebar-expanded", open);
      syncRailButton();
      if (!open && collapse && collapse.dataset.labelShow) {
        // setCollapsed() owns the label outside the tablet range.
        if (!tabletRail.matches) setCollapsed(body.classList.contains("sidebar-collapsed"));
      }
    }

    var stored = null;
    try {
      stored = localStorage.getItem(SIDEBAR_KEY);
    } catch (error) {
      stored = null;
    }
    if (stored === "1") setCollapsed(true);

    if (collapse && claimNode(collapse, "initNavigation")) collapse.addEventListener("click", function () {
      if (tabletRail.matches) { setExpanded(!document.body.classList.contains("sidebar-expanded"), true); return; }
      setCollapsed(!document.body.classList.contains("sidebar-collapsed"), true);
    });
    if (expand && claimNode(expand, "initNavigation")) expand.addEventListener("click", function () {
      if (tabletRail.matches) { setExpanded(true, true); return; }
      setCollapsed(false, true);
    });
    if (claimNode(document, "initNavigation")) {
      document.addEventListener("pointerdown", function (event) {
        var sidebar = document.getElementById("app-sidebar");
        if (document.body.classList.contains("sidebar-expanded") && sidebar && !sidebar.contains(event.target)) setExpanded(false, true);
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && document.body.classList.contains("sidebar-expanded")) setExpanded(false, true);
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
          setDrawer(false);
        }
      });
      document.addEventListener("keydown", function (event) {
        var sidebar = document.getElementById("app-sidebar");
        if (event.key !== "Tab" || !sidebar || !document.body.classList.contains("nav-open")) return;
        var focusable = Array.from(sidebar.querySelectorAll("a, button, summary, input, select")).filter(function (el) {
          return !el.disabled && el.getClientRects().length > 0;
        });
        var first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
      document.addEventListener("host:close-navigation", function () { setDrawer(false); });
    }
    var onRailChange = function () { setExpanded(false); syncRailButton(); if (!tabletRail.matches) setCollapsed(document.body.classList.contains("sidebar-collapsed")); };
    if (claimNode(tabletRail, "initNavigation") && tabletRail.addEventListener) tabletRail.addEventListener("change", onRailChange);
    syncRailButton();

    toggles.forEach(function (button) {
      if (!claimNode(button, "initNavigation")) return;
      button.addEventListener("click", function () {
        setDrawer(!document.body.classList.contains("nav-open"));
      });
    });
    closers.forEach(function (button) {
      if (!claimNode(button, "initNavigation")) return;
      button.addEventListener("click", function () { setDrawer(false); });
    });
    if (claimNode(window, "initNavigation")) window.addEventListener("resize", function () { setDrawer(false); });
    // Self-heal: a rail left inert while the window is wide would swallow every click.
    function healInert() {
      var rail = document.getElementById("app-sidebar");
      var main = document.getElementById("main-content");
      if (isCompact() || document.body.classList.contains("nav-open")) return;
      if (rail && rail.inert) rail.inert = false;
      if (main && main.inert) main.inert = false;
    }
    if (claimNode(document, "initNavigationHeal")) {
      document.addEventListener("pointerdown", healInert, true);
      document.addEventListener("visibilitychange", healInert);
      window.addEventListener("focus", healInert);
      window.addEventListener("pageshow", healInert);
    }
    setDrawer(false);
  }

  function initTogglePanels() {
    document.querySelectorAll("[data-toggle-panel]").forEach(function (button) {
      if (!claimNode(button, "initTogglePanels")) return;
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
      if (!claimNode(button, "initTogglePanels")) return;
      button.addEventListener("click", function () {
        var panel = button.closest(".action-panel");
        if (panel) panel.classList.add("hidden");
      });
    });
    if (new URLSearchParams(window.location.search).get("new") === "1") {
      var addPanel = document.getElementById("add-stay-panel");
      if (addPanel && claimNode(addPanel, "initTogglePanels")) {
        addPanel.classList.remove("hidden");
        var heading = addPanel.querySelector(".ui-section-h h2");
        if (heading) { heading.setAttribute("tabindex", "-1"); heading.style.outline = "none"; heading.focus(); }
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
      if (!claimNode(link, "initDetailsLinks")) return;
      link.addEventListener("click", function () { openTarget(link.hash); });
    });
    if (claimNode(window, "initDetailsLinks")) {
      window.addEventListener("hashchange", function () { openTarget(window.location.hash); });
    }
    openTarget(window.location.hash);
  }

  function initDismissBanners() {
    bindHostNodes("[data-dismiss-banner]", function (button) {
      button.addEventListener("click", function () {
        var banner = button.closest(".dismissible-banner, .banner");
        if (banner) banner.remove();
      });
    });
  }

  function initNotifications() {
    document.querySelectorAll("form[data-notification-dismiss]").forEach(function (form) {
      if (!claimNode(form, "initNotifications")) return;
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
    if (claimNode(document, "feedbackVisibility")) {
      document.addEventListener("visibilitychange", function () {
        document.querySelectorAll("[data-toast]").forEach(function (toast) {
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
      if (!claimNode(toast, "initToasts")) return;
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
      if (!claimNode(form, "initFilterPanels")) return;
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
    if (claimNode(document, "initDateRanges")) {
      document.addEventListener("pointerdown", function (event) {
        document.querySelectorAll("[data-date-range]").forEach(function (range) {
          var popover = range.querySelector("[data-range-popover]");
          if (range._ubyClose && popover && !popover.hidden && !range.contains(event.target)) range._ubyClose(true);
        });
      });
      document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        document.querySelectorAll("[data-date-range]").forEach(function (range) {
          var popover = range.querySelector("[data-range-popover]");
          if (range._ubyClose && popover && !popover.hidden) { event.preventDefault(); range._ubyClose(true); }
        });
      });
    }
    form.querySelectorAll("[data-date-range]").forEach(function (range) {
      if (!claimNode(range, "initDateRanges")) return;
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
        var formatter = { format: function (d) { return String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0") + "." + d.getFullYear(); } };
        caption.textContent = draftFrom && draftUntil ? formatter.format(parse(draftFrom)) + " – " + formatter.format(parse(draftUntil)) : draftFrom ? formatter.format(parse(draftFrom)) + " – …" : draftUntil ? "… – " + formatter.format(parse(draftUntil)) : trigger.dataset.allDates || "";
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
      range._ubyClose = close;
      setCaption(); render();
    });
  }

  function initMonthPickers(form) {
    if (claimNode(document, "initMonthPickers")) {
      document.addEventListener("pointerdown", function (event) {
        document.querySelectorAll("[data-month-picker]").forEach(function (picker) {
          var panel = picker.querySelector("[data-month-grid-panel]");
          if (picker._ubyClose && panel && !panel.hidden && !picker.contains(event.target)) picker._ubyClose(true);
        });
      });
      document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        document.querySelectorAll("[data-month-picker]").forEach(function (picker) {
          var panel = picker.querySelector("[data-month-grid-panel]");
          if (picker._ubyClose && panel && !panel.hidden) { event.preventDefault(); picker._ubyClose(true); }
        });
      });
    }
    form.querySelectorAll("[data-month-picker]").forEach(function (picker) {
      if (!claimNode(picker, "initMonthPickers")) return;
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
      picker._ubyClose = close;
      setCaption(); render();
    });
  }

  /* Legacy auto-submit remains available only to forms that explicitly opt in. */
  function initAutoFilters() {
    document.querySelectorAll("form input[type=checkbox][data-toggle-submit]").forEach(function (input) {
      var toggleForm = input.form;
      if (!toggleForm || !claimNode(input, "initAutoFilters")) return;
      input.addEventListener("change", function () {
        toggleForm.requestSubmit ? toggleForm.requestSubmit() : toggleForm.submit();
      });
    });
    document.querySelectorAll("form[data-auto-submit]").forEach(function (form) {
      if (!claimNode(form, "initAutoFilters")) return;
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
      if (!claimNode(input, "initGeneratedPasswords")) return;
      if (!input.value) fillGeneratedPassword(input);
    });

    document.querySelectorAll("[data-generate-password]").forEach(function (button) {
      if (!claimNode(button, "initGeneratedPasswords")) return;
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
    if (!claimNode(dialog, "initResetPasswordDialog")) return;

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
    if (!claimNode(shell, "initConfirmDialog")) return;
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

    bindHostNodes("form[data-confirm]", function (form) {
      form.addEventListener("submit", function (e) {
        if (form.dataset.confirmBypass === "1") {
          form.dataset.confirmBypass = "";
          return;
        }
        e.preventDefault();
        openDialog(form.getAttribute("data-confirm-message"), form, null);
      });
    });

    bindHostNodes("button[data-confirm]", function (button) {
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

  var powerToolsKeydown = null;
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
      if (item.havel) {
        if (command.open) command.close();
        if (window.UbyHavel && window.UbyHavel.open) window.UbyHavel.open(item.query || "");
        else window.location.assign(item.url);
        return;
      }
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
      function fold(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase(); }
      var words = fold(query).trim().split(/\s+/).filter(Boolean);
      function fuzzyScore(haystack, word) {
        return haystack.indexOf(word);
      }
      var askHavel = null;
      visible = items.map(function (item) {
        if (item.havel) { askHavel = item; return null; }
        var haystack = fold([item.label, item.meta, item.group, item.keywords].join(" "));
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
      var noMatch = false;
      if (!visible.length && askHavel && words.length) {
        var asked = String(query || "").trim();
        noMatch = true;
        visible = [{ label: askHavel.label + ": " + asked, group: askHavel.group, url: askHavel.url, havel: true, query: asked }];
      }
      if (!visible.length) {
        var empty = document.createElement("p");
        empty.className = "command-empty";
        empty.textContent = results.getAttribute("data-empty") || "";
        results.appendChild(empty);
        return;
      }
      if (noMatch) { var none = document.createElement("p"); none.className = "command-empty"; none.textContent = results.getAttribute("data-empty") || ""; results.appendChild(none); }
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
      if (!claimNode(button, "initPowerTools")) return;
      button.addEventListener("click", openCommand);
    });
    document.querySelectorAll("[data-command-close]").forEach(function (button) {
      if (!claimNode(button, "initPowerTools")) return;
      button.addEventListener("click", closeCommand);
    });
    if (command && claimNode(command, "initPowerTools")) {
      command.addEventListener("close", clearCommandCopyError);
      command.addEventListener("click", function (event) {
        if (event.target === command) closeCommand();
      });
    }
    document.querySelectorAll("[data-shortcuts-open]").forEach(function (button) {
      if (!claimNode(button, "initPowerTools")) return;
      button.addEventListener("click", function () {
        document.dispatchEvent(new Event("host:close-navigation"));
        if (shortcuts && typeof shortcuts.showModal === "function") shortcuts.showModal();
      });
    });
    document.querySelectorAll("[data-shortcuts-close]").forEach(function (button) {
      if (!claimNode(button, "initPowerTools")) return;
      button.addEventListener("click", function () { if (shortcuts) shortcuts.close(); });
    });

    if (input && claimNode(input, "initPowerTools")) {
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

    powerToolsKeydown = function (event) {
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
    };
    if (claimNode(document, "initPowerTools")) {
      document.addEventListener("keydown", function (event) { if (powerToolsKeydown) powerToolsKeydown(event); });
    }
  }

  function initSavedViews() {
    var key = "ubyhost-saved-stay-views";
    var container = document.querySelector("[data-saved-views]");
    var button = document.querySelector("[data-save-view]");
    if (button && !claimNode(button, "initSavedViews")) return;
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
      if (!claimNode(form, "initInlineEdit")) return;
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
      if (!claimNode(form, "initSubmitGuard")) return;
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
    if (claimNode(window, "initSubmitGuard")) {
      window.addEventListener("pageshow", function () {
        document.querySelectorAll("[data-submit-guard]").forEach(function (button) {
          button.disabled = false;
          button.removeAttribute("data-submit-guard");
        });
      });
    }
  }

  /* 0093 help: contextual "?" tips (macro help_tip). Hover/focus/tap open, Esc and outside click close. */
  var helpTipState = { current: null, timer: null };
  function initHelpTips() {
    var tips = Array.prototype.slice.call(document.querySelectorAll("[data-help-tip]"));
    if (!tips.length) return;

    /* 0901: a "?" never drops onto its own line. The last word before it (or a short inline element) and the "?"
       share one no-break box, so a wrapping heading or label breaks before that word instead of before the "?". */
    tips.forEach(function (tip) {
      var parent = tip.parentNode;
      if (!parent || parent.classList.contains("tip-tail")) return;
      var prev = tip.previousSibling;
      while (prev && prev.nodeType === 3 && !prev.nodeValue.trim()) prev = prev.previousSibling;
      if (prev && prev.nodeType === 1 && /^(LABEL|H[1-6]|LEGEND)$/.test(prev.tagName)) {
        /* the "?" sits beside its label: move it inside, so it wraps with the label's last word */
        prev.appendChild(tip);
        parent = prev;
        prev = tip.previousSibling;
        while (prev && prev.nodeType === 3 && !prev.nodeValue.trim()) prev = prev.previousSibling;
      }
      var tail = null;
      if (prev && prev.nodeType === 3) {
        var m = /^([\s\S]*?)(\S+)(\s*)$/.exec(prev.nodeValue);
        if (!m) return;
        tail = document.createElement("span");
        tail.className = "tip-tail";
        prev.nodeValue = m[1];
        tail.appendChild(document.createTextNode(m[2]));
      } else if (prev && prev.nodeType === 1 && /^(SPAN|B|STRONG|EM|A|SMALL|BUTTON)$/.test(prev.tagName) && (prev.textContent || "").length <= 24 && !/flex|grid/.test(window.getComputedStyle(parent).display)) {
        tail = document.createElement("span");
        tail.className = "tip-tail";
        parent.insertBefore(tail, prev);
        tail.appendChild(prev);
      }
      if (!tail) return;
      if (!tail.parentNode) parent.insertBefore(tail, tip);
      tail.appendChild(tip);
    });

    function place(tip) {
      var btn = tip.querySelector(".help-tip-btn");
      var body = tip.querySelector(".help-tip-body");
      var margin = 16; /* 0912b: 16 px gutter on every side, max 360 px, so a tooltip never leaves a 320 px phone */
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      var wide = vw >= 1024;
      var width = vw < 600 ? Math.min(360, vw - 2 * margin) : Math.min(320, vw - 2 * margin); /* 1003 fix: 390 px phone gets 358 px, lint needs >= 356 */
      body.style.width = width + "px";
      body.style.maxWidth = width + "px";
      if (!wide) {
        /* Phones: inline styles beat every page-level rule; the JS owns the position. */
        body.style.position = "fixed";
        body.style.right = "auto";
        body.style.left = "0px";
        body.style.top = "0px";
      } else {
        body.style.position = "";
        body.style.right = "";
      }
      var r = btn.getBoundingClientRect();
      var w = body.offsetWidth || width;
      var h = body.offsetHeight;
      var left = tip.classList.contains("help-tip-end") ? r.right - w : r.left;
      left = Math.max(margin, Math.min(left, vw - w - margin));
      /* 0912c: on phones the fixed tab bar covers the bottom of the screen; the visible bottom is above it. */
      /* 0912f: the floor is the top of the lowest-starting visible fixed element that overlaps the
         tooltip horizontally (tab bar, chat button), minus 16; the tooltip never covers its own trigger. */
      var floorY = window.innerHeight - 16;
      var fixedEls = document.querySelectorAll("nav.tabs, .ui-tabbar, .havel-fab");
      for (var bi = 0; bi < fixedEls.length; bi++) {
        var bEl = fixedEls[bi];
        var bcs = window.getComputedStyle(bEl);
        if (bcs.position !== "fixed" || bcs.display === "none" || bcs.visibility === "hidden" || bEl.offsetHeight <= 0) continue;
        var br = bEl.getBoundingClientRect();
        if (br.right <= left || br.left >= left + w) continue;
        if (br.top - 16 < floorY) floorY = br.top - 16;
      }
      var top = r.bottom + 8;
      if (top + h > floorY && r.top - 8 - h >= margin) top = r.top - 8 - h;
      top = Math.max(margin, Math.min(top, floorY - h));
      if (wide) {
        // Desktop: the body is absolutely positioned inside .help-tip, so the viewport
        // coordinates must be made relative to its offset parent (else it drifts right).
        var ob = body.offsetParent ? body.offsetParent.getBoundingClientRect() : { left: 0, top: 0 };
        body.style.left = (left - ob.left) + "px";
        body.style.top = (top - ob.top) + "px";
      } else {
        /* The box sits at left:0 / top:0 now, so its rect is the origin of its containing block
           (0,0 when fixed to the viewport; non-zero inside a transformed ancestor). Correct for it. */
        var o = body.getBoundingClientRect();
        body.style.left = (left - o.left) + "px";
        body.style.top = (top - o.top) + "px";
      }
    }
    function close(tip) {
      tip.classList.remove("is-open");
      tip.removeAttribute("data-pinned");
      tip.querySelector(".help-tip-btn").setAttribute("aria-expanded", "false");
      if (helpTipState.current === tip) helpTipState.current = null;
    }
    function open(tip, pinned) {
      if (helpTipState.current && helpTipState.current !== tip) close(helpTipState.current);
      window.clearTimeout(helpTipState.timer);
      helpTipState.current = tip;
      tip.classList.add("is-open");
      tip.classList.toggle("help-tip-end", tip.getBoundingClientRect().left > window.innerWidth / 2);
      tip.querySelector(".help-tip-btn").setAttribute("aria-expanded", "true");
      if (pinned) tip.setAttribute("data-pinned", "1");
      place(tip);
    }
    function closeSoon(tip) {
      window.clearTimeout(helpTipState.timer);
      helpTipState.timer = window.setTimeout(function () {
        if (!tip.hasAttribute("data-pinned") && !tip.contains(document.activeElement)) close(tip);
      }, 150);
    }

    tips.forEach(function (tip) {
      if (!claimNode(tip, "initHelpTips")) return;
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
    if (claimNode(document, "initHelpTips")) {
      document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape" || !helpTipState.current) return;
        var tip = helpTipState.current;
        close(tip);
        tip.querySelector(".help-tip-btn").focus();
      });
      document.addEventListener("click", function (e) {
        if (helpTipState.current && !helpTipState.current.contains(e.target)) close(helpTipState.current);
      });
      function reflow() { if (helpTipState.current) place(helpTipState.current); }
      window.addEventListener("resize", reflow);
      window.addEventListener("scroll", reflow, { capture: true, passive: true });
    }
  }

  /* 1003: the page "?" (details.page-help). Mouse: hover or keyboard focus opens it under the dot (above if no room),
     leaving closes after 150 ms, click pins it. Touch: tap toggles, tap outside closes. Esc closes. No JS: native details. */
  var pageHelpState = { current: null, timer: null };
  function initPageHelp() {
    var items = Array.prototype.slice.call(document.querySelectorAll("details.page-help"));
    if (!items.length) return;
    var hoverOk = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)");
    function place(d) {
      var body = d.querySelector(".page-help-body");
      var wrap = d.closest(".page-help-wrap") || d;
      if (!body || !d.open) return;
      var m = 8;
      var vw = document.documentElement.clientWidth;
      var vh = window.innerHeight;
      var w = Math.min(320, vw - 2 * m);
      body.style.position = "absolute"; /* CSS: .page-help-wrap is the containing block, so the box moves with its ? */
      body.style.width = w + "px";
      body.style.maxWidth = w + "px";
      body.style.right = "auto";
      body.style.margin = "0";
      body.style.transform = "none";
      body.style.top = "calc(100% + 8px)";
      body.style.left = "0px";
      var wr = wrap.getBoundingClientRect();
      var h = body.offsetHeight;
      body.style.left = Math.max(m - wr.left, Math.min(0, vw - m - w - wr.left)) + "px"; /* keep inside the viewport */
      if (wr.bottom + 8 + h > vh - m && wr.top - 8 - h >= m) body.style.top = (-(h + 8)) + "px"; /* flip above if no room below */
    }
    function close(d) {
      d.open = false;
      d.removeAttribute("data-pinned");
      if (pageHelpState.current === d) pageHelpState.current = null;
    }
    function show(d, pinned) {
      if (pageHelpState.current && pageHelpState.current !== d) close(pageHelpState.current);
      window.clearTimeout(pageHelpState.timer);
      pageHelpState.current = d;
      d.open = true;
      if (pinned) d.setAttribute("data-pinned", "1");
      place(d);
    }
    function closeSoon(d) {
      window.clearTimeout(pageHelpState.timer);
      pageHelpState.timer = window.setTimeout(function () {
        if (!d.hasAttribute("data-pinned") && !d.contains(document.activeElement)) close(d);
      }, 150);
    }
    items.forEach(function (d) {
      if (!claimNode(d, "initPageHelp")) return;
      var summary = d.querySelector("summary");
      d.addEventListener("toggle", function () { if (d.open) place(d); });
      if (summary) {
        summary.addEventListener("click", function (e) {
          e.preventDefault(); /* we own open/close, so hover and click never fight over the native toggle */
          if (d.open && d.hasAttribute("data-pinned")) close(d);
          else show(d, true);
        });
        summary.addEventListener("focus", function () {
          if (hoverOk && hoverOk.matches && summary.matches(":focus-visible")) show(d, false);
        });
      }
      d.addEventListener("pointerenter", function (e) {
        if (e.pointerType === "mouse" && hoverOk && hoverOk.matches) show(d, false);
      });
      d.addEventListener("pointerleave", function (e) {
        if (e.pointerType === "mouse" && hoverOk && hoverOk.matches) closeSoon(d);
      });
      d.addEventListener("focusout", function (e) {
        if (!d.contains(e.relatedTarget) && !d.hasAttribute("data-pinned")) close(d);
      });
    });
    if (claimNode(document, "initPageHelp")) {
      document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape" || !pageHelpState.current) return;
        var d = pageHelpState.current;
        close(d);
        var s = d.querySelector("summary");
        if (s) s.focus();
      });
      document.addEventListener("click", function (e) {
        if (pageHelpState.current && !pageHelpState.current.contains(e.target)) close(pageHelpState.current);
      });
      function reflow() { if (pageHelpState.current) place(pageHelpState.current); }
      window.addEventListener("resize", reflow);
      window.addEventListener("scroll", reflow, { capture: true, passive: true });
    }
  }


  /* 0076: a page with several independent forms (the business editor's
     Business details and Invoice details). Saving one form, or leaving the
     page, asks first when another of them holds unsaved changes. */
  // 0955: dirty means a control differs from its loaded value; typing the original back clears it.
  function formSnapshot(form) {
    var rows = [];
    new FormData(form).forEach(function (value, key) {
      rows.push([key, value instanceof File ? "file:" + value.name : String(value)]);
    });
    return JSON.stringify(rows.sort());
  }
  function recomputeDirty(form) {
    if (!form._ubyBase) return;
    var dirty = form.getAttribute("data-dirty-start") === "1" || formSnapshot(form) !== form._ubyBase;
    if (dirty) form.setAttribute("data-dirty", "1"); else form.removeAttribute("data-dirty");
  }

  function initUnsavedForms() {
    var forms = Array.prototype.slice.call(document.querySelectorAll("form[data-unsaved-guard]"));
    if (!forms.length) return;
    forms.forEach(function (form) {
      if (!claimNode(form, "initUnsavedForms")) return;
      form._ubyBase = formSnapshot(form);
      var mark = function () { recomputeDirty(form); };
      form.addEventListener("input", mark);
      form.addEventListener("change", mark);
      form.addEventListener("submit", function () { form._ubySubmitting = true; });
    });
    // 0952: door-code controls sit outside their form and name it with form="...", so they bubble to document, not to the form.
    if (!document._ubyOutsideMark) {
      document._ubyOutsideMark = true;
      var markOutside = function (event) {
        var owner = event.target && event.target.form;
        if (owner && owner.hasAttribute("data-unsaved-guard") && !owner.contains(event.target)) recomputeDirty(owner);
      };
      document.addEventListener("input", markOutside);
      document.addEventListener("change", markOutside);
    }
    // 0955: a focused field under the sticky Save row scrolls clear of it (scroll-padding alone does not move a visible field).
    if (!document._ubyFocusClear) {
      document._ubyFocusClear = true;
      var keepClear = function (field) {
        if (!field || !field.closest || !field.closest("#property-settings-form")) return;
        var bar = document.querySelector(".savebar[data-for='property-settings-form']");
        if (!bar || getComputedStyle(bar).display === "none") return;
        field.scrollIntoView({ block: "nearest" });
      };
      document.addEventListener("focusin", function (event) { keepClear(event.target); });
      // The bar appears on the first edit, after the field already has focus.
      document.addEventListener("input", function (event) { keepClear(event.target); });
    }
    if (claimNode(window, "initUnsavedForms")) {
      window.addEventListener("beforeunload", function (event) {
        var current = Array.prototype.slice.call(document.querySelectorAll("form[data-unsaved-guard]"));
        var unsaved = current.some(function (form) {
          return form.getAttribute("data-dirty") === "1" && form._ubySubmitting !== true;
        });
        current.forEach(function (form) { form._ubySubmitting = false; });
        if (!unsaved) return;
        event.preventDefault();
        event.returnValue = "";
      });
    }
  }

  /* 0540: on the phone the property page opens with every section closed, as the mockup.
     Only a section opened by default (no ?section=) is closed; a requested one stays open. */
  function initPhoneDefaultClosed() {
    if (!window.matchMedia("(max-width: 1023px)").matches) return;
    if (/[?&](section|view)=/.test(window.location.search) || window.location.hash) return;
    document.querySelectorAll("details#sec-basics").forEach(function (node) {
      if (!claimNode(node, "initPhoneDefaultClosed")) return;
      node.removeAttribute("open");
    });
  }
  /* 0543: an aside link to a property section (#sec-*) opens that section; a #sec-* hash opens it on load */
  function initPropSectionLinks() {
    function openSection(hash) {
      if (!/^#(sec-|door-code$|smart-locks$)/.test(hash || "")) return;
      var target = document.getElementById(hash.slice(1));
      // 0952: #door-code and #smart-locks sit inside the #sec-lock accordion: open that one and scroll to the target.
      var node = target && !/^sec-/.test(target.id) && target.closest ? target.closest("details.prop-sec") : target;
      if (node && node.tagName === "DETAILS" && node.classList.contains("prop-sec")) {
        node.open = true;
        if (target !== node && target.scrollIntoView) target.scrollIntoView();
      }
    }
    document.querySelectorAll('a[href^="#sec-"]').forEach(function (link) {
      if (!claimNode(link, "initPropSectionLinks")) return;
      link.addEventListener("click", function () { openSection(link.getAttribute("href")); });
      /* Keyboard: activate opens the section like click (B04 Enter key from Playwright; hash sync can race in CI). */
      link.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" && e.key !== " ") return;
        var h = link.getAttribute("href");
        if (!h || h.charAt(0) !== "#") return;
        e.preventDefault();
        openSection(h);
        try {
          history.replaceState(null, "", window.location.pathname + window.location.search + h);
        } catch (_) {}
      });
    });
    if (window.location.hash) openSection(window.location.hash);
    if (claimNode(window, "initPropSectionLinks")) {
      window.addEventListener("hashchange", function () { openSection(window.location.hash); });
    }
  }
  /* 0547: the one-page property form. Restores what the removed tabs did: switch
     status text, an invalid field opens its closed section, the calendar connect
     panel opens for ?add_calendar=1 or its hash, and Save returns to the last
     opened section. */
  var PROPERTY_RETURN_SECTION = { "sec-basics": "property", "sec-police": "reporting", "sec-fee": "reporting", "sec-messages": "guests", "sec-lock": "lock" };
  function initPropertyPage() {
    var form = document.querySelector("form#property-settings-form");
    if (form && claimNode(form, "initPropertyPage")) {
      var lastOpened = null;
      var returnInput = form.querySelector("input[data-property-return]");
      // 0952: #sec-lock sits outside the form now, so listen on the document for it too.
      document.addEventListener("toggle", function (event) {
        var node = event.target;
        if (node.tagName === "DETAILS" && node.open && node.id && node.matches("details.prop-sec") && (form.contains(node) || node.id === "sec-lock")) lastOpened = node.id;
      }, true);
      form.addEventListener("submit", function () {
        var group = PROPERTY_RETURN_SECTION[lastOpened];
        if (!group || !returnInput) return;
        returnInput.value = returnInput.value.replace(/([?&]section=)[^&#]*/, "$1" + group);
      });
      // A switch says "Not saved yet" until the form is saved; never "Enabled".
      // 0952: door-code switches sit outside the form and name it with form="...".
      Array.prototype.slice.call(document.querySelectorAll("input[data-switch-saved]")).filter(function (input) {
        return input.form === form;
      }).forEach(function (input) {
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
      // A field the browser refuses may sit in a closed section: open it first,
      // so the browser can focus the field and say what is wrong.
      var revealing = false;
      form.addEventListener("invalid", function (event) {
        if (revealing) return;
        revealing = true;
        window.setTimeout(function () { revealing = false; }, 0);
        var sec = event.target.closest && event.target.closest("details.prop-sec");
        if (sec) sec.open = true;
      }, true);
    }
    var connect = document.getElementById("calendar-connect");
    if (!connect || !claimNode(connect, "initPropertyPage")) return;
    var hash = window.location.hash;
    var target = null;
    try { target = hash.length > 1 ? document.getElementById(decodeURIComponent(hash.slice(1))) : null; } catch (_) { target = null; }
    var wanted = new URLSearchParams(window.location.search).get("add_calendar") === "1"
      || !!target && (target === connect || connect.contains(target));
    if (!wanted) return;
    connect.classList.remove("is-collapsed");
    var calendars = document.getElementById("sec-calendars");
    if (calendars && calendars.tagName === "DETAILS") calendars.open = true;
  }
  /* ---- 0084 O1: unsaved changes, in-app Save / Discard / Stay ----------------
     A form with data-unsaved-guard that holds changes (data-dirty, set by
     initUnsavedForms) asks before an in-app link leaves it:
       Save    submits that form as usual; the server validates and returns the
               host where the form's return_to / next says (no chained jump: a
               refused save must stay on its error page).
       Discard restores the loaded values, then follows the link.
       Stay    (also Esc) keeps the edits and returns focus to the link.
     Links that keep the draft on screen (cards and anchors into
     Settings, in-page #anchors) do not ask. Tab close, reload and
     other sites keep the browser's own prompt. Without JavaScript nothing here
     runs and the forms post as before. */
  function initUnsavedDialog() {
    var forms = Array.prototype.slice.call(document.querySelectorAll("form[data-unsaved-guard]"));
    var dialog = document.getElementById("unsaved-dialog");
    if (!forms.length) return;
    var pendingLink = null;

    function isDirty(form) { return form.getAttribute("data-dirty") === "1"; }
    // 0955: the property Save bar sits outside its form, linked by data-for="<form id>".
    function formBars(form) {
      return form.id ? Array.prototype.slice.call(document.querySelectorAll('.savebar[data-for="' + form.id + '"]')) : [];
    }
    function resetButtons(form) {
      var out = Array.prototype.slice.call(form.querySelectorAll("[data-unsaved-reset]"));
      formBars(form).forEach(function (bar) { out = out.concat(Array.prototype.slice.call(bar.querySelectorAll("[data-unsaved-reset]"))); });
      return out;
    }
    function dirtyForms() { return forms.filter(isDirty); }

    // The "Discard changes" button beside Save shows only while its form is dirty.
    function syncResetButtons() {
      forms.forEach(function (form) {
        formBars(form).concat(Array.prototype.slice.call(form.querySelectorAll(".savebar"))).forEach(function (bar) {
          bar.classList.toggle("is-dirty", isDirty(form));
        });
      });
    }

    // Back to the loaded values. Switch labels and dependent fields listen for
    // "change", so tell them; then the form is clean again.
    function discard(form) {
      form.reset();
      // 0952: form.elements also holds controls outside the form that name it with form="...".
      Array.prototype.slice.call(form.elements).filter(function (el) {
        return el.matches("select, input[type=checkbox], input[type=radio]");
      }).forEach(function (el) {
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });
      // Cancel is the new loaded state: the reset values become the base for the next edit.
      if (form.getAttribute("data-dirty-start") !== "1") form._ubyBase = formSnapshot(form);
      recomputeDirty(form);
    }

    // True when following this link keeps the draft on screen.
    function keepsDraft(url) {
      var here = window.location;
      return url.pathname === here.pathname && url.search === here.search && !!url.hash;
    }

    // 0952: same as initUnsavedForms, for controls outside the form: update the Save bar and reset buttons.
    if (!document._ubyOutsideSync) {
      document._ubyOutsideSync = true;
      var syncOutside = function (event) {
        var owner = event.target && event.target.form;
        if (owner && forms.indexOf(owner) > -1 && !owner.contains(event.target)) {
          syncResetButtons();
        }
      };
      document.addEventListener("input", syncOutside);
      document.addEventListener("change", syncOutside);
    }
    forms.forEach(function (form) {
      if (!claimNode(form, "initUnsavedDialog")) return;
      form.addEventListener("input", syncResetButtons);
      form.addEventListener("change", syncResetButtons);
      resetButtons(form).forEach(function (button) {
        button.addEventListener("click", function (event) {
          // After a failed save the page holds the posted values: the link reloads the saved page.
          if (form.getAttribute("data-dirty-start") === "1") { form._ubySubmitting = true; return; }
          event.preventDefault();
          discard(form);
          syncResetButtons();
        });
      });
    });
    syncResetButtons();
    // Back/Forward may restore typed values without input events.
    if (claimNode(window, "initUnsavedDialog")) window.addEventListener("pageshow", syncResetButtons);

    if (!dialog || typeof dialog.showModal !== "function") return;
    if (!claimNode(dialog, "initUnsavedDialog")) return;
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
      // 0955: Cancel resets the form in place; it is not a page change to guard.
      if (link.hasAttribute("data-unsaved-reset")) return;
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

  var pageHooks = [];
  var pageStarted = false;
  window.UbyHost = window.UbyHost || {};
  window.UbyHost.onPage = function (fn) { pageHooks.push(fn); if (pageStarted) fn(); };

  function initSectionNotice() {
    var n = document.querySelector("[data-section-notice]");
    if (!n || !claimNode(n, "initSectionNotice")) return;
    n.scrollIntoView({ block: "center" });
    n.focus({ preventScroll: true });
  }

  // 1024: a failed property save opens the section with the first error, scrolls to it and focuses it; a saved page keeps the banner in view.
  function initSaveSummary() {
    var s = document.querySelector("[data-save-summary]");
    if (!s || !claimNode(s, "initSaveSummary")) return;
    var id = s.getAttribute("data-first-error");
    if (!id) {
      s.scrollIntoView({ block: "nearest" });
      return;
    }
    var t = document.getElementById(id);
    if (!t) {
      s.scrollIntoView({ block: "center" });
      s.focus({ preventScroll: true });
      return;
    }
    var sec = t.closest("details");
    if (sec) sec.open = true;
    t.scrollIntoView({ block: "center" });
    t.focus({ preventScroll: true });
  }

  // 1024: in the editor the stay-fee boxes the app needs get a star and aria-required while the rate is above 0.
  function initStayFeeStars() {
    var rate = document.getElementById("stay_fee_rate_czk");
    if (!rate || !document.getElementById("property-settings-form") || !document.getElementById("sec-fee")) return;
    if (!claimNode(rate, "initStayFeeStars")) return;
    function sync() {
      var needed = parseFloat(rate.value) > 0;
      ["stay_fee_vs", "stay_fee_council_account", "stay_fee_authority_name"].forEach(function (id) {
        var input = document.getElementById(id);
        var label = document.querySelector('label[for="' + id + '"]');
        if (!input || !label) return;
        input.setAttribute("aria-required", needed ? "true" : "false");
        var star = label.querySelector(".req-star");
        if (needed && !star) {
          star = document.createElement("span");
          star.className = "req-star";
          star.setAttribute("aria-hidden", "true");
          star.textContent = "*";
          var tip = label.querySelector(".help-tip, button");
          if (tip && tip.parentNode) tip.parentNode.insertBefore(star, tip);
          else label.appendChild(star);
        } else if (!needed && star) {
          star.remove();
        }
      });
    }
    rate.addEventListener("input", sync);
  }

  // 0971: one dismiss control on every inline success notice (success_notice macro, section notice, cleaning notice).
  function initSuccessNotices() {
    if (!document.body.classList.contains("host-workspace")) return;
    if (document.body.classList.contains("admin-workspace")) return;
    var root = feedbackRoot();
    var label = (root && root.getAttribute("data-dismiss-label")) || "Dismiss notification";
    Array.prototype.forEach.call(document.querySelectorAll("[data-success-notice], .section-notice.ok, p.cleaning-notice"), function (notice) {
      if (!claimNode(notice, "initSuccessNotices")) return;
      var close = notice.querySelector("[data-success-dismiss]");
      if (!close) {
        close = document.createElement("button");
        close.type = "button";
        close.className = "success-notice-close";
        close.setAttribute("data-success-dismiss", "");
        close.setAttribute("aria-label", label);
        close.textContent = "\u00d7";
        notice.appendChild(close);
      }
      close.addEventListener("click", function () {
        var section = notice.closest("section");
        var heading = (section && section.querySelector("h2")) || document.querySelector("main h1, h1");
        notice.remove();
        if (!heading) return;
        if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      });
    });
  }

  function initPage() {
    initPhoneDefaultClosed();
    initPropSectionLinks();
    initPropertyPage();
    initCopy();
    // 0955: widgets that disable or fill fields first, so the dirty baseline is their settled state.
    initAutomationFields();
    initControllerFields();
    initUnsavedForms();
    initUnsavedDialog();
    initSectionNotice();
    initSaveSummary();
    initStayFeeStars();
    initSuccessNotices();
    initHelpTips();
    initPageHelp();
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
    initFilterPanels();
    initAutoFilters();
    initGeneratedPasswords();
    initResetPasswordDialog();
    initConfirmDialog();
    initSubmitGuard();
    initPowerTools();
    initSavedViews();
    initInlineEdit();
    pageStarted = true;
    pageHooks.forEach(function (fn) { fn(); });
  }
  window.UbyHost = window.UbyHost || {};
  window.UbyHost.initPage = initPage;
  document.addEventListener("turbo:load", initPage);
  if (!window.Turbo) document.addEventListener("DOMContentLoaded", initPage);
  // Forms stay full page loads: Turbo must not submit them.
  if (window.Turbo) window.Turbo.config.forms.mode = "off";
})();
