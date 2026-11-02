# 0794 brief: Poplatek z pobytu (/stay-fees) on the v2 look, with the approved two-step box

Status: in-progress

Executor: Haiku 5.5. Read `AGENTS.md`, `docs/context/executor.md`, then `docs/tasks/0790-records-pages-v2-common.md` (shared rules, tests, report) and follow it. Your CSS block is `/* 0794 stay fees v2 (start) */` … `(end)` in `App/app/static/app2.css`. Another executor (0795) edits tests at the same time; do not edit tests other than the ones named here.

## Context

- The stay fee two-step change (old PR #652, brief `docs/tasks/0630-stay-fee-one-box.md`) is already merged into this branch: `App/app/templates/stay_fees.html`, `App/app/routes/stay_fees.py`, strings `stay_fees.pay.*`, test `App/tests/test_stay_fee_pay_steps*.py`. Its styling lives in `App/app/static/host2.css`, which v2 pages do NOT load: port only the rules this page needs into your 0794 block, scoped `body.v2 .stay-fees-page`, values from the v2 tokens.
- Approved by Josef (keep exactly): each card has two steps, "Kontrola" (figures + "Ano, sedí") and "Odeslat a zaplatit". Step 2 is ONE box: Stáhnout PDF (ghost), Otevřít datovou schránku (the only primary `btn`) with the council's data box ID, and the QR panel (amount, account, VS) beside them from 1024 px; below 1024 px the QR panel sits on top, account and VS each have a copy button. NO "Odesláno"/"Zaplaceno" marks or forms anywhere on the page, even though the phone v1 mockup shows them; if the template still renders them, remove that markup (not the route/data).
- Desktop look: mockup view `fee` in `docs/design/mockup/ubyhost-redesign-v2.html` (head h1 + one-line `.sub` + ghost button, cards). Phone: `data-s="poplatek"` / `poplatek-2` in `docs/design/mockup/ubyhost-phone-v1.html` as layout reference only, with phone v2 shared classes (`h2.sec`, cards radius 24, see `0729`/`0735` blocks in app2.css).
- Head: h1 `t('stay_fees.title')` (grep the real key), sub line, existing secondary actions become `btn ghost`. Settings links (e.g. "Nastavit poplatek") become a ghost head button, not text links. No tab strip.

## Files

`stay_fees.html`, the 0794 block, `App/tests/v2_mockup.py` (append one PAGES entry), `App/tests/test_stay_fee_pay_steps*.py`, `test_stay_fee_detail.py`, `test_fee_setup_compatibility.py` (update only assertions on old markup/classes per the standing rule in 0790). Not `stay_fee_detail.html`.

## 0710 entry

`{"name": "stay_fees", "path": "/stay-fees", "view": "fee", "selectors": [".head h1", ".head .sub", ".head .btn.ghost", "main .card"], "phone_mockup": PHONE_MOCKUP_V2, "phone_view": "menu", "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1"], "missing_ok": {}}`
If the rich test host has no fee period, say so in the report and add the reason to missing_ok.

## Tests

0710 `-k stay_fees`, then `tests/test_stay_fee*.py tests/test_fee_setup_compatibility.py tests/test_host_i18n.py`, browser env as in 0790. Screenshots 390 and 1440 into `docs/tasks/screenshots-0790/stay-fees-<w>.png`, with a fee period showing step 2 if the fixture allows (otherwise say so).

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
