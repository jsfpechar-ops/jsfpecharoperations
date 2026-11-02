# 0789a: /settings index + group sub-pages (part A of 0789)

Status: todo. Executor: Haiku 5.5, alone, branch `claude/project-thread-umes84`. Parent brief: 0789 (read section 1 for the look; refs in /mnt/project-files/settings-area/airbnb-ref/). Same layout at 390, 768 and 1280.

## Approach (decided by the orchestrator; Python change authorised for exactly these items)

1. `App/app/routes/admin.py`: move the body of `settings_view` into `_settings_context(request) -> dict` (no logic change). `/settings` renders `settings.html` with `group=None`. Add one GET route per group, registered explicitly (no `{group}` path parameter, because `/settings/archived` lives in `exports.py`): `for g in SETTINGS_GROUPS: router.add_api_route(f"/settings/{g}", ..., methods=["GET"])`, each rendering `settings.html` with `group=g`, same login guard.
   `SETTINGS_GROUPS = ("account", "security", "phone", "data", "technical", "help")`.
2. `settings.html`: when `group` is None, render only the index (see 3). When set, render the back header (back link to `/settings`, big h1 = the group's title) and only that group's existing sections, unchanged:
   - account: `#settings-account`
   - security: `#settings-security`
   - phone: `#settings-phone`
   - data: `#settings-archive`, `#settings-retention`, `#settings-data`, `#settings-privacy`
   - technical: `#settings-technical` (render it open, not inside a closed details), `#settings-ubyport`, `#settings-audit`, `#settings-version`
   - help: `#settings-guide`, `#settings-legal`
   `#settings-privacy-requests` section moves off /settings: the index row links to `/privacy-requests` instead.
   Keep every form, id, POST target, help tip and data-* attribute as it is.
3. Index (`group` None): back button (round 40 px light grey, `←`, href `/` or the Menu tab, `aria-label`), h1 "Settings" (32 px phone, same at tablet/desktop), plain list, no cards: 64 px rows = 24 px line icon + label (17 px) + `›` at right, no descriptions, 1 px divider between groups. Rows in this order: Account → /settings/account, Login & security → /settings/security, Phone app → /settings/phone, Data & archive → /settings/data, Business & legal details → /entities, Data requests → /privacy-requests, Archive → /settings/archived, Technical → /settings/technical, Help → /settings/help. Keep the /predplatne row (subscription) as a row too if settings.html has one today. Labels from existing translation keys where they exist; new keys in both en and cs.
4. Shared partials in `App/app/templates/partials/`: `settings_back_header.html` (back button + h1, args href/title), `settings_index_row.html` (icon, label, href). CSS in the 0780 block of `App/app/static/app2.css`, scoped to the settings pages, 720 lane at every width.
5. Update anchor links that pointed into the old single page (string changes only): `grep -rn 'settings#' App/app` → e.g. `/settings#settings-account` becomes `/settings/account#settings-account`, `#settings-stay-fee-emails` → `/settings/account#…`, `#settings-group-security` → `/settings/security`, `#settings-group-phone` → `/settings/phone`, `#settings-group-data` → `/settings/data`. Same in tests that assert those URLs.

## Tests

Make `test_0789_airbnb_settings_pattern_every_width` (already in `App/tests/test_0786_settings_geometry_browser.py`) pass for the index and the back header; adjust its selectors to your class names if needed, but keep its checks. Add a unit test: each `/settings/<group>` returns 200 when logged in and contains its section ids; `/settings/archived` still works. Then run the brief 0789 section 6 command and fix what this part broke (tests that looked for a section on `/settings` now fetch the sub-page).

## Do not

Restyle the group contents yet (part B does toggles/value cards and /entities, /privacy-requests, /settings/archived). No app.js change. No cache key yet.

## Report

Append "Part A" to `docs/tasks/0789-report.md`: commits, test line, what is left. Commit on the branch, do not push.
