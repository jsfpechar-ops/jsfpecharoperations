# 0023: Cleaning page polish (compact pills, compact list rows, calmer header)

Status: todo
Depends on: none (independent of 0022) | Base commit: 34b7933 (head of `feature/host-design0123-20261016`, PR 397) | Branch: `task/0023-cleaning-page-polish` cut from that head
Executor: Haiku 5.5 sub-agent (CSS-first, no JS logic change) | Fits one session, 90k tokens at most

## 1. Objective

The `/cleaning` page on staging looks heavy and off-standard. Make it compact and calm and in line with [HOST_APP_DESIGN §3](../HOST_APP_DESIGN.md#3-layout-visual-system-and-language) and [DESIGN components](../DESIGN.md#components): small tinted calendar pills, small "+N" overflow chips, one-row list cards, amber (not red) for "set the times", one slim period filter, one coral primary action.

## 2. Context

Owner complaints (2026-10-17, two screenshots of staging): (a) the cleaning pills in the calendar are ugly: saturated orange (#f5b942) with a heavy brown border and bold text; the "+1 more cleanings" bars below them are too large. (b) The list under the calendar is oversized: 22px names, 19px values, 24px padding, big filled red warning blocks repeated on every card, so a few cleanings fill several screens. (c) The header and the period form (48px inputs in a bordered panel) are loud.

Rules that apply: light mode only; one coral primary per page; amber = needs host action, red = critical only; "colour is never the only signal" (keep every text and `aria-label`); targets 44px on touch (≤760px keep the current touch sizes untouched); focus rings stay visible; keep every i18n key and text, no copy change. No JavaScript logic change: the DOM already has the hooks (`.cal-event.is-cleaning-marker`, `.cal-cleaning-icon`, `.cal-cleaning-label`, `.cal-cleaning-property`, `.cal-cleaning-count`, `.cal-more.has-cleaning-overflow`, `.cal-cleaning-overflow-icon/-count/-label`).

Tokens (from `App/app/static/tokens.css`, use only these): `--amber:#8a5200`, `--amber-bg:#fff4d6`, `--status-action-bg:#fde9c2`, `--status-action-ink:#6b3a00`, `--status-action-border:#eec27a`, `--red`, `--red-bg`, `--ink`, `--ink-secondary`, `--ink-muted`, `--border`, `--surface`, `--canvas-subtle`, `--brand-ink`, `--brand-soft`, `--radius-sm`, `--teal`, `--blue`, `--purple`.

Facts you will confirm in the code before editing (STOP if they differ, §8):

1. `App/app/static/dashboard-calendar.css`, one shared selector list (around lines 336 to 357 on the PR head) gives the toolbar controls AND the cleaning pills the same declarations:
   ```
   body.host-workspace .dashboard-calendar .cal-toolbar button.btn,
   body.host-workspace .dashboard-calendar .cal-heading button.btn,
   body.host-workspace .dashboard-calendar .cal-toolbar select,
   body.host-workspace .dashboard-calendar .cal-heading select,
   .dashboard-calendar .cal-event.is-cleaning-marker,
   .cleaning-page .dashboard-calendar .cal-event.is-cleaning-marker {
     box-sizing:border-box; height:28px; ... border:1px solid #674900; border-radius:5px; background:#f5b942; ... font-weight:800; ...
   ```
   The toolbar selectors must keep their rule. Only the two `.is-cleaning-marker` selectors move out into their own new rule (Step 2).
2. `.cal-week { --event-height:22px; }` and `.cal-week-events { grid-auto-rows:var(--event-height); }`: month pills sit in 22px rows, so the pill height must be `var(--event-height)` (22px), not 28px.
3. `App/app/static/cleaning.css` ends with "Compact turnover groups…" override blocks that already shrink some rules; you replace the card rules in place instead of adding a third layer.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/dashboard-calendar.css` | edit | Pill and overflow chip styles (Steps 1 to 3) |
| `App/app/static/cleaning.css` | edit | Header, period form, legend, list cards (Steps 4 to 8) |
| `App/app/templates/cleaning.html`, `cleaning_edit.html`, `cleaning_properties.html`, `cleaning_settings.html`, `cleaning_shares.html` | edit | Only the `?v=` query of the `cleaning.css` link: append `-0023` |
| `App/app/templates/_dashboard_calendar.html` | edit | Only the `?v=` query of the `dashboard-calendar.css` link: append `-0023` |
| `App/tests/test_cleaning_browser.py` | edit only if an assertion breaks | Adjust sizes or selectors the new design changes; never weaken a touch-target or overflow check |
| `docs/tasks/0023-report.md`, `docs/tasks/0023-screenshots/*.png` | new | §9 and §7 |

No other file may change. In particular no JS, no Python, no i18n, no template markup.

## 4. Steps

Read each region with `grep -n` first, then read only that range.

**Step 1: split the shared rule.** In `dashboard-calendar.css`, remove only the two `.is-cleaning-marker` selectors from the shared list in fact 1. Leave the toolbar rule exactly as it is.

**Step 2: new pill rule.** Replace the old cleaning-marker styling (the removed selectors, the `.cal-cleaning-icon`, `.cal-cleaning-label`, `.cal-cleaning-property` rules, and the line `.cleaning-page .cal-event[data-event-kind=cleaning] {...}` in `cleaning.css`) with this block, placed where the old pill block was. Desktop and tablet (above 760px) only; leave the existing `@media (max-width:760px)` pill rules (46px touch pills showing the count) alone:

```css
/* Cleaning pill: quiet amber tint, icon + property, one line. */
.dashboard-calendar .cal-event.is-cleaning-marker,
.cleaning-page .dashboard-calendar .cal-event.is-cleaning-marker {
  box-sizing:border-box; display:flex; align-items:center; gap:4px;
  height:var(--event-height,22px); min-height:0; max-height:none; margin:0 1px; padding:0 7px 0 5px;
  border:1px solid var(--status-action-border); border-left:3px solid var(--amber); border-radius:6px;
  background:var(--amber-bg); color:var(--status-action-ink);
  font-size:11px; font-weight:600; line-height:1; box-shadow:none; overflow:hidden;
}
.dashboard-calendar .cal-event.is-cleaning-marker:hover { background:var(--status-action-bg); filter:none; color:var(--status-action-ink); }
.dashboard-calendar .cal-cleaning-icon { flex:0 0 12px; width:12px; height:12px; color:var(--amber); }
.dashboard-calendar .cal-cleaning-label { display:none; }              /* the icon plus aria-label/title carry "Cleaning" */
.dashboard-calendar .cal-cleaning-property { display:block; flex:1 1 auto; min-width:0; max-width:none; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.dashboard-calendar .cal-cleaning-count { display:none; }
.dashboard-calendar .cal-event.is-cleaning-marker.is-gantt-cleaning { height:20px; }
```

The `.cal-cleaning-label { display:none }` rule must not apply inside `.cal-day-list` (the day popover keeps its readable label): check the existing `.cal-day-list .cal-cleaning-label` rules still win; if not, add `.cal-day-list .cal-cleaning-label { display:block; }` after it.

**Step 3: overflow chip.** Find the `.cal-more.has-cleaning-overflow` / `.cal-cleaning-overflow-*` rules. Above 760px make the chip tiny and quiet; keep its `aria-label`/`title`:

```css
.dashboard-calendar .cal-more.has-cleaning-overflow { display:inline-flex; align-items:center; gap:3px; width:auto; height:var(--event-height,22px); min-height:0; padding:0 6px; border:0; border-radius:6px; background:transparent; color:var(--amber); font-size:11px; font-weight:600; line-height:1; }
.dashboard-calendar .cal-more.has-cleaning-overflow:hover { background:var(--amber-bg); }
.dashboard-calendar .cal-cleaning-overflow-icon { flex:0 0 12px; width:12px; height:12px; }
.dashboard-calendar .cal-cleaning-overflow-label { display:none; }
```

Under 760px keep the existing sizes.

**Step 4: header.** In `cleaning.css`: `.cleaning-page h1 { font-size:1.625rem; margin:4px 0 2px; }`; `.cleaning-page-heading { margin-bottom:12px; gap:16px; }`; `.cleaning-page-heading p { font-size:.875rem; color:var(--ink-muted); margin:0; }`; `.cleaning-actions { gap:8px; }`; above 760px `.cleaning-page .btn { min-height:36px; padding:6px 14px; font-size:13px; }` (the ≤760px rule keeps 44px). Exactly one coral (`.btn.primary`) stays: "Add cleaning". Do not change markup.

**Step 5: skip link.** `.cleaning-skip`: visually hidden until focused (position:absolute; clip; on `:focus` show it normally with the focus ring). It must stay in the DOM and first in tab order.

**Step 6: period form and legend.** Make the period form a slim row, no panel: `.cleaning-period { padding:0; background:transparent; border:0; border-radius:0; gap:10px 12px; margin:0 0 10px; align-items:flex-end; }`; labels `font-size:12px; font-weight:600; color:var(--ink-secondary); margin-bottom:4px;`; inputs `min-height:36px; padding:6px 10px; font-size:13px;` and `flex:0 1 150px` for the two fields; the reset link `font-size:13px; min-height:36px`. At ≤760px inputs go back to 44px. Legend: `font-size:12px; color:var(--ink-secondary); gap:14px; margin:6px 0 10px;` with 10px rounded swatches (`width:10px;height:10px;border-radius:3px;`): booking swatch teal tint, cleaning swatch `var(--amber-bg)` with `var(--amber)` border (match the new pill).

**Step 7: list.** Replace the card rules (including the "Compact turnover groups" override block) with one compact set:

```css
.cleaning-list { margin-top:20px; }
.cleaning-list h2 { font-size:1.125rem; font-weight:650; margin:0 0 10px; }
.cleaning-date-group { margin:0 0 14px; }
.cleaning-date-group > h3 { font-size:13px; font-weight:650; color:var(--ink-secondary); letter-spacing:.01em; padding:0 0 6px; margin:0 0 6px; border-bottom:1px solid var(--border); }
.cleaning-card { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,2fr) auto; grid-template-areas:"head facts acts"; align-items:center; gap:4px 20px; padding:9px 12px; margin:0 0 6px; background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--teal); border-radius:8px; }
.cleaning-card[data-cleaning-color=blue] { border-left-color:var(--blue); }
.cleaning-card[data-cleaning-color=purple] { border-left-color:var(--purple); }
.cleaning-card-heading { grid-area:head; display:block; min-width:0; }
.cleaning-card h4 { font-size:15px; font-weight:650; line-height:1.3; margin:0; }
.cleaning-origin { display:block; font-size:12px; color:var(--ink-muted); }
.cleaning-facts { grid-area:facts; display:flex; flex-wrap:wrap; gap:2px 24px; margin:0; }
.cleaning-facts dt { font-size:11px; font-weight:600; color:var(--ink-muted); margin:0; }
.cleaning-facts dd { font-size:13px; line-height:1.35; margin:0; }
.cleaning-card-actions { grid-area:acts; display:flex; align-items:center; gap:12px; margin:0; justify-self:end; }
.cleaning-card-actions .btn { min-height:32px; padding:4px 12px; font-size:13px; }
.cleaning-card-actions > a:not(.btn) { font-size:13px; min-height:32px; }
.cleaning-card > :is(.cleaning-warning,.cleaning-access,.cleaning-instructions) { grid-column:1 / -1; }
.cleaning-warning { justify-self:start; margin:0; padding:3px 9px; font-size:12px; line-height:1.4; color:var(--status-action-ink); background:var(--amber-bg); border-radius:6px; }
.cleaning-warning:is([data-conflict],.cleaning-conflict) { color:var(--red); background:var(--red-bg); }
.cleaning-access { display:flex; align-items:baseline; gap:10px; padding:6px 10px; border-radius:6px; }
.cleaning-pin { display:inline; font-size:15px; margin:0; }
.cleaning-instructions { margin:0; font-size:13px; line-height:1.45; }
.cleaning-instructions h5 { font-size:12px; margin:0 0 2px; }
```

The conflict warning ("This cleaning conflicts with the booking window") is the only one that may stay red. There is no class that tells the two warnings apart in the markup, so do this: keep BOTH `.cleaning-warning` paragraphs amber (calmer, still a text warning) and drop the `:is(...)` red rule above. Do not change the markup.

Cards under 900px: `grid-template-columns:minmax(0,1fr) auto; grid-template-areas:"head acts" "facts facts";`. Under 760px: `grid-template-columns:minmax(0,1fr); grid-template-areas:"head" "facts" "acts";`, `.cleaning-card-actions { justify-self:start; }`, and the card action button back to `min-height:44px`.

**Step 8: cache busting.** Append `-0023` to the `?v=` of the `cleaning.css` link in the five templates listed in §3 and of the `dashboard-calendar.css` link in `_dashboard_calendar.html`.

**Step 9: review the shared effects.** `dashboard-calendar.css` also styles the Dashboard calendar and the Gantt view. Look at both: the pills must still fit their rows (no clipping, no overlap with the day number or with the next lane), and the Dashboard calendar must not otherwise change.

## 5. Do not touch

`App/app/static/*.js`, any Python file, i18n files, `reservations.html`, `dashboard.html`, `host-design0123.css`, `.github/`, the mobile (≤760px) pill rules and touch-target sizes. Hard rules 5, 6 and 7 of AGENTS.md apply (light mode only; browser and geometry tests 0 skipped; screenshots in the report). No new dependency, no new file besides §3.

## 6. Commands

From `App/` (never set `PYTHONPATH=App`):

```
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=../docs/tasks/0023-screenshots .venv/bin/python -m pytest tests -q -k "cleaning or dashboard_calendar or host_geometry or wide_geometry"
UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q
```

If `App/.venv` is missing, create it from the project's declared requirements (no new dependency). Chromium is preinstalled (`/opt/pw-browsers`); do not run `playwright install`. From the repo root: `python3 scripts/context_lint.py`. One failure, `test_feed_dns_pinning`, is a known sandbox DNS issue (see `docs/tasks/0006-report.md`); report it, do not fix it.

Screenshots (demo data, light mode) into `docs/tasks/0023-screenshots/`: `/cleaning` at 1280, 1024, 390 and 360 px (`cleaning-1280.png`…), the month calendar (pills and overflow chips visible), the list, the Gantt view at 1280, and the Dashboard calendar at 1280 (shared CSS check). A short Playwright script is fine; keep it outside the repo (scratchpad).

## 7. Acceptance

- [ ] Month pills are 22px high, amber tint with a thin border and a 3px amber left edge, icon plus property name; no saturated orange, no brown border.
- [ ] "+N" overflow chips are small and quiet (icon and number), full text in `aria-label`/`title`.
- [ ] List cards are one compact row at 1280px (name, dates, buttons), about 60px high without warnings; warnings are small amber lines, not big filled blocks.
- [ ] Header and period form are slim; one coral button only ("Add cleaning"); skip link still works with the keyboard.
- [ ] No horizontal overflow at 360, 390, 1024, 1280px; touch targets at ≤760px unchanged (44px).
- [ ] Dashboard calendar and Gantt still render correctly (screenshots).
- [ ] Browser and geometry tests: 0 skipped. Every changed test assertion is explained in the report.
- [ ] `python3 scripts/context_lint.py` prints OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or fact in §2 is not found as described;
- a test fails twice;
- a new dependency, a JS change, a Python change or a markup change seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- you are about 85k tokens in;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0023-report.md` (1,500 tokens at most) and set `Status: review`: the files changed (`git diff --stat`), each command with the last 5 lines of its output, §7 ticked honestly, deviations, questions, owner steps left. Commit on `task/0023-cleaning-page-polish`; never push.

## Risk list (for the reviewer)

`App/app/static/dashboard-calendar.css` (the shared rule split in Step 1 must not change the toolbar controls) and `App/app/static/cleaning.css` (the card block replaces two older layers). Check the Dashboard calendar screenshot.

## Owner steps

1. Push the branch: `git push origin task/0023-cleaning-page-polish:feature/host-design0123-20261016` (or merge it into the PR branch).
2. Wait for CI on PR 397 and look at the `/cleaning` screenshots at 360 and 1280 px.
3. If they look right, merge with `scripts/merge-pr-on-green.sh`. Deploy to production is yours.
