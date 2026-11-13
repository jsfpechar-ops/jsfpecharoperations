# 1200: WAL-G refuses to push without its encryption key; server bootstrap hardening

Status: todo
Depends on: none | Base commit: 29f86658 | Branch: task/1200-walg-fail-closed
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Both WAL-G scripts (`walg-ship.sh`, `walg-backup.sh`) refuse to push anything to S3 when `WALG_LIBSODIUM_KEY` is empty, so a missing key can never produce unencrypted archives (same fail-closed style as `backup.sh` for `pg_dump`). `setup-server.sh` also installs unattended-upgrades and writes an sshd drop-in that turns off password login and root login on a fresh server.

## 2. Context

Rules: public repo, never print or commit a secret value (name the variable only); no new dependency (unattended-upgrades is an Ubuntu package installed by apt on a fresh server, not a project dependency); SQL not involved.

How the key reaches the scripts (verified):

- `deploy/lightsail/docker-compose.yml` lines 75-77: the `walg` service reads `.env.walg` through `env_file`. So `WALG_LIBSODIUM_KEY` exists **inside the walg container**, which runs `walg-ship.sh`. The check in `walg-ship.sh` therefore tests the plain environment variable.
- `deploy/lightsail/scripts/walg-backup.sh` runs on the **host** and sources only `.env` (lines 11-16), never `.env.walg`. It runs `wal-g` via `docker compose exec -T walg`, so the key must be tested **inside the container**: `docker compose exec -T walg sh -c '[ -n "${WALG_LIBSODIUM_KEY:-}" ]'`. Testing the host variable would be wrong.

Excerpt 1, `deploy/lightsail/walg/walg-ship.sh` lines 11-15:

```sh
ship_once() {
  if [ -z "${WALG_S3_PREFIX:-}" ]; then
    echo "walg-ship: WALG_S3_PREFIX is not set (is .env.walg missing?); shipping nothing" >&2
    return 1
  fi
```

Excerpt 2, `deploy/lightsail/scripts/walg-backup.sh` lines 17-19:

```bash

docker compose exec -T walg wal-g backup-push /var/lib/postgresql/data
docker compose exec -T walg wal-g delete retain FULL 7 --confirm
```

Excerpt 3, `deploy/lightsail/scripts/setup-server.sh` lines 34-42:

```bash
echo "==> Configuring firewall (SSH, HTTP, HTTPS)"
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi

INSTALL_DIR="${UBYHOST_INSTALL_DIR:-/opt/ubyhost}"
```

Tests (verified): `App/tests/test_pg_backup_scripts.py`
- `run_ship` (about lines 593-613) builds the env for `walg-ship.sh` with a `wal-g` stub. It passes `WALG_S3_PREFIX` but no key, so after step 1 the existing ship tests would fail until the key is added to that env.
- `make_check_tree` / `run_walg` (about lines 646-676) run `walg-backup.sh` with a `docker` stub, `CHECK_DOCKER_STUB`, whose `case` ends with `exit 0` for unknown commands, so the new in-container key check passes by default there.
- No test covers `setup-server.sh`; `bash -n` and shellcheck are its checks.

Consequence to state in the PR (the owner must understand it): when the key is missing, `walg-ship.sh` ships nothing and logs one error every 15 seconds. The postgres container's `archive_command` still copies finished WAL into the spool volume, so WAL piles up **in the spool** (not in Postgres itself) until the key is restored. `walg-check.sh` (cron every 10 minutes) already alerts when a spool file is older than 30 minutes or the spool is large. This is the intended fail-closed behaviour: no unencrypted data leaves the server, and the alarm fires.

`setup-server.sh` only runs on a **fresh** server. This brief does not change the live server.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/walg/walg-ship.sh | edit | key check after the prefix check in `ship_once` |
| deploy/lightsail/scripts/walg-backup.sh | edit | in-container key check before `backup-push` |
| deploy/lightsail/scripts/setup-server.sh | edit | unattended-upgrades and sshd drop-in |
| App/tests/test_pg_backup_scripts.py | edit | key in `run_ship` env; 2 new tests; stub case for the backup check |
| docs/OPERATIONS.md | edit | one sentence at the end of the "Encryption and key custody" bullet (about line 653) |

