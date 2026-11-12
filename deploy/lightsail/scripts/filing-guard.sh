#!/usr/bin/env bash
# Filing guard for a restored box (brief 1169, disaster recovery step 6).
#
# pg-restore.sh --file writes .restored-box next to .env: this box was rebuilt
# from a backup file, and the old server may still be filing the same guests.
# While that marker exists, scheduled filing must stay off: UBYHOST_ENABLE_SCHEDULER=0
# and `submit` in neither UBYHOST_GO_JOB_KINDS nor UBYHOST_JOB_QUEUE_KINDS, in .env
# and in the caller's environment (Compose prefers the shell over .env).
# (With `submit` in neither list the Python worker files guests itself, so the
# lists alone never prove that filing is off.)
# Apartments in immediate mode still file when a guest or host saves: keep the
# site on the "we're down" page until the marker is removed.
# The owner removes the marker once the old server is confirmed off:
# docs/DISASTER_RECOVERY.md, "Two servers never file at once".
#
# Usage (from deploy/lightsail): ./scripts/filing-guard.sh [--assume-restored]
#   --assume-restored: check as if the marker existed (pg-restore.sh --file,
#   before it writes the marker)
#   exit 0: no marker; or marker and filing off; or the one-run override is set
#   exit 3: marker and scheduled filing could run
# One-run override, prefixed on the command, never exported, never in .env:
#   UBYHOST_FILING_GUARD_OVERRIDE=1 ./scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

# Captured before `source .env`, and readonly, so .env cannot change them.
readonly MARKER=".restored-box"
readonly OVERRIDE="${UBYHOST_FILING_GUARD_OVERRIDE:-}"
readonly CALLER_GO_JOB_KINDS="${UBYHOST_GO_JOB_KINDS:-}"
readonly CALLER_JOB_QUEUE_KINDS="${UBYHOST_JOB_QUEUE_KINDS:-}"

case "${1:-}" in
  --assume-restored) ASSUME_RESTORED=1 ;;
  "") ASSUME_RESTORED=0 ;;
  *) echo "usage: $0 [--assume-restored]" >&2; exit 2 ;;
esac
readonly ASSUME_RESTORED

if [ "${ASSUME_RESTORED}" != "1" ] && [ ! -f "${MARKER}" ]; then
  exit 0
fi

if [ ! -f .env ]; then
  echo "ERROR: restored box and no .env in ${ROOT}" >&2
  exit 3
fi
if grep -Eq '^[[:space:]]*(export[[:space:]]+)?UBYHOST_FILING_GUARD_OVERRIDE=' .env; then
  echo "ERROR: UBYHOST_FILING_GUARD_OVERRIDE must not be in .env; prefix it on the command for one run" >&2
  exit 3
fi

# .env is what the containers get (env_file); the caller lists are checked too.
unset UBYHOST_ENABLE_SCHEDULER UBYHOST_GO_JOB_KINDS UBYHOST_JOB_QUEUE_KINDS
set -a
# shellcheck disable=SC1091
if ! source .env; then
  echo "ERROR: restored box and .env in ${ROOT} could not be read" >&2
  exit 3
fi
set +a

has_submit() {
  local list
  list="$(printf '%s' "${1:-}" | tr -d '[:space:]')"
  case ",${list}," in
    *,submit,*) return 0 ;;
  esac
  return 1
}

reasons=()
case "${UBYHOST_ENABLE_SCHEDULER:-1}" in
  0|false|no) ;;
  *) reasons+=("UBYHOST_ENABLE_SCHEDULER is not 0: the Python worker files guests") ;;
esac
if has_submit "${UBYHOST_GO_JOB_KINDS:-}"; then
  reasons+=("submit is in UBYHOST_GO_JOB_KINDS")
fi
if has_submit "${UBYHOST_JOB_QUEUE_KINDS:-}"; then
  reasons+=("submit is in UBYHOST_JOB_QUEUE_KINDS")
fi
if has_submit "${CALLER_GO_JOB_KINDS}"; then
  reasons+=("submit is in UBYHOST_GO_JOB_KINDS in the shell environment (Compose prefers it over .env)")
fi
if has_submit "${CALLER_JOB_QUEUE_KINDS}"; then
  reasons+=("submit is in UBYHOST_JOB_QUEUE_KINDS in the shell environment")
fi

if [ "${#reasons[@]}" -eq 0 ]; then
  echo "NOTE: restored box (${ROOT}/${MARKER}): scheduled filing is off; apartments in immediate mode still file when a guest or host saves. Remove the marker once the old server is confirmed off (docs/DISASTER_RECOVERY.md)." >&2
  exit 0
fi

echo "!!! RESTORED BOX: the old server may still be filing the same guests with the police." >&2
for reason in "${reasons[@]}"; do
  echo "!!!   ${reason}" >&2
done
if [ "${OVERRIDE}" = "1" ]; then
  echo "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1: continuing with scheduled filing on. Remove ${ROOT}/${MARKER} once the old server is confirmed off." >&2
  exit 0
fi
echo "ERROR: automatic filing stays blocked on a restored box (${ROOT}/${MARKER}). Stop the old server, then follow docs/DISASTER_RECOVERY.md, \"Two servers never file at once\"." >&2
exit 3
