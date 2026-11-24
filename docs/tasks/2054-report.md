# 2054 report: functional parity rerun

Status: review

## 1. Files changed

- docs/tasks/2054-report.md (this file). No other tracked file changed.
- Outside the repo: artifacts under /var/tmp/parity-2054/ (audit.out, handlers.json, docs/go-python-parity-audit.json). The /cursor/stores symlinks from step 2 remain in place.

## 2. Commands (last lines)

- Step 1 (earlier session, not re-run): env OK, Postgres 127.0.0.1:5433 accepting connections, Go at /usr/local/go/bin/go.
- Step 2 (earlier session, not re-run): symlinks under /cursor/stores/bc-6e0cc745-.../ present.
- Step 3 (re-check): `select datname, pid, application_name ... where datname like 'parity%'` returned no rows. Count 0. Leftover `ubyhost-web-parity` processes: 0. OK.
- Step 4a: `python3 scripts/go_jobs_parity.py`
  - `15 Python kinds, 15 Go kinds, 0 failing` and exit 0. 2.6 s.
- Step 4b: `python3 scripts/go_parity_check.py --all --json /var/tmp/parity-2054/handlers.json`
  - `342/342 Python routes have a Go handler`.
- Step 5: audit started 2026-11-24 15:04:06 UTC in the background.
- Step 6: poll finished with the audit output tail:
  - `{"paths": 137, "rows": 843, "pass": 647, "pass_soft": 14, "accepted": 179, "fail": 3}`
  - `EXIT 1` (some rows fail; not a crash).
- Step 7: failing rows read from docs/go-python-parity-audit.json (`lang_rows` 396, `pin_paths` 12).

## 3. Counts

- Audit: rows 843, pass 647, pass-soft 14, accepted 179, fail 3.
- Jobs: 15 of 15 Python job kinds match Go; 0 failing.
- Handlers: 342 of 342 Python routes have a Go handler. Missing: 0.
- Runtime: audit about 7.5 min (15:04:06 to 15:11:28 UTC).
- Baseline: fail 0 / 843 rows. Now: fail 3 / 843 rows. Row count matches the baseline.

## 4. Failing rows

- FAIL: `/terms/booking`, persona anon, DOM drift (py 200, go 200, body length 526 vs 3836, similarity 0.23).
- FAIL: `/terms/booking`, persona host, same DOM drift.
- FAIL: `/terms/booking`, persona admin, same DOM drift.

Not marked RETIRED. The brief marks RETIRED only for routes starting `/booking-sites` and payment routes. `/terms/booking` does not match those prefixes. The owner or orchestrator should decide whether it belongs to the retired booking set.

RETIRED rows: none found in the failing list.

## 5. Acceptance (section 7)

- [x] Audit finished with a JSON summary line and `EXIT 1` (not a crash).
- [x] Report lists rows, pass, pass-soft, accepted, fail; job-kind result; handler missing count (0).
- [x] Every failing row written in plain words, marked FAIL.
- [x] Comparison line: baseline fail 0 / 843 rows; now fail 3 / 843 rows.
- [ ] `git status --short` shows only this report (checked before the commit: clean tree).

## 6. Deviations

Done: steps 1 to 8. Step 3 was re-checked after the orchestrator stopped the leftover Go servers; it showed 0 rows.

## 7. Questions

- Is `/terms/booking` a retired booking route? If yes, the three rows should move to RETIRED and the fail count becomes 0.

## 8. Owner steps left

- Decide on `/terms/booking` (FAIL or RETIRED). No push done here; the orchestrator pushes the branch.
- Leftover Go parity servers at the end of the run: 0.
