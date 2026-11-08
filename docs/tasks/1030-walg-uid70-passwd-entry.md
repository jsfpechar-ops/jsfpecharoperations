# 1030: walg sidecar image needs a passwd entry for uid 70

Status: review
Depends on: none | Base commit: HEAD of branch | Branch: claude/eloquent-mendel-vd8mfi
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the owner's server, `docker compose run --rm --no-deps walg wal-g backup-list` fails with `ERROR: user: unknown userid 70`. The `walg` service runs as `user: "70:70"` (the postgres uid of the Alpine production image), but the Debian image has no passwd entry for uid 70, and WAL-G looks its user up. Add a passwd and group entry for uid/gid 70 to the sidecar image, with a test.

## 2. Context

- `deploy/lightsail/docker-compose.yml` line 74: `user: "70:70"` on the `walg` service. Do not change it: the spool volume and the data mount are owned by uid 70.
- `deploy/lightsail/walg/Dockerfile` ends with these two lines (anchors, must match verbatim):

```
COPY walg-ship.sh /usr/local/bin/walg-ship.sh
RUN chmod 0755 /usr/local/bin/walg-ship.sh
```

- The Debian `postgres` user is uid 999; uid 70 is free in Debian bookworm.
- The existing test `test_walg_dockerfile_pins_debian_postgres_and_verifies_checksum` in `App/tests/test_pg_backup_scripts.py` (line 196) reads the file with `(WALG_DIR / "Dockerfile").read_text()` and ends with this line (anchor):

```
    assert re.search(r"^ARG WALG_ASSET=wal-g-pg-(20|22)\.04-amd64\.tar\.gz$", text, re.M)
```

- Docker is not available to you: you cannot build the image. The owner rebuilds and tests on the server.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/walg/Dockerfile | edit | add one RUN line at the end |
| App/tests/test_pg_backup_scripts.py | edit | add one test after the Dockerfile test |
| docs/tasks/1030-walg-uid70-passwd-entry.md and 1030-report.md | edit/create | status and report |

No other file may change.

## 4. Steps

1. In `deploy/lightsail/walg/Dockerfile`, directly after the line `RUN chmod 0755 /usr/local/bin/walg-ship.sh`, add this line (one line, a blank line between is not needed):

```
RUN groupadd -g 70 walg && useradd -u 70 -g 70 -M -d /tmp -s /usr/sbin/nologin walg
```

Check: `tail -3 deploy/lightsail/walg/Dockerfile | cut -c1-100 | tail -5` shows the three last lines, ending with the `groupadd` line.

2. In `App/tests/test_pg_backup_scripts.py`, directly after the line `    assert re.search(r"^ARG WALG_ASSET=wal-g-pg-(20|22)\.04-amd64\.tar\.gz$", text, re.M)` and its following two blank lines (before `def test_postgres_keeps_its_image_and_no_network_and_archives_to_the_spool():`), insert:

```python
def test_walg_dockerfile_has_a_passwd_entry_for_uid_70():
    # compose runs the walg service as 70:70; wal-g fails with "unknown userid 70" without it
    text = (WALG_DIR / "Dockerfile").read_text()
    assert re.search(r"^RUN groupadd -g 70 \w+ && useradd -u 70 -g 70 ", text, re.M)
    assert compose_services()["walg"]["user"] == "70:70"


```

Keep exactly two blank lines before the next `def`. Check: `grep -n 'passwd_entry_for_uid_70' App/tests/test_pg_backup_scripts.py | tail -3` prints one line.

3. Run: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 skipped. If `App/.venv` is missing, create it from the repo files (`python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`) and rerun.
4. Run `python3 scripts/context_lint.py 2>&1 | tail -5`. Expected: ends with `context lint: OK`.
5. Write `docs/tasks/1030-report.md`, set this brief to `Status: review`, commit, and push the branch (`git push -u origin claude/eloquent-mendel-vd8mfi`). Do not open a PR (the orchestrator does that).

## 5. Do not touch

`docker-compose.yml`, `walg-ship.sh`, any script, any other test, any doc other than this brief and its report.

## 6. Commands

Written in section 4. Every command ends with `| tail`.

## 7. Acceptance

- [ ] `grep -c 'useradd -u 70' deploy/lightsail/walg/Dockerfile | tail -3` prints `1`.
- [ ] `test_pg_backup_scripts.py` passes with 0 skipped.
- [ ] `python3 scripts/context_lint.py 2>&1 | tail -5` ends with `context lint: OK`.
- [ ] `git status --short | head -3` is empty after the push.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor is not found verbatim, a test fails twice, you reach 25 tool calls, a new dependency seems needed, a file outside section 3 needs a change, or you need secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1030-report.md` (600 tokens at most): files changed, each command with its last 5 output lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

Read the diff of `deploy/lightsail/walg/Dockerfile` only.

## Owner steps

After the PR is merged: on the server run `cd /opt/ubyhost && git fetch origin main && git reset --hard origin/main && cd deploy/lightsail && docker compose build walg 2>&1 | tail -5`, then `docker compose run --rm --no-deps walg wal-g backup-list 2>&1 | tail -5`. Expected: no `unknown userid` error.
