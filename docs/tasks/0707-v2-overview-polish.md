# 0707: v2 Overview polish (resets, banner, tucked extras, bar labels)
Status: todo
Depends on: 0706 commit 39c31a7 | Base commit: task/0706-v2-overview | Branch: task/0707-v2-polish
Executor: Haiku 5.5 | Fits one session: 25 tool calls

## 1. Objective
The v2 Overview (`/`) at 1280 px is close to the mockup but shows browser defaults. Fix them in `App/app/static/app2.css` (and the two template spots named), compare with `/mnt/project-files/ux-redesign/overview/mockup-overview-1280.png`.

## 2. Context (what the screenshot shows, fix each)
1. Links are blue/underlined (account card, nav, buttons, table host name, quiet links). Add base resets: `body.v2 a{color:inherit;text-decoration:none}`; quiet links ink-3 with underline only on hover; `.btn` links keep white/ink text.
2. "Přeskočit na hlavní obsah" skip link is visible at top-left: `.skip-link` visually hidden until `:focus` (position absolute, left -9999px; on focus top 8px left 8px, white card).
3. The practice/test env banner (from `_env_banner.html`, included by base.html) is unstyled text: style its root element in v2 like the mockup `.note` but warn colours (`background:var(--warns);color:var(--warn);border-radius:10px;padding:10px 14px;font-size:13px;margin-bottom:16px`). Find its class with `grep -n 'class=' App/app/templates/_env_banner.html`.
4. The old phone bottom tab bar and the Havel bubble render as raw links at the bottom of the page. In v2 hide the phone tab bar at all widths (the v2 sidebar is the navigation) and hide the Havel launcher bubble (the sidebar has "Pomoc a Havel"); find their root classes in base.html / their includes and add `body.v2 .X{display:none}`.
5. Demo-clear button: style as a quiet link (no border/background, ink-3, 13px, underline on hover, font inherit).
6. Row menu trigger in the Dnes table (`row_menu_begin` button) shows as a default bordered button: make it the mockup's `···` (no border/background, ink-3, letter-spacing .1em); its menu popup needs a white card with shadow (find the menu classes in `_components.html` and give them `position:absolute; background:#fff; border:1px solid var(--line); border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,.08); padding:6px` and items `display:block; padding:8px 12px; border-radius:6px` hover `#f6f6f4`; hidden state must stay hidden — keep whatever `hidden` attribute/class the JS toggles).
7. Calendar bars have no text when the stay has no label. In `_overview_calendar_rows` in `App/app/routes/admin.py` use the label fallback: `event["label"]` or, if empty, the source name (airbnb → "Airbnb", booking → "Booking", else `t('calendar.kind_stay')` / "Pobyt") followed by " · N" guests when guests > 0. Overlapping stays in one property row must not overlap visually: give each bar `grid-row` by lane (simple greedy: first lane whose last end <= start), and the row height grows (`grid-auto-rows:44px`).
8. Dnes "Stav" column is empty for waiting stays: show `.pill.p-warn` with `tp('host.missing', progress.not_registered)` when `progress.not_registered`, `.pill.p-ok` "Hotovo, nahlášeno policii" when reported/not_required (use an existing key if there is one: `grep -n 'nahlášeno policii' App/app/host_i18n.py | head`), `.pill.p-bad` for failed/overdue with the existing failed text.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/dashboard.html` (items 6 class hooks and 8 only), `App/app/routes/admin.py` (item 7 only), `App/app/templates/base.html` (only the app2.css `?v=` → `20261101-0707`), `App/tests/static_versions.json` (`--write`). Screenshot `docs/tasks/screenshots-0707/overview-cs-1280.png` and `-390.png` via `UBYHOST_SHOTS_0701=<abs path> .venv/bin/python -m pytest tests/test_0701_overview_cards_browser.py -k shot` from App/. Report `docs/tasks/0707-report.md`.

## 4. Steps
Items 1-6 (CSS) one commit; item 7 one commit; item 8 one commit; versions + screenshots + report one commit. Look at the screenshot yourself (Read the PNG) and fix anything still showing browser defaults before the last commit.

## 5. Do not touch
Tests (another brief updates them), JS, other templates.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_privacy_first.py -q 2>&1 | tail -3`; repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py 2>&1 | tail -1`.

## 7. Acceptance
Screenshot at 1280 shows no underlined/blue links, no skip link, styled banner, no raw bottom bar, labelled bars, Stav pills.

## 8. Stop and ask
If hiding the phone tab bar or Havel bubble needs a JS change, stop.

## 9. Report
`docs/tasks/0707-report.md`: status, what changed per item, screenshot paths.
