-- UbyHost PostgreSQL role bootstrap PROPOSAL (brief 0456).
--
-- Run through deploy/lightsail/scripts/postgres-create-roles.sh, which supplies
-- the passwords as psql variables from environment variables (read by \getenv
-- below). Never run this by hand with a password on the command line, and never
-- commit a password.
--
-- Roles:
--   ubyhost_app      application runtime: CONNECT + DML only, no DDL.
--   ubyhost_migrate  explicit schema/migration owner: USAGE + CREATE on public
--                    plus default DML privileges for objects it creates.
--   ubyhost_backup   OPTIONAL proposal; pgBackRest currently runs as the local
--                    postgres superuser inside the postgres container, so the
--                    grants at the end stay commented until a DBA confirms the
--                    minimum set (pg_read_all_data, backup functions, ...).
--
-- This file is idempotent: roles are created when missing, passwords updated,
-- grants re-applied. Re-run it after a transfer/bootstrap to grant on the
-- tables that now exist. It does NOT change UBYHOST_DATABASE_URL; switching the
-- app DSN is an owner/engineer decision (see the owner runbook, section 9).

\set ON_ERROR_STOP on

\getenv app_password UBYHOST_ROLE_APP_PASSWORD
\getenv migration_password UBYHOST_ROLE_MIGRATION_PASSWORD
\getenv backup_password UBYHOST_ROLE_BACKUP_PASSWORD
\set skip_backup 1
\getenv skip_backup UBYHOST_ROLE_SKIP_BACKUP

\if :{?app_password}
\else
  \echo 'ubyhost_app password was not provided; refusing to change roles.'
  \quit 3
\endif
\if :{?migration_password}
\else
  \echo 'ubyhost_migrate password was not provided; refusing to change roles.'
  \quit 3
\endif

-- 1. Create roles when missing, then set/rotate the password. Passwords arrive
--    as values and are re-quoted by format(%L) when the role is created.
SELECT format(
  'CREATE ROLE ubyhost_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_app');
\gexec
ALTER ROLE ubyhost_app PASSWORD :'app_password';

SELECT format(
  'CREATE ROLE ubyhost_migrate LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_migrate');
\gexec
ALTER ROLE ubyhost_migrate PASSWORD :'migration_password';

\if :skip_backup
  \echo 'ubyhost_backup role skipped (no password file supplied); pgBackRest keeps using the local superuser.'
\else
  \if :{?backup_password}
    SELECT format(
      'CREATE ROLE ubyhost_backup LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
      :'backup_password')
    WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_backup');
    \gexec
    ALTER ROLE ubyhost_backup PASSWORD :'backup_password';
    -- DBA review required before pgBackRest is reconfigured to use this role.
    -- GRANT pg_read_all_data TO ubyhost_backup;
    -- GRANT EXECUTE ON FUNCTION pg_backup_start(text, boolean) TO ubyhost_backup;
    -- GRANT EXECUTE ON FUNCTION pg_backup_stop(boolean) TO ubyhost_backup;
  \else
    \echo 'Unable to set a backup password; refusing to leave a half-configured backup role.'
    \quit 3
  \endif
\endif

-- 2. Connection and schema access.
SELECT format(
  'GRANT CONNECT ON DATABASE %I TO ubyhost_app, ubyhost_migrate',
  current_database());
\gexec

GRANT USAGE ON SCHEMA public TO ubyhost_app;
GRANT USAGE, CREATE ON SCHEMA public TO ubyhost_migrate;

-- 3. Existing objects (no-op before the transfer created them; re-run after).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ubyhost_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ubyhost_app;

-- 4. Objects the migration role creates in the future.
ALTER DEFAULT PRIVILEGES FOR ROLE ubyhost_migrate IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ubyhost_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ubyhost_migrate IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO ubyhost_app;

\echo 'Role proposal applied: ubyhost_app (DML), ubyhost_migrate (DDL). No app DSN was changed.'
