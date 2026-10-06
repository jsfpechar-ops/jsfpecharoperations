# Archive index

These files are historical and are not read by default. Their open findings were distilled into [known-issues](../context/known-issues.md) on 2026-10-06.

- Open one only if a K- row or a decision cites it.
- Then `grep -n '^#'` the file and read one section.

| Path (under `docs/archive/`) | What it is | Superseded by |
|---|---|---|
| `FOLLOWUPS.md` | Follow-up findings, phases 1–6 (W, BE, LD, MK ids) | known-issues |
| `UBYHOST_CODE_AUDIT.md`, `SECURITY_REVIEW_2026-09-15.md`, `PHASE_1-6_REVIEW_2026-09-24.md`, `TECHNICAL_COMPLIANCE_AUDIT.md` | Audits from September 2026 | known-issues (K-S, K-L) |
| `plans/UbyHost_prelaunch_review/` | Prelaunch review A01–A77, owner answers Q1–Q12, plan T01–T151 (applied) | known-issues (K-F, K-I), decisions |
| `plans/UbyHost_Audit_and_Cursor_Plan_2026-09-28.md` | Architecture and reliability audit, AR-01…AR-51 | known-issues |
| `plans/GDPR_COMPLIANCE_REVIEW_2026-09-27.md`, `plans/GDPR_REMEDIATION_PLAN.md` | GDPR review and plan (code shipped; G-D owner decisions partly open) | known-issues (K-L, K-P) |
| `plans/UX_AUDIT.md`, `plans/UX_IMPLEMENTATION_REVIEW.md`, `plans/PLAN_UX_UI_OVERHAUL.md` | UX audit (162 items, about 151 landed) and its review | known-issues (K-U) |
| `plans/host-app-redesign/` | Host redesign evidence and preview (built) | `docs/HOST_APP_DESIGN.md` |
| `plans/PLAN_TICKET_WALLET_V2.md` | Ticket Wallet guest UI (archived; may return) | `App/app/static/archive/ticket-wallet/README.md` |
| `plans/PLAN_POPLATEK_Z_POBYTU.md` | Guest-facing stay fee (on hold) | - |
| `plans/THREE_PLAN_GITHUB_DELIVERY.md` | October 1 three-branch rollout (done) | - |
| `UbyHost_workplan/series/`, `UbyHost_workplan/notes/` | Patches 0001–0034 / WP01–WP33 and their notes (all merged, PR #237) | git history |
| `UbyHost_workplan/0*.md`, `MERGE_SEQUENCE.md`, `OWNER_*.md`, `STAGING_ON_RENDER_STEP_BY_STEP.md`, `UbyHost_architecture_review.md`, `skills/` | Workplan guides, checklists, council verdicts, owner how-tos | status, workflow |
| `SKILL.md`, `LOGO_PROMPT.md`, `NEXT_MAIL_RELEASE.md` | Review-council skill, old logo brief, mail release record | - |

Still live in `docs/UbyHost_workplan/`: `04_legal_positions.md` (legal decisions), `03_when_triggered.md` (later items: S3 blobs, Postgres, Stripe) and `compliance/`.
