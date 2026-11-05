# 0960: calendar create dialog actions, label input, cleaning day-cell name

Status: blocked: after step 1, command 4 (tests/test_cleaning_browser.py, test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs[1280-800]) fails: dialog top differs by 75.5 px between tabs; see docs/tasks/0960-report.md
Depends on: 0958 (already in the base) | Base commit: de537cb3 | Branch: codex/0960-b02-calendar-create
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Batch B02 findings C04, C05, C06. In the Add stay / Add cleaning dialog, Create is the only coral button and Cancel is a quiet secondary button in the same place in both modes. The optional booking-label input uses the shared input style. In the cleaning calendar the day-cell add controls are named "Add cleaning · <date>" (CS "Přidat úklid · <date>") instead of "Add a stay from <date>".

## 2. Context

Worktree `/tmp/ubyhost-b02-worktree`, branch above, already created from 0958 (its `aria-pressed` and `body.v2` colour rules stay as they are; do not duplicate them). `App/.venv` is a symlink to `/tmp/ubyhost-0958-worktree/App/.venv`.

Measured causes (Chromium, current code):
- Desktop (1280): Cancel is `btn soft` but `.btn.soft` has no desktop rule, so `app2.css` `.btn{background:var(--acc)}` paints it coral, 79 px wide, while Create is 430 px wide. Mobile (390) Cancel is grey and both are full-width stacked. Two layouts, and Cancel competes with Create.
- `.cal-create-popover > form{min-height:min(680px,...)}` leaves a large empty area in the cleaning mode.
- `#cal-label` has no `type`, renders with a 2 px dark `#767676` border and 0 radius; sibling inputs have 1 px `#dcdcd7` border and 8 px radius.
- `calendar.select_day` ("Add a stay from %(date)s") names every day cell, including in cleaning mode (`root.dataset.cleaning === "true"`, JS var `cleaningMode`). No new i18n key is needed: `labels.add_cleaning` already exists ("Add cleaning" / "Přidat úklid").

Anchors (each must be found with `grep -nF`; if not, STOP, section 8):

1. `App/app/templates/_dashboard_calendar.html`: `<input id="cal-label" name="summary" maxlength="500">`
2. same file: `<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0958b">`
3. same file: `<script src="/static/dashboard-calendar.js?v=20261105-0956b" defer></script>`
4. `App/app/static/dashboard-calendar.js`: `button.setAttribute("aria-label", format("select_day", { date: fullDate(date) }));`
5. same file: `button.dataset.calDay = day; button.setAttribute("aria-label", property.name + " · " + format("select_day", { date: fullDate(day) }));`
6. `App/app/static/dashboard-calendar.css`: last line is `}` closing `@media (min-width:768px) and (max-width:1023px)`, preceded by `body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chip.cal-clean-chip > span { min-width:0; overflow:hidden; text-overflow:ellipsis; }`. The patch appends after it; the file has 879 lines.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_dashboard_calendar.html | edit | label `type="text"`; cache keys |
| App/app/static/dashboard-calendar.css | edit | append one block |
| App/app/static/dashboard-calendar.js | edit | two aria-label lines |
| App/tests/test_dashboard_calendar_browser.py | append | one test at end of file |
| App/tests/static_versions.json | regenerate | by the script |
| docs/tasks/0960-report.md | create | report |

No other file may change.

## 4. Steps

### Step 1: apply the patch

From the repo root (`/tmp/ubyhost-b02-worktree`) write the patch to a file with the heredoc below, then check and apply it:

