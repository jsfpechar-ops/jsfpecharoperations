# 1261: deploy switch `UBYHOST_SCHEMA_APPLY` (python | go)

Status: todo
Depends on: 1260 merged | Base commit: a83df54 (plus 1260) | Branch: task/1261-go-schema-deploy-switch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations, deploy path). Plan: docs/plans/go-full-move.md Lane D, step D1.

## 1. Objective

`deploy/lightsail/scripts/deploy.sh` learns `UBYHOST_SCHEMA_APPLY`: unset, empty or `python` keeps today's `pg_schema.py apply`; `go` builds the new Go image first and runs `ubyhost-web migrate apply --expect-database ubyhost` (brief 1260) in it; any other value stops the deploy before it touches the stack. Default stays Python, so merging changes nothing until the owner sets `go` in the server `.env`.

## 2. Context

Today (deploy.sh, PG_MODE=1 branch, after the image build):

```bash
  echo "==> Applying PostgreSQL goose migrations (new image)"
  if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
    scripts/pg_schema.py apply --expect-database ubyhost; then
```

The Go image was only built later, in the block `if docker compose config --services | grep -qx 'ubyhost-go'; then` ("Rebuild the local Go image"), and only when `COMPOSE_PROFILES` has `go`. In go mode the build moves before the apply and uses `--profile go`, so it works whether or not the profile is enabled (checked with Docker Compose v5.6: `docker compose --profile go config --services` lists `ubyhost-go`; `run` has `--no-deps` and `-T`). `--no-deps` skips the service's `depends_on: ubyhost (healthy)`. The Go image's entrypoint is `/usr/local/bin/ubyhost-web` and it sets `UBYHOST_MIGRATIONS_DIR=/app/migrations_pg`; compose gives it `UBYHOST_DATABASE_URL`, `UBYHOST_DATA_DIR=/data` (read-only volume: Go only reads the marker; the Go and Python images both run as uid 10001, so the 0600 marker is readable), and the PostgreSQL socket volume. A failed build or apply exits before `up`, exactly as the Python path does. The later Go rebuild block is skipped in go mode (already built).

`deploy/lightsail/scripts/pg-cutover.sh` is NOT changed: it is the one-time SQLite to PostgreSQL copy, which needs Python's SQLite schema code and builds an empty database (Go apply refuses an empty database by design).

The edit script below was dry-run on base a83df54: it produced the expected diff at the end of this brief, `bash -n` and `shellcheck -S error` passed, and a copy of deploy.sh with `.env` `UBYHOST_SCHEMA_APPLY=bogus` exited 1 with `UBYHOST_SCHEMA_APPLY must be python or go (got 'bogus'); refusing deployment.`; with `go` and no `UBYHOST_DATABASE_URL` it exited 1 with `UBYHOST_SCHEMA_APPLY=go needs PostgreSQL (UBYHOST_DATABASE_URL); refusing deployment.`

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/deploy.sh | edit (step 1 script) | switch check after PG_MODE; go branch in the apply step; skip the later Go rebuild in go mode |
| docs/LIGHTSAIL.md | edit (step 1 script) | new subsection "Schema apply: Python or Go" + one day-to-day command row |
| docs/tasks/1261-report.md | new | your report |
| docs/tasks/1261-go-schema-deploy-switch.md | exists | this brief; only its Status line changes |

No other file may change.

## 4. Steps

**Step 1. Apply the edits.** From the repo root, run exactly (the script checks each anchor occurs once and stops otherwise):

