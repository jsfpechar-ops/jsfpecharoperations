/* Design v2 shell: the More tab opens a bottom sheet (MASTER 6.2.4).
   Without JavaScript the tab is a plain link to Settings. */
(function () {
  "use strict";
  function sheetFor(trigger) {
    return document.getElementById(trigger.getAttribute("data-sheet-open"));
  }
  document.addEventListener("click", function (event) {
    var opener = event.target.closest ? event.target.closest("[data-sheet-open]") : null;
    if (opener) {
      var sheet = sheetFor(opener);
      if (sheet && sheet.hasAttribute("data-havel-modeless") && typeof sheet.show === "function") {
        event.preventDefault();
        if (!sheet.open) sheet.show();
        return;
      }
      if (sheet && typeof sheet.showModal === "function") {
        event.preventDefault();
        if (!sheet.open) sheet.showModal();
      }
      return;
    }
    var closer = event.target.closest ? event.target.closest("[data-sheet-close]") : null;
    if (closer) {
      var dialog = closer.closest("dialog");
      if (dialog) dialog.close();
      return;
    }
    var open = event.target.closest ? event.target.closest("dialog.ui-dialog[open]") : null;
    if (open && event.target === open && !open.hasAttribute("data-havel-modeless")) open.close();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var active = document.activeElement;
    var dialog = active && active.closest ? active.closest("dialog[data-havel-modeless][open]") : null;
    if (dialog) {
      event.preventDefault();
      dialog.close();
    }
  });
  document.addEventListener("click", function (event) {
    var palette = event.target.closest ? event.target.closest("#more-sheet [data-command-open]") : null;
    if (palette) {
      var s = document.getElementById("more-sheet");
      if (s && s.open) s.close();
    }
  }, true);
})();
