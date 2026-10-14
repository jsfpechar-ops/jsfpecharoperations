# 0101: Remove the old links and their adapters

Status: review | Executor: Claude (owner-authorized) | Branch base: claude/quirky-lamport-9svmd1 (fdcd8da) | Report: [0101-report](0101-report.md)

## 1. Objective

Owner decision 2026-10-13: "get rid of all the old links, we're not big enough to worry about users being used to old links — get rid of anything old and redundant." This deletes the redirect and compatibility code that 0076, 0077, 0078, 0092, 0094, 0096 and 0097 kept for old bookmarks. Every internal link now names its canonical page.

## 2. Context

The adapters are listed in [acceptance](../plans/host-ux-acceptance.md), rows "Legacy GET/POST adapters". Kept on purpose: guest `/l/<slug>` links and their old-slug redirects, URLs used in e-mails, iCal feeds, callbacks, `/healthz`, auth and public pages. A parallel worker owns `property_setup.py`, `_property_setup_guide.html`, `_property_overview.html`, the setup-step routes and the demo stay. None of them were edited.

## 3. Files

Removed (they now answer 404, or 405 for a POST):

| Path | Canonical home |
|---|---|
| `GET /automation` | `/apartments/{id}?view=settings&section=automation#automation`. With several properties: `/apartments#property-summaries` |
| `GET/POST /invoices/settings[?entity=]` | `/entities?edit={id}#entity-invoice` (POST `/entities/{id}/invoice`). With several or no businesses: `/entities` |
| `GET/POST /stay-fees/{id}/setup` | `/apartments/{id}?view=settings&section=reporting#stay-fee-settings` |
| `GET /apartments/{id}/ws-request.txt`, anchor `#ws-request-letter` | Settings → Reporting & fees `#ubyport` |
| `GET /setup`, `GET/POST /setup/{welcome,name,address,bookings}` (`routes/setup_wizard.py`, `templates/setup/*`) | `/apartments/new` or the property. The setup banner links the step's page |
| The app.js `HASHES` table (old `#basics`, `#communication`, `#door-code`, `#ubyport`, `#stay-fee-settings`, `#automation`, `#calendars`…) | Links and redirects carry `?view=&section=`. The hash only scrolls |

Also removed: 30 `setup.*` wizard strings (EN+CS), the `.wizard*` CSS, `_save_address_only`, `_legacy_invoice_entity`, `stay_fees._fee_values`, and `/automation` in `seo.PRIVATE_PREFIXES`.

Kept for e-mail: `GET /guest-links`. The lifecycle tip `lifecycle_no_guest` linked it, and tips already sent still do. The tip now links `/apartments#property-summaries`.

Also kept: the no-JS `:has(:target)` CSS rule. It is generic, and the Overview readiness links in `_property_overview.html` use in-page `#fragment`s.

## 4. Steps

Done in one session: delete the routes, point every link at its canonical URL, then delete or rewrite the tests that pinned the old behaviour.

## 5. Do not touch

The parallel worker's files (§2), `/l/` guest routes, mail routes, and `main`.

## 6. Commands

From `App/`, with the staging/mock env: `pytest tests -q`, `tools/smoke.py` (as in CI), `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`. From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- `App/tests/test_no_dead_internal_links.py` renders 27 host pages and Search for one host. Every same-origin `href` answers below 400. Every form target is a route for its method. Every JS literal path exists. The removed patterns appear nowhere under `App/app`.
- The smoke run expects 404 on every removed path.

## 8. Stop and ask

If an e-mail links one of these routes, change the e-mail and keep the redirect. This happened once (`/guest-links`).

## 9. Report

[0101-report](0101-report.md).
