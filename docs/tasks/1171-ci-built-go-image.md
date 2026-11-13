# 1171: CI builds and pushes the Go image too; the server never builds on a CI deploy

Status: review
Depends on: 0422 (merged: Python image already built in CI) | Base commit: current main | Branch: task/1171-ci-built-go-image
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens
Tier: C. Review: orchestrator reads the diff. Report: docs/tasks/1171-report.md

## 1. Objective

Owner decision 2026-11-13: images are built in GitHub Actions and pushed to GHCR (ghcr.io); the server only pulls and restarts. Reason: the target server is 1 vCPU / 2 GB, and on-host builds grow the build cache (about 6 GB in 14 days) and spike the CPU on every deploy. Brief 0422 already does this for the Python image. This brief finishes it: the Go image (`go/Dockerfile`, a Go compile) is built in CI and pulled too, and a failed pull on a CI deploy stops the deploy with the old containers still running (today it silently builds on the server). Prune of old images and build cache and the `:previous` rollback tags already exist and stay as they are.

## 2. Context (what exists today, verified)

- `.github/workflows/deploy-lightsail.yml` (reusable; production auto-deploys after CI is green on main, rule 8 stays): the step "Deploy Lightsail" already refuses unless CI checks are green, then builds the Python image with `docker build --pull -t "${IMAGE}" "${SRC}"` from a clean `git fetch` checkout in `mktemp -d`, pushes it to `ghcr.io/<repo>:<full sha>`, and passes `UBYHOST_IMAGE` to `deploy.sh` over SSH. `permissions: packages: write` is already set there and in `deploy-production.yml`. No third-party action is used for this: plain `docker login ghcr.io` with `GITHUB_TOKEN`. Keep it that way.
- `deploy/lightsail/scripts/deploy.sh` lines 202-216 pull `UBYHOST_IMAGE` and tag it `ubyhost:local`; if the pull fails it falls back to `docker compose build --pull` on the server. Lines 242-250 always run `docker compose build ubyhost-go` on the server. Lines 406-409 prune dangling images and build cache older than 72 h after success. Lines 40-60 `rollback()` restores `ubyhost:previous` and `ubyhost-go:previous`.
- `deploy/lightsail/docker-compose.yml`: services `ubyhost` (`build:` root `Dockerfile`, `image: ubyhost:local`), `ubyhost-go` (`build:` `go/Dockerfile`, `image: ubyhost-go:local`, profile `go`), `walg` (`build: ./walg`, `image: ubyhost-walg:local`, profile `walg`). All other services use pinned registry images. **Compose is not changed**: `build:` stays for local dev and manual deploys, the server just tags the pulled image with the `:local` name compose already uses.
- Secret safety (checked by the brief writer, you re-check in step 1): the CI build context is a clean git checkout, so an untracked server `.env` or database can never enter it. Root `.dockerignore` already excludes `.git`, `.github`, `docs/`, `**/.env`, `**/.env.*` (except `.env.example`), `App/data/*`, `App/tests`, `*.md`. `Dockerfile` copies only `App/requirements.lock`, `App/`, `docker-entrypoint.sh`. `go/Dockerfile` copies only `go/` and `App/migrations_pg/`. The images are public (public repo), so this check is part of the brief.
- The `walg` image is not part of this brief: it is built once when absent (compose builds only if the image is missing) and almost never changes.
- `docker/*` actions are not used anywhere in the repo; do not add any action.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/deploy-lightsail.yml` | edit | build and push the Go image, add moving tag, pass `UBYHOST_GO_IMAGE` |
| `deploy/lightsail/scripts/deploy.sh` | edit | pull both images before anything changes; fail closed; skip the on-server Go build |
| `docs/LIGHTSAIL.md` | edit | one paragraph in "Deploy from GitHub Actions", one rollback-by-SHA block |
| `docs/tasks/1171-report.md` | create | the report |
| `docs/tasks/1171-ci-built-go-image.md` | edit | `Status:` line only |

No other file may change. Do not touch `App/`, `go/`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `ci.yml`.

## 4. Steps

Every Before text must be found exactly once (`grep -nF`). Not found: STOP (section 8). Commit after each step with `1171 step k`.

### Step 1: verify nothing secret enters the images (no edit)

Run:

```bash
grep -nE '^(COPY|ADD)' Dockerfile go/Dockerfile 2>&1 | tail -30
grep -nE '^\*\*/\.env|^App/data|^docs/|^\.git$|^App/tests' .dockerignore 2>&1 | tail -30
git ls-files | grep -E '(^|/)\.env$|\.db$|\.sqlite3?$|\.pem$' | tail -30
```

Expected: the COPY lines are exactly `App/requirements.lock`, `App/`, `docker-entrypoint.sh`, `go/go.mod go/go.sum`, `go/`, `--from=builder ...`, `App/migrations_pg/`; the `.dockerignore` greps print all five patterns; the third command prints nothing (or only `.env.example`-style names that are not `.env`). Anything else: STOP and report it, do not continue.

### Step 2: `.github/workflows/deploy-lightsail.yml`

Edit 1. Before:

````text
          IMAGE="ghcr.io/$(printf '%s' "${REPO_SLUG}" | tr '[:upper:]' '[:lower:]'):${DEPLOY_SHA}"
````

After:

````text
          IMAGE_REPO="ghcr.io/$(printf '%s' "${REPO_SLUG}" | tr '[:upper:]' '[:lower:]')"
          IMAGE="${IMAGE_REPO}:${DEPLOY_SHA}"
          GO_IMAGE="${IMAGE_REPO}-go:${DEPLOY_SHA}"
````

Edit 2. Before:

````text
          docker build --pull -t "${IMAGE}" "${SRC}"
          docker push "${IMAGE}"
          docker logout ghcr.io
          rm -rf "${SRC}"
          echo "Pushed ${IMAGE}"
````

After:

````text
          docker build --pull -t "${IMAGE}" "${SRC}"
          docker build --pull -f "${SRC}/go/Dockerfile" -t "${GO_IMAGE}" "${SRC}"
          docker push "${IMAGE}"
          docker push "${GO_IMAGE}"
          # Moving tags (production or staging) for humans; deploys always use the commit tag.
          docker tag "${IMAGE}" "${IMAGE_REPO}:${TARGET}"
          docker tag "${GO_IMAGE}" "${IMAGE_REPO}-go:${TARGET}"
          docker push "${IMAGE_REPO}:${TARGET}"
          docker push "${IMAGE_REPO}-go:${TARGET}"
          docker logout ghcr.io
          rm -rf "${SRC}"
          echo "Pushed ${IMAGE} and ${GO_IMAGE}"
````

Edit 3 (heredoc passed to the server; keep the 10 leading spaces). Before:

````text
          UBYHOST_IMAGE="${IMAGE}"
          TARGET="${TARGET}"
````

After:

````text
          UBYHOST_IMAGE="${IMAGE}"
          UBYHOST_GO_IMAGE="${GO_IMAGE}"
          TARGET="${TARGET}"
````

Edit 4. Before:

````text
          UBYHOST_IMAGE="\${UBYHOST_IMAGE}" ./scripts/deploy.sh
````

After:

````text
          UBYHOST_IMAGE="\${UBYHOST_IMAGE}" UBYHOST_GO_IMAGE="\${UBYHOST_GO_IMAGE}" ./scripts/deploy.sh
````

Edit 5 (comment above the build). Before:

````text
          # production CPU. deploy.sh falls back to a server build if the pull fails.
````

After:

````text
          # production CPU. deploy.sh stops (old containers keep running) if a pull fails.
````

Command:

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy-lightsail.yml')); print('yaml ok')" 2>&1 | tail -30
grep -c "GO_IMAGE" .github/workflows/deploy-lightsail.yml 2>&1 | tail -30
```