```
cat > /tmp/0960.patch <<'PATCH_EOF'
diff --git a/App/app/static/dashboard-calendar.css b/App/app/static/dashboard-calendar.css
index 63ed2ec7..0676efe9 100644
--- a/App/app/static/dashboard-calendar.css
+++ b/App/app/static/dashboard-calendar.css
@@ -877,3 +877,11 @@ body.v2 #calendar.dashboard-calendar[data-readonly="false"] .cal-pill[data-cal-c
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chip.cal-clean-chip .cal-cleaning-icon { display:none; }
   body.v2 #calendar.dashboard-calendar[data-readonly="false"][data-cleaning="true"] .cal-tile-chip.cal-clean-chip > span { min-width:0; overflow:hidden; text-overflow:ellipsis; }
 }
+
+/* 0960: one action row in both create modes. Cancel is quiet, Create is the only coral button. */
+#calendar .cal-create-popover > form { min-height:0; }
+#calendar .cal-create-popover .cal-dialog-actions { display:flex; flex-direction:row; flex-wrap:nowrap; justify-content:flex-end; align-items:stretch; gap:8px; margin-top:20px; }
+#calendar .cal-create-popover .cal-dialog-actions .btn { box-sizing:border-box; min-height:44px; height:44px; margin:0; }
+#calendar .cal-create-popover .cal-dialog-actions .btn.soft { flex:0 0 96px; width:96px; min-width:96px; padding:0; border:1px solid var(--line-2); background:var(--surface); color:var(--ink); }
+#calendar .cal-create-popover .cal-dialog-actions .btn.soft:hover:not(:disabled) { background:var(--surface-2); }
+#calendar .cal-create-popover .cal-dialog-actions .btn.primary { flex:1 1 0; width:auto; min-width:0; }
diff --git a/App/app/static/dashboard-calendar.js b/App/app/static/dashboard-calendar.js
index d187235d..96acd55f 100644
--- a/App/app/static/dashboard-calendar.js
+++ b/App/app/static/dashboard-calendar.js
@@ -368,7 +368,7 @@
         if (date < root.dataset.today) day.classList.add("is-past");
         const button = el("button", "cal-day-number"); button.append(el("span", "cal-num", String(dateValue(date).getUTCDate())));
         button.type = "button"; button.dataset.calDay = date;
-        button.setAttribute("aria-label", format("select_day", { date: fullDate(date) }));
+        button.setAttribute("aria-label", cleaningMode ? labels.add_cleaning + " · " + fullDate(date) : format("select_day", { date: fullDate(date) }));
         button.title = labels.keyboard;
         if (dots && hostCleaning) {
           const dayCleanings = state.events.filter(event => event.kind === "cleaning" && displayOverlap(event, date, addDays(date, 1)));
@@ -528,7 +528,7 @@
       for (let index = 0; index < number; index++) {
         const day = addDays(start, index), button = el("button", "cal-gantt-slot");
         button.type = "button"; button.dataset.date = day; button.dataset.property = String(property.id);
-        button.dataset.calDay = day; button.setAttribute("aria-label", property.name + " · " + format("select_day", { date: fullDate(day) }));
+        button.dataset.calDay = day; button.setAttribute("aria-label", property.name + " · " + (cleaningMode ? labels.add_cleaning + " · " + fullDate(day) : format("select_day", { date: fullDate(day) })));
         if ([0, 6].includes(dateValue(day).getUTCDay())) button.classList.add("is-weekend");
         if (day === root.dataset.today) button.classList.add("is-today");
         days.append(button);
diff --git a/App/app/templates/_dashboard_calendar.html b/App/app/templates/_dashboard_calendar.html
index ea08b044..da1ec3fa 100644
--- a/App/app/templates/_dashboard_calendar.html
+++ b/App/app/templates/_dashboard_calendar.html
@@ -1,5 +1,5 @@
 {# Calendar data is fetched from an owner-scoped endpoint, never embedded in browser storage. #}
-<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0958b">
+<link rel="stylesheet" href="/static/dashboard-calendar.css?v=20261105-0960a">
 <section id="calendar" class="dashboard-calendar" data-calendar data-today="{{ today.isoformat() }}" data-source="{{ calendar_source | default('/dashboard/calendar') }}" data-cleaning="{{ 'true' if calendar_cleaning | default(false) else 'false' }}" data-readonly="{{ 'true' if calendar_readonly | default(false) else 'false' }}" data-calendar-date="{{ calendar_date | default('') }}" data-range-from="{{ calendar_from | default('') }}" data-range-to="{{ calendar_to | default('') }}" data-lang="{{ lang }}" aria-labelledby="calendar-title">
   <div class="cal-head" data-cal-head>
   <div class="cal-heading">
@@ -51,7 +51,7 @@
         <p class="cal-field-error" data-cal-error-for="date_to"></p>
         <p class="cal-nights" data-cal-nights></p>
         <div class="field"><label for="cal-guests">{{ t('stays.add_panel.guests') }} <span class="opt">{{ t('common.optional') }}</span></label><input id="cal-guests" name="expected_guests" type="number" min="1" max="60"><p class="cal-field-error" data-cal-error-for="expected_guests"></p></div>
-        <div class="field"><label for="cal-label">{{ t('stays.add_panel.label') }} <span class="opt">{{ t('common.optional') }}</span></label><input id="cal-label" name="summary" maxlength="500"></div>
+        <div class="field"><label for="cal-label">{{ t('stays.add_panel.label') }} <span class="opt">{{ t('common.optional') }}</span></label><input id="cal-label" name="summary" type="text" maxlength="500"></div>
         <div class="field"><label for="cal-email">{{ t('stays.add_panel.email') }} <span class="opt">{{ t('common.optional') }}</span></label><input id="cal-email" name="guest_email" type="email" maxlength="254"></div>
         <div class="cal-overlap" data-cal-overlap hidden><p>{{ t('calendar.overlap') }}</p><label><input type="checkbox" name="allow_overlap" value="1"> {{ t('calendar.overlap_confirm') }}</label></div>
       </div>
@@ -170,4 +170,4 @@
   <script type="application/json" data-cal-properties>[{% for apartment in apartments if apartment.active %}{{ {'id': apartment.id, 'name': apartment.internal_name} | tojson }}{% if not loop.last %},{% endif %}{% endfor %}]</script>
   <script type="application/json" data-cal-labels>{{ calendar_labels | tojson }}</script>
 </section>
-<script src="/static/dashboard-calendar.js?v=20261105-0956b" defer></script>
+<script src="/static/dashboard-calendar.js?v=20261105-0960a" defer></script>
PATCH_EOF
git apply --check /tmp/0960.patch 2>&1 | tail -30
git apply /tmp/0960.patch 2>&1 | tail -30
git diff --stat | tail -10
```

