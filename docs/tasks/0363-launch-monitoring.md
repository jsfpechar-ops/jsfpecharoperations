# 0363: Launch monitoring: uptime probe, weekly restore drill, migration guard, failing public smoke

Status: todo
Depends on: 0362 (both edit ci.yml) | Base commit: 73fc1e7 (task/0361 head; 0362 runs in parallel, the orchestrator merges the two) | Branch: task/0363-launch-monitoring
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Nothing watches production between deploys, nobody proves the backups restore, an edited migration would never re-run on production, and a broken public site still shows a green deploy. Add four small guards, all in workflow files and one script, with no app code change.

## 2. Context

- Production: `https://ubyhost.com`, health at `https://ubyhost.com/healthz`.
- SSH pattern to copy (from `.github/workflows/deploy-lightsail.yml`): environment secrets `LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_PRIVATE_KEY`, `LIGHTSAIL_KNOWN_HOSTS`; key written to `~/.ssh/lightsail_deploy.pem` (mode 600), known_hosts to `~/.ssh/known_hosts`, host stripped of spaces and `ubuntu@`, then `ssh -o StrictHostKeyChecking=yes -i ~/.ssh/lightsail_deploy.pem "ubuntu@${LIGHTSAIL_HOST}"`. Server checkout: `/opt/ubyhost`.
- `deploy/lightsail/scripts/restore_test.sh` (run from `deploy/lightsail`) restores the newest Litestream replica into a temp file, checks integrity and row counts, prints only counts, writes nothing. Exit 0 = intact.
- `deploy/lightsail/scripts/deploy.sh` ends with:
  ```bash
    if ! ./scripts/smoke-remote.sh; then
      echo "WARNING: public smoke failed (DNS/TLS/Cloudflare?). Internal healthz is above." >&2
    fi
  ```
- Migrations: `App/app/migrations/NNNN_name.sql`, numbered without gaps. A migration already on main must never be edited, renamed or deleted.
- `ci.yml` job `context` runs `python3 scripts/context_lint.py` with `fetch-depth: 50`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `.github/workflows/uptime.yml` | create | 15-minute probe, opens or comments an issue on failure |
| `.github/workflows/restore-drill.yml` | create | Weekly restore drill on production over SSH |
| `scripts/migration_guard.py` | create | Fail when a PR edits, renames or deletes an existing migration, or skips a number |
| `.github/workflows/ci.yml` | edit | Add the guard step to job `context` |
| `deploy/lightsail/scripts/deploy.sh` | edit | Public smoke failure exits 1 |
| `docs/tasks/0363-report.md` | create | Report |

No other file may change.

## 4. Steps

1. Create `.github/workflows/uptime.yml`:
   ```yaml
   name: Uptime

   # Every 15 minutes: production answers /healthz and the home page, and the
   # TLS certificate has more than 14 days left. A failure opens one issue
   # labelled "outage" (or comments on the open one) so it reaches the owner.
   on:
     schedule:
       - cron: "*/15 * * * *"
     workflow_dispatch:

   permissions:
     contents: read
     issues: write

   concurrency:
     group: uptime
     cancel-in-progress: false

   jobs:
     probe:
       runs-on: ubuntu-latest
       timeout-minutes: 5
       steps:
         - name: Probe production
           id: probe
           run: |
             set -uo pipefail
             problems=""
             for url in https://ubyhost.com/healthz https://ubyhost.com/; do
               code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 --retry 2 --retry-delay 10 "$url" || echo 000)"
               [ "$code" = "200" ] || problems="${problems}${url} answered ${code}. "
             done
             end="$(echo | openssl s_client -servername ubyhost.com -connect ubyhost.com:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)"
             if [ -z "$end" ]; then
               problems="${problems}TLS certificate could not be read. "
             elif [ $(( ($(date -d "$end" +%s) - $(date +%s)) / 86400 )) -lt 14 ]; then
               problems="${problems}TLS certificate expires ${end}. "
             fi
             echo "problems=${problems}" >> "$GITHUB_OUTPUT"
             [ -z "$problems" ] && echo "All good." || { echo "$problems"; exit 1; }

         - name: Open or update the outage issue
           if: failure()
           env:
             GH_TOKEN: ${{ github.token }}
             PROBLEMS: ${{ steps.probe.outputs.problems }}
           run: |
             gh label create outage --repo "$GITHUB_REPOSITORY" --color B60205 2>/dev/null || true
             open="$(gh issue list --repo "$GITHUB_REPOSITORY" --label outage --state open --json number --jq '.[0].number')"
             body="$(date -u '+%Y-%m-%d %H:%M UTC'): ${PROBLEMS:-probe failed} Run: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
             if [ -n "$open" ]; then
               gh issue comment "$open" --repo "$GITHUB_REPOSITORY" --body "$body"
             else
               gh issue create --repo "$GITHUB_REPOSITORY" --label outage --title "Production is down or degraded" --body "$body"
             fi
   ```
   Commit `0363 step 1`.
