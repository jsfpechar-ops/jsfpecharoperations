#!/bin/sh
set -eu

read_secret() {
  env_name="$1"
  secret_path="$2"
  if [ ! -s "$secret_path" ]; then
    echo "Required PostgreSQL secret is missing or empty: $secret_path" >&2
    exit 1
  fi
  secret_value="$(cat "$secret_path")"
  if [ -z "$secret_value" ]; then
    echo "Required PostgreSQL secret is empty: $secret_path" >&2
    exit 1
  fi
  export "$env_name=$secret_value"
  unset secret_value
}

read_secret PGBACKREST_REPO1_S3_KEY /run/secrets/pgbackrest_s3_key
read_secret PGBACKREST_REPO1_S3_KEY_SECRET /run/secrets/pgbackrest_s3_secret
read_secret PGBACKREST_REPO1_CIPHER_PASS /run/secrets/pgbackrest_cipher_pass
exec pgbackrest "$@"