```bash
python3 - <<'EOF' 2>&1 | tail -10
from pathlib import Path

DEPLOY = Path("deploy/lightsail/scripts/deploy.sh")
DOCS = Path("docs/LIGHTSAIL.md")


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"anchor not found exactly once in {path}: {old.splitlines()[0]!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"edited {path}")


PG_MODE = '''PG_MODE=0
if [ -n "${UBYHOST_DATABASE_URL:-}" ]; then
  PG_MODE=1
fi
'''
replace_once(DEPLOY, PG_MODE, PG_MODE + '''
# 1261: which code applies the PostgreSQL goose files. python (the default,
# also when unset or empty) runs App/scripts/pg_schema.py in the new ubyhost
# image; go runs `ubyhost-web migrate apply` in the new ubyhost-go image. Both
# write the same goose_db_version rows, so either can follow the other.
# Checked here, before anything touches the stack.
SCHEMA_APPLY="${UBYHOST_SCHEMA_APPLY:-python}"
case "${SCHEMA_APPLY}" in
  python) ;;
  go)
    if [ "${PG_MODE}" != "1" ]; then
      echo "UBYHOST_SCHEMA_APPLY=go needs PostgreSQL (UBYHOST_DATABASE_URL); refusing deployment." >&2
      exit 1
    fi
    ;;
  *)
    echo "UBYHOST_SCHEMA_APPLY must be python or go (got '${SCHEMA_APPLY}'); refusing deployment." >&2
    exit 1
    ;;
esac
''')

replace_once(DEPLOY, '''  echo "==> Applying PostgreSQL goose migrations (new image)"
  if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \\
    scripts/pg_schema.py apply --expect-database ubyhost; then
    echo "Goose apply failed." >&2
    exit 1
  fi
  echo "Goose migrations applied."
''', '''  if [ "${SCHEMA_APPLY}" = "go" ]; then
    # 1261: build the new Go image first, so the apply runs the merged code.
    # --profile go: the service is profile-gated and may not be enabled.
    echo "==> Building the Go image for the schema apply"
    if ! docker compose --profile go build ubyhost-go; then
      echo "Go image build failed." >&2
      exit 1
    fi
    echo "==> Applying PostgreSQL goose migrations (new Go image)"
    if ! docker compose --profile go run --rm --no-deps -T ubyhost-go \\
      migrate apply --expect-database ubyhost; then
      echo "Goose apply failed." >&2
      exit 1
    fi
  else
    echo "==> Applying PostgreSQL goose migrations (new image)"
    if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \\
      scripts/pg_schema.py apply --expect-database ubyhost; then
      echo "Goose apply failed." >&2
      exit 1
    fi
  fi
  echo "Goose migrations applied."
''')

replace_once(DEPLOY, '''if docker compose config --services | grep -qx 'ubyhost-go'; then
  # Rebuild the local Go image so a merged change reaches production.
  # Runs before "up", so a failed build leaves the running stack untouched.
''', '''if [ "${SCHEMA_APPLY}" != "go" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
  # Rebuild the local Go image so a merged change reaches production.
  # Runs before "up", so a failed build leaves the running stack untouched.
  # With UBYHOST_SCHEMA_APPLY=go it was built before the schema apply.
''')

ROLLBACK = '''Rollback **UbyPort target** (test ↔ prod): edit `.env` `UBYHOST_UBYPORT_ENV`, then `./scripts/deploy.sh`.
'''
replace_once(DOCS, ROLLBACK, ROLLBACK + '''
### Schema apply: Python or Go (`UBYHOST_SCHEMA_APPLY`)

On PostgreSQL, `deploy.sh` applies pending goose files (`App/migrations_pg/`) with the new image before `up`; a failure stops the deploy and the running stack stays as it was. `.env` `UBYHOST_SCHEMA_APPLY` picks the code that does it:

| Value | What runs |
|---|---|
| unset, empty or `python` (default) | `scripts/pg_schema.py apply --expect-database ubyhost` in the new `ubyhost` image |
| `go` | The Go image is built first, then `docker compose --profile go run --rm --no-deps -T ubyhost-go migrate apply --expect-database ubyhost` (works whether or not `COMPOSE_PROFILES` has `go`) |
| anything else | `deploy.sh` stops before touching the stack; `go` on SQLite stops too |

The Go command (`ubyhost-web migrate plan|check|apply --expect-database <db>`) makes the same checks as Python: the public schema, the database name, and the authority marker in `/data/database-authority.json` (database, schema and URL fingerprint). It takes the same advisory locks, runs every pending goose file in one transaction and commits only when the schema then matches what the app expects. It applies goose files only: a fresh, empty database still needs `pg_schema.py apply` (or `pg-cutover.sh`) once, and Go refuses with "legacy schema not set up". `pg-cutover.sh` stays Python-only: it copies SQLite data, and Go has no SQLite.

Rollback: remove `UBYHOST_SCHEMA_APPLY` from `.env` (or set it to `python`), then `./scripts/deploy.sh`. Both write the same `goose_db_version` rows, so either one can take over from the other at any time.
''')

ROW = '''| `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost` | Apply pending PostgreSQL goose migrations (`App/migrations_pg/`) after a deploy whose notes mention a goose file; the app will not start while one is pending |
'''
replace_once(DOCS, ROW, ROW + '''| `docker compose --profile go run --rm --no-deps ubyhost-go migrate check --expect-database ubyhost` | Go check of the PostgreSQL schema (`plan` lists pending goose files, `apply` applies them); see [Schema apply](#schema-apply-python-or-go-ubyhost_schema_apply) |
''')
EOF
```

