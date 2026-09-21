(() => {
  const reel = document.querySelector("[data-product-reel]");
  if (!reel) return;

  const scenes = [...reel.querySelectorAll("[data-scene]")];
  const progress = [...reel.querySelectorAll("[data-progress]")];
  const toggle = reel.querySelector("[data-reel-toggle]");
  const icon = reel.querySelector("[data-reel-icon]");
  const caption = reel.querySelector("[data-reel-caption]");
  const labels = reel.querySelector("[data-reel-labels]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const stage = reel.closest(".demo-wrap");
  const intervalMs = 3000;
  let active = reducedMotion.matches ? scenes.length - 1 : 0;
  let timer = null;
  let paused = reducedMotion.matches;

  const labelFor = (index) => labels?.dataset[`label${index}`] || "";

  function render() {
    scenes.forEach((scene, index) => {
      scene.classList.toggle("is-active", index === active);
      scene.setAttribute("aria-hidden", index === active ? "false" : "true");
    });
    progress.forEach((item, index) => {
      item.classList.toggle("is-active", index === active);
    });
    caption.textContent = labelFor(active);
    reel.classList.toggle("is-paused", paused);
    if (stage) stage.classList.toggle("is-reduced", reducedMotion.matches);
    toggle.disabled = reducedMotion.matches;
    icon.textContent = paused ? "▶" : "Ⅱ";
    toggle.setAttribute(
      "aria-label",
      paused ? toggle.dataset.play : toggle.dataset.pause
    );
  }

  function stop() {
    if (timer) window.clearInterval(timer);
    timer = null;
  }

  function start() {
    stop();
    if (paused || reducedMotion.matches) return;
    timer = window.setInterval(() => {
      active = (active + 1) % scenes.length;
      render();
    }, intervalMs);
  }

  function setMotionPreference() {
    stop();
    if (reducedMotion.matches) {
      active = scenes.length - 1;
      paused = true;
    }
    render();
    start();
  }

  toggle.addEventListener("click", () => {
    if (reducedMotion.matches) return;
    paused = !paused;
    render();
    start();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });

  reducedMotion.addEventListener?.("change", setMotionPreference);
  render();
  start();
})();
