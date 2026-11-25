# 2054: functional parity rerun (DOM and behaviour audit, jobs, handlers)

Status: todo
Depends on: none | Base commit: current tip of the branch | Branch: the branch you are on (claude/nice-hawking-fw98ct); do not push, merge or open a PR
Executor: Haiku 5.5, alone | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Rerun the Go-versus-Python parity tools on the current branch and report the numbers. Compare them with the baseline in docs/context/status.md: **fail 0, 843 rows, 6 languages**. Report only. Fix nothing.

## 2. Context

- `scripts/e2e/page_parity_audit.py` starts Python and Go against one seeded Postgres, opens every GET route in Chromium at 390 and 1280 for 3 personas (anon, host, admin), and scores each row `pass`, `pass-soft`, `accepted*` or `fail*`. It takes no arguments. It runs every language itself (cs, de, es, fr, uk, vi, plus the default) and one PIN pass; **it cannot be split by language**. Expect 15 to 40 minutes, longer than one Bash call (600000 ms max), so you run it in the background and poll.
- The audit hard-codes `STORE_MEDIA=/cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/media/parity` and `STORE_DOC=.../docs/go-python-parity-audit.md`. No env var overrides them and they are written unconditionally (screenshots, then a `.json` next to `STORE_DOC`). `/cursor` does not exist here. Without editing code, redirect them with symlinks (step 2). That needs root (`id -u` prints 0).
- Another agent may use the parity databases. The audit drops and recreates `parity_tpl` and `parity_run` on 127.0.0.1:5433.
- Booking site and payments are retired. Rows for `/booking-sites*` and for payment routes (`/predplatne*`, Stripe, `/pay*`) are reported as RETIRED, not as failures.
- Never print guest data. The repo is public.

## 3. Files

| Path | Action | What |
|---|---|---|
| docs/tasks/2054-report.md | create | the report |

No other tracked file may change. Artifacts go under `/var/tmp/parity-2054/` (outside the repo).

## 4. Steps

1. Set up (never pipe a source). From the repo root:
   `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; tail -5 /var/tmp/parity_env.log; pg_isready -h 127.0.0.1 -p 5433 | tail -3; which go | tail -3`
   Expect: empty log or few lines, `127.0.0.1:5433 - accepting connections`, a path ending `/go`. Anything else: STOP.
2. Redirect the hard-coded store paths (shell state does not persist between calls; this is filesystem state):
   `mkdir -p /var/tmp/parity-2054/media /var/tmp/parity-2054/docs /cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1 && ln -sfn /var/tmp/parity-2054/media /cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/media && ln -sfn /var/tmp/parity-2054/docs /cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/docs 2>&1 | tail -30`
   Check: `ls -l /cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1 | tail -5` shows two symlinks to `/var/tmp/parity-2054/...`. If `mkdir` fails (not root): STOP and ask the owner.
3. Check nobody else is using the parity databases:
   `$UBYHOST_E2E_PSQL postgresql://postgres@127.0.0.1:5433/postgres -tAc "select datname, count(*) from pg_stat_activity where datname like 'parity%' group by 1" | tail -30`
   Expect: no rows. Any row: STOP (the other agent is running) and report that.
4. Fast tools first (each under 2 minutes; handler check and jobs both build the Go probe):
   `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; python3 scripts/go_jobs_parity.py 2>&1 | tail -30`
   Expect: exit 0 and a line saying all job kinds match (15 of 15). Note any "missing" or "interval" line.
   `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; python3 scripts/go_parity_check.py --all --json /var/tmp/parity-2054/handlers.json 2>&1 | tail -30`
   Expect: a summary; with `--all` it never fails, so read the "missing" count. Missing handlers for retired booking or payment routes are RETIRED; any other missing handler is a finding. Use `python3 -c` on the json only if the summary is not enough.
5. Start the DOM and behaviour audit in the background (one call; it returns at once):
   `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; nohup sh -c 'App/.venv/bin/python scripts/e2e/page_parity_audit.py > /var/tmp/parity-2054/audit.out 2>&1; echo "EXIT $?" >> /var/tmp/parity-2054/audit.out' > /dev/null 2>&1 & echo started | tail -3`
   Expect: `started`. It does not need the `--` flags; do not add arguments.
