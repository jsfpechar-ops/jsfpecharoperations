# 1146: test_endtoend.py gets its own database (K-E2E-ORDER)

Status: todo
Depends on: none | Base commit: 7a7e32de | Branch: task/1146-e2e-isolation
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`App/tests/test_endtoend.py` fails 13 tests whenever any earlier test module has left rows in the shared SQLite test database. Give the file a private database so it no longer depends on test order. Test-side only: no app code changes.

## 2. Context

Root cause (reproduced, verified by the orchestrator's simulation; the diff below was run in a scratch worktree):

- `App/tests/conftest.py` sets one SQLite file for the whole pytest session (`os.environ.setdefault("UBYHOST_DB", str(_TMP / "test.db"))`). Only PostgreSQL gets a clean database per module (`postgresql_schema_reset`, module scope, autouse). SQLite does not. That is why CI (Postgres) and a lone run pass, and the combined SQLite run fails.
- `test_endtoend.py` assumes an empty install: test 02 expects the onboarding demo, test 06 asserts exactly one `reservation` row, test 08 and later use `SELECT * FROM reservation` without a filter.
- Any predecessor module that leaves reservation, apartment or guest rows breaks it. Proven predecessors that alone trigger it (each run as `<file> tests/test_endtoend.py`): `tests/test_form_chrome.py` (12 failed), `tests/test_finish_moment_0274.py` (11 failed), `tests/test_host_language.py` (12 failed). It is not specific to the filing/claim files; the whole-suite order (all non-browser files, then test_endtoend) fails 13. First failure: `test_06_calendar_import_creates_the_stay_and_skips_the_block`, `AssertionError: the blocked dates should not become a stay` (`assert 2 == 1` after test_form_chrome; `124 == 1` after the whole suite).
- Not in the 1142 mix itself: the 1142 file list alone (claim, icalsync, sm_*, endtoend) passes in this checkout; the failure needs a leaking module in the list.

The established pattern for a private SQLite database is `monkeypatch.setattr(config, "DB_PATH", tmp_path / "x.sqlite3")` before `db.init_db()` (see `tests/test_0540_cleaning_tables.py`). `conftest.postgresql_init_db_reset` treats a new `DB_PATH` as a fresh database on PostgreSQL too, so the same fix is correct on both backends.

Anchors in `App/tests/test_endtoend.py` (must be found verbatim, else STOP, §8):

Anchor A (line 20):
```
from app import auth, claim, codelists, db, reporting
```

Anchor B (lines 87-89):
```
@pytest.fixture(scope="module")
def client(mock_ubyport):
    db.init_db()
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_endtoend.py | edit | import `config`; new module fixture `e2e_database`; `client` depends on it |
| docs/tasks/1146-report.md | create | the report |

No other file may change.

## 4. Steps

1. In `App/tests/test_endtoend.py`, replace Anchor A with:
```
from app import auth, claim, codelists, config, db, reporting
```
Check: `grep -n '^from app import' App/tests/test_endtoend.py | tail -30` shows `config` in the line.

2. Replace Anchor B with exactly:
```
@pytest.fixture(scope="module")
def e2e_database(tmp_path_factory):
    """A database of its own: this file assumes an empty install (K-E2E-ORDER)."""
    from _pytest.monkeypatch import MonkeyPatch

    patcher = MonkeyPatch()
    patcher.setattr(config, "DB_PATH", tmp_path_factory.mktemp("e2e") / "e2e.sqlite3")
    yield
    patcher.undo()


@pytest.fixture(scope="module")
def client(mock_ubyport, e2e_database):
    db.init_db()
```
Check: `git diff --stat | tail -30` shows `App/tests/test_endtoend.py | 15 +++++++++++++--` (13 insertions, 2 deletions).

3. Run the section 6 commands in order, including the revert-bite.

## 5. Do not touch

`App/app/`, `go/`, `App/tests/conftest.py`, any other test file. No new dependency. No `PYTHONPATH=App`.

## 6. Commands

Run from `App/`.

a. Failing order, fix applied (a leaking predecessor first):
`.venv/bin/python -m pytest tests/test_form_chrome.py tests/test_finish_moment_0274.py tests/test_host_language.py tests/test_endtoend.py -q --tb=short 2>&1 | tail -30`
Expect: all pass, 0 failed (about 60 passed).

b. The 1142 filing/claim mix plus a leaker last before endtoend:
`.venv/bin/python -m pytest tests/test_claim_*.py tests/test_filing_*.py tests/test_form_chrome.py tests/test_endtoend.py -q --tb=short 2>&1 | tail -30`
Expect: all pass.

c. test_endtoend alone:
`.venv/bin/python -m pytest tests/test_endtoend.py -q --tb=short 2>&1 | tail -30`
Expect: `28 passed`.

d. Predecessor alone:
`.venv/bin/python -m pytest tests/test_form_chrome.py -q --tb=short 2>&1 | tail -30`
Expect: all pass.

e. Successor check (endtoend must not leak into later modules):
`.venv/bin/python -m pytest tests/test_endtoend.py tests/test_form_chrome.py tests/test_host_language.py tests/test_filing_watchdog.py -q --tb=short 2>&1 | tail -30`
Expect: all pass.

f. Revert-bite: `git stash push -- tests/test_endtoend.py`, then run command a again with `--tb=no`. Expect: about `12 failed`, first `test_06_...`. Then `git stash pop` and re-run command a: all pass again. Confirm `git diff --stat | tail -30` is back to the one file.

Do not run the full suite. CI runs the rest.

## 7. Acceptance

- [ ] Command a: 0 failed.
- [ ] Commands b, c, d, e: 0 failed, 0 skipped added by this change.
- [ ] Revert-bite (f): failed with the fix removed, passed after restore.
- [ ] `git diff --stat` shows only `App/tests/test_endtoend.py` (plus the report).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- command a still fails after the fix (report the first traceback; do not patch app code);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1146-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/tests/test_endtoend.py`: the fixture must patch `config.DB_PATH` before `db.init_db()` and undo it at module end.

## Owner steps

1. After review, open the draft PR and merge with `scripts/merge-pr-on-green.sh`.
