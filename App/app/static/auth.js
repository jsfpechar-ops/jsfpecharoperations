/* The one interactive thing an auth page needs: copying a value such as the
   two-factor setup key. Deliberately a small copy of the [data-copy] handler in
   app.js rather than app.js itself, which carries the whole host chrome. */
(function () {
  "use strict";

  function copyText(button) {
    var target = document.getElementById(button.getAttribute("data-copy"));
    if (!target) return;
    // Works for form fields and for blocks of text such as the setup key.
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
        var copyLabel = button.getAttribute("data-copy-label") || "";
        if (label) {
          button.textContent = label;
          button.setAttribute("aria-label", label);
        }
        setTimeout(function () {
          button.classList.remove("copied");
          if (label) {
            button.textContent = copyLabel;
            if (copyLabel) button.setAttribute("aria-label", copyLabel);
          }
        }, 1600);
      });
    } catch (error) {
      // The value stays selected so it can still be copied by hand.
    }
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      copyText(button);
    });
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });
})();
