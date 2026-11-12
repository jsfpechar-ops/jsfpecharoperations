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