Expected: three files, 13 insertions and 5 deletions. `--check` fails: STOP.

Commit: `git add -A App && git commit -m "0960 step 1"`.

### Step 2: append the test

Append this block exactly at the end of `App/tests/test_dashboard_calendar_browser.py` (two blank lines before it; nothing else in the file changes):

```python
@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("locale", ["en", "cs"])
@pytest.mark.parametrize("entry", ["dashboard", "cleaning"])
def test_0960_create_actions_label_input_and_cleaning_day_name(
    calendar_workspace, calendar_origin, width, locale, entry
):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(
            browser, calendar_workspace, calendar_origin, width=width,
            locale=locale, touch=width < 768,
        )
        try:
            path = "/cleaning" if entry == "cleaning" else "/"
            page.goto(f"{calendar_origin}{path}?lang={locale}&cal_date=2026-10-01&cal_view=calendar")
            page.wait_for_selector(".cal-week")
            wait_loaded(page)
            day = page.locator('[data-cal-day="2026-10-10"]')
            name = day.get_attribute("aria-label")
            if entry == "cleaning":
                assert name.startswith("Add cleaning" if locale == "en" else "Přidat úklid"), name
                assert "stay" not in name.lower() and "pobyt" not in name.lower(), name
            else:
                assert name.startswith("Add a stay" if locale == "en" else "Přidat pobyt"), name
            day.click(position={"x": 8, "y": 8})
            if page.locator("[data-cal-day-add]").is_visible():
                page.locator("[data-cal-day-add]").click()
            dialog = page.locator("[data-cal-create]")
            dialog.wait_for(state="visible")
            boxes = {}
            for kind in ("stay", "cleaning"):
                dialog.locator(f'[data-cal-type-choice="{kind}"]').click()
                data = page.evaluate("""() => {
                    const dialog = document.querySelector('[data-cal-create]');
                    const read = node => {
                        const box = node.getBoundingClientRect(), css = getComputedStyle(node);
                        return {x: Math.round(box.x - dialog.getBoundingClientRect().x), w: Math.round(box.width), h: Math.round(box.height),
                            bg: css.backgroundColor, border: css.borderTopWidth + css.borderTopStyle, radius: css.borderTopLeftRadius};
                    };
                    const buttons = [...dialog.querySelectorAll('.cal-dialog-actions .btn')].filter(b => b.offsetParent);
                    const filled = [...dialog.querySelectorAll('button.btn')].filter(b => b.offsetParent &&
                        getComputedStyle(b).backgroundColor === getComputedStyle(dialog.querySelector('[data-cal-save]')).backgroundColor);
                    return {cancel: read(dialog.querySelector('.cal-dialog-actions .btn.soft')), save: read(dialog.querySelector('[data-cal-save]')),
                        filled: filled.map(b => b.hasAttribute('data-cal-save')), count: buttons.length,
                        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                        dialogOverflow: dialog.scrollWidth > dialog.clientWidth,
                        label: dialog.querySelector('#cal-label') && dialog.querySelector('#cal-label').offsetParent ? read(dialog.querySelector('#cal-label')) : null,
                        guests: dialog.querySelector('#cal-guests').offsetParent ? read(dialog.querySelector('#cal-guests')) : null};
                }""")
                boxes[kind] = data
                assert data["count"] == 2 and data["filled"] == [True], (kind, data)
                assert data["cancel"]["bg"] != data["save"]["bg"], (kind, data)
                assert data["cancel"]["h"] == data["save"]["h"], (kind, data)
                assert data["cancel"]["x"] < data["save"]["x"], (kind, data)
                assert not data["overflow"] and not data["dialogOverflow"], (kind, data)
                if kind == "stay":
                    assert data["label"]["h"] == data["guests"]["h"], data
                    assert data["label"]["border"] == data["guests"]["border"] == "1pxsolid", data
                    assert data["label"]["radius"] == data["guests"]["radius"] != "0px", data
                    page.locator("#cal-label").focus()
                    label_ring = page.evaluate("() => { const c = getComputedStyle(document.querySelector('#cal-label')); return c.outlineColor + c.outlineWidth + c.outlineStyle; }")
                    page.locator("#cal-guests").focus()
                    guests_ring = page.evaluate("() => { const c = getComputedStyle(document.querySelector('#cal-guests')); return c.outlineColor + c.outlineWidth + c.outlineStyle; }")
                    assert label_ring == guests_ring, (label_ring, guests_ring)
                shot(page, f"0960-{entry}-{kind}-{locale}-{width}")
            assert boxes["stay"]["cancel"]["x"] == boxes["cleaning"]["cancel"]["x"]
            assert boxes["stay"]["cancel"]["w"] == boxes["cleaning"]["cancel"]["w"]
            assert boxes["stay"]["save"]["x"] == boxes["cleaning"]["save"]["x"]
            assert boxes["stay"]["save"]["w"] == boxes["cleaning"]["save"]["w"]
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden")
        finally:
            context.close()
            browser.close()
```

