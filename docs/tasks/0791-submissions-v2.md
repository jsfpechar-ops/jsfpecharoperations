# 0791 brief: Odeslání (/submissions) on the v2 look

Status: in-progress

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (shared rules, tests, report) and follow it.

## Page

- Template: `App/app/templates/submissions.html` (49 lines). CSS block: `/* 0791 submissions v2 (start) */` … `(end)` in `App/app/static/app2.css`.
- Head: h1 = `t('reports.title')`; `.sub` = `t('reports.lede')`; head ghost button "download receipts" (`/submissions/receipts.zip`, only `{% if receipt_count %}`, keep the download icon); keep the `reports.download_receipts_hint` line as a `p.sub ph-hide` under the head. No phone add button. The old tabs (Odeslání/Domovní kniha) go away: add a ghost head button linking to `/housebook` with `t('nav.housebook')`.
- Desktop table columns stay the same (when, property, mode, guests, outcome, stamp, actions). Outcome: map `submission_pill(submission.state)` to a v2 pill; check what the macro renders in `_components.html` and, if it is a `ui-badge`, add a `v2=true` style switch to the macro only if other callers keep their output (grep callers), otherwise write the `span.pill` mapping inline in this template.
- Phone card: `.sav` = first letter of the property name; `b` = property name; `small` = date/time · mode; pill = outcome. Same href `/submissions/<id>`.

## 0710 entry (append to PAGES in App/tests/v2_mockup.py)

`{"name": "submissions", "path": "/submissions", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn.ghost", "main table th", "main table td"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {}}`
If the rich test host has no submissions, add "main table th"/"main table td"/".card.stay"/".sav"/".stay .in b"/".stay .in small" to missing_ok with the reason "fixture has no police submission" and say so in the report.

## 1. Objective

Restyle the page(s) named above onto the v2 look; no behaviour change.

## 2. Context

See the sections above and docs/tasks/0790-records-pages-v2-common.md.

## 3. Files

Only the files named above, plus this brief's report.

## 4. Steps

Follow the sections above in order.

## 5. Do not touch

base.html, catalog.json, static_versions.json, docs/design/mockup/, other briefs' CSS blocks and templates.

## 6. Commands

From App/: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <files> -q --tb=short 2>&1 | tail -30

## 7. Acceptance

The named tests pass with 0 skipped; screenshots at 390 and 1440 px exist.

## 8. Stop and ask

A test outside the standing rule fails, or the tool-call cap comes near: write the report with what is left.

## 9. Report

docs/tasks/<number>-report.md as described in 0790.
