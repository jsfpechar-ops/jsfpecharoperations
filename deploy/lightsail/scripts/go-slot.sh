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

# compose build of ubyhost-go tags ubyhost-go:slot-a (the service image). The
# rest of deploy.sh still uses ubyhost-go:local. Call only after a compose
# build. After a CI pull, :local is already the new image.
go_alias_built_to_local() {
  if docker image inspect ubyhost-go:slot-a >/dev/null 2>&1; then
    docker tag ubyhost-go:slot-a ubyhost-go:local
  fi
}

# 1830 compose services are ubyhost-go:slot-a and ubyhost-go-b:slot-b, but
# deploy.sh pulls/builds ubyhost-go:local. Without these aliases, `compose run`
# (schema apply) and `compose up` miss the pulled image: they rebuild on the
# server or fail the deploy. slot-a always tracks :local so goose apply uses
# the new image. slot-b is created only when missing, from :previous if we
# have it, so `up` does not fail on the first deploy after 1830 and does not
# retag a live slot B.
go_ensure_slot_images() {
  if ! docker image inspect ubyhost-go:local >/dev/null 2>&1; then
    return 0
  fi
  docker tag ubyhost-go:local ubyhost-go:slot-a
  if docker image inspect ubyhost-go:slot-b >/dev/null 2>&1; then
    return 0
  fi
  if docker image inspect ubyhost-go:previous >/dev/null 2>&1; then
    docker tag ubyhost-go:previous ubyhost-go:slot-b
  else
    docker tag ubyhost-go:local ubyhost-go:slot-b
  fi
}
