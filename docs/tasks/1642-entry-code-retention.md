# 1642: Retention — wipe the entry code after `entry_code_until` or after archiving (Go step, Python twin for the golden)

Status: todo (after 1641 merges)
Depends on: 1641 | Base commit: bdfaa4d4 | Branch: task/1642-entry-code-retention
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (deletes data)

## 1. Objective

Add a retention step `entry_codes` right after `door_code_pins`: it sets `apartment.entry_code_enc` to NULL when `entry_code_until` is more than one day past, or when the apartment was archived more than one day ago. When `entry_code_until` is NULL and the apartment is active, the code stays until the host clears it. A deleted workspace deletes its apartment rows (Python `retention.py:388`, `DELETE FROM apartment WHERE owner_user_id = ?`), and the code goes with them. Hosts cannot delete a single apartment, only archive it (`POST /apartments/{id}/archive`); that is why archived apartments are wiped too (owner decision 2026-11-14; restoring an apartment means the host types the code again).

## 2. Context (verified on bdfaa4d4)

Go step to copy, `go/internal/retention/steps.go:403-416`:

```go
func stepDoorCodePins(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := r.daysAgoISO(1)
	where := `pin_enc IS NOT NULL AND valid_to IS NOT NULL AND valid_to < $1`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM door_code WHERE `+where, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE door_code SET pin_enc = NULL, updated_at = $2 WHERE `+where, cutoff, pyISO(r.now))
	return n, err
}
```

Go registry and label, `go/internal/retention/retention.go:149` and `:278`:

```go
	{"door_code_pins", stepDoorCodePins},
```
```go
		"door_code_pins":       "valid_to more than 1 day ago",
```

Step order test, `go/internal/retention/retention_test.go:46-50` (`TestStepsOrderMatchesPython`, the `want` list ends `"webauthn_challenges", "door_code_pins",` then `"cleaning", ...`).

The Go golden (`go/internal/retention/golden_test.go:20-21`: "golden is testdata/golden.json, written by App/scripts/retention_golden.py from the real Python retention.run() on the same fixture") compares every step's count by name. A Go-only step breaks it. **go-first exception 1 (parity plumbing):** the same step is added to `App/app/retention.py`, the fixture and the golden script, so the golden stays a real Python-versus-Go proof. Side effect: production retention, still Python today (`retention` is not in `UBYHOST_GO_JOB_KINDS`), wipes the codes as well.

Python anchors, `App/app/retention.py`: `:495` `def _door_code_pin_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:`, `:503` `    where = "pin_enc IS NOT NULL AND valid_to IS NOT NULL AND valid_to < ?"`, `:558` `    ("door_code_pins", _door_code_pin_step),`, `:589` `        "door_code_pins": "valid_to more than 1 day ago",`. Golden script state queries, `App/scripts/retention_golden.py:86-87`:

```python
    "door_code": (
        "SELECT id::text || '|' || COALESCE(pin_enc, '~') || '|' || updated_at FROM door_code ORDER BY id"
```