Check: `grep -c "def test_0960" App/tests/test_dashboard_calendar_browser.py` prints 1. Commit: `git add -A App && git commit -m "0960 step 2"`.

### Step 3: regenerate the cache manifest

From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. Expected diff in `tests/static_versions.json`: only the `dashboard-calendar.css` and `dashboard-calendar.js` entries (new sha256, `v` = `20261105-0960a`). Commit: `git add -A App && git commit -m "0960 step 3"`.

## 5. Do not touch

Record-type logic and C01 selected-state CSS from 0958, date logic, overlap rules, creation endpoints, cleaning logic, `host_i18n.py`, any other CSS or template. Hard rules from AGENTS.md: light mode only, no new dependency, no push, merge or deploy.

## 6. Commands

From `App/`, each with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-b02` in front, ending `-rs --tb=short 2>&1 | tail -30`. Zero skipped. One command at a time; the browser files are slow, so use a long timeout or run in the background and read the output file.

1. `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -k "0960 or 0958 or reclamps" -q -x`
   Expected: 26 passed (12 + 12 + 2), 0 skipped.
2. `.venv/bin/python -m pytest tests/test_dashboard_calendar.py tests/test_calendar_*.py tests/test_sample_calendar.py -q -x`
3. `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q -x`
4. `.venv/bin/python -m pytest tests/test_cleaning*.py -q -x`
5. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q -x` (no browser variables needed; expected 16 passed)
6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