2. Create `.github/workflows/restore-drill.yml`: `name: Restore drill`; `on: schedule: - cron: "30 3 * * 1"` plus `workflow_dispatch`; `permissions: contents: read`; one job `drill` with `environment: production`, `runs-on: ubuntu-latest`, `timeout-minutes: 15`, one step `Run restore_test.sh on production` whose env holds the three `LIGHTSAIL_*` secrets and whose run block does, with `set -euo pipefail`: the key and known_hosts setup and host cleanup exactly as in §2, then `ssh ... "ubuntu@${LIGHTSAIL_HOST}" 'cd /opt/ubyhost/deploy/lightsail && ./scripts/restore_test.sh'`, then `rm -f ~/.ssh/lightsail_deploy.pem`. Comment at the top: "Weekly proof that the newest backup restores. Read-only: restore_test.sh writes only a temp file and prints only row counts." Commit `0363 step 2`.
3. Create `scripts/migration_guard.py`:
   ```python
   #!/usr/bin/env python3
   """Fail when a change edits, renames or deletes a migration that is on the base branch,
   or adds migrations that do not continue the numbering without gaps.

   Usage: migration_guard.py BASE_REF   (e.g. origin/main)
   """
   from __future__ import annotations

   import re
   import subprocess
   import sys

   DIR = "App/app/migrations/"


   def git(*args: str) -> str:
       return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


   def main() -> int:
       base = sys.argv[1]
       errors = []
       for line in git("diff", "--name-status", f"{base}...HEAD", "--", DIR).splitlines():
           status, *paths = line.split("\t")
           if status[0] != "A":
               errors.append(f"{status} {' '.join(paths)}: a migration on {base} must never change; add a new file")
       numbers = lambda text: sorted(int(m) for m in re.findall(r"(\d{4})_[^/\s]*\.sql", text))
       before = numbers(git("ls-tree", "--name-only", base, DIR))
       after = numbers(git("ls-tree", "--name-only", "HEAD", DIR))
       added = [n for n in after if n not in before]
       expected = list(range((before[-1] if before else 0) + 1, (before[-1] if before else 0) + 1 + len(added)))
       if added != expected:
           errors.append(f"new migrations {added} must be numbered {expected} (no gaps, no reuse)")
       for error in errors:
           print(f"::error title=Migration guard::{error}")
       print("migration guard: OK" if not errors else f"migration guard: {len(errors)} problem(s)")
       return 1 if errors else 0


   if __name__ == "__main__":
       raise SystemExit(main())
   ```
   Commit `0363 step 3`.
4. In `ci.yml` job `context`, after the context lint step, add:
   ```yaml
         - name: Migration guard
           if: github.event_name == 'pull_request'
           run: |
             git fetch --no-tags --depth=50 origin "${{ github.base_ref }}"
             python3 scripts/migration_guard.py "origin/${{ github.base_ref }}"
   ```
   Commit `0363 step 4`.
5. In `deploy/lightsail/scripts/deploy.sh` replace the `WARNING: public smoke failed` line with:
   ```bash
      echo "ERROR: public smoke failed (DNS/TLS/Cloudflare?). Internal healthz passed, the new version is running; check the public site now." >&2
      exit 1
   ```
   Commit `0363 step 5`. Run §6. Write the report.

## 5. Do not touch

`App/`, the deploy, backup and restore logic other than the one line in step 5, job names in `ci.yml`, `scripts/merge-pr-on-green.sh`. Never run anything against a server, never use secrets, never push or merge.

## 6. Commands

(a) `App/.venv/bin/python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('ok')" .github/workflows/uptime.yml .github/workflows/restore-drill.yml .github/workflows/ci.yml 2>&1 | tail -5` prints `ok`.

(b) `git fetch -q origin main && python3 scripts/migration_guard.py origin/main 2>&1 | tail -5` prints `migration guard: OK`.

(c) `bash -n deploy/lightsail/scripts/deploy.sh && shellcheck -S error deploy/lightsail/scripts/deploy.sh 2>&1 | tail -5` prints nothing (if shellcheck is missing, say so).

(d) `python3 scripts/context_lint.py 2>&1 | tail -3` ends with `context lint: OK`.

## 7. Acceptance

- [ ] §6 (a) to (d) as expected.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; you reach 25 tool calls or about 50k tokens; a step is unclear; you would need push, merge, secrets or SSH.

## 9. Report

Write `docs/tasks/0363-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

`.github/workflows/restore-drill.yml`, `deploy/lightsail/scripts/deploy.sh`, `scripts/migration_guard.py`

## Owner steps

1. Merge when CI is green.
2. GitHub, Actions tab, "Uptime", "Run workflow": it should go green within a minute.
3. Actions tab, "Restore drill", "Run workflow". If the production environment asks for approval, approve. It should end with every count matching. If it fails, tell the orchestrator; that means backups need attention before launch.
4. To get outage e-mails: on the repo page, Watch, Custom, tick Issues.
