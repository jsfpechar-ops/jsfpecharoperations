# 1009: WAL-G continuous archiving, sidecar image, compose, shipper, tests, decision

Status: review
Depends on: 1007, 1008 (run after both) | Base commit: 47640cf | Branch: task/1009-walg-archiving
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Split: this brief is the sidecar image, compose, shipper script, tests and decision. Brief 1010 (monitor, base-backup script, runbook, owner rollout and drills) depends on it. **Do not deploy 1009 alone**: the owner deploys after 1010 is merged, with the rollout in 1010. Merging 1009 alone changes nothing in production: archiving stays off until the owner sets `UBYHOST_PG_ARCHIVE=on` (1010 rollout).

Reviewer note (2026-11-07): redesigned from the first draft. The production postgres service keeps its pinned Alpine image unchanged (no base-image switch, no collation risk, rollback is two `.env` lines). Only the new `walg` sidecar uses a Debian image, because WAL-G release binaries are built for glibc, not musl.

## 1. Objective

Give the production Postgres continuous WAL archiving to S3 (eu-central-1) through WAL-G, so the owner can restore to any minute of the last 7 days (data loss at most about 5 minutes). The daily age-encrypted `pg_dump` backups stay unchanged and stay the primary backup.

## 2. Context

Rules: AGENTS.md rule 4 (new dependency needs an owner decision line), rule 2 (new outbound request needs its reason in the PR), rule 3 (no secrets, bucket name or account id in the repo), rule 5.

**Owner decision (2026-11-07, in chat):** the owner approved WAL-G on the condition that the cost stays small, unlike Litestream, whose S3 read-back traffic was high. WAL-G only writes (PUT) and lists in normal running. `archive_timeout=300` caps PUT requests at about 288 a day, about USD 0.05 a month.

**Design, and why.**

