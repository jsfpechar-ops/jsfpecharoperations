# 1202: Go service gets only the variables it reads; gomod in Dependabot; audit the lock file

Status: todo
Depends on: none | Base commit: 29f86658 | Branch: task/1202-go-least-secrets-and-dependency-scans
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Stop passing the whole `.env` to the `ubyhost-go` container: pass only the variables the Go code reads. Also add Dependabot for the Go module, and make CI audit `requirements.lock` (what the image installs) instead of `requirements.txt`.

## 2. Context

Hard rules that apply: 3 (no secrets in the repo; this brief names variables, never values), 4 (no new dependency: no govulncheck), 8 (never push to `main`; PR stays a draft because green merges auto-deploy).

**Verified facts (orchestrator, base 29f86658).**

- `deploy/lightsail/docker-compose.yml` lines 198-200 (service `ubyhost-go`): `env_file: .env` then an `environment:` block with five keys (`UBYHOST_DATABASE_URL`, `UBYHOST_GO_JOB_KINDS`, `UBYHOST_STRIPE_MODE`, `UBYHOST_STRIPE_WEBHOOK_SECRET`, `UBYHOST_DATA_DIR`).
- The Go module is one binary, `go/cmd/ubyhost-web`, which serves HTTP and runs every Go job kind (`billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi`, `deadlines`). There is no second job binary. `go/Dockerfile` sets `UBYHOST_GO_ADDR` and `UBYHOST_MIGRATIONS_DIR` itself, so they are not passed.
- The Go code reads env only through `os.Getenv`, `os.LookupEnv` or functions given those (`getenv`/`lookup` parameters). A grep of every quoted `NAME_LIKE_THIS` literal in non-test `go/**/*.go` found 43 variables beyond the five already listed (below). No dynamic or prefix-built names exist (every `getenv(x)` call site passes a literal or a literal-valued parameter). `UBYHOST_TEST_DATABASE_URL` is test-only: do not pass it. The `PG*`, `AWS_*` and `HTTP(S)_PROXY` variables are not set in `.env.example`, so nothing is lost for them.
- **Correction to the review finding:** the Go service really reads `UBYHOST_SECRET_KEY` and `UBYHOST_DATA_KEYS`/`UBYHOST_DATA_KEY_LEGACY` (`go/internal/secure/datakeys.go`, used by the `submit` job), so these stay. What the change removes from the container: `UBYHOST_AWS_*` / SES keys, Turnstile secret, Grafana tokens, admin, backup and Postgres-archive variables, and anything added to `.env` later.
- How compose gets values: compose auto-loads `.env` from the directory of the compose file (`deploy/lightsail/`) for interpolation and for pass-through. A variable written as a bare key (`NAME:` with no value) is passed into the container only when `.env` (or the shell) defines it; when it is undefined the variable is left out. This is the same behaviour as `env_file`. Do **not** write `NAME: ${NAME:-}` for the new variables: that sets an empty string, and Go treats "set but empty" differently from "unset" for `POSTHOG_HOST`, `POSTHOG_ASSETS_HOST` and `UBYHOST_META_GRAPH_VERSION` (defaults apply only when unset, `go/internal/posthog/sync.go` lines 54-61, `go/internal/metacapi/send.go` lines 78-82). The orchestrator checked this with `docker compose config` in a scratch directory.
- `.github/dependabot.yml` ends with a `docker` entry for `/go` (no `gomod`). Existing style: `schedule: { interval: weekly }`.
- `.github/workflows/ci.yml` line 91: `run: pip install pip-audit==2.9.0 && pip-audit -r requirements.txt --strict`. The job's default `working-directory` is `App` (lines 22-24), and the step at line 90 installs `requirements.lock` with `--require-hashes`. `App/requirements.lock` is pip-compile output with `--hash=` lines, so it can be audited with `--require-hashes`. `Dockerfile` line 19 installs `requirements.lock` with `--require-hashes`.
- `docs/ENVIRONMENT.md` line 53 (row `UBYHOST_GO_JOB_KINDS`) says the Go service "reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`".

If an excerpt below is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/docker-compose.yml | edit | `ubyhost-go`: remove `env_file: .env`; add 43 pass-through keys |
| .github/dependabot.yml | edit | append a `gomod` entry for `/go` |
| .github/workflows/ci.yml | edit | line 91: audit `requirements.lock` |
| docs/ENVIRONMENT.md | edit | one sentence in the `UBYHOST_GO_JOB_KINDS` row (line 53) |

No other file may change.

## 4. Steps

**Step 1: compose.** Anchor check: `grep -nF "profiles: [\"go\"]" deploy/lightsail/docker-compose.yml | tail -30`. Read lines 190-206 only. In the `ubyhost-go` service only (lines 198-206), delete the line `    env_file: .env` (the one directly after `profiles: ["go"]`; do not touch the `env_file: .env` lines at about 102 and 152). Then replace the `environment:` block so it reads exactly:

