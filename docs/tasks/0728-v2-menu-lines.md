# 0728: phone Menu with live lines and a proper log-out row
Status: todo
Depends on: 0727 | Branch: task/0727-v2-lone-stay-card (worktree /tmp/wt0727, continue there after 0727)
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Owner, 20:03: "the menu phone looks kinda boring, why is there a log out like that". Give every Menu row its small second line as in the approved phone mockup (`docs/design/mockup/ubyhost-phone-v1.html`, `data-s="menu"`: `<span class="t"><b>..</b><small>..</small></span>`), a live line for Cleaning, and turn the bare "Log out" link into a proper row in its own card at the bottom.

## 2. Context (orchestrator, decided)
- Template `App/app/templates/menu.html`; route `menu_view` in `App/app/routes/admin.py` line ~4564 (renders with `apartments` only).
- Second lines (new i18n keys in `App/app/host_i18n.py` en + cs and `App/app/host_vi_i18n.py` vi, next to the existing `nav.*` keys):
  - `menu.sub.cleaning_live` = en "{today} today, {week} this week" / cs "{today} dnes, {week} tento týden" / vi "{today} hôm nay, {week} tuần này"; `menu.sub.cleaning_none` = en "Nothing planned this week" / cs "Tento týden nic" / vi "Tuần này không có lịch"
  - `menu.sub.stay_fees` = en "Monthly report for the town" / cs "Měsíční hlášení pro obec" / vi "Báo cáo hằng tháng cho thành phố"
  - `menu.sub.payments` = en "Payment requests, invoices" / cs "Žádosti o platbu, faktury" / vi "Yêu cầu thanh toán, hóa đơn"
  - `menu.sub.settings` = en "Company, notifications, plan, privacy" / cs "Firma, upozornění, tarif, soukromí" / vi "Công ty, thông báo, gói, quyền riêng tư"
  - `menu.sub.guide` = en "Ask anything" / cs "Zeptejte se na cokoli" / vi "Hỏi bất cứ điều gì"
  - `menu.sub.admin` = en "Workspaces and support" / cs "Účty a podpora" / vi "Tài khoản và hỗ trợ"
- Cleaning live count: in `menu_view`, `from app import cleaning, claim`; `today = claim.prague_today()`; `events = cleaning.schedule(access.owner_id(request), today, today + timedelta(days=6))["events"]`. First print one event's keys in a quick python check to confirm the cleaning kind value and the start field (expected `kind == "cleaning"`, `start` ISO date); count today's (`start[:10] == today.isoformat()`) and the week's. Pass `cleaning_today`, `cleaning_week` to the template. Wrap in try/except Exception -> None, None so the menu never fails because of cleaning; the template then shows no line for Cleaning.
- Badge: when `cleaning_today` > 0, show `<span class="badge">{{ cleaning_today }}</span>` before the chevron (mockup `.badge`, already styled by the phone shared block; grep `.badge` in app2.css, and only add a rule if none applies inside `.row`).
- Log out: replace the `<form class="menu-logout">` block with
  `<form method="post" action="/logout" class="list menu-logout"><button class="row" type="submit"><span class="ic" aria-hidden="true">{{ icon('log-out', 22) }}</span><span class="t"><b>{{ t('nav.logout') }}</b></span></button></form>`
  (check `log-out` exists in `_icons.html`; if not, use the closest existing icon name and say which). In app2.css phone block add: `body.v2 .menu-logout{margin-top:16px}body.v2 .menu-logout .row{width:100%;border:0;background:none;font:inherit;text-align:left;cursor:pointer}body.v2 .menu-logout .ic{background:#efefeb;color:var(--ink2)}` — reuse the existing `.list`/`.row` card look; the grey icon box marks it as not a feature row. No chevron.
- Desktop: /menu is a phone page; desktop look not in scope.
- Design lint: any new class (`menu-logout` already exists) goes in `docs/design/catalog.json`.

## 3. Files
`App/app/templates/menu.html`, `App/app/routes/admin.py` (menu_view only, <= 15 lines), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/tests/test_0728_menu_geometry_browser.py`, `App/tests/v2_mockup.py` (only if a menu selector needs a `missing_ok`/override), `docs/design/catalog.json` if needed, screenshot `docs/tasks/screenshots-0728/menu-390.png`, report `docs/tasks/0728-report.md`.

## 4. Steps
1. i18n keys (en, cs, vi). Commit.
2. Route counts + template second lines + badge. Run `tests/test_0710_v2_mockup_match_browser.py -k menu` and any test that greps menu.html (`grep -ln "menu" tests/test_*menu*.py tests/test_0718*.py 2>/dev/null`). Commit.
3. Log-out row + CSS. Key to `20261101-0728`, `tests/test_static_versions.py --write`. Commit.
4. Geometry test (owner 20:05: rigorous geometry and design checks). Add `App/tests/test_0728_menu_geometry_browser.py` using the fixtures of `tests/test_0710_v2_mockup_match_browser.py` (import them the same way that file does). At widths 320, 360, 390 and 768 on /menu assert: no horizontal overflow (`document.documentElement.scrollWidth <= innerWidth`); every `.menu-list .row` and the log-out row is >= 56 px tall and their left and right edges match within 1 px; each `.row .t small` is one line (height <= its line-height + 1) and does not overlap the badge or chevron (right edge of `.t` <= left edge of the next sibling); the log-out card's top is >= 12 px below the last menu row's bottom; the bottom of the log-out card sits above the tab bar top when scrolled to the end; all text contrast is unchanged (reuse the colour checks already in v2_mockup if a helper exists, else skip contrast). Run it, 0 skipped. Commit.
5. Screenshot at 390 of /menu (the 0710 screenshot mode writes menu shots; copy the menu 390 one to docs/tasks/screenshots-0728/menu-390.png), Read it. Restore other PNGs (`git restore --pathspec-from-file`), remove untracked PNGs outside screenshots-0728. Report, Status: done. Commit (step 5).

## 5. Do not touch
`app.js`, other routes, other templates, the tab bar.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py <menu tests found in step 2> -q --tb=line -rs 2>&1 | tail -12`; ruff `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`; repo root `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Every row has a second line; Cleaning shows live counts; Log out is a row in its own card with a grey icon; tests and lints pass, 0 skipped.

## 8. Stop and ask
Stop on the Cleaning count (show no line, keep going) if `cleaning.schedule` does not return events with a kind and a start date.

## 9. Report
`docs/tasks/0728-report.md`: changes, the event keys you found, test tails, screenshot path.
