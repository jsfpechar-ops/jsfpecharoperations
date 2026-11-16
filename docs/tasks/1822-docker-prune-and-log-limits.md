# 1822: Docker and logs: prune every deploy, 10 MB x 3 log files, journald cap

Status: todo
Depends on: none | Base commit: current tip of the working branch | Branch: task/1822-docker-prune-and-log-limits
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (deploy script, compose, docs; no filing code)

## 1. Objective

After every deploy `docker system df` shows under 1 GB reclaimable, every container's log is capped at 10 MB x 3 files, and the owner has a step to cap the system journal at 100 MB.

## 2. Context

[optimization-wins](../plans/optimization-wins.md) section 7, lane E, brief 1822. Facts found in the files:

- **Prune already exists** at the end of `deploy/lightsail/scripts/deploy.sh` (lines 469-475):

```
# 0962: success is final. Drop dangling images (the old ubyhost:local of each
# deploy) and build cache older than 72 hours. Never -a: it would delete
# ubyhost:previous and digest-pinned service images. A failed prune is ignored.
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f --filter until=72h >/dev/null 2>&1 || true
echo "Pruned dangling Docker images and build cache older than 72h."
```

  `ubyhost:previous` and `ubyhost-go:previous` are tagged at lines 216 and 220 (`docker tag ubyhost:local ubyhost:previous`), and used by the rollback at lines 73-77. They are tagged, so a plain `docker image prune -f` (dangling only) never removes them. The reclaimable data that remains is the build cache younger than 72 hours (every deploy builds on the server) and old digest-pinned service images left after a pin change.