```yaml
    # Only the variables the Go code reads are passed in, not the whole .env
    # (no SES/AWS, Turnstile, Grafana or backup secrets). A bare key is passed
    # through from .env (auto-loaded beside this file) only when it is set there;
    # do not write NAME: ${NAME:-}, an empty string is not the same as unset.
    # A new variable read in go/ must be added here.
    environment:
      UBYHOST_DATABASE_URL: ${UBYHOST_DATABASE_URL:-}
      UBYHOST_GO_JOB_KINDS: ${UBYHOST_GO_JOB_KINDS:-}
      UBYHOST_STRIPE_MODE: ${UBYHOST_STRIPE_MODE:-off}
      UBYHOST_STRIPE_WEBHOOK_SECRET: ${UBYHOST_STRIPE_WEBHOOK_SECRET:-}
      UBYHOST_DATA_DIR: /data
      UBYHOST_AI_FEATURES:
      UBYHOST_AI_PROVIDER:
      UBYHOST_AI_TEST_EMAILS:
      UBYHOST_ANTHROPIC_API_KEY:
      UBYHOST_APP_BASE_URL:
      UBYHOST_BILLING_ENABLED:
      UBYHOST_DATA_KEYS:
      UBYHOST_DATA_KEY_LEGACY:
      UBYHOST_DEPLOYMENT:
      UBYHOST_DOOR_CODES:
      UBYHOST_DPA_VERSION:
      UBYHOST_HEARTBEAT_FILING_URL:
      UBYHOST_HEARTBEAT_ICAL_URL:
      UBYHOST_HEARTBEAT_URL:
      UBYHOST_ICAL_ALLOW_PRIVATE:
      UBYHOST_IMPERSONATION_MAX_HOURS:
      UBYHOST_MAIL_BACKEND:
      UBYHOST_MAX_BATCH:
      UBYHOST_META_ACCESS_TOKEN:
      UBYHOST_META_DATASET_ID:
      UBYHOST_META_GRAPH_VERSION:
      UBYHOST_META_TEST_EVENT_CODE:
      UBYHOST_MISTRAL_API_KEY:
      UBYHOST_MOCK_URL:
      UBYHOST_OPERATOR_EMAIL:
      UBYHOST_PRIVACY_VERSION:
      UBYHOST_PUBLIC_BASE_URL:
      UBYHOST_PY_WEBHOOK_URL:
      UBYHOST_SECRET_KEY:
      UBYHOST_SOAP_WSA_HEADER:
      UBYHOST_STRIPE_MONTHLY_API_CALLS:
      UBYHOST_STRIPE_SECRET_KEY:
      UBYHOST_SUBMIT_SWEEP_MINUTES:
      UBYHOST_TERMS_VERSION:
      UBYHOST_TTLOCK_CLIENT_ID:
      UBYHOST_TTLOCK_CLIENT_SECRET:
      UBYHOST_UBYPORT_DOMAIN:
      UBYHOST_UBYPORT_ENV:
      UBYHOST_UBYPORT_TIMEOUT:
      UBYHOST_WEB_PUSH:
      POSTHOG_ASSETS_HOST:
      POSTHOG_HOST:
      POSTHOG_PROJECT_API_KEY:
```

Count: 5 existing lines plus 43 new keys. The `volumes:` line after the block stays. Verify: `grep -c '^      [A-Z_]*:' ` is not reliable here, so run Step 4 instead. Commit: `1202 step 1`.

**Step 2: dependabot.** Append at the end of `.github/dependabot.yml` (after the last `docker` `/go` entry, keep two-space indent style):

```yaml
  - package-ecosystem: gomod
    directory: /go
    schedule: { interval: weekly }
```

No `groups`, no `ignore` (module bumps stay individual; the toolchain pin is already handled by the docker `/go` entry). Commit: `1202 step 2`.

**Step 3: CI audit.** `grep -nF "pip-audit -r requirements.txt --strict" .github/workflows/ci.yml`. Replace on that one line only `pip-audit -r requirements.txt --strict` with `pip-audit --require-hashes -r requirements.lock --strict` (the job runs in `App/`, so the path is right; the line becomes `run: pip install pip-audit==2.9.0 && pip-audit --require-hashes -r requirements.lock --strict`). Do not run pip-audit (it needs the network; CI proves it). Commit: `1202 step 3`.

**Step 4: doc line.** `grep -nF 'run `./scripts/deploy.sh`. |' docs/ENVIRONMENT.md` must find exactly one line (the `UBYHOST_GO_JOB_KINDS` row). Append, before the closing ` |` of that row: ` The `ubyhost-go` service receives only the variables listed under its `environment:` in `docker-compose.yml`, not the whole `.env`; a new variable read in `go/` must be added there.` Change nothing else. Commit: `1202 step 4`.

## 5. Do not touch

Any `go/` file, the `ubyhost` and `worker` services (they keep `env_file: .env`), `.env.example`, `deploy/lightsail/scripts/`, requirements files, `Dockerfile`. No secrets or values. No `govulncheck` or other new tool (rule 4; owner decision needed). Never push to `main`, never merge.

## 6. Commands

Run each, ending `| tail -30`:

