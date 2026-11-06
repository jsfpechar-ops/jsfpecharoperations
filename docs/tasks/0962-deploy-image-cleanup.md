# 0962: Deploy prunes old Docker images and build cache

Status: in-progress
Depends on: none | Base commit: 97ccfc5 | Branch: claude/zealous-planck-raxu4v (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

After every successful deploy, `deploy.sh` removes dangling Docker images and build cache older than 72 hours, and keeps a rollback image for the Go service the same way it already does for the app. This stops the production disk filling up (14% to 50% in 6 days, 297 images, 66.6 GB reclaimable, because every deploy leaves the old `ubyhost:local` untagged and nothing prunes).

## 2. Context

- Production facts (2026-11-06): `docker image prune -f` freed 42.4 GB, `docker builder prune -f --filter until=72h` brought the disk to 8%.
- Remaining images that MUST survive: `ubyhost:previous` (auto-rollback), `ubyhost:local`, `ubyhost-go:local`, and digest-pinned service images (postgres, litestream, caddy, cadvisor) that show as `<none>` tags but are in use. Therefore `docker image prune -a`, `docker system prune` and `docker volume prune` are FORBIDDEN. Only `docker image prune -f` (dangling only) and `docker builder prune -f --filter until=72h`.
- A failed prune must never fail or roll back a deploy: every prune line ends `|| true`, and the prune runs only after success is final (after `.deployed-sha` is written), never inside `rollback()`.
- `deploy.sh` DOES build the Go image (`docker compose build ubyhost-go`, compose service `ubyhost-go`, image `ubyhost-go:local`, profile `go`), so the Go keep-previous pattern is included. `ubyhost-go:previous` is tagged only if `ubyhost-go:local` exists, and restored in `rollback()` only if `ubyhost-go:previous` exists, mirroring the app lines.

Anchors in `deploy/lightsail/scripts/deploy.sh` (verbatim):

Anchor A (inside `rollback()`):
```
  if docker image inspect ubyhost:previous >/dev/null 2>&1; then
    docker tag ubyhost:previous ubyhost:local
  fi
```

Anchor B (before the build):
```
if docker image inspect ubyhost:local >/dev/null 2>&1; then
  docker tag ubyhost:local ubyhost:previous
  echo "Kept the running image as ubyhost:previous for rollback."
fi
```

Anchor C (last lines of the file):
```
# 0710: this commit is now the rollback target.
git rev-parse HEAD > .deployed-sha
```

Anchor D, docs, `docs/LIGHTSAIL.md` section "## Disk, logs, photos":
```
Photos grow until hosts verify IDs or the 30-day stale sweep runs.
```

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/deploy.sh | edit | Go previous tag, Go rollback restore, post-success prune |
| docs/LIGHTSAIL.md | edit | One paragraph under "Disk, logs, photos" |
| docs/tasks/0962-deploy-image-cleanup.md | edit | Status line only |
| docs/tasks/0962-report.md | create | Report |

No other file may change.

## 4. Steps

Set `Status: in-progress` in this brief first. Before every step: `grep -nF "<first line of the anchor>" <file>`; not found means STOP (§8). After every step: `git commit -am "0962 step k"`.

1. Go rollback restore. In `deploy.sh`, find Anchor A (it appears once, inside `rollback()`). Insert directly after its closing `fi`:
```
  if docker image inspect ubyhost-go:previous >/dev/null 2>&1; then
    docker tag ubyhost-go:previous ubyhost-go:local
  fi
```
Command: `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30`. Expected: no output.

2. Go keep-previous. Find Anchor B. Insert directly after its closing `fi`:
```
if docker image inspect ubyhost-go:local >/dev/null 2>&1; then
  docker tag ubyhost-go:local ubyhost-go:previous
  echo "Kept the running Go image as ubyhost-go:previous for rollback."
fi
```
Command: `grep -n 'ubyhost-go:previous' deploy/lightsail/scripts/deploy.sh | tail -30`. Expected: 4 matching lines (two in rollback, two here, counting the echo).

3. Prune after success. Find Anchor C (end of file). Append after `git rev-parse HEAD > .deployed-sha`:
```

# 0962: success is final. Drop dangling images (the old ubyhost:local of each
# deploy) and build cache older than 72 hours. Never -a: it would delete
# ubyhost:previous and digest-pinned service images. A failed prune is ignored.
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f --filter until=72h >/dev/null 2>&1 || true
echo "Pruned dangling Docker images and build cache older than 72h."
```
Command: `grep -n 'prune' deploy/lightsail/scripts/deploy.sh | tail -30`. Expected: the comment line plus 3 command/echo lines, all after the `.deployed-sha` line, none inside `rollback()`, and no `-a`.

4. Docs. In `docs/LIGHTSAIL.md`, find Anchor D. Insert this paragraph directly after the paragraph that contains Anchor D (blank line before and after):
```
Every successful deploy runs `docker image prune -f` and `docker builder prune -f --filter until=72h`, so old app images and stale build cache do not fill the disk. Never run `docker image prune -a` or `docker system prune`: they delete `ubyhost:previous` (the rollback image) and the pinned service images. If the disk is above 70% between deploys, run the two commands by hand and check `docker system df`.
```
Command: `grep -n 'prune' docs/LIGHTSAIL.md | tail -30`. Expected: one line containing the new paragraph.

5. Shellcheck. Command: `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`. Expected: no output. If `shellcheck: command not found`, run `sudo apt-get install -y shellcheck 2>&1 | tail -5`, then rerun.

6. Report and branch. Write `docs/tasks/0962-report.md` (§9), set `Status: review` in this brief, then `git add docs/tasks/0962-report.md docs/tasks/0962-deploy-image-cleanup.md && git commit -m "0962 report" 2>&1 | tail -30` and `git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30`. Expected: push succeeds. Do NOT open a PR (the orchestrator does).

## 5. Do not touch

- The existing lines of `rollback()` and every other line of `deploy.sh`: only the insertions in steps 1 to 3.
- Any other script, compose file, workflow or test.
- AGENTS.md hard rules that apply: no new dependency, no secrets, never push to `main`, no deploy.

## 6. Commands

- `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30` expects no output.
- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` expects no output.
- `git diff 97ccfc5 --stat 2>&1 | tail -30` expects only the files in §3.
- No pytest: test-map row "Deploy scripts" is shellcheck only.

## 7. Acceptance

- [ ] `grep -c 'prune -a\|system prune' deploy/lightsail/scripts/deploy.sh` prints 0 (the comment says "Never -a", which does not match).
- [ ] The three prune lines are after `.deployed-sha` and outside `rollback()`.
- [ ] `ubyhost-go:previous` is tagged before the build and restored in `rollback()`.
- [ ] shellcheck and `bash -n` print nothing.
- [ ] `git diff 97ccfc5 --stat` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim;
- shellcheck fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- `git push` is refused (hand the exact command to the owner);
- a step is unclear.

## 9. Report

Write `docs/tasks/0962-report.md` (600 tokens at most) and set `Status: review`. The report has: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/scripts/deploy.sh`: `rollback()` must behave as before for the app (the Go restore is guarded by `docker image inspect`, so it is a no-op when no Go image exists); the prune must come after `.deployed-sha`, use only `image prune -f` and `builder prune -f --filter until=72h`, and every prune line must end `|| true`.

## Owner steps

Plain words, in order. The executor cannot do these.

1. Merge the PR with `scripts/merge-pr-on-green.sh`, then deploy as usual.
2. Create the disk alert in Grafana Cloud:
   1. Open your Grafana Cloud site and sign in.
   2. In the left menu click "Alerting", then "Alert rules", then the blue "New alert rule" button.
   3. Name it "Disk above 70%".
   4. For the query, pick your Prometheus data source, switch the editor to "Code", and paste:
      `100 * (1 - node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"})`
   5. Under "Alert condition" choose "Is above" and type `70`.
   6. Set "Pending period" (for) to `15m`.
   7. Pick or create a folder and an evaluation group (every `1m` is fine).
   8. Under "Configure notifications" pick a contact point that sends to your email (if none exists: "Alerting" > "Contact points" > "Add contact point", type Email, enter your address, Save, then select it here).
   9. Click "Save rule and exit". Optionally use "Test" on the contact point to confirm the email arrives.
3. Fix the "CPU usage % (7d)" panel (shows about 600% instead of about 6%):
   1. Open the dashboard and hover the panel "CPU usage % (7d)".
   2. Click the three dots (or press `e`) and choose "Edit".
   3. Check the query is `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[11m])))`. Do not change it.
   4. In the right-hand options, search for "Unit" (under "Standard options").
   5. Open the Unit list and choose "Percent (0-100)". Do not choose "Percent (0.0-1.0)".
   6. Click "Save dashboard" (top right), then "Save". The panel should now show a small number like 6%.
4. After the deploy, on the server run `docker system df`. Write down the Images line. After the NEXT deploy run it again and confirm Images RECLAIMABLE stays small (a few GB at most, not tens of GB) and the disk (`df -h /`) does not climb.
