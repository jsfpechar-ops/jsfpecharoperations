# Domain: <name>

Cap 1,000 tokens. One per domain (e.g. auth, billing, legal). Link out instead of copying text from elsewhere.

**Scope:** which user-visible features and which files (`App/app/...`).

**Invariants:** rules that must always hold; each one points to the test that pins it.

**Data:** the tables and columns it owns, and the retention line in `App/app/retention.py`.

**External:** outbound requests and processors, linked to `docs/privacy/ROPA.md`.

**Open:** the K- IDs in [known-issues](../known-issues.md) and the plan in `docs/plans/`.
