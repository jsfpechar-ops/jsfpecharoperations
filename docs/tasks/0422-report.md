# 0422 report: CI-built image

Status: review
Branch: task/0422-ci-built-image | Executor: Haiku 5.5

## Files changed

- `deploy/lightsail/scripts/deploy.sh`: pulls `UBYHOST_IMAGE` if set and tags it `ubyhost:local`; else builds as before.
- `.github/workflows/deploy-lightsail.yml`: `packages: write`; builds from the DEPLOY_SHA commit, pushes to GHCR; passes `UBYHOST_IMAGE` to the server.
- `.github/workflows/deploy-production.yml`, `.github/workflows/deploy-staging.yml`: `packages: write`.
- `docs/tasks/0422-ci-built-image.md`: Status set to in-progress, then review.
- `docs/tasks/0422-report.md`: this file.

## Commands (last lines)

- `bash -n deploy/lightsail/scripts/deploy.sh && ... shellcheck`: no output from bash -n; `no shellcheck` (not installed).
- `python3 yaml.safe_load deploy-lightsail.yml`: `yaml ok`. Production and staging also parse: `yaml ok`.
- `grep -n "UBYHOST_IMAGE\|packages: write\|docker push" deploy-lightsail.yml`: 4 lines (46, 123, 140, 191). Brief expected 5; see Deviations.
- `grep -c "packages: write"` on the two caller files: `1` each.
- actionlint via docker: `failed to connect to the docker API at unix:///var/run/docker.sock ... no such file or directory`. Not run; CI runs it.
- `python3 scripts/context_lint.py`: `context lint: OK` (exit 0). Only WARN lines about other open briefs.

## Section 7 checklist

- [x] `deploy.sh` passes `bash -n`. shellcheck not installed, not run.
- [x] All three workflows parse as YAML and grant `packages: write`.
- [x] `deploy-lightsail.yml` builds, pushes and passes `UBYHOST_IMAGE` to `deploy.sh`.
- [x] Manual `./scripts/deploy.sh` with no `UBYHOST_IMAGE` still runs `docker compose build --pull` (else branch, verified by reading the code only).

## Deviations

- Commits: step 1 includes the status change to in-progress. Step 2 and 3 share one commit (`0422 step 2`). Steps 4 and 5 share one commit (`0422 step 4`). Step 6 is its own commit. Edits are in the same files; splitting them needed interactive staging.
- Step 5 grep: the brief expects 5 lines; the file has 4 matches, each checked by reading. No extra line is missing from the brief's content.
- Step 7: docker daemon not reachable.

## Questions

- None blocking. The security hook warned about GitHub Actions injection risks. The new lines use only env values (`REPO_SLUG`, `DEPLOY_SHA`, `GH_DEPLOY_TOKEN`, `GITHUB_ACTOR`), not `github.event.*` input.

## Owner steps left

1. Merge, then run Actions → Deploy staging once. Expect `Pushed ghcr.io/...:<sha>`. The first server log may show the fallback warning.
2. GitHub: profile → Packages → jsfpecharoperations → Package settings → Change visibility → Public.
3. Run Deploy staging again; the server log should say `Using CI-built image`.