6. Wait without burning tool calls (each call at most 590 s; repeat until it prints `EXIT`, at most 6 calls, so at most about 60 minutes):
   `timeout 590 sh -c 'until grep -q "^EXIT" /var/tmp/parity-2054/audit.out; do sleep 15; done'; tail -5 /var/tmp/parity-2054/audit.out`
   Finished: last lines are one JSON object `{"paths": ..., "rows": ..., "pass": ..., "pass_soft": ..., "accepted": ..., "fail": ...}` and `EXIT 0` (fail 0) or `EXIT 1` (some fail). A Traceback or `EXIT 2+` is an audit crash, not a parity result: copy its last 15 lines into the report and STOP. After 6 waits without `EXIT`: STOP, report `blocked`, say how far it got (`tail -3` of the log).
7. Read the failing rows from the artifact (no table dump; only failures):
   `python3 -I -c "import json;d=json.load(open('/var/tmp/parity-2054/docs/go-python-parity-audit.json'));m=d['meta'];print({k:m[k] for k in ('paths','rows','pass','pass_soft','accepted','fail','lang_rows','pin_paths')});[print(r['verdict'],r['route'],r['persona'],r['py_status'],r['go_status'],r['cause'],r['note'][:120]) for r in d['rows'] if r['verdict'].startswith('fail')][:60]" 2>&1 | tail -60`
   If more than 55 failing rows, also print counts per `cause` (`m['causes']`) and list the routes grouped by cause. Mark each failing row whose route starts `/booking-sites` or is a payment route (see section 2) as RETIRED.
8. Write `docs/tasks/2054-report.md` (section 9) and commit it by explicit path:
   `git add docs/tasks/2054-report.md && git commit -m "2054 report: functional parity rerun" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf" 2>&1 | tail -30`
   Do not push. Hand the push to the orchestrator.

## 5. Do not touch

- Any code, test, template, doc or script. No fix, no "improvement", no edit of the `STORE_*` constants.
- `main`, secrets, servers, deploy. No push, merge or PR.
- No new dependency. No full pytest suite.

## 6. Commands

Only those in section 4. Every command ends `| tail -30` (or `tail -60` where stated). Runtime limits: steps 1 to 3 and 7 under 1 minute each; step 4 under 2 minutes each; steps 5 and 6 about 15 to 40 minutes in total; one Bash call never above 600000 ms.

Expected results, all as the baseline: audit `fail` 0; rows about 843 (the count may differ by the new rows since the baseline; say by how much); jobs 15 of 15; handlers: no missing handler outside the retired routes.

## 7. Acceptance

- [ ] Audit finished with a JSON summary line and `EXIT 0` or `EXIT 1` (not a crash).
- [ ] Report lists rows, pass, pass-soft, accepted, fail, for the audit; the job-kind result; the handler-check missing count.
- [ ] Every failing row is written in plain words (route, persona, what differs: status or content) and marked FAIL or RETIRED.
- [ ] Comparison line: "baseline fail 0 / 843 rows; now fail N / M rows".
- [ ] `git status --short | tail -30` shows only `docs/tasks/2054-report.md` (and the brief itself if still untracked).

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- step 1 shows Postgres or Go missing;
- step 2 `mkdir` fails (not root) or step 3 shows parity connections (another agent is running);
- the audit crashes (Traceback or `EXIT 2` or higher), or does not finish within 6 waits;
- you reach 25 tool calls or about 50k tokens (write `Done: steps 1 to k. Left: steps k+1 to 8.`);
- a step is unclear or needs a code change.

## 9. Report

Write `docs/tasks/2054-report.md` (600 tokens at most), `Status: review`:

1. Files changed (only the report).
2. Each command with the last 5 lines of its output.
3. Counts: audit rows, pass, pass-soft, accepted, fail; jobs; handlers. Baseline comparison.
4. Every failing row in plain words, with RETIRED rows listed separately and not counted as failures.
5. §7 ticked.
6. Deviations, Questions, owner steps left (none expected; the symlinks under `/cursor` are outside the repo and may stay).

## Risk list (for the reviewer)

None; no code changes. Read the failing-row list in the report.

## Owner steps

None.
