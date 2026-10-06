# UbyHost: agent entry point

Read this file, then [status](docs/context/status.md). Open nothing else unless a routing row below says so.
**Never audit the whole repo** unless the owner asks for it in the current chat.

## Roles

- **Orchestrator** (Opus): plans, writes briefs in `docs/tasks/`, reviews reports. Never edits `App/`.
- **Executor** (Cursor: composer, Kimi or GLM only): follows one brief exactly. Reads only this file, the brief and the files the brief names.
- **Owner** (Josef): merges, deploys, secrets, servers. Give him numbered click-by-click steps in plain words.

## Hard rules (full text: [rules](docs/context/rules.md))

1. UbyPort filing correctness beats every other feature ([UBYPORT_CORE](docs/UBYPORT_CORE.md)).
2. Privacy first: store only what the law or a feature needs. No tracking cookies (`App/tests/test_privacy_first.py`), no third-party scripts except Turnstile. New personal-data field: add a line in `App/app/retention.py`. New outbound request: give the reason in the PR.
3. Public repo: never commit secrets, `.env`, databases, guest data or operator identity.
4. No new dependency without an owner decision line in [decisions](docs/context/decisions.md).
5. SQL only through `App/app/db.py` helpers, Postgres-portable. A schema change is a new `App/app/migrations/` file.
6. Light mode only. Auth forms work without JavaScript.
7. Template, CSS or guest-page change: browser and geometry tests pass with 0 skipped, plus screenshots in the report.
8. Never push to `main`. Merge only with `scripts/merge-pr-on-green.sh`. Production deploy is manual, done by the owner.
9. Copy: one explanation lives in one place; no sentence the button already says; write "no tracking cookies", never "no cookies".

## Test

From `App/`: `.venv/bin/python -m pytest tests -q` (never set `PYTHONPATH=App`). From the repo root: `python3 scripts/context_lint.py`.

## Routing (open only your row; in long files read one section: `grep -n '^## '`, then that range)

| Touching | Read |
|---|---|
| UbyPort, submission, claim, automation | [UBYPORT_CORE](docs/UBYPORT_CORE.md), [submit_state](docs/OPERATIONS.md#the-submit_state-state-machine) |
| Guest pages | [Arrival lane](docs/DESIGN.md#guest-registration-arrival-lane-active), [rules: guest pages](docs/context/rules.md#guest-pages) |
| Host UI | [HOST_APP_DESIGN](docs/HOST_APP_DESIGN.md) (that page's section), [geometry](docs/DESIGN.md#action-geometry) |
| Database, migrations | [rules: database](docs/context/rules.md#database) |
| Personal data, retention, legal copy | [RETENTION](docs/privacy/RETENTION.md), [ROPA](docs/privacy/ROPA.md), [legal positions](docs/UbyHost_workplan/04_legal_positions.md#summary-of-decisions) |
| Auth, sessions, secrets | [SECURITY](docs/SECURITY.md), [rules: secrets](docs/context/rules.md#secrets) |
| Env vars | [ENVIRONMENT](docs/ENVIRONMENT.md) (one section) |
| Deploy, server, backups | [LIGHTSAIL](docs/LIGHTSAIL.md), [backups](docs/OPERATIONS.md#backup-and-restore) |
| Mail | [SES](docs/SES.md), [rules: mail](docs/context/rules.md#mail) |
| A bug, or "is X known?" | `grep` [known-issues](docs/context/known-issues.md) for the file or area |
| Where code lives, a term, why a choice | [architecture](docs/context/architecture.md), [glossary](docs/context/glossary.md), `grep` [decisions](docs/context/decisions.md) |
| Old audit or patch detail | [archive index](docs/archive/README.md), then one section only |

## Session protocol (details: [workflow](docs/context/workflow.md))

- **Start:** read this file, then status, then your routed row. Grep before you read. Read ranges, never whole files over 300 lines. If something is unclear, ask the owner instead of exploring.
- **End (orchestrator):** update status (5 lines at most), append to decisions and known-issues, run the lint. A workflow change gets a `[workflow]` decision and a [workflow](docs/context/workflow.md) edit.
- One chat per task. Close the chat when the brief or the review is done.
