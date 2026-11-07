# 0997: WAL-G continuous archiving, image, compose, shipper, tests, decision

Status: todo
Depends on: 0996 | Base commit: 47640cf | Branch: task/0997-walg-archiving
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Split: this brief is the image, compose, config, shipper script, tests and decision. Brief 0998 (check script, base-backup script, runbook, owner rollout) depends on it. **Do not deploy 0997 alone**: the owner deploys after 0998 is merged, with the owner steps in 0998.

## 1. Objective

Give the production Postgres continuous WAL archiving to S3 (eu-central-1) through WAL-G, so the owner can restore to any minute of the last 7 days. The daily age-encrypted `pg_dump` backups stay unchanged; this adds point-in-time recovery on top.

## 2. Context

Rules: AGENTS.md rule 4 (new dependency needs an owner decision line), rule 2 (privacy: new outbound request needs its reason in the PR), rule 3 (no secrets in the repo), rule 5.

**Owner decision (2026-11-07, in chat):** the owner approved WAL-G on the condition that the cost stays small, unlike Litestream, whose S3 read-back traffic was high. WAL-G only writes (PUT) and lists; it never reads back during normal running. `archive_timeout=300` caps PUT requests at 288 a day, about 8,600 a month, about USD 0.05.

**Design deviation from the request, and why.** The postgres service has `network_mode: none` (no network at all). `wal-g wal-push` cannot reach S3 from inside it. Opening the network on the database container would break the trust boundary written in the compose comment. So: Postgres copies each finished WAL segment into a local spool volume (`archive_command` is a plain `cp`), and a separate `walg` sidecar container, which has network but no listening port, ships the spool to S3 with `wal-g wal-push`. The sidecar also runs the daily `wal-g backup-push` (0998). Consequence for monitoring: `pg_stat_archiver` only proves the copy into the spool, so 0998's check also watches the spool age.

**Anchor 1, `deploy/lightsail/docker-compose.yml`, the pinned image line (copy it verbatim into the Dockerfile `FROM`):**

```
    image: postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
```

**Anchor 2, the same file, the postgres service lines you replace:**

```
    network_mode: none
    command: ["postgres", "-c", "listen_addresses=", "-c", "shared_buffers=256MB", "-c", "max_connections=50", "-c", "log_min_duration_statement=1000"]
```

**Anchor 3, same file, volumes:**

```
      - ubyhost-pgdata:/var/lib/postgresql/data
      - ubyhost-pgsock:/var/run/postgresql
```

**Anchor 4, same file, end of file:**

```
  ubyhost-pgsock:
    name: ubyhost-pgsock
```

**Owner-supplied WAL-G values (the owner fills this block before the brief runs). Never invent any of them. I could not verify a version or checksum offline.**

```
WALG_VERSION=PENDING
WALG_ASSET=PENDING      (the exact release file name for Alpine/musl on amd64, a .tar.gz)
WALG_SHA256=PENDING     (64 hex characters from the official release page)
```

If any value still says `PENDING`, **STOP at step 1** and hand the owner the commands in the Owner steps section below. The server is x86_64.

Why a pinned checksum: the build downloads a binary that will hold the backup encryption key and the S3 credentials. A build that cannot verify its download must fail.

Retention (confirmed against `docs/privacy/RETENTION.md`, row "Encrypted backups": 30 days local and off-site): WAL archives and base backups keep 7 days (`wal-g delete retain FULL 7`), shorter than the 30-day window, so erased personal data is gone from them in at most 10 days (7 plus the S3 lifecycle safety net). 0998 adds the RETENTION row.

Environment variable names the sidecar reads from `.env.walg` (git-ignored by the existing `.env.*` rule; the owner creates it on the server, 0998): `WALG_S3_PREFIX`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `WALG_COMPRESSION_METHOD`, `WALG_LIBSODIUM_KEY`, `WALG_LIBSODIUM_KEY_TRANSFORM`, `PGHOST`, `PGUSER`, `PGDATABASE`. This brief commits no values.

**Context-rollout upload (orchestrator):** put files flat in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/postgres-walg/Dockerfile | create | pinned postgres image plus checksum-verified WAL-G, spool dir |
| deploy/lightsail/postgres-walg/walg-ship.sh | create | loop that ships spooled WAL files with `wal-g wal-push` |
| deploy/lightsail/docker-compose.yml | edit | build the postgres image, archive settings, spool volume, `walg` service |
| App/tests/test_pg_backup_scripts.py | edit | append static and stub tests for the above |
| docs/context/decisions.md | edit | append one `[backup]` line |

No other file may change.

## 4. Steps

