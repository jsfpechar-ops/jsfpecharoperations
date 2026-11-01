# 0729 brief: phone v2 Today (Airbnb style) and the shared phone v2 parts

Status: todo
Executor: Haiku 5.5, alone, in a worktree of branch `claude/project-thread-50hyv5`.

## 1. Objective

Below 1024 px the Overview page (`/`) looks like `docs/design/mockup/ubyhost-phone-v2.html`, screens `dnes` and `empty`:
a Today/Upcoming pill switch, one centred headline, need cards (tone label, bold name, one full-width button),
a centred "TODAY" label and centred stay cards. Nothing else on phone. Desktop (1024 px and wider) does not change.
The shared phone card and section label change for every v2 page (Josef approved the style app-wide on 2026-11-01 21:15).

## 2. Context

- Approved design: `docs/design/mockup/ubyhost-phone-v2.html` (already committed by the orchestrator; do not edit it).
- v2 pages opt in with `{% set v2 = true %}`; phone rules live in `App/app/static/app2.css` inside `@media (max-width:1023px)`.
- `.ph-only` is hidden at 1024 px and wider; `.ph-hide` is hidden below 1024 px.
- Shared mockup test: `App/tests/v2_mockup.py` (PAGES, BOX_OVERRIDES) and `App/tests/test_0710_v2_mockup_match_browser.py`.
- Standing rule for this brief: you may update test assertions about the **phone layout (below 1024 px) of `/`** that this brief changes on purpose (removed top row, removed "Potřebuje vás" heading and badge, removed calendar link, new card sizes). Change nothing else in tests; if a desktop assertion fails, stop and ask.

## 3. Files

