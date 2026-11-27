#!/usr/bin/env bash
# Shared helpers for the backup scripts. Source it from deploy/lightsail.
# Compose service names, never container names: the container name depends on
# the project directory (ubyhost-ubyhost-go-1) and on the blue/green slot.

compose_has_go_app() {
  docker compose --profile go config --services 2>/dev/null | grep -x ubyhost-go >/dev/null
}

compose_has_python_app() {
  docker compose config --services 2>/dev/null | grep -x ubyhost >/dev/null
}

# One-off shell in a disposable app container (reads /data even when none are running).
ubyhost_app_run_sh() {
  local cmd="$1"
  if compose_has_go_app && ! compose_has_python_app; then
    docker compose --profile go run --rm --no-deps -T --entrypoint sh ubyhost-go -c "$cmd"
  elif compose_has_python_app; then
    docker compose run --rm --no-deps -T --entrypoint sh ubyhost -c "$cmd"
  else
    echo "ERROR: no ubyhost-go or ubyhost service in compose." >&2
    return 1
  fi
}

# Space-separated services to stop around a destructive restore (PostgreSQL dumps).
ubyhost_restore_stop_services() {
  local out=""
  if compose_has_python_app; then
    docker compose config --services 2>/dev/null | grep -x worker >/dev/null && out="worker"
    out="${out}${out:+ }ubyhost"
  fi
  if compose_has_go_app; then
    out="${out}${out:+ }ubyhost-go ubyhost-go-b"
  fi
  printf '%s\n' "${out}"
}

# In-container health check for whichever stack is configured.
ubyhost_app_healthz_ok() {
  local svc
  if compose_has_go_app && ! compose_has_python_app; then
    svc="$(ubyhost_app_service)" || return 1
    docker compose --profile go exec -T "${svc}" \
      wget -qO- --timeout=3 http://127.0.0.1:8081/healthz >/dev/null 2>&1
  elif compose_has_python_app; then
    docker compose exec -T ubyhost python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
      >/dev/null 2>&1
  else
    return 1
  fi
}

# Live Go blue/green slot service from .go-slot (defaults to slot A = ubyhost-go).
ubyhost_live_go_service() {
  local s
  s="$(cat .go-slot 2>/dev/null || echo a)"
  if [ "${s}" = "b" ]; then
    printf '%s\n' ubyhost-go-b
  else
    printf '%s\n' ubyhost-go
  fi
}

# Print the compose service of the running app container: prefer the live Go
# slot from .go-slot when both slots are up (e.g. during blue/green overlap),
# then fall back to the other Go slot, else the Python ubyhost service.
# Exit 1 when none is running.
ubyhost_app_service() {
  local live other svc
  live="$(ubyhost_live_go_service)"
  if [ "${live}" = ubyhost-go-b ]; then
    other=ubyhost-go
  else
    other=ubyhost-go-b
  fi
  for svc in "${live}" "${other}"; do
    if docker compose --profile go ps -q --status running "${svc}" 2>/dev/null | grep . >/dev/null; then
      printf '%s\n' "${svc}"
      return 0
    fi
  done
  if docker compose config --services 2>/dev/null | grep -x ubyhost >/dev/null \
    && docker compose ps -q --status running ubyhost 2>/dev/null | grep . >/dev/null; then
    printf '%s\n' ubyhost
    return 0
  fi
  return 1
}

# ubyhost_app_exec <command...>: run a command in the running app container.
ubyhost_app_exec() {
  local svc
  svc="$(ubyhost_app_service)" || return 1
  case "${svc}" in
    ubyhost) docker compose exec -T "${svc}" "$@" ;;
    *) docker compose --profile go exec -T "${svc}" "$@" ;;
  esac
}

ubyhost_container_ref() {
  if [ -n "${UBYHOST_CONTAINER:-}" ]; then
    printf '%s\n' "${UBYHOST_CONTAINER}"
    return 0
  fi
  local compose_dir="${1:?compose project directory}"
  local svc id
  svc="$(cd "${compose_dir}" && ubyhost_app_service)" || svc=""
  id=""
  if [ -n "${svc}" ]; then
    if [ "${svc}" = ubyhost ]; then
      id="$(cd "${compose_dir}" && docker compose ps -q --status running "${svc}" 2>/dev/null | head -1)"
    else
      id="$(cd "${compose_dir}" && docker compose --profile go ps -q --status running "${svc}" 2>/dev/null | head -1)"
    fi
  fi
  if [ -z "${id}" ]; then
    echo "No running app container (ubyhost-go, ubyhost-go-b or ubyhost). From deploy/lightsail run: docker compose up -d" >&2
    echo "Or set UBYHOST_CONTAINER to the name from: docker compose ps" >&2
    return 1
  fi
  printf '%s\n' "${id}"
}