AGENTS rule 2: a new personal-data field gets a line in `App/app/retention.py` (the module docstring or field list where `door_code` PINs are described: `grep -n "pin_enc\|door code" App/app/retention.py | head`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/retention/steps.go` | edit | `stepEntryCodes` after `stepDoorCodePins` |
| `go/internal/retention/retention.go` | edit | registry entry after `door_code_pins`; label |
| `go/internal/retention/retention_test.go` | edit | `"entry_codes"` after `"door_code_pins"` in `want` |
| `go/internal/retention/testdata/fixture.sql` | edit | three apartments' entry codes (step 4) |
| `go/internal/retention/testdata/golden.json` | regenerated | `retention_golden.py` |
| `App/app/retention.py` | edit (exception 1, parity) | doc line, `_entry_code_step`, registry, label |
| `App/scripts/retention_golden.py` | edit (exception 1, parity) | state query `apartment_entry_code` |
| `App/tests/test_retention_entry_code.py` | new | Python step: expired wiped, NULL kept, archived wiped, dry run counts only, owner run skips |

No other file may change.

## 4. Steps

1. Go step after `stepDoorCodePins`:

```go
// stepEntryCodes wipes a building entry code a day after entry_code_until or a
// day after the apartment was archived. A code with no end date stays until the
// host clears it; the apartment row itself goes with its workspace.
func stepEntryCodes(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := r.daysAgoISO(1)
	where := `entry_code_enc IS NOT NULL AND (
		(COALESCE(entry_code_until, '') <> '' AND entry_code_until < $1)
		OR (COALESCE(archived_at, '') <> '' AND archived_at < $1))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM apartment WHERE `+where, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE apartment SET entry_code_enc = NULL WHERE `+where, cutoff)
	return n, err
}
```

   Registry: `{"entry_codes", stepEntryCodes},` on the line after `{"door_code_pins", stepDoorCodePins},`. Label: `"entry_codes": "entry_code_until or archived more than 1 day ago",` after the `door_code_pins` label. Test list: insert `"entry_codes",` after `"door_code_pins",`.
2. Python twin `_entry_code_step(today, dry_run, owner_user_id)` right after `_door_code_pin_step`: the same body shape as lines 495-511, table `apartment`, the where clause of step 1 with `?` for both placeholders (pass `cutoff` twice), and `UPDATE apartment SET entry_code_enc = NULL WHERE ...`. Registry `("entry_codes", _entry_code_step),` after line 558; label as in Go after line 589. Doc line: "apartment.entry_code_enc (building entry code, encrypted): wiped 1 day after entry_code_until or after archiving; kept while NULL until the host clears it; deleted with the workspace."
3. `retention_golden.py`: add `"apartment_entry_code": ("SELECT id::text || '|' || COALESCE(entry_code_enc, '~') FROM apartment ORDER BY id"),` next to `"door_code"` (same tuple style).
4. `fixture.sql`: append (use apartment ids that exist in the fixture: `grep -n "INSERT INTO apartment" go/internal/retention/testdata/fixture.sql`) one `UPDATE` each: an active apartment with `entry_code_enc = 'gAAAA-fixture-expired'`, `entry_code_until = '2020-01-01'`; one with `'gAAAA-fixture-open'` and `entry_code_until` NULL; one archived apartment (or set `archived_at = '2020-01-01T00:00:00+00:00'` on one) with `'gAAAA-fixture-archived'`. Fake ciphertext only.
5. Start the throwaway PostgreSQL of brief 1641 §4 step 3, then from `App/`: `UBYHOST_TEST_DATABASE_URL=... .venv/bin/python scripts/retention_golden.py 2>&1 | tail -5` and `--check`. `git diff --stat` must show only `golden.json` from this run.
6. Python test file (use the retention test fixtures already used by `tests/test_retention*.py`; copy the setup of the door-code PIN test there: `grep -n "door_code_pins\|_door_code_pin_step" App/tests/test_retention*.py | head`).
7. Run §6, commit per step.

## 5. Do not touch

Other retention steps, `stepWorkspaces` / workspace deletion, `door_code` logic, mail, guest pages, `App/app/db.py`. No real code value anywhere.

## 6. Commands

From `go/`: `go test ./internal/retention/... 2>&1 | tail -30` (with `UBYHOST_TEST_DATABASE_URL` set for the golden; 0 skipped)
From `App/`: `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py tests/test_pii_encryption.py tests/test_data_keys.py -q --tb=short -x 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Go and Python both list `entry_codes` right after `door_code_pins`; `TestStepsOrderMatchesPython` and the golden test green.
- [ ] Golden state shows: expired code wiped, open-ended code kept, archived code wiped; dry run wipes nothing; an owner-scoped run returns 0.
- [ ] Retention doc line present; retention + privacy rows green.

## 8. Stop and ask

Stop if: 1641 is not on main; PostgreSQL cannot start (the golden cannot be regenerated: do not hand-edit `golden.json`); the golden diff changes counts of any other step; an excerpt is not found; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1642-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`go/internal/retention/steps.go`, `App/app/retention.py` (both delete data), `go/internal/retention/testdata/golden.json`.

## Owner steps

1. None for Python: the nightly retention job (Python today) runs the new step on deploy. `UBYHOST_RETENTION_AUTOPURGE` governs the Go job as before; the Go step reaches production when `retention` joins `UBYHOST_GO_JOB_KINDS` (thread "Port retention job", J2).
