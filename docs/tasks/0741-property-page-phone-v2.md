# 0741 brief: phone v2 property page (Airbnb style)

Status: todo (run after 0740 is committed on the same branch)
Executor: Haiku 5.5, alone, on branch `claude/project-thread-b9cg54` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push).

## 1. Objective

Below 1024 px, `/apartments/<id>` looks like screen `nemovitost` of `docs/design/mockup/ubyhost-phone-v2.html`:
round soft back button, the property name centred (30 px), the address centred under it, the guest link card
(small-caps "Guest link" label, link in bold, a PIN row with a divider and the PIN large on the right, then
"Copy link" as the coral button and "Copy PIN" as the outlined button, stacked), centred "SETTINGS" label, and the
section rows (dot, title, one grey state line, chevron) with no divider lines. Opening a row still opens the section in place:
keep every `details.prop-sec`, its `id`, `open` logic and `initPropertyPage` in app.js untouched. Markup changes: none
expected (CSS only); desktop (>= 1024 px) must not change.

## 2. Context

- Design: `docs/design/mockup/ubyhost-phone-v2.html` (its `/* property page (0741)` CSS block and the `data-s="nemovitost"` section; do not edit it).
- Template: `App/app/templates/apartment_form.html` (`.prop-phone-top`, `h1.big`, `.prop-phone-sub`, `.guest-card`), `App/app/templates/_property_editor.html` (`h2.sec.prop-phone-only`, `details.prop-sec > summary`).
- CSS: `App/app/static/app2.css` ~lines 717-765 (0541/0542 phone property rules: `.prop-phone-top`, `.prop-phone-sub`, `.guest-card`, `.prop-sec > summary`) and line ~593 (`.guest-btns`).
- Standing rule for tests: you may change phone-only (below 1024 px) assertions about the property page header, guest card and summary rows in `App/tests/test_0541_property_page_phone_browser.py`, `test_0534_property_page_v2.py` and the `property` entry of `App/tests/v2_mockup.py`. Change no desktop assertion and no other test; if another test fails, stop and write it in the report.

## 3. Steps

1. Read app2.css lines 715-770 and 590-595. Edit the existing phone rules in place (do not append a second competing block) so that below 1024 px:
   - `.prop-phone-top`: `display:flex;padding:8px 0 0;margin-bottom:12px`; its `.round`: 44×44, `border-radius:50%`, `background:#f4f3ef`, grid-centred icon.
   - `.prop-phone-top ~ h1.big` (only on this page): `font-size:30px;line-height:1.15;font-weight:800;letter-spacing:-.02em;text-align:center;margin:0 8px 6px`.
   - `.prop-phone-sub`: `text-align:center;color:var(--ink3);font-size:16px;margin:0 0 24px`.
   - `.guest-card`: the shared phone card (radius 24, ring shadow, padding 22px, no border; check it already gets them from the 0718 `.card` rule), `display:block`.
     `.guest-card b` (the title): `display:block;font-size:13px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em`.
     `.guest-card .sub`: `font-size:17px;font-weight:700;color:var(--ink);margin:6px 0 14px;overflow-wrap:anywhere`.
     `.guest-pin`: `display:flex;align-items:baseline;justify-content:space-between;border-top:1px solid var(--line);padding-top:14px;margin-bottom:16px`; `.guest-pin-label` 15px ink3; `.guest-pin-value` `font-size:22px;font-weight:800;letter-spacing:.12em`.
     `.guest-btns`: `display:flex;flex-direction:column;gap:10px`; both buttons full width, `min-height:50px;border-radius:12px;font-size:16px;font-weight:700`.
     First button (copy link, the direct `.guest-btns > .copy-btn`): coral filled (`background:var(--acc);color:#fff;border:0`).
     PIN button (`.guest-pin-copy .copy-btn`): white, `color:var(--ink);border:1.5px solid var(--ink)`. Replace the 0542 rule that forced both white rather than adding an override on top.
     The copied-state check icon must stay visible on both (white on coral: use `currentColor`).
   - `.prop-sec > summary`: `grid-template-columns:10px minmax(0,1fr) 20px;column-gap:16px;min-height:64px;padding:12px 0;border-bottom:0`;
     `summary > div b` `font-size:17px;font-weight:600;line-height:1.3`; `.sec-state` `display:block;color:var(--ink3);font-size:14px;line-height:1.35`; `.dot` 10×10.
2. New classes, if any, go in `docs/design/catalog.json`; run `python3 scripts/design_lint.py 2>&1 | tail -5` from the repo root.
3. Cache key: set the app2.css `?v=` in `App/app/templates/base.html` to `20261102-0741`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
4. `App/tests/v2_mockup.py`, `property` entry: add `"phone_mockup": PHONE_MOCKUP_V2,`; set `"phone_selectors"` to
   `[".tabs", ".tab.on", ".prop-phone-top .round", ".big, .head h1", ".prop-phone-sub", ".guest-card", ".guest-card b", ".guest-card .sub", ".guest-pin-value", ".guest-btns .btn", "h2.sec", ".prop-sec > summary", ".prop-sec summary b", ".sec-state", ".dot"]`.
   Add `missing_ok` entries for `.guest-pin-value` and `.prop-phone-sub` only if the demo property has no PIN / no address (say which in the report).
5. Tests (from `App/`; do NOT reinstall playwright, the venv pins 1.63.0 to match /opt/pw-browsers):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "property" -q --tb=short -x 2>&1 | tail -30`
   Box failures that follow text length get a `"selector@width"` BOX_OVERRIDES entry with the app value under `# text-dependent: app copy vs phone v2 mockup demo copy (0741)`. Style failures: fix the CSS, never override a style.
   Then: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0541_property_page_phone_browser.py tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_host_property_controls_browser.py tests/test_host_properties_navigation.py tests/test_property_form_save.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (0 skipped),
   and from the repo root `python3 scripts/context_lint.py 2>&1 | tail -5`.
6. Commit (do not push): `0741: phone v2 property page (Airbnb style)` ending with
   ```
   Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
   ```
7. Report `docs/tasks/0741-report.md`: changed files, command tails, overrides added, deviations. Commit it with the work.
