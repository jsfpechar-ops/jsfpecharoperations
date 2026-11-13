# 1206: App connects to Postgres as a restricted role (K-S11)

Status: todo
Depends on: PR 966 merged (it edits deploy/lightsail/docker-compose.yml; base this branch on main AFTER it merges) | Base commit: 8eb6721eb | Branch: task/1206-postgres-app-role
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add an idempotent owner-run script that creates role `ubyhost_app` (NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN), makes it the owner of every application object, and proves it cannot run `COPY ... PROGRAM`. The owner then flips the user in `UBYHOST_DATABASE_URL` in the server `.env`; backup, WAL-G and restore scripts keep the bootstrap superuser `ubyhost`. A SQL injection then no longer gives file read or command execution in the postgres container (owner decision today: fix K-S11).

## 2. Context

Rules: AGENTS rule 3 (no secrets, no operator identity in the repo), rule 4 (no new dependency), rule 5 applies to app SQL only, not to this ops script. Owner steps are plain numbered words.

Facts found (all verified by the orchestrator; do not re-investigate):

1. **One knob already exists: the DSN user lives in `.env`, not in compose.**
   - The only variable is `UBYHOST_DATABASE_URL` (one DSN for Python web, worker and Go). Form on the server: `postgresql://ubyhost@/ubyhost?host=/var/run/postgresql` (pg-cutover.sh:17; `env-switch` at pg-cutover.sh:56-63 writes it).
   - Python web and worker read it through `env_file: .env` (docker-compose.yml: ubyhost service about line 100; worker about line 155). Go gets it by `UBYHOST_DATABASE_URL: ${UBYHOST_DATABASE_URL:-}` (docker-compose.yml:209). Parsed in App/app/config.py:93-101 and go/cmd/ubyhost-web/main.go:151.
   - All three reach postgres only through the `ubyhost-pgsock` volume (docker-compose.yml:112, 161, 258); the postgres service has `network_mode: none`, `listen_addresses=` empty, `POSTGRES_HOST_AUTH_METHOD: trust` (docker-compose.yml:14-24).
   - **Consequence: no compose change is needed.** Compose keeps `POSTGRES_USER: ubyhost` (the bootstrap superuser, used by admin scripts). A merge and auto-deploy cannot change who the app connects as, because `.env` on the server is not in git.
2. **Who migrates:** `scripts/pg_schema.py apply` (App/app/db.py:1809-1838 `apply_postgresql_schema`: runs `_postgres_schema_ddl`, then the goose files in App/migrations_pg). It runs from deploy.sh:218-224 with `docker compose run ... ubyhost` and therefore with the `.env` DSN user, so after the flip migrations run as `ubyhost_app` and need ownership of the tables (ALTER TABLE) and CREATE on schema `public`. Go only checks for pending goose files (`UBYHOST_MIGRATIONS_DIR`, main.go:165-185); it never applies. App/app/migrations is frozen and SQLite only.
3. **Superuser needs: none found.** grep of App/migrations_pg, App/app/db.py, db_postgres.py, go/ for CREATE EXTENSION, COPY PROGRAM, pg_read_file, ALTER SYSTEM, SET ROLE, SECURITY DEFINER, session_replication_role: no hits. Advisory locks (`pg_advisory_lock`, `pg_advisory_xact_lock`, db.py:965, db_postgres.py:710) are allowed for any role. Triggers and plpgsql functions (db_postgres.py:441-537) are created in `public`, so the app role must own them (the script transfers them).
4. **What else connects as `ubyhost` (all stay superuser, none is changed):** backup.sh:57 (pg_dump), pg-restore.sh:115,120 (pg_restore), pg-cutover.sh:17-19,49,71,142-143, walg-check.sh:31 (psql), the postgres healthcheck (docker-compose.yml:44), the WAL-G sidecar (physical copy via walg-backup.sh:24, wal-push via spool; no SQL login), the drill in docs/OPERATIONS.md:773 (restores with `--no-owner`). CI jobs `test-postgres`, `test-postgres-full`, `go` use the `postgres` user of the service container (ci.yml:177-198, 251, 290), not `ubyhost`. Tests that hardcode `ubyhost@` are URL parsing fixtures only (test_db_postgres.py:1596-1646, test_pg_cutover_script.py:17); they do not change.
5. **Auth:** `trust` over the socket, no password. A second role needs no password; keep it passwordless (the secret-free design). Residual risk to state in SECURITY.md: the app can still reach the superuser by changing the DSN user, but an SQL injection cannot change the DSN.
6. **Restore note:** `pg_restore` without `--no-owner` into a fresh cluster fails on `OWNER TO ubyhost_app` unless the role exists. pg-restore.sh is not changed; the docs line says: on a new cluster run `pg-app-role.sh` first (it works on an empty database). Objects created later by a superuser (restore, cutover) need one re-run of the script.