A command fails: read the last 30 lines, fix once, rerun. Fails again: STOP.

## 6b. Chromium UX checks (these make the batch pass or fail)

The new test writes screenshots to `/tmp/ubyhost-b02/calendar-0960-<entry>-<kind>-<locale>-<width>.png` (entry dashboard or cleaning, kind stay or cleaning, locale en or cs, width 390, 768, 1280). Open with the Read tool at least these, and say in the report for each what you saw in one sentence: `0960-dashboard-stay-en-390`, `0960-dashboard-cleaning-en-390`, `0960-cleaning-stay-en-390`, `0960-cleaning-cleaning-cs-390`, `0960-dashboard-stay-en-768`, `0960-cleaning-cleaning-cs-768`, `0960-dashboard-stay-en-1280`, `0960-cleaning-cleaning-cs-1280`, `0960-dashboard-stay-cs-1280`. The test already asserts the rest of the 36 combinations (Add stay and Add cleaning, from Dashboard and Cleaning, 390/768/1280, EN and CS). Required in every image:

- Create is the only coral filled button. Cancel is white with a thin grey border.
- Cancel and Create sit on one row at the bottom, Cancel left (96 px wide, 44 px high), Create fills the rest; identical positions in Add stay and Add cleaning.
- The Label input has the same height, 1 px light border, rounded corners and focus ring as Guests and the other inputs.
- No clipped text (CS "Vytvořit pobyt/úklid" fits), no horizontal scrollbar, no overlap, no large empty area under the cleaning form.
- The Cleaning page day cells announce "Add cleaning · <date>" (asserted by the test; it also asserts the Dashboard cells still say "Add a stay").

Any image that fails a bullet: STOP and report with the filename. Never silence or loosen an assertion.

## 7. Acceptance

- [ ] Step 1 applied with `git apply --check` clean; 3 commits `0960 step 1..3`.
- [ ] Commands 1 to 6 all green, 0 skipped.
- [ ] Section 6b screenshots viewed and described, all bullets true.
- [ ] `git diff de537cb3 --stat` lists only the files in section 3.
- [ ] Nothing printed from guest data.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; `git apply --check` fails; a command fails twice; a screenshot fails a 6b bullet; a file outside section 3 needs a change; 25 tool calls or about 50k tokens are reached (write the report as `blocked`, see executor.md); push, merge or deploy would be needed.

## 9. Report

Write `docs/tasks/0960-report.md` (600 tokens at most): `git diff --stat`, each command with its last 5 lines, section 7 ticked, one sentence per viewed screenshot, deviations, questions. Set `Status: review`. Do not push; hand the branch name to the orchestrator.

## Risk list (for the reviewer)

`App/app/static/dashboard-calendar.css` (new block uses `#calendar` for specificity over the `.cleaning-page` and `body.v2` rules), `App/app/static/dashboard-calendar.js` (two aria-label lines, cleaning mode only), `App/app/templates/_dashboard_calendar.html`.

## Owner steps

1. After review, push `codex/0960-b02-calendar-create` and open the PR; merge only with `scripts/merge-pr-on-green.sh`.
