/* WP09: opt-out and opt-back-in for website analytics, loaded only on /privacy
 * and only while PostHog is configured. The tracker counts nothing while
 * localStorage "ubyhost.analytics.disabled" is set. The key is written only
 * when the visitor clicks the link, so no consent is needed for it. Listed in
 * cookie_inventory.py. */
(function () {
  "use strict";
  var KEY = "ubyhost.analytics.disabled";
  var root = document.getElementById("analytics-optout");
  if (!root) return;

  function isOff() {
    try {
      return window.localStorage.getItem(KEY) !== null;
    } catch (err) {
      return false;
    }
  }

  function render() {
    var off = isOff();
    var states = root.querySelectorAll("[data-optout-when]");
    for (var i = 0; i < states.length; i++) {
      states[i].hidden = (states[i].getAttribute("data-optout-when") === "off") !== off;
    }
  }

  root.addEventListener("click", function (event) {
    var link = event.target.closest("[data-optout-action]");
    if (!link) return;
    event.preventDefault();
    try {
      if (link.getAttribute("data-optout-action") === "disable") {
        window.localStorage.setItem(KEY, "1");
      } else {
        window.localStorage.removeItem(KEY);
      }
    } catch (err) {
      /* Storage blocked: nothing to change, the state below stays truthful. */
    }
    render();
    var shown = root.querySelector("[data-optout-when]:not([hidden]) [data-optout-action]");
    if (shown) shown.focus();
  });

  render();
})();
