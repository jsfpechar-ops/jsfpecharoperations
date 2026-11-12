#!/usr/bin/env bash
# Filing guard for a restored box (brief 1169, disaster recovery step 6).
#
# pg-restore.sh --file writes .restored-box next to .env: this box was rebuilt
# from a backup file, and the old server may still be filing the same guests.
# While that marker exists, automatic filing must stay off: UBYHOST_ENABLE_SCHEDULER=0
# and `submit` in neither UBYHOST_GO_JOB_KINDS nor UBYHOST_JOB_QUEUE_KINDS.
# (With `submit` in neither list the Python worker files guests itself, so the
# lists alone never prove that filing is off.)
# The owner removes the marker once the old server is confirmed off:
# docs/DISASTER_RECOVERY.md, "Two servers never file at once".
#
# Usage (from deploy/lightsail): ./scripts/filing-guard.sh
#   exit 0: no marker; or marker and filing off; or the one-run override is set
#   exit 3: marker and automatic filing could run
# One-run override, never in .env: UBYHOST_FILING_GUARD_OVERRIDE=1 ./scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

MARKER=".restored-box"
[ -f "${MARKER}" ] || exit 0

OVERRIDE="${UBYHOST_FILING_GUARD_OVERRIDE:-}"

if [ ! -f .env ]; then
  echo "ERROR: restored box and no .env in ${ROOT}" >&2
  exit 3
fi
if grep -Eq '^[[:space:]]*(export[[:space:]]+)?UBYHOST_FILING_GUARD_OVERRIDE=' .env; then
  echo "ERROR: UBYHOST_FILING_GUARD_OVERRIDE must not be in .env; set it on the command line for one run" >&2
  exit 3
fi

# Only .env counts: it is what the containers get (env_file).
unset UBYHOST_ENABLE_SCHEDULER UBYHOST_GO_JOB_KINDS UBYHOST_JOB_QUEUE_KINDS
# shellcheck disable=SC1091
set -a
source .env
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

if [ "${#reasons[@]}" -eq 0 ]; then
  echo "NOTE: restored box (${ROOT}/${MARKER}): automatic filing is off. Remove the marker once the old server is confirmed off (docs/DISASTER_RECOVERY.md)." >&2
  exit 0
fi

echo "!!! RESTORED BOX: the old server may still be filing the same guests with the police." >&2
for reason in "${reasons[@]}"; do
  echo "!!!   ${reason}" >&2
done
if [ "${OVERRIDE}" = "1" ]; then
  echo "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1: continuing with automatic filing on. Remove ${ROOT}/${MARKER} once the old server is confirmed off." >&2
  exit 0
fi
echo "ERROR: automatic filing stays blocked while ${ROOT}/${MARKER} exists. Stop the old server, then follow docs/DISASTER_RECOVERY.md, \"Two servers never file at once\"." >&2
exit 3