Design: the SQL lives in `deploy/lightsail/scripts/pg-app-role.sql` (so CI can run it with plain `psql -f`, no docker); `pg-app-role.sh` pipes it into the postgres container. Ownership is moved with explicit `ALTER ... OWNER TO` generated from the catalog (`REASSIGN OWNED` refuses bootstrap-superuser objects). Sequences linked to a table column (serial/identity, `pg_depend.deptype` `a` or `i`) are skipped: they follow the table.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/pg-app-role.sql | create | role + ownership + before/after report + `COPY PROGRAM` denial check |
| deploy/lightsail/scripts/pg-app-role.sh | create | wrapper (`apply`, `check`) |
| App/tests/test_pg_app_role_script.py | create | static safety tests |
| .github/workflows/ci.yml | edit | one new step in `test-postgres` |
| docs/context/test-map.md | edit | add the new test file to the row that lists test_pg_cutover_script.py |
| docs/SECURITY.md | edit | residual-risks row |
| docs/LIGHTSAIL.md | edit | one table row (command) |
| docs/OPERATIONS.md | edit | short subsection with the owner runbook |
| docs/ENVIRONMENT.md | edit | one line in "Database (PostgreSQL, optional)" |
| docs/context/known-issues.md | edit | K-S11 row (file is at its size cap: replace, do not add lines) |

No other file may change. deploy/lightsail/docker-compose.yml is NOT changed.

## 4. Steps

Commit after each step (`1206 step k`).

1. Create `deploy/lightsail/scripts/pg-app-role.sql` with exactly:

```sql
-- 1206 (K-S11): restricted role for the app. Run as the bootstrap superuser:
--   ./scripts/pg-app-role.sh apply
-- Idempotent. Never drops anything. No password: the postgres service has no
-- network and trusts its socket volume (docs/SECURITY.md).
\set ON_ERROR_STOP on
\echo '== before'
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin FROM pg_roles WHERE rolname IN ('ubyhost', 'ubyhost_app') ORDER BY 1;
SELECT count(*) AS objects_not_owned_by_app FROM (
  SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')
     AND c.relowner <> COALESCE((SELECT oid FROM pg_roles WHERE rolname = 'ubyhost_app'), 0)
) s;

DO $do$
DECLARE r record; app_oid oid;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_app') THEN
    CREATE ROLE ubyhost_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN;
  ELSE
    ALTER ROLE ubyhost_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN;
  END IF;
  SELECT oid INTO app_oid FROM pg_roles WHERE rolname = 'ubyhost_app';
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO ubyhost_app', current_database());
  ALTER SCHEMA public OWNER TO ubyhost_app;
  FOR r IN  -- tables, views, materialized views, foreign tables, standalone sequences
    SELECT c.relkind, format('%I.%I', n.nspname, c.relname) AS name
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relowner <> app_oid
       AND c.relkind IN ('r','p','v','m','S','f')
       AND NOT (c.relkind = 'S' AND EXISTS (
             SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a','i')))
     ORDER BY CASE c.relkind WHEN 'S' THEN 2 ELSE 1 END, 2
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO ubyhost_app',
      CASE r.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                     WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END, r.name);
  END LOOP;
  FOR r IN  -- functions and procedures (the invoice guards, ubyhost_sqlite_date)
    SELECT p.oid::regprocedure::text AS name, p.prokind
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proowner <> app_oid AND p.prokind IN ('f','p')
       AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO ubyhost_app',
      CASE r.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END, r.name);
  END LOOP;
  FOR r IN  -- enum and domain types
    SELECT format('%I.%I', n.nspname, t.typname) AS name, t.typtype
      FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
     WHERE n.nspname = 'public' AND t.typowner <> app_oid AND t.typtype IN ('e','d')
  LOOP
    EXECUTE format('ALTER %s %s OWNER TO ubyhost_app',
      CASE r.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, r.name);
  END LOOP;
END
$do$;

\echo '== after'
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin FROM pg_roles WHERE rolname = 'ubyhost_app';
SELECT count(*) AS objects_not_owned_by_app FROM (
  SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')
     AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = 'ubyhost_app')
) s;

\echo '== proof: the app role must be refused (expect PASS lines)'
DO $do$
BEGIN
  IF (SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
        FROM pg_roles WHERE rolname = 'ubyhost_app') THEN
    RAISE EXCEPTION 'FAIL: ubyhost_app has a privileged attribute';
  END IF;
  RAISE NOTICE 'PASS: ubyhost_app has no privileged attribute';
  SET LOCAL ROLE ubyhost_app;
  BEGIN
    EXECUTE $$COPY (SELECT 1) TO PROGRAM 'true'$$;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: COPY PROGRAM was allowed for ubyhost_app';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: COPY PROGRAM refused for ubyhost_app';
  END;
END
$do$;
```

   Run `python3 - <<'X'` is not needed; check only that the file has no tab characters: `grep -c $'\t' deploy/lightsail/scripts/pg-app-role.sql | tail -30` prints 0.

2. Create `deploy/lightsail/scripts/pg-app-role.sh` (then `chmod +x`):

```bash
#!/usr/bin/env bash
# 1206 (K-S11): create the restricted app role and give it the app objects.
#   ./scripts/pg-app-role.sh apply   run pg-app-role.sql as the bootstrap superuser
#   ./scripts/pg-app-role.sh check   read-only: role attributes and objects not owned by the app role
# Run from deploy/lightsail on the server. Idempotent; re-run after a restore or a
# cutover (objects created by the superuser). It never drops anything.
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  apply)
    docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 < scripts/pg-app-role.sql
    ;;
  check)
    docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 -c \
      "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin FROM pg_roles WHERE rolname IN ('ubyhost','ubyhost_app') ORDER BY 1" -c \
      "SELECT count(*) AS objects_not_owned_by_app FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f') AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = 'ubyhost_app')"
    ;;
  *)
    echo "usage: $0 apply|check" >&2
    exit 2
    ;;
esac
```

