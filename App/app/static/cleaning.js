/* The server renders the full list; calendar updates replace that same view. */
(function () {
  "use strict";
  const root = document.querySelector("[data-calendar][data-cleaning='true']");
  if (!root) return;
  const labels = JSON.parse(document.querySelector("[data-cleaning-labels]").textContent);
  const list = document.querySelector("[data-cleaning-list]");
  const error = document.querySelector("[data-cleaning-error]");
  const readOnly = root.dataset.readonly === "true";
  let events = new Map(), dragged = null, saving = false;
  function showError(text) { error.textContent = text; error.hidden = !text; }
  function applySnapshot(data) {
    events = new Map(data.cleanings.map(item => [String(item.eventId), item]));
    // listHtml comes only from the escaped Jinja template at the authorized
    // same-origin endpoint. Codes are never put into browser storage.
    list.innerHTML = data.listHtml;
    showError("");
    for (const name of ["from", "to"]) {
      const input = document.querySelector("#cleaning-" + name);
      if (input) input.value = data[name];
    }
    if (!readOnly) {
      const url = new URL(location.href);
      url.searchParams.set("from", data.from); url.searchParams.set("to", data.to);
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  }
  root.addEventListener("calendar:loaded", event => applySnapshot(event.detail));
  if (root.cleaningSnapshot) applySnapshot(root.cleaningSnapshot);
  root.addEventListener("calendar:error", event => {
    showError(labels.load_error);
    if (readOnly && [401, 403, 404].includes(event.detail.status)) {
      list.replaceChildren(); root.querySelector("[data-cal-body]").replaceChildren();
      root.querySelectorAll("dialog").forEach(dialog => { if (dialog.open) dialog.close(); });
    }
  });
  root.addEventListener("cleaning:create", event => {
    if (readOnly) return;
    const params = new URLSearchParams({ date: event.detail.date });
    if (event.detail.property) params.set("property", event.detail.property);
    location.assign("/cleaning/new?" + params);
  });
  root.addEventListener("click", event => {
    const link = event.target.closest("[data-cal-open]");
    if (link && link.getAttribute("href").startsWith("#")) {
      const dialog = link.closest("dialog"); if (dialog.open) dialog.close();
    }
  });
  function refresh() {
    if (!saving && !document.hidden && !document.querySelector("dialog[open]") &&
        !list.contains(document.activeElement)) root.dispatchEvent(new Event("calendar:refresh"));
  }
  setInterval(refresh, 60000);
  document.addEventListener("visibilitychange", refresh);
  window.addEventListener("focus", refresh);
  if (readOnly) return;
  root.addEventListener("dragstart", event => {
    const block = event.target.closest("[data-cal-event][data-event-kind='cleaning']");
    if (!block || saving || root.querySelector("[data-cal-body]").getAttribute("aria-busy") === "true") {
      event.preventDefault(); return;
    }
    const id = block.dataset.calEvent.split(":")[1];
    dragged = events.get(id);
    if (!dragged) { event.preventDefault(); return; }
    event.dataTransfer.setData("text/plain", dragged.id);
    event.dataTransfer.effectAllowed = "move";
    block.classList.add("is-dragging");
  });
  root.addEventListener("dragover", event => {
    if (!dragged) return;
    const cell = event.target.closest("[data-date]");
    if (!cell) return;
    if (cell.dataset.property && Number(cell.dataset.property) !== dragged.propertyId) return;
    event.preventDefault(); event.dataTransfer.dropEffect = "move";
    root.querySelectorAll(".cleaning-drop-target").forEach(node => node.classList.remove("cleaning-drop-target"));
    cell.classList.add("cleaning-drop-target");
  });
  root.addEventListener("dragend", () => {
    dragged = null;
    root.querySelectorAll(".is-dragging,.cleaning-drop-target").forEach(node => node.classList.remove("is-dragging", "cleaning-drop-target"));
  });
  root.addEventListener("drop", async event => {
    const cell = event.target.closest("[data-date]"), item = dragged;
    if (!item || !cell || saving || (cell.dataset.property && Number(cell.dataset.property) !== item.propertyId)) return;
    event.preventDefault();
    dragged = null; saving = true;
    const data = new FormData();
    data.set("_csrf", root.querySelector("[name='_csrf']").value);
    data.set("apartment_id", String(item.propertyId)); data.set("scheduled_date", cell.dataset.date);
    data.set("revision", String(item.revision)); data.set("start_time", item.startTime || "");
    data.set("end_time", item.endTime || ""); data.set("notes", item.notes);
    try {
      const response = await fetch("/cleaning/events/" + item.eventId, {
        method: "POST", body: data, headers: { Accept: "application/json" }, cache: "no-store"
      });
      if (!response.ok || response.redirected) throw new Error("save");
      showError("");
    } catch (_) { showError(labels.changed); }
    finally {
      saving = false;
      root.dispatchEvent(new Event("calendar:refresh"));
    }
  });
})();
