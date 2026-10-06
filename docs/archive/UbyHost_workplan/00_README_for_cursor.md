# UbyHost work plan for Cursor

Read this file first, then `AGENTS.md` and **[../../UBYPORT_CORE.md](../../UBYPORT_CORE.md)** (police reporting is the core function and must not regress), then the notes for the work package (WP) you are asked to do.

## What is here

| Path | Contents |
|---|---|
| `series/0001-...` to `series/0034-...` | The code. 34 `git format-patch` files, one per WP, in merge order. |
| `series/INTEGRATION_NOTES.md` | How cross-WP conflicts were resolved, test counts per checkpoint, known open items. |
| `notes/WPNN-*.md` | Per WP: summary, files, tests, deviations from the spec, what to verify, manual owner steps. Read the notes before applying the patch. |
| `01_before_golive.md`, `02_after_golive.md`, `03_when_triggered.md` | The original specifications. `series/` and `notes/` override them. |
| `04_legal_positions.md` | The owner's legal decisions (researched, not attorney advice). Texts in the code come from here. |
| `compliance/` | Internal compliance documents (records of processing, DPIA, breach runbook, terms clauses, manual filing guide). Not code. |
| `06_council_verdict.md`, `07_council_verdict_round2.md` | Why the order is what it is, and the four gates. |
| `UbyHost_architecture_review.md` | Background reasoning. Section 12 holds the owner decisions on infrastructure and analytics. |
| `skills/` | Two skills the owner uses (poteto-mode, llm-council). Not part of the app. |
| `OWNER_MANUAL_SETUP.md` | Consolidated owner secrets, server setup, and per-patch manual steps. |
| `OWNER_WORKFLOW_STEP_BY_STEP.md` | Full owner playbook: where to click for GitHub, Render, AWS, Lightsail `.env`, all phases. |
| `MERGE_SEQUENCE.md` | Prepared `cursor/wp-stack-NN-682e` branches and merge order for all 34 PRs. |
| `STAGING_ON_RENDER_STEP_BY_STEP.md` | Owner click-by-click guide to recreate **ubyhost-staging** on Render. |

Put the whole folder in the repo at `docs/plans/UbyHost_workplan/`, except `skills/`.

## Base

The series applies on `main` at `709076a` (PR 230 merged, including its follow-up fixes). A fresh checkout of that commit takes all 34 patches with `git am`, zero conflicts. The full suite passed on the 33-patch tree (2,775 passed, 2 skipped, guest browser e2e and host geometry included). WP33 was then added as 0021. Its own tests and the reservation, dashboard, deadline, watchdog, cookie, i18n and em-dash tests passed on the 34-patch tree. The full suite was not rerun on the 34-patch tree, so step 4 below on every PR is the check. If `main` has moved since, use `git am -3` and resolve small conflicts keeping both behaviours.

## Procedure for each PR

For patch number NN (one WP per PR, strictly in numeric order, the next one only after the previous is merged):

1. `git checkout main && git pull`, then `git checkout -b wpNN-<short-name>`.
2. `git am -3 docs/plans/UbyHost_workplan/series/00NN-*.patch`. On a conflict, resolve it, `git add`, `git am --continue`. Write each resolution in the PR description.
3. Read `notes/WPNN-*.md` and do everything under "What Cursor must verify or adapt".
4. Run:
   - `cd App && ruff check app tests tools --select E9,F63,F7,F82,F401,F841`;
   - the full test suite in ONE process, as CI runs it (do not exclude `test_endtoend` or `test_demo_seed`);
   - for WPs that change templates or CSS: the guest browser e2e with `UBYHOST_REQUIRE_BROWSER=1` at 320, 360 and 390 px, plus `tests/test_host_geometry.py`, with 0 skipped.
5. Open a draft PR titled `WPNN: <title>`. Description: what changed, test counts, conflict resolutions, the manual owner steps copied from the notes, and for HIGH RISK WPs the exact diff hunks the notes name for review by hand.
6. Never push to `main`, never merge, never force-push a shared branch.

## Order

Infrastructure first (the owner sets these up now, not at go-live):

| # | WP | Title | Risk |
|---|---|---|---|
| 0001 | WP05 | Litestream continuous backup to S3 | medium |
| 0002 | WP06 | Scheduler in its own process, web workers | HIGH |
| 0003 | WP07 | Job heartbeats, static caching, compression | low |
| 0004 | STEP0 | Staging deploy target | low |
| 0005 | WP32 | Container sizing for the 8 GB server | low |

Filing correctness:

| # | WP | Title | Risk |
|---|---|---|---|
| 0006 | WP30 | Request and store the Doručenka PDF correctly | HIGH |
| 0007 | WP31 | Exactly one automatic resend per interrupted filing | HIGH |

Product, privacy and legal (before the first real host):