3. Create `App/tests/test_pg_app_role_script.py`. Style: module docstring, `ROOT = Path(__file__).resolve().parents[2]`, `SCRIPTS = ROOT / "deploy/lightsail/scripts"` as in test_pg_backup_scripts.py. Tests (static, no docker, no database):
   - `test_script_syntax`: `bash -n pg-app-role.sh` returns 0 (skip nothing; bash exists in CI).
   - `test_script_is_strict_and_executable`: contains `set -euo pipefail`, file mode has the user-exec bit.
   - `test_role_is_not_privileged`: SQL contains `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN` at least twice (create and alter), and does not contain the word `SUPERUSER` outside `NOSUPERUSER` (regex `(?<!NO)SUPERUSER` has no match).
   - `test_sql_is_safe_to_rerun`: no `DROP `, no `REASSIGN OWNED`, no `PASSWORD`, no `GRANT ALL`, no `ALTER SYSTEM`, no `CREATE DATABASE`; contains `IF NOT EXISTS (SELECT 1 FROM pg_roles` and `ON_ERROR_STOP`.
   - `test_sql_moves_ownership`: contains `ALTER SCHEMA public OWNER TO ubyhost_app`, `OWNER TO ubyhost_app` in at least 4 places, and `deptype IN ('a','i')`.
   - `test_sql_proves_copy_program_refused`: contains `COPY (SELECT 1) TO PROGRAM` and `insufficient_privilege`.
   - `test_wrapper_runs_admin_as_superuser`: wrapper contains `-U ubyhost ` and does not contain `ubyhost_app@` or `-U ubyhost_app`.
   - `test_compose_does_not_hardcode_the_app_role`: parse deploy/lightsail/docker-compose.yml with `yaml.safe_load`; `postgres.environment.POSTGRES_USER == "ubyhost"`; the text `ubyhost_app` does not occur in the file; `services["ubyhost-go"]["environment"]["UBYHOST_DATABASE_URL"] == "${UBYHOST_DATABASE_URL:-}"`. This is the executable form of the auto-deploy safety property (§ Owner steps, "Safety property").
   - `test_no_secret_in_files`: neither new script file contains `password`, `secret`, `token` (case-insensitive) outside comments that say "No password" (check by removing lines starting `--` or `#` first).
   Run: `.venv/bin/python -m pytest tests/test_pg_app_role_script.py -q --tb=short -x 2>&1 | tail -30`.

