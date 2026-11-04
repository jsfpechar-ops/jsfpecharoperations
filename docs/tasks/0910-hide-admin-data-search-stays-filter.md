# 0910: Hide admin-only data from customers, search finds guests, Stays filter starts closed

Status: todo. Source: UX review 2026-11-04 (findings 2, 3, 6, 7; Stays rows of the UI table). Executor: Haiku 5.5, one run.
Read first: AGENTS.md, docs/context/executor.md, this brief. Open only the files and line ranges named here.

## 0. Before you start
- Start only after PR #772 (dashboard setup card) is merged. It edits `base.html`, `app2.css`, `_components.html` and `layout_lint.js`, so branch from a fresh `origin/main` after that merge. This brief edits none of those files.
- Risk: the Cmd-K search work may touch `App/app/routes/api.py` and `App/app/static/app.js` (`initPowerTools`). No open PR for it was found on 2026-11-04. If `git log origin/main -5 -- App/app/routes/api.py` shows a commit newer than 2026-11-03, STOP and ask.
- Guest pages and public pages stay untouched. No Payments templates or routes.

## 1. Objective
Customers stop seeing the Technical settings page and the raw retention debug string. The Cmd-K search finds stays by guest name and says plainly when nothing matches. The Stays filter panel arrives closed from the server instead of flashing open. The Stays date chip uses dd.mm.yyyy. The Add stay panel and stay rows lose the stray focus ring and the stray separator.

## 2. Context (verified 2026-11-04)
- An admin is `current_user.role == 'admin'`. Templates already use it (`_shell_sidebar.html:36`, `_shell_v2.html:37`). In Python: `auth.current_user(request)["role"] == "admin"` (as in `routes/api.py`).
- Settings groups: `routes/admin.py:4773` `SETTINGS_GROUPS = (... "technical" ...)`. The routes are registered in a loop at ~4879, and all go through `_settings_page(request, group)` (~4781). `routes/admin.py` imports only `APIRouter, Depends, Request` from fastapi (line 21).
- The Settings index row for Technical: `templates/settings.html:34`.
- The retention debug string: `templates/settings.html` ~262-272, inside `#settings-data`: `{% for key, value in retention_last_run.counts.items() %}{{ key }}={{ value }}...`.
- The purge form: `templates/settings.html` ~253-260 (`action="/settings/purge-expired"`). It is already `disabled` at 0, but the review still saw a clickable "Delete 0 expired records" button.
- Search API: `App/app/routes/api.py` `command_palette` (line 21). The stays block (~86-102) selects `r.summary` only, with the label `f"{stay['internal_name']} · {stay['date_from']} – {stay['date_to']}"` (ISO dates).
- Search JS: `App/app/static/app.js` `render(query)` at ~1631-1675. `fuzzyScore` does subsequence matching, which is why "Beatrice" matches "CLOSED – Not available". The Havel row replaces the empty state at ~1663-1666.
- Empty text: `data-empty="{{ t('command.empty') }}"` in base.html (do not edit base.html). Keys: `command.empty` in `host_i18n.py` en ~601 and cs ~2670, and in `host_vi_i18n.py` ~714.
- Guest first name and surname are stored in plain text (`db.py` `ENCRYPTED_GUEST_COLUMNS` does not list them).
- Stays filter: the form is at `templates/reservations.html:106` (`id="stays-filter-panel" ... class="filters ui-section host-filter-panel stays-filter" data-filter-panel`). Its toggle is at line 27 (`data-filter-toggle aria-expanded="true" ... hidden`). In JS, `initFilterPanels` at `app.js` ~1051 adds `is-enhanced is-collapsed`. CSS already hides `.is-collapsed` (`app2.css:534`, `host.css:514`). CSP allows inline style (`main.py:186` `style-src 'self' 'unsafe-inline'`).
- Date chip: `app.js` ~1147-1150 builds `formatter = new Intl.DateTimeFormat(lang, { day: "numeric", month: "short", year: "numeric" })`, which shows "Nov 4, 2026".