No other file may change.

## 4. Steps

1. **walg-ship.sh.** Anchor: `grep -nF 'shipping nothing' deploy/lightsail/walg/walg-ship.sh`. Not found: STOP. Directly after the closing `fi` of that block (line 15), insert (two-space indent, POSIX sh, never print the value):

   ```sh
     if [ -z "${WALG_LIBSODIUM_KEY:-}" ]; then
       echo "walg-ship: WALG_LIBSODIUM_KEY is not set (is .env.walg missing the key?); refusing to ship unencrypted WAL" >&2
       return 1
     fi
   ```

   Also change line 6's comment end only if needed: no. Run `sh -n deploy/lightsail/walg/walg-ship.sh 2>&1 | tail -30`. Commit `1200 step 1`.

2. **walg-backup.sh.** Anchor: `grep -nF 'backup-push /var/lib/postgresql/data' deploy/lightsail/scripts/walg-backup.sh`. Not found: STOP. Insert directly above that line (line 18, after the blank line 17):

   ```bash
   # The key lives in .env.walg inside the walg container, not in this shell: test it there.
   if ! docker compose exec -T walg sh -c '[ -n "${WALG_LIBSODIUM_KEY:-}" ]'; then
     echo "Refusing to push an unencrypted base backup: WALG_LIBSODIUM_KEY is empty in the walg container (check .env.walg)." >&2
     exit 1
   fi

   ```

   (Single quotes are deliberate: the variable must expand inside the container.) Run `bash -n deploy/lightsail/scripts/walg-backup.sh 2>&1 | tail -30`. Commit `1200 step 2`.

3. **setup-server.sh.** Anchor: `grep -nF 'INSTALL_DIR="${UBYHOST_INSTALL_DIR' deploy/lightsail/scripts/setup-server.sh`. Not found: STOP. Insert this block directly above that line (after the firewall `fi` and its blank line):

   ```bash
   echo "==> Enabling automatic security updates"
   apt-get install -y unattended-upgrades
   systemctl enable --now unattended-upgrades

   echo "==> Hardening SSH (key login only, no root login)"
   SSHD_DROPIN=/etc/ssh/sshd_config.d/10-ubyhost-hardening.conf
   mkdir -p /etc/ssh/sshd_config.d
   printf 'PasswordAuthentication no\nPermitRootLogin no\n' > "${SSHD_DROPIN}.new"
   if cmp -s "${SSHD_DROPIN}.new" "${SSHD_DROPIN}" 2>/dev/null; then
     rm -f "${SSHD_DROPIN}.new"
   else
     mv "${SSHD_DROPIN}.new" "${SSHD_DROPIN}"
     if sshd -t; then
       systemctl reload ssh || systemctl reload sshd
     else
       rm -f "${SSHD_DROPIN}"
       echo "sshd -t rejected the hardening drop-in; removed it, SSH left unchanged." >&2
       exit 1
     fi
   fi

   ```

   Idempotent: a second run finds identical content and does nothing. Run `bash -n deploy/lightsail/scripts/setup-server.sh 2>&1 | tail -30`. Commit `1200 step 3`.

