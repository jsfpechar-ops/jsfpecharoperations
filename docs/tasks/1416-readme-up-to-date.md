# 1416: Bring README.md up to date with what the repository documents

Status: todo
Depends on: none (touches only README.md and the report; independent of 1413 to 1415) | Base commit: 531e8359 | Branch: task/1416-readme-update
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Correct the stale facts in `README.md` (128 lines): database, Go code, staging, test file count, and the `⚠️ UNKNOWN` markers, using only facts that named files confirm. Keep its structure and length (about 128 lines, no new sections).

## 2. Context

Hard rule 3: the repo is public, never add operator identity (names, personal emails, hosts, IPs, server paths). Hard rule 9: one explanation lives in one place; link to docs instead of repeating them. The executor does not guess: every claim it cannot verify goes into the report, and the README keeps (or drops) the old wording, it never invents.

Stale claims the brief writer found (grep to locate; line numbers are from base commit 531e8359):
- Line 13: stack says `SQLite (WAL)`. Line 17: `the database is still SQLite. A Postgres move is planned and explicitly deferred ... No Go code ...`. Lines 24, 66, 98: SQLite file on a Docker volume, `Database | SQLite ...`, `db.py SQLite access`.
- Line 15 and 87 to 88: staging is Render `ubyhost-staging` (`render.yaml`). `docs/DEPLOYMENT.md` lines 13 and 28 still list Render staging, so it may still exist: check, do not assume it is gone.
- Line 103: `~515 files` in `tests/`; `ls App/tests | wc -l` was 780 entries (769 `.py`); say "about 770 files" only after counting `ls App/tests/*.py | wc -l` yourself.
- Lines 8, 16, 34, 36, 41, 66, 122, 127, 128: `⚠️ UNKNOWN` markers.
- Line 128 names a personal-looking email address. Rule 3: do not keep a personal address; refer to [`SECURITY.md`](SECURITY.md) and, only if `grep -n "support@" App/app/config.py` still shows it, the generic support address. Report that you removed it.

Sources the executor may use, and only these: `docs/context/status.md` (Production section: Postgres cutover done, Go routes and jobs live, `COMPOSE_PROFILES=walg,monitoring,go`), `docs/ENVIRONMENT.md` (grep, one section), `docs/LIGHTSAIL.md`, `docs/DEPLOYMENT.md`, `render.yaml`, the `go/` directory (`ls go go/cmd go/internal | head -40`, `go/go.mod` first lines for the module and Go version), `deploy/lightsail/docker-compose.yml` (grep `image:`, `profiles:`, `postgres`), `App/requirements.txt`, `Dockerfile`, `go/Dockerfile`, `App/pytest.ini`, `.github/workflows/ci.yml`. Each is read by grep then a range of 150 lines or fewer.

## 3. Files

| Path | Action | What |
|---|---|---|
| `README.md` | edit | corrected facts, same structure |
| `docs/tasks/1416-report.md` | create | the report incl. the unverified list |

No other file may change (not even a README link target; if a link is broken, report it).

## 4. Steps

1. Locate every claim: `grep -n "SQLite\|sqlite\|Postgres\|No Go\|Go \|Render\|render\|515\|UNKNOWN\|josef@" README.md | cut -c1-200 | head -40`.
2. Database. Confirm from `docs/context/status.md` ("Postgres cutover done") and `deploy/lightsail/docker-compose.yml` (a Postgres service or `UBYHOST_DATABASE_URL`; grep `postgres`) that production runs Postgres. Also check from `App/app/db.py` (`grep -n "sqlite3\|psycopg\|DATABASE_URL" App/app/db.py | head -15`) and `docs/ENVIRONMENT.md` (`grep -n "DATABASE_URL" docs/ENVIRONMENT.md | head`) whether SQLite is still used for local development and tests (CI has both a SQLite job and Postgres jobs). Then rewrite lines 13, 17, 24, 66, 98 so they say: production on PostgreSQL (name the Postgres image tag only if the compose file shows it), SQLite still the local and test default only if step evidence shows it. Replace the commit-hash sentence on line 17 by a link to `docs/context/status.md`.
3. Go. From `ls go/cmd go/internal`, `go/go.mod` and the status file, write one sentence: a Go service (module path and Go version from `go.mod`; binary names from `go/cmd`) serves the routes and runs the queue jobs listed in `docs/context/status.md`, behind Caddy paths from `docs/ENVIRONMENT.md`. Do not copy the route lists; link. Add the Go directory to the layout table (lines 85 to 108) in the existing format, one line each for `go/` and, if it exists, `deploy/lightsail/`. Add Go to the stack line 13 and to the tech-stack table near line 62 to 66 (version from `go.mod` or `go/Dockerfile`).
4. Staging. Read `docs/DEPLOYMENT.md` lines 1 to 40 and `render.yaml` (first 40 lines). If Render staging is still described as current there, keep the README line but make it match (name, mock UbyPort). If a document says it was retired, say so and cite it. If the documents disagree, keep the README line as is and put the disagreement in the report.
5. Test count. `ls App/tests/*.py | wc -l` and `ls App/tests | wc -l`; write `~` plus the `.py` count rounded to ten, and keep the words "pytest; browser tests".
6. Markers. For each `⚠️ UNKNOWN`: if a named source above settles it (for example the version source, a license file at the repo root via `ls`, whether `requirements.lock` is used locally via `grep -n "requirements.lock" docs/*.md README.md | head`), replace the marker with the fact and its file. If not settled, keep the marker unchanged and list it in the report. Do not delete the line 8 legend or line 122 gap report link unless no `UNKNOWN` remains; if one remains keep both. Do not run the app or any test.
7. Check: `git diff --stat README.md | tail -3` (about 128 lines kept, plus or minus 10); `grep -n "josef@\|/home/\|\.pem\|[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}" README.md | head` prints nothing; `grep -c "SQLite" README.md` and read each remaining mention; link check for every relative link you added: `grep -o "](\([^)#h][^)]*\)" README.md | sed 's/](//; s/#.*//' | sort -u | while read -r p; do [ -e "$p" ] || echo "MISSING $p"; done | head`. Then `python3 scripts/context_lint.py 2>&1 | tail -30`.
8. Write the report, commit `1416 step k`, push the task branch (never `main`).

## 5. Do not touch

Every file except `README.md` and the report. No new section, no badges, no secrets, hosts or personal data. Hard rules 3 and 9.

## 6. Commands

Steps 1, 5, 7 (greps and counts). No tests.

## 7. Acceptance

- [ ] README no longer says the database is SQLite-only or that Postgres is deferred, and no longer says there is no Go code, each change backed by a file named in the report.
- [ ] Test count matches `ls App/tests/*.py | wc -l` within ten.
- [ ] No `josef@`, home path, IP address or key file name in README.md (step 7 prints nothing).
- [ ] The link check prints no `MISSING`.
- [ ] Report lists every claim not verified, every remaining `UNKNOWN`, and the Render finding.
- [ ] Context lint has no new error.

## 8. Stop and ask

Stop and write the report if: two sources contradict on production facts (database, Go) rather than staging; a fact needs a file the brief does not name; you reach 25 tool calls or about 50k tokens.

## 9. Report

`docs/tasks/1416-report.md` (600 tokens at most), `Status: review`: files changed, each corrected claim with its source file, unverified claims, remaining `UNKNOWN`, the Render finding, the removed email, deviations, questions, owner steps.

## Risk list (for the reviewer)

`README.md` lines on database, Go and staging (the facts), and that no operator identity was added.

## Owner steps

1. Open the PR and wait for the green check.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