1. Read the "Owner-supplied WAL-G values" block in section 2. If any value is `PENDING`, STOP (section 8) and put the owner commands from "Owner steps" in your report as `blocked`. Command: `grep -n PENDING docs/tasks/0997-walg-continuous-archiving.md | tail -30`. Expected: the three lines show real values; otherwise stop.

2. Confirm anchors 1 to 4 exist. Command: `grep -n 'image: postgres:16-alpine@sha256:0cefaabd\|network_mode: none\|name: ubyhost-pgsock' deploy/lightsail/docker-compose.yml | tail -30`. Expected: three hits. Any missing: STOP.

3. Create `deploy/lightsail/postgres-walg/Dockerfile` with this content, replacing the three `<...>` with the owner values from step 1:

```dockerfile
# 0997: the pinned Postgres image plus WAL-G. Used by the postgres service
# (archive_command copies WAL into /walspool) and the walg sidecar (ships it to S3).
FROM postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
ARG WALG_VERSION=<WALG_VERSION>
ARG WALG_ASSET=<WALG_ASSET>
ARG WALG_SHA256=<WALG_SHA256>
RUN set -eu \
 && apk add --no-cache ca-certificates \
 && wget -q -O /tmp/walg.tgz "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/${WALG_ASSET}" \
 && echo "${WALG_SHA256}  /tmp/walg.tgz" | sha256sum -c - \
 && tar -xzf /tmp/walg.tgz -C /tmp \
 && install -m 0755 "$(find /tmp -maxdepth 2 -type f -name 'wal-g*' ! -name '*.tgz' | head -1)" /usr/local/bin/wal-g \
 && rm -rf /tmp/walg.tgz /tmp/wal-g* \
 && wal-g --version
RUN mkdir -p /walspool && chown postgres:postgres /walspool && chmod 700 /walspool
COPY walg-ship.sh /usr/local/bin/walg-ship.sh
RUN chmod 0755 /usr/local/bin/walg-ship.sh
```

Command: `grep -c 'sha256sum -c' deploy/lightsail/postgres-walg/Dockerfile`. Expected: `1`.

4. Create `deploy/lightsail/postgres-walg/walg-ship.sh` with this content. `WALG_SHIP_ONCE=1` is for the tests.

```sh
#!/bin/sh
# 0997: ship finished WAL files from the spool to S3 with wal-g, oldest first.
# Postgres copies each segment into the spool (archive_command); this container has
# the network. A file is deleted only after wal-push succeeded, so a failure
# keeps it and retries; the spool grows and 0998's walg-check.sh alerts.
set -u
SPOOL="${WALG_SPOOL:-/walspool}"
INTERVAL="${WALG_SHIP_INTERVAL:-15}"

ship_once() {
  for f in $(ls -1 "$SPOOL" 2>/dev/null | grep -Ev '\.tmp$' | sort); do
    if wal-g wal-push "$SPOOL/$f"; then
      rm -f "$SPOOL/$f"
    else
      echo "walg-ship: wal-push failed for $f, will retry" >&2
      return 1
    fi
  done
  return 0
}

if [ "${WALG_SHIP_ONCE:-0}" = 1 ]; then
  ship_once
  exit $?
fi
while true; do
  ship_once || true
  sleep "$INTERVAL"
done
```

Command: `chmod +x deploy/lightsail/postgres-walg/walg-ship.sh && sh -n deploy/lightsail/postgres-walg/walg-ship.sh && echo ok | tail -30`. Expected: `ok`.

5. Edit `deploy/lightsail/docker-compose.yml`, postgres service, one edit each:

   a. Replace the line `    image: postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab` with:

```
    build:
      context: ./postgres-walg
    image: ubyhost-postgres-walg:local
```

   b. Replace the `command:` line (anchor 2) with this one (the `network_mode: none` line above it stays exactly as is):

```
    command:
      - postgres
      - -c
      - listen_addresses=
      - -c
      - shared_buffers=256MB
      - -c
      - max_connections=50
      - -c
      - log_min_duration_statement=1000
      # 0997: WAL archiving. No network here, so archive_command only copies into
      # the spool; the walg service ships it to S3. archive_timeout=300 forces a
      # segment at least every 5 minutes (about USD 0.05 a month in PUT requests).
      - -c
      - archive_mode=on
      - -c
      - archive_timeout=300
      - -c
      - archive_command=test ! -f /walspool/%f && cp %p /walspool/%f.tmp && mv /walspool/%f.tmp /walspool/%f
```

   c. After the line `      - ubyhost-pgsock:/var/run/postgresql` that follows `ubyhost-pgdata:/var/lib/postgresql/data` (first occurrence only), add `      - ubyhost-walspool:/walspool`.

   d. Insert this new service directly before the line `  ubyhost:` (the app service):

