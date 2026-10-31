# PostgreSQL continuation — incomplete drafts

Psycopg 3 and pgBackRest are explicitly owner-approved. Latest owner-supplied AGENTS.md requires Haiku 5.5 execution. No PostgreSQL runtime or operations implementation has been applied to the repository. Production is unchanged.

The adjacent UNREVIEWED-postgresql-runtime.patch and UNREVIEWED-postgresql-operations.patch preserve draft differences against the current working tree, not HEAD. Do not apply automatically. They lack completed review and persisted integration coverage. Earlier bundle files and changes.patch are stale and must not be treated as the final migration kit.

Runtime agent reports real disposable PostgreSQL 18.6 checks for 67 tables/version 33, typed transfer hashes, six invoice guards, sequence highwater, binding, dates, money and writer serialization. These are reported experiments, not a completed test report. Operations has not rehearsed encrypted pgBackRest restore/PITR. Docker and macOS build prerequisites were unavailable. Source drafts remain at /tmp/pg-proposal and /tmp/pg-ops-proposal. Local disposable PostgreSQL is at 127.0.0.1:55432, tools /tmp/pg18.6/bin; no production access was used.

## Next executor prompt

You are Haiku 5.5. Read AGENTS.md, docs/context/executor.md, and docs/tasks/0455-postgresql-runtime-and-transfer.md. Follow that one brief. The runtime draft patch in this directory is unreviewed evidence, not permission to apply it. Prepare the exact source diff and resolve the brief's review gate before implementation. Preserve current unrelated work. Complete persisted PostgreSQL integration tests and SQLite regression checks specified by the brief, then report exact results and remaining limitations. Do not push, merge or deploy. Task 0456 follows separately after 0455 interfaces are settled.

## Remaining deliverables

Runtime exact-diff review, application, dependency locks, persisted tests; operations exact-diff review, runbook, cutover failure tests and actual encrypted restore/PITR rehearsal; reconciliation of both CLI contracts; final complete-file bundle, manifest, placement script and fresh combined patch. Do not label the migration complete until these are finished.
