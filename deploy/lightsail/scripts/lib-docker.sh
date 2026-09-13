#!/usr/bin/env bash
# Shared helpers for backup upload scripts (gdrive, S3).

ubyhost_container_ref() {
  if [ -n "${UBYHOST_CONTAINER:-}" ]; then
    printf '%s\n' "${UBYHOST_CONTAINER}"
    return 0
  fi
  local compose_dir="${1:?compose project directory}"
  local id
  id="$(cd "${compose_dir}" && docker compose ps -q ubyhost 2>/dev/null | head -1)"
  if [ -z "${id}" ]; then
    echo "No running ubyhost container. From deploy/lightsail run: docker compose up -d" >&2
    echo "Or set UBYHOST_CONTAINER to the name from: docker compose ps" >&2
    return 1
  fi
  printf '%s\n' "${id}"
}
