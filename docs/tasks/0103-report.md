# 0103: Dashboard calendar implementation report

Status: review
Base: 2662f404a40dc29dac3dcb888e83cf8e5b636f9d
Branch: feature/dashboard-interactive-calendar-20261015

## Changes
Interactive Month/Week/Year and property Gantt below the action queue; pointer/
keyboard night selection, persisted manual creation through POST /reservations,
overlap confirmation, booking details, native stay links, scoped loading/retry.
Auto uses Month for 1–2 visible properties and Gantt for 3+; manual view choice
and harmless display preferences persist. Removed the Waiting for guests tile.
Explicit owner-scoped payload, exclusive checkout, warm existing design tokens.

## Verification
- JavaScript syntax: passed via the available V8 runtime.
- Pure JavaScript date/layout checks: passed (DST date arithmetic, leap day,
  Monday start, October grid, 2/3-property Auto boundary, manual override,
  stacked overlap and adjacent-stay lane reuse).
- Local Python/pytest/ruff/browser/context commands: not run. No shell tool is
  available in this chat, despite the environment reporting running.
- First CI run: context, secret scan, shellcheck, dependency audit, runtime lint
  and type check passed. Full tests found an undeclared calendar preference key;
  fixed by adding the functional storage inventory row (all published languages).
- Second CI: full Python/coverage, lint/type/audit, context, secrets, shell,
  smoke and Docker passed. Chromium drag/create/save/details passed.
- Four browser tests stopped at polling expressions blocked by the existing CSP.
  Replaced expression waits with function predicates; CSP is unchanged.
- Added reverse Gantt selection, fresh-visit preference persistence, larger mobile
  targets and explicit target-size checks. A parallel calendar review job provides
  fast feedback; the full required browser suite still runs with zero-skip gates.
- Isolated review exposed a fresh-database test-order dependency; added explicit
  schema setup and a standalone dashboard render assertion. Startup failures now
  record visible-page and script/API diagnostics with synthetic fixtures.
- Final browser/geometry result: see current [PR checks](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/395/checks).
  Synthetic screenshots are uploaded as calendar-feature-review and dashboard-calendar-review.
- Browser suite includes actual drag/save/details, keyboard/overlap, Auto/manual
  preference, retry, EN/CS geometry and synthetic screenshots in CI artifacts.

## Staging
Not deployed. Render access is not exposed by the connected tools.
Review the exact green PR head, select this branch on Render ubyhost-staging,
Manual Deploy → Deploy latest commit, verify the SHA and signed-in flows.
The separate Lightsail Deploy staging workflow is not a Render deployment.
No main merge, production deploy, provider calls, credentials or real guest data.