Expected: `edited deploy/lightsail/scripts/deploy.sh` three times, `edited docs/LIGHTSAIL.md` twice. An `AssertionError: anchor not found`: STOP (§8).

**Step 2. Verify.**

```bash
sha256sum deploy/lightsail/scripts/deploy.sh docs/LIGHTSAIL.md 2>&1 | tail -3
```

Expected when neither file changed on main since a83df54:

```
886b17054b6b1ba09adff9c9150124ab090626d99240689c103ba274adffc2c5  deploy/lightsail/scripts/deploy.sh
3fa0684853e3f17d1e3f4ebde90e11f622f6b55122509d74d6f0cebdbf644f0e  docs/LIGHTSAIL.md
```

If a value differs, run `git log --oneline a83df54..HEAD -- deploy/lightsail/scripts/deploy.sh docs/LIGHTSAIL.md 2>&1 | tail -5`. No commit listed: STOP. A commit listed: compare `git diff` with "Expected diff" below; the + and - lines must be identical (only line numbers may move). Write which in Deviations. Then `bash -n deploy/lightsail/scripts/deploy.sh && echo syntax ok`. Commit: `git add deploy/lightsail/scripts/deploy.sh docs/LIGHTSAIL.md && git commit -m "1261 step 1-2"`.

**Step 3. Refusal check** (touches no Docker; deploy.sh stops before anything runs):

```bash
T=$(mktemp -d) && mkdir "$T/scripts" && cp deploy/lightsail/scripts/deploy.sh "$T/scripts/" && echo 'UBYHOST_SCHEMA_APPLY=bogus' > "$T/.env" && bash "$T/scripts/deploy.sh"; echo "rc=$?"; echo 'UBYHOST_SCHEMA_APPLY=go' > "$T/.env" && bash "$T/scripts/deploy.sh"; echo "rc=$?"; rm -rf "$T"
```

Expected: the two refusal lines quoted in §2, each followed by `rc=1`.

**Step 4.** Run §6, write the report (§9).

## 5. Do not touch

- `deploy/lightsail/scripts/pg-cutover.sh`, `deploy/lightsail/docker-compose.yml`, `go/Dockerfile`, `deploy/lightsail/scripts/preflight.sh`, everything under `go/` and `App/`.
- `docs/ENVIRONMENT.md`, `docs/context/*` (coordinator-only).
- Never run `deploy.sh` for real, never touch a server or `.env` (rules 3 and 8). Never push to main.

## 6. Commands

```bash
shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -10
```

Expected: no output. If `shellcheck` is not installed, write that in the report; CI job `shellcheck` runs it.

```bash
python3 scripts/context_lint.py 2>&1 | tail -3
```

Expected last line: `context lint: OK`.

## 7. Acceptance

- [ ] Step 1 printed 5 `edited` lines; step 2 sha256 match (or the identical-diff deviation); `bash -n` ok.
- [ ] Step 3: both refusals, `rc=1` twice.
- [ ] `git diff --stat` lists only deploy.sh and LIGHTSAIL.md (plus the report).
- [ ] After push: CI `shellcheck` green.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, or the diff differs from "Expected diff";
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1261-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`deploy/lightsail/scripts/deploy.sh` full diff: the switch must run before any Docker command; the go branch must build before it applies and exit 1 on either failure before `up`; the python branch must be byte-identical to today's command; the later Go rebuild must still run in python mode.

## Owner steps (after 1260 and 1261 are merged and deployed; do this on a quiet day)

1. SSH to the server and go to the stack folder:

```bash
cd /opt/ubyhost/deploy/lightsail
```

2. Build the Go image and run the read-only Go check (changes nothing):

```bash
docker compose --profile go build ubyhost-go && docker compose --profile go run --rm --no-deps -T ubyhost-go migrate check --expect-database ubyhost
```

It must print `PostgreSQL schema check OK: database=ubyhost, version=..., tables=..., goose=...`. If it prints `failed` instead, stop here and send that line to the orchestrator.

