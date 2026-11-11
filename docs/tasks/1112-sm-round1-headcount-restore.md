# 1112: Restore the 1095 headcount code that the round-1 combined branch overwrote

Status: review
Depends on: none | Base commit: 35381fdff | Branch: task/sm-round1-combined
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [explicit state machines](../plans/explicit-state-machines.md), round 1. Correction for PR #920 (the combined round-1 PR).

**HIGH RISK: police filing and headcount.** This is a correction, not a feature. You restore two function bodies byte for byte from `origin/main`. You do not write new code, you do not edit any other line of `App/app/reporting.py` or `App/app/claim.py`, and you do not touch the three state-machine blocks (`TRANSITIONS`, `SUBMISSION_TRANSITIONS`, claim `TRANSITIONS`).

## 1. Objective

The combined round-1 commit `35381fdff` (PR #920, branch `task/sm-round1-combined`) carries an older copy of two functions than `origin/main` (brief 1095, the lead-reduced headcount, merged in PR #896). `expected_guest_count` in `App/app/reporting.py` ignores `reservation["lead_reduced_guests"]`, and `_declared_count` in `App/app/claim.py` no longer calls `reporting.expected_guest_count`. On the branch `App/tests/test_headcount_1095.py` fails 23 of 48 tests. Restore both functions from `origin/main` verbatim so the round-1 diff against `main` contains only the declared-and-pinned state-machine additions (no runtime change, as the plan requires).

## 2. Context

Rules that bind this brief: round 1 is "declare and pin, no runtime change"; the diff of `App/app/` against `origin/main` must be insertions of inert dicts only; no migration, no dependency, no template or copy change; no Go change. Nothing here may read `TRANSITIONS` at runtime.

Excerpts. Each must exist verbatim; if one is not found, STOP (section 8).

### The wrong copies (on the branch today)

`App/app/reporting.py`, line 458:

```python
def expected_guest_count(reservation) -> Optional[int]:
    """Host override wins over what the lead guest declared."""
    if reservation["expected_guests_override"]:
        return reservation["expected_guests_override"]
    return reservation["declared_guests"]
```

`App/app/claim.py`, line 383:

```python
def _declared_count(reservation, row) -> int:
    """The headcount a resend keeps: the host's override, else the declared one."""
    if reservation["expected_guests_override"]:
        return int(reservation["expected_guests_override"])
    expected = reporting.reservation_progress(reservation)["expected"]
    return int(expected or row["declared_guests"] or 1)
```

### The right copies (`origin/main`, ec7736303) — restore these verbatim

`App/app/reporting.py` on `origin/main` (line 420), the whole function from `def` to the last `return`:

```python
def expected_guest_count(reservation) -> Optional[int]:
    """Host override, else the declared count; a lower lead reduction wins over both."""
    if reservation["expected_guests_override"]:
        base = reservation["expected_guests_override"]
    else:
        base = reservation["declared_guests"]
    try:
        reduced = reservation["lead_reduced_guests"]
    except (KeyError, IndexError):
        reduced = None
    if reduced and (base is None or reduced < base):
        return reduced
    return base
```

`App/app/claim.py` on `origin/main` (line 361), the whole function:

```python
def _declared_count(reservation, row) -> int:
    """The headcount a resend keeps: the host's override, else the declared one."""
    expected = reporting.expected_guest_count(reservation)
    return int(expected or row["declared_guests"] or 1)
```

Each restored body is followed on `origin/main` by two blank lines (then `# Well under SQLite's bound-parameter limit ...` in `reporting.py`, `def _completion_fee(` in `claim.py`). Keep the blank lines the branch already has there.

### What must stay as it is (the round-1 additions, not part of this correction)

- `App/app/reporting.py`: the `TRANSITIONS` dict (brief 1105, directly after `NOT_REQUIRED = "not_required"  # Czech nationals: house book only`) and the `SUBMISSION_TRANSITIONS` dict (brief 1106, directly before the comment `# The envelope is the only thing in the row that carries guest data`).
- `App/app/claim.py`: the `TRANSITIONS` dict (brief 1109, directly after `CLAIMED = "claimed"`).
- Every other file the combined commit added or changed (`cleaning_codes.py`, `door_codes.py`, `guest_guide_import.py`, `mail.py`, `meta_capi.py`, `push.py`, the `test_sm_*.py` files, the briefs).

### Expected diff against `origin/main` once the restore is done

`git diff origin/main --stat -- App/app` lists the eight files of the combined commit, all insertion-only (no `-` line in any of them). In particular `reporting.py` is `60 insertions(+)` (TRANSITIONS 38 + SUBMISSION_TRANSITIONS 22) and `claim.py` is `22 insertions(+)`. Before the restore they show `74 +++-` and `26 +-`.

### Open questions (findings; this brief does not fix them)

1. How the combined branch picked up the old function bodies is not investigated here (most likely a conflict resolved in favour of the pre-1095 side of a merge). The fix is the restore only. The orchestrator decides whether to rebase the branch on `origin/main` instead.
2. `App/tests/test_endtoend.py::test_06_calendar_import_creates_the_stay_and_skips_the_block` fails in the agent VM on this branch (brief 1105 report: "same row flaky on BASE"). It is not caused by the headcount code. Step 6 says how to treat it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/reporting.py` | edit | Replace the body of `expected_guest_count` with the `origin/main` copy (step 2). Nothing else |
| `App/app/claim.py` | edit | Replace the body of `_declared_count` with the `origin/main` copy (step 3). Nothing else |
| `docs/tasks/1112-report.md` | create | Your report (section 9) |

No other file may change. No test file changes: `test_headcount_1095.py` and every `test_sm_*.py` stay as they are.

## 4. Steps

Run every command from the repo root unless it says otherwise. Commit after steps 3 and 8 only (messages below).

1. Confirm the anchors and fetch `main`.

   ```
   git fetch origin main 2>&1 | tail -30
   git rev-parse --short origin/main | tail -30
   git show origin/main:App/app/reporting.py | grep -nF "a lower lead reduction wins over both" | tail -30
   git show origin/main:App/app/claim.py | grep -nF "expected = reporting.expected_guest_count(reservation)" | tail -30
   grep -nF '"""Host override wins over what the lead guest declared."""' App/app/reporting.py | tail -30
   grep -nF 'expected = reporting.reservation_progress(reservation)["expected"]' App/app/claim.py | tail -30
   grep -cE "^TRANSITIONS = \{|^SUBMISSION_TRANSITIONS = \{" App/app/reporting.py | tail -30
   grep -c "^TRANSITIONS = {" App/app/claim.py | tail -30
   ```

   Expected, in order: fetch output with no error; a short hash (`ec77363` or a later merge commit; if later, `git diff ec7736303 origin/main --stat -- App/app/reporting.py App/app/claim.py | tail -30` must print nothing, else STOP); `420:` line with the docstring; `363:` line; one line at `459:`; one line at `387:`; `2`; `1`. Any other result: STOP.

2. Restore `expected_guest_count` in `App/app/reporting.py`. Use the edit tool (not sed) to replace exactly the five-line wrong copy from section 2 (from `def expected_guest_count` through `    return reservation["declared_guests"]`) with the thirteen-line `origin/main` copy, character for character, including the new docstring. Then check, from the repo root (the `diff` uses bash process substitution; run it under `bash`):

   ```
   diff <(git show origin/main:App/app/reporting.py | sed -n '/^def expected_guest_count/,/^    return base$/p') <(sed -n '/^def expected_guest_count/,/^    return base$/p' App/app/reporting.py) | tail -30
   git diff --stat -- App/app/reporting.py | tail -30
   ```

   Expected: the `diff` prints nothing; the stat is `1 file changed, 11 insertions(+), 3 deletions(-)` and names only `reporting.py`.

3. Restore `_declared_count` in `App/app/claim.py`. Use the edit tool to replace exactly the two lines

   ```python
       if reservation["expected_guests_override"]:
           return int(reservation["expected_guests_override"])
       expected = reporting.reservation_progress(reservation)["expected"]
   ```

   with the one line

   ```python
       expected = reporting.expected_guest_count(reservation)
   ```

   The `def`, the docstring and the `return int(expected or row["declared_guests"] or 1)` line stay. Then check:

   ```
   diff <(git show origin/main:App/app/claim.py | sed -n '/^def _declared_count/,/^    return int(expected/p') <(sed -n '/^def _declared_count/,/^    return int(expected/p' App/app/claim.py) | tail -30
   git diff --stat -- App/app/claim.py | tail -30
   ```

   Expected: the `diff` prints nothing; the stat names only `claim.py` (`1 insertion(+), 3 deletions(-)`). Commit: `git add App/app/reporting.py App/app/claim.py && git commit -m "1112 step 3: restore expected_guest_count and _declared_count from main" | tail -30`.

4. Prove the correction touches nothing else and that the state-machine blocks are intact.

   ```
   git diff origin/main -- App/app/reporting.py App/app/claim.py | grep -c '^-[^-]' | tail -30
   git diff origin/main --stat -- App/app | tail -30
   git diff origin/main -- App/app/reporting.py App/app/claim.py | grep -nE "expected_guest_count|_declared_count|lead_reduced" | tail -30
   grep -c "TRANSITIONS" App/app/reporting.py App/app/claim.py | tail -30
   ```

   Expected: `0` (no line of `origin/main` is removed or changed in either file); eight files, all insertion-only, `reporting.py | 60 +++` and `claim.py | 22 +++`; no output from the third command (neither function appears in the diff); `reporting.py` and `claim.py` counts unchanged from step 1 (the `TRANSITIONS` and `SUBMISSION_TRANSITIONS` blocks are still there). Any difference: STOP.

5. Run the headcount tests. From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_headcount_1095.py -q --tb=short 2>&1 | tail -30
   ```

   Expected: all pass, `0 failed` (48 tests; the file has 30 test functions, parametrised). Before the restore: `23 failed, 25 passed`. A failure: STOP and report the last 30 lines (do not edit the test, do not edit any other function).

6. Run the filing row (the same command as step 5 of [brief 1105](1105-sm-guest-submit-state.md), the test-map row "Filing, UbyPort, worker, claim"). From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short 2>&1 | tail -30
   ```

   Expected: all pass. Known exception: if the only failure is `tests/test_endtoend.py::test_06_calendar_import_creates_the_stay_and_skips_the_block` (663 passed, 1 failed, as in the 1105 report), run it alone once on a clean copy of `origin/main` to show it is not ours:

   ```
   git worktree add --detach /tmp/main-check origin/main 2>&1 | tail -30
   cd /tmp/main-check/App && /agent/repos/jsfpecharoperations/App/.venv/bin/python -m pytest tests/test_endtoend.py -q --tb=line -k test_06 2>&1 | tail -30
   cd /agent/repos/jsfpecharoperations && git worktree remove --force /tmp/main-check && git worktree prune
   ```

   If `test_06` fails there too, record "fails on origin/main as well" in the report and move on. If it passes on `origin/main` and fails on this branch, STOP: the restore is not the cause, but report it. Any other failure: STOP.

7. Run every state-machine pin test. From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short 2>&1 | tail -30
   ```

   Expected: all pass, `0 failed` (the eight `test_sm_*.py` files; 100 tests at brief time). The restore touches no writer a pin test reads, so a failure here means a step went wrong: STOP and report it.

8. Run the context lint, write the report and commit.

   ```
   python3 scripts/context_lint.py 2>&1 | tail -30
   ```

   Expected: no error (warnings about other briefs are fine; copy them into the report). Write `docs/tasks/1112-report.md` (section 9), set `Status: review` at the top of this brief, then:

   ```
   git add docs/tasks/1112-report.md docs/tasks/1112-sm-round1-headcount-restore.md && git commit -m "1112 step 8: report" | tail -30
   ```

   Push is the owner's step (section 8): `git push origin task/sm-round1-combined`.

## 5. Do not touch

- Everything in `App/app/reporting.py` and `App/app/claim.py` except the two function bodies of steps 2 and 3. In particular the `TRANSITIONS` dict and `SUBMISSION_TRANSITIONS` dict in `reporting.py`, and the `TRANSITIONS` dict in `claim.py`.
- Every other writer and every other file under `App/app/`, `go/`, migrations, templates.
- Every test file (`test_headcount_1095.py`, all `test_sm_*.py`): the fix is to the code, never to the tests.
- `docs/context/test-map.md`, `docs/OPERATIONS.md`, the other round-1 briefs.
- AGENTS.md hard rules that apply: 1 (UbyPort filing correctness beats every other feature: the headcount feeds the filing gate, so the restore must be verbatim), 4 (no new dependency), 5 (no migration), 8 (never push to `main`; do not merge).

## 6. Commands

| Step | Command (from `App/` unless noted) | Expected |
|---|---|---|
| 2, 3 | the two `diff <(git show origin/main:...)` commands, repo root | no output |
| 4 | `git diff origin/main -- App/app/reporting.py App/app/claim.py \| grep -c '^-[^-]'`, repo root | `0` |
| 5 | `.venv/bin/python -m pytest tests/test_headcount_1095.py -q --tb=short 2>&1 \| tail -30` | `0 failed` (was `23 failed, 25 passed`) |
| 6 | the filing row command in step 6 | all pass, or only `test_06` failing and also failing on `origin/main` |
| 7 | `.venv/bin/python -m pytest tests/test_sm_*.py -q --tb=short 2>&1 \| tail -30` | `0 failed` |
| 8 | (repo root) `python3 scripts/context_lint.py 2>&1 \| tail -30` | no error |

Never the full suite.

## 7. Acceptance

- [ ] `expected_guest_count` in `App/app/reporting.py` and `_declared_count` in `App/app/claim.py` are identical to `origin/main` (the step 2 and step 3 `diff` commands print nothing).
- [ ] `git diff origin/main -- App/app/reporting.py App/app/claim.py | grep -c '^-[^-]'` prints `0`; the `TRANSITIONS`, `SUBMISSION_TRANSITIONS` and claim `TRANSITIONS` blocks are unchanged by this brief (`git diff HEAD~1 -- App/app` after step 3 shows only the two function bodies).
- [ ] `tests/test_headcount_1095.py`: `0 failed`.
- [ ] Filing row (the step 5 command of brief 1105): all pass, or the `test_06` exception documented as failing on `origin/main` too.
- [ ] `tests/test_sm_*.py`: `0 failed`.
- [ ] `git diff --stat origin/main -- go | tail -30` prints nothing.
- [ ] Context lint: no error.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor in section 2 or step 1 is not found, or `origin/main` has moved the two functions since `ec7736303`;
- a restore `diff` prints anything, or the step 4 count of removed lines is not `0`;
- a headcount or `test_sm_*` test fails (do not edit a test or another function);
- the filing row fails anywhere except the documented `test_06` case;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1112-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat HEAD~2`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations (the `test_06` result on `origin/main`, if it came up).
5. Questions (copy the two open questions from section 2 if still unanswered).
6. Owner steps left.

Do not open a new PR: the commits go on PR #920's branch.

## Risk list (for the reviewer)

- `App/app/reporting.py`: only the `expected_guest_count` body changed; the diff against `origin/main` is insertions only (60 lines).
- `App/app/claim.py`: only the `_declared_count` body changed; the diff against `origin/main` is insertions only (22 lines).
- No test file changed. Confirm `git diff --stat HEAD~2 | tail -30` lists the two source files and the two docs files and nothing else.

## Owner steps

1. Push `task/sm-round1-combined` (`git push origin task/sm-round1-combined`) so PR #920 picks up the correction, and wait for the checks to go green.
2. Tell the orchestrator it is green. The orchestrator merges PR #920 with `scripts/merge-pr-on-green.sh` and adds the test-map rows.
