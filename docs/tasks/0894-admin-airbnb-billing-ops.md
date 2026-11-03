# 0894: Airbnb look on admin billing and operations

Status: todo
Depends on: 0893 (merged, or on its branch) | Base commit: 41e86bd3 | Branch: task/0894-admin-airbnb-billing-ops
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`/admin/fakturace` (billing) and `/admin/operations` get the same Airbnb look 0893 gives the other admin pages: pill tabs, a big bold title with its description under an 18 px "?", every section's help line under a "?" on its heading, 12 px between neighbours, on phone, tablet and desktop. Visual and copy placement only.

## 2. Context

- Run after 0893. It creates `App/app/static/admin2.css` and the helpers `fine_print_and_gap_findings` and `shoot` in `App/tests/test_0893_admin_airbnb_browser.py`; this brief links and imports them read-only. If either is missing, STOP.
- OUT of scope (owner, admin portal review 2026-11-01): the "Reports" disclosure, removing the duplicate trial funnel, the Czech funnel title, collapsing healthy Operations blocks, moving Incidents. Do not move, merge or remove any section, table, form or button.
- Page-specific CSS goes in a NEW file `App/app/static/admin2-system.css` (this brief owns it). Never edit `admin2.css`, `app2.css` or `base.html`.
- Fine print rule (same as 0893): a `.ui-sub` paragraph whose i18n key ends in `.help`, `_help`, `.lede` or `.export_help` moves under a "?" on its section heading, using `tip_label(text, id, help, tag='span')` from `_components.html`. Status content (`.none`, counts, spend, VS, dates, e-mails, payment messages, draft `pre`) stays visible; `admin2.css` already makes `.ui-sub` 16 px. `<label class="ui-sub"` becomes `<label class="admin-label"`.
- Speed: the mark-paid date is already prefilled with `today` and the month picker with `month`; nothing to add. Report the taps for "mark an invoice paid" and "export the month".

Anchors (exact, on 41e86bd3):

