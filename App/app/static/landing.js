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
  const dwellMs = 3000;
  const last = scenes.length - 1;
  // One pass through the four scenes, then it rests on the last one. DESIGN.md
  // forbids looping motion, and a reel that never stops competes with the CTA
  // sitting right above it. Replay is the way back in.
  let active = reducedMotion.matches ? last : 0;
  let mode = reducedMotion.matches ? "done" : "playing";
  let timer = null;

  const labelFor = (index) => labels?.dataset[`label${index}`] || "";

  function controlLabel() {
    if (mode === "playing") return toggle.dataset.pause;
    if (mode === "done") return toggle.dataset.replay;
    return toggle.dataset.play;
  }

  function render() {
    scenes.forEach((scene, index) => {
      scene.classList.toggle("is-active", index === active);
      scene.setAttribute("aria-hidden", index === active ? "false" : "true");
    });
    progress.forEach((item, index) => {
      item.classList.toggle("is-active", index === active);
    });
    caption.textContent = labelFor(active);
    reel.classList.toggle("is-paused", mode !== "playing");
    reel.classList.toggle("is-done", mode === "done");
    if (stage) stage.classList.toggle("is-reduced", reducedMotion.matches);
    toggle.disabled = reducedMotion.matches;
    icon.textContent = mode === "playing" ? "Ⅱ" : "▶";
    toggle.setAttribute("aria-label", controlLabel());
  }

  function stop() {
    if (timer) window.clearTimeout(timer);
    timer = null;
  }

  function schedule() {
    stop();
    if (mode !== "playing" || reducedMotion.matches) return;
    timer = window.setTimeout(tick, dwellMs);
  }

  function tick() {
    timer = null;
    if (mode !== "playing") return;
    if (active >= last) {
      mode = "done";
      render();
      return;
    }
    active += 1;
    render();
    schedule();
  }

  function replay() {
    active = 0;
    mode = "playing";
    render();
    schedule();
  }

  function setMotionPreference() {
    stop();
    if (reducedMotion.matches) {
      active = last;
      mode = "done";
    }
    render();
    schedule();
  }

  toggle.addEventListener("click", () => {
    if (reducedMotion.matches) return;
    if (mode === "done") {
      replay();
    } else if (mode === "playing") {
      mode = "paused";
      stop();
      render();
    } else {
      mode = "playing";
      render();
      schedule();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else schedule();
  });

  reducedMotion.addEventListener?.("change", setMotionPreference);
  render();
  schedule();
})();
