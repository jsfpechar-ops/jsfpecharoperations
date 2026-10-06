# Decisions

Append-only, one line each: `date | decision | reason | link`.

- Tags: `[workflow]` = a process change; also edit [workflow](workflow.md) and [prompts](prompts.md) when you add one.
- Find past decisions with `grep -i <topic>`. Don't read this file whole.
- Superseded lines stay; add a new line that says what it supersedes.
- When the file goes over its cap, entries older than 90 days that nothing references move to `docs/archive/decisions-YYYY.md`.

- 2026-09-09 | Core product = automatic UbyPort filing plus the house book (uvítací kniha); everything else is optional | the owner's founding rule | [UBYPORT_CORE](../UBYPORT_CORE.md)
- 2026-09-13 | Production on AWS Lightsail; Render is staging with mock UbyPort, permanently | cost, control | [LIGHTSAIL](../LIGHTSAIL.md)
- 2026-09-14 | Hosts use TOTP 2FA + 8 recovery codes, forced in production; Turnstile on login and guest PIN | security | [SECURITY](../SECURITY.md)
- 2026-09-16 | Light mode only; dark mode parked | owner policy | [DESIGN](../DESIGN.md#color-mode-light-only-no-dark-mode)
- 2026-09-18 | Mail via AWS SES (no-reply@ubyhost.com, DKIM) | already on AWS; keeps SMS/login options open | [SES](../SES.md)
- 2026-09-26 | Every change goes through an owner-reviewed PR; production deploy is manual only | safety | [rules](rules.md#merging-and-deploying)
- 2026-09-26 | Invoices: standalone and host-only; the guest-facing stay fee is on hold; the host-only stay-fee remittance tool is built and optional | scope | [plans](../plans/README.md)
- 2026-10-03 | Stay fee charged per started day (arrival, departure]; use the rate the period was saved with | under-charging is the host's liability | P Q-answers
- 2026-10-03 | Filing: one automatic retry, then red plus mail to the host; code 150 = success; pause after repeated wrong UbyPort passwords | the police account can lock | P
- 2026-10-03 | Sign-up stays off in production (`UBYHOST_SIGNUP_ENABLED`) until the owner chooses | launch with invited hosts | [ENVIRONMENT](../ENVIRONMENT.md#accounts)
- 2026-10-04 | Lightsail 8 GB / 2 vCPU (~$44/month) | headroom for worker and Litestream | [LIGHTSAIL](../LIGHTSAIL.md#production-instance-ubyhostcom)
- 2026-10-05 | WP22/WP24 legal texts 1.6 shipped without the counsel gate; lawyer review stays open | ship with real hosts | K-L rows
- 2026-10-05 | Umami only on public pages; in-app metrics server-side | privacy first | [rules](rules.md#privacy)
- 2026-10-05 | Admin preview: full workspace access, reason optional, 24 h default | the owner must be able to support hosts | PR #280, K-P01
- 2026-10-05 | Ticket Wallet guest UI archived (kept in `App/app/static/archive/`), may return | simpler guest form | -
- 2026-10-06 | [workflow] Opus orchestrates only (plans, briefs, reviews); Cursor executes with composer, Kimi or GLM only | Opus was 92% of $1,588 per 30 days | [workflow](workflow.md)
- 2026-10-06 | [workflow] Context system: AGENTS.md L0 + `docs/context/` L1 + `docs/plans/` L2; audits archived; known-issues.md replaces FOLLOWUPS.md | 87% of spend was re-read context | [README](README.md)
- 2026-10-06 | [workflow] WP/patch series closed at WP33/0034; new work uses task numbers NNNN | one numbering scheme | [workflow](workflow.md)
- 2026-10-06 | [workflow] At most one council per plan, only for HIGH RISK (filing, deletion, legal); never per PR | 3 councils in one day found the same issues | [workflow](workflow.md)
- 2026-10-06 | Cloudflare MCP servers removed from the local Cursor MCP config | context cost in every chat, and production DNS/WAF access for agents | task 0001
- 2026-10-06 | Cursor automations (regression coverage, bug sweep) stay as they are and read known-issues.md | owner choice | [prompts](prompts.md#bug-hunt-automation)
- 2026-10-06 | [workflow] Task 0001 merged (#281) before orchestrator review; review post-merge approved; stale PR cleanup remains owner-run | owner merged early | [0001 report](../tasks/0001-report.md)
- 2026-10-06 | [workflow] Context-rollout upload: flat files only in the rollout bundle folder (no subfolder); MANIFEST at bundle root | place_files script paths | [TEMPLATE](../tasks/TEMPLATE.md)
- 2026-10-06 | Downloads opt out of the navigation skeleton by `download` / `data-no-skeleton` plus a path-ending rule, pinned by a template scan test | a stay-fee PDF click blanked the page for 15 s | skeleton.js
- 2026-10-06 | Stay-fee PDF: host bed-day adjustments fold into the facility row (no "Úprava výpočtu" line); the CSV register keeps one neutral line "přenocování bez záznamu hosta" so it adds up to the payment | owner: a correction line looks wrong to the office; council: register must reconcile | stay_fee.py
- 2026-10-06 | UbyPort outcome by police severity: 0-2 accepted, 4-6 not accepted; 112 = reported late = accepted (supersedes "112 = batch not received") | police letter CPR-34587-2/ČJ-2026-930023, A1-A5 | [OPERATIONS](../OPERATIONS.md#ubyport-error-codes-and-what-112-and-150-really-do)
- 2026-10-06 | The sweep sends a refused record once, then waits for the host to fix it (was 3 tries) | police B2-B3: resending refused data counts against the host | [OPERATIONS](../OPERATIONS.md#ubyport-error-codes-and-what-112-and-150-really-do)
- 2026-10-06 | Staging may target the police test environment (`ubyport_env=test`) with the issued UBY-WS test account; credentials only in the staging app, never in git | police B4: test behaves like production | [LIGHTSAIL](../LIGHTSAIL.md)
- 2026-10-06 | Abbreviation (zkratka) check accepts 5-6 letters or digits | the police issued a 6-character test abbreviation | validation.py
