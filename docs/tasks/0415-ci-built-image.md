# 0415: Build the production image in GitHub Actions, pull it on the server

Status: todo
Depends on: none | Base commit: 838bec1 | Branch: task/0415-ci-built-image
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The Lightsail deploy builds the Docker image in GitHub Actions from the exact commit CI passed, pushes it to GHCR, and the server only pulls it. The 2 vCPU production server stops spending CPU and minutes on builds during a deploy; a manual deploy or a failed pull still builds on the server as before.

## 2. Context

- Owner decision (2026-10-26, architecture review): deploys should not build on the production server.
- `deploy/lightsail/scripts/deploy.sh` lines 133-134:

```
echo "==> Building image"
docker compose build --pull
```

  Just above, the script tags the running `ubyhost:local` as `ubyhost:previous` for rollback. Every compose service runs `image: ubyhost:local`, so tagging the pulled image as `ubyhost:local` keeps compose and rollback unchanged.
- `.github/workflows/deploy-lightsail.yml` (reusable, called by `deploy-production.yml` and `deploy-staging.yml`) runs one bash step with no checkout. It resolves `DEPLOY_SHA`, checks CI, then SSHes to the server with an unquoted heredoc. Excerpts:

```
permissions:
  contents: read
  checks: read

jobs:
```

```
          install -m 700 -d ~/.ssh
          printf '%s\n' "${LIGHTSAIL_SSH_PRIVATE_KEY}" > ~/.ssh/lightsail_deploy.pem
```

```
          DEPLOY_SHA="${DEPLOY_SHA}"
          TARGET="${TARGET}"
```

```
          chmod +x scripts/*.sh
          ./scripts/deploy.sh
          REMOTE
```

  In the heredoc, `${X}` expands on the runner and `\${X}` on the server.
- `deploy-production.yml` and `deploy-staging.yml` each have, at workflow level:

```
permissions:
  contents: read
  checks: read
```

  A called workflow can only use permissions its caller grants, so both callers need `packages: write` too.
- CI runs `shellcheck -S error` on `deploy/lightsail/scripts/*.sh` and actionlint + zizmor on workflows. No new action is added: plain `docker login/build/push` only (AGENTS.md rule 4).

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/deploy-lightsail.yml` | edit | `packages: write`; build and push; pass `UBYHOST_IMAGE` to the server |
| `.github/workflows/deploy-production.yml` | edit | `packages: write` |
| `.github/workflows/deploy-staging.yml` | edit | `packages: write` |
| `deploy/lightsail/scripts/deploy.sh` | edit | pull `UBYHOST_IMAGE` if set, else build |
| `docs/tasks/0415-report.md` | create | report |

No other file may change.

## 4. Steps

1. In `deploy/lightsail/scripts/deploy.sh`, replace the two lines

```
echo "==> Building image"
docker compose build --pull
```

   with exactly:

```
# 0415: the GitHub deploy builds the image from the commit CI passed, pushes it
# to GHCR and passes it here as UBYHOST_IMAGE, so the server only pulls. A
# manual deploy without it, or a pull that fails, builds here as before.
if [ -n "${UBYHOST_IMAGE:-}" ] && docker pull "${UBYHOST_IMAGE}"; then
  echo "==> Using CI-built image ${UBYHOST_IMAGE}"
  docker tag "${UBYHOST_IMAGE}" ubyhost:local
  # Drop the extra tag so old commit images do not pile up on the disk.
  docker image rm "${UBYHOST_IMAGE}" >/dev/null
else
  if [ -n "${UBYHOST_IMAGE:-}" ]; then
    echo "WARNING: could not pull ${UBYHOST_IMAGE}; building on the server instead." >&2
  fi
  echo "==> Building image"
  docker compose build --pull
fi
```

   Command: `bash -n deploy/lightsail/scripts/deploy.sh && (command -v shellcheck >/dev/null && shellcheck -S error deploy/lightsail/scripts/deploy.sh || echo "no shellcheck") 2>&1 | tail -30` → no errors.

2. In `.github/workflows/deploy-lightsail.yml`, replace the permissions block excerpt with:

```
permissions:
  contents: read
  checks: read
  packages: write # 0415: push the deploy image to GHCR