```yaml
  # 0997: ships WAL to S3 and runs the daily base backup (0998). Has network, no
  # listening port. Reads the database only through the socket and a read-only
  # data directory. Credentials and the encryption key come from .env.walg
  # (root-only on the server, never in git).
  walg:
    image: ubyhost-postgres-walg:local
    restart: unless-stopped
    user: postgres
    env_file: .env.walg
    command: ["/usr/local/bin/walg-ship.sh"]
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ubyhost-pgdata:/var/lib/postgresql/data:ro
      - ubyhost-pgsock:/var/run/postgresql
      - ubyhost-walspool:/walspool
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    mem_limit: 256m
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

```

   e. At the end of the file (anchor 4), append:

```
  ubyhost-walspool:
    name: ubyhost-walspool
```

Command: `cd deploy/lightsail && grep -n 'walg\|walspool\|archive_' docker-compose.yml | tail -30`. Expected: lines for the build, the `archive_*` flags, three `walspool` volume entries (postgres, walg, top-level) and the `walg:` service. Do NOT run `docker compose config` with a real `.env`; if you check syntax, use `python3 -c "import yaml,sys;yaml.safe_load(open('deploy/lightsail/docker-compose.yml'))" | tail -30` from the repo root. Expected: no output.

6. Append tests to the end of `App/tests/test_pg_backup_scripts.py`. First `grep -n '^import\|^from' App/tests/test_pg_backup_scripts.py | tail -30` (expected: `os`, `shutil`, `subprocess`, `Path`, `pytest` already imported; add `import re` at the top only if missing). Append:

```python
COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"
WALG_DIR = ROOT / "deploy/lightsail/postgres-walg"
PINNED = "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab"


def postgres_block():
    text = COMPOSE.read_text()
    start = text.index("\n  postgres:\n")
    return text[start:text.index("\n  walg:\n")]


def test_walg_dockerfile_uses_pinned_image_and_verifies_checksum():
    text = (WALG_DIR / "Dockerfile").read_text()
    assert f"FROM {PINNED}" in text
    assert "sha256sum -c" in text
    match = re.search(r"ARG WALG_SHA256=([0-9a-f]{64})\n", text)
    assert match, "WALG_SHA256 must be 64 lowercase hex characters, never PENDING"
    assert re.search(r"ARG WALG_VERSION=v\d+\.\d+\.\d+", text)


def test_postgres_service_archives_but_stays_off_the_network():
    block = postgres_block()
    assert "network_mode: none" in block
    for flag in ("archive_mode=on", "archive_timeout=300", "archive_command=test ! -f /walspool/%f"):
        assert flag in block
    assert "wal-g" not in block  # the database container never talks to S3
    assert "ubyhost-walspool:/walspool" in block


def test_walg_sidecar_has_no_secrets_in_compose():
    text = COMPOSE.read_text()
    walg = text[text.index("\n  walg:\n"):text.index("\n  ubyhost:\n")]
    assert "env_file: .env.walg" in walg
    assert "network_mode" not in walg
    assert "ports" not in walg and "expose" not in walg
    assert "ubyhost-pgdata:/var/lib/postgresql/data:ro" in walg
    for forbidden in ("AWS_SECRET", "AKIA", "LIBSODIUM_KEY="):
        assert forbidden not in text


def test_walg_ship_script_syntax():
    result = subprocess.run(["sh", "-n", str(WALG_DIR / "walg-ship.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("push_ok", [True, False])
def test_walg_ship_deletes_only_after_a_good_push(tmp_path, push_ok):
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "000000010000000000000002").write_text("w2")
    (spool / "000000010000000000000001").write_text("w1")
    (spool / "000000010000000000000003.tmp").write_text("half")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "wal-g"
    stub.write_text('#!/bin/sh\necho "$*" >> "$STUB_LOG"\n[ "$PUSH_OK" = 1 ]\n')
    stub.chmod(0o755)
    log = tmp_path / "stub.log"
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "PUSH_OK": "1" if push_ok else "0", "WALG_SPOOL": str(spool), "WALG_SHIP_ONCE": "1"}
    result = subprocess.run(["sh", str(WALG_DIR / "walg-ship.sh")], env=env,
                            capture_output=True, text=True, timeout=30)
    pushed = log.read_text().splitlines()
    assert (spool / "000000010000000000000003.tmp").exists()  # never shipped
    if push_ok:
        assert result.returncode == 0
        assert [p.rsplit("/", 1)[-1] for p in pushed] == ["000000010000000000000001", "000000010000000000000002"]
        assert sorted(p.name for p in spool.iterdir()) == ["000000010000000000000003.tmp"]
    else:
        assert result.returncode == 1
        assert len(pushed) == 1  # stops at the first failure, oldest first
        assert (spool / "000000010000000000000001").exists() and (spool / "000000010000000000000002").exists()
```

Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. If `test_walg_dockerfile_uses_pinned_image_and_verifies_checksum` fails because a value is not real, STOP: do not weaken the test.

