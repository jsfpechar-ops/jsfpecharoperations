# 0002: Land the police answers, the download skeleton fix and the stay-fee row as three stacked PRs

Status: todo
Depends on: none | Base commit: 074be58 | Branch: task/0002a-download-skeleton, task/0002b-stay-fee-row, task/0002c-ubyport-severity
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

The code is already written and tested by the orchestrator. It arrives as the patch file `0002-bundle.patch` in docs/tasks. Apply it, check it in a real browser, and open three stacked PRs so each concern can be reviewed and reverted alone.

## 2. Context

Rules that apply (from `docs/context/rules.md`): never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (the owner does that); a template or static JS change needs the browser and geometry tests to pass with 0 skipped, plus screenshots; HIGH RISK filing changes need an owner decision (recorded in `docs/context/decisions.md`, 2026-10-06).

The patch holds four commits, in this order:

| # | Commit subject starts with | PR |
|---|---|---|
| 1 | `Keep the page visible when a download starts` | 0002a |
| 2 | `Show the town office one row per facility` | 0002b |
| 3 | `Stop treating late filings as failures` | 0002c |
| 4 | `Load the error severities` | 0002c |

What each fixes:

- **0002a.** Clicking Download PDF or Download CSV on a stay-fee report blanked the page behind the loading skeleton for 15 s. `App/app/static/skeleton.js` only skipped URLs ending in a file extension, and `/stay-fees/42/pdf` has none. The same happened on `POST /settings/workspace-export` and `POST /admin/users/{id}/export`.
- **0002b.** The stay-fee PDF for the town office showed a separate "Úprava výpočtu" row. The owner wants it folded into the facility row. The CSV register keeps one neutral line, "přenocování bez záznamu hosta (doplněno ubytovatelem)", so its total still matches the payment.
- **0002c.** The Foreign Police answered in writing (24 Sep 2026): the outcome depends on code severity, 0-2 accepted, 4-6 refused; 112 = reported late = accepted; do not auto-resend refused records. Also: the mock behaves like the police test environment, the abbreviation check takes 5-6 letters or digits, a passed connection test loads the error severities, and the script `reconcile_accepted_codes.py` (dry run by default) marks guests filed whose only code was 112.

## 3. Files

| Path | Action | What |
|---|---|---|
| `0002-bundle.patch` (docs/tasks) | delete in 0002a | The bundle, once applied |
| every file in the four commits | apply as is | Do not edit |
| `0002-report.md` (docs/tasks) | create | §9 |
| `docs/tasks/0002-police-downloads-stayfee.md` | edit | `Status:` line only |

No other file may change.

## 4. Steps

1. `git fetch origin && git checkout main && git pull`. Confirm the file `0002-bundle.patch` exists in docs/tasks.
2. Create the top branch and apply all four commits: `git checkout -b task/0002c-ubyport-severity && git am docs/tasks/0002-bundle.patch`. It must print `Applying:` four times with no conflict. If `git am` fails, run `git am --abort` and STOP (§8).
3. Make the two lower branches from the same history: `git branch task/0002a-download-skeleton HEAD~3` and `git branch task/0002b-stay-fee-row HEAD~2`.
4. `git checkout task/0002a-download-skeleton`, then remove the bundle (`git rm` on docs/tasks/0002-bundle.patch), set `Status: in-progress` in this brief, and commit "Remove the applied 0002 bundle". Then `git checkout task/0002b-stay-fee-row && git rebase task/0002a-download-skeleton`, then `git checkout task/0002c-ubyport-severity && git rebase task/0002b-stay-fee-row`.
5. On `task/0002c-ubyport-severity` (it holds everything), run §6. Everything must pass except the three tests §6 lists as already failing on `main`.
6. Browser check on `task/0002c-ubyport-severity`, against a local run (`cd App && ./run.sh`, mock UbyPort). Log in, open a property with a stay-fee period that has an adjustment, and save the period. Then click each of these and confirm that a file downloads and the page never turns into grey skeleton blocks:
   - Stay fees, then a facility, then **Download PDF** and **Download CSV**
   - Invoices, then an invoice, then **Download PDF**
   - Reports, then a submission, then **Doručenka**; and **Download receipts (ZIP)**
   - House book CSV export
   - Users (admin), row menu, **Export**
   Also click a normal link (Dashboard, then Stays) and confirm the page loads normally.
   Open the stay-fee PDF. It has one row per facility, no "Úprava výpočtu", and its total equals the CSV total.
   Take screenshots at 360, 390 and 1280 px of the stay-fee detail page and of the PDF.