3. Switch the deploy to Go: open `.env` (`nano .env`), add the line `UBYHOST_SCHEMA_APPLY=go`, save.

4. Deploy once: GitHub, Actions, Deploy production, Run workflow, type DEPLOY. In the log look for `==> Applying PostgreSQL goose migrations (new Go image)` and `Goose migrations applied.`

5. Rollback at any time: delete the `UBYHOST_SCHEMA_APPLY=go` line from `.env` and deploy again (step 4). Both paths write the same `goose_db_version` rows.

## Notes for the coordinator (lines to add; threads do not edit these files)

- `docs/ENVIRONMENT.md`, deploy section, new row: `| UBYHOST_SCHEMA_APPLY | python | PostgreSQL only, read by deploy.sh. go: apply goose files with ubyhost-web migrate apply in the new Go image (built first) instead of pg_schema.py; anything but python/go/empty stops the deploy. Rollback: remove it and deploy. [LIGHTSAIL](LIGHTSAIL.md#schema-apply-python-or-go-ubyhost_schema_apply) |`
- `docs/context/decisions.md`: `[deploy] 2026-11-13 deploy.sh UBYHOST_SCHEMA_APPLY=python|go chooses the goose apply; default python; pg-cutover.sh stays Python (SQLite copy, empty target). pg_schema.py is removed only after one clean production week on go. Brief 1261.`
- Lane DR step 6 (filing guard in deploy.sh/preflight) also edits `deploy.sh`: do not run it at the same time as this brief.

## Expected diff (on base a83df54)

~~~~diff
diff --git a/deploy/lightsail/scripts/deploy.sh b/deploy/lightsail/scripts/deploy.sh
index 29d09e4..e88dd8b 100755
--- a/deploy/lightsail/scripts/deploy.sh
+++ b/deploy/lightsail/scripts/deploy.sh
@@ -22,6 +22,26 @@ if [ -n "${UBYHOST_DATABASE_URL:-}" ]; then
   PG_MODE=1
 fi
 
+# 1261: which code applies the PostgreSQL goose files. python (the default,
+# also when unset or empty) runs App/scripts/pg_schema.py in the new ubyhost
+# image; go runs `ubyhost-web migrate apply` in the new ubyhost-go image. Both
+# write the same goose_db_version rows, so either can follow the other.
+# Checked here, before anything touches the stack.
+SCHEMA_APPLY="${UBYHOST_SCHEMA_APPLY:-python}"
+case "${SCHEMA_APPLY}" in
+  python) ;;
+  go)
+    if [ "${PG_MODE}" != "1" ]; then
+      echo "UBYHOST_SCHEMA_APPLY=go needs PostgreSQL (UBYHOST_DATABASE_URL); refusing deployment." >&2
+      exit 1
+    fi
+    ;;
+  *)
+    echo "UBYHOST_SCHEMA_APPLY must be python or go (got '${SCHEMA_APPLY}'); refusing deployment." >&2
+    exit 1
+    ;;
+esac
+
 # 0710: rollback target. .deployed-sha is written only when a deploy finished;
 # before the first one, ORIG_HEAD is the commit the workflow reset away from.
 PREV_SHA="$(cat .deployed-sha 2>/dev/null || git rev-parse -q --verify ORIG_HEAD 2>/dev/null || true)"
@@ -218,11 +238,27 @@ fi
 if [ "${PG_MODE}" = "1" ]; then
   # PostgreSQL: apply pending goose files with the new image, before the stack
   # starts. A failure exits here, before `up` touches the running stack.
-  echo "==> Applying PostgreSQL goose migrations (new image)"
-  if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
-    scripts/pg_schema.py apply --expect-database ubyhost; then
-    echo "Goose apply failed." >&2
-    exit 1
+  if [ "${SCHEMA_APPLY}" = "go" ]; then
+    # 1261: build the new Go image first, so the apply runs the merged code.
+    # --profile go: the service is profile-gated and may not be enabled.
+    echo "==> Building the Go image for the schema apply"
+    if ! docker compose --profile go build ubyhost-go; then
+      echo "Go image build failed." >&2
+      exit 1
+    fi
+    echo "==> Applying PostgreSQL goose migrations (new Go image)"
+    if ! docker compose --profile go run --rm --no-deps -T ubyhost-go \
+      migrate apply --expect-database ubyhost; then
+      echo "Goose apply failed." >&2
+      exit 1
+    fi
+  else
+    echo "==> Applying PostgreSQL goose migrations (new image)"
+    if ! docker compose run --rm --no-deps -T --entrypoint python ubyhost \
+      scripts/pg_schema.py apply --expect-database ubyhost; then
+      echo "Goose apply failed." >&2
+      exit 1
+    fi
   fi
   echo "Goose migrations applied."
 elif [ -n "${BACKUP_STAMP}" ]; then