```

3. In the same file, directly before the line `          install -m 700 -d ~/.ssh`, insert exactly (10 leading spaces, like the lines around it):

```
          # 0415: build the image here from the exact commit, push it to GHCR
          # and let the server pull it, so a deploy does not build on the
          # production CPU. deploy.sh falls back to a server build if the pull fails.
          IMAGE="ghcr.io/$(printf '%s' "${REPO_SLUG}" | tr '[:upper:]' '[:lower:]'):${DEPLOY_SHA}"
          SRC="$(mktemp -d)"
          git -C "${SRC}" init -q
          git -C "${SRC}" fetch -q --depth 1 "https://x-access-token:${GH_DEPLOY_TOKEN}@github.com/${REPO_SLUG}.git" "${DEPLOY_SHA}"
          git -C "${SRC}" checkout -q FETCH_HEAD
          printf '%s' "${GH_DEPLOY_TOKEN}" | docker login ghcr.io -u "${GITHUB_ACTOR}" --password-stdin
          docker build --pull -t "${IMAGE}" "${SRC}"
          docker push "${IMAGE}"
          docker logout ghcr.io
          rm -rf "${SRC}"
          echo "Pushed ${IMAGE}"
```

4. In the same file, replace the heredoc lines

```
          DEPLOY_SHA="${DEPLOY_SHA}"
          TARGET="${TARGET}"
```

   with

```
          DEPLOY_SHA="${DEPLOY_SHA}"
          UBYHOST_IMAGE="${IMAGE}"
          TARGET="${TARGET}"
```

5. In the same file, replace

```
          chmod +x scripts/*.sh
          ./scripts/deploy.sh
          REMOTE
```

   with

```
          chmod +x scripts/*.sh
          UBYHOST_IMAGE="\${UBYHOST_IMAGE}" ./scripts/deploy.sh
          REMOTE
```

   Command: `python3 -c "import yaml;yaml.safe_load(open('.github/workflows/deploy-lightsail.yml'));print('yaml ok')" 2>&1 | tail -30` → `yaml ok`. Then `grep -n "UBYHOST_IMAGE\|packages: write\|docker push" .github/workflows/deploy-lightsail.yml 2>&1 | tail -30` → 5 lines.

6. In `.github/workflows/deploy-production.yml` and in `.github/workflows/deploy-staging.yml`, replace the workflow-level block

```
permissions:
  contents: read
  checks: read
```

   with

```
permissions:
  contents: read
  checks: read
  packages: write # 0415: deploy-lightsail.yml pushes the image to GHCR
```

   Command: `grep -c "packages: write" .github/workflows/deploy-production.yml .github/workflows/deploy-staging.yml 2>&1 | tail -30` → `1` for each file.

7. If docker is available, run `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.9 -color 2>&1 | tail -30` → no output. If docker is not available, write that in the report; CI runs it.

8. Write the report, commit.

## 5. Do not touch

`docker-compose.yml`, `Dockerfile`, `ci.yml`, `docs/`, `App/`. Never add an action or dependency. Never push, merge, set secrets or deploy.

## 6. Commands

The step commands above, plus `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root. No pytest: no Python changes.

## 7. Acceptance

- [ ] `deploy.sh` passes `bash -n` (and shellcheck `-S error` if installed).
- [ ] All three workflows parse as YAML and grant `packages: write`.
- [ ] `deploy-lightsail.yml` builds, pushes and passes `UBYHOST_IMAGE` to `deploy.sh` on the server.
- [ ] A manual `./scripts/deploy.sh` with no `UBYHOST_IMAGE` still runs `docker compose build --pull`.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a check fails twice, you reach 25 tool calls or about 50k tokens, a file outside §3 needs a change, or a step is unclear.

## 9. Report

Write `docs/tasks/0415-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Commit; the orchestrator pushes and opens the PR.

## Risk list (for the reviewer)

`.github/workflows/deploy-lightsail.yml` (token handling, heredoc escaping), `deploy/lightsail/scripts/deploy.sh`.

## Owner steps

1. Merge, then run **Actions → Deploy staging** once. The log shows `Pushed ghcr.io/jsfpechar-ops/jsfpecharoperations:<sha>`. The server log may show the fallback warning on this first run, because the new package starts private.
2. On GitHub: your profile → **Packages** → `jsfpecharoperations` → **Package settings** → **Change visibility** → **Public** → confirm. The image holds only the public app code; secrets stay in the server `.env`.
3. Run **Deploy staging** again: the server log now says `Using CI-built image`. Then production deploys use it too.