7. Push the three branches to `origin` with upstream tracking (`-u`): `task/0002a-download-skeleton`, `task/0002b-stay-fee-row`, `task/0002c-ubyport-severity`.
8. Open three stacked PRs: 0002a into `main`, 0002b into `task/0002a-download-skeleton`, 0002c into `task/0002b-stay-fee-row`. Titles: "Downloads: keep the page visible", "Stay fees: one row per facility for the office", "Filing: police severity rule, 112 is an accept". In each body say whether filing behaviour changed (only 0002c: yes, HIGH RISK, owner decision 2026-10-06). Paste the screenshots into 0002a and 0002b.
9. Write `0002-report.md` in docs/tasks (§9) on `task/0002c-ubyport-severity`, set `Status: review` in this brief, commit, and push.

## 5. Do not touch

- Any file not in the four commits, except the three in §3.
- Do not edit the applied code to make a test pass. A failing test is a STOP.
- No secrets, `.env`, databases, police PDFs, UbyPort passwords or the test facility address in git or PR text. This repository is public.
- Do not merge, do not deploy, and never run `reconcile_accepted_codes.py --apply`.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q
```

Expected: everything passes, with 0 skipped in the browser and geometry files. These three also fail on `main` when run alone. Ignore them only if they fail on `main` in your run too: `test_host_i18n::test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_mail_failed_alert::test_the_send_loop_stores_the_code_and_renders_a_name`, `test_notification_copy::test_present_rebuilds_stay_title_with_czech_dates`.

From the repo root: `python3 scripts/context_lint.py` prints `context lint: OK`.

## 7. Acceptance

- [ ] `git am` applied four commits cleanly.
- [ ] Full suite green apart from the three known failures; the browser and geometry files ran with 0 skipped.
- [ ] Every download in step 6 saves a file and the page stays visible.
- [ ] The stay-fee PDF has one row per facility and no "Úprava výpočtu"; the CSV total equals the PDF total.
- [ ] Three stacked PRs are open, with screenshots at 360, 390 and 1280 px on 0002a and 0002b.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if:

- `git am` reports a conflict;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `0002-report.md` in docs/tasks (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat main...task/0002c-ubyport-severity`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/ubyport/errors.py` and `App/app/reporting.py` (classify call, duplicate rule, `SUBMISSION_MAX_AUTO_ATTEMPTS = 1`)
- `App/app/codelists.py` (Chyby layout, severity in `extra`)
- `reconcile_accepted_codes.py` (App scripts folder)
- `App/app/stay_fee.py` (`hlaseni`, register line)
- `App/app/static/skeleton.js`

## Owner steps

1. Merge 0002a, then 0002b, then 0002c with `scripts/merge-pr-on-green.sh`, in that order.
2. Deploy production.
3. On each production property, press **Save and test connection** once. That loads the police error severities.
4. On the server, from `App/`, run `.venv/bin/python scripts/reconcile_accepted_codes.py`. Look up two or three of the listed guest ids in the UbyPort web application. If they are there, run it again with `--apply`.
5. September stay fees: version 2 is sealed with the old layout. Press **Start correction**, then save, to get version 3 with one row. Send version 3 only if version 2 has not gone to the office yet.
6. Staging test filing with the police test account: `deploy/lightsail/README.md`, section "Filing against the police test environment".