@@ -239,9 +275,10 @@ elif [ -n "${BACKUP_STAMP}" ]; then
   echo "Migration dry-run passed."
 fi
 
-if docker compose config --services | grep -qx 'ubyhost-go'; then
+if [ "${SCHEMA_APPLY}" != "go" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
   # Rebuild the local Go image so a merged change reaches production.
   # Runs before "up", so a failed build leaves the running stack untouched.
+  # With UBYHOST_SCHEMA_APPLY=go it was built before the schema apply.
   if ! docker compose build ubyhost-go; then
     echo "Go image build failed." >&2
     exit 1
diff --git a/docs/LIGHTSAIL.md b/docs/LIGHTSAIL.md
index 0f15ac6..c8646c1 100644
--- a/docs/LIGHTSAIL.md
+++ b/docs/LIGHTSAIL.md
@@ -202,6 +202,20 @@ cd deploy/lightsail && ./scripts/deploy.sh
 
 Rollback **UbyPort target** (test ↔ prod): edit `.env` `UBYHOST_UBYPORT_ENV`, then `./scripts/deploy.sh`.
 
+### Schema apply: Python or Go (`UBYHOST_SCHEMA_APPLY`)
+
+On PostgreSQL, `deploy.sh` applies pending goose files (`App/migrations_pg/`) with the new image before `up`; a failure stops the deploy and the running stack stays as it was. `.env` `UBYHOST_SCHEMA_APPLY` picks the code that does it:
+
+| Value | What runs |
+|---|---|
+| unset, empty or `python` (default) | `scripts/pg_schema.py apply --expect-database ubyhost` in the new `ubyhost` image |
+| `go` | The Go image is built first, then `docker compose --profile go run --rm --no-deps -T ubyhost-go migrate apply --expect-database ubyhost` (works whether or not `COMPOSE_PROFILES` has `go`) |
+| anything else | `deploy.sh` stops before touching the stack; `go` on SQLite stops too |
+
+The Go command (`ubyhost-web migrate plan|check|apply --expect-database <db>`) makes the same checks as Python: the public schema, the database name, and the authority marker in `/data/database-authority.json` (database, schema and URL fingerprint). It takes the same advisory locks, runs every pending goose file in one transaction and commits only when the schema then matches what the app expects. It applies goose files only: a fresh, empty database still needs `pg_schema.py apply` (or `pg-cutover.sh`) once, and Go refuses with "legacy schema not set up". `pg-cutover.sh` stays Python-only: it copies SQLite data, and Go has no SQLite.
+
+Rollback: remove `UBYHOST_SCHEMA_APPLY` from `.env` (or set it to `python`), then `./scripts/deploy.sh`. Both write the same `goose_db_version` rows, so either one can take over from the other at any time.
+
 ## Day-to-day commands
 
 All from `deploy/lightsail/`:
@@ -222,6 +236,7 @@ All from `deploy/lightsail/`:
 | `./scripts/pg-cutover.sh rollback` | Switch `.env` back to SQLite (type ROLLBACK to confirm) |
 | `./scripts/backup-gdrive.sh` | rclone copy of today's snapshot folder (made by `backup.sh`) to Google Drive |
 | `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost` | Apply pending PostgreSQL goose migrations (`App/migrations_pg/`) after a deploy whose notes mention a goose file; the app will not start while one is pending |
+| `docker compose --profile go run --rm --no-deps ubyhost-go migrate check --expect-database ubyhost` | Go check of the PostgreSQL schema (`plan` lists pending goose files, `apply` applies them); see [Schema apply](#schema-apply-python-or-go-ubyhost_schema_apply) |
 
 Public `GET /healthz` in **production** returns `status`, `version`, `data_dir_writable` only (no env labels). Confirm `ubyport_env` with `./scripts/status.sh` or Settings.
~~~~