1. Compose check in a scratch directory (the repo has no real `.env`; `docker compose config` needs one):
   `S=$(mktemp -d) && cp deploy/lightsail/docker-compose.yml $S/ && cp deploy/lightsail/.env.example $S/.env && touch $S/.env.walg && printf 'UBYHOST_MAIL_BACKEND=ses\nUBYHOST_AWS_ACCESS_KEY_ID=leakcheck\nPOSTHOG_HOST=\n' >> $S/.env && (cd $S && COMPOSE_PROFILES=go docker compose config 2>&1 | awk '/^  ubyhost-go:/{f=1} f' | sed -n 1,70p) | tail -30`
   Expected inside the `ubyhost-go` block: `UBYHOST_MAIL_BACKEND: ses` and `POSTHOG_HOST: ""` present; `UBYHOST_AWS_ACCESS_KEY_ID` absent; no `ACME_EMAIL`, `TURNSTILE_SECRET` or `GRAFANA_*`; no error.
2. YAML parse: `python3 -c "import yaml;[yaml.safe_load(open(p)) for p in ('.github/dependabot.yml','.github/workflows/ci.yml','deploy/lightsail/docker-compose.yml')];print('ok')" 2>&1 | tail -30` (expect `ok`).
3. Dependabot has the entry: `python3 -c "import yaml;d=yaml.safe_load(open('.github/dependabot.yml'));print([(u['package-ecosystem'],u['directory']) for u in d['updates']])" 2>&1 | tail -30` (expect `('gomod', '/go')` in the list).
4. Actionlint if installed: `command -v actionlint >/dev/null && actionlint .github/workflows/ci.yml 2>&1 | tail -30 || echo "actionlint not installed"`.
5. Tests that read the compose file: `cd App && .venv/bin/python -m pytest tests/test_wp32_container_sizing.py tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` (expect all pass).
6. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expect no errors).
7. `git diff --stat | tail -30` (expect exactly the four files in §3).

## 7. Acceptance

- [ ] `ubyhost-go` has no `env_file`; `ubyhost` and `worker` still do (`grep -n 'env_file' deploy/lightsail/docker-compose.yml | tail -30` shows the other services only).
- [ ] The `ubyhost-go` `environment:` has 48 keys: 5 original plus the 43 listed in Step 1.
- [ ] Command 1 shows the pass-through works and the AWS key does not reach the container.
- [ ] `gomod` for `/go` is in dependabot.yml; YAML parses.
- [ ] ci.yml line 91 audits `requirements.lock` with `--require-hashes`.
- [ ] Commands 2, 5, 6 pass; `git diff --stat` lists only the four files.
- [ ] One doc sentence added to the ENVIRONMENT.md row.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- command 1 shows an `ubyhost-go` variable set to empty that `.env` leaves unset (it means a `${...:-}` form was used by mistake);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1202-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Open one **draft** PR (green merges auto-deploy; keep it a draft). The PR text must carry:

- Why: least privilege for the Go container; Dependabot for Go; audit the file the image installs. Outbound requests: none new.
- **Rollback:** revert the PR (restores `env_file: .env`), then on the server run `cd ~/ubyhost/deploy/lightsail && ./scripts/deploy.sh` (or the owner's usual deploy command). Quick fix without a revert: add the missing variable name to the `ubyhost-go` `environment:` list and redeploy.
- **Post-deploy check (owner):** the numbered steps below.

## Risk list (for the reviewer)

- deploy/lightsail/docker-compose.yml, `ubyhost-go` block: a variable missing from the list silently breaks a Go job. Re-grep to confirm: `grep -rnoE '"[A-Z][A-Z0-9]*_[A-Z0-9_]+"' go --include=*.go | grep -v _test.go | grep -v ERR_CZE | tail -30` (names must all be in the list, except `UBYHOST_GO_ADDR`, `UBYHOST_MIGRATIONS_DIR` set by `go/Dockerfile`, and `UBYHOST_DATABASE_URL` already present).
- .github/workflows/ci.yml line 91: `--require-hashes` with `-r requirements.lock` must pass in CI; if CI's pip-audit rejects it, drop only `--require-hashes` (hashes in the file are still verified).

## Owner steps

Only when the PR is ready to ship (after the draft is marked ready and merged with `scripts/merge-pr-on-green.sh`; the merge auto-deploys):

1. Wait for the deploy to finish (GitHub Actions, "Deploy" run turns green).
2. Open `https://<your-domain>/healthz` in a browser. It must show OK.
3. On the server, run `cd ~/ubyhost/deploy/lightsail && docker compose ps ubyhost-go`. The state must be `Up (healthy)`. If the `go` profile is off in `.env` the service is not listed: skip steps 3 to 5.
4. Run `docker compose logs --tail=50 ubyhost-go`. No lines saying `missing`, `not configured` or `error` that were not there before the deploy.
5. In the admin job view (or after 10 minutes in the logs) check that the Go jobs still ran: `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi`, `deadlines`, each with a recent success time and no new failure. Heartbeat monitors (`UBYHOST_HEARTBEAT_*`) must not alert.
6. If anything is off, tell the orchestrator, or revert the PR and redeploy.
7. In GitHub, open Insights, Dependency graph, Dependabot: a `gomod` entry for `/go` appears within a day.
