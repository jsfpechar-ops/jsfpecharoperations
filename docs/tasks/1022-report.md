# 1022 report (executor)

Status: done after 1022-fix-1 (asset-name test corrected)

## 1. Files changed (git diff --cached --stat)

- deploy/lightsail/walg/Dockerfile (new, 21 lines)
- deploy/lightsail/walg/walg-ship.sh (new, 39 lines)
- deploy/lightsail/docker-compose.yml (61 lines changed: postgres archive flags and spool volume, walg service, walspool volume)
- App/tests/test_pg_backup_scripts.py (118 lines appended, `import re` added)

Not changed yet: docs/context/decisions.md (step 7).

## 2. Commands and last 5 lines

- Step 1 `grep -c '^[A-Z_0-9]*=PENDING' docs/tasks/1022-walg-continuous-archiving.md`: `0`. PASS.
- Step 2 anchor grep: 5 hits (command, pgdata volume, `ubyhost:`, `name: ubyhost-pgsock`, image). PASS.
- Step 3 Dockerfile grep: `2`. PASS.
- Step 4 `sh -n` on walg-ship.sh: `ok`. PASS.
- Step 5 compose edits and YAML check: volumes list includes `ubyhost-walspool`; `['walg'] postgres:16-alpine@sha256:0c`. PASS.
- Step 6 pytest (`tests/test_pg_backup_scripts.py tests/test_pg_cutover_script.py tests/test_wp32_container_sizing.py -x`): 13 passed, 1 failed:
  `test_walg_dockerfile_pins_debian_postgres_and_verifies_checksum`, assertion on `^ARG WALG_ASSET=wal-g-pg-ubuntu-(20|22)\.04-amd64\.tar\.gz$`. FAIL (see Questions).
- Step 8 `python3 scripts/context_lint.py`: `context lint: OK` (warnings are pre-existing). PASS.
- Step 8 `shellcheck`: not installed, not attempted.

## 3. Section 7 acceptance

- [x] postgres image pin and `network_mode: none` unchanged (checked by grep and test)
- [ ] Dockerfile FROM/checksum: FROM and sha256sum pass; the asset-name assertion fails
- [x] postgres archive command, archive_mode, archive_timeout
- [x] walg service: profile, user 70:70, `.env.walg` required false, read-only data mount, no ports
- [ ] grep for AKIA / LIBSODIUM_KEY= / s3:// not run (the test's forbidden-string check passed)
- [ ] pytest line: fails on one test
- [ ] decision line: not done (step 7 not reached)

## 4. Deviations

Done: steps 1 to 6 (step 6 partly: tests appended, one fails). Left: step 6 fix decision, step 7 (decision line), step 8 shellcheck (not installed), section 9 PR text.

## 5. Questions

1. Owner value `WALG_ASSET=wal-g-pg-22.04-amd64.tar.gz` (section 2) does not match the test regex or owner step 6, which both say `wal-g-pg-ubuntu-22.04-amd64.tar.gz`. The file name with `ubuntu-` is the one WAL-G releases use. Please confirm the exact asset name. I did not change the value or the test. If it is the `ubuntu-` name, the value in section 2 and the Dockerfile `ARG WALG_ASSET` must change, and the checksum must be checked against that file (I did not change `WALG_SHA256`).

## 6. Owner steps left

Nothing deployed. Deploy only after 1023 is merged, with the 1023 rollout.

## 7. Fix-1 results (brief 1022-fix-1)

- Owner confirmed the asset is `wal-g-pg-22.04-amd64.tar.gz`. Question 1 above is resolved: the test regex (line 202), the 1022 test excerpt (line 281) and owner step 6 now use the `wal-g-pg-` name. Dockerfile, compose and walg-ship.sh untouched; checksums untouched.
- `grep -c 'pg-ubuntu' docs/tasks/1022-walg-continuous-archiving.md` prints `0`; the test file has no `ubuntu` in its `wal-g-pg-` lines.
- Step 3 `pytest tests/test_pg_backup_scripts.py -q --tb=short -x -rs`: last line `21 passed in 0.44s` (0 skipped).
- Step 5 `python3 scripts/context_lint.py`: last line `context lint: OK` (WARN lines are pre-existing).
- Step 7 decision line appended to `docs/context/decisions.md` (the 1022 approval line).
