# 0962 report: deploy prunes old Docker images and build cache

Executor: Haiku 5.5. Branch: claude/zealous-planck-raxu4v. Base: 7f2a321.

## Files changed (`git diff --stat 7f2a321 HEAD`)

```
 deploy/lightsail/scripts/deploy.sh      | 14 ++++++++++++++
 docs/LIGHTSAIL.md                       |  2 ++
 docs/tasks/0962-deploy-image-cleanup.md |  2 +-
 3 files changed, 17 insertions(+), 1 deletion(-)
```

Plus this report (`docs/tasks/0962-report.md`, new).

## Steps and commands

1. Go rollback restore in `rollback()` (commit "0962 step 1", also sets brief Status to in-progress).
   `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30` gave no output, exit 0.
2. Go keep-previous after the app block (commit "0962 step 2").
   `grep -n 'ubyhost-go:previous' deploy/lightsail/scripts/deploy.sh | tail -30`:
   ```
   54:  if docker image inspect ubyhost-go:previous >/dev/null 2>&1; then
   55:    docker tag ubyhost-go:previous ubyhost-go:local
   209:  docker tag ubyhost-go:local ubyhost-go:previous
   210:  echo "Kept the running Go image as ubyhost-go:previous for rollback."
   ```
3. Prune after `.deployed-sha` (commit "0962 step 3").
   `grep -n 'prune' ... | tail -30`:
   ```
   417:# ubyhost:previous and digest-pinned service images. A failed prune is ignored.
   418:docker image prune -f >/dev/null 2>&1 || true
   419:docker builder prune -f --filter until=72h >/dev/null 2>&1 || true
   ```
4. Docs paragraph in `docs/LIGHTSAIL.md` under "## Disk, logs, photos" (commit "0962 step 4").
   `grep -n 'prune' docs/LIGHTSAIL.md | tail -30` shows the new paragraph line (354).
5. Shellcheck: `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`
   printed no output, exit 0 (after `sudo apt-get update` and `sudo apt-get install -y shellcheck`, which installed 0.9.0-1).

## Section 7 acceptance

- [x] `grep -c 'prune -a\|system prune' deploy/lightsail/scripts/deploy.sh` prints 0.
- [x] The three prune lines are after `.deployed-sha` (line 413) and outside `rollback()`.
- [x] `ubyhost-go:previous` is tagged before the build and restored in `rollback()`.
- [x] shellcheck and `bash -n` print nothing.
- [x] `git diff 7f2a321 HEAD --stat` lists only the §3 files (plus this report).

## Deviations

- Brief §6 uses `git diff 97ccfc5 --stat`, which also shows the two brief files added in 7f2a321 (0962 and 0963). Using the base 7f2a321 gives only the §3 files.
- The echo line in step 3 starts with "Pruned" (capital P), so `grep 'prune'` does not list it. The grep shows the two command lines only.
- Brief step 6 (commit of the report and brief, then push) is done in the final commit.
- Commit trailers use the Co-Authored-By line given in the task (Opus 5.5). The executor model is Haiku 5.5.

## Questions

None.

## Owner steps left

1. Open a PR from `claude/zealous-planck-raxu4v` and merge it with `scripts/merge-pr-on-green.sh`, then deploy as usual.
2. After the deploy, on the server run `docker system df` and note the Images line. After the next deploy, run it again and confirm Images RECLAIMABLE stays small and `df -h /` does not climb.
3. Optional from brief Owner steps: create the Grafana "Disk above 70%" alert and fix the "CPU usage % (7d)" unit (see the brief).