Expected: `yaml ok`; the count prints `6` or more.

### Step 3: `deploy/lightsail/scripts/deploy.sh`

Edit 1 (replace the whole pull-or-build block, lines 202-216). Before:

````text
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
````

After:

````text
# 1171: with UBYHOST_IMAGE set (the GitHub deploy) the server never builds: both
# images are pulled first, and a failed pull stops here, before anything is
# changed, so the old containers keep running. Without it (a manual deploy on
# the server) the images are built here as before.
if [ -n "${UBYHOST_IMAGE:-}" ]; then
  if ! docker pull "${UBYHOST_IMAGE}"; then
    echo "ERROR: could not pull ${UBYHOST_IMAGE}. Nothing was changed; the old containers keep running. Check that the GHCR package is public (docs/LIGHTSAIL.md, Deploy from GitHub Actions)." >&2
    exit 1
  fi
  echo "==> Using CI-built image ${UBYHOST_IMAGE}"
  docker tag "${UBYHOST_IMAGE}" ubyhost:local
  # Drop the extra tag so old commit images do not pile up on the disk.
  docker image rm "${UBYHOST_IMAGE}" >/dev/null
  if [ -n "${UBYHOST_GO_IMAGE:-}" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
    if ! docker pull "${UBYHOST_GO_IMAGE}"; then
      echo "ERROR: could not pull ${UBYHOST_GO_IMAGE}. Nothing was changed; the old containers keep running. Check that the GHCR package is public (docs/LIGHTSAIL.md, Deploy from GitHub Actions)." >&2
      exit 1
    fi
    echo "==> Using CI-built Go image ${UBYHOST_GO_IMAGE}"
    docker tag "${UBYHOST_GO_IMAGE}" ubyhost-go:local
    docker image rm "${UBYHOST_GO_IMAGE}" >/dev/null
  fi
else
  echo "==> Building image"
  docker compose build --pull
fi
````

Edit 2 (skip the on-server Go build when the Go image was pulled). Before:

````text
if docker compose config --services | grep -qx 'ubyhost-go'; then
  # Rebuild the local Go image so a merged change reaches production.
````

After:

````text
if [ -z "${UBYHOST_IMAGE:-}" ] && docker compose config --services | grep -qx 'ubyhost-go'; then
  # Manual deploy only (1171): a GitHub deploy pulled the Go image above.
  # Rebuild the local Go image so a merged change reaches production.
````

Note for the executor: with `UBYHOST_IMAGE` set and `UBYHOST_GO_IMAGE` unset (an old workflow run), the Go image is simply not updated; do not add a build fallback.

Command:

```bash
shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30
bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30
```

Expected: no output from either.

### Step 4: `docs/LIGHTSAIL.md`

Edit 1. Before:

````text
Workflow **Deploy production** pins the run to the current `main` revision, verifies CI is green for it, then SSHs and runs `git reset --hard` + `./scripts/deploy.sh`.
````

After:

````text
Workflow **Deploy production** pins the run to the current `main` revision, verifies CI is green for it, builds the app image and the Go image on the GitHub runner, pushes both to GHCR (`ghcr.io/<owner>/<repo>:<commit sha>` and `...-go:<commit sha>`, plus a moving `production` or `staging` tag), then SSHs and runs `git reset --hard` + `./scripts/deploy.sh`. The server only pulls the two images; it does not build on a GitHub deploy (a manual `./scripts/deploy.sh` on the server still builds). If a pull fails, `deploy.sh` stops before changing anything and the old containers keep running. The images are public because the repo is public; GHCR creates each new package as private, so after the first push of a new package the owner sets it to public (Packages, the package, Package settings, Change visibility).
````

Edit 2 (rollback block, add after the existing code block). Before:

````text
Rollback **UbyPort target** (test ↔ prod): edit `.env` `UBYHOST_UBYPORT_ENV`, then `./scripts/deploy.sh`.
````

After:

````text
Rollback **to an earlier deployed commit** by its image (no build; only commits that were deployed from GitHub have images). One command on the server, with `SHA` the full 40-character commit and `REPO` the lowercase `owner/repo`:

```bash
cd /opt/ubyhost && SHA=<full-sha> REPO=<owner/repo> && git fetch origin "$SHA" && git reset --hard "$SHA" && cd deploy/lightsail && UBYHOST_IMAGE="ghcr.io/$REPO:$SHA" UBYHOST_GO_IMAGE="ghcr.io/$REPO-go:$SHA" ./scripts/deploy.sh
```

The quicker undo of the last deploy is the automatic one: `deploy.sh` restores `ubyhost:previous` and `ubyhost-go:previous` by itself when a deploy fails its checks.

Rollback **UbyPort target** (test ↔ prod): edit `.env` `UBYHOST_UBYPORT_ENV`, then `./scripts/deploy.sh`.
````

Command:

```bash
grep -c "UBYHOST_GO_IMAGE\|ghcr.io" docs/LIGHTSAIL.md 2>&1 | tail -30
```

Expected: `3` or more.

### Step 5: report and status line

Create `docs/tasks/1171-report.md` (600 tokens at most, format in executor.md). Change only the `Status:` line of this brief to `review`.

## 5. Do not touch

Everything not in section 3. Do not remove the pruning at the end of `deploy.sh`. Do not add `docker/*` actions or any other action. Do not add `docker image prune -a`. Do not change `docker-compose.yml`.

## 6. Commands

```bash
shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-lightsail.yml')); print('yaml ok')" 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

These are the test-map row "Deploy scripts, Caddyfile, compose". No pytest. CI runs the rest, including the `docker` job that builds both images.

## 7. Acceptance

- [ ] Step 1 greps show no secret path in either image's COPY set.
- [ ] `shellcheck` prints nothing; `yaml ok`; context lint passes.
- [ ] `grep -nF "building on the server instead" deploy/lightsail/scripts/deploy.sh` prints nothing.
- [ ] `grep -c "docker compose build" deploy/lightsail/scripts/deploy.sh` still counts the two manual-deploy build lines only (the `--pull` one and the `ubyhost-go` one, now guarded by `-z "${UBYHOST_IMAGE:-}"`).
- [ ] The prune lines at the end of `deploy.sh` are unchanged.
- [ ] No new third-party action: `grep -n "uses:" .github/workflows/deploy-lightsail.yml` prints nothing new.
- [ ] PR opened as **draft** (rule 8: green merges auto-deploy).

## 8. Stop and ask

An anchor is not found verbatim; Step 1 shows an unexpected file; shellcheck reports an error you cannot fix in one try; line numbers differ by more than 10 from section 2.

## 9. Report

`docs/tasks/1171-report.md`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left (below). Set `Status: review`, open one draft PR.

## Owner steps (after the draft PR is green; plain words)

Before merging, so the first real deploy does not fail on a private package:

1. On GitHub open the repo, then Actions, then "Deploy staging" in the left list, then "Run workflow". Choose the PR branch `task/1171-ci-built-go-image` and start it. It builds and pushes both images (the staging server pull of the new Go package may fail the first time because the package is still private; that is expected and harmless, nothing on staging changes).
2. On GitHub open your profile or the organisation page, then "Packages". Open the package named like the repo with `-go` at the end. Click "Package settings" (right side), scroll to "Danger Zone", click "Change visibility", choose "Public", type the package name to confirm. Do the same for the package without `-go` if it is not already public.
3. Run "Deploy staging" once more on the same branch; it should now pass.
4. Click "Ready for review" on the PR and merge it (or use `scripts/merge-pr-on-green.sh`). Production deploys by itself.
5. First production deploy: the server already holds an old locally built `ubyhost-go:local`; the new run pulls both images and tags them. Nothing else to do. If the run shows "could not pull", step 2 was missed: do step 2, then Actions, Deploy production, Run workflow, type DEPLOY. The old site kept running the whole time.
6. After a week, SSH not needed: the build cache stops growing because the server no longer builds. To check, run `docker system df` on the server once; the build cache line should stay near 0.
