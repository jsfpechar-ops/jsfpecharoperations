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
  function dayPoint(value) { return distance("1970-01-01", value); }
  function eventPoint(event, edge) {
    const actual = edge === "start" ? event.start : event.end;
    const value = event[edge === "start" ? "displayStart" : "displayEnd"];
    if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return dayPoint(actual);
    const day = value.slice(0, 10), time = value.slice(11);
    const [hour, minute] = time.split(":").map(Number);
    return dayPoint(day) + hour / 24 + minute / 1440;
  }
  function overlap(event, start, end) {
    return dayPoint(event.start) < dayPoint(end) && dayPoint(event.end) > dayPoint(start);
  }
  function displayOverlap(event, start, end) {
    return eventPoint(event, "start") < dayPoint(end) && eventPoint(event, "end") > dayPoint(start);
  }
  function layoutPoint(event, edge) {
    if (event.kind !== "cleaning") return eventPoint(event, edge);
    return dayPoint(event.start) + (edge === "end" ? 1 : 0);
  }
  function autoView(mode, propertyCount) { return mode === "auto" ? (propertyCount >= 3 ? "gantt" : "calendar") : mode; }
  function lanes(events, start, end) {
    const leftEdge = dayPoint(start), rightEdge = dayPoint(end), ends = [], segments = [];
    let cleaningLane = null;
    events.filter(event => layoutPoint(event, "start") < rightEdge && layoutPoint(event, "end") > leftEdge)
      .slice().sort((a, b) => Number(a.kind === "cleaning") - Number(b.kind === "cleaning") ||
        layoutPoint(a, "start") - layoutPoint(b, "start") ||
        layoutPoint(a, "end") - layoutPoint(b, "end") ||
        (Number.isFinite(a.id) && Number.isFinite(b.id) ? a.id - b.id : String(a.id).localeCompare(String(b.id))))
      .forEach(event => {
        const left = Math.max(layoutPoint(event, "start"), leftEdge);
        const right = Math.min(layoutPoint(event, "end"), rightEdge);
        const column = Math.floor(left - leftEdge);
        const lastColumn = Math.ceil(right - leftEdge);
        const length = Math.max(1, lastColumn - column);
        if (event.kind === "cleaning" && cleaningLane === null) cleaningLane = ends.length;
        let lane = ends.findIndex((last, index) => last <= left &&
          (event.kind !== "cleaning" || index >= cleaningLane));
        if (lane < 0) lane = ends.length;
        ends[lane] = right;
        const lastDayStart = leftEdge + column + length - 1;
        segments.push({ event, lane, column, length,
          startFraction: left - (leftEdge + column),
          endFraction: Math.max(0, Math.min(1, right - lastDayStart)) });
      });
    return { segments, count: ends.length };
  }
  function placeEvent(link, segment) {
    link.style.gridColumn = String(segment.column + 1) + " / span " + String(segment.length);
    link.style.gridRow = String(segment.lane + 1);
    const width = Math.max(1, segment.length);
    link.style.marginLeft = "calc(" + (segment.startFraction * 100 / width) + "% + 1px)";
    link.style.marginRight = "calc(" + ((1 - segment.endFraction) * 100 / width) + "% + 1px)";
  }
  // Pure date/layout functions above are also exercised independently in browser tests.
  const root = document.querySelector("[data-calendar]");
  if (!root) return;
  const cleaningMode = root.dataset.cleaning === "true";
  const readOnly = root.dataset.readonly === "true";
  const cleaningLabels = JSON.parse(document.querySelector("[data-cleaning-labels]")?.textContent || "{}");
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
  const cleaningPreferencesKey = "ubyhost.cleaning.display.v1";
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(cleaningMode ? cleaningPreferencesKey : preferencesKey) || "{}"); } catch (_) { /* Storage may be disabled. */ }
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
    date: validDate(queryDate) ? queryDate : (root.dataset.calendarDate || root.dataset.today),
    property: properties.some(item => String(item.id) === query.get("cal_property")) ? query.get("cal_property") : "",
    properties, events: [], loading: false,
    display: { property: preferences.property !== false, label: preferences.label !== false, guests: preferences.guests !== false }
  };
  let requestNumber = 0, controller = null, selection = null, suppressClickUntil = 0;
  let keyboardAnchor = null, dayListDate = null, saving = false, createKind = cleaningMode ? "cleaning" : "stay";
  const focusReturn = new WeakMap();
  let lastLoadedRange = null;
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function savePreferences() {
    try {
      const displaySettings = JSON.stringify({ mode: state.mode, ...state.display });
      if (cleaningMode) localStorage.setItem(cleaningPreferencesKey, displaySettings);
      else localStorage.setItem(preferencesKey, displaySettings);
    } catch (_) { /* Optional. */ }
  }
  function view() { return autoView(state.mode, state.property ? 1 : state.properties.length); }
  function range() {
    if (view() === "gantt" && cleaningMode) return [state.date,
      state.date === root.dataset.rangeFrom && root.dataset.rangeTo ? root.dataset.rangeTo : addDays(state.date, 30)];
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
  function setMessage(text, retry = false, href = "", linkLabel = labels.open) {
    message.replaceChildren();
    message.hidden = !text;
    if (text) message.append(el("span", "", text));
    if (href) {
      const link = el("a", "", linkLabel);
      link.href = href; message.append(link);
    }
    if (retry) {
      const button = el("button", "btn", labels.retry);
      button.type = "button"; button.addEventListener("click", typeof retry === "function" ? retry : load); message.append(button);
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
  // Native selects retain platform keyboard navigation and localized month names.
  for (let month = 1; month <= 12; month++) {
    const value = String(month).padStart(2, "0");
    const option = el("option", "", new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(dateValue("2026-" + value + "-01")));
    option.value = value; $("[data-cal-month]").append(option);
  }
  for (let year = 1900; year <= 2100; year++) {
    const option = el("option", "", String(year)); option.value = String(year); $("[data-cal-year]").append(option);
  }
  function syncControls() {
    const currentView = view(), [start, end] = range();
    $$("[data-cal-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.calView === currentView)));
    $$("[data-cal-scale]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.calScale === state.scale)));
    $("[data-cal-scales]").hidden = currentView === "gantt";
    $("[data-cal-month]").value = state.date.slice(5, 7);
    $("[data-cal-month]").hidden = currentView === "calendar" && state.scale === "year";
    $("[data-cal-year]").value = state.date.slice(0, 4);
    $("[data-cal-period]").textContent = currentView === "calendar" && state.scale === "year" ? state.date.slice(0, 4) :
      currentView === "calendar" && state.scale === "week" ? shortDate(start) + " – " + fullDate(addDays(end, -1)) : monthName(state.date);
    $("[data-cal-prev]").disabled = state.date <= "1900-01-01";
    $("[data-cal-next]").disabled = state.date >= "2100-12-01";
    $("[data-cal-auto]").checked = state.mode === "auto";
    $$("[data-cal-display]").forEach(input => { input.checked = state.display[input.dataset.calDisplay]; });
    if (cleaningMode && currentView === "gantt") $("[data-cal-period]").textContent = shortDate(start) + " – " + fullDate(addDays(end, -1));
    fillProperties($("[data-cal-property]"), true);
    $$("[data-calendar-add]").forEach(link => { link.setAttribute("aria-haspopup", "dialog"); });
  }
  function labelFor(event) {
    if (cleaningMode) return (event.kind === "cleaning" ? (cleaningLabels.title || labels.cleaning) : cleaningLabels.booking) + " · " + event.property;
    const parts = [];
    const label = (event.label || "").trim();
    // Imported placeholders are booking state, not a useful stay title.
    const generic = /^(?:[!⚠]\s*)?(?:reserved|booked|reservation|rezervováno|rezervace)$/iu.test(label);
    if (state.display.label && label && !generic) parts.push(label);
    if (state.display.property) parts.push(event.property);
    if (state.display.guests && event.expected !== null) parts.push(String(event.expected));
    return parts.join(" · ") || shortDate(event.start) + " – " + shortDate(event.end);
  }
  function statusFor(event) {
    if (event.preview) return labels.preview;
    if (event.tone === "overdue") return labels.status_failed && event.status === "failed" ?
      labels.overdue + " · " + labels.status_failed : labels.overdue;
    return labels["status_" + event.status] || labels.booked;
  }
  function propertyColor(id) { return ["teal", "blue", "purple"][Math.abs(Number(id)) % 3]; }
  function appendCleaningIcon(node, className) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("class", className || "cal-cleaning-icon");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M15 3l6 6M13 5l6 6M12 10l4 4-8 8H3v-5zM5 17v4M8 15v5M11 13v4");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.append(path);
    node.append(svg);
  }
  function eventLink(event) {
    const isCleaning = event.kind === "cleaning";
    const link = el("a", "cal-event is-" + event.tone + (isCleaning ? " is-cleaning-marker" : ""));
    link.dataset.eventKind = event.kind || "booking";
    if (cleaningMode) link.draggable = isCleaning && !readOnly;
    link.href = event.url; link.dataset.calEvent = String(event.id);
    link.dataset.calColor = propertyColor(event.propertyId);
    link.setAttribute("aria-haspopup", "dialog");
    const status = cleaningMode ? (isCleaning ? cleaningLabels.title : cleaningLabels.booking) : statusFor(event);
    link.title = labelFor(event) + " · " + fullDate(event.start) + " – " + fullDate(event.end) + " · " + status +
      (event.conflict ? " · " + labels.conflict : "");
    if (isCleaning) link.title = (cleaningLabels.title || labels.cleaning) + " · " + event.property + " · " + fullDate(event.start) +
      (cleaningMode && event.startTime ? " · " + event.startTime + "–" + event.endTime : "") +
      (cleaningMode && event.timingUnavailable ? " · " + cleaningLabels.timing_unavailable : "") +
      (cleaningMode && event.conflict ? " · " + cleaningLabels.conflict : "");
    link.setAttribute("aria-label", link.title);
    if (isCleaning) {
      appendCleaningIcon(link);
      link.append(el("span", "cal-cleaning-label", cleaningLabels.title || labels.cleaning));
      link.append(el("span", "cal-cleaning-property", event.property || ""));
      link.append(el("span", "cal-cleaning-count", "1"));
    } else {
      link.append(el("span", "", labelFor(event)));
    }
    return link;
  }
  function markConflicts() {
    const byProperty = new Map();
    state.events.filter(event => event.kind !== "cleaning").forEach(event => { event.conflict = false; const list = byProperty.get(event.propertyId) || []; list.push(event); byProperty.set(event.propertyId, list); });
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
    const mobile = matchMedia("(max-width:760px)").matches;
    const bookingBudgetDefault = cleaningMode ? 1 : (mobile ? 1 : 2);
    for (let week = start; week < end; week = addDays(week, 7)) {
      const until = addDays(week, 7);
      const bookings = lanes(state.events.filter(event => event.kind !== "cleaning"), week, until);
      const cleanings = lanes(state.events.filter(event => event.kind === "cleaning"), week, until);
      const bookingBudget = cleanings.count ? 1 : bookingBudgetDefault;
      const visibleBookings = bookings.segments.filter(segment => segment.lane < bookingBudget);
      const hiddenBookings = bookings.segments.filter(segment => segment.lane >= bookingBudget);
      const visibleCleanings = cleanings.segments.filter(segment => segment.lane === 0);
      const hiddenCleanings = cleanings.segments.filter(segment => segment.lane > 0);
      const cleaningRows = visibleCleanings.length ? 1 : 0;
      const days = el("div", "cal-week-days");
      for (let index = 0; index < 7; index++) {
        const date = addDays(week, index), day = el("div", "cal-day");
        day.dataset.date = date;
        if (date.slice(0, 7) !== state.date.slice(0, 7) && state.scale !== "week") day.classList.add("is-outside");
        if (date === root.dataset.today) day.classList.add("is-today");
        const button = el("button", "cal-day-number", String(dateValue(date).getUTCDate()));
        button.type = "button"; button.dataset.calDay = date;
        button.setAttribute("aria-label", format("select_day", { date: fullDate(date) }));
        button.title = labels.keyboard; day.append(button); days.append(day);
      }
      const overlay = el("div", "cal-week-events");
      if (cleaningMode || cleanings.count) {
        visibleCleanings.forEach(segment => {
          const link = eventLink(segment.event);
          if (layoutPoint(segment.event, "start") < dayPoint(week)) link.classList.add("continues-start");
          if (layoutPoint(segment.event, "end") > dayPoint(until)) link.classList.add("continues-end");
          segment.lane = 0;
          placeEvent(link, segment); overlay.append(link);
        });
        visibleBookings.forEach(segment => {
          const link = eventLink(segment.event);
          if (eventPoint(segment.event, "start") < dayPoint(week)) link.classList.add("continues-start");
          if (eventPoint(segment.event, "end") > dayPoint(until)) link.classList.add("continues-end");
          segment.lane += cleaningRows;
          placeEvent(link, segment); overlay.append(link);
        });
      } else {
        visibleBookings.forEach(segment => {
          const link = eventLink(segment.event);
          if (eventPoint(segment.event, "start") < dayPoint(week)) link.classList.add("continues-start");
          if (eventPoint(segment.event, "end") > dayPoint(until)) link.classList.add("continues-end");
          placeEvent(link, segment); overlay.append(link);
        });
      }
      let summaryCount = 0;
      for (let index = 0; index < 7; index++) {
        const day = addDays(week, index), dayEnd = addDays(day, 1);
        const moreBookings = hiddenBookings.filter(segment => displayOverlap(segment.event, day, dayEnd)).length;
        const moreCleanings = hiddenCleanings.filter(segment => displayOverlap(segment.event, day, dayEnd)).length;
        if (!moreBookings && !moreCleanings) continue;
        const parts = [];
        if (moreCleanings) parts.push(String(moreCleanings) + " " + (cleaningLabels.overflow_cleanings || labels.more_cleanings));
        if (moreBookings) parts.push(cleaningMode ? String(moreBookings) + " " + cleaningLabels.overflow_bookings : format("more", { count: moreBookings }));
        const button = el("button", "cal-more cal-day-summary" + (moreCleanings ? " has-cleaning-overflow" : ""), parts.join(" · "));
        button.type = "button"; button.dataset.calMore = day;
        button.setAttribute("aria-label", fullDate(day) + " · " + parts.join(" · "));
        button.title = button.getAttribute("aria-label");
        if (moreCleanings) {
          button.textContent = "";
          appendCleaningIcon(button, "cal-cleaning-icon cal-cleaning-overflow-icon");
          button.append(el("span", "cal-cleaning-overflow-count", "+" + String(moreCleanings)));
          button.append(el("span", "cal-cleaning-overflow-label", cleaningLabels.overflow_cleanings || labels.more_cleanings));
          button.append(el("span", "cal-summary-sr-only", parts.join(" · ")));
        }
        button.style.gridColumn = String(index + 1);
        const lastEventRow = Math.max(cleaningRows,
          visibleBookings.reduce((max, segment) => Math.max(max, segment.lane + 1), 0));
        const summaryRow = lastEventRow + 1;
        button.style.gridRow = String(summaryRow);
        overlay.append(button); summaryCount++;
      }
      const bookingRowCount = visibleBookings.reduce(
        (max, segment) => Math.max(max, segment.lane + 1 - cleaningRows), 0);
      const lastEventRow = Math.max(cleaningRows,
        visibleBookings.reduce((max, segment) => Math.max(max, segment.lane + 1), 0));
      const lanesShown = Math.max(1, lastEventRow + (summaryCount ? 1 : 0));
      const desktopRows = [
        ...Array.from({ length: cleaningRows }, () => "28px"),
        ...Array.from({ length: bookingRowCount }, () => "22px"),
        ...(summaryCount ? ["18px"] : [])
      ];
      const mobileRows = [
        ...Array.from({ length: cleaningRows }, () => "46px"),
        ...Array.from({ length: bookingRowCount }, () => "46px"),
        ...(summaryCount ? ["44px"] : [])
      ];
      if (desktopRows.length) {
        overlay.style.setProperty("--desktop-event-rows", desktopRows.join(" "));
        overlay.style.setProperty("--mobile-event-rows", mobileRows.join(" "));
      }
      const row = el("div", "cal-week"); row.style.setProperty("--lanes", String(lanesShown));
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
        const events = state.events.filter(event => displayOverlap(event, day, addDays(day, 1)));
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
    const [start, end] = cleaningMode ? range() : [monthStart(state.date), moveMonth(state.date, 1)];
    const number = distance(start, end);
    const scroll = el("div", "cal-gantt-scroll"), timeline = el("div", "cal-gantt-timeline");
    timeline.style.setProperty("--days", String(number));
    const heading = el("div", "cal-gantt-header");
    heading.append(el("span", "cal-gantt-name", labels.property));
    for (let index = 0; index < number; index++) {
      const day = addDays(start, index), cell = el("span", day === root.dataset.today ? "is-today" : "");
      cell.append(el("span", "", weekday(day)), el("br"), el("span", "", String(cleaningMode ? dateValue(day).getUTCDate() : index + 1)));
      heading.append(cell);
    }
    timeline.append(heading);
    state.properties.filter(property => !state.property || String(property.id) === state.property).forEach(property => {
      const events = state.events.filter(event => event.propertyId === property.id);
      const layout = lanes(events, start, end);
      const row = el("div", "cal-gantt-row");
      const name = el("div", "cal-gantt-name"); name.title = property.name;
      name.dataset.calColor = propertyColor(property.id); name.append(el("span", "", property.name));
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
        if (segment.event.kind === "cleaning") {
          link.classList.add("is-gantt-cleaning");
          if (number > 18) link.classList.add("is-narrow-cleaning");
        }
        if (eventPoint(segment.event, "start") < dayPoint(start)) link.classList.add("continues-start");
        if (eventPoint(segment.event, "end") > dayPoint(end)) link.classList.add("continues-end");
        placeEvent(link, segment); overlay.append(link);
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
      const response = await fetch((root.dataset.source || "/dashboard/calendar") + "?" + params.toString(), { signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store" });
      if (number !== requestNumber) return;
      if (response.redirected || response.status === 401 || response.status === 403) throw new Error("session");
      if (!response.ok || !(response.headers.get("content-type") || "").includes("application/json")) {
        const error = new Error("load"); error.status = response.status; throw error;
      }
      const data = await response.json();
      if (number !== requestNumber) return;
      state.properties = data.properties; state.events = data.events; state.loading = false;
      const actualRange = range();
      if (actualRange[0] !== from || actualRange[1] !== to) { await load(); return; }
      lastLoadedRange = [from, to]; render(); body.setAttribute("aria-busy", "false"); setMessage("");
      if (cleaningMode) {
        root.cleaningSnapshot = data; // In-memory only; supports late-loading list consumers.
        root.dispatchEvent(new CustomEvent("calendar:loaded", { detail: data }));
      }
      rememberURL();
    } catch (error) {
      if (error.name === "AbortError" || number !== requestNumber) return;
      console.error("Calendar load failed:", error.name, error.message);
      state.loading = false; body.setAttribute("aria-busy", "false");
      setMessage(error.message === "session" ? labels.session_error : labels.load_error, true);
      // Keep the last successful view visible, but disable creating from stale data.
      lastLoadedRange = null;
      if (cleaningMode) root.dispatchEvent(new CustomEvent("calendar:error", { detail: { status: error.status || 0 } }));
    }
  }
  function show(dialog) {
    focusReturn.set(dialog, document.activeElement);
    if (!dialog.open) dialog.showModal();
  }
  function close(dialog) {
    if (dialog === createDialog && saving) return;
    dialog.close();
    if (dialog === createDialog) { createAnchor = null; createAnchorDate = ""; }
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
    if (event.kind === "cleaning" && !cleaningMode) {
      container.append(el("h3", "cal-detail-property", event.property), el("p", "", fullDate(event.start)));
      if (event.checkout) container.append(el("p", "", labels.checkout + ": " + fullDate(event.checkout) +
        " · " + (event.checkoutTime || labels.time_missing)));
      if (event.nextArrival) container.append(el("p", "", labels.next_arrival + ": " + fullDate(event.nextArrival) +
        " · " + (event.checkinTime || labels.time_missing)));
      if (event.timingUnavailable) container.append(el("p", "cleaning-warning", labels.cleaning_timing_unavailable));
      $("[data-cal-open]").href = event.url; $("[data-cal-open]").textContent = labels.view_cleaning;
      $("[data-cal-open]").hidden = false;
      if (dayDialog.open) close(dayDialog);
      show(detailsDialog); return;
    }
    if (cleaningMode) {
      container.append(el("h3", "cal-detail-property", event.property), el("p", "", fullDate(event.start)));
      if (event.kind === "cleaning") {
        if (event.startTime) container.append(el("p", "", event.startTime + "–" + event.endTime));
        const turnover = el("dl", "cal-detail-facts");
        if (event.checkout) turnover.append(el("dt", "", cleaningLabels.checkout),
          el("dd", "", fullDate(event.checkout) + " · " + (event.checkoutTime || cleaningLabels.time_missing)));
        turnover.append(el("dt", "", cleaningLabels.arrival), el("dd", "",
          event.nextArrival ? fullDate(event.nextArrival) + " · " + (event.checkinTime || cleaningLabels.time_missing) : cleaningLabels.no_arrival));
        container.append(turnover);
        if (event.code) {
          const access = el("div", "cleaning-access");
          access.append(el("span", "", cleaningLabels.code), el("strong", "cleaning-pin",
            event.code + (event.codeSource === "ttlock" ? "#" : "")));
          container.append(access);
        }
        if (event.timingUnavailable) container.append(el("p", "cleaning-warning", cleaningLabels.timing_unavailable));
        if (event.conflict) container.append(el("p", "cleaning-warning", cleaningLabels.conflict));
        [event.notes, event.instructions].filter(Boolean).forEach(text => container.append(el("p", "cleaning-text", text)));
      } else container.append(el("p", "", cleaningLabels.booking + " · " + fullDate(event.end)));
      $("[data-cal-open]").href = event.url; $("[data-cal-open]").textContent = cleaningLabels.skip;
      $("[data-cal-open]").hidden = event.kind !== "cleaning";
      if (dayDialog.open) close(dayDialog);
      show(detailsDialog); return;
    }
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
    $("[data-cal-open]").textContent = labels.open;
    $("[data-cal-open]").hidden = false;
    if (dayDialog.open) close(dayDialog);
    show(detailsDialog);
  }
  function openDay(day) {
    dayListDate = day; $("[data-cal-day-dialog] #cal-day-title").textContent = cleaningMode ? fullDate(day) : format("day_stays", { date: fullDate(day) });
    const list = $("[data-cal-day-list]"); list.replaceChildren(); list.className = "cal-day-list";
    const events = state.events.filter(event => displayOverlap(event, day, addDays(day, 1)));
    events.forEach(event => list.append(eventLink(event)));
    if (!events.length) list.append(el("p", "cal-empty", labels.none_today));
    show(dayDialog);
  }
  function updateNights() {
    if (createKind !== "stay") return;
    const start = form.elements.date_from.value, end = form.elements.date_to.value;
    form.elements.date_to.min = start && validDate(start) ? addDays(start, 1) : "1900-01-02";
    form.elements.date_to.setCustomValidity(start && end && end <= start ? labels.error_dates : "");
    const nights = start && end ? distance(start, end) : 0;
    const plural = new Intl.PluralRules(locale).select(nights);
    $("[data-cal-nights]").textContent = nights > 0 ? format(plural === "one" ? "nights_one" : plural === "few" ? "nights_few" : "nights_many", { count: nights }) : "";
    const canCheck = lastLoadedRange && start >= lastLoadedRange[0] && end <= lastLoadedRange[1];
    const conflicts = canCheck && state.events.some(event => event.kind !== "cleaning" && String(event.propertyId) === form.elements.apartment_id.value && overlap(event, start, end));
    $("[data-cal-overlap]").hidden = !conflicts;
    form.elements.allow_overlap.checked = false;
    $$("[data-cal-error-for]").forEach(node => { node.textContent = ""; });
    $("[data-cal-save-error]").textContent = "";
  }
  function setCreateKind(kind) {
    if (saving || readOnly) return;
    createKind = kind === "cleaning" ? "cleaning" : "stay";
    const cleaningFields = $("[data-cal-cleaning-fields]"), stayFields = $("[data-cal-stay-fields]");
    cleaningFields.hidden = createKind !== "cleaning"; stayFields.hidden = createKind !== "stay";
    cleaningFields.querySelectorAll("input,select,textarea").forEach(input => { input.disabled = createKind !== "cleaning"; });
    stayFields.querySelectorAll("input,select,textarea").forEach(input => { input.disabled = createKind !== "stay"; });
    form.action = createKind === "cleaning" ? "/cleaning/events" : "/reservations";
    $("[data-cal-create-title]").textContent = createKind === "cleaning" ? labels.add_cleaning : labels.add_stay;
    $("[data-cal-save]").textContent = createKind === "cleaning" ? labels.create_cleaning : labels.create_stay;
    $$("[data-cal-type-choice]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.calTypeChoice === createKind));
    });
    if (createKind === "stay") updateNights();
    if (createDialog.open) requestAnimationFrame(() => placeCreate(createAnchor));
  }
  let createAnchor = null, createAnchorDate = "";
  function placeCreate(anchor) {
    if (!createDialog.open) return;
    if (matchMedia("(max-width:760px)").matches) {
      createDialog.style.removeProperty("left");
      createDialog.style.removeProperty("top");
      return;
    }
    const liveAnchor = anchor && anchor.isConnected ? anchor :
      Array.from(root.querySelectorAll("[data-date]")).find(node => node.dataset.date === createAnchorDate);
    const box = createDialog.getBoundingClientRect();
    const target = liveAnchor && liveAnchor.getBoundingClientRect ? liveAnchor.getBoundingClientRect() : null;
    let left = target ? target.left : (innerWidth - box.width) / 2;
    let top = target ? target.bottom + 8 : (innerHeight - box.height) / 2;
    left = Math.max(12, Math.min(left, innerWidth - box.width - 12));
    if (top + box.height > innerHeight - 12 && target) top = target.top - box.height - 8;
    top = Math.max(12, Math.min(top, innerHeight - box.height - 12));
    createDialog.style.left = Math.round(left) + "px";
    createDialog.style.top = Math.round(top) + "px";
  }
  function openCreate(start, end, property, kind = (cleaningMode ? "cleaning" : "stay"), anchor = null) {
    if (readOnly) { openDay(start); return; }
    if (!state.properties.length) return;
    cancelSelection();
    form.reset(); fillProperties(form.elements.apartment_id, false);
    const selected = property || state.property;
    if (selected) form.elements.apartment_id.value = String(selected);
    form.elements.date_from.value = start; form.elements.date_to.value = end;
    form.elements.scheduled_date.value = start;
    $("[data-cal-save-error]").textContent = "";
    $$("[data-cal-error-for]").forEach(node => { node.textContent = ""; });
    setCreateKind(kind);
    if (dayDialog.open) close(dayDialog);
    createAnchor = anchor; createAnchorDate = start;
    show(createDialog);
    requestAnimationFrame(() => placeCreate(createAnchor));
    (createKind === "cleaning" ? form.elements.scheduled_date : form.elements.apartment_id).focus();
  }
  function paintSelection() {
    $$("[data-date]").forEach(node => {
      node.classList.toggle("is-selected", !!selection && node.dataset.date >= selection.start && node.dataset.date <= selection.end &&
        (!selection.property || node.dataset.property === selection.property));
    });
    if (selection) $("[data-cal-selection]").textContent = format("selection", { start: shortDate(selection.start), end: shortDate(addDays(selection.end, 1)) });
  }
  function cancelSelection() { selection = null; keyboardAnchor = null; $$("[data-date].is-selected").forEach(node => node.classList.remove("is-selected")); $("[data-cal-selection]").textContent = ""; }
  root.addEventListener("pointerdown", event => {
    if (readOnly || event.pointerType === "touch" || event.button !== 0 || state.loading || !lastLoadedRange ||
      event.target.closest("[data-cal-event], [data-cal-more], dialog")) return;
    const cell = event.target.closest("[data-date]");
    if (!cell || !body.contains(cell)) return;
    event.preventDefault();
    const focusable = cell.matches("[data-cal-day]") ? cell : cell.querySelector("[data-cal-day]");
    if (focusable) focusable.focus({ preventScroll: true });
    selection = { anchor: cell.dataset.date, start: cell.dataset.date, end: cell.dataset.date, property: cell.dataset.property || state.property, lastX: event.clientX, pointerId: event.pointerId };
    root.setPointerCapture(event.pointerId); paintSelection();
  });
  root.addEventListener("pointermove", event => {
    if (!selection || selection.pointerId !== event.pointerId) return;
    const movementX = event.clientX - selection.lastX; selection.lastX = event.clientX;
    const target = document.elementFromPoint(event.clientX, event.clientY);
    const cell = target && target.closest("[data-date]");
    if (cell && body.contains(cell) && (!selection.property || !cell.dataset.property || cell.dataset.property === selection.property)) {
      const day = cell.dataset.date; selection.start = day < selection.anchor ? day : selection.anchor;
      selection.end = day > selection.anchor ? day : selection.anchor; paintSelection();
    }
    const scroll = $("[data-cal-body] .cal-gantt-scroll");
    if (scroll) {
      const box = scroll.getBoundingClientRect();
      if (movementX > 0 && event.clientX > box.right - 32) scroll.scrollLeft += 18;
      else if (movementX < 0 && event.clientX < box.left + 180) scroll.scrollLeft -= 18;
    }
  });
  root.addEventListener("pointerup", event => {
    if (!selection || selection.pointerId !== event.pointerId) return;
    const chosen = { ...selection };
    const pointTarget = document.elementFromPoint(event.clientX, event.clientY);
    const anchor = pointTarget && pointTarget.closest("[data-date]");
    cancelSelection(); suppressClickUntil = Date.now() + 400;
    if (root.hasPointerCapture(event.pointerId)) root.releasePointerCapture(event.pointerId);
    openCreate(chosen.start, addDays(chosen.end, 1), chosen.property, cleaningMode ? "cleaning" : "stay", anchor);
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
      if (event.shiftKey && !readOnly) {
        keyboardAnchor = keyboardAnchor || day;
        selection = { anchor: keyboardAnchor, start: nextDay < keyboardAnchor ? nextDay : keyboardAnchor,
          end: nextDay > keyboardAnchor ? nextDay : keyboardAnchor, property: cell.dataset.property || state.property };
        paintSelection();
      } else cancelSelection();
      candidates[0].focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const start = selection ? selection.start : day, end = addDays(selection ? selection.end : day, 1);
      openCreate(start, end, cell.dataset.property || state.property, cleaningMode ? "cleaning" : "stay", cell);
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
      openCreate(day.dataset.calDay, addDays(day.dataset.calDay, 1), day.dataset.property || state.property, cleaningMode ? "cleaning" : "stay", day); return;
    }
    const more = target.closest("[data-cal-more]");
    if (more) { openDay(more.dataset.calMore); return; }
    const month = target.closest("[data-cal-month-open]");
    if (month) { state.date = month.dataset.calMonthOpen; state.mode = "calendar"; state.scale = "month"; savePreferences(); load(); return; }
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
    if (target.closest("[data-cal-day-add]") && dayListDate) openCreate(dayListDate, addDays(dayListDate, 1), state.property, cleaningMode ? "cleaning" : "stay", target.closest("[data-cal-day-add]"));
  });
  document.querySelectorAll("[data-calendar-add]").forEach(link => link.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0 || !state.properties.length) return;
    event.preventDefault();
    openCreate(root.dataset.today, addDays(root.dataset.today, 1), state.property,
      link.dataset.calCreateType || (cleaningMode ? "cleaning" : "stay"), link);
  }));
  $$("[data-cal-type-choice]").forEach(button => button.addEventListener("click", () => setCreateKind(button.dataset.calTypeChoice)));
  $("[data-cal-property]").addEventListener("change", event => {
    state.property = event.target.value;
    if (state.mode === "auto") state.scale = "month";
    load();
  });
  function changePeriod() {
    const next = $("[data-cal-year]").value + "-" + $("[data-cal-month]").value + "-01";
    if (validDate(next)) { state.date = next; load(); }
  }
  $("[data-cal-month]").addEventListener("change", changePeriod);
  $("[data-cal-year]").addEventListener("change", changePeriod);
  $$("[data-cal-view]").forEach(button => button.addEventListener("click", () => {
    state.mode = button.dataset.calView;
    savePreferences(); load();
  }));
  $$("[data-cal-scale]").forEach(button => button.addEventListener("click", () => {
    state.mode = "calendar"; state.scale = button.dataset.calScale;
    savePreferences(); load();
  }));
  $("[data-cal-auto]").addEventListener("change", event => {
    state.mode = event.target.checked ? "auto" : view();
    if (state.mode === "auto") state.scale = "month";
    savePreferences(); load();
  });
  $$("[data-cal-display]").forEach(input => input.addEventListener("change", () => {
    state.display[input.dataset.calDisplay] = input.checked; savePreferences(); render();
  }));
  ["date_from", "date_to", "apartment_id"].forEach(name => form.elements[name].addEventListener("change", updateNights));
  async function refreshDashboardRegions() {
    const response = await fetch(location.pathname + location.search, {
      credentials: "same-origin", headers: { Accept: "text/html" }, cache: "no-store"
    });
    if (!response.ok || response.redirected || !(response.headers.get("content-type") || "").includes("text/html"))
      throw new Error("dashboard-refresh");
    const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
    for (const key of ["stats", "work"]) {
      const current = document.querySelector('[data-dashboard-refresh="' + key + '"]');
      const fresh = parsed.querySelector('[data-dashboard-refresh="' + key + '"]');
      if (!current || !fresh) throw new Error("dashboard-refresh");
      const imported = document.importNode(fresh, true);
      current.replaceWith(imported);
      if (key === "work") {
        document.dispatchEvent(new CustomEvent("ubyhost:content-updated", { detail: { root: imported } }));
      }
    }
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving || !form.reportValidity()) return;
    const savedKind = createKind, savedProperty = form.elements.apartment_id.value;
    const savedDate = savedKind === "cleaning" ? form.elements.scheduled_date.value : form.elements.date_from.value;
    const savedEnd = savedKind === "stay" ? form.elements.date_to.value : addDays(savedDate, 1);
    const actionPath = savedKind === "cleaning" ? "/cleaning/events" : "/reservations";
    const action = actionPath + (root.dataset.lang ? "?lang=" + encodeURIComponent(root.dataset.lang) : "");
    const payload = new FormData(form); // Capture before disabling the type controls.
    const save = $("[data-cal-save]");
    saving = true; save.disabled = true; save.textContent = labels.saving;
    $$("[data-cal-type-choice]").forEach(button => { button.disabled = true; });
    $("[data-cal-save-error]").textContent = "";
    try {
      const response = await fetch(action, { method: "POST", body: payload,
        headers: { Accept: "application/json", "x-csrf-token": form.elements._csrf.value } });
      if (response.redirected || !(response.headers.get("content-type") || "").includes("application/json")) throw new Error("session");
      const data = await response.json();
      if (response.status === 409 && data.overlap && savedKind === "stay") {
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
          const first = Object.keys(data.errors)[0];
          const input = form.elements.namedItem(first); if (input && !input.disabled) input.focus();
          return;
        }
        throw new Error("save");
      }
      // The POST has committed. Refresh failures stay in the saved state and never invite a duplicate.
      saving = false; close(createDialog);
      const [rangeStart, rangeEnd] = range();
      if (!displayOverlap({ start: savedDate, end: savedEnd }, rangeStart, rangeEnd)) state.date = savedDate;
      if (state.property && state.property !== savedProperty) state.property = savedProperty;
      const createdMessage = savedKind === "cleaning" ? labels.cleaning_created : labels.stay_created;
      const openLabel = savedKind === "cleaning" ? labels.view_cleaning : labels.open;
      const targetUrl = new URL(data.url, location.href);
      if (root.dataset.lang) targetUrl.searchParams.set("lang", root.dataset.lang);
      const openHref = targetUrl.pathname + targetUrl.search + targetUrl.hash;
      const refreshCommitted = async () => {
        let refreshed = false;
        try {
          await load();
          refreshed = !!lastLoadedRange;
          if (refreshed && savedKind === "stay" && !cleaningMode) await refreshDashboardRegions();
        } catch (_) {
          refreshed = false;
        }
        setMessage(refreshed ? createdMessage : createdMessage + " " + labels.refresh_failed,
          refreshed ? false : refreshCommitted, openHref, openLabel);
      };
      await refreshCommitted();
    } catch (error) {
      $("[data-cal-save-error]").textContent = error.message === "session" ? labels.session_error : labels.save_error;
    } finally {
      saving = false; save.disabled = false; save.textContent = createKind === "cleaning" ? labels.create_cleaning : labels.create_stay;
      $$("[data-cal-type-choice]").forEach(button => { button.disabled = false; });
      if (createDialog.open) requestAnimationFrame(() => placeCreate(createAnchor));
    }
  });
  window.addEventListener("resize", () => {
    if (!state.loading && lastLoadedRange) render();
    if (createDialog.open) requestAnimationFrame(() => placeCreate(createAnchor));
  });
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
  setCreateKind(cleaningMode ? "cleaning" : "stay");
  root.addEventListener("calendar:refresh", load);
  if (cleaningMode) {
    $("[data-cal-day-add]").hidden = readOnly;
    root.querySelectorAll("[data-cal-display='guests']").forEach(input => { input.closest("label").hidden = true; });
  }
  load();
})();
