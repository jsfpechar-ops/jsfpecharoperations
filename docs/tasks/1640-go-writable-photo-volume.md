# 1640: Go service: mount the data volume writable (owner decision 2026-11-14)

Status: todo
Tier: B (one line of deploy config; no code)
Depends on: none | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 10 tool calls, 20k tokens

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1640 step k`. Never create a branch, never push, never open a PR.

## 1. Objective

The owner decided on 2026-11-14 (decisions.md, the `2026-11-14 [dep/infra]` line) that `ubyhost-go` may write to the data volume. Change the one compose line that mounts it read-only, so that briefs 1447 (add a guide card photo), 1603 (delete a demo stay with its passport photo files), 1596 (`/demo/reset`) and 1597 (`/demo`) can run in production.

## 2. Context

Rules (AGENTS.md): 2 privacy: no new personal-data field, no new outbound request; the Go service gets the same file access the Python service has had since the start. 4 no dependency. 3 nothing secret in this file.

The Go service today (`deploy/lightsail/docker-compose.yml`):

```yaml
    volumes:
      - ubyhost-pgsock:/var/run/postgresql
      - ubyhost-data:/data:ro
    expose:
      - "8081"
```

Facts the brief writer checked:

- Both images run as uid 10001 (`App/Dockerfile` line 25: `useradd --create-home --uid 10001 ubyhost`, `chown ubyhost:ubyhost /data`; `go/Dockerfile`: `adduser -D -u 10001 ubyhost`). The files Python wrote (`passport_photos/*.enc` mode 0600, `guide_photos/*.jpg`, `property_photos/*`) are owned by 10001, so the Go process can delete and replace them with no `chown`.
- The named volume `ubyhost-data` already exists and is mounted read-write by the Python `web` (line 111) and `worker` (line 163) services; the Go service gets the same volume, not a copy.
- The Go service keeps `cap_drop: [ALL]` and `no-new-privileges`. Nothing else in the service changes.
- This is the only line to change. A narrower mount (only `guide_photos` and `passport_photos`) is not possible with a named volume without moving files, so the whole volume is writable. What Go may write is limited by code: brief 1447 writes `guide_photos/`, brief 1603 and 1596 delete from `passport_photos/`, brief 1597 later writes `passport_photos/` and `property_photos/`. The SQLite file is gone with PostgreSQL (status.md).
- No test reads this line (`grep -rn 'data:ro' App/tests` finds only the pgdata mount of the walg service).

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | line `- ubyhost-data:/data:ro` of the `ubyhost-go` service becomes `- ubyhost-data:/data` |
| `docs/LIGHTSAIL.md` | edit | one sentence under the `ubyhost-go` line (step 3) |
| `docs/tasks/1640-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `grep -nF "      - ubyhost-data:/data:ro" deploy/lightsail/docker-compose.yml | tail -3` prints exactly one line, number 286 or near it.
   - `grep -nF 'serves no traffic until a Caddy route exists (G2).' docs/LIGHTSAIL.md | tail -2` prints one line (number 56 or near it) that ends with that sentence.

1. In `deploy/lightsail/docker-compose.yml`, replace this exact text (it is unique because of the `:ro` and the `expose` line after it):

   ```
         - ubyhost-pgsock:/var/run/postgresql
         - ubyhost-data:/data:ro
       expose:
         - "8081"
   ```

   by

   ```
         - ubyhost-pgsock:/var/run/postgresql
         - ubyhost-data:/data
       expose:
         - "8081"
   ```

   (Keep the six-space indent of the list items exactly as in the file.) Check: `grep -c 'ubyhost-data:/data:ro' deploy/lightsail/docker-compose.yml | tail -1` prints `0`, and `git diff --stat | tail -3` shows 1 insertion and 1 deletion. Commit "1640 step 1".

2. Validate the file still parses (the profiles need no env for a syntax check):

   ```bash
   python3 -c "import yaml,sys; d=yaml.safe_load(open('deploy/lightsail/docker-compose.yml')); print(d['services']['ubyhost-go']['volumes'])" 2>&1 | tail -3
   ```

   Expected: `['ubyhost-pgsock:/var/run/postgresql', 'ubyhost-data:/data']`. If the `yaml` module is missing, do not install it: write "yaml missing" in the report and go on.

3. In `docs/LIGHTSAIL.md`, on the line found by the second check of step 0, append at its end (one space before the new text) this sentence, exactly:

   ```
   Its data volume is mounted writable (decision 2026-11-14): the Go routes that add a guide photo or delete passport photo files need it; after changing the mount run "docker compose --profile go up -d ubyhost-go".
   ```

   Commit "1640 step 3".

4. Run the context lint (repo root): `python3 scripts/context_lint.py 2>&1 | tail -30`. It must print no finding about the files of §3. Then write the report (§9), set `Status: review` and commit "1640 step 4".

## 5. Do not touch

Every other line of the compose file, `go/`, `App/`, `docs/context/` (the decision line is already there), Caddy files, `.env` files, `UBYHOST_GO_PATHS`.

## 6. Commands

Exactly those of §4 (steps 0, 2 and 4). No test-map row applies (config only). Never the full suite.

## 7. Acceptance

- [ ] `git diff --stat main...HEAD | tail -5` lists only the three paths of §3 (`origin/main...HEAD` if there is no local `main`); the compose file shows 1 insertion, 1 deletion.
- [ ] `grep -c 'ubyhost-data:/data:ro' deploy/lightsail/docker-compose.yml | tail -1` prints `0`.
- [ ] The `python3 -c` line of step 2 printed the two-item list (or the report says "yaml missing").
- [ ] `python3 scripts/context_lint.py` reports nothing for these files.

## 8. Stop and ask

Stop, and write the report, if an anchor of step 0 is not found, the file is not as quoted, a second file needs a change, or you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command). 10 tool calls or about 20k tokens: write the report as `blocked`.

## 9. Report

Write `docs/tasks/1640-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`deploy/lightsail/docker-compose.yml`: the diff must be the one line. Nothing else may lose its `:ro` (the pgdata mount of the walg service and the Caddy and monitoring mounts stay read-only).

## Owner steps

Nothing changes in production until you deploy. When the PR that holds this brief and the Go code of 1447 is merged and deployed:

1. On the Lightsail server, in the project folder, run `docker compose --profile go up -d ubyhost-go` (the usual deploy does this itself).
2. Check: `docker compose exec ubyhost-go sh -c 'touch /data/.w && rm /data/.w && echo writable'` prints `writable`.
3. Rollback: put `:ro` back on the line, run the same `up -d` command. The Go routes that need the volume then answer 500 for the photo files only; Python keeps serving everything else.
