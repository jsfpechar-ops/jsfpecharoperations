(function () {
  var form = document.getElementById("claim-confirm-form");
  var secret = document.getElementById("claim-secret");
  if (!form || !secret) return;
  var hash = (window.location.hash || "").replace(/^#/, "");
  var match = hash.match(/(?:^|&|[?])c=([^&]+)/) || hash.match(/^c=(.+)$/);
  if (!match && hash.indexOf("=") === -1 && hash.length > 16) {
    secret.value = hash;
  } else if (match) {
    secret.value = decodeURIComponent(match[1]);
  }
  if (window.history && window.history.replaceState) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
})();
