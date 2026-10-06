# Context system

The goal: every session starts from about 3–5k tokens of trusted context instead of an audit. The lint (`scripts/context_lint.py`) enforces the caps.

**Layers**

- **L0:** `AGENTS.md`, always loaded. Cursor and Claude Code (via `CLAUDE.md`) read it automatically.
- **L1:** this folder, opened on demand through the AGENTS.md routing table.
- **L2:** `docs/plans/` and the domain docs, opened only for that feature.
- **Archive:** `docs/archive/`, never read by default. Use the [index](../archive/README.md).

**Files** (token cap; size = characters ÷ 4)

| File | Purpose | Cap |
|---|---|---|
| `AGENTS.md` | Roles, hard rules, routing, protocol | 1,500 |
| [status](status.md) | Production, now, next, blocked, owner steps done | 700 |
| [decisions](decisions.md) | Append-only, one line each | 2,000 |
| [known-issues](known-issues.md) | Open bugs and findings (grep it) | 2,500 |
| [rules](rules.md) | Full text of the hard rules | 2,500 |
| [architecture](architecture.md) | Stack and code map | 1,500 |
| [workflow](workflow.md) | Process, triggers, compaction | 1,800 |
| [glossary](glossary.md), [prompts](prompts.md) | Terms; paste-ready prompts | 700 / 800 |
| `domains/<name>.md` | Only when a domain outgrows one architecture row | 1,000 |
| Task brief / report | `docs/tasks/` | 12,000 / 1,500 |

**New domain** (e.g. auth after passkeys): copy `docs/context/domains/_template.md` to `domains/<name>.md`, add one routing row in AGENTS.md, and add one decisions line.

**Baseline** (spend-doctor, 30 days to 2026-10-06, this Mac)

- $1,588 total, 91.8 % Opus.
- 86.6 % of cost was carried context.
- Peak session averaged 340k context tokens.
- 62 stale-cache rewrites (about $137).

Cursor, in the same period: 142 cloud chats, 101 of them auto-spawned subagents, plus 5+ repeated whole-repo audits.
