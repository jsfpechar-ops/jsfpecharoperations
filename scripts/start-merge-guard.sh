#!/usr/bin/env bash
# Start merge-pr-on-green.sh for a PR in tmux (auto-merge when green).
# Usage: scripts/start-merge-guard.sh <pr-number>
set -euo pipefail

PR="${1:?usage: start-merge-guard.sh <pr-number>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="merge-pr-${PR}"

if tmux -f /exec-daemon/tmux.portal.conf has-session -t "=${SESSION}" 2>/dev/null; then
  echo "merge guard already running: ${SESSION}"
  exit 0
fi

tmux -f /exec-daemon/tmux.portal.conf new-session -d -s "${SESSION}" -c "${ROOT}" -- "${SHELL:-bash}" -l
tmux -f /exec-daemon/tmux.portal.conf send-keys -t "${SESSION}:0.0" \
  "cd ${ROOT} && git pull --ff-only origin main 2>/dev/null || true; MERGE_GUARD_TIMEOUT=7200 scripts/merge-pr-on-green.sh ${PR} 2>&1 | tee /tmp/merge-${PR}.log" C-m
echo "started ${SESSION} (log: /tmp/merge-${PR}.log)"