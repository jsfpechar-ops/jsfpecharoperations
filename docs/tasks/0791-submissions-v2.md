# 0791 brief: Odeslání (/submissions) on the v2 look

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (shared rules, tests, report) and follow it.

## Page

- Template: `App/app/templates/submissions.html` (49 lines). CSS block: `/* 0791 submissions v2 (start) */` … `(end)` in `App/app/static/app2.css`.
- Head: h1 = `t('reports.title')`; `.sub` = `t('reports.lede')`; head ghost button "download receipts" (`/submissions/receipts.zip`, only `{% if receipt_count %}`, keep the download icon); keep the `reports.download_receipts_hint` line as a `p.sub ph-hide` under the head. No phone add button. The old tabs (Odeslání/Domovní kniha) go away: add a ghost head button linking to `/housebook` with `t('nav.housebook')`.
- Desktop table columns stay the same (when, property, mode, guests, outcome, stamp, actions). Outcome: map `submission_pill(submission.state)` to a v2 pill; check what the macro renders in `_components.html` and, if it is a `ui-badge`, add a `v2=true` style switch to the macro only if other callers keep their output (grep callers), otherwise write the `span.pill` mapping inline in this template.
- Phone card: `.sav` = first letter of the property name; `b` = property name; `small` = date/time · mode; pill = outcome. Same href `/submissions/<id>`.

## 0710 entry (append to PAGES in App/tests/v2_mockup.py)

`{"name": "submissions", "path": "/submissions", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn.ghost", "main table th", "main table td"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {}}`
If the rich test host has no submissions, add "main table th"/"main table td"/".card.stay"/".sav"/".stay .in b"/".stay .in small" to missing_ok with the reason "fixture has no police submission" and say so in the report.