- The postgres service has `network_mode: none` and its image stays exactly `postgres:16-alpine@sha256:0cefaabd...` (the compose comment's trust boundary; `App/tests/test_pg_cutover_script.py` asserts both). Postgres never runs wal-g.
- `archive_command` copies each finished WAL file into a local spool volume `ubyhost-walspool` **durably**: copy to `<name>.tmp`, `sync` the file, rename to the final name, `sync` the directory, and only then exit 0. If the final name already exists with identical bytes (Postgres retries after a crash) it exits 0; with different bytes it exits non-zero, so Postgres keeps the WAL in `pg_wal` and the 1010 monitor alerts. Nothing is ever overwritten silently.
- Archiving is switched by `UBYHOST_PG_ARCHIVE` from `.env` (default `off`), so staging and local stacks that share this compose file are unchanged and do not fill a spool.
- A `walg` sidecar (compose profile `walg`, image `ubyhost-walg:local` built from `deploy/lightsail/walg/`, Debian `postgres:16.x-bookworm` + checksum-verified WAL-G) has network on the project's default network, no port. `walg-ship.sh` runs `wal-g wal-push` per spool file, oldest first, and deletes a spool file **only after wal-push exited 0** (upload confirmed). It runs as uid/gid 70, the postgres uid of the Alpine image, so it can read the spool and the read-only data directory.
- The daily `wal-g backup-push` (1010) runs in the sidecar. It needs (a) a Postgres connection: through the shared socket volume `ubyhost-pgsock` (`PGHOST=/var/run/postgresql`, user `ubyhost`, trust auth on the socket, exactly how the app connects; no password exists or is added), and (b) the data files: through `ubyhost-pgdata` mounted read-only. `pg_backup_stop` waits until the WAL the backup needs is archived (copied to the spool); the shipper then uploads it.
- Restores run the Debian image's Postgres in a scratch container with network and `restore_command = 'wal-g wal-fetch %f %p'` (1010 runbook); a real restore is brought back into production as a `pg_dump` through the existing `pg-restore.sh`, so the production data directory never meets a glibc Postgres.

**Anchor 1, `deploy/lightsail/docker-compose.yml`, the postgres command line (unchanged by 1007 and 1008; verified 2026-11-07):**

```
    command: ["postgres", "-c", "listen_addresses=", "-c", "shared_buffers=256MB", "-c", "max_connections=50", "-c", "log_min_duration_statement=1000"]
```

**Anchor 2, same file, the postgres volumes (the only place these two lines follow each other):**

```
      - ubyhost-pgdata:/var/lib/postgresql/data
      - ubyhost-pgsock:/var/run/postgresql
```

**Anchor 3, same file, the start of the app service:**

```
  ubyhost:
    build:
      context: ../..
```

**Anchor 4, same file, in the top-level `volumes:` block (NOT the end of the file: `caddy-data`, `caddy-config` and `networks:` follow):**

```
  ubyhost-pgsock:
    name: ubyhost-pgsock
```

**Owner-supplied values (the orchestrator pastes them here before the brief runs). Never invent any of them.**

```
PG_DEBIAN_IMAGE=postgres:16.15-bookworm@sha256:5264710be20f409750ac6dc4e5706dcef929c87e241605463f0f9aefa932a8d9
WALG_VERSION=v3.0.9
WALG_ASSET=wal-g-pg-22.04-amd64.tar.gz
WALG_SHA256=4f03ee4679db7f660bfd1b2b8291ac5df247cd2ec48074b60c112f4897299f24
```

If any value still says `PENDING`, **STOP at step 1** and put the "Owner steps (before this brief runs)" below into your report as `blocked`.

Why pinned checksum and digest: the image holds the backup encryption key and S3 credentials at run time. A build that cannot verify its download must fail.

Retention (`docs/privacy/RETENTION.md`, row "Encrypted backups": 30 days local/off-site): WAL and base backups keep 7 days (`wal-g delete retain FULL 7`), S3 lifecycle deletes after 10 days as a safety net, so both stay inside 30 days. 1010 adds the RETENTION row.

Variables the sidecar reads from `.env.walg` (git-ignored by the existing `.env.*` rule in `.gitignore`; the owner creates it on the server, 1010): `WALG_S3_PREFIX`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `WALG_COMPRESSION_METHOD`, `WALG_LIBSODIUM_KEY`, `WALG_LIBSODIUM_KEY_TRANSFORM`, `WALG_UPLOAD_CONCURRENCY`, `PGHOST`, `PGUSER`, `PGDATABASE`. This brief commits no values.

**Context-rollout upload (orchestrator):** put files flat in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/walg/Dockerfile | create | Debian Postgres 16 image (pinned digest) plus checksum-verified WAL-G |
| deploy/lightsail/walg/walg-ship.sh | create | loop that ships spooled WAL with `wal-g wal-push`, deletes only after success |
| deploy/lightsail/docker-compose.yml | edit | archive flags, spool volume on postgres, `walg` service, volume declaration |
| App/tests/test_pg_backup_scripts.py | edit | append static and stub tests |
| docs/context/decisions.md | edit | append one `[backup]` line |

No other file may change.

## 4. Steps

1. Check the owner values. Command: `grep -c '^[A-Z_0-9]*=PENDING' docs/tasks/1009-walg-continuous-archiving.md | tail -30`. Expected: `0` (the four value lines in section 2 hold real values). Anything else: STOP.

2. Confirm the anchors. Command: `grep -n 'log_min_duration_statement=1000"\]\|ubyhost-pgdata:/var/lib/postgresql/data$\|^  ubyhost:$\|name: ubyhost-pgsock\|image: postgres:16-alpine@sha256:0cefaabd' deploy/lightsail/docker-compose.yml | tail -30`. Expected: five hits (command, pgdata volume, `ubyhost:`, `name: ubyhost-pgsock`, the image line). Any missing: STOP.

3. Create `deploy/lightsail/walg/Dockerfile`, replacing the four `<...>` with the owner values from section 2:

```dockerfile
# 1009: image for the walg sidecar only (compose profile "walg"). The production
# postgres service keeps its pinned Alpine image and never runs wal-g. Debian
# (glibc) because the WAL-G release binaries are built for glibc. The Postgres 16
# binaries here are used only by the restore drill (docs/OPERATIONS.md).
FROM <PG_DEBIAN_IMAGE>
ARG WALG_VERSION=<WALG_VERSION>
ARG WALG_ASSET=<WALG_ASSET>
ARG WALG_SHA256=<WALG_SHA256>
RUN set -eu \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /tmp/walg.tar.gz "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/${WALG_ASSET}" \
 && echo "${WALG_SHA256}  /tmp/walg.tar.gz" | sha256sum -c - \
 && mkdir /tmp/walg \
 && tar -xzf /tmp/walg.tar.gz -C /tmp/walg \
 && install -m 0755 "$(find /tmp/walg -type f | head -1)" /usr/local/bin/wal-g \
 && rm -rf /tmp/walg /tmp/walg.tar.gz \
 && wal-g --version
COPY walg-ship.sh /usr/local/bin/walg-ship.sh
RUN chmod 0755 /usr/local/bin/walg-ship.sh
```

Command: `grep -c 'sha256sum -c\|^FROM postgres:16\.[0-9]*-bookworm@sha256:[0-9a-f]\{64\}$' deploy/lightsail/walg/Dockerfile | tail -30`. Expected: `2`.

4. Create `deploy/lightsail/walg/walg-ship.sh` with this content (`WALG_SHIP_ONCE=1` is for the tests):

```sh
#!/bin/sh
# 1009: ship finished WAL files from the spool to S3 with wal-g, oldest first.
# The postgres container (no network) copies each finished file into the spool
# (archive_command); this container has the network. A spool file is deleted
# only after `wal-g wal-push` exited 0 (upload confirmed). A failure keeps it and
# retries; 1010's walg-check.sh alerts when a file stays too long.
set -u
SPOOL="${WALG_SPOOL:-/walspool}"
INTERVAL="${WALG_SHIP_INTERVAL:-15}"

ship_once() {
  if [ -z "${WALG_S3_PREFIX:-}" ]; then
    echo "walg-ship: WALG_S3_PREFIX is not set (is .env.walg missing?); shipping nothing" >&2
    return 1
  fi
  # Only finished WAL names (segments, timeline history, backup labels): skips
  # *.tmp copies in progress and anything else that may appear in the spool.
  for f in $(ls -1 "$SPOOL" 2>/dev/null \
      | grep -E '^[0-9A-F]{24}$|^[0-9A-F]{24}\.[0-9A-F]{8}\.backup$|^[0-9A-F]{8}\.history$' \
      | LC_ALL=C sort); do
    [ -f "$SPOOL/$f" ] || continue
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

Command: `chmod +x deploy/lightsail/walg/walg-ship.sh && sh -n deploy/lightsail/walg/walg-ship.sh && echo ok | tail -30`. Expected: `ok`.

5. Edit `deploy/lightsail/docker-compose.yml`, one edit per sub-step. Do not touch the `image:` line or `network_mode: none`.

   a. Replace the anchor 1 line (the whole `    command: [...]` line) with:

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
      # 1009: WAL archiving, on only when .env sets UBYHOST_PG_ARCHIVE=on
      # (production). No network here: archive_command only copies each WAL file
      # durably into the spool (tmp, sync, rename, sync dir; identical re-copy is
      # ok, a different file fails); the walg service ships it to S3.
      # archive_timeout=300: a segment at least every 5 minutes when there is
      # activity (about USD 0.05 a month in PUT requests).
      - -c
      - archive_mode=${UBYHOST_PG_ARCHIVE:-off}
      - -c
      - archive_timeout=300
      - -c
      - 'archive_command=if [ -f /walspool/%f ]; then cmp -s %p /walspool/%f; else cp %p /walspool/%f.tmp && sync /walspool/%f.tmp && mv /walspool/%f.tmp /walspool/%f && sync /walspool; fi'
```

   b. Replace the two anchor 2 lines with these three (the third is new):

```
      - ubyhost-pgdata:/var/lib/postgresql/data
      - ubyhost-pgsock:/var/run/postgresql
      - ubyhost-walspool:/walspool
```

   c. Insert this block directly before the anchor 3 lines (keep one blank line between it and `  ubyhost:`):

```yaml
  # 1009: WAL-G sidecar, started only with COMPOSE_PROFILES containing walg
  # (production). Ships the WAL spool to S3 and runs the daily base backup
  # (1010). Default project network (not web), no port. Reaches Postgres only
  # through the socket volume (trust auth, like the app) and a read-only data
  # mount, as uid 70 = postgres in the Alpine image. Keys come from .env.walg
  # (root-only on the server, never in git); without it the shipper only logs
  # errors and the WAL waits in the spool.
  walg:
    profiles: ["walg"]
    build:
      context: ./walg
    image: ubyhost-walg:local
    restart: unless-stopped
    init: true
    user: "70:70"
    env_file:
      - path: .env.walg
        required: false
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
    mem_limit: 512m
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

```

   d. Replace the two anchor 4 lines with these four:

```
  ubyhost-pgsock:
    name: ubyhost-pgsock
  ubyhost-walspool:
    name: ubyhost-walspool
```

Command: `python3 -c "import yaml;d=yaml.safe_load(open('deploy/lightsail/docker-compose.yml'));print(sorted(d['volumes']));print(d['services']['walg']['profiles'], d['services']['postgres']['image'][:28])" 2>&1 | tail -30`. Expected: the volume list contains `ubyhost-walspool`, then `['walg'] postgres:16-alpine@sha256:0ce`. Do NOT run `docker compose config` (no `.env` here).

6. Append tests to the end of `App/tests/test_pg_backup_scripts.py`. First `grep -n '^import\|^from' App/tests/test_pg_backup_scripts.py | tail -30`; add `import re` after `import os` only if missing. Then append:

```python
COMPOSE = ROOT / "deploy/lightsail/docker-compose.yml"
WALG_DIR = ROOT / "deploy/lightsail/walg"
PINNED_PG = "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab"


def compose_services():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(COMPOSE.read_text())["services"]


def archive_command():
    command = compose_services()["postgres"]["command"]
    return next(p for p in command if p.startswith("archive_command=")).split("=", 1)[1]


def test_walg_dockerfile_pins_debian_postgres_and_verifies_checksum():
    text = (WALG_DIR / "Dockerfile").read_text()
    assert re.search(r"^FROM postgres:16\.\d+-bookworm@sha256:[0-9a-f]{64}$", text, re.M)
    assert "sha256sum -c" in text
    assert re.search(r"^ARG WALG_SHA256=[0-9a-f]{64}$", text, re.M), "never PENDING"
    assert re.search(r"^ARG WALG_VERSION=v\d+\.\d+\.\d+$", text, re.M)
    assert re.search(r"^ARG WALG_ASSET=wal-g-pg-(20|22)\.04-amd64\.tar\.gz$", text, re.M)


def test_postgres_keeps_its_image_and_no_network_and_archives_to_the_spool():
    pg = compose_services()["postgres"]
    assert pg["image"] == PINNED_PG
    assert pg["network_mode"] == "none"
    assert "archive_mode=${UBYHOST_PG_ARCHIVE:-off}" in pg["command"]
    assert "archive_timeout=300" in pg["command"]
    assert "wal-g" not in " ".join(pg["command"])  # the database container never talks to S3
    assert "ubyhost-walspool:/walspool" in pg["volumes"]


def test_archive_command_copies_durably_and_never_overwrites(tmp_path):
    spool = tmp_path / "walspool"
    spool.mkdir()
    wal = tmp_path / "000000010000000000000007"
    wal.write_bytes(b"x" * 4096)
    cmd = archive_command().replace("/walspool", str(spool)).replace("%p", str(wal)).replace("%f", wal.name)

    def run():
        return subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=30)

    first = run()
    assert first.returncode == 0, first.stderr
    assert (spool / wal.name).read_bytes() == wal.read_bytes()
    assert not (spool / f"{wal.name}.tmp").exists()
    assert run().returncode == 0  # Postgres may retry the same file after a crash
    (spool / wal.name).write_bytes(b"different")
    assert run().returncode != 0  # a different file with the same name is an error
    assert (spool / wal.name).read_bytes() == b"different"


def test_walg_sidecar_is_profiled_unprivileged_and_has_no_secrets():
    walg = compose_services()["walg"]
    assert walg["profiles"] == ["walg"]
    assert walg["user"] == "70:70"
    assert walg["env_file"] == [{"path": ".env.walg", "required": False}]
    assert "ubyhost-pgdata:/var/lib/postgresql/data:ro" in walg["volumes"]
    assert "ubyhost-pgsock:/var/run/postgresql" in walg["volumes"]
    for key in ("ports", "expose", "network_mode", "networks", "environment"):
        assert key not in walg
    text = COMPOSE.read_text() + (WALG_DIR / "Dockerfile").read_text()
    for forbidden in ("AWS_SECRET", "AKIA", "LIBSODIUM_KEY=", "s3://"):
        assert forbidden not in text


def test_walg_ship_script_syntax():
    result = subprocess.run(["sh", "-n", str(WALG_DIR / "walg-ship.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def run_ship(tmp_path, push_ok, prefix="s3://test-bucket/postgres-wal"):
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "000000010000000000000002").write_text("w2")
    (spool / "000000010000000000000001").write_text("w1")
    (spool / "000000010000000000000003.tmp").write_text("half")
    (spool / "walg_status").mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "wal-g"
    stub.write_text('#!/bin/sh\necho "$*" >> "$STUB_LOG"\n[ "$PUSH_OK" = 1 ]\n')
    stub.chmod(0o755)
    log = tmp_path / "stub.log"
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(log),
           "PUSH_OK": "1" if push_ok else "0", "WALG_SPOOL": str(spool), "WALG_SHIP_ONCE": "1",
           "WALG_S3_PREFIX": prefix}
    result = subprocess.run(["sh", str(WALG_DIR / "walg-ship.sh")], env=env,
                            capture_output=True, text=True, timeout=30)
    pushed = log.read_text().splitlines() if log.exists() else []
    return result, spool, pushed


@pytest.mark.parametrize("push_ok", [True, False])
def test_walg_ship_deletes_only_after_a_good_push(tmp_path, push_ok):
    result, spool, pushed = run_ship(tmp_path, push_ok)
    assert (spool / "000000010000000000000003.tmp").exists()  # never shipped
    assert (spool / "walg_status").is_dir()  # not a WAL name: ignored
    if push_ok:
        assert result.returncode == 0, result.stderr
        assert [p.rsplit("/", 1)[-1] for p in pushed] == ["000000010000000000000001", "000000010000000000000002"]
        assert sorted(p.name for p in spool.iterdir()) == ["000000010000000000000003.tmp", "walg_status"]
    else:
        assert result.returncode == 1
        assert len(pushed) == 1  # stops at the first failure, oldest first
        assert (spool / "000000010000000000000001").exists() and (spool / "000000010000000000000002").exists()


def test_walg_ship_refuses_without_a_destination(tmp_path):
    result, spool, pushed = run_ship(tmp_path, True, prefix="")
    assert result.returncode == 1
    assert pushed == []
    assert (spool / "000000010000000000000001").exists()
```

Command: `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py tests/test_pg_cutover_script.py tests/test_wp32_container_sizing.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 skipped. If `test_walg_dockerfile_pins_debian_postgres_and_verifies_checksum` fails because a value is not real, STOP: never weaken a test.

7. Append one line at the end of `docs/context/decisions.md`, in the same format as the 1008 line just above it (`- 2026-11-07 | [backup] ... | owner | ...`; check with `tail -3 docs/context/decisions.md | cut -c1-120`):

```
- 2026-11-07 | [backup] WAL-G approved (rule 4): WAL archiving + PITR to S3 | owner | [1009](../tasks/1009-walg-continuous-archiving.md)
```

Command: `tail -1 docs/context/decisions.md | cut -c1-60 | tail -30`. Expected: `- 2026-11-07 | [backup] WAL-G approved (rule 4)`.

8. Lint and shell checks. Commands: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no new error) and `shellcheck -S error deploy/lightsail/walg/walg-ship.sh 2>&1 | tail -30` (expected: no output; if `shellcheck` is not installed, say so in the report, do not install).

## 5. Do not touch

`deploy/lightsail/scripts/*` (1010 owns the new ones; `backup.sh`, `pg-restore.sh`, `deploy.sh`, `preflight.sh` stay as they are), `docs/OPERATIONS.md`, `docs/privacy/RETENTION.md`, `docs/ENVIRONMENT.md`, `docs/LIGHTSAIL.md` (1010), `.env*` files, `.gitignore`, `App/app/`, the other tests. Rules 3 (no secrets, no real bucket name, account id or key), 4 (done by the decision line) and 5 apply. Do not change the postgres `image:` line, `network_mode: none`, `environment:` or the healthcheck. Do not run docker.

## 6. Commands

Only: the pytest line in step 6, `shellcheck` in step 8, `python3 scripts/context_lint.py`. Each ends `| tail -30`. Never the full suite.

## 7. Acceptance

- [ ] `grep -c 'image: postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab' deploy/lightsail/docker-compose.yml` prints `1`, and `network_mode: none` is still in the postgres service.
- [ ] The Dockerfile `FROM` is `postgres:16.N-bookworm@sha256:<64 hex>`, with a 64-hex `WALG_SHA256` and `sha256sum -c`.
- [ ] The postgres command has `archive_mode=${UBYHOST_PG_ARCHIVE:-off}`, `archive_timeout=300` and the spool `archive_command` (tested by `test_archive_command_copies_durably_and_never_overwrites`).
- [ ] The `walg` service has profile `walg`, `user: "70:70"`, `.env.walg` with `required: false`, a read-only data mount, no ports.
- [ ] `grep -rn 'AKIA\|LIBSODIUM_KEY=[0-9a-f]\|s3://' deploy/lightsail/docker-compose.yml deploy/lightsail/walg | tail -30` shows nothing.
- [ ] The pytest line in step 6 passes with 0 skipped; context lint shows no new error.
- [ ] The decision line is the last line of decisions.md.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor (1 to 4) is not found;
- any owner value in section 2 is `PENDING`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency other than the WAL-G binary and the Debian Postgres base image seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1009-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left: "deploy only after 1010 is merged, with the 1010 rollout".

PR text must say, for rule 2: the new outbound requests are the `walg` container writing to the owner's dedicated S3 bucket (eu-central-1), and the build-time downloads of the WAL-G release from github.com and of `ca-certificates`/`curl` from the Debian mirror; reason: point-in-time recovery; data sent: WAL and base backups encrypted on the server with libsodium before upload, nothing readable by AWS.

## Risk list (for the reviewer)

`deploy/lightsail/docker-compose.yml` (production database command: the `archive_command` string, `archive_mode` default `off`; image and `network_mode: none` unchanged), `deploy/lightsail/walg/Dockerfile` (pinned digest, checksum), `deploy/lightsail/walg/walg-ship.sh` (deletes spool files only after a good push; name filter).

## Owner steps (before this brief runs; only while section 2 says PENDING)

In plain words. You need SSH to the server; about 15 minutes.

1. On the server: `cd /opt/ubyhost/deploy/lightsail && docker compose exec -T postgres postgres --version`. It prints something like `postgres (PostgreSQL) 16.10`. Write down the `16.N` number.
2. `docker compose exec -T postgres id -u postgres`. It must print `70`. If not, stop and tell the orchestrator (the sidecar's `user: "70:70"` depends on it).
3. `docker compose version`. It must be `v2.24.0` or newer (the `required: false` setting needs it). Do the same on the staging server. If older, stop and tell the orchestrator.
4. `docker pull postgres:16.N-bookworm` (your number from step 1), then `docker image inspect --format '{{index .RepoDigests 0}}' postgres:16.N-bookworm`. It prints `postgres@sha256:` and 64 characters. Your `PG_DEBIAN_IMAGE` is `postgres:16.N-bookworm@sha256:<those 64 characters>`.
5. In your browser open https://github.com/wal-g/wal-g/releases. Take the newest release that is **not** marked "Pre-release". Its tag (like `v3.0.5`) is `WALG_VERSION`.
6. In that release, click **Assets**. Find the file whose name is `wal-g-pg-22.04-amd64.tar.gz` (if there is no 22.04 one, take `wal-g-pg-20.04-amd64.tar.gz`). Never take a `24.04` file: it needs a newer system library than Debian 12 has. That name is `WALG_ASSET`.
7. On the server: `cd /tmp && curl -fsSLO https://github.com/wal-g/wal-g/releases/download/<TAG>/<ASSET> && sha256sum <ASSET>`. Then compare the 64 characters with the "sha256:" value GitHub shows next to the asset on the release page, or, if the release has a file `<ASSET>.sha256`, with `curl -fsSL https://github.com/wal-g/wal-g/releases/download/<TAG>/<ASSET>.sha256`. They must be identical. That is `WALG_SHA256`. If they differ, stop and tell the orchestrator.
8. Check that the binary runs on the Debian image: `docker run --rm -v /tmp/<ASSET>:/w.tgz:ro postgres:16.N-bookworm sh -c 'mkdir /x && tar -xzf /w.tgz -C /x && "$(find /x -type f | head -1)" --version'`. It must print a WAL-G version. If it says `GLIBC_2.xx not found` or a missing `.so` library, try the 20.04 asset from step 6; if that fails too, stop and tell the orchestrator. Then `rm /tmp/<ASSET>`.
9. Send the four values (`PG_DEBIAN_IMAGE`, `WALG_VERSION`, `WALG_ASSET`, `WALG_SHA256`) to the orchestrator, who pastes them into section 2. None of them is a secret.