`App/app/templates/admin_billing.html`
```
{% block meta %}{{ t('billing.admin.lede') }}{% endblock %}
```
```
{% call ui_section(t('billing.admin.month.title'), id='month') %}
```
```
<p class="ui-sub">{{ t('billing.admin.month.export_help') }}</p>
```
`App/app/templates/admin_operations.html`
```
{% block meta %}{{ t('ops.lede') }}{% endblock %}
```
```
  <p class="ui-sub">{{ t('ops.filings.help') }}</p>
```
The other help lines in `admin_operations.html` follow the same shape: `ops.feeds.help`, `ops.jobs.help`, `ops.mail.help`, `ops.ttlock.help`, `ops.alerts.help`, `ops.havel.help`, `incidents.review_help`, `incidents.draft_help`. Find each with `grep -n "_help\|\.help'" App/app/templates/admin_operations.html | head -20` and the section heading above it with `grep -n "ui_section(\|<h2" App/app/templates/admin_operations.html | head -20`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/admin2-system.css` | create | billing/ops-only rules |
| `App/app/templates/admin_billing.html` | edit | v2, CSS links, title "?", section "?", labels |
| `App/app/templates/admin_operations.html` | edit | v2, CSS links, title "?", section "?" |
| `App/tests/test_0894_admin_airbnb_billing_ops_browser.py` | create | geometry test, 6 widths |
| `App/tests/static_versions.json` | regenerate | `--write`, never by hand |

Existing tests in §6 may get an assertion updated to the new markup; never delete a behaviour test. No other file may change.

## 4. Steps

1. Create `App/app/static/admin2-system.css` with exactly this:
```css
/* 0894: admin billing and operations, on top of admin2.css. Light mode only. */
body.v2 .ui-body ul{display:grid;gap:12px;padding-left:20px}
body.v2 .ui-body pre.ui-sub{white-space:pre-wrap;padding:16px;border:1px solid #e5e5e5;border-radius:12px;background:#fff}
body.v2 .ui-body input[type="file"]{min-height:44px}
body.v2 .ui-body details>summary{min-height:44px;display:flex;align-items:center;font-size:16px}
```
2. In both templates, directly after the `{% extends "host_page.html" %}` line, add:
```
{% set v2 = true %}
{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893"><link rel="stylesheet" href="/static/admin2-system.css?v=20261102-0894">{% endblock %}
{% from "_components.html" import tip_label with context %}
```
   Command: `grep -c "admin2-system.css" App/app/templates/admin_billing.html App/app/templates/admin_operations.html | tail -3`. Expected: 1 each.
3. `admin_billing.html`: replace the meta anchor with `{% block page_title %}{{ tip_label(self.title(), 'admin-billing-help', t('billing.admin.lede'), tag='span') }}{% endblock %}`.
4. `admin_billing.html`: replace the month section anchor with `{% call ui_section(tip_label(t('billing.admin.month.title'), 'month-help', t('billing.admin.month.export_help'), tag='span'), id='month') %}` and delete the `export_help` paragraph line. Then run `grep -n "ui-sub\">{{ t('billing.admin" App/app/templates/admin_billing.html | head -20`: apply the same change to any other line whose key ends in `.help`, `_help` or `.lede` (status lines such as `.none` stay). Command: `grep -c "export_help" App/app/templates/admin_billing.html | tail -3`, expected `1`.
5. `admin_billing.html`: replace every `<label class="ui-sub"` with `<label class="admin-label"` (Edit, replace_all). Command: `grep -c "label class=\"ui-sub\"" App/app/templates/admin_billing.html | tail -3`, expected `0`.
6. `admin_operations.html`: replace the meta anchor with `{% block page_title %}{{ tip_label(self.title(), 'admin-ops-help', t('ops.lede'), tag='span') }}{% endblock %}`.
7. `admin_operations.html`: for each help line listed in §2 (nine), wrap the heading of its section in `tip_label(<same title text>, '<section>-help', t('<help key>'), tag='span')` (in a `ui_section(...)` first argument, or inside the `<h2>`), and delete the help `<p>` line. Keep the `ttlock.counts`, `havel.spend` and `.none` lines. One Edit per section. Command: `grep -c "<p class=\"ui-sub\">{{ t('ops\.[a-z]*\.help')" App/app/templates/admin_operations.html | tail -3`, expected `0`.
8. Write `App/tests/test_0894_admin_airbnb_billing_ops_browser.py`: `from tests.test_0893_admin_airbnb_browser import host, base, fine_print_and_gap_findings, shoot  # noqa: F401`. Pages: `admin_billing` `/admin/fakturace`, `admin_operations` `/admin/operations`; widths 320, 390, 768, 1024, 1280, 1440; `?lang=en`. Checks: `body.v2`; one visible h1 >= 28 px; no horizontal overflow; `nav.ui-tabs` with exactly one `aria-current`, pills >= 44 px and >= 12 px apart; each `.help-tip-btn` on its heading's last line; `fine_print_and_gap_findings(page)` empty; `shoot(page, name, width)` (with `UBYHOST_SHOTS_0893=1` it writes to `screenshots-0893/`; pass a name starting `0894-`). Run §6 command 1; fix only `admin2-system.css` until green, 0 skipped. A finding only `admin2.css` could fix: STOP and report it for 0893's owner.
9. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
10. Run §6 command 2. A test that checks an action, link or `data-*` hook that disappeared: STOP.
11. §6 command 3 for screenshots; look at each 390 px image once.

## 5. Do not touch

`admin_home.html`, `admin_customers.html`, `admin_customer.html`, `admin2.css` (0893), `admin_users.html`, the funnel and incidents pages, `host_page.html`, `base.html`, `_ui*.html`, `_components.html`, `app.css`, `app2.css`, `app.js`, any Python or i18n file. AGENTS.md rules 2, 5, 6, 7, 9; the PostHog funnel section in billing stays as is.

## 6. Commands

From `App/`:
1. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0894_admin_airbnb_billing_ops_browser.py -q -rs --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed|skipped" | cut -c1-240 | tail -20`. Expected: passed, 0 skipped.
2. `.venv/bin/python -m pytest tests/test_admin_operations.py tests/test_billing_admin.py tests/test_admin_funnel.py tests/test_admin_section_tabs.py tests/test_design_admin.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0419_admin_billing_browser.py tests/test_funnel_ads_geometry_browser.py -q -rs --tb=line -p no:cacheprovider 2>&1 | tail -10`. Expected: passed, 0 skipped.
3. `UBYHOST_SHOTS_0893=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0894_admin_airbnb_billing_ops_browser.py -q -k "390 or 1280" -p no:cacheprovider 2>&1 | tail -5`.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Command 1: passed at all six widths, 0 skipped.
- [ ] Command 2 passed, 0 skipped.
- [ ] The count of `<form`, `<table`/`ui_table_begin` and `ui_section(` per template is the same before and after (numbers in the report).
- [ ] One 390 px screenshot per page (and 1280), names starting `0894-`.
- [ ] Report lists the taps for "mark an invoice paid" and "export the month".

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found verbatim, or 0893's CSS or helpers are missing;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a section, table, form or button would have to move, merge or disappear;
- a file outside §3 needs a change, or a Python change seems needed;
- a step is unclear.

## 9. Report

Write `docs/tasks/0894-report.md` (600 tokens at most) and set `Status: review`. The report has: files changed (`git diff --stat`); each §6 command with its last 5 lines; §7 ticked; Deviations; Questions; owner steps left.

## Risk list (for the reviewer)

`admin_billing.html` (mark paid, storno, statement import, exports), `admin_operations.html` (incident drafts).

## Owner steps

1. Open the PR and check the 390 px screenshots.
2. On staging, mark one test invoice paid from your phone and download the month export.