4. `.github/workflows/ci.yml`: grep -nF "Fail if PostgreSQL tests were skipped" .github/workflows/ci.yml. The step ends with the `if grep -q skipped ...` run line (about line 205) followed by a blank line and `- name: No PostgreSQL module yet`. Insert this step between them (same indentation as the neighbouring steps; the job's default working-directory is App):

```yaml
      - name: App works as the non-superuser role
        env:
          PGPASSWORD: ubyhost
        run: |
          set -euo pipefail
          # 1206: the production role script, then migrate and read as ubyhost_app
          psql -h localhost -U postgres -d ubyhost_test -v ON_ERROR_STOP=1 -q -f ../deploy/lightsail/scripts/pg-app-role.sql
          psql -h localhost -U postgres -d ubyhost_test -v ON_ERROR_STOP=1 -q -c "ALTER ROLE ubyhost_app PASSWORD 'ubyhost'"
          export UBYHOST_DATABASE_URL=postgresql://ubyhost_app:ubyhost@localhost:5432/ubyhost_test
          python scripts/pg_schema.py apply --expect-database ubyhost_test
          python scripts/pg_schema.py check --expect-database ubyhost_test
          UBYHOST_TEST_DATABASE_URL="$UBYHOST_DATABASE_URL" python -m pytest tests/test_db_postgres.py -q -rs --tb=short 2>&1 | tail -30
```

   The `'ubyhost'` password is the same throwaway CI password already used in this file for the service container; it is not a production secret. The pipe into `tail` hides pytest's exit code; replace the last line with `set -o pipefail` already active (the step starts with `set -euo pipefail`, so the pipe fails the step). If you suspect the pytest line cannot work as a non-superuser (the evidence would be a `permission denied to create database` or similar in the log of the CI run, which you cannot see), keep it anyway: this step is the proof. Validate the YAML locally: `python3 -c "import yaml;yaml.safe_load(open('.github/workflows/ci.yml'))" 2>&1 | tail -30`.
   Note for the report: CI proves migrate + schema check + the PostgreSQL test module as `ubyhost_app`. The full suite (`test-postgres-full`, about 30 min) stays on the superuser; running it as `ubyhost_app` is left out on purpose.

5. Docs (each: grep the anchor, add exactly the text, nothing else):
   - docs/SECURITY.md: in the `## Residual risks` table add a row after the `| **Backups** |` row: `| **App database role** | Once the owner runs `pg-app-role.sh` and sets the user in `UBYHOST_DATABASE_URL`, the app, worker and Go service connect as `ubyhost_app` (no superuser, createdb, createrole; refused `COPY PROGRAM`), so an SQL injection cannot read files or run commands in the postgres container. Auth is still `trust` over the private socket, so code that edits the DSN could still pick `ubyhost`; backup, WAL-G and restore scripts keep the superuser. Runbook: OPERATIONS.md "App database role". |`
   - docs/LIGHTSAIL.md: after the row starting `` | `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply `` add: `` | `./scripts/pg-app-role.sh apply` or `check` | Create or refresh the restricted app role `ubyhost_app` and its object ownership (owner step, once; again after a restore or cutover) | ``
   - docs/OPERATIONS.md: insert before the line `### WAL-G continuous archiving and point-in-time recovery` a new `### App database role (K-S11)` subsection: the owner runbook of "Owner steps" below in 6 to 8 lines (steps 1-9 condensed, keep the numbers), plus: restore into a fresh cluster needs `./scripts/pg-app-role.sh apply` before `pg-restore.sh`; the existing drill (`--no-owner`) is unaffected.
   - docs/ENVIRONMENT.md: at the end of the `## Database (PostgreSQL, optional)` section (before `## Development and test only`) add one line: `Production sets the user in `UBYHOST_DATABASE_URL` to `ubyhost_app` (`postgresql://ubyhost_app@/ubyhost?host=/var/run/postgresql`) after the owner runs `scripts/pg-app-role.sh apply`; admin scripts keep the `ubyhost` superuser. No separate variable.`
   - docs/context/known-issues.md: replace the K-S11 row by the single line `| K-S11 | Med owner step | server .env | Run pg-app-role.sh, then set ubyhost_app in the DSN; remove row when done | 1206 |`. File line count must not grow: `wc -l docs/context/known-issues.md | tail -30` stays 102.
   - docs/context/test-map.md: `grep -nF test_pg_cutover_script docs/context/test-map.md`; add `test_pg_app_role_script.py` next to it in the same row, same separator style.
   Then: `python3 scripts/context_lint.py 2>&1 | tail -30` (from the repo root).

## 5. Do not touch

deploy/lightsail/docker-compose.yml, pg-cutover.sh, pg-restore.sh, backup.sh, walg scripts, deploy.sh, anything under App/app, App/migrations_pg, go/. AGENTS rules 3 and 4: no secret, no real `.env`, no operator identity, no new dependency. Never push or merge; open one PR as draft (merge is the owner's, via `scripts/merge-pr-on-green.sh`).

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_pg_app_role_script.py -q --tb=short -x 2>&1 | tail -30` expect all passed.
- `.venv/bin/python -m pytest tests/test_pg_cutover_script.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` expect all passed (compose and scripts untouched).
- `bash -n ../deploy/lightsail/scripts/pg-app-role.sh 2>&1 | tail -30` expect no output.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` expect clean; `git diff --stat | tail -30` expect only the §3 files.
Not run by you (needs a server): the SQL itself. If `psql` and a local Postgres happen to exist, do not set one up; CI step 4 is the SQL proof.

## 7. Acceptance

- [ ] The new test file passes; test_pg_cutover_script and test_pg_backup_scripts still pass.
- [ ] `git diff --stat` shows docker-compose.yml unchanged and no file outside §3.
- [ ] Safety property: a merge and auto-deploy without the owner steps cannot break production. Verified by `test_compose_does_not_hardcode_the_app_role` (compose never names `ubyhost_app` and still passes `UBYHOST_DATABASE_URL` through unchanged) and by the fact that the only thing that selects the app user is the server-side `.env`, which no deploy edits (deploy.sh only sources it).
- [ ] ci.yml parses as YAML and contains the new step after "Fail if PostgreSQL tests were skipped".
- [ ] known-issues.md still has 102 lines; context_lint clean.
- [ ] No secret, password, or operator identity added (`git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_' | tail -30`: only the CI throwaway `PASSWORD 'ubyhost'`/`PGPASSWORD` lines and comment text "No password" may match).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (including `Fail if PostgreSQL tests were skipped`, the `Backups` risk row, or the `test_pg_cutover_script` test-map row);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change (compose changes are NOT part of this brief);
- context_lint complains about size in a file you edited and shortening your own added text does not fix it;
- you need push, merge, secrets, SSH or deploy (hand it to the owner).

## 9. Report

Write `docs/tasks/1206-report.md` (600 tokens at most), set `Status: review`. Contents: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations, questions, owner steps left. State plainly that the SQL was not executed locally and that CI step 4 is its first run.

## Risk list (for the reviewer)

- deploy/lightsail/scripts/pg-app-role.sql: ownership loops (sequences linked to tables are skipped on purpose; enum/domain types covered), the `COPY PROGRAM` proof block.
- .github/workflows/ci.yml: the new step only; the pytest line as a non-superuser may need to be narrowed if `test_db_postgres.py` creates databases.
- App/tests/test_pg_app_role_script.py: the compose assertion.

## Owner steps

Safety property: nothing changes in production until step 5. Merging and auto-deploy only add files. The app keeps connecting as `ubyhost` until you edit `.env` yourself.

1. SSH to the server and `cd` to the folder with `docker-compose.yml` (deploy/lightsail). Wait until the 1206 PR has merged and the auto-deploy finished (the new script is then in `scripts/`).
2. Take a backup first: run `./scripts/backup.sh` and wait for it to finish without an error line.
3. Run `./scripts/pg-app-role.sh apply`. It prints `== before`, `== after` and `== proof`.
4. Check the output: in `== after`, `ubyhost_app` shows `rolsuper f`, `rolcreatedb f`, `rolcreaterole f`, `rolcanlogin t`, and `objects_not_owned_by_app` is `0`. Under `== proof` there are two `PASS` lines and no `FAIL` or `ERROR`. If anything else shows, stop and send me the output; nothing has switched yet.
5. Make a copy of the setting: `cp -p .env .env.before-1206`. Open `.env` and in the line `UBYHOST_DATABASE_URL=postgresql://ubyhost@/ubyhost?host=/var/run/postgresql` change only `ubyhost@` to `ubyhost_app@`. Save.
6. Run `docker compose up -d` (add `--profile go` or your usual COMPOSE_PROFILES, as you always do). Wait about a minute.
7. Check the site: `curl -fsS https://<your-site>/healthz`, and `docker compose ps` shows `ubyhost`, `worker` (and `ubyhost-go` if used) as healthy/running. Check the log has no "permission denied": `docker compose logs --tail 50 worker 2>&1 | tail -30`.
8. Check Go: wait for its next scheduled job (or open the admin page that shows the last job run) and run `docker compose logs --tail 50 ubyhost-go 2>&1 | tail -30`: no `permission denied` lines.
9. Check backups: run `./scripts/backup.sh` again (it must finish without error), and, if WAL-G is on, `./scripts/walg-check.sh` (it must report no problem; the WAL push and base backup run as the superuser, so they are unaffected). The next night's backup ping is the final proof.
10. Roll back, if anything is wrong: `cp -p .env.before-1206 .env`, then `docker compose up -d`. The app is on `ubyhost` again within a minute. Ownership by `ubyhost_app` is harmless for the superuser, so nothing else needs undoing.
11. After a restore or a cutover, run `./scripts/pg-app-role.sh apply` again (objects the superuser created). On a brand-new cluster run it before `pg-restore.sh`. When all is well, tell the orchestrator to delete the K-S11 row.
