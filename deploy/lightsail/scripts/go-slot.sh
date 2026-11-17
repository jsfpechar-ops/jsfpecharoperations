#!/usr/bin/env bash
# 1830: slot helpers for deploy.sh. Source it, do not run it.
# Slot A is the compose service ubyhost-go, slot B is ubyhost-go-b.
# .go-slot (beside docker-compose.yml, not in git) holds the live slot: a or b.
set -euo pipefail

go_svc() { if [ "$1" = "a" ]; then echo ubyhost-go; else echo ubyhost-go-b; fi; }

go_live_slot() {
  local s
  s="$(cat .go-slot 2>/dev/null || echo a)"
  case "${s}" in a | b) echo "${s}" ;; *) echo a ;; esac
}

go_idle_slot() { if [ "$(go_live_slot)" = "a" ]; then echo b; else echo a; fi; }

# go_wait_healthy <slot> <seconds>: 0 when Docker reports the container healthy.
go_wait_healthy() {
  local cid status i
  for i in $(seq 1 "$2"); do
    cid="$(docker compose --profile go ps -q "$(go_svc "$1")" 2>/dev/null || true)"
    if [ -n "${cid}" ]; then
      status="$(docker inspect -f '{{.State.Health.Status}}' "${cid}" 2>/dev/null || true)"
      [ "${status}" = "healthy" ] && return 0
    fi
    sleep 1
  done
  return 1
}
