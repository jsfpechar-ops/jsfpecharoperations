# 0315: Guide audit: which host page the Help & guide covers

Status: todo
Depends on: none | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0315-guide-audit
Executor: Haiku 5.5 | Fits one session: 8 tool calls, 15k tokens

## 1. Objective

Add `docs/plans/guide-coverage.md`: one row per host page in the layout guard's `ROUTES`, the guide anchor that explains it (or "missing"), and the order in which briefs 0316, 0317, 0318 and 0328 fill the gaps. Havel (AI) knows only what the guide says (plan `docs/plans/havel-support-assistant.md` section 16), so this table is the checklist for the guide work. Docs only.

## 2. Context

The orchestrator did the audit on 2026-10-24 against these files; the table in step 1 is the result. You only write it down.

- `App/tests/test_design_guardrails_browser.py` line 32: `ROUTES = {key: path for key, (path, _selector) in CAPTURE_ROUTES.items()}`, then `ROUTES.update({` adds `cleaning`, `guest-new`, the eight `setup-*` steps and `settings-account`. `CAPTURE_ROUTES` is in `App/tests/test_host_wide_geometry_browser.py` line 37.
- `App/app/templates/guide.html` line 9: `{% set sections = ['overview', 'statuses', 'setup', 'stays', 'guests', 'reporting', 'filters', 'housebook', 'stay_fee', 'invoices', 'settings', 'door-codes', 'faster', 'faq', 'legal'] + (['demo'] if demo_available else []) %}`. The `reporting` section also has the sub-anchors `manual-filing` and `ubyport-credentials`.

Context-rollout upload (orchestrator): none.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/plans/guide-coverage.md | new | the coverage table |
| docs/tasks/0315-report.md | new | report |

No other file may change.

## 4. Steps

1. Branch: `git fetch origin && git checkout -b task/0315-guide-audit origin/main`. Command: `grep -c "settings-account" App/tests/test_design_guardrails_browser.py && grep -c "'door-codes', 'faster'" App/app/templates/guide.html`. Expected: `1` and `1` (else STOP: the files changed since the audit).

2. Create `docs/plans/guide-coverage.md` with exactly this content:

````markdown
# Help & guide coverage (brief 0315, 2026-10-24)

Havel (AI) answers only from the guide (plan `havel-support-assistant.md` section 16), so every host page needs a guide
section a beginner can follow: **what it is**, **when you need it**, **how to do it** (one action per step, tap on a
phone and click on a computer) and **if something goes wrong**. "Partial" means the section exists but lacks the steps
or the trouble part. Routes are the keys of `ROUTES` in `App/tests/test_design_guardrails_browser.py`.

| Route key | Path | Guide anchor | State | Filled by |
|---|---|---|---|---|
| dashboard | `/` | overview, statuses | partial: no steps, no trouble part | 0328 |
| stays | `/reservations` | stays, filters | partial: no steps for calendars or Add stay | 0317 |
| stays-archive | `/reservations?range=archive` | none | missing | 0328 (Archive) |
| stay-detail | `/reservations/{id}` | stays (detail paragraph), faq | partial | 0317 |
| guest-new | `/reservations/{id}/guests/new` | stays (detail: "add or remove guests") | partial | 0317 |
| properties | `/apartments` | setup | partial: steps describe fields, not the screens | 0318 |
| property-new | `/apartments/new` | setup | partial | 0318 |
| property-detail, property-detail-configured | `/apartments/{id}` | setup | partial: the three tabs are not named | 0316 (tabs), 0318 |
| guest-links | `/apartments/{id}?view=settings&section=guests` | setup step 5, guests, faq | partial: no PIN or new-link steps | 0317 |
| automation | `/apartments/{id}?view=settings&section=automation` | setup step 4, reporting | covered | none |
| fee-setup | `/apartments/{id}?view=settings&section=reporting` | stay_fee | partial: where to set the rate is not said | 0318 |
| setup-property, setup-calendar, setup-police, setup-automation, setup-stay-fee, setup-door-lock, setup-guest-link, setup-try-it | `/apartments/{id}/setup/*` | setup | missing: the guided setup is not described | 0318 |
| operators, operator-add, operator-edit | `/entities` | setup step 1 | partial | 0318 |
| invoices | `/invoices` | invoices, filters | partial: no steps | 0318 |
| invoice-new-picker, invoice-new-selected | `/invoices/new` | invoices | partial | 0318 |
| invoice-detail | `/invoices/{id}` | invoices | partial | 0318 |
| invoice-settings | `/entities?edit={id}&next=/invoices` | none | missing | 0318 |
| fees-unset, fees-configured | `/stay-fees` | stay_fee, filters | partial: the three payment steps are not described | 0318 |
| fee-detail | `/stay-fees/{id}` | stay_fee | partial | 0318 |
| housebook | `/housebook` | housebook, legal | covered | none |
| submissions | `/submissions` | reporting, statuses | covered | none |
| submission-detail | `/submissions/{id}` | reporting, manual-filing | covered | none |
| cleaning | `/cleaning` | none | missing | 0317 |
| archive | `/settings/archived` | settings (one word) | missing | 0328 |
| settings, settings-account | `/settings` | settings | partial: mentions a password the app no longer has | 0328 |
| smart-locks | `/smart-locks` | door-codes | covered | none |

Pages outside `ROUTES` that Havel links (plan section 6): `/privacy-requests` (settings: one sentence; 0328),
`/cleaning/properties` and `/cleaning/shares` (missing; 0317), `/havel` (0322 adds one sentence to "Finding your way").

## Order

1. **0316** "Finding your way" (new first section: the menu on a phone and on a computer, the tabs, search, the
   "How does this work?" panel) and a glossary (iCal, PIN, UbyPort, IDUB, stay fee, guest register, guest link, stay).
2. **0317** Cleaning (new section), Guest links and PIN, Stays and calendars (steps and trouble parts).
3. **0318** Properties and first-time setup (the guided setup), Business details, Stay fees, Invoices.
4. **0328** Dashboard, Settings and security (corrects the password sentence), Archive, Data requests.
5. **0326** Vietnamese for every new key, and `GUIDE_STRINGS["vi"]` so Havel reads the guide in Vietnamese.
6. **0327** `App/tests/test_guide_coverage.py`, the new anchors in Havel's page map, the PR template line.

Areas already complete enough for Havel and left alone: Guest check-in (`guests`), Police reporting (`reporting`,
`manual-filing`, `ubyport-credentials`), Guest register (`housebook`), Digital door lock (`door-codes`), Common
questions (`faq`), Your legal duties (`legal`).
````

   Command: `grep -c '^| ' docs/plans/guide-coverage.md`. Expected: `27`.

3. Commit (`0315 step 2`), run the lint from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: `context lint: OK`.

## 5. Do not touch

Everything under `App/`. Any other file in `docs/`. Hard rules: AGENTS.md 3 (public repo), 8 (never push to `main`).

## 6. Commands

1. `grep -c '^| ' docs/plans/guide-coverage.md` → `27`.
2. `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] `docs/plans/guide-coverage.md` exists with the table and the order, byte for byte as in step 2.
- [ ] The lint is OK.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: step 1's greps do not print `1` twice.

## 9. Report

Write `docs/tasks/0315-report.md` (300 tokens at most) and set `Status: review`: the file, the two command outputs, section 7 ticked.

## Risk list (for the reviewer)

None: one new docs file.

## Owner steps

1. Read the table. If a page is missing that you want Havel to know about, say so before 0318 runs.
