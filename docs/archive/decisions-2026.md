# Decisions archive 2026

Moved from docs/context/decisions.md during compaction.
- 2026-10-06 | [workflow] Task 0001 merged (#281) before orchestrator review; review post-merge approved; stale PR cleanup remains owner-run | owner merged early | [0001 report](../tasks/0001-report.md)
- 2026-10-06 | [workflow] Context-rollout bundle: flat files only; MANIFEST at root | place_files paths | [TEMPLATE](../tasks/TEMPLATE.md)
- 2026-10-06 | [workflow] Opus plans/briefs/reviews; Cursor executes (Composer/Kimi/GLM) | Opus used 92% of $1,588/30d | [workflow](workflow.md)
- 2026-10-06 | Cloudflare MCP servers removed from the local Cursor MCP config | context cost in every chat, and production DNS/WAF access for agents | task 0001
- 2026-10-06 | Cursor automations (regression coverage, bug sweep) stay as they are and read known-issues.md | owner choice | [prompts](prompts.md#bug-hunt-automation)
- 2026-09-26 | Every change goes through an owner-reviewed PR; production deploy is manual only | safety | [rules](rules.md#merging-and-deploying)
- 2026-09-26 | Invoices standalone/host-only; guest stay fee on hold; optional host remittance tool built | scope | [plans](../plans/README.md)
- 2026-10-03 | Filing: one automatic retry, then red plus mail to the host; code 150 = success; pause after repeated wrong UbyPort passwords | the police account can lock | P
- 2026-10-04 | Lightsail 8 GB / 2 vCPU (~$44/month) | headroom for worker and Litestream | [LIGHTSAIL](../LIGHTSAIL.md#production-instance-ubyhostcom)
- 2026-10-05 | Umami only on public pages; in-app metrics server-side | privacy first | [rules](rules.md#privacy)
- 2026-10-05 | Ticket Wallet guest UI archived (kept in `App/app/static/archive/`), may return | simpler guest form | -
