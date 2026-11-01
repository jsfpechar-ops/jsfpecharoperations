# 0710: Caddy config checked in CI and before restart; deploy rolls back when the public site is down
Status: ready
Depends on: none | Base commit: origin/main (f00b979) | Branch: claude/project-thread-qjrmqz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
2026-11-01 15:11Z: #653 changed the Caddyfile and the caddy `environment:` in compose. `docker compose up -d` recreated the caddy container, the new Caddy could not load the file and exited, `caddy reload` failed, `deploy.sh` exited without undoing anything: Cloudflare 521 until revert #666. Close the gap three ways: (a) CI validates every Caddyfile with the compose caddy service (same image digest, environment, mounts); (b) `deploy.sh` validates the new Caddyfile the same way on the server before anything restarts; (c) after the restart `deploy.sh` checks the public `/healthz` and, if it fails (or Caddy reload or app health fails), puts back the last good compose file, Caddyfile and app image.
## 2. Context
- `deploy/lightsail/scripts/deploy.sh` runs from `/opt/ubyhost/deploy/lightsail` after the workflow did `git reset --hard <new sha>` (so `ORIG_HEAD` is the previously deployed commit). It already tags the running image `ubyhost:previous` (line ~146).
- Cloudflare mode Caddy aborts any request not from Cloudflare IPs, so a local curl to 127.0.0.1:443 can never pass. The check must use the public URL `${UBYHOST_PUBLIC_BASE_URL}/healthz` (required in `.env`; `smoke-remote.sh` already curls it from the server).
- The caddy image has no entrypoint; its command is `caddy run ...`, so `docker compose run caddy caddy validate ...` works. `docker compose run` does not publish ports, so it never clashes with the running Caddy.
- Compose has `env_file: .env` on two services: CI needs an empty `.env` in `deploy/lightsail` or compose refuses to load.
## 3. Files
New: `deploy/lightsail/scripts/caddy-validate.sh`. Edit: `deploy/lightsail/scripts/deploy.sh`, `deploy/lightsail/.gitignore`, `.github/workflows/ci.yml`, `.github/workflows/deploy-lightsail.yml`, `docs/context/test-map.md`. Write `docs/tasks/0710-report.md`. Nothing else.
## 4. Steps
1. Create `deploy/lightsail/scripts/caddy-validate.sh` (then `chmod +x`) with exactly:
```bash
#!/usr/bin/env bash
# 0710: validate a Caddyfile with the caddy service from docker-compose.yml:
# the image digest, environment and certificate mounts production runs.
# Usage (from deploy/lightsail): ./scripts/caddy-validate.sh caddy/Caddyfile.active
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
FILE="${1:?usage: caddy-validate.sh CADDYFILE}"
docker compose run --rm --no-deps -T \
  -v "${ROOT}/${FILE}:/etc/caddy/Caddyfile.check:ro" \
  caddy caddy validate --config /etc/caddy/Caddyfile.check --adapter caddyfile
```
2. `deploy/lightsail/.gitignore`: append two lines `caddy/Caddyfile.previous` and `.deployed-sha`.
3. `deploy.sh`, anchor `source "$(dirname "$0")/litestream_env.sh"`. Insert directly ABOVE the line `# shellcheck disable=SC1091` that precedes it:
```bash
# 0710: rollback target. .deployed-sha is written only when a deploy finished;
# before the first one, ORIG_HEAD is the commit the workflow reset away from.
PREV_SHA="$(cat .deployed-sha 2>/dev/null || git rev-parse -q --verify ORIG_HEAD 2>/dev/null || true)"

# 0710: the site as visitors reach it (Cloudflare, Caddy, app). About 60 s.
public_ok() {
  for _ in $(seq 1 12); do
    if curl -fsS --max-time 10 -o /dev/null "${UBYHOST_PUBLIC_BASE_URL%/}/healthz"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

# 0710: put back the last good compose file, Caddyfile and app image. Database
# migrations are not undone (goose files are additive). The working tree stays
# modified until the next deploy's git reset.
rollback() {
  echo "==> Rolling back to ${PREV_SHA:-the previous image and Caddyfile}" >&2
  if [ -n "${PREV_SHA}" ]; then
    git checkout "${PREV_SHA}" -- docker-compose.yml caddy/Caddyfile.acme caddy/Caddyfile.cloudflare || true
  fi
  if [ -f caddy/Caddyfile.previous ]; then
    cp caddy/Caddyfile.previous caddy/Caddyfile.active
  fi
  if docker image inspect ubyhost:previous >/dev/null 2>&1; then
    docker tag ubyhost:previous ubyhost:local
  fi
  docker compose up -d --no-build --remove-orphans || true
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true
  if public_ok; then
    echo "Rollback done: the public site answers again. The new release is NOT live." >&2
  else
    echo "ROLLBACK DID NOT BRING THE SITE BACK. Run: docker compose ps; docker compose logs --tail=50 caddy" >&2
  fi
}

```
4. `deploy.sh`, anchor `if [ "${CLOUDFLARE_PROXY:-0}" = "1" ]; then` (the FIRST match, line ~47). Insert directly above it:
```bash
# 0710: keep the running Caddyfile for rollback.
if [ -f caddy/Caddyfile.active ]; then
  cp caddy/Caddyfile.active caddy/Caddyfile.previous
fi

```
Then, directly BELOW the `fi` that closes that if/else (the line after `cp caddy/Caddyfile.acme caddy/Caddyfile.active`), insert:
```bash

# 0710: a recreated Caddy container does not keep its old config, so a broken
# file takes the site down. Test it with the production caddy service before
# anything restarts.
echo "==> Validating the Caddyfile"
if ! bash ./scripts/caddy-validate.sh caddy/Caddyfile.active; then
  if [ -f caddy/Caddyfile.previous ]; then
    cp caddy/Caddyfile.previous caddy/Caddyfile.active
  fi
  echo "The new Caddyfile is invalid; nothing was restarted." >&2
  exit 1
fi
```
5. `deploy.sh`, the comment block above `echo "==> Reloading Caddy"`: replace its last two lines
`# validates the new config before applying it and keeps the running config if` / `# validation fails, so aborting here on a bad config is safe.` with:
```bash
# validates the new config before applying it, but a container that `up -d`
# recreated has no running config to keep, so a failure here rolls back.
```
In the reload failure branch replace `  echo "Caddy reload failed — the deployed Caddyfile is NOT active." >&2` + `  exit 1` with:
```bash
  echo "Caddy reload failed." >&2
  rollback
  exit 1
```
6. `deploy.sh`, the block starting `if [ "${HEALTHY}" != "1" ]; then` through its closing `fi`: replace the whole block with:
```bash
if [ "${HEALTHY}" != "1" ]; then
  echo "New release never became healthy." >&2
  rollback
  exit 1
fi

echo "==> Checking the public site (Cloudflare, Caddy, app)"
if ! public_ok; then
  echo "The public site does not answer after the restart." >&2
  rollback
  exit 1
fi
```
7. `deploy.sh`, at the very end of the file (after the final `fi` of the public smoke block) append:
```bash
# 0710: this commit is now the rollback target.
git rev-parse HEAD > .deployed-sha
```
8. `.github/workflows/ci.yml`: insert a new job directly above the line `  context:` (keep 2-space job indent, same checkout pin as the `docker` job):
```yaml
  caddy:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - name: Validate every Caddyfile with the production caddy service
        env:
          UBYHOST_DOMAIN: ubyhost.example
          ACME_EMAIL: ci@ubyhost.example
        working-directory: deploy/lightsail
        run: |
          touch .env
          openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=ubyhost.example \
            -keyout caddy/certs/origin-key.pem -out caddy/certs/origin.pem 2>/dev/null
          for f in caddy/Caddyfile.acme caddy/Caddyfile.cloudflare; do
            for app in "" app.ubyhost.example; do
              echo "==> ${f} (UBYHOST_APP_DOMAIN='${app}')"
              UBYHOST_APP_DOMAIN="${app}" ./scripts/caddy-validate.sh "${f}"
            done
          done

```
9. `.github/workflows/deploy-lightsail.yml`, in the `need=[...]` list: change `"docker","secrets"]` to `"docker","secrets","caddy"]`.
10. `docs/context/test-map.md`: insert a row directly above `| A module with no row |`:
`| Deploy scripts, Caddyfile, compose | `shellcheck -S error deploy/lightsail/scripts/*.sh`; CI job `caddy` validates both Caddyfiles with the compose caddy service |`
11. Commit each step pair as `0710 step k`.
## 5. Do not touch
`App/`, `go/`, other workflows, other deploy scripts, `docker-compose.yml`, the Caddyfiles.
## 6. Commands
- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` and `bash -n deploy/lightsail/scripts/deploy.sh deploy/lightsail/scripts/caddy-validate.sh`.
- `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/ci.yml .github/workflows/deploy-lightsail.yml && echo ok`.
- `python3 scripts/context_lint.py 2>&1 | tail -3`.
(No Docker daemon here: the orchestrator proves the CI job on the PR.)
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. Commands above pass. `grep -c 'rollback$' deploy/lightsail/scripts/deploy.sh` is 3.
## 8. Stop and ask
Any anchor not found, or a block in §4 that does not match the file.
## 9. Report
`docs/tasks/0710-report.md`: command tails, diff stat.
