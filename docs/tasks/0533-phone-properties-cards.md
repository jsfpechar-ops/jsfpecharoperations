# 0533: Nemovitosti on the phone, 1:1 with the approved phone mockup
Status: todo (start only after 0718, the shared phone shell, is merged into this branch)
Depends on: 0532 (v2 list, this branch), 0718 (phone shell and phone checks in the 0710 test, from claude/project-thread-50hyv5) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Owner decision 2026-11-01 16:57: the phone layout matches the approved phone mockup `docs/design/mockup/ubyhost-phone-v1.html` 1:1, built from its own markup and CSS. Below 768 px, `/apartments` shows the mockup screen `data-s="nemovitosti"`: one `.card.prop` per property (coloured `.cover` tile with initials, `.in` with name, address and the `.setup` chips); tapping a card opens the property. The computer table (0532) stays unchanged from 768 px up.

## 2. Context
- Mockup screen: `grep -n 'data-s="nemovitosti"' docs/design/mockup/ubyhost-phone-v1.html`, read that section (about 22 lines) and the CSS rules `.prop`, `.cover`, `.cover .ini`, `.cover .cap`, `.prop .in`, `.st`, `.st:before`, `.st.g/.r/.n` (lines ~110-118).
- Shared phone classes come from 0718 (do not copy them): `.top`, `.round`, `.big`, `.sub`, phone `.card`, `.tabs`/`.tab`. `.head h1` already gets the `.big` size on phone; keep the 0532 `.head` and do not add a second title. Read the 0718 block in `App/app/static/app2.css` (`grep -n 0718`) before writing CSS.
- Markup: after the 0532 `.card.props-card` table in `App/app/templates/apartments.html`, add `<div class="props-phone">` with, per row, `<a class="card prop" href="/apartments/{{ apartment.id }}">` containing `<div class="cover" style="background:{{ gradient }}"><span class="ini">{{ initials }}</span></div><div class="in"><b>{{ name }}</b><small>{{ address_text }}</small><div class="setup">` and one `<span class="st g|r|n" data-setup-chip data-state>` per chip (spans, not links: the whole card is the link, as in the mockup; keep the sr-only state text) `</div></div></a>`.
- Initials: first letter of the first two words of the name, upper case (one letter if one word). Gradient: pick by `apartment.id % 3` from the mockup's three: `linear-gradient(135deg,#d0452d,#e9836f)`, `linear-gradient(135deg,#3f6f8f,#7fa8c2)`, `linear-gradient(135deg,#5c7a4f,#9db58c)`. Do it in the template (a Jinja `set`), no route change.
- No `.cap` ("4 hosté"): the app stores no guest capacity. This is a known departure; note it in the report.
- Visibility: below 768 px hide `.props-card`, show `.props-phone`; from 768 px hide `.props-phone`. The `.card` is a link: `display:block;text-decoration:none;color:inherit`.
- Phone chips use the mockup values (13px, 700, padding 5px 10px, dot `:before`, `.st.r` uses `--accs`/`--acc2` if tokens.css has them, else the values from the mockup `:root`). Scope them `body.v2 .props-phone .st` so the computer chips stay as 0532.
- Shared test: `App/tests/v2_mockup.py` `properties` entry: add `phone_view: "nemovitosti"` and `phone_selectors` `[".big, .head h1", ".card.prop", ".cover", ".cover .ini", ".prop .in b", ".prop .in small", ".props-phone .st.g", ".props-phone .st.r"]` (adjust names to the 0718 format; read how the overview entry does it). Do not change comparison logic.

## 3. Files
Edit `App/app/templates/apartments.html`, `App/app/static/app2.css` (0532/0533 block only; bump the `?v=` key in `base.html`), `App/tests/static_versions.json` (via `--write`), `App/tests/v2_mockup.py` (properties entry only), `App/tests/test_0530_properties_chips.py` (add: phone cards render one `a.card.prop` per property with four chips and the right href). Screenshots `docs/tasks/screenshots-0533/`. Report `docs/tasks/0533-report.md`.

## 4. Steps
1. Markup. Commit `0533 step 1`.
2. CSS, key bump, `--write`. Commit `0533 step 2`.
3. Test entry and the 0530 test addition; run until green. Commit `0533 step 3`.
4. Section 6. Commit `0533 step 4`.
5. Screenshots: app `/apartments?lang=cs` and mockup screen `nemovitosti` at 390 (and 320), side by side as separate PNGs `app-390.png`, `mockup-390.png`, `app-320.png`, `mockup-320.png`. Commit `0533 step 5`.

## 5. Do not touch
Any JS file, the route, the shared 0718 rules, the computer table layout, the property page, the wizard, other templates. No new dependency.

## 6. Commands (from `App/`; browser tests SKIP SILENTLY without the env vars)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then the two groups in brief 0532 section 6, then from the repo root `python3 scripts/design_lint.py | tail -3` (add new classes `prop`, `cover`, `ini`, `in`, `props-phone` to the allow-list the way 0532 did for apartments.html) and `python3 scripts/context_lint.py 2>&1 | tail -3`. Restore tracked PNGs a run rewrites outside `screenshots-0533/`.

## 7. Acceptance
All pass, 0 skipped. The 0710 test passes for `properties` at all widths including the strict phone check at 320 and 390. Only section 3 files plus section 8 tests changed.

## 8. Stop and ask
Standing rule: a test that finds `/apartments` rows with a selector that only matches the table may add `.props-phone .card.prop` for phone widths (selector only; list each). Stop if a test about another page fails, or if a 0718 shared rule seems wrong for this page.

## 9. Report
`docs/tasks/0533-report.md`: status, tails, diff stat, screenshot paths, deviations (no `.cap`). Stage files by name, never `git add -A`; never commit `App/.venv`. Do not push.
