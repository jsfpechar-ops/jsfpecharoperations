#!/usr/bin/env bash
# Pre-deploy gate: Python vs Go pixel parity for every host, admin and guest page. Exit 1 on any visible or error row.
set -u
cd "$(dirname "$0")/../.."
source scripts/e2e/parity_env.sh
rc=0
cd App
for g in A B C D E F G H; do
  PARITY_GROUP=$g .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
done
PARITY_PIN=1 PARITY_GROUP=P .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -3
[ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
if [ "$rc" -eq 0 ]; then echo "GATE: PASS"; else echo "GATE: FAIL"; fi
exit $rc
