/* UbyHost reservation calendar. Date arithmetic uses UTC date-only values. */
(function () {
  "use strict";
  const DAY = 86400000;
  function dateValue(value) { return new Date(value + "T00:00:00Z"); }
  function iso(value) { return value.toISOString().slice(0, 10); }
  function addDays(value, days) { return iso(new Date(dateValue(value).getTime() + days * DAY)); }
  function distance(start, end) { return Math.round((dateValue(end) - dateValue(start)) / DAY); }
  function monday(value) { return addDays(value, -((dateValue(value).getUTCDay() + 6) % 7)); }
  function monthStart(value) { return value.slice(0, 7) + "-01"; }
  function moveMonth(value, amount) {
    const day = dateValue(monthStart(value));
    day.setUTCMonth(day.getUTCMonth() + amount);
    return iso(day);
  }
  function monthRange(value) {
    const first = monthStart(value), last = moveMonth(first, 1);
    const start = monday(first);
    return [start, addDays(start, Math.ceil(distance(start, last) / 7) * 7)];
  }
  function overlap(event, start, end) { return event.start < end && event.end > start; }
  function autoView(mode, propertyCount) { return mode === "auto" ? (propertyCount >= 3 ? "gantt" : "calendar") : mode; }
  function lanes(events, start, end) {
    const ends = [], segments = [];
    events.filter(event => overlap(event, start, end)).slice().sort((a, b) =>
      a.start.localeCompare(b.start) || a.end.localeCompare(b.end) || a.id - b.id
    ).forEach(event => {
      const left = event.start < start ? start : event.start;
      const right = event.end > end ? end : event.end;
      let lane = ends.findIndex(last => last <= left);
      if (lane < 0) lane = ends.length;
      ends[lane] = right;
      segments.push({ event, lane, column: distance(start, left), length: distance(left, right) });
    });
    return { segments, count: ends.length };
  }
  // Pure date/layout functions above are also exercised independently in browser tests.
  const root = document.querySelector("[data-calendar]");
  if (!root) return;
  const $ = selector => root.querySelector(selector);
  const $$ = selector => Array.from(root.querySelectorAll(selector));
  const labels = JSON.parse($("[data-cal-labels]").textContent);
  const locale = root.dataset.lang === "cs" ? "cs-CZ" : "en-GB";
  const format = (key, values = {}) => Object.entries(values).reduce((text, [name, value]) =>
    text.replace("%(" + name + ")s", String(value)), labels[key] || key);
  const shortDate = value => new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" }).format(dateValue(value));
  const fullDate = value => new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(dateValue(value));
  const monthName = value => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(dateValue(value));
  const weekday = value => new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(dateValue(value));
  const body = $("[data-cal-body]"), message = $("[data-cal-message]");
  const createDialog = $("[data-cal-create]"), form = $("[data-cal-form]");
  const detailsDialog = $("[data-cal-details]"), dayDialog = $("[data-cal-day-dialog]");
  const settingsDialog = $("[data-cal-settings-dialog]");
  const preferencesKey = "ubyhost.calendar.display.v1";
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(preferencesKey) || "{}"); } catch (_) { /* Storage may be disabled. */ }
  if (!preferences || typeof preferences !== "object" || Array.isArray(preferences)) preferences = {};
  const properties = JSON.parse($("[data-cal-properties]").textContent);
  const query = new URLSearchParams(location.search);
  const queryMode = query.get("cal_view"), queryDate = query.get("cal_date");
  const validMode = value => ["auto", "calendar", "gantt"].includes(value);
  const validDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value || "") &&
    value >= "1900-01-01" && value <= "2100-12-31" &&
    Number.isFinite(dateValue(value).getTime()) && iso(dateValue(value)) === value;
  const state = {
    mode: validMode(queryMode) ? queryMode : (validMode(preferences.mode) ? preferences.mode : "auto"),
    scale: ["month", "week", "year"].includes(query.get("cal_scale")) ? query.get("cal_scale") : "month",
    date: validDate(queryDate) ? queryDate : root.dataset.today,
    property: properties.some(item => String(item.id) === query.get("cal_property")) ? query.get("cal_property") : "",
    properties, events: [], loading: false,
    display: { property: preferences.property !== false, label: preferences.label !== false, guests: preferences.guests !== false }
  };
  let requestNumber = 0, controller = null, selection = null, suppressClickUntil = 0;
  let keyboardAnchor = null, dayListDate = null, saving = false;
  const focusReturn = new WeakMap();
  let lastLoadedRange = null, refreshOnDetailsClose = false;
  detailsDialog.addEventListener("close", () => { if (refreshOnDetailsClose) location.reload(); });
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function savePreferences() {
    try { localStorage.setItem(preferencesKey, JSON.stringify({ mode: state.mode, ...state.display })); } catch (_) { /* Optional. */ }
  }
  function view() { return autoView(state.mode, state.property ? 1 : state.properties.length); }
  function range() {
    if (view() === "gantt") return [monthStart(state.date), moveMonth(state.date, 1)];
    if (state.scale === "week") { const start = monday(state.date); return [start, addDays(start, 7)]; }
    if (state.scale === "year") return [state.date.slice(0, 4) + "-01-01", String(Number(state.date.slice(0, 4)) + 1) + "-01-01"];
    return monthRange(state.date);
  }
  function rememberURL() {
    const params = new URLSearchParams(location.search);
    params.set("cal_view", state.mode); params.set("cal_date", state.date); params.set("cal_scale", state.scale);
    if (state.property) params.set("cal_property", state.property); else params.delete("cal_property");
    history.replaceState(null, "", location.pathname + "?" + params.toString() + location.hash);
  }
  function setMessage(text, retry = false) {
    message.replaceChildren();
    message.hidden = !text;
    if (text) message.append(el("span", "", text));
    if (retry) {
      const button = el("button", "btn", labels.retry);
      button.type = "button"; button.addEventListener("click", load); message.append(button);
    }
  }
  function fillProperties(select, all) {
    const chosen = all ? state.property : select.value;
    select.replaceChildren();
    if (all) { const option = el("option", "", labels.all_properties); option.value = ""; select.append(option); }
    state.properties.forEach(property => {
      const option = el("option", "", property.name); option.value = String(property.id); select.append(option);
    });
    if (Array.from(select.options).some(option => option.value === chosen)) select.value = chosen;
  }
  function syncControls() {
    const currentView = view(), [start, end] = range();
    $$("[data-cal-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.calView === currentView)));
    $$("[data-cal-scale]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.calScale === state.scale)));
    $("[data-cal-scales]").hidden = currentView === "gantt";
    $("[data-cal-month]").value = state.date.slice(0, 7);
    $("[data-cal-period]").textContent = currentView === "calendar" && state.scale === "year" ? state.date.slice(0, 4) :
      currentView === "calendar" && state.scale === "week" ? shortDate(start) + " – " + fullDate(addDays(end, -1)) : monthName(state.date);
    $("[data-cal-prev]").disabled = state.date <= "1900-01-01";
    $("[data-cal-next]").disabled = state.date >= "2100-12-01";
    $("[data-cal-auto]").checked = state.mode === "auto";
    $$("[data-cal-display]").forEach(input => { input.checked = state.display[input.dataset.calDisplay]; });
    fillProperties($("[data-cal-property]"), true);
    $$("[data-calendar-add]").forEach(link => { link.setAttribute("aria-haspopup", "dialog"); });
  }
  function labelFor(event) {
    const parts = [];
    if (state.display.label && event.label) parts.push(event.label);
    if (state.display.property) parts.push(event.property);
    if (state.display.guests && event.expected !== null) parts.push(String(event.expected));
    return parts.join(" · ") || event.label || event.property;
  }
  function statusFor(event) {
    if (event.preview) return labels.preview;
    if (event.tone === "overdue") return labels.status_failed && event.status === "failed" ?
      labels.overdue + " · " + labels.status_failed : labels.overdue;
    return labels["status_" + event.status] || labels.booked;
  }
  function eventLink(event) {
    const link = el("a", "cal-event is-" + event.tone);
    link.href = event.url; link.dataset.calEvent = String(event.id);
    link.setAttribute("aria-haspopup", "dialog");
    const status = statusFor(event);
    link.title = labelFor(event) + " · " + fullDate(event.start) + " – " + fullDate(event.end) + " · " + status +
      (event.conflict ? " · " + labels.conflict : "");
    link.setAttribute("aria-label", link.title);
    if (event.tone === "overdue" || event.tone === "action" || event.conflict) {
      const mark = el("span", "cal-event-mark", "!"); mark.setAttribute("aria-hidden", "true"); link.append(mark);
    }
    link.append(el("span", "", labelFor(event)));
    return link;
  }
  function markConflicts() {
    const byProperty = new Map();
    state.events.forEach(event => { event.conflict = false; const list = byProperty.get(event.propertyId) || []; list.push(event); byProperty.set(event.propertyId, list); });
    byProperty.forEach(events => {
      const active = [];
      events.slice().sort((a, b) => a.start.localeCompare(b.start)).forEach(event => {
        for (let i = active.length - 1; i >= 0; i--) if (active[i].end <= event.start) active.splice(i, 1);
        active.forEach(other => { other.conflict = true; event.conflict = true; });
        active.push(event);
      });
    });
  }
  function renderCalendar() {
    const [start, end] = range(), weekdays = el("div", "cal-weekdays");
    for (let day = 0; day < 7; day++) weekdays.append(el("span", "", weekday(addDays(start, day))));
    body.append(weekdays);
    const maximum = matchMedia("(max-width:760px)").matches ? 2 : 3;
    for (let week = start; week < end; week = addDays(week, 7)) {
      const until = addDays(week, 7), layout = lanes(state.events, week, until);
      const hiddenSegments = layout.segments.filter(segment => segment.lane >= maximum);
      const visible = layout.segments.filter(segment => segment.lane < maximum);
      const count = Math.max(1, Math.min(layout.count, maximum) + (hiddenSegments.length ? 1 : 0));
      const row = el("div", "cal-week"); row.style.setProperty("--lanes", String(count));
      const days = el("div", "cal-week-days");
      for (let index = 0; index < 7; index++) {
        const date = addDays(week, index), day = el("div", "cal-day");
        day.dataset.date = date;
        if (date.slice(0, 7) !== state.date.slice(0, 7) && state.scale !== "week") day.classList.add("is-outside");
        if (date === root.dataset.today) day.classList.add("is-today");
        const button = el("button", "cal-day-number", String(dateValue(date).getUTCDate()));
        button.type = "button"; button.dataset.calDay = date;
        button.setAttribute("aria-label", format("select_day", { date: fullDate(date) }));
        button.title = labels.keyboard;
        day.append(button); days.append(day);
      }
      const overlay = el("div", "cal-week-events");
      visible.forEach(segment => {
        const link = eventLink(segment.event);
        link.style.gridColumn = String(segment.column + 1) + " / span " + String(segment.length);
        link.style.gridRow = String(segment.lane + 1);
        if (segment.event.start < week) link.classList.add("continues-start");
        if (segment.event.end > until) link.classList.add("continues-end");
        overlay.append(link);
      });
      if (hiddenSegments.length) {
        for (let index = 0; index < 7; index++) {
          const day = addDays(week, index), hidden = hiddenSegments.filter(segment => overlap(segment.event, day, addDays(day, 1)));
          if (!hidden.length) continue;
          const button = el("button", "cal-more", format("more", { count: hidden.length }));
          button.type = "button"; button.dataset.calMore = day;
          button.style.gridColumn = String(index + 1); button.style.gridRow = String(Math.min(layout.count, maximum) + 1);
          overlay.append(button);
        }
      }
      row.append(days, overlay); body.append(row);
    }
  }
  function renderYear() {
    const grid = el("div", "cal-year");
    for (let month = 0; month < 12; month++) {
      const start = state.date.slice(0, 4) + "-" + String(month + 1).padStart(2, "0") + "-01", end = moveMonth(start, 1);
      const mini = el("div", "cal-mini"), title = el("button", "cal-mini-title", monthName(start));
      title.type = "button"; title.dataset.calMonthOpen = start;
      const days = el("div", "cal-mini-grid");
      for (let day = 0; day < 7; day++) days.append(el("span", "", weekday(addDays("2026-01-05", day))));
      for (let day = monday(start); day < start; day = addDays(day, 1)) days.append(el("span", "", ""));
      for (let day = start; day < end; day = addDays(day, 1)) {
        const button = el("button", "cal-mini-day", String(dateValue(day).getUTCDate()));
        button.type = "button"; button.dataset.calMonthOpen = day;
        button.setAttribute("aria-label", fullDate(day));
        const events = state.events.filter(event => overlap(event, day, addDays(day, 1)));
        if (events.length) button.classList.add("has-stays");
        if (events.some(event => event.tone === "overdue" || event.tone === "action")) button.classList.add("has-action");
        if (day === root.dataset.today) button.classList.add("is-today");
        days.append(button);
      }
      mini.append(title, days); grid.append(mini);
    }
    body.append(grid);
  }
  function renderGantt() {
    const start = monthStart(state.date), end = moveMonth(start, 1), number = distance(start, end);
    const scroll = el("div", "cal-gantt-scroll"), timeline = el("div", "cal-gantt-timeline");
    timeline.style.setProperty("--days", String(number));
    const heading = el("div", "cal-gantt-header");
    heading.append(el("span", "cal-gantt-name", labels.property));
    for (let index = 0; index < number; index++) {
      const day = addDays(start, index), cell = el("span", day === root.dataset.today ? "is-today" : "");
      cell.append(el("span", "", weekday(day)), el("br"), el("span", "", String(index + 1)));
      heading.append(cell);
    }
    timeline.append(heading);
    state.properties.filter(property => !state.property || String(property.id) === state.property).forEach(property => {
      const events = state.events.filter(event => event.propertyId === property.id);
      const layout = lanes(events, start, end), row = el("div", "cal-gantt-row");
      const name = el("div", "cal-gantt-name"); name.title = property.name; name.append(el("span", "", property.name));
      const track = el("div", "cal-gantt-track"); track.style.setProperty("--lanes", String(Math.max(1, layout.count)));
      const days = el("div", "cal-gantt-days"), overlay = el("div", "cal-gantt-events");
      for (let index = 0; index < number; index++) {
        const day = addDays(start, index), button = el("button", "cal-gantt-slot");
        button.type = "button"; button.dataset.date = day; button.dataset.property = String(property.id);
        button.dataset.calDay = day; button.setAttribute("aria-label", property.name + " · " + format("select_day", { date: fullDate(day) }));
        if ([0, 6].includes(dateValue(day).getUTCDay())) button.classList.add("is-weekend");
        if (day === root.dataset.today) button.classList.add("is-today");
        days.append(button);
      }
      layout.segments.forEach(segment => {
        const link = eventLink(segment.event);
        link.style.gridColumn = String(segment.column + 1) + " / span " + String(segment.length);
        link.style.gridRow = String(segment.lane + 1); overlay.append(link);
      });
      track.append(days, overlay); row.append(name, track); timeline.append(row);
    });
    scroll.append(timeline); body.append(scroll);
  }
  function render() {
    cancelSelection(); syncControls(); body.replaceChildren();
    if (!state.properties.length) { body.append(el("p", "cal-empty", labels.empty_properties)); return; }
    markConflicts();
    if (view() === "gantt") renderGantt(); else if (state.scale === "year") renderYear(); else renderCalendar();
    if (!state.events.length) body.append(el("p", "cal-empty", labels.empty));
  }
  async function load() {
    const number = ++requestNumber;
    if (controller) controller.abort();
    controller = new AbortController(); state.loading = true; body.setAttribute("aria-busy", "true");
    syncControls(); setMessage(labels.loading);
    const [from, to] = range(), params = new URLSearchParams({ from, to, lang: root.dataset.lang });
    if (state.property) params.set("property", state.property);
    try {
      const response = await fetch("/dashboard/calendar?" + params.toString(), { signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store" });
      if (number !== requestNumber) return;
      if (response.redirected || response.status === 401 || response.status === 403) throw new Error("session");
      if (!response.ok || !(response.headers.get("content-type") || "").includes("application/json")) throw new Error("load");
      const data = await response.json();
      if (number !== requestNumber) return;
      state.properties = data.properties; state.events = data.events; state.loading = false;
      const actualRange = range();
      if (actualRange[0] !== from || actualRange[1] !== to) { await load(); return; }
      lastLoadedRange = [from, to]; render(); body.setAttribute("aria-busy", "false"); setMessage(""); rememberURL();
    } catch (error) {
      if (error.name === "AbortError" || number !== requestNumber) return;
      state.loading = false; body.setAttribute("aria-busy", "false");
      setMessage(error.message === "session" ? labels.session_error : labels.load_error, true);
      // Keep the last successful view visible, but disable creating from stale data.
      lastLoadedRange = null;
    }
  }
  function show(dialog) {
    focusReturn.set(dialog, document.activeElement);
    if (!dialog.open) dialog.showModal();
  }
  function close(dialog) {
    if (dialog === createDialog && saving) return;
    dialog.close();
  }
  $$("dialog").forEach(dialog => {
    dialog.addEventListener("close", () => {
      const target = focusReturn.get(dialog); focusReturn.delete(dialog);
      if ($("dialog[open]")) return;
      if (target && target.isConnected && !target.closest("dialog:not([open])")) target.focus();
      else body.focus();
    });
    dialog.addEventListener("cancel", event => { if (dialog === createDialog && saving) event.preventDefault(); });
    dialog.addEventListener("click", event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close(dialog);
    });
  });
  function openDetails(event) {
    const container = $("[data-cal-detail-content]"); container.replaceChildren();
    container.append(el("h3", "cal-detail-property", event.property));
    if (event.label) container.append(el("p", "cal-detail-label", event.label));
    const facts = el("dl", "cal-detail-facts");
    const guestCount = event.expected === null ? String(event.complete) + " / " + labels.unknown : String(event.complete) + " / " + String(event.expected);
    [[labels.arrival, fullDate(event.start)], [labels.departure, fullDate(event.end)],
      [labels.guests, guestCount], [labels.report, event.status === "awaiting_guest" ? labels.details_needed : statusFor(event)],
      [labels.source, event.source === "manual" ? labels.manual : labels.imported]
    ].forEach(([name, value]) => facts.append(el("dt", "", name), el("dd", "", value)));
    container.append(facts);
    if (event.conflict) container.append(el("p", "cal-overlap", labels.conflict));
    $("[data-cal-open]").href = event.url;
    if (dayDialog.open) close(dayDialog);
    show(detailsDialog);
  }
  function openDay(day) {
    dayListDate = day; $("[data-cal-day-dialog] #cal-day-title").textContent = format("day_stays", { date: fullDate(day) });
    const list = $("[data-cal-day-list]"); list.replaceChildren(); list.className = "cal-day-list";
    const events = state.events.filter(event => overlap(event, day, addDays(day, 1)));
    events.forEach(event => list.append(eventLink(event)));
    if (!events.length) list.append(el("p", "cal-empty", labels.none_today));
    show(dayDialog);
  }
  function updateNights() {
    const start = form.elements.date_from.value, end = form.elements.date_to.value;
    form.elements.date_to.min = start && validDate(start) ? addDays(start, 1) : "1900-01-02";
    form.elements.date_to.setCustomValidity(start && end && end <= start ? labels.error_dates : "");
    const nights = start && end ? distance(start, end) : 0;
    const plural = new Intl.PluralRules(locale).select(nights);
    $("[data-cal-nights]").textContent = nights > 0 ? format(plural === "one" ? "nights_one" : plural === "few" ? "nights_few" : "nights_many", { count: nights }) : "";
    const canCheck = lastLoadedRange && start >= lastLoadedRange[0] && end <= lastLoadedRange[1];
    const conflicts = canCheck && state.events.some(event => String(event.propertyId) === form.elements.apartment_id.value && overlap(event, start, end));
    $("[data-cal-overlap]").hidden = !conflicts;
    form.elements.allow_overlap.checked = false;
    $$("[data-cal-error-for]").forEach(node => { node.textContent = ""; });
    $("[data-cal-save-error]").textContent = "";
  }
  function openCreate(start, end, property) {
    if (!state.properties.length) return;
    cancelSelection();
    form.reset(); fillProperties(form.elements.apartment_id, false);
    const selected = property || state.property;
    if (selected) form.elements.apartment_id.value = String(selected);
    form.elements.date_from.value = start; form.elements.date_to.value = end;
    $("[data-cal-save-error]").textContent = "";
    $$("[data-cal-error-for]").forEach(node => { node.textContent = ""; });
    updateNights();
    if (dayDialog.open) close(dayDialog);
    show(createDialog);
    form.elements.apartment_id.focus();
  }
  function paintSelection() {
    $$("[data-date]").forEach(node => {
      node.classList.toggle("is-selected", !!selection && node.dataset.date >= selection.start && node.dataset.date <= selection.end &&
        (!selection.property || node.dataset.property === selection.property));
    });
    if (selection) $("[data-cal-selection]").textContent = format("selection", { start: shortDate(selection.start), end: shortDate(addDays(selection.end, 1)) });
  }
  function cancelSelection() { selection = null; keyboardAnchor = null; $$("[data-date].is-selected").forEach(node => node.classList.remove("is-selected")); }
  root.addEventListener("pointerdown", event => {
    if (event.pointerType === "touch" || event.button !== 0 || state.loading || !lastLoadedRange ||
      event.target.closest("[data-cal-event], [data-cal-more], dialog")) return;
    const cell = event.target.closest("[data-date]");
    if (!cell || !body.contains(cell)) return;
    event.preventDefault();
    selection = { anchor: cell.dataset.date, start: cell.dataset.date, end: cell.dataset.date, property: cell.dataset.property || state.property };
    root.setPointerCapture(event.pointerId); paintSelection();
  });
  root.addEventListener("pointermove", event => {
    if (!selection) return;
    const target = document.elementFromPoint(event.clientX, event.clientY);
    const cell = target && target.closest("[data-date]");
    if (cell && body.contains(cell) && (!selection.property || !cell.dataset.property || cell.dataset.property === selection.property)) {
      const day = cell.dataset.date; selection.start = day < selection.anchor ? day : selection.anchor;
      selection.end = day > selection.anchor ? day : selection.anchor; paintSelection();
    }
    const scroll = $("[data-cal-body] .cal-gantt-scroll");
    if (scroll) {
      const box = scroll.getBoundingClientRect();
      if (event.clientX > box.right - 32) scroll.scrollLeft += 18;
      else if (event.clientX < box.left + 180) scroll.scrollLeft -= 18;
    }
  });
  root.addEventListener("pointerup", event => {
    if (!selection) return;
    const chosen = { ...selection }; cancelSelection(); suppressClickUntil = Date.now() + 400;
    if (root.hasPointerCapture(event.pointerId)) root.releasePointerCapture(event.pointerId);
    openCreate(chosen.start, addDays(chosen.end, 1), chosen.property);
  });
  root.addEventListener("pointercancel", cancelSelection);
  root.addEventListener("lostpointercapture", cancelSelection);
  root.addEventListener("keydown", event => {
    if (event.key === "Escape") { cancelSelection(); return; }
    const cell = event.target.closest("[data-cal-day]");
    if (!cell || state.loading || !lastLoadedRange) return;
    const day = cell.dataset.calDay, deltas = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (event.key in deltas) {
      event.preventDefault();
      const nextDay = addDays(day, deltas[event.key]);
      const candidates = $$("[data-cal-day]").filter(node => node.dataset.calDay === nextDay &&
        (node.dataset.property || "") === (cell.dataset.property || ""));
      if (!candidates.length) return;
      if (event.shiftKey) {
        keyboardAnchor = keyboardAnchor || day;
        selection = { anchor: keyboardAnchor, start: nextDay < keyboardAnchor ? nextDay : keyboardAnchor,
          end: nextDay > keyboardAnchor ? nextDay : keyboardAnchor, property: cell.dataset.property || state.property };
        paintSelection();
      } else cancelSelection();
      candidates[0].focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const start = selection ? selection.start : day, end = addDays(selection ? selection.end : day, 1);
      openCreate(start, end, cell.dataset.property || state.property);
    }
  });
  root.addEventListener("click", event => {
    const target = event.target;
    if (target.closest("[data-cal-close]")) { close(target.closest("dialog")); return; }
    const booking = target.closest("[data-cal-event]");
    if (booking && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
      event.preventDefault(); const found = state.events.find(item => String(item.id) === booking.dataset.calEvent);
      if (found) openDetails(found); return;
    }
    const day = target.closest("[data-cal-day]");
    if (day) {
      if (Date.now() < suppressClickUntil || state.loading || !lastLoadedRange) return;
      openCreate(day.dataset.calDay, addDays(day.dataset.calDay, 1), day.dataset.property || state.property); return;
    }
    const more = target.closest("[data-cal-more]");
    if (more) { openDay(more.dataset.calMore); return; }
    const month = target.closest("[data-cal-month-open]");
    if (month) { state.date = month.dataset.calMonthOpen; state.mode = "calendar"; state.scale = "month"; savePreferences(); load(); return; }
    const mode = target.closest("[data-cal-view]");
    if (mode) { state.mode = mode.dataset.calView; savePreferences(); load(); return; }
    const scale = target.closest("[data-cal-scale]");
    if (scale) { state.mode = "calendar"; state.scale = scale.dataset.calScale; savePreferences(); load(); return; }
    if (target.closest("[data-cal-settings]")) { show(settingsDialog); return; }
    if (target.closest("[data-cal-today]")) { state.date = root.dataset.today; load(); return; }
    const movement = target.closest("[data-cal-prev], [data-cal-next]");
    if (movement) {
      const sign = movement.hasAttribute("data-cal-prev") ? -1 : 1;
      const next = view() === "calendar" && state.scale === "week" ? addDays(state.date, sign * 7) :
        moveMonth(state.date, sign * (view() === "calendar" && state.scale === "year" ? 12 : 1));
      state.date = next < "1900-01-01" ? "1900-01-01" : next > "2100-12-01" ? "2100-12-01" : next;
      load(); return;
    }
    if (target.closest("[data-cal-day-add]") && dayListDate) openCreate(dayListDate, addDays(dayListDate, 1), state.property);
  });
  document.querySelectorAll("[data-calendar-add]").forEach(link => link.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || !state.properties.length) return;
    event.preventDefault(); openCreate(root.dataset.today, addDays(root.dataset.today, 1), state.property);
  }));
  $("[data-cal-property]").addEventListener("change", event => {
    state.property = event.target.value;
    if (state.mode === "auto") state.scale = "month";
    load();
  });
  $("[data-cal-month]").addEventListener("change", event => {
    const next = event.target.value + "-01"; if (validDate(next)) { state.date = next; load(); }
  });
  $("[data-cal-auto]").addEventListener("change", event => {
    state.mode = event.target.checked ? "auto" : view();
    if (state.mode === "auto") state.scale = "month";
    savePreferences(); load();
  });
  $$("[data-cal-display]").forEach(input => input.addEventListener("change", () => {
    state.display[input.dataset.calDisplay] = input.checked; savePreferences(); render();
  }));
  ["date_from", "date_to", "apartment_id"].forEach(name => form.elements[name].addEventListener("change", updateNights));
  form.addEventListener("submit", async event => {
    event.preventDefault(); if (saving || !form.reportValidity()) return;
    saving = true; const save = $("[data-cal-save]"); save.disabled = true; save.textContent = labels.saving;
    $("[data-cal-save-error]").textContent = "";
    const payload = new FormData(form);
    try {
      const response = await fetch(form.action, { method: "POST", body: payload,
        headers: { Accept: "application/json", "x-csrf-token": form.elements._csrf.value } });
      if (response.redirected || !(response.headers.get("content-type") || "").includes("application/json")) throw new Error("session");
      const data = await response.json();
      if (response.status === 409 && data.overlap) {
        $("[data-cal-overlap]").hidden = false;
        $("[data-cal-save-error]").textContent = data.error;
        form.elements.allow_overlap.focus(); return;
      }
      if (!response.ok) {
        if (data.errors) {
          Object.entries(data.errors).forEach(([field, text]) => {
            const target = $$("[data-cal-error-for]").find(node => node.dataset.calErrorFor === field);
            if (target) target.textContent = text;
          });
          const first = Object.keys(data.errors)[0]; if (form.elements[first]) form.elements[first].focus();
          return;
        }
        throw new Error("save");
      }
      saving = false; close(createDialog);
      // Show the newly created stay even if its dates lie outside the current view.
      if (!overlap({ start: form.elements.date_from.value, end: form.elements.date_to.value }, ...range())) state.date = form.elements.date_from.value;
      if (state.property && state.property !== form.elements.apartment_id.value) state.property = form.elements.apartment_id.value;
      await load();
      setMessage(labels.created);
      const saved = state.events.find(item => item.id === data.id);
      if (saved) { refreshOnDetailsClose = true; openDetails(saved); } else location.assign(data.url);
    } catch (error) {
      $("[data-cal-save-error]").textContent = error.message === "session" ? labels.session_error : labels.save_error;
    } finally {
      saving = false; save.disabled = false; save.textContent = labels.save;
    }
  });
  window.addEventListener("resize", () => { if (!state.loading && lastLoadedRange) render(); });
  window.addEventListener("popstate", () => {
    const params = new URLSearchParams(location.search);
    if (validMode(params.get("cal_view"))) state.mode = params.get("cal_view");
    if (validDate(params.get("cal_date"))) state.date = params.get("cal_date");
    state.property = state.properties.some(item => String(item.id) === params.get("cal_property")) ? params.get("cal_property") : "";
    state.scale = ["month", "week", "year"].includes(params.get("cal_scale")) ? params.get("cal_scale") : "month";
    load();
  });
  $$(".cal-enhanced").forEach(node => { node.hidden = false; });
  $("[data-cal-fallback]").hidden = true;
  fillProperties(form.elements.apartment_id, false);
  load();
})();