| # | WP | Title | Risk |
|---|---|---|---|
| 0008 | WP01 | Deadline shows the filing time once reported | low |
| 0009 | WP02 | Property names in guest e-mails | low |
| 0010 | WP03 | Guide second pass | low |
| 0011 | WP04 | Admin access to guest data | HIGH |
| 0012 | WP25 | House book layout, filed-guest locking, Doručenka button | medium |
| 0013 | WP28 | UI bug sweep | low |
| 0014 | WP08 | Passport upload hardening | low |
| 0015 | WP09 | Umami on public pages, privacy policy, subprocessors | medium |
| 0016 | WP27 | Privacy first: audit, brand, cookie guard test | low |
| 0017 | WP22 | Retention aligned to law | medium |
| 0018 | WP23 | Filing watchdog and "filed by hand" mark | HIGH |
| 0019 | WP24 | Terms, DPA and manual-filing texts | medium |
| 0020 | WP26 | Guest pages in German, Spanish, French (auto-detected) | medium |
| 0021 | WP33 | Overdue stays in the default Stays view, guest languages behind a switch | low |

After the first hosts are live: 0022 WP10, 0023 WP13, 0024 WP14 (HIGH), 0025 WP15, 0026 WP17, 0027 WP11, 0028 WP12, 0029 WP16 (HIGH), 0030 WP18, 0031 WP19 (HIGH), 0032 WP20 (HIGH), 0033 WP21 (HIGH), 0034 WP29.

Feature switches that stay off until the owner turns them on: `UBYHOST_LIFECYCLE_MAIL`, `UBYHOST_SIGNUP_ENABLED`, the Meta and Umami settings. `UBYHOST_RETENTION_AUTOPURGE=1` is set by the owner when the first real host starts.

Browser tests: run the guest browser e2e and `tests/test_host_geometry.py` with `UBYHOST_REQUIRE_BROWSER=1` and 0 skipped for every WP that touches templates or CSS.

## Gates (the owner checks these, not code review)

The owner is not a developer. Each gate is something he can see on staging. Do not open the next PR after a gate until the owner says the gate passed.

1. Gate 1, after 0001 to 0005. `./scripts/restore_test.sh` passes on the server, and every healthchecks.io check is green.
2. Gate 2, after 0006 and 0007. One test stay filed from staging against the UbyPort test endpoint (`UBYHOST_UBYPORT_ENV=test`) shows "Download Doručenka (PDF)" and the PDF opens. If UbyPort rejects the request or no PDF comes back, stop. Do not start 0008 until the owner says it works.
3. Gate 3, during 0008 to 0021. At most one PR a day. Each PR is deployed to staging and clicked through before the next one is opened. Put a one-sentence summary at the top of every PR description. If the owner cannot follow it, he does not merge.
4. Gate 4, first real host. 0001 to 0021 merged, a Doručenka received in Gate 2, every health check green, `UBYHOST_RETENTION_AUTOPURGE=1`, and `UBYHOST_GUEST_LANGS` holds only languages a native speaker has read.

0022 to 0034 wait until real hosts use the app. Open one only when the owner asks for it.

## Permanent rules

0. **UbyPort filing correctness is non-negotiable.** Correct `ZapisUbytovane` requests, response parsing, Doručenka PDF storage, and no double-filing outweigh any other goal. See `docs/UBYPORT_CORE.md`. HIGH-risk WPs in the filing row (0006, 0007, 0018, …) need explicit filing tests and owner Gate 2 when the workplan says so.
1. Do only what the WP says. Anything else that looks wrong goes in the PR under "Noticed, not changed".
2. Match the existing code style. No new dependency.
3. Never commit secrets, operator identity, real guest data or `.env` values (AGENTS.md).
4. Every user-visible string in EN and CS through `host_i18n.py`, `i18n.py` or `guide_i18n.py`.
5. No analytics or third-party script on app pages, guest pages (`/l/...`, including the pick page) or auth pages. Only public marketing and legal pages may load Umami. A guard test enforces it.
6. The database claim (`claim_sendable`) is the only guard against double filing. Never call UbyPort or fetch a feed inside an open transaction.
7. All SQL through the `db.py` helpers, parameterised. No new triggers, no SQLite-only syntax, small `with db.immediate()` blocks. New schema changes as numbered migration files once WP18 is in.
8. If a patch's assumption about the code is wrong, stop at that point, describe it in the PR, propose the smallest fix.
9. Apply every patch exactly as written. Do not rewrite, "improve" or reorder a patch, and never edit an earlier patch. Later patches are built on the exact text of earlier ones, so any change breaks everything after it. A fix goes in as a new commit on top of the PR and is described in the PR.
10. Do not regenerate the series or move a patch. Moving 0029 (WP16) before 0022 was tried and conflicts in `db.py`.
