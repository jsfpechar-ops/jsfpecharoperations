# 1210 report

Status: review
Branch: claude/lucid-pascal-grjjn9 (not task/1210-ci-built-go-image, see Deviations). Not pushed, no PR.

## Files changed

- `.github/workflows/deploy-lightsail.yml`: builds and pushes the Go image (`-go`), moving tags, passes `UBYHOST_GO_IMAGE`. Commit cf0109d4.
- `deploy/lightsail/scripts/deploy.sh`: pulls both images before tagging anything and fails closed on a pull error; the on-server Go build is skipped only when a Go image was pulled (`GO_IMAGE_PULLED`). Commits 33993202, then the review-fix commit.
- `docs/LIGHTSAIL.md`: GitHub deploy paragraph and rollback-by-SHA block. Commit d1310cb8.
- `docs/tasks/1210-report.md` (this file), `docs/tasks/1210-ci-built-go-image.md` (Status line only).

## Steps

- Step 1 (secret check): done, matches expectations (see below).
- Step 2 (workflow): done.
- Step 3 (deploy.sh): done.
- Step 4 (LIGHTSAIL.md): done.
- Step 5 (report, status): done.

## Command output

- Step 1 `grep -nE '^(COPY|ADD)'`: `Dockerfile:18 App/requirements.lock`, `:21 App/`, `:22 docker-entrypoint.sh`; `go/Dockerfile:4 go/go.mod go/go.sum`, `:6 go/`, `:11 --from=builder`, `:12 App/migrations_pg/`. No other COPY.
- Step 1 `.dockerignore`: `.git`, `App/data/*`, `docs/`, `App/tests`, `**/.env`, `**/.env.*` all present.
- Step 1 tracked `.env`/`.db`/`.sqlite`/`.pem`: none.
- Step 2 `yaml ok`; `GO_IMAGE` count `7`.
- Step 3 `bash -n deploy/lightsail/scripts/deploy.sh`: exit 0, no output.
- Step 3 `shellcheck`: NOT RUN. `command -v shellcheck` returns nothing on this machine (exit 1). This check is still open.
- Step 4 `grep -c "UBYHOST_GO_IMAGE\|ghcr.io"`: `2` (lines). Occurrence count is 4 (`ghcr.io` x3, `UBYHOST_GO_IMAGE` x1), so the brief's "3 or more" is met by occurrences.
- Final `python3 scripts/context_lint.py`: `context lint: OK`, exit 0 (WARN lines are pre-existing notices).

## Acceptance (section 7)

- Secret greps clean: yes.
- shellcheck silent: NOT VERIFIED (not installed).
- yaml ok and lint pass: yes.
- `building on the server instead` absent: yes.
- `docker compose build` lines: 2 (manual `--pull`; `ubyhost-go` build guarded by `GO_IMAGE_PULLED != 1`).
- Prune block at end of deploy.sh unchanged: yes (not in the diff).
- No new `uses:`: yes.
- PR as draft: NOT DONE (see Deviations).

## Deviations

- Branch: the brief says `task/1210-ci-built-go-image`; I stayed on `claude/lucid-pascal-grjjn9` as instructed.
- No PR opened and nothing pushed, per the run instructions.
- Step 4 count: brief expected `3` or more lines; grep -c counts lines and gives 2. Occurrences give 4. Documentation content is as specified.
- Status set to `review` per step 5, but shellcheck could not run, so the brief's acceptance is not fully verified. Run `shellcheck -S error deploy/lightsail/scripts/*.sh` before merge, or rely on CI.
- Review fix: on a GitHub deploy with `UBYHOST_GO_IMAGE` empty (an old workflow run), the server now builds the Go image, because the coordinator asked for the build to be skipped only when a Go image was pulled. This goes against brief section 4's note ("do not add a build fallback"). Owner or orchestrator to decide whether to keep it.
- Step 2 anchors were found at different line numbers than the brief lists (workflow lines 116/122/140/191/115). Text matched exactly, so I applied the edits.

## Questions

- Confirm that `shellcheck` is acceptable to run in CI only, since it is not on this machine.

## Owner steps left

Per the brief: run "Deploy staging" on the PR branch, set the new `-go` GHCR package(s) to public, rerun staging, then mark the PR ready and merge. Production then auto-deploys.
