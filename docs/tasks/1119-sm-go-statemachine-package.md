# 1119: Go home for every round 1 transition table, with a parity test

Status: todo
Depends on: PR #920 merged to main | Base commit: main after PR #920 | Branch: task/1119-sm-go-statemachine
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the package `go/internal/statemachine` holding the twelve round 1 transition tables as plain Go data, and a Python test that fails when a Go table and its Python table differ. Nothing calls the Go package yet; it only saves re-deriving each table when its domain is ported.

This is not a fix brief: it adds three new files and changes no existing file's behaviour, so there is no failing-first step.

## 2. Context

Rules that apply: AGENTS.md hard rule 4 (no new dependency: the Go file imports only `sort`, the test only `sort` and `testing`; the Python test only `re`, `pathlib`, `pytest` and `app` modules), rule 5 (nothing here touches SQL). Language rule of docs/plans/explicit-state-machines-rounds-2-4.md: shared logic that must outlive the Python app is written in Go.

Go module path (`go/go.mod`): `github.com/jsfpechar-ops/jsfpecharoperations/go`, `go 1.25.0`. The new package is `github.com/jsfpechar-ops/jsfpecharoperations/go/internal/statemachine`. Existing small packages (`go/internal/secure`, `go/internal/validation`) start with a package doc comment and no license header; they use stdlib `testing` only, tests in the same package (`package secure`), no testify. Follow that.

CI (`.github/workflows/ci.yml`, step "Format, vet, test and build the Go module", `working-directory: go`):

```
test -z "$(gofmt -l .)"
go vet ./...
go test ./... -count=1
go build ./cmd/ubyhost-web
```

There is no golangci config. The Go code below is already gofmt-formatted (tabs, aligned map values). Paste it byte for byte; do not retype it and do not re-align anything.

### The twelve tables (read from the code on PR #920)

Key = `table.column`. Python shape: S = dict of sets, T = dict of tuples. "None key" means the Python dict has a `None` key meaning "no row yet" (the INSERT); the Go table spells it as `"<none>"`. No table has NULL as a state, and none has `None` as a target.

| Machine key | Python table | Shape | None key | States (rows) |
|---|---|---|---|---|
| `ad_click.send_state` | `meta_capi.SEND_TRANSITIONS` | S | yes: `None: {"pending"}` | 6 + none |
| `billing_account.status` | `billing.TRANSITIONS` | S | no | 6 |
| `cleaning_code.state` | `cleaning_codes.TRANSITIONS` | S | no | 10 |
| `door_code.state` | `door_codes.TRANSITIONS` | S | no | 9 |
| `email_outbox.state` | `mail.OUTBOX_TRANSITIONS` | S | no | 6 |
| `guest.submit_state` | `reporting.TRANSITIONS` | S | no (a new row starts pending or not_required, not a move) | 5 |
| `guide_import.status` | `guest_guide_import.IMPORT_TRANSITIONS` | S | no | 6 |
| `payment_request.status` | `payment_request._TRANSITIONS` | S | no | 6 |
| `push_outbox.state` | `push.PUSH_TRANSITIONS` | S | no | 3 |
| `reservation_claim.state` | `claim.TRANSITIONS` | S | yes: `None: {UNCLAIMED}` | 3 + none |
| `site_booking.status` | `booking_site._TRANSITIONS` | S | no | 7 |
| `submission.state` | `reporting.SUBMISSION_TRANSITIONS` | T | yes: `None: ("running",)` | `running` + none |

Facts the files below rely on:

