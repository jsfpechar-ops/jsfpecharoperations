# 1202 report

Status: review

## 1. Files changed (`git diff --stat c729b7bf..HEAD`)

```
 .github/dependabot.yml              |  3 +++
 .github/workflows/ci.yml            |  2 +-
 deploy/lightsail/docker-compose.yml | 49 ++++++++++++++++++++++++++++++++++++-
 docs/ENVIRONMENT.md                 |  2 +-
 4 files changed, 53 insertions(+), 3 deletions(-)
```

Commits on exec-1202: `630b0a63` (step 1), `d61f541c` (step 2), `9d960c82` (step 3), `96318a84` (step 4).

## 2. Commands (last 5 lines)

1. Compose check (scratch dir): exit 0. `UBYHOST_MAIL_BACKEND: ses` and `POSTHOG_HOST: ""` present; `UBYHOST_AWS` count 0; `ACME|TURNSTILE|GRAFANA` count 0; `env_file` count 0 in the `ubyhost-go` block; 48 environment keys. PASS
2. YAML parse: `ok`. PASS
3. Dependabot: `[('pip', '/App'), ('github-actions', '/'), ('docker', '/'), ('docker', '/go'), ('gomod', '/go')]`. PASS
4. Actionlint: `actionlint not installed`. NOT RUN
5. `pytest tests/test_wp32_container_sizing.py tests/test_pg_backup_scripts.py -q -rs -x`: `92 passed in 2.67s`, no skips. PASS
6. `python3 scripts/context_lint.py`: `context lint: OK` (only pre-existing WARN lines). PASS
7. `git diff --stat`: the four files in §3 only. PASS

## 3. §7 acceptance

- [x] `ubyhost-go` has no `env_file`; `ubyhost` (line 102), `worker` (line 154) and the walg service (line 75) keep theirs.
- [x] `ubyhost-go` `environment:` has 48 keys (5 original + 43).
- [x] Command 1 shows pass-through works; AWS key absent.
- [x] `gomod` for `/go` present; YAML parses.
- [x] ci.yml audits `requirements.lock` with `--require-hashes`.
- [x] Commands 2, 5, 6 pass; diff lists only the four files.
- [x] One doc sentence added to the ENVIRONMENT.md row.

## 4. Deviations

- Base commit: treated as satisfied, per the session override.
- Line numbers shifted by task 1201: `env_file: .env` of `ubyhost-go` was at line 203. Located by anchor, as instructed. The 1201 lines (`cap_drop`, `security_opt`) are untouched.
- Step 1 also added the brief's comment block above `environment:`, as the brief's exact text includes it.
- No push, no PR (session override).

## 5. Questions

None.

## 6. Owner steps left

- Push `exec-1202` and open a **draft** PR (the orchestrator integrates it). Rollback and post-deploy checks are in the brief.
- Install actionlint or let CI check `ci.yml` (`--require-hashes` with `requirements.lock` must pass in CI; if not, drop only `--require-hashes`).