4. **Tests.** In `App/tests/test_pg_backup_scripts.py`:
   a. In `run_ship`, add `"WALG_LIBSODIUM_KEY": "test-key-not-real",` to the `env` dict next to `"WALG_S3_PREFIX": prefix}` (change the closing `}` accordingly), and add a parameter `key="test-key-not-real"` to the signature `def run_ship(tmp_path, push_ok, prefix="s3://test-bucket/postgres-wal", key="test-key-not-real"):` using `"WALG_LIBSODIUM_KEY": key`.
   b. After `test_walg_ship_refuses_without_a_destination`, add:

   ```python
   def test_walg_ship_refuses_without_the_encryption_key(tmp_path):
       result, spool, pushed = run_ship(tmp_path, True, key="")
       assert result.returncode == 1
       assert pushed == []  # nothing uploaded unencrypted
       assert "WALG_LIBSODIUM_KEY" in result.stderr
       assert "test-key-not-real" not in result.stderr
       assert (spool / "000000010000000000000001").exists()
   ```

   c. In `CHECK_DOCKER_STUB`, add this case line before `*"backup-push"*)`:
   `  *LIBSODIUM_KEY*) [ "${KEY_MISSING:-0}" = 1 ] && exit 1 ;;`
   d. After `test_walg_backup_failure_deletes_nothing_and_does_not_ping`, add:

   ```python
   def test_walg_backup_refuses_without_the_encryption_key(tmp_path):
       result, recorded = run_walg("walg-backup.sh", tmp_path, {"KEY_MISSING": "1"})
       assert result.returncode != 0
       assert "WALG_LIBSODIUM_KEY" in result.stderr
       assert "backup-push" not in recorded
       assert "delete retain" not in recorded
       assert "ping.invalid" not in recorded
   ```

   Run the §6 test command. Commit `1200 step 4`.

5. **Doc.** Anchor: `grep -nF 'Encryption and key custody' docs/OPERATIONS.md`. Append to the end of that single bullet (after "only the pg_dump backups remain.") this sentence: ` Without the key both WAL-G scripts refuse to push: \`walg-ship.sh\` ships nothing (finished WAL waits in the spool and \`walg-check.sh\` alerts) and \`walg-backup.sh\` exits 1 before the base backup.` Run `python3 scripts/context_lint.py 2>&1 | tail -30`. Commit `1200 step 5`.

## 5. Do not touch

`backup.sh`, `walg-check.sh`, `docker-compose.yml`, `.env.walg*`, any other test or doc, the live server. No secret value anywhere (the test key above is a fake literal). No new dependency. Hard rule 8: never push to `main`, never merge.

## 6. Commands

```
sh -n deploy/lightsail/walg/walg-ship.sh 2>&1 | tail -30
bash -n deploy/lightsail/scripts/walg-backup.sh 2>&1 | tail -30
bash -n deploy/lightsail/scripts/setup-server.sh 2>&1 | tail -30
shellcheck -S error deploy/lightsail/scripts/*.sh deploy/lightsail/walg/walg-ship.sh 2>&1 | tail -30   # skip if not installed (command -v shellcheck)
cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x -k "walg" 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: no output from the `-n` and shellcheck runs; pytest all passed (the walg tests including the two new ones); lint passes.

## 7. Acceptance

- [ ] `grep -n 'WALG_LIBSODIUM_KEY' deploy/lightsail/walg/walg-ship.sh deploy/lightsail/scripts/walg-backup.sh | tail -30` shows a check in each; no line prints the value.
- [ ] `grep -n 'PasswordAuthentication no\|PermitRootLogin no\|sshd -t\|unattended-upgrades' deploy/lightsail/scripts/setup-server.sh | tail -30` shows all four.
- [ ] The walg tests pass, including the two new refusal tests.
- [ ] `git diff --stat` lists only the five files in §3.
- [ ] PR opened as a **draft** (merges auto-deploy). PR text includes the spool consequence from §2 and the sentence "setup-server.sh only runs on a fresh server; the live server is not changed."

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1200-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `walg-backup.sh`: the single-quoted in-container check (must not expand on the host).
- `setup-server.sh`: the sshd block. Order must be write, `sshd -t`, then reload; a bad file is removed. Lockout risk is only on a fresh server where the owner has not yet added an SSH key (Lightsail instances come with a key pair, so normally fine).
- The test stub change (`CHECK_DOCKER_STUB`) must not alter other walg tests.

## Owner steps

1. Open the draft PR on GitHub and read the description (the spool consequence is in it).
2. Nothing on the live server changes. Optional check that the key is present on the server: `cd /opt/ubyhost/deploy/lightsail && docker compose exec -T walg sh -c 'test -n "$WALG_LIBSODIUM_KEY" && echo key-present'`. It prints `key-present` and never shows the key.
3. Mark the PR ready only when you want the new scripts deployed; then run `scripts/merge-pr-on-green.sh` as usual.
