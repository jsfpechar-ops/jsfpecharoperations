# 0459: Tenancy audit of host-facing routes (read-only)
Status: todo
Depends on: none | Base commit: main | Branch: task/0459-tenancy-audit
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 60k tokens
## 1. Objective
Produce the list of database reads and writes reachable by a logged-in host that are not scoped to that host. No code changes. The fix briefs are written from this list by the orchestrator.
## 2. Context
Hosts are scoped by `host_id`/`user_id` columns and, for guests, a signed cookie of owned guest ids (`App/app/routes/guest.py:_owned_ids`). There is no row-level security. Routes contain about 63 bare `WHERE id = ?` lookups; many are in platform-admin routes and are fine. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 3.
## 3. Files (read only)
`App/app/routes/*.py` except `admin*.py` and `signup.py`; `App/app/auth.py` (how role and host are attached to the request).
## 4. Steps
1. For each route file: `grep -n "WHERE id = ?\|WHERE id=?\|WHERE slug = ?\|WHERE token = ?" <file>`.
2. For every hit, read the 15 lines above it and record: route path, HTTP method, table, the id's source (path, query, form, cookie), and whether an ownership check happens before or after (`host_id = ?`, `_owned_ids`, `owned_entity`, a role check).
3. Classify: OK (scoped), ADMIN (admin-only route), LEAK (host-reachable, unscoped), WRITE-LEAK (same, for UPDATE/DELETE).
4. For each LEAK/WRITE-LEAK: the exact fix in one line (add `AND host_id = ?` with the session host id, or route through an existing helper).
## 5. Acceptance
One table in the report with every hit; counts per class; no file edited.
## 6. Report
`docs/tasks/0459-report.md`, under 150 lines.
