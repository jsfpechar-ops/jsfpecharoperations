# 1064 report

Status: blocked

Files changed: `scripts/count_required_inputs.py` (new), this report, brief status.

Commands:
- syntax check: `syntax ok`
- `--selftest`: `selftest: OK`
- count: 16 lines, flow/required/total equal the brief table (baseline below)
- `python3 scripts/context_lint.py`: FAIL, pre-existing: docs/context/status.md ~712 tokens > cap 700 (not touched by this brief, section 5 forbids docs/context/). Orchestrator must compact status.md.

Before-table (Wave 1 baseline, base commit 0d851ca4):

```
flow                         | required | total 
sign-up                      |        2 |     4 
setup wizard (first run)     |       21 |    45 
operator (entity)            |        4 |    10 
property create              |        6 |    10 
calendars                    |        2 |     4 
police details (wizard step) |        5 |     7 
stay fee (wizard step)       |        4 |    17 
lock (wizard step)           |        2 |     4 
invoice                      |        4 |    40 
payment request              |        2 |     7 
guest 1 PIN                  |        1 |     1 
guest 2 pick stay            |        0 |     0 
guest 3 claim                |        2 |     2 
guest 4-7 form               |        9 |    16 
guest 8 stay hub             |        1 |     1 
```

Section 7: all items ticked (script imports only re, sys, pathlib; no App/ change; no UI, no screenshots).

Deviations: branch `claude/1064-required-inputs-count` used instead of the header's `task/...`. Fetching it needed an explicit refspec. Questions: none. Owner steps: merge.
