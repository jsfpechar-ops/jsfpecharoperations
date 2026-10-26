#!/usr/bin/env bash
# TTLock checks on the server, one word each. Prints no passwords or tokens.
#   ./scripts/ttlock-check.sh logs [HOURS]        TTLock lines from web + worker (default 24)
#   ./scripts/ttlock-check.sh accounts            stored lock accounts (id, owner, username, status)
#   ./scripts/ttlock-check.sh locks ACCOUNT_ID    locks that account can see
#   ./scripts/ttlock-check.sh gateway ACCOUNT_ID LOCK_ID   gateway test (up to 35 s)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

cmd="${1:-}"
case "${cmd}" in
  logs)
    hours="${2:-24}"
    docker compose logs --no-color --since "${hours}h" ubyhost worker 2>&1 | grep -i ttlock | tail -50 || true
    echo "(no lines above = nothing was logged; the worker logs TTLock only when it makes a call)"
    ;;
  accounts)
    docker compose exec -T worker python -c "from app import db; [print(r['id'], r['owner_user_id'], r['username'], r['status']) for r in db.query('SELECT id, owner_user_id, username, status FROM lock_account')]"
    ;;
  locks)
    : "${2:?usage: ttlock-check.sh locks ACCOUNT_ID}"
    docker compose exec -T worker python -c "import sys; from app import ttlock; print(ttlock.list_admin_locks(int(sys.argv[1])))" "$2"
    ;;
  gateway)
    : "${2:?usage: ttlock-check.sh gateway ACCOUNT_ID LOCK_ID}"
    : "${3:?usage: ttlock-check.sh gateway ACCOUNT_ID LOCK_ID}"
    docker compose exec -T worker python -c "import sys; from app import ttlock; print('lock time (ms):', ttlock.query_lock_time(int(sys.argv[1]), sys.argv[2]))" "$2" "$3" 2>&1 | grep -E "errcode|TTLockError|lock time" || true
    echo "-2012 lock not under any gateway | -3002 gateway offline | -3003 gateway busy | -3036 lock offline | -3037 lock busy | 10011 refresh token invalid"
    ;;
  *)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