7. Append one line to the end of `docs/context/decisions.md` (use the same `| ... |` style as the lines above it):

```
- 2026-11-07 | [backup] WAL-G approved by the owner (new dependency, rule 4): continuous WAL archiving and point-in-time recovery for the production Postgres to S3 eu-central-1, on top of the daily age-encrypted pg_dump, which stays. Condition: small cost, unlike Litestream whose S3 read-back traffic was high; WAL-G only writes and lists, archive_timeout=300 gives about USD 0.05 a month in PUT requests. Postgres keeps network_mode none and spools WAL locally; a walg sidecar ships it. WAL and base backups keep 7 days, inside the 30-day backup window | owner | [0997](../tasks/0997-walg-continuous-archiving.md), 0998
```

8. Lint and shell checks. Commands: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no new error) and `shellcheck -S error deploy/lightsail/postgres-walg/walg-ship.sh 2>&1 | tail -30` (expected: no output; if `shellcheck` is not installed, say so in the report, do not install).

## 5. Do not touch

`deploy/lightsail/scripts/*` (0998 owns them), `backup.sh`, `pg-restore.sh`, `deploy.sh`, `docs/OPERATIONS.md`, `docs/privacy/RETENTION.md` (0998), `.env*` files, `.gitignore`. Rules 3 (no secrets, no real bucket name, no key), 4 (done by the decision line) and 5 apply. Do not remove `network_mode: none`. Do not change the pinned digest. Do not run docker.

## 6. Commands

Only the test-map rows for deploy scripts and compose: the pytest line in step 6, `shellcheck` in step 8, `python3 scripts/context_lint.py`. Each ends `| tail -30`. Never the full suite.

## 7. Acceptance

- [ ] The Dockerfile `FROM` line equals the compose image line from before the change (digest `0cefaabd...5731ab`), and has a 64-hex checksum and `sha256sum -c`.
- [ ] The postgres service still has `network_mode: none`, and has `archive_mode=on`, `archive_timeout=300` and the spool `archive_command`.
- [ ] The `walg` service has `env_file: .env.walg`, a read-only data mount, no ports.
- [ ] `grep -rn 'AKIA\|LIBSODIUM_KEY=' deploy docs/tasks/0997* | tail -30` shows nothing.
- [ ] The pytest line in step 6 passes; context lint shows no new error.
- [ ] The decision line is the last line of decisions.md.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt (anchors 1 to 4) is not found;
- any WALG value in section 2 is `PENDING`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency other than the WAL-G binary seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0997-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left: "deploy only after 0998 is merged".

PR text must say, for rule 2: the new outbound request is the `walg` container writing to the owner's S3 bucket (eu-central-1) and the build-time download of the WAL-G release from github.com; reason: point-in-time recovery; data sent: client-side encrypted WAL, nothing readable by AWS.

## Risk list (for the reviewer)

`deploy/lightsail/docker-compose.yml` (production database command and volumes; `network_mode: none` kept), `deploy/lightsail/postgres-walg/Dockerfile` (pinned digest, checksum), `deploy/lightsail/postgres-walg/walg-ship.sh` (deletes spool files only after a good push).

## Owner steps

Only needed if section 2 still says `PENDING`. In plain words:

1. Open https://github.com/wal-g/wal-g/releases in your browser and pick the newest release that is not marked pre-release. Write down its tag, like `v3.0.x`. Tell the orchestrator: "verified on the release page" is your word, not mine.
2. In that release's file list, find the Alpine (musl) build for Postgres on amd64. If there is no Alpine asset, tell the orchestrator: then the Dockerfile must change to a Debian-based Postgres image, which is a decision for you (new base image, new digest).
3. On the same page, open the checksum file for that asset (a `.sha256` file next to it) and copy the 64-character hash. If the release has no checksum file, run on your laptop: `curl -fsSL -o walg.tgz https://github.com/wal-g/wal-g/releases/download/<TAG>/<ASSET>` then `sha256sum walg.tgz`. Compare it with the hash shown on the release page or in the release notes if there is one.
4. Send the three values (tag, asset file name, hash) to the orchestrator, who pastes them into section 2. Check once that the asset's notes list libsodium encryption support; if not, tell the orchestrator before continuing.