- Many Python tables spell states with constants (`PENDING`, `ISSUING`, `UNCLAIMED`); the parity test imports the real tables, so it sees strings.
- Terminal states are empty sets in Python (`"sent": set()`) and an empty row in Go (`"sent": {},`).
- `submission.state` is the one table whose targets have no row of their own (`ok`, `error`, ... are targets of `running` only). Python is left as it is; the Go test lists those six targets in `terminalOnly`, which is the "documented terminal" case.
- Self-moves are real moves: `cleaning_code.state` lists `active -> active` and `revoke_pending -> revoke_pending`; `reservation_claim.state` lists `unclaimed`, `provisional`, `claimed` to themselves. `Allowed` returns true for them exactly where listed, and false elsewhere (for example `guest.submit_state` `pending -> pending`).
- Names are the DB table and column each pin test uses (`tests/test_sm_*.py`). `billing_account.status` is the column written by `billing.set_status` (`UPDATE billing_account SET status = ?`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/statemachine/tables.go` | create | the tables, `NoRow`, `Allowed`, `Machines` |
| `go/internal/statemachine/tables_test.go` | create | unit tests for `Allowed`, `Machines`, table shape |
| `App/tests/test_sm_go_parity.py` | create | Python parity test, parses `tables.go` as text |

No other file may change. `docs/context/test-map.md` and `docs/context/architecture.md` are done by the orchestrator (§5); do not edit them.

## 4. Steps

1. Check PR #920 is in your base: `ls App/tests/test_sm_site_booking.py go/internal/secure/signer.go 2>&1 | tail -30`. Expected: both paths listed. Either missing: STOP (§8).
2. Check the packages do not exist: `ls go/internal/statemachine App/tests/test_sm_go_parity.py 2>&1 | tail -30`. Expected: both "No such file or directory". Anything else: STOP.
3. Create `go/internal/statemachine/tables.go` with exactly this content (tabs for indentation; do not change spacing):

```go
// Package statemachine holds the state-transition tables of the Python app
// (round 1 of docs/plans/explicit-state-machines.md) as Go data, so that no
// table has to be re-derived when a domain is ported to Go.
//
// Nothing calls this package yet. App/tests/test_sm_go_parity.py parses this
// file as text and fails when a table here differs from its Python table.
// Change a table in both places in the same PR.
//
// Layout the parity test depends on (keep it, gofmt aligns the values):
//
//	"table.column": {                    one machine, opened on its own line
//		"from": {"to1", "to2"},          one row per line, sorted, double quotes
//		"end": {},                       a state with no way out is an empty row
//	},                                   the machine is closed with a tab then "},"
package statemachine

import "sort"

// NoRow is the "from" state of a move that creates the row (the INSERT), and
// the Python None key. It is never a "to" state. The tables spell it as the
// literal "<none>"; TestNoRowMatchesTables keeps the two in step. No machine
// has a NULL state: a NULL column is reported as NoRow by the caller.
const NoRow = "<none>"

// Tables maps "table.column" to from-state to the sorted list of states the
// code may move to. Every state a machine can hold is a key of its machine,
// so a state with no way out is a key with an empty list.
var Tables = map[string]map[string][]string{
	"ad_click.send_state": {
		"<none>":    {"pending"},
		"expired":   {},
		"failed":    {},
		"pending":   {"expired", "sending", "withdrawn"},
		"sending":   {"failed", "pending", "sent", "withdrawn"},
		"sent":      {},
		"withdrawn": {},
	},
	"billing_account.status": {
		"active":        {"canceling", "overdue"},
		"canceling":     {"active", "paused"},
		"overdue":       {"active", "paused"},
		"paused":        {"active"},
		"trial_pending": {"trialing"},
		"trialing":      {"active", "paused"},
	},
	"cleaning_code.state": {
		"active":         {"active", "detached", "revoke_pending", "revoked"},
		"detached":       {},
		"failed":         {"retrying", "revoke_pending"},
		"issuing":        {"active", "failed", "retrying", "revoke_pending"},
		"pending":        {"issuing", "revoke_pending", "revoked"},
		"retrying":       {"issuing", "revoke_pending"},
		"revoke_failed":  {"revoke_pending"},
		"revoke_pending": {"revoke_pending", "revoking"},
		"revoked":        {"revoke_pending"},
		"revoking":       {"revoke_failed", "revoke_pending", "revoked"},
	},
	"door_code.state": {
		"expired":        {},
		"failed":         {},
		"issued":         {"expired", "revoke_pending"},
		"issuing":        {"expired", "failed", "issued", "pending", "retrying"},
		"pending":        {"issuing", "revoked"},
		"retrying":       {"issuing", "revoked"},
		"revoke_failed":  {"issued"},
		"revoke_pending": {"issued", "revoke_failed", "revoked"},
		"revoked":        {},
	},
	"email_outbox.state": {
		"bounced":    {},
		"complained": {},
		"failed":     {},
		"queued":     {"failed", "sending"},
		"sending":    {"failed", "queued", "sent"},
		"sent":       {},
	},
	"guest.submit_state": {
		"blocked":      {"error", "not_required", "pending", "sent"},
		"error":        {"blocked", "not_required", "pending", "sent"},
		"not_required": {"blocked", "error", "pending", "sent"},
		"pending":      {"blocked", "error", "not_required", "sent"},
		"sent":         {"blocked", "error", "pending"},
	},
	"guide_import.status": {
		"done":    {"expired", "failed", "used"},
		"expired": {},
		"failed":  {},
		"queued":  {"failed", "running"},
		"running": {"done", "failed"},
		"used":    {},
	},
	"payment_request.status": {
		"awaiting_payment": {"cancelled", "expired", "paid"},
		"cancelled":        {"paid"},
		"draft":            {"cancelled", "sent"},
		"expired":          {"paid"},
		"paid":             {},
		"sent":             {"awaiting_payment", "cancelled", "expired", "paid"},
	},
	"push_outbox.state": {
		"failed": {},
		"queued": {"failed", "sent"},
		"sent":   {},
	},
	"reservation_claim.state": {
		"<none>":      {"unclaimed"},
		"claimed":     {"claimed", "unclaimed"},
		"provisional": {"claimed", "provisional", "unclaimed"},
		"unclaimed":   {"provisional", "unclaimed"},
	},
	"site_booking.status": {
		"cancelled":      {"refunded"},
		"clash_refunded": {},
		"expired":        {"cancelled", "clash_refunded", "paid"},
		"paid":           {"cancelled", "clash_refunded", "refunded"},
		"pending":        {"clash_refunded", "expired", "paid"},
		"refunded":       {},
		"requested":      {"cancelled", "expired", "paid"},
	},
	"submission.state": {
		"<none>":  {"running"},
		"running": {"error", "ok", "ok_duplicate", "outcome_unknown", "partial", "transport_error"},
	},
}

// Machines returns the machine names ("table.column"), sorted.
func Machines() []string {
	names := make([]string, 0, len(Tables))
	for name := range Tables {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Allowed reports whether machine lists the move from to to. Pass NoRow as
// from for the INSERT that creates the row. An unknown machine or from state
// is not allowed. A move to the same state is allowed only where the table
// lists it.
func Allowed(machine, from, to string) bool {
	for _, next := range Tables[machine][from] {
		if next == to {
			return true
		}
	}
	return false
}
```

   Command: `cd go && gofmt -l internal/statemachine 2>&1 | tail -30`. Expected: no output.
4. Create `go/internal/statemachine/tables_test.go` with exactly this content:

```go
package statemachine

import (
	"sort"
	"testing"
)

func TestAllowed(t *testing.T) {
	cases := []struct {
		machine, from, to string
		want              bool
	}{
		{"guest.submit_state", "pending", "sent", true},
		{"guest.submit_state", "sent", "not_required", false},
		{"guest.submit_state", "pending", "pending", false},
		{"submission.state", NoRow, "running", true},
		{"submission.state", "running", "ok", true},
		{"submission.state", "ok", "running", false},
		{"submission.state", NoRow, "ok", false},
		{"reservation_claim.state", "claimed", "claimed", true},
		{"reservation_claim.state", "claimed", "provisional", false},
		{"push_outbox.state", "sent", "failed", false},
		{"guide_import.status", "done", "used", true},
		{"no_such.machine", "a", "b", false},
		{"guest.submit_state", "no_such_state", "sent", false},
		{"guest.submit_state", "", "pending", false},
	}
	for _, c := range cases {
		if got := Allowed(c.machine, c.from, c.to); got != c.want {
			t.Errorf("Allowed(%q, %q, %q) = %v, want %v", c.machine, c.from, c.to, got, c.want)
		}
	}
}

func TestMachines(t *testing.T) {
	names := Machines()
	if len(names) != 12 {
		t.Fatalf("Machines() has %d names, want 12: %v", len(names), names)
	}
	if !sort.StringsAreSorted(names) {
		t.Errorf("Machines() is not sorted: %v", names)
	}
	for _, name := range names {
		if _, ok := Tables[name]; !ok {
			t.Errorf("Machines() lists %q, which is not in Tables", name)
		}
	}
}

// terminalOnly lists the targets that have no row because the Python table
// leaves them out: submission.state ends in one of reporting.
// TERMINAL_SUBMISSION_STATES and nothing moves it again.
var terminalOnly = map[string][]string{
	"submission.state": {"error", "ok", "ok_duplicate", "outcome_unknown", "partial", "transport_error"},
}

func isTerminalOnly(machine, state string) bool {
	for _, s := range terminalOnly[machine] {
		if s == state {
			return true
		}
	}
	return false
}

// Every state a machine can move to is itself a row of that machine, or is
// listed in terminalOnly. A state with no way out is otherwise a row with an
// empty list. NoRow is only ever a "from".
func TestEveryTargetIsARow(t *testing.T) {
	for _, machine := range Machines() {
		table := Tables[machine]
		for from, targets := range table {
			for _, to := range targets {
				if to == NoRow {
					t.Errorf("%s: %q lists NoRow as a target", machine, from)
				}
				if _, ok := table[to]; !ok && !isTerminalOnly(machine, to) {
					t.Errorf("%s: %q -> %q, but %q is not a row or a listed terminal", machine, from, to, to)
				}
			}
		}
	}
}

func TestRowsAreSortedAndUnique(t *testing.T) {
	for _, machine := range Machines() {
		for from, targets := range Tables[machine] {
			for i := 1; i < len(targets); i++ {
				if targets[i-1] >= targets[i] {
					t.Errorf("%s: row %q is not sorted and unique: %v", machine, from, targets)
					break
				}
			}
		}
	}
}

// The tables write NoRow as a literal; a machine that starts from an INSERT
// must use exactly the constant, and no table may use any other spelling.
func TestNoRowMatchesTables(t *testing.T) {
	inserts := []string{"ad_click.send_state", "reservation_claim.state", "submission.state"}
	for _, machine := range inserts {
		if _, ok := Tables[machine][NoRow]; !ok {
			t.Errorf("%s has no NoRow row", machine)
		}
	}
	for _, machine := range Machines() {
		for from := range Tables[machine] {
			if from == "" || (from != NoRow && from[0] == '<') {
				t.Errorf("%s: row %q looks like a sentinel but is not NoRow", machine, from)
			}
		}
	}
}
```

   Command: `cd go && gofmt -l internal/statemachine && go vet ./internal/statemachine/ && go test ./internal/statemachine/ -count=1 2>&1 | tail -30`. Expected: `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/statemachine`.
5. Create `App/tests/test_sm_go_parity.py` with exactly this content:

```python
"""1119: every Python transition table equals its Go twin in go/internal/statemachine/tables.go.

The Go file is read as text, never compiled. Its layout is fixed (see the
package comment there): one machine per `"table.column": {` line, one row per
line as `"from": {"to1", "to2"},`, the machine closed by `},`. A table changed
in one language and not the other fails here with the machine and the pair.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import (
    billing,
    booking_site,
    claim,
    cleaning_codes,
    door_codes,
    guest_guide_import,
    mail,
    meta_capi,
    payment_request,
    push,
    reporting,
)

APP = Path(__file__).resolve().parents[1]
TABLES_GO = APP.parent / "go" / "internal" / "statemachine" / "tables.go"

NO_ROW = "<none>"

# "table.column": the Python table. None keys (claim, meta_capi, submission)
# are the Go NoRow. Sets and tuples are compared as sets.
PYTHON_TABLES = {
    "ad_click.send_state": meta_capi.SEND_TRANSITIONS,
    "billing_account.status": billing.TRANSITIONS,
    "cleaning_code.state": cleaning_codes.TRANSITIONS,
    "door_code.state": door_codes.TRANSITIONS,
    "email_outbox.state": mail.OUTBOX_TRANSITIONS,
    "guest.submit_state": reporting.TRANSITIONS,
    "guide_import.status": guest_guide_import.IMPORT_TRANSITIONS,
    "payment_request.status": payment_request._TRANSITIONS,
    "push_outbox.state": push.PUSH_TRANSITIONS,
    "reservation_claim.state": claim.TRANSITIONS,
    "site_booking.status": booking_site._TRANSITIONS,
    "submission.state": reporting.SUBMISSION_TRANSITIONS,
}

MACHINE_RE = re.compile(r'^\t"([a-z_]+\.[a-z_]+)": \{$')
ROW_RE = re.compile(r'^\t\t"([^"]+)":\s+\{(.*)\},$')
CLOSE = "\t},"
STATE_RE = re.compile(r'"([^"]*)"')


def parse_go_tables() -> dict:
    """{machine: {from_state: set(to_states)}} from tables.go, plain line scan."""
    lines = TABLES_GO.read_text(encoding="utf-8").splitlines()
    start = lines.index("var Tables = map[string]map[string][]string{")
    tables: dict = {}
    machine = None
    for number, line in enumerate(lines[start + 1:], start + 2):
        if line == "}":
            assert machine is None, f"tables.go:{number}: machine {machine} is not closed"
            return tables
        if machine is None:
            found = MACHINE_RE.match(line)
            assert found, f"tables.go:{number}: expected a machine line, got {line!r}"
            machine = found.group(1)
            assert machine not in tables, f"tables.go:{number}: machine {machine} listed twice"
            tables[machine] = {}
        elif line == CLOSE:
            machine = None
        else:
            found = ROW_RE.match(line)
            assert found, f"tables.go:{number}: expected a row line in {machine}, got {line!r}"
            source = found.group(1)
            assert source not in tables[machine], f"tables.go:{number}: {machine} row {source!r} listed twice"
            tables[machine][source] = set(STATE_RE.findall(found.group(2)))
    raise AssertionError("tables.go: the closing '}' of Tables was not found")


def python_rows(table: dict) -> dict:
    return {(NO_ROW if source is None else source): set(targets) for source, targets in table.items()}


def test_go_has_exactly_the_python_machines():
    go = parse_go_tables()
    assert set(go) == set(PYTHON_TABLES), (
        f"machines only in Go: {sorted(set(go) - set(PYTHON_TABLES))}; "
        f"machines only in Python: {sorted(set(PYTHON_TABLES) - set(go))}"
    )


@pytest.mark.parametrize("machine", sorted(PYTHON_TABLES))
def test_machine_matches_go(machine):
    go = parse_go_tables().get(machine)
    assert go is not None, f"{machine}: not in tables.go"
    py = python_rows(PYTHON_TABLES[machine])
    py_pairs = {(a, b) for a, targets in py.items() for b in targets}
    go_pairs = {(a, b) for a, targets in go.items() for b in targets}
    missing_in_go = sorted(py_pairs - go_pairs)
    extra_in_go = sorted(go_pairs - py_pairs)
    assert not missing_in_go and not extra_in_go, (
        f"{machine}: Python and Go differ. "
        f"In Python only (add to tables.go): {missing_in_go}. "
        f"In Go only (add to the Python table, or remove from tables.go): {extra_in_go}."
    )
    assert set(py) == set(go), (
        f"{machine}: rows differ. In Python only: {sorted(set(py) - set(go))}. "
        f"In Go only: {sorted(set(go) - set(py))}."
    )


def test_go_no_row_constant_is_the_literal_used_in_tables():
    text = TABLES_GO.read_text(encoding="utf-8")
    assert f'const NoRow = "{NO_ROW}"' in text
```

   Command, from `App/`: `.venv/bin/python -m pytest tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30`. Expected: `14 passed`.
6. Prove the test can fail (do not commit this): in `go/internal/statemachine/tables.go` change the line `"paused":        {"active"},` to `"paused":        {"active", "trialing"},`, run the command of step 5. Expected: 1 failed, with a message that starts `billing_account.status: Python and Go differ.` and contains `[('paused', 'trialing')]`. Then edit the line back to its original text (do not use `git checkout`; if you committed in step 3 you may use it), and run step 3's gofmt command and step 5's command again. Expected: no gofmt output, `14 passed`.
7. Context lint, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: exit 0, no new error.
8. Commit with the message `1119 steps 1 to 7`, write the report (§9).

## 5. Do not touch

- Everything under `App/app/`, every existing test, every existing Go file, `.github/`, `go/go.mod`, `go/go.sum`.
- No caller: do not import `statemachine` from any other package. Dead code is intended for this brief.
- Orchestrator does after merge, not you: (a) `docs/context/architecture.md` Go row; (b) a `docs/context/test-map.md` row; (c) a `[workflow]` or decisions line if wanted. Do not edit these.
- AGENTS.md hard rules that apply: 3 (no secrets or guest data: none here), 4 (no dependency), 8 (never push to main; the owner merges).

## 6. Commands

From the repo root:

```
cd go && gofmt -l . 2>&1 | tail -30
cd go && go vet ./... 2>&1 | tail -30
cd go && go test ./internal/statemachine/ -count=1 2>&1 | tail -30
```

From `App/`:

```
.venv/bin/python -m pytest tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

The test-map has no row for these files; the rows above are the whole set. Do not run `go test ./...` for the whole module (needs Postgres in CI) and do not run the full Python suite.

## 7. Acceptance

- [ ] `git status --short` shows exactly the three files of §3 (plus `docs/tasks/1119-report.md`).
- [ ] `gofmt -l .` in `go/` prints nothing; `go vet ./...` prints nothing.
- [ ] `go test ./internal/statemachine/ -count=1` prints `ok`.
- [ ] `pytest tests/test_sm_go_parity.py` prints `14 passed`.
- [ ] Step 6 showed one failure naming `billing_account.status` and the pair, and was reverted.
- [ ] `grep -rn 'internal/statemachine' go --include=*.go | grep -v '^go/internal/statemachine' | tail -30` prints nothing (no caller).
- [ ] Context lint exits 0.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or path in step 1 or 2 is not as stated;
- a test fails twice;
- the parity test fails on an unmutated tree (a Python table on main differs from the one in this brief: report the machine and pair it prints, do not edit a Python table to make it pass);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed (`go.mod` must not change);
- a file outside §3 needs a change;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1119-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Low risk, new files only, no caller. Read in full: `go/internal/statemachine/tables.go` and `App/tests/test_sm_go_parity.py`. The only judgement call is the machine keys (`table.column`); check them against the pin tests `App/tests/test_sm_*.py`. Orchestrator after merge, exact edits:

1. `docs/context/architecture.md`, the `Go port (G1)` row: replace the text `, `go/internal/schema/` (goose files and pending state) |` with `, `go/internal/schema/` (goose files and pending state), `go/internal/statemachine/` (round 1 transition tables as Go data; `App/tests/test_sm_go_parity.py` keeps them equal to Python) |`.
2. `docs/context/test-map.md`, new row: `| State machine tables (Python or Go) | `test_sm_*.py` and, from `go/`, `go test ./internal/statemachine/ -count=1` |`. The existing rows do not cover `test_sm_*.py`.

## Owner steps

1. Open the PR the executor made and wait for CI to go green (the Go job runs gofmt, vet and tests; the Python job runs the parity test).
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>`. Nothing changes on the server: no caller uses the package.