- `App/app/templates/dashboard.html`
- `App/app/routes/admin.py` (only the `dashboard` function's context dict)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`
- `App/app/static/app2.css`
- `App/app/templates/base.html` (css cache key only) and `App/tests/static_versions.json` (rewritten by the script)
- `docs/design/catalog.json`
- `App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py`
- tests listed in step 9 only when the standing rule allows it
- new: `App/tests/test_0729_phone_today_geometry_browser.py`
- new: `docs/tasks/0729-phone-v2-today-report.md`, `docs/tasks/screenshots-0729/`

## 4. Steps

1. `App/app/routes/admin.py`, in `dashboard()`, in the context dict right after the `"today_rows": [ ... ],` entry, add:
   ```python
            # 0729: phone "All done" line names the next arrival after today.
            "next_arrival": min(
                (row["reservation"] for row in rows if str(row["reservation"]["date_from"])[:10] > today.isoformat()),
                key=lambda r: str(r["date_from"])[:10],
                default=None,
            ),
   ```
2. i18n. In `App/app/host_i18n.py` add after the line `"dashboard.today.nights.few": ...` in the **English** dict:
   ```python
        "dashboard.ph.upcoming": "Upcoming",
        "dashboard.ph.need": "%(count)s things need you today",
        "dashboard.ph.need.one": "1 thing needs you today",
        "dashboard.ph.need.few": "%(count)s things need you today",
        "dashboard.ph.done": "All done. Nothing needs you today.",
        "dashboard.ph.next": "Next arrival: %(when)s, %(place)s",
   ```
   and after `"dashboard.today.nights.few": "%(count)s noci",` in the **Czech** dict:
   ```python
        "dashboard.ph.upcoming": "Nadcházející",
        "dashboard.ph.need": "Dnes na vás čeká %(count)s věcí",
        "dashboard.ph.need.one": "Dnes na vás čeká 1 věc",
        "dashboard.ph.need.few": "Dnes na vás čekají %(count)s věci",
        "dashboard.ph.done": "Hotovo. Dnes na vás nic nečeká.",
        "dashboard.ph.next": "Další příjezd: %(when)s, %(place)s",
   ```
   In `App/app/host_vi_i18n.py` add after the `"dashboard.today.nights.few"` line:
   ```python
    "dashboard.ph.upcoming": "Sắp tới",
    "dashboard.ph.need": "%(count)s việc cần bạn hôm nay",
    "dashboard.ph.need.one": "1 việc cần bạn hôm nay",
    "dashboard.ph.need.few": "%(count)s việc cần bạn hôm nay",
    "dashboard.ph.done": "Xong hết. Hôm nay không có việc gì.",
    "dashboard.ph.next": "Khách đến tiếp theo: %(when)s, %(place)s",
   ```
   If `dashboard.today.nights.many` exists in a dict, also add `"dashboard.ph.need.many"` there with the same text as the base key.
3. `App/app/templates/dashboard.html`:
   a. Replace the whole line `  <div class="top ov-top"><span></span><a class="round" href="/reservations?new=1" aria-label="{{ t('stays.add_stay') }}">{{ icon('plus', 20) }}</a></div>` with:
   ```jinja
  {#- 0729: phone v2 top (Airbnb style): Today/Upcoming switch and one headline. -#}
  <div class="ph-top ph-only">
    <nav class="seg" aria-label="{{ t('dashboard.title') }}"><a class="on" href="/" aria-current="page">{{ t('nav.today') }}</a><a href="/reservations">{{ t('dashboard.ph.upcoming') }}</a></nav>
    {% if ny_lines %}<h1 class="hl">{{ tp('dashboard.ph.need', ny_lines | length) }}</h1>
    {% else %}<h1 class="hl done">{{ t('dashboard.ph.done') }}</h1>{% if next_arrival %}<p class="hl-sub">{{ t('dashboard.ph.next', when=(next_arrival.date_from | string)[:10] | date_long(lang), place=next_arrival.internal_name) }}</p>{% endif %}{% endif %}
  </div>
   ```
   b. `<div class="head ov-head"><div>` becomes `<div class="head ov-head ph-hide"><div>`.
   c. `<h2 id="needs-you-title" class="sec">{{ t('needs_you.title') }}{% if ny_lines %} <span class="badge ph-only">{{ ny_lines | length }}</span>{% endif %}</h2>` becomes `<h2 id="needs-you-title" class="sec ph-hide">{{ t('needs_you.title') }}</h2>`.
   d. `<div class="card needs-you-calm allgood">` becomes `<div class="card needs-you-calm allgood ph-hide">`.
   e. `<div class="quiet ov-month" data-dashboard-month>` becomes `<div class="quiet ov-month ph-hide" data-dashboard-month>`.
   f. `<h2 class="sec">{{ t('dashboard.today.title') }} <a class="ph-only" href="/?cal_view=calendar">{{ t('calendar.calendar') }}</a></h2>` becomes `<h2 class="sec{{ ' ph-hide' if not today_rows }}">{{ t('dashboard.today.title') }}</h2>`.
4. `App/app/static/app2.css`, existing lines (exact text, inside the `/* 0718 phone classes ... */` block):
   a. Replace `body.v2 h2.sec{font-size:20px;font-weight:800;letter-spacing:-.015em;margin:28px 0 12px;display:flex;justify-content:space-between;align-items:baseline}` **in the 0718 block only** (the one indented under `@media (max-width:1023px){` right after `body.v2 .sub,body.v2 .head .sub`) with
      `body.v2 h2.sec{font-size:13px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em;margin:26px 0 12px;display:flex;justify-content:center;align-items:baseline}`.
      Leave the desktop `h2.sec` rule near line 230 alone if it is outside the phone media query (check with `grep -n "h2.sec{" App/app/static/app2.css` and read 3 lines above each hit to see its media query).
   b. Replace `body.v2 .card{margin:0 0 12px;background:#fff;border-radius:18px;padding:18px;box-shadow:0 1px 2px rgba(0,0,0,.05),0 6px 20px rgba(0,0,0,.07);border:1px solid #f1f0ec}` with
      `body.v2 .card{margin:0 0 16px;background:#fff;border-radius:24px;padding:22px;box-shadow:0 6px 24px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.03);border:0}`.
   c. Replace `body.v2 .need b{display:block;font-size:17px;line-height:1.3}body.v2 .need small{display:block;color:var(--ink3);font-size:14px;margin-top:3px}` with
      `body.v2 .need .t{display:block;font-size:13px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;line-height:1.4}body.v2 .need[data-tone="red"] .t{color:var(--acc-text)}body.v2 .need[data-tone="amber"] .t{color:var(--warn)}body.v2 .need small{display:block;font-size:20px;font-weight:800;letter-spacing:-.01em;color:var(--ink);line-height:1.3;margin-top:2px}body.v2 .need .ic{display:none}`.
   d. In the line `body.v2 .ov-top,body.v2 .ph-only{display:none}` (inside `@media (min-width:1024px)`) delete `body.v2 .ov-top,` so it reads `body.v2 .ph-only{display:none}`.
   e. Delete the line `  body.v2 .ov-head > .btn{display:none}` (0719 block; `.ov-head` is now hidden as a whole on phone).
   f. Replace `@media (max-width:1023px){body.v2 h2.sec a.ph-only{display:inline-flex;align-items:center;min-height:44px}body.v2 .big{margin:2px 0 4px}}` with `@media (max-width:1023px){body.v2 .big{margin:2px 0 4px}}`.
   g. In `@media (max-width:1023px){body.v2 .ui-body:has(> .ov-month) > :not(h2.sec){margin-top:0;margin-bottom:0}body.v2 #needs-action .todo{gap:0}body.v2 #needs-action .needs-you-card-item{margin-bottom:12px}body.v2 details.needs-you-more{margin:0}}` change `margin-bottom:12px` to `margin-bottom:16px`.
   h. Append at the very end of the file:
   ```css
/* 0729 phone v2 (Airbnb style, approved 2026-11-01 21:15): shared phone parts; values from docs/design/mockup/ubyhost-phone-v2.html */
@media (max-width:1023px){
  body.v2 .ph-top{padding-top:8px}
  body.v2 .seg{display:flex;gap:10px;justify-content:center;margin:0 0 28px}
  body.v2 .seg a{display:inline-flex;align-items:center;min-height:44px;padding:0 20px;border-radius:999px;background:#f4f3ef;color:var(--ink);font-weight:600;font-size:15px;text-decoration:none}
  body.v2 .seg a.on{background:var(--ink);color:#fff;box-shadow:0 4px 12px rgba(0,0,0,.18)}
  body.v2 .hl{font-size:30px;line-height:1.15;font-weight:800;letter-spacing:-.02em;text-align:center;margin:0 8px 28px}
  body.v2 .hl.done{margin-top:120px}
  body.v2 .hl-sub{text-align:center;color:var(--ink3);font-size:16px;margin:-16px 0 28px}
  body.v2 .needs-you-actions{margin-top:14px}
  body.v2 .hs .card{align-items:center;text-align:center;padding:26px 22px 28px;gap:0}
  body.v2 .hs .kind{font-size:15px;font-weight:600;text-transform:none;letter-spacing:0}
  body.v2 .hs .who{flex-direction:column;align-items:center;gap:0}
  body.v2 .hs .av{width:72px;height:72px;font-size:26px;border:3px solid #fff;margin:18px 0 16px}
  body.v2 .hs .nm{font-size:22px}
  body.v2 .hs .meta{font-size:15px;margin-top:4px}
  body.v2 .hs .pill{margin-top:14px}
}
   ```
5. Cache key: in `App/app/templates/base.html` change the app2.css key `20261101-0728c` (or whatever `app2.css?v=` currently shows) to `20261101-0729`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
6. `docs/design/catalog.json`: add these to the `"classes"` list (keep the list's existing order style; append at the end): `"ph-top"`, `"seg"`, `"hl"`, `"hl-sub"`, `"done"`. If `class_notes` needs a description for new classes (run `python3 scripts/design_lint.py | tail -20` to see), add one-line notes: ph-top "phone v2 top block (0729)", seg "phone v2 pill switch", hl "phone v2 centred headline", hl-sub "line under the phone headline", done "headline state when nothing needs the host".
7. `App/tests/v2_mockup.py`:
   a. Under `PHONE_MOCKUP = ...` add `PHONE_MOCKUP_V2 = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-phone-v2.html"`.
   b. Change `def phone_url() -> str:` / `return PHONE_MOCKUP.resolve().as_uri()` to `def phone_url(mockup: Path = PHONE_MOCKUP) -> str:` / `return Path(mockup).resolve().as_uri()`.
   c. In the `overview` PAGES entry add `"phone_mockup": PHONE_MOCKUP_V2,` and set `"phone_selectors"` to:
      `[".tabs", ".tab", ".tab.on", ".seg a.on", ".hl", "h2.sec", ".card.need", ".need .t", ".need small", ".card.need .btn", ".hs .card", ".kind", ".av", ".nm", ".meta", ".hs .pill"]`.
      In its `missing_ok`, rename the keys `".need b"` to `".need .t"`, delete `".need .ic"`, and add `"h2.sec": "the Today label shows only when a stay arrives or leaves today"`.
   d. In `BOX_OVERRIDES` delete every key that starts with `.card.need`, `.need b`, `.need small`, `.hs .card`, `.kind`, `.nm`, `.meta`, `.hs .pill`, `.head h1`, `.head .sub`, `h2.sec`. Keep the `.card.me` and `.big` keys (the Menu brief 0735 handles them).
8. `App/tests/test_0710_v2_mockup_match_browser.py`: change `def _open_phone(browser, key, width):` to `def _open_phone(browser, key, width, mockup=PHONE_MOCKUP):` and inside it `page.goto(phone_url())` to `page.goto(phone_url(mockup))`. At every call of `_open_phone(` pass `spec.get("phone_mockup", PHONE_MOCKUP)` as the 4th argument. Add `PHONE_MOCKUP` to the import from `v2_mockup` if it is not imported.
9. Run (from `App/`):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -k "overview" 2>&1 | tail -30`
   For each **box** failure (width/height) on `.card.need`, `.need .t`, `.need small`, `.hs .card`, `.nm`, `.meta`, `.hs .pill`, `.kind` at 320 or 390: these are text-dependent (fixture copy is longer than the mockup's). Add a `"selector@width": {"height": "<app value>"}` entry to BOX_OVERRIDES (also `"width"` only for `.hs .pill`, `.nm`, `.meta`, `.kind`, whose width follows the text) under one comment line `# text-dependent: fixture copy vs phone v2 mockup demo copy (0729)`. Any **style** failure (font-size, color, radius, padding, shadow) means the CSS in step 4 was not applied: fix the CSS, never add an override for it. A `.hs .card` width failure: a lone card must be the full row (350 px at 390, 280 px at 320); add those widths only if the app shows exactly them.
10. New file `App/tests/test_0729_phone_today_geometry_browser.py`, modelled on `App/tests/test_0728_menu_geometry_browser.py` (copy its fixtures, login and browser setup exactly). For widths 320, 360, 390, 768 open `/?lang=en` and assert:
    - `.seg` is visible, centred (left gap and right gap to the viewport differ by at most 2 px), each `.seg a` is at least 44 px tall;
    - `.hl` is visible, its text is centred (`text-align` is `center`), font-size 30px, and it does not overflow the viewport (`right <= innerWidth`);
    - `.ov-head`, `.ov-month`, `#needs-you-title` are not visible; no element with class `ov-top` exists;
    - every visible `.card.need` has border-radius 24px, its `.btn` spans the card's inner width (btn width >= card width − 2×22 − 2) and is at least 44 px tall; `.need .ic` is not visible;
    - if `.hs .card` exists: it is centred in the row, its `.av` is 72×72, and the card does not overflow the viewport;
    - no horizontal page scroll (`document.documentElement.scrollWidth <= innerWidth`);
    - nothing overlaps the tab bar: the last visible element of `main` ends above `.tabs` top when scrolled to the bottom (scroll to bottom first);
    - at 1280: `.ph-top` is not visible and `.ov-head` is visible (desktop unchanged).
    Add one test for the empty state if the fixture lets you clear the needs-you lines easily (look for an existing test that renders `/` with no needs-you lines, e.g. grep `needs_you.calm` in tests); if not, skip it and say so in the report.
11. Run the tests from step 12. Then take screenshots: `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -k screenshots 2>&1 | tail -5` and copy the overview 390 and 320 phone shots into `docs/tasks/screenshots-0729/` (`overview-390.png`, `overview-320.png`). Restore any other tracked PNGs the run rewrote: `git status --short | grep '\.png$'` then `git restore <those paths>` (keep only the new screenshots-0729 files).
12. Commit: `git add -A App docs && git commit -m "0729: phone v2 Today (Airbnb style) and shared phone parts"` (with the Co-Authored-By trailer from the orchestrator's instructions). Do not push.

## 5. Do not touch

- Desktop rules (anything inside `@media (min-width:1024px)` except step 4d), `_shell_v2.html`, the tab bar, `menu.html` (brief 0735), `docs/design/mockup/*.html`.
- Other pages' templates and CSS. No new dependencies. No JS.

## 6. Commands

From `App/` (browser tests need the env vars):
```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0729_phone_today_geometry_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_host_wide_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py tests/test_needs_you_0240.py -q --tb=short -rs 2>&1 | tail -30
.venv/bin/python -m ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
```
From the repo root: `python3 scripts/design_lint.py | tail -5` and `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

- [ ] At 320, 360, 390 and 768 the Overview shows only: pill switch, headline, need cards (2, then "Show N more"), "TODAY" label and stay cards; at 1280 it looks as before.
- [ ] Every listed test passes with 0 skipped; the new geometry test exists and passes.
- [ ] No BOX_OVERRIDES entry for a style property; every new override is height (or width for text-sized elements) with the 0729 comment.
- [ ] design lint and context lint OK; css key bumped.

## 8. Stop and ask

- A desktop (1024 px or wider) assertion fails.
- A test outside step 12's list fails because of this change.
- You would need to edit a mockup file, add a dependency, or change the tab bar.
- You reach 25 tool calls without the tests green: commit what you have and report.

## 9. Report

Write `docs/tasks/0729-phone-v2-today-report.md` with: Status line, changed files, last lines of each command, every BOX_OVERRIDES entry you added with its measured value, deviations, and the two screenshot paths.
