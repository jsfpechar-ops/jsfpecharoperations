// 0404: the Leon setup import step reloads itself while the listing is being fetched.
(function () {
  if (!document.querySelector("[data-leon-import-wait]")) return;
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    if (tries > 30) { clearInterval(timer); return; }
    if (document.hidden) return;
    window.location.reload();
  }, 10000);
})();
