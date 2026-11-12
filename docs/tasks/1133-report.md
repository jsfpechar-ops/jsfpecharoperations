# 1133 report

Status: review

## Files changed

- `docs/DISASTER_RECOVERY.md` (new, 5742 bytes, commit 2a5d551d)
- `docs/tasks/1133-report.md` (new, this file)

## Commands

- `wc -c docs/DISASTER_RECOVERY.md` gave 5742 (limit 10000).
- `python3 scripts/context_lint.py 2>&1 | tail -15`, last lines: `2 commit(s) touched App/ after the last status.md update...`, `next free: task 1134 | migration 0046`, `context lint: OK`. No ERROR lines.
- `test -f docs/DISASTER_RECOVERY.md && echo ok | tail -30` printed `ok`.
- `git status --short | tail -30` printed nothing (clean).

## Section 7 acceptance

- [x] Runbook has all 8 sections; every command is in its own block. (Short inline commands in numbered steps are code spans, not fenced blocks; see Deviations.)
- [x] No AWS login is needed in any rebuild step.
- [x] The two-servers guard appears before the rebuild steps.
- [x] Lint shows no ERROR for the two files.
- [x] Two commits on the branch, nothing pushed. (Runbook commit 2a5d551d; report commit follows.)

## Deviations

- Section 2 facts were confirmed by grep. The repo-root `scripts/` folder does not hold `deploy.sh`, `pg-restore.sh` or `status.sh`. They live in `deploy/lightsail/scripts/`, so the runbook runs commands from `/opt/ubyhost/deploy/lightsail`, as `docs/LIGHTSAIL.md` does.
- Commit message for step 2 used the brief's own text, not the `NNNN step k` pattern.
- Added step 13 (delete the age identity file from the server after restore). This follows the "never on the server" key-custody rule in `docs/OPERATIONS.md`.
- Some short commands in numbered steps (`docker compose stop`, `./scripts/deploy.sh`, `crontab -e`) are inline code, not fenced blocks.
- Commit step 5 for the report uses `docs: 1133 report`.

## Questions

- The brief does not name the exact stay or Doručenka URL paths, so the runbook asks for a browser check rather than a fixed curl path.
- `curl --resolve` may fail TLS against Cloudflare origin certificates. The runbook falls back to a browser hosts-file check and does not use `-k`. Please confirm this is the intended check.

## Owner steps left

- Owner or lawyer: add the new provider to the `/subprocessors` register and `docs/privacy/ROPA.md` (runbook section "After the move").

## Files that should link to the runbook (orchestrator adds the links)

- `docs/LIGHTSAIL.md` (rebuild section)
- `docs/OPERATIONS.md` (backup section)
- `docs/context/status.md`
- `AGENTS.md` routing "Deploy, server, backups" row
