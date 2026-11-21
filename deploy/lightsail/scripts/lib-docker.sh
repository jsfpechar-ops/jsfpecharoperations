#!/usr/bin/env bash
# Shared helpers for the Lightsail scripts (gdrive, S3, backup, deploy, status).

# --- Which app service is in this checkout ----------------------------------
# 1782 removed the Python services (`ubyhost`, `worker`) from the Lightsail
# compose file; 1999 finishes the move to Go-only. Every script that used to
# exec into `ubyhost` asks these helpers instead, so a checkout that still has
# the Python services keeps working unchanged. All callers cd to
# deploy/lightsail first, so `docker compose config` reads that .env.
# Read from the compose file itself, not `docker compose config`: that works in
# the trimmed fixture trees the shell tests build (no docker, no daemon) and
# costs nothing. With no compose file present, assume the old Python layout.
app_is_python() {
  [ -f docker-compose.yml ] || return 0
  grep -qE '^  ubyhost:[[:space:]]*$' docker-compose.yml
}

# The app service name as written in the compose file (may not be running).
app_service() {
  if app_is_python; then printf 'ubyhost\n'; else printf 'ubyhost-go\n'; fi
}

# The *running* app container that owns /data: the Python app, or whichever Go
# slot is up (deploy.sh records the live slot in .go-slot; either slot owns the
# same volume, so the first running one is fine). Empty when nothing runs.
app_running_service() {
  if app_is_python; then printf 'ubyhost\n'; return 0; fi
  docker compose ps --status running --services 2>/dev/null \
    | grep -x 'ubyhost-go\|ubyhost-go-b' | head -1
}

# Run a one-off command in the app image, for a stack that is not up yet.
app_run() {
  if app_is_python; then
    docker compose run --rm --no-deps -T ubyhost "$@"
  else
    docker compose --profile go run --rm --no-deps -T ubyhost-go "$@"
  fi
}

ubyhost_container_ref() {
  if [ -n "${UBYHOST_CONTAINER:-}" ]; then
    printf '%s\n' "${UBYHOST_CONTAINER}"
    return 0
  fi
  local compose_dir="${1:?compose project directory}"
  local id="" svc
  svc="$(cd "${compose_dir}" && app_running_service)"
  if [ -n "${svc}" ]; then
    id="$(cd "${compose_dir}" && docker compose ps -q "${svc}" 2>/dev/null | head -1)"
  fi
  if [ -z "${id}" ]; then
    echo "No running app container (ubyhost or ubyhost-go). From deploy/lightsail run: ./scripts/deploy.sh" >&2
    echo "Or set UBYHOST_CONTAINER to the name from: docker compose ps" >&2
    return 1
  fi
  printf '%s\n' "${id}"
}
