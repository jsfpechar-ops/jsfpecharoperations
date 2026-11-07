# 0967: restore calendar orientation and overflow legibility (B09: C02, C03)

Status: blocked (check 1 stopped at existing test_calendar_geometry_locales_and_screenshots line 335: max tile height 226 > 184; see docs/tasks/0967-report.md)
Depends on: 0978 (colour fix, this branch's base); B02 (codex/0960-b02-calendar-create) shares calendar files, merge order is the owner's | Base commit: de537cb3 | Branch: codex/0967-b09-calendar-orient
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The dashboard calendar page gets a visible, non-empty H1 ("Calendar", the navigation name) and no month caption that repeats the period title. In the month tiles the "+N" badge gets its own last row under the stay bars, so it never covers booking text, and bars show only their avatar (never a name fragment) when the week is too narrow for a readable name.

## 2. Context

Worktree `/tmp/ubyhost-b09-worktree` already exists on the branch above (created by the orchestrator, based on 0978). All paths below are relative to the repo root unless they start with `App/`. Rules that apply: AGENTS.md hard rules 6 (light mode), 7 (browser + geometry tests, 0 skipped, one 390 px screenshot per changed page), 10 (UX gate: you look at screenshots and write what you saw).

What is wrong today (verified by reading):

- `App/app/templates/dashboard.html` line 49: with `cal_view`, the H1 holds `<span class="ph-hide cal-hide">` (never shown) and `<span class="ph-only">Calendar</span>` (shown only at 1023 px and below). At 1024 px and up the H1 is empty and the CSS `.head h1:after` coral bar (app2.css line 79) shows with no title. Phone and tablet already show "Calendar" (centred, 30 px); that stays as it is.
- `App/app/static/dashboard-calendar.js` `pillRow()`: stays in lane 3 and later are counted in `hidden[]`. The `+N` button is placed with CSS `grid-row:1; align-self:start; margin:10px 10px 0 0` (dashboard-calendar.css line 808), i.e. on top of the lane 0 bar. That is the collision.
- `.cal-month-title` (h4, first month section) repeats `[data-cal-period]` shown in the sticky head.
- With the day panel open the grid is narrowed by 316-340 px (css lines 701 and 705; existing tests keep the toolbar left of the panel, so the margin stays) and bar names shrink to 1-2 characters.

Decisions already taken (do not reopen): keep the panel margin; phone dot tiles, the phone bottom sheet and the cleaning page (`data-cleaning="true"`) are untouched; the 4th lane is only added at 768 px and up and not in cleaning mode (the cleaning chips offset formula uses `--pl`). The first month caption is hidden at 768 px and up only; later month captions stay as month dividers. Names are hidden by a CSS container query when the week row is 687 px wide or less (one-night bar then has under 40 px for the name); the title, aria-label and day panel keep the full name.

Context rollout: not used.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/dashboard.html | edit | line 49 only: the calendar H1 (step 1) |
| App/app/templates/_dashboard_calendar.html | edit | line 2 and line 173: only the two `?v=` keys (step 2). The calendar `<h2 id="calendar-title">` is left alone: the CSS already hides it visually at every width |
| App/app/static/dashboard-calendar.css | edit | append one block at the end (step 2) |
| App/app/static/dashboard-calendar.js | edit | `pillRow()`: the `overflowLane` constant, one `gridRow` line, `overlay.dataset.lanes` line (step 2) |
| App/tests/static_versions.json | edit | the two entries, via the patch (step 2) |
| App/tests/test_dashboard_calendar_browser.py | edit | one existing line (`range(3)` to `range(4)` in `check_tiles_0891`, plus its comment) and four new tests appended (step 3) |
| docs/tasks/0967-report.md | create | the report (§9) |

No other file may change.

## 4. Steps

Run everything from the worktree. First:

```
cd /tmp/ubyhost-b09-worktree && git status --short | tail -5 && git log --oneline -1 | tail -2
ln -s /tmp/ubyhost-0958-worktree/App/.venv App/.venv 2>&1 | tail -3
```
Expected: clean status, `de537cb3`. `App/.venv` is git-ignored. If `/tmp/ubyhost-0958-worktree/App/.venv` is missing, STOP (§8).

### Step 1: visible H1 (finding C02)

Anchor check:
```
grep -nF "<span class=\"ph-only\">{% if cal_view %}{{ t('nav.calendar') }}" App/app/templates/dashboard.html | cut -c1-80 | tail -3
```
Must print line 49. Not found: STOP. Write the patch below to `/tmp/ubyhost-b09-a.patch` (exactly as shown), then:
```
git apply --check /tmp/ubyhost-b09-a.patch && git apply /tmp/ubyhost-b09-a.patch && git diff --stat | tail -5
git commit -am "0967 step 1" | tail -2
```

```diff
diff --git a/App/app/templates/dashboard.html b/App/app/templates/dashboard.html
index 8cc6aa6d..6964e14e 100644
--- a/App/app/templates/dashboard.html
+++ b/App/app/templates/dashboard.html
@@ -46,7 +46,7 @@
   </div>
   <div class="head ov-head"><div>
     {#- 0729: the page's one h1: "Overview" on desktop, the headline on phone. -#}
-    <h1 class="hl{{ ' done' if not ny_lines }}"><span class="ph-hide{{ ' cal-hide' if cal_view }}">{{ t('dashboard.title') }}{{ page_help('dashboard') }}</span><span class="ph-only">{% if cal_view %}{{ t('nav.calendar') }}{% elif ny_lines %}{{ tp('dashboard.ph.need', ny_lines | length) }}{% else %}{{ t('dashboard.ph.done') }}{% endif %}</span></h1>
+    <h1 class="hl{{ ' done' if not ny_lines }}">{% if cal_view %}<span>{{ t('nav.calendar') }}</span>{% else %}<span class="ph-hide">{{ t('dashboard.title') }}{{ page_help('dashboard') }}</span><span class="ph-only">{% if ny_lines %}{{ tp('dashboard.ph.need', ny_lines | length) }}{% else %}{{ t('dashboard.ph.done') }}{% endif %}</span>{% endif %}</h1>
     <p class="sub ph-hide{{ ' cal-hide' if cal_view }}">{{ today.isoformat() | date_long(lang) }}</p>
     <div class="ov-quiet ph-hide{{ ' cal-hide' if cal_view }}">
     <p class="ov-links ph-hide{{ ' cal-hide' if cal_view }}">
```

Effect: with `cal_view` the H1 is one plain `<span>` with `nav.calendar` ("Calendar"; Czech "Kalendář") at every width. Without `cal_view` the markup and phone text are as before (the `cal-hide` class and the `if cal_view` branch inside the old spans were dead there).

### Step 2: overflow lane, repeated caption, narrow bars, focus ring (finding C03)

Anchors (each must print exactly one line, else STOP):
```
grep -nF "overlay.dataset.lanes = String(shown);" App/app/static/dashboard-calendar.js | tail -3
grep -nF "hidden.forEach((count, index) => {" App/app/static/dashboard-calendar.js | tail -3
grep -nF "dashboard-calendar.css?v=20261105-0958b" App/app/templates/_dashboard_calendar.html | cut -c1-90 | tail -3
grep -nF "dashboard-calendar.js?v=20261105-0956b" App/app/templates/_dashboard_calendar.html | cut -c1-90 | tail -3
```
Write the patch to `/tmp/ubyhost-b09-b.patch`, then:
```
git apply --check /tmp/ubyhost-b09-b.patch && git apply /tmp/ubyhost-b09-b.patch && git diff --stat | tail -8
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3; cd .. && git status --short | tail -8
```
`--write` must leave `App/tests/static_versions.json` unchanged beyond the patch (the patch already holds the new sha256 values). If `git diff` shows other changes in that json, STOP. Then `git commit -am "0967 step 2" | tail -2`.

```diff
diff --git a/App/app/static/dashboard-calendar.css b/App/app/static/dashboard-calendar.css
index 63ed2ec7..40a2cf9b 100644
--- a/App/app/static/dashboard-calendar.css
+++ b/App/app/static/dashboard-calendar.css
@@ -877,3 +877,19 @@ body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-pill[data-cal-c
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chip.cal-clean-chip .cal-cleaning-icon { display:none; }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chip.cal-clean-chip > span { min-width:0; overflow:hidden; text-overflow:ellipsis; }
 }
+
+/* 0967: host calendar orientation and overflow legibility (month tiles, 768 px and up; the phone dot tiles and the cleaning page are unchanged).
+   1. The "+N" badge sits in its own last grid row under the stay lanes (JS gives it row lanes+1), so it never covers a bar.
+   2. The first month caption repeats the period title above it, so it is hidden; later months keep their caption.
+   3. When the week is too narrow for a readable name (side panel open, narrow window) the bars show only the avatar; the full name stays in the title, the aria-label and the day panel. */
+@media (min-width:768px) {
+  body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] .cal-pill-more { align-self:end; justify-self:end; height:24px; min-height:24px; margin:0 4px 0 0; line-height:24px; }
+  body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] .cal-month:first-of-type .cal-month-title { display:none; }
+  body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] .cal-week.is-dots { container:calweek / inline-size; }
+  @container calweek (max-width:687px) {
+    body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] .cal-pill-name { display:none; }
+    body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] .cal-pill { min-width:32px; padding:0 4px; }
+  }
+  /* A keyboard ring that shows on the dark bars and badges and on the white and dark tiles. */
+  body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="false"] :is(.cal-pill, .cal-pill-more):focus-visible { outline:2px solid #fff; outline-offset:0; box-shadow:0 0 0 4px #222; }
+}
diff --git a/App/app/static/dashboard-calendar.js b/App/app/static/dashboard-calendar.js
index d187235d..41014447 100644
--- a/App/app/static/dashboard-calendar.js
+++ b/App/app/static/dashboard-calendar.js
@@ -319,14 +319,17 @@
         pill.append(el("span", "cal-pill-avatar", (name.trim().charAt(0) || "·").toUpperCase()), el("span", "cal-pill-name", name));
         overlay.append(pill);
       });
+    // 0967: on the host calendar at 768 px and up the "+N" badge gets its own last grid row under the stay lanes, so it never covers a bar.
+    const overflowLane = !cleaningMode && matchMedia("(min-width:768px)").matches && hidden.some(Boolean);
     hidden.forEach((count, index) => {
       if (!count) return;
       const date = addDays(week, index), more = el("button", "cal-pill-more", "+" + String(count));
       more.type = "button"; more.dataset.calMore = date; more.style.gridColumn = String(index * 2 + 1) + " / span 2";
+      if (overflowLane) more.style.gridRow = String(shown + 1);
       more.setAttribute("aria-label", fullDate(date) + " · " + format("more", { count }));
       overlay.append(more);
     });
-    overlay.dataset.lanes = String(shown);
+    overlay.dataset.lanes = String(shown + (overflowLane ? 1 : 0));
     return overlay;
   }
   function renderCalendar() {
diff --git a/App/app/templates/_dashboard_calendar.html b/App/app/templates/_dashboard_calendar.html
index ea08b044..a552cee4 100644
--- a/App/app/templates/_dashboard_calendar.html
+++ b/App/app/templates/_dashboard_calendar.html
@@ -1,5 +1,5 @@
 {# Calendar data is fetched from an owner-scoped endpoint, never embedded in browser storage. #}
-<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0958b">
+<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0967a">
 <section id="calendar" class="dashboard-calendar" data-calendar data-today="{{ today.isoformat() }}" data-source="{{ calendar_source | default('/dashboard/calendar') }}" data-cleaning="{{ 'true' if calendar_cleaning | default(false) else 'false' }}" data-readonly="{{ 'true' if calendar_readonly | default(false) else 'false' }}" data-calendar-date="{{ calendar_date | default('') }}" data-range-from="{{ calendar_from | default('') }}" data-range-to="{{ calendar_to | default('') }}" data-lang="{{ lang }}" aria-labelledby="calendar-title">
   <div class="cal-head" data-cal-head>
   <div class="cal-heading">
@@ -170,4 +170,4 @@
   <script type="application/json" data-cal-properties>[{% for apartment in apartments if apartment.active %}{{ {'id': apartment.id, 'name': apartment.internal_name} | tojson }}{% if not loop.last %},{% endif %}{% endfor %}]</script>
   <script type="application/json" data-cal-labels>{{ calendar_labels | tojson }}</script>
 </section>
-<script src="/static/dashboard-calendar.js?v=20261105-0956b" defer></script>
+<script src="/static/dashboard-calendar.js?v=20261105-0967a" defer></script>
diff --git a/App/tests/static_versions.json b/App/tests/static_versions.json
index 04a71229..22ccbf6d 100644
--- a/App/tests/static_versions.json
+++ b/App/tests/static_versions.json
@@ -60,12 +60,12 @@
     "v": "20260915a"
   },
   "dashboard-calendar.css": {
-    "sha256": "e1674c6b2263bfc11de7504bfc9d8d7377c25fc088acce4d45c2a760f9e1fe9f",
-    "v": "20261105-0958b"
+    "sha256": "f10abb4241be2928211620d02c351e84b7d64626e41f593c9affd90f247298b5",
+    "v": "20261105-0967a"
   },
   "dashboard-calendar.js": {
-    "sha256": "327c1375ba47ad6b040b9e301a5696bf9fa9b0ce3a5fd46678f0a36f773a6bf1",
-    "v": "20261105-0956b"
+    "sha256": "50fc2a79fdb2afd12d422daa165cae4d00277d897eb0fa8ac8a01d6c2be4e4bd",
+    "v": "20261105-0967a"
   },
   "docs/ubyport-ws-credential-sample.pdf": {
     "sha256": "0c147cf9c5dd5326612bc4668c5bce853cf300171ca62e3a0bab688c09b75fe6",
```

Effect: at 768 px and up, outside cleaning mode, when any day has hidden stays the `+N` button is placed in grid row `shown + 1` (below the last bar lane) and `--pl` grows by one, so the tile grows by 44 px (the existing `calc(94px + (--pl - 1) * 44px)`); the badge is bottom-aligned inside its tile. Phone and cleaning behaviour are unchanged.

### Step 3: tests

Anchor: `grep -nF "for k in range(3))" App/tests/test_dashboard_calendar_browser.py | cut -c1-60 | tail -3` must print one line. Write the patch to `/tmp/ubyhost-b09-c.patch`, then:
```
git apply --check /tmp/ubyhost-b09-c.patch && git apply /tmp/ubyhost-b09-c.patch && git diff --stat | tail -5
python3 -W error -m py_compile App/tests/test_dashboard_calendar_browser.py 2>&1 | tail -5
git commit -am "0967 step 3" | tail -2
```

```diff
diff --git a/App/tests/test_dashboard_calendar_browser.py b/App/tests/test_dashboard_calendar_browser.py
index 3f479295..f7cca121 100644
--- a/App/tests/test_dashboard_calendar_browser.py
+++ b/App/tests/test_dashboard_calendar_browser.py
@@ -1001,9 +1001,9 @@ def check_tiles_0891(rows, width, tile_height=None):
         for a, b in zip(row["t"], row["t"][1:]):
             assert abs(b[0] - a[1] - gap) <= 1, ("column gap", width, a, b)
         if tile_height:
-            # 0905: each extra stacked stay lane adds 44 px; every tile of a row has the same height.
+            # 0905: each extra stacked stay lane adds 44 px (0967: the +N lane is the fourth); every tile of a row has the same height.
             heights = {round(t[3] - t[2]) for t in row["t"]}
-            assert len(heights) == 1 and any(abs(heights.copy().pop() - (tile_height + k * 44)) <= 1 for k in range(3)), ("tile height", width, row)
+            assert len(heights) == 1 and any(abs(heights.copy().pop() - (tile_height + k * 44)) <= 1 for k in range(4)), ("tile height", width, row)
     for upper, lower in zip(rows, rows[1:]):
         if upper["s"] == lower["s"]:
             assert abs(lower["t"][0][2] - upper["t"][0][3] - gap) <= 1, ("row gap", width, upper, lower)
@@ -1270,3 +1270,176 @@ def test_0978_record_type_selection_is_visually_unambiguous(
         finally:
             context.close()
             browser.close()
+
+
+# 0967: calendar orientation (one named H1, no repeated month caption) and a +N lane that never covers a bar.
+NAV_NAME_0967 = {"en": "Calendar", "cs": "Kalendář"}
+DENSE_DAYS_0967 = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
+PANEL_OPEN_0967 = "() => [...document.querySelectorAll('[data-cal-day-dialog][open]')].every(d => getComputedStyle(d).opacity === '1')"
+OVERFLOW_0967 = r"""(day) => {
+    const badge = document.querySelector(`.cal-pill-more[data-cal-more="${day}"]`);
+    if (!badge) return null;
+    const week = badge.closest('.cal-week'), tile = week.querySelector(`.cal-day[data-date="${day}"]`);
+    const b = badge.getBoundingClientRect(), t = tile.getBoundingClientRect();
+    const pills = [...week.querySelectorAll('.cal-pill')];
+    return {
+        count: parseInt(badge.textContent.replace(/\D/g, ''), 10),
+        covering: pills.filter(p => p.dataset.calFrom <= day && day < p.dataset.calTo).length,
+        badgeTop: b.top, lowestBar: Math.max(...pills.map(p => p.getBoundingClientRect().bottom)),
+        inside: b.left >= t.left - 1 && b.right <= t.right + 1 && b.top >= t.top - 1 && b.bottom <= t.bottom + 1,
+    };
+}"""
+NAMES_0967 = """() => [...document.querySelectorAll('.cal-pill-name')]
+    .filter(node => getComputedStyle(node).display !== 'none').map(node => Math.round(node.getBoundingClientRect().width))"""
+
+
+def overlaps_0967(page, first, second):
+    """Pairs of visible boxes (first vs second) that share more than half a pixel in both directions, per week row."""
+    return page.evaluate("""([first, second]) => {
+        const hit = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
+        const visible = node => node.offsetParent !== null && getComputedStyle(node).visibility !== 'hidden';
+        const found = [];
+        document.querySelectorAll('.cal-week').forEach(week => {
+            const a = [...week.querySelectorAll(first)].filter(visible), b = [...week.querySelectorAll(second)].filter(visible);
+            a.forEach(x => b.forEach(y => { if (x !== y && hit(x.getBoundingClientRect(), y.getBoundingClientRect())) found.push([x.textContent, y.textContent]); }));
+        });
+        return found;
+    }""", [first, second])
+
+
+def open_month_0967(page, origin, locale="en", date="2026-10-01"):
+    page.goto(f"{origin}/?lang={locale}&cal_view=calendar&cal_date={date}")
+    page.wait_for_selector(".cal-month")
+    wait_loaded(page)
+    page.evaluate("window.scrollTo(0, 0)")
+    page.wait_for_timeout(300)
+
+
+@pytest.mark.parametrize("locale", ["en", "cs"])
+@pytest.mark.parametrize("width", [390, 768, 1280])
+def test_0967_calendar_page_has_one_named_heading_and_no_repeated_month(calendar_workspace, calendar_origin, width, locale):
+    with sync_api.sync_playwright() as playwright:
+        browser = launch(playwright)
+        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale=locale, touch=width < 768)
+        try:
+            open_month_0967(page, calendar_origin, locale)
+            headings = page.locator("h1:visible")
+            assert headings.count() == 1, headings.all_inner_texts()
+            assert headings.first.inner_text().strip() == NAV_NAME_0967[locale]
+            h1, head = headings.first.bounding_box(), page.locator("[data-cal-head]").bounding_box()
+            assert h1["width"] > 40 and h1["height"] > 16 and h1["y"] + h1["height"] <= head["y"] + 1, (h1, head)
+            assert headings.first.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
+            assert page.locator("[data-cal-period]").inner_text().strip()
+            if width >= 768:
+                titles = page.locator(".cal-month-title")
+                assert titles.first.is_hidden() and titles.nth(1).is_visible()  # the first caption repeats the period title
+            assert page.evaluate(FITS_0891)
+            shot(page, f"0967-heading-{locale}-{width}")
+        finally:
+            context.close()
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [390, 768, 1280])
+def test_0967_overflow_badge_has_its_own_lane_and_counts_match_the_day_list(calendar_workspace, calendar_origin, width):
+    with sync_api.sync_playwright() as playwright:
+        browser = launch(playwright)
+        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
+        try:
+            open_month_0967(page, calendar_origin)
+            if width < 768:  # the phone keeps its dot tiles and the day sheet; no badge is drawn
+                assert page.locator(".cal-pill-more:visible").count() == 0
+                return
+            assert overlaps_0967(page, ".cal-pill-more", ".cal-pill") == []
+            measured = {}
+            for day in DENSE_DAYS_0967:
+                info = page.evaluate(OVERFLOW_0967, day)
+                assert info and info["count"] >= 1 and info["covering"] <= 3, (day, info)
+                assert info["inside"], (day, info)
+                assert info["badgeTop"] >= info["lowestBar"] - 0.5, (day, info)  # the badge lane is under every bar of the week
+                measured[day] = info
+            shot(page, f"0967-overflow-{width}")
+            for day, info in measured.items():
+                page.locator(f'.cal-pill-more[data-cal-more="{day}"]').click()
+                page.wait_for_selector("[data-cal-day-dialog]", state="visible")
+                page.wait_for_function(PANEL_OPEN_0967)
+                items = page.locator('[data-cal-day-list] .cal-event:not([data-event-kind="cleaning"])').count()
+                assert items == info["covering"] + info["count"], (day, items, info)  # hidden count + drawn bars = the day list
+                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
+                page.locator("[data-cal-day-dialog]").wait_for(state="hidden")
+        finally:
+            context.close()
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [768, 1024, 1280])
+def test_0967_open_day_panel_never_crushes_booking_text(calendar_workspace, calendar_origin, width):
+    with sync_api.sync_playwright() as playwright:
+        browser = launch(playwright)
+        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
+        try:
+            open_month_0967(page, calendar_origin)
+            for state in ("closed", "open"):
+                if state == "open":
+                    page.locator('.cal-pill-more[data-cal-more="2026-10-16"]').click()
+                    page.wait_for_selector("[data-cal-day-dialog]", state="visible")
+                    page.wait_for_function(PANEL_OPEN_0967)
+                    for item in page.locator("[data-cal-day-list] .cal-event").all():
+                        assert item.bounding_box()["width"] >= 200  # the panel list keeps full, wrapped names
+                    assert page.locator('.cal-pill-more[data-cal-more="2026-10-16"]').is_visible()
+                assert page.locator(".cal-pill").count() >= 3
+                names = page.evaluate(NAMES_0967)
+                assert all(width_ >= 36 for width_ in names), (state, names)  # a name is readable or not drawn; never a fragment
+                assert overlaps_0967(page, ".cal-pill-more", ".cal-pill") == []
+                assert page.evaluate(FITS_0891)
+                shot(page, f"0967-panel-{state}-{width}")
+            page.locator("[data-cal-day-dialog] [data-cal-close]").click()
+            page.locator("[data-cal-day-dialog]").wait_for(state="hidden")
+        finally:
+            context.close()
+            browser.close()
+
+
+@pytest.mark.parametrize("width", [768, 1280])
+def test_0967_scales_navigation_and_keyboard_focus(calendar_workspace, calendar_origin, width):
+    with sync_api.sync_playwright() as playwright:
+        browser = launch(playwright)
+        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
+        try:
+            open_month_0967(page, calendar_origin, date="2026-10-14")
+            for scale in ("week", "year", "month"):
+                page.locator(f'[data-cal-scale="{scale}"]').click()
+                wait_loaded(page)
+                assert page.locator("h1:visible").count() == 1
+                assert page.locator("[data-cal-period]").inner_text().strip()
+                assert overlaps_0967(page, ".cal-more", ".cal-event") == []
+                if scale == "week":
+                    assert page.locator(".cal-more:visible").count() >= 1
+                    shot(page, f"0967-week-{width}")
+                if scale == "year":
+                    assert page.locator(".cal-mini-title").count() == 12
+                    assert page.locator("[data-cal-period]").inner_text().strip() == "2026"
+                    shot(page, f"0967-year-{width}")
+            page.evaluate("window.scrollTo(0, 0)")
+            page.locator("[data-cal-next]").click()
+            wait_loaded(page)
+            assert page.locator("[data-cal-period]").inner_text() == "November 2026"
+            page.locator("[data-cal-prev]").click()
+            wait_loaded(page)
+            assert page.locator("[data-cal-period]").inner_text() == "October 2026"
+            page.locator("[data-cal-today]").click()
+            wait_loaded(page)
+            page.evaluate("window.scrollTo(0, 0)")
+            assert page.locator("[data-cal-period]").inner_text() == page.locator(".cal-month").first.get_attribute("aria-label")
+            open_month_0967(page, calendar_origin)
+            badge = page.locator('.cal-pill-more[data-cal-more="2026-10-16"]')
+            badge.focus()
+            page.keyboard.press("Shift+Tab")
+            page.keyboard.press("Tab")  # a key press, so :focus-visible applies
+            assert badge.evaluate("node => node === document.activeElement")
+            ring = badge.evaluate("node => { const s = getComputedStyle(node); return [s.outlineStyle, parseFloat(s.outlineWidth), s.boxShadow]; }")
+            assert (ring[0] != "none" and ring[1] >= 2) or ring[2] != "none", ring
+            shot(page, f"0967-focus-{width}")
+        finally:
+            context.close()
+            browser.close()
```

The new tests, in words: (1) one visible H1 equal to the navigation name in EN and CS at 390/768/1280, above the sticky head, not clipped, no horizontal scroll, first month caption hidden at 768+ and the second visible; (2) at 768/1280 each of Oct 14-18 has a badge inside its tile, below every bar of the week, overlapping no bar, and `bars drawn on that day + badge number == items in the day list`; at 390 no badge is visible; (3) at 768/1024/1280 with the panel closed and open every drawn bar name is at least 36 px wide or not drawn, the panel list items are at least 200 px wide, no horizontal scroll; (4) at 768/1280 Month, Week and Year views show one H1, week `+N more` buttons overlap no bar, Year shows 12 mini months and period "2026", previous/next/today work, and a keyboard-focused badge shows a ring.

## 5. Do not touch

- Event filtering, dates, occupancy, booking spans, fractional checkout, fetching (`/dashboard/calendar`), the create dialog, the phone dot tiles and bottom sheet, the cleaning page and its CSS, `app2.css`, `base.html`, i18n files.
- Do not change the day-panel margin rules (css lines 701, 705): existing tests require the toolbar to stay left of the panel.
- AGENTS hard rules: light mode only; no tracking cookies or new outbound requests; no new dependency (the container query is plain CSS); never push, never merge, never touch `main`; no secrets or guest data in the report or screenshots.

## 6. Commands

Run from `/tmp/ubyhost-b09-worktree/App`. Always the same prefix; every command ends `2>&1 | tail -30`. Shots go to `/tmp/ubyhost-b09` only. Run in this order and stop at the first failing command (rule: one fix, one rerun, then STOP).

```
export UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b09; mkdir -p /tmp/ubyhost-b09
```
1. New and touched calendar tests (expect all pass, 0 skipped; 14 new test cases: 6 + 3 + 3 + 2 parametrised, plus the existing ones in that file):
`.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -rs -q --tb=short -x 2>&1 | tail -30`
2. Calendar row, rest: `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar.py tests/test_calendar_*.py tests/test_sample_calendar.py tests/test_0898_calendar_names_browser.py tests/test_0955_calendar_toolbar_stable_browser.py tests/test_0956_calendar_rule_colours_browser.py -rs -q --tb=short -x 2>&1 | tail -30`
3. Dashboard and phone geometry: `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_0765_phone_today_window_browser.py tests/test_dashboard_rows_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_0905_cleaning_calendar_stays_browser.py tests/test_0507_page_hooks_browser.py -rs -q --tb=short -x 2>&1 | tail -30`
4. Host pages and design: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py -rs -q --tb=short -x 2>&1 | tail -30`
5. v2 row: `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -rs -q --tb=short -x 2>&1 | tail -30`
6. Static checks: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`
7. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

Skipped tests (`-rs` lists them) mean broken: STOP. A failure in an existing test that was green before your steps (do not stash or checkout to compare; read the failure): if it is the 0891 tile-height check, the `range(4)` edit is already in; any other existing failure: STOP and report the test name and last 30 lines.

### UX gate (rule 10; you decide pass or fail)

The tests write these PNGs to `/tmp/ubyhost-b09` (`calendar-0967-*.png`): `heading-{en,cs}-{390,768,1280}`, `overflow-{768,1280}`, `panel-{closed,open}-{768,1024,1280}`, `week-{768,1280}`, `year-{768,1280}`, `focus-{768,1280}`. Open each file once with the Read tool (do not retake) and look for: H1 present, readable and not duplicated; no coral bar without title; badge bottom-right in its tile with clear space above it; no dark badge on bar text; with the panel open every visible bar name is a readable word or the bar shows only the circle avatar (never 1-3 letters); Week and Year views intact; focus ring visible. Write one line per group of shots into the report (§9) as `shot: seen / verdict`. If a shot shows a defect the tests did not catch (for example the badge cut off, the tile too tall, bars mis-aligned after the container-query hides names): fail the gate, STOP, and describe it. Never loosen a test to pass.

## 7. Acceptance

- [ ] Steps 1-3 committed as `0967 step 1`, `0967 step 2`, `0967 step 3`; `git diff --stat main...HEAD` lists only the §3 files.
- [ ] Commands 1-7 pass, 0 skipped.
- [ ] H1 "Calendar"/"Kalendář" is the only visible H1 at 390, 768 and 1280, EN and CS.
- [ ] No `.cal-pill-more` overlaps a `.cal-pill` (measured); badge sits below every bar of its week; hidden counts + drawn bars equal the day list for Oct 14-18.
- [ ] With the panel open at 768, 1024 and 1280 no bar shows a name narrower than 36 px; the day list items are at least 200 px wide.
- [ ] Month, Week, Year, previous, next, today and keyboard focus checked by the tests and the screenshots at 768 and 1280; 390 px shots seen for the H1 and the unchanged phone tiles.
- [ ] Event filtering, dates, occupancy, spans and fetching untouched (`git diff` shows no change to those functions).
- [ ] Design-system checklist (`docs/design/design-system.md`) ticked in the report.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or patch hunk is not found, or `git apply --check` fails;
- `/tmp/ubyhost-0958-worktree/App/.venv` is missing;
- a test fails twice, a browser test is skipped, or `static_versions.json` shows changes beyond the patch;
- a UX shot fails the gate (see §6);
- you reach 25 tool calls or about 50k tokens (report as `blocked`, "Done: steps 1 to k. Left: steps k+1 to 3 and commands");
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear, or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0967-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat`); each command with the last 5 lines of its output; §7 ticked; the UX gate lines (one per shot group, seen / verdict); Deviations; Questions; owner steps left. Commit it as `0967 report`. Do not push and do not open a PR: the orchestrator does that after review.

## Risk list (for the reviewer)

- `App/app/static/dashboard-calendar.js` `pillRow()` (the extra row; tile height now up to `94 + 3 * 44`).
- `App/app/static/dashboard-calendar.css` last block (container query on `.cal-week.is-dots`: check it creates no layout shift of the week rows).
- `App/app/templates/dashboard.html` line 49 (phone text for the other states must be unchanged).
- Merge with B02 (`codex/0960-b02-calendar-create`): both touch the calendar JS, CSS and `static_versions.json`; the `?v=` keys and the two json entries will conflict and must be re-bumped and re-written by the merger.
- Known and left alone: on the phone with no open needs the calendar H1 keeps the old 120 px top margin (`h1.hl.done`, app2.css line 904); cleaning-page badge placement is unchanged.

## Owner steps

1. Nothing to do until the orchestrator reports the review. After that, merge only with `scripts/merge-pr-on-green.sh <PR number>`; deploy stays manual.
