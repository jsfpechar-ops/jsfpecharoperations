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
