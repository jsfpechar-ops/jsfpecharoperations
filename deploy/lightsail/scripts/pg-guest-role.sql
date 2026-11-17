-- 1834: restricted role for the guest program (plan guest-form-isolation
-- section 2). Run as the bootstrap superuser AFTER migration 00020 is applied:
--   docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1 < scripts/pg-guest-role.sql
-- Idempotent. Never drops anything. No password: the postgres service has no
-- network and trusts its socket volume (docs/SECURITY.md), as for ubyhost_app.
-- Run it again after any restore or cutover (grants are not restored).
\set ON_ERROR_STOP on

DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ubyhost_guest') THEN
    CREATE ROLE ubyhost_guest NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN CONNECTION LIMIT 3;
  ELSE
    ALTER ROLE ubyhost_guest NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS LOGIN CONNECTION LIMIT 3;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO ubyhost_guest', current_database());
END
$do$;
ALTER ROLE ubyhost_guest SET statement_timeout = '2s';
GRANT USAGE ON SCHEMA public TO ubyhost_guest;
-- Reset, then grant exactly plan section 2 (revoking a table privilege also
-- revokes its column privileges).
REVOKE ALL ON guest_form_snapshot, guest_inbox FROM ubyhost_guest;
GRANT SELECT ON guest_form_snapshot TO ubyhost_guest;
GRANT INSERT (idempotency_key, token_hash, reservation_id, contract_version, received_at, payload_enc)
  ON guest_inbox TO ubyhost_guest;
GRANT SELECT (id, idempotency_key, token_hash, reservation_id, status, received_at)
  ON guest_inbox TO ubyhost_guest;

\echo '== role'
SELECT rolname, rolconnlimit, rolconfig, rolsuper, rolcreaterole FROM pg_roles WHERE rolname = 'ubyhost_guest';

\echo '== proof: expect four PASS lines'
DO $do$
BEGIN
  SET LOCAL ROLE ubyhost_guest;
  PERFORM 1 FROM guest_form_snapshot LIMIT 1;
  PERFORM id, idempotency_key, token_hash, reservation_id, status, received_at FROM guest_inbox LIMIT 1;
  RESET ROLE;
  RAISE NOTICE 'PASS: ubyhost_guest reads the snapshot and its inbox columns';
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    PERFORM 1 FROM guest LIMIT 1;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can read the guest table';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: guest table refused';
  END;
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    PERFORM payload_enc FROM guest_inbox LIMIT 1;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can read payload_enc';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: payload_enc read refused';
  END;
  SET LOCAL ROLE ubyhost_guest;
  BEGIN
    UPDATE guest_inbox SET status = 'done' WHERE false;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: ubyhost_guest can update guest_inbox';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'PASS: inbox update refused';
  END;
END
$do$;
