# 0363 report

Status: review

## Files changed

- `.github/workflows/uptime.yml` (new, step 1)
- `.github/workflows/restore-drill.yml` (new, step 2)
- `scripts/migration_guard.py` (new, step 3)
- `.github/workflows/ci.yml` (step 4: 5 lines added after the context lint step)
- `deploy/lightsail/scripts/deploy.sh` (step 5: 3 lines changed)
- `docs/tasks/0363-report.md` (new)

`git diff --stat 73fc1e7 HEAD` also lists the brief file `docs/tasks/0363-launch-monitoring.md`, which was already committed before this session.

## Commands

(a) YAML parse of uptime, restore-drill, ci: `ok`
(b) `python3 scripts/migration_guard.py origin/main`: `migration guard: OK`
(c) `bash -n` plus `shellcheck -S error deploy.sh`: `bash -n` ok, shellcheck printed nothing (used /tmp/zz/bin/shellcheck)
(d) `python3 scripts/context_lint.py`: `context lint: OK`
actionlint: see Deviations.

## Checklist

- [x] §6 (a) to (d) as expected
- [x] `git diff --stat` shows only the §3 files

## Deviations

- actionlint exits 1. Two findings: the known SC2087 on deploy-lightsail.yml (ignored, per brief), and a new one: `.github/workflows/uptime.yml:26` shellcheck SC2015 (info) on the last line of the probe script, `[ -z "$problems" ] && echo "All good." || { ...; exit 1; }`. Behaviour is correct; it is style only. I did not change it because the brief gives exact text. Fix if CI runs actionlint: replace with an `if [ -z "$problems" ]; then echo "All good."; else echo "$problems"; exit 1; fi`.
- Done: steps 1 to 5. Left: none.

## Questions

- `ci.yml` migration guard uses `${{ github.base_ref }}` inside `run:`. Brief text kept as given. Reviewer may prefer passing it through `env:`.
- The executor brief says to open one PR. Not done, per your instruction (no push, no PR).

## Owner steps left

1. Merge when CI is green (after the orchestrator decides on the SC2015 info).
2. Actions, "Uptime", "Run workflow".
3. Actions, "Restore drill", "Run workflow"; approve the production environment if asked.
4. Watch the repo, Custom, tick Issues, for outage e-mails.

## Orchestrator review

Merged 0362 in (this PR stacks on it). Fixed two review findings: the uptime probe ends with if/else instead of `A && B || C` (shellcheck SC2015), and the migration guard reads `github.base_ref` through `env:` (zizmor template-injection). actionlint and zizmor (high) clean.