- **Logging block exists on every service, inline, no x-anchor.** Nine copies in `deploy/lightsail/docker-compose.yml`, at lines 54, 89, 136, 182, 306, 338, 373, 406, 431, 458 (ten with caddy's comment at 371-372; confirm by grep). Each is:

```
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

  Target is `max-file: "3"`. There is no `x-` anchor (`grep -n '^x-' deploy/lightsail/docker-compose.yml` prints nothing); do not add one, change the number in place so the diff stays reviewable.
- **Journald cap is an owner step.** `grep -rni journald docs/*.md deploy/lightsail/scripts/setup-server.sh` finds nothing. The right place is `docs/LIGHTSAIL.md`, section "Disk, logs, photos" (starts line 379), after the paragraph that ends "...check `docker system df`." (line ~391).
- Hard rules: 3 no secrets, no server IPs or hostnames; 4 no new dependency; plain words for owner steps; never `docker image prune -a` or `docker system prune` (they delete the rollback image and pinned service images).

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/deploy.sh` | edit | prune step at the end (lines 469-475) |
| `deploy/lightsail/docker-compose.yml` | edit | `max-file` 5 to 3 in each `logging:` block |
| `docs/LIGHTSAIL.md` | edit | owner step: journald 100 MB cap; fix the prune sentence (line ~391) |
| `docs/tasks/1822-report.md` | create | the report (§9) |

Check that no test pins `max-file`: `grep -rn "max-file" App/tests | tail -5` (expected: nothing; if a test does, STOP and ask).

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP.
   - `grep -nF 'docker builder prune -f --filter until=72h' deploy/lightsail/scripts/deploy.sh` prints one line.
   - `grep -cF 'max-file: "5"' deploy/lightsail/docker-compose.yml` prints the number of services with logging (expected 10; record the number).
   - `grep -n '^x-' deploy/lightsail/docker-compose.yml | tail -3` prints nothing.
1. `deploy.sh`: replace the two prune lines and the echo (see open question 1 for the exact scope). Default in this brief: keep `docker image prune -f` (dangling images) and drop the age filter on the cache, so the cache is emptied after every successful deploy:

```
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f >/dev/null 2>&1 || true
echo "Pruned dangling Docker images and all build cache."
```

   Update the comment above it to match (build cache of every deploy, still never `-a`). The prune stays after the success marker, so a failed deploy still rolls back with its cache. Keep `|| true`.
2. `docker-compose.yml`: change every `max-file: "5"` to `max-file: "3"` (`sed -i 's/max-file: "5"/max-file: "3"/' deploy/lightsail/docker-compose.yml` is allowed). Check the count is unchanged: `grep -cF 'max-file: "3"'` equals the number from step 0 and `grep -cF 'max-file: "5"'` prints 0. If a service has no `logging:` block, do not add one (open question 2).
3. `docs/LIGHTSAIL.md`: (a) in the paragraph at line ~391 change "`docker builder prune -f --filter until=72h`" to match step 1; (b) add after it a short owner step in plain words:

```
**One-time: cap the system journal at 100 MB (owner, once per server).**
1. Log in to the server.
2. Run: `sudo mkdir -p /etc/systemd/journald.conf.d`
3. Run: `printf '[Journal]\nSystemMaxUse=100M\n' | sudo tee /etc/systemd/journald.conf.d/ubyhost.conf`
4. Run: `sudo systemctl restart systemd-journald`
5. Check: `journalctl --disk-usage` prints 100 MB or less (it may take a day to shrink).
```

   Add one sentence that container logs are capped at 10 MB x 3 files each by the compose file.
4. Commands in §6; write the report.

## 5. Do not touch

`docker-compose.yml` anything except `max-file`; the rollback code in `deploy.sh` (lines 60-125) and the `docker tag ... :previous` lines (216, 220); `docker image prune -a`, `docker system prune`, `docker volume prune` anywhere; `setup-server.sh`; any server file. No hostnames or IPs.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` is silent (test-map row: "Deploy scripts, Caddyfile, compose").
- `docker compose -f deploy/lightsail/docker-compose.yml config -q 2>&1 | tail -10` is silent. If `docker` or env variables are missing in the sandbox, run `python3 -c "import yaml;yaml.safe_load(open('deploy/lightsail/docker-compose.yml'))" 2>&1 | tail -5` and say so in the report.
- `cd App && .venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_go_compose_mail_env.py -q --tb=short -x 2>&1 | tail -30` passes (compose-reading tests).
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean.

## 7. Acceptance

- [ ] `grep -cF 'max-file: "5"' deploy/lightsail/docker-compose.yml` prints 0 and `max-file: "3"` appears in every former place.
- [ ] `deploy.sh` still never runs `prune -a` or `system prune` (`grep -n "prune" deploy/lightsail/scripts/deploy.sh | tail -10` shows only the two lines above).
- [ ] `docs/LIGHTSAIL.md` has the five owner steps for journald.
- [ ] `git diff --stat` lists only §3 paths; one commit per step (`1822 step k`).

Owner check after the merge (hand over in the report): after the next deploy run `docker system df` and read the RECLAIMABLE column: the total is under 1 GB; run `docker images | grep previous` and see `ubyhost:previous` and `ubyhost-go:previous` still there.

## 8. Stop and ask

Stop and write the report if: an anchor is not found; the compose block differs from §2; a test pins `max-file`; a test fails twice; 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, SSH or deploy.

## 9. Report

`docs/tasks/1822-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left (the journald steps and the `docker system df` check). Then set `Status: review` and open one PR.

## Risk list (for the reviewer)

`deploy/lightsail/scripts/deploy.sh` (the prune must never remove the rollback image), `deploy/lightsail/docker-compose.yml`.

## Open questions for the orchestrator

1. **Is the goal reachable with the default step 1?** The prune already runs every deploy, yet reclaimable space is not under 1 GB today, and this cannot be measured from the files. Two likely sources: build cache (step 1 removes the 72 h filter) and old pinned images (a changed digest leaves the old image unused but tagged, so `image prune -f` skips it). If after one deploy `docker system df` is still over 1 GB, the orchestrator must decide between `docker image prune -a --filter "until=..."` (risk: removes `:previous` if it is old enough; it would need the two `:previous` tags excluded by a different approach) and listing unused pinned images by hand. Ask the owner to paste `docker system df -v | head -40` before deciding. Brief 1800 (CI builds, server only pulls) removes the build cache source entirely.
2. **Services without a `logging:` block.** Compose lists more services than logging blocks if any service (for example ones under a `profiles:` entry) lacks it. The executor only changes the numbers; confirm with the owner if a service should get a block.
3. **`max-size`.** The plan says 10 MB x 3; the file already has 10m. Only `max-file` changes.