## 3. Files
`App/app/routes/admin.py`, `App/app/templates/settings.html`, `App/app/routes/api.py`, `App/app/static/app.js`, `App/app/templates/reservations.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, the template that links `app.js` (cache key only), `App/tests/static_versions.json` (if `test_static_versions.py` demands it), and the tests you add.

## 4. Steps
1. **Technical page is admin-only.** In `_settings_page`, right after `if guard: return guard`, add:
   ```python
   if group == "technical":
       viewer = auth.current_user(request)
       if not viewer or viewer["role"] != "admin":
           raise HTTPException(status_code=404)
   ```
   Add `HTTPException` to the fastapi import on line 21. In `settings.html:34`, wrap the Technical index row in `{% if current_user.role == 'admin' %}...{% endif %}`.
2. **Retention debug string is admin-only.** In `settings.html`, change the `{% if retention_last_run.counts %}` that wraps the `key=value` loop to `{% if retention_last_run.counts and current_user.role == 'admin' %}`. Customers keep the date and the dry-run/live word.
3. **No purge button when there is nothing to purge.** Wrap the whole `<form method="post" action="/settings/purge-expired" ...>...</form>` in `{% if expired_records %}...{% endif %}`. The "expired" value card above it already says 0.
4. **Search indexes guest names.** In `command_palette`, after the `reservations` query, load the names of those stays' guests through the db helpers:
   ```python
   stay_ids = [int(r["id"]) for r in reservations]
   names: dict = {}
   if stay_ids:
       marks = ", ".join("?" for _ in stay_ids)
       for g in db.query(f"SELECT reservation_id, first_name, surname FROM guest WHERE reservation_id IN ({marks})", tuple(stay_ids)):
           names.setdefault(int(g["reservation_id"]), []).append(f"{g['first_name'] or ''} {g['surname'] or ''}".strip())
   ```
   First verify the column: `grep -n "FROM guest WHERE reservation_id" App/app/*.py | head -3`. If nothing matches, STOP. For each stay, set `"keywords": " ".join([stay["summary"] or "", *names.get(int(stay["id"]), [])])`. Set `"meta"` to the first guest name when there is one, else keep `stay["summary"] or t("command.stay")`. Show the label dates as dd.mm.yyyy with a local helper `_cz(d)` (`s = str(d)[:10]; return f"{s[8:10]}.{s[5:7]}.{s[:4]}"`).
5. **Search matches whole substrings, accent-insensitive.** In `app.js` `render(query)`, add `function fold(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase(); }`. Build `words` with `fold(query).trim().split(/\s+/)` and the haystack with `fold([...].join(" "))`. Replace the body of `fuzzyScore(haystack, word)` with `return haystack.indexOf(word);` and keep its name and callers.
6. **"No results" before the Havel row.** In the block `if (!visible.length && askHavel && words.length)`, set `var noMatch = true;` before replacing `visible` (declare `var noMatch = false;` above it). After `results.textContent = ""` has run and before `visible.forEach`, add: `if (noMatch) { var none = document.createElement("p"); none.className = "command-empty"; none.textContent = results.getAttribute("data-empty") || ""; results.appendChild(none); }`. Copy: `command.empty` becomes en "No results", cs "Nic nenalezeno", vi "Không có kết quả".
7. **Stays filter arrives closed.** In `reservations.html:106`, add ` is-collapsed` to the form's class list. On line 27, change the toggle to `aria-expanded="false"`. Keep `hidden`, because JS reveals it. Directly after the closing `</form>` of `#stays-filter-panel`, add `<noscript><style>html body form#stays-filter-panel.is-collapsed{display:block}</style></noscript>` so the filter still works without JavaScript.
8. **Date chip in dd.mm.yyyy.** Read `app.js` 1140-1160. If `formatter` (line ~1149) is used only through `formatter.format(date)`, replace it with `var formatter = { format: function (d) { return String(d.getDate()).padStart(2, "0") + "." + String(d.getMonth() + 1).padStart(2, "0") + "." + d.getFullYear(); } };`. If it is used any other way, STOP. Leave the month formatter (~1153) as it is.
9. **Add stay: no red focus ring on load, no stray dash.** `grep -n "autofocus" App/app/templates/reservations.html`: remove `autofocus` from the property `<select>` in `#add-stay-panel` (and only there). In the row at ~211, `{{ guest_count(progress, placeholder=true) }} &middot; {{ source_badge(...) }}`, render the guest count and the `&middot;` only when there is a count: wrap both in `{% if progress.expected or progress.guests %}...{% endif %}`. First check those fields exist: `grep -n "progress.expected\|progress.guests" App/app/templates/reservations.html | head`. If neither appears, STOP.
10. Bump the `?v=` cache key of `app.js` where it is linked (`grep -rn "static/app.js?v=" App/app/templates | head`). Follow `test_static_versions.py`.

## 5. Do not touch
`base.html`, `app2.css`, `_components.html`, `layout_lint.js` (PR #772); guest and public templates; anything under `payments*`; `go/`; migrations.

## 6. Commands (from `App/`, each ending `2>&1 | tail -30`)
- New tests in `tests/test_0910_admin_only_and_search.py`:
  - a non-admin GET `/settings/technical` returns 404; an admin gets 200;
  - a non-admin `/settings` has no `/settings/technical` link;
  - `/settings/data` as a non-admin with a recorded retention run has no `=` count string;
  - `/api/command-palette` returns an item whose `keywords` contain a seeded guest's surname;
  - `/reservations` HTML has `stays-filter-panel` with `is-collapsed`.
  If an existing test opens `/settings/technical` as a non-admin, change it to log in as admin. Do not delete it.
- `.venv/bin/python -m pytest tests/test_0910_admin_only_and_search.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs`, 0 skipped.
- Copy row: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_flash_literals.py -q --tb=short -x` (use the `test_*_i18n.py` files that exist).
- UX gate (AGENTS rule 10, workflow "UX gate"): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped, zero host findings. Open the `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` shots for Stays and Settings (data, index). In the PR body, per page: "390: ...; 768: ...; 1280: ...".
- Repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] A customer has no Technical row, gets 404 on `/settings/technical`, sees no `key=value` retention text, and sees no purge button at 0.
- [ ] Searching a guest's first name or surname (with or without accents) lists that stay. A query that matches nothing shows "No results" above the Havel row.
- [ ] The Stays filter is closed in the server HTML (curl shows `is-collapsed`), and opens with the Filters button. Without JS, the panel is visible.
- [ ] The date chip reads `04.11.2026 – ...`.
- [ ] No new dependency, no migration, light mode only, 12 px neighbour rule held in the screenshots.

## 8. Stop and ask
An anchor is not found; `guest.reservation_id` does not exist; a test pins the fuzzy search or the Technical page for customers in a way you can't fix by logging in as admin; `formatter` is used other than `.format()`.

## 9. Report
`docs/tasks/0910-report.md` (executor.md format), with the 390 px screenshots of Stays and Settings → Data.
