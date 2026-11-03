# 0828 brief: Help & guide (/guide) searchable and folded

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
Josef (2026-11-02 15:14, "yes make it better"): /guide is comprehensive but one 17-screen wall with no search. Make it Wolt-like: (1) a search field at the top that filters topics as you type, (2) every topic folded by default showing only its title, opening on tap. No copy changes.

## 2. Context
Template `App/app/templates/guide.html` (~25 `<section class="guide-section card …" id="…">` with h2 and h3 subheads, a desktop TOC and a phone TOC `details.guide-toc-phone`). Look rules: block `/* 0803 help guide + Havel page (v2) */` in `App/app/static/app2.css`. Anchors like `/guide#door-codes` are linked from other pages and help tips: they must keep working (open that topic and scroll to it).

## 3. Files
`App/app/templates/guide.html`, new `App/app/static/guide.js` (own code, no library), `App/app/static/app2.css` (0803 block only), i18n files only for the search placeholder and the "no results" line (add one key each in every language file the guide uses; grep `guide.title`), `App/tests/test_0800_v2_remaining_pages_browser.py` or a new `App/tests/test_0828_guide_search_browser.py`, `App/tests/static_versions.json` via `.venv/bin/python tests/test_static_versions.py --write` (new file gets a `?v=20261102-0828` key).

## 4. Steps
a. Each topic becomes `<details class="guide-topic" id="…"><summary><h2>…</h2></summary>…body…</details>` (keep the section id on the details; keep h3 ids inside). Closed by default. Summary row: title left, small chevron right, 16 px padding, 12 px between topics, whole row is the tap target (>= 44 px high).
b. Search: `<input type="search" class="guide-search" hidden>` above the topics with the placeholder; `guide.js` removes `hidden`, and on input (debounced 100 ms, case- and diacritics-insensitive via `normalize('NFD')`) hides topics whose title+body text does not contain the query, opens the matching ones, and shows the "no results" line when none match. Empty query restores all closed. Esc clears.
c. Anchors: on load and on `hashchange`, if the hash names a topic or an element inside one, open that details and scroll it into view.
d. Without JavaScript: no search field, topics still open on tap (native details), anchors still reachable (they open on click via the TOC because the browser opens a details containing the target in Chromium; if a test shows it does not, leave the TOC as plain links).
e. Remove the desktop and phone TOC only if search + folding make it redundant? No: keep the TOC on desktop as a left list of topic links (it opens the topic via step c); remove the phone TOC details (search replaces it).
f. Tests (browser, 390 and 1280): all topics closed on load; typing "PIN" leaves only matching topics, opened; a nonsense query shows the no-results line; `/guide#door-codes` opens that topic; page height at 1280 on load < 3000 px; geometry check from the 0800 file passes for /guide.
g. Check whether the sidebar search (Ctrl K palette, grep `palette` in templates/static) finds guide topics. Do NOT build it; just write the finding in the report.

## 5. Do not touch
Guide copy, other pages, other app2.css blocks, the app2.css cache key (orchestrator bumps it).

## 6. Commands
From App/, `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`:
- `.venv/bin/python -m pytest tests/test_0828_guide_search_browser.py tests/test_0800_v2_remaining_pages_browser.py -k "guide" -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests -q -k "guide and not guest_guide" --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_host_i18n.py tests/test_privacy_first.py -q 2>&1 | tail -3` → 0 failed
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
Section 6 green; screenshots `UBYHOST_SHOTS_0800=1` for guide at 390 and 1280 show the search field and folded topics.

## 8. Stop and ask
Stop at 30 tool calls, or if a copy change seems needed.

## 9. Report
`docs/tasks/0828-report.md`: markup change, JS size, tests, the Ctrl K finding, final tails.
