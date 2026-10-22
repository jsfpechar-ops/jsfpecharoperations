# 0247: Round 2 verification (geometry, design, UX)

Status: todo
Depends on: 0246 | Base commit: after 0246 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Prove round 2 (0239 to 0246: plain error fixes, "What needs you" on the dashboard, the property health check, the day-before nudge and one-button emails) holds up in the browser: the browser and geometry tests for every changed page pass with 0 skipped, and screenshots of the changed pages exist at 390, 1280 and 2000 px, sidebar open and collapsed, with demo data, after a stale-cache visit of the old app, in EN, CS and VI. This brief changes no app code.

## 2. Context

- Owner rule (UI verification, 2026-10-19): every changed page at 390/1280/2000, sidebar open and collapsed, demo data, a reload with a stale cache; a page is done only once its screenshots are saved. Languages: EN, CS, VI.
- Browser tests in this container: CI pins Playwright 1.63.0 (already installed in `App/.venv`), which wants headless shell build 1243; a symlinked copy of the container's build sits at `/tmp/claude-0/pw`. So every browser command starts with `PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw`.
- Screenshot tool: `/mnt/project-files/design-reset/tools/shots.py` (seeds demo data, `--old-app` serves the old checkout first in the same browser profile to catch stale `?v=` keys, writes PNGs and `report.json` with geometry problems per shot). `/mnt/project-files` is a network mount: use a trailing slash on paths, never search the whole folder.
- On a fresh seed the first stay and property have id 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| `/mnt/project-files/foolproof-round2/` | create | screenshots and report.json per language |
| `docs/tasks/0247-report.md` | create | report |

No file in the repo other than the report and this brief's Status line may change. If a test fails, do NOT fix app code: record it in the report.

## 4. Steps

### Step 1. Old app for the stale-cache check

`cd /home/user/jsfpecharoperations && git worktree add /tmp/claude-0/oldapp origin/main 2>&1 | tail -3`
(if `origin/main` is missing: `git fetch origin main 2>&1 | tail -3` first). Expected: a worktree at `/tmp/claude-0/oldapp`.

### Step 2. Browser and geometry tests (0 skipped)

```
cd /home/user/jsfpecharoperations/App && PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_geometry.py tests/test_host_quiet_dashboard_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_dashboard_rows_browser.py tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_followup_browser.py tests/test_onboarding_wizard_browser.py tests/test_design_guardrails_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_a11y_guard_browser.py tests/test_host_wide_geometry_browser.py -q --tb=line -rs 2>&1 | tail -30
```

Expected: all passed, 0 skipped. Copy the last 10 lines into the report. A failure: rerun only that file once with `--tb=short 2>&1 | tail -30` and copy the last 30 lines into the report.

### Step 3. Non-browser tests for round 2

```
cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_alert_stack.py tests/test_plain_fixes_0239.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_property_health_0244.py tests/test_arrival_nudge_0245.py tests/test_paste_check_0233.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_privacy_first.py tests/test_static_versions.py tests/test_design_lint.py -q --tb=line 2>&1 | tail -15
```

### Step 4. Screenshots, three languages

Pages (one comma list): `/,/reservations,/reservations/1,/apartments,/apartments/1,/apartments/1?view=overview,/apartments/1?view=settings&section=reporting`

(`/` is the "What needs you" card; `/reservations/1` is where its buttons and the emails land (`#now`) and where refused guests now read in plain words; `/apartments/1` shows the health check when the setup wizard card is not active. If the health check is not on `/apartments/1` in the shots because the demo property still shows the wizard card, say so in the report; do not change the seed.)

For each LANG in `en`, `cs`, `vi` run (one command per language):

```
cd /home/user/jsfpecharoperations/App && PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app /home/user/jsfpecharoperations/App --old-app /tmp/claude-0/oldapp/App --out /mnt/project-files/foolproof-round2/LANG/ --pages "<the list above>" --widths 390,1280,2000 --lang LANG 2>&1 | tail -15
```

If `--lang vi` is refused by the tool, say so in the report and keep EN and CS.

Round 2 changed `workflow.css` (new `?v=` key), so the `--old-app` pass must show no stale-stylesheet problem: in step 5 check every shot's `sheets` list names `workflow.css?v=20261022-0246`.

### Step 5. Read the geometry report

For each language: `python3 -c "import json;r=json.load(open('/mnt/project-files/foolproof-round2/LANG/report.json'));print(json.dumps(r, ensure_ascii=False)[:1500])"`. List in the report every shot with a problem (name and problem), or "none".

### Step 6. Look at the key shots once

Open (Read tool) only these EN images and write one line each on what you see (cut text, overlap, missing strip/tracker): `reservations-1-390.png`, `reservations-1-1280.png`, `apartments-1-setup-door-lock-390.png` (use the real file names from the folder listing `ls /mnt/project-files/foolproof-round2/en/ | head -60`).

### Step 7. Clean up

`cd /home/user/jsfpecharoperations && git worktree remove --force /tmp/claude-0/oldapp 2>&1 | tail -3`

## 5. Do not touch

All of `App/`. Do not retake shots more than once.

## 6. Commands

As in steps 2 to 5.

## 7. Acceptance

- [ ] Step 2: all passed, 0 skipped (or every failure quoted).
- [ ] Step 3: all passed.
- [ ] Screenshots saved for en, cs, vi under `/mnt/project-files/foolproof-round2/`.
- [ ] Geometry problems listed.

## 8. Stop and ask

Stop, and write the report, if: a command cannot run at all (missing tool, server does not start) after one retry; you reach 25 tool calls.

## 9. Report

Write `docs/tasks/0247-report.md` (800 tokens at most): each command's last lines, the geometry problems, the three image notes, deviations. Set `Status: review`, commit both as `0247 report` with `git add` of those two files only. Do not push or open a PR.

## Risk list (for the reviewer)

None (no code change).

## Owner steps

None.
