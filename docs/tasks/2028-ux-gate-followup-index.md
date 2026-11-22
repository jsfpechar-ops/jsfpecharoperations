# 2028: UX-gate follow-up index (what the 26-page gate found, 2026-11-22)

Status: todo | Branch: task/2028-followup-index | Owner: orchestrator wrote this index; each child brief runs alone as Haiku 5.5
Source: `docs/tasks/2019-ux-gate-2011-2018.md` — 26 page labels × 390/768/1280 = 78 screenshots, all opened. Totals: **1 PASS, 19 PASS with findings, 5 FAIL, 1 GAP**; design-system checklist **3 of 10** §1 rules. Gate A (DOM parity) was already green when this gate ran (`fail: 0`, 411 rows).

## 1. Objective

Turn the five FAIL pages and the three tooling/global findings into briefs, in this order (one brief per session, top-down):

1. **2021** — fix `App/scripts/go_page_parity_screenshots.py`. **Run this first**: it is the only thing that can produce a Go-vs-Python *visual* diff, and without it every visual claim in this series is unbacked. It is also why the 2016 pass honestly recorded its screenshots as skipped.
2. **2022** — the claim device gate (`formPagesRequireClaim`, `stayClaimDeviceGate`). **Status: blocked on the owner.** The only security item here; UbyPort filing risk.
3. **2023** — `/admin` at 390: clipped tab, money KPI wrapping mid-number, tables, no pagination, sub-44 px targets.
4. **2024** — `/booking-sites`: an unnamed row, a singular title, 30 px targets.
5. **2025** — `/apartments/{id}/booking-site` + `/guide/questions`: stray block above the chrome, wordmark as H1, coral heading, a third tab-bar variant.
6. **2026** — `/guests/{id}`: "(optional)" reporting "required", red errors on a clean GET, five helper lines, a 12 × 12 input. Guest personal data — privacy row first.
7. **2027** — `--ink-faint` is 3.13:1 on white / 2.92:1 on canvas and fails AA everywhere it is used. One token, both stacks, no switch needed.

## 2. Context — the rule every page brief here has to respect

**Identical to prod was the acceptance criterion of 2011–2018, and it is the constraint on this round.** These five pages are character-identical to Python today (`/dev/ui` 2152/2152, `/guests/1` 10851/10851, `/reservations` 2599/2599), which means the FAILs are **pre-existing product problems inherited from Python**, not parity regressions.

So a Go-only fix would break `docs/plans/staging-prod-identical.md` — the owner's 1:1 requirement. Each page brief therefore carries, per [go-first](docs/context/go-first.md) ("bug fix: fix it in Go … the brief's owner steps include the switch"):

- the fix is **Go only**, and
- the **owner step** adds the path to prod `UBYHOST_GO_PATHS` (`docs/ENVIRONMENT.md:190`), which restores 1:1 by construction.

Do not "solve" the tension by editing Python to match, and do not add a second implementation.

`2027` is the exception: the CSS in `App/app/static` ships in the Go image (PR #1230), so one token change fixes both stacks at once and the plan stays true with no switch.

Two other findings are deliberately **not** briefs:

- `/` as admin renders the host Dashboard — there is no admin branch. That is a routing/product decision for the owner, recorded in `docs/context/known-issues.md`.
- The `/admin/fakturace/export` GAP: the ZIP route 500s on `pdf_blob IS NULL` on **both** stacks (956/956 identical). Behaviour is parity; the 500 is a data/seed and product question, not a UX fix.

## 3. Files

- `docs/tasks/2021-go-page-parity-screenshots-tool-fix.md`
- `docs/tasks/2022-claim-device-gate.md`
- `docs/tasks/2023-admin-home-390.md`
- `docs/tasks/2024-booking-sites-list.md`
- `docs/tasks/2025-apartment-pages-chrome.md`
- `docs/tasks/2026-guest-detail-form.md`
- `docs/tasks/2027-ink-faint-contrast.md`
- `docs/tasks/2019-ux-gate-2011-2018.md` (the evidence for all of them)

## 4. Steps

1. Run 2021 first, then re-run the gate it unblocks so 2023-2026 start from a measured Go-vs-Python diff instead of a description.
2. Run 2022 only after the owner answers §8 of that brief.
3. Run 2023-2026 in any order after 2021 (they touch different pages); 2027 can go at any time.
4. After each child, re-run the parity audit and confirm no row regressed **and** that the path it fixed is either switched in prod `UBYHOST_GO_PATHS` by the owner or listed as pending that switch.

## 5. Do not touch

`App/` and `go/` are edited only by the child executors under their own briefs; the orchestrator changes only `docs/`. No Caddy or `UBYHOST_GO_PATHS` changes from this index — those are owner steps inside each child brief.

## 6. Commands

```bash
python3 scripts/go_parity_check.py --all 2>&1 | tail -30            # expect 342/342
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5   # expect fail: 0
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30   # expect 0 skipped
python3 scripts/context_lint.py 2>&1 | tail -10
```

## 7. Acceptance

- Parity audit still `fail: 0`; `go_parity_check.py --all` 342/342; lint green with 0 skipped; `context_lint.py` OK.
- Every page brief reports 390/768/1280 screenshots it actually opened, and the design-system checklist ticked only where measured.
- For each page fixed and switched, staging and prod render the same page — either because prod runs Go for it, or because the token is shared.

## 8. Stop and ask

Escalate to the owner: any change to a claim-only rule or the UbyPort payload (2022, 2026), any fix that would need Python edited to match (that breaks the 1:1 plan, and the answer is the `UBYHOST_GO_PATHS` switch, not a second implementation), and the `/` admin-branch question.

## 9. Report

Orchestrator keeps this file as the running index; each child appends `docs/tasks/NNNN-report.md`. Update `docs/context/status.md` when a page's state changes, and close the matching row in `docs/context/known-issues.md`.
