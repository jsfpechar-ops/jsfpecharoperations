package doorcodes

import (
	"fmt"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// moveEnv is an issued row whose apartment check-in moved from 14:00 to 15:00, so the stay window
// changed. The clock starts 2026-11-10, five days before the stay, so the priority is normal.
func moveEnv(t *testing.T) *lcEnv {
	t.Helper()
	e := newLcEnv(t)
	e.issued()
	// Issue stored next_attempt_at at the 2026-11-15 clock; the moves start earlier, so clear it,
	// and forget the create call that issue made.
	e.exec("UPDATE door_code SET next_attempt_at = NULL WHERE id = $1", e.dc)
	e.lk.creates = 0
	e.lk.priorities = nil
	e.exec("UPDATE apartment SET checkin_hour = 15 WHERE id = $1", e.apt)
	e.clk.t = time.Date(2026, 11, 10, 10, 0, 0, 0, time.UTC)
	return e
}

// movedWindow is the stay window of moveEnv after the check-in change.
func movedWindow(t *testing.T) (int64, int64) {
	t.Helper()
	startMS, endMS, err := ttlock.StayWindow("2026-11-15", "2026-11-18", 15, 10, 1)
	if err != nil {
		t.Fatal(err)
	}
	return startMS, endMS
}

func TestLcMoveReplacesCodeAndDeletesOld(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "123456", "code-2", nil }
	e.lk.priorities = nil
	mailBefore := len(e.mail.enqueued)
	e.moveTick()

	d := e.row(e.dc)
	wantState(t, d, StateIssued, d.Attempts)
	if derefOr(d.ProviderCodeID, "") != "code-2" || derefOr(d.CodeKind, "") != "random" {
		t.Fatalf("provider=%q kind=%q, want code-2 random", derefOr(d.ProviderCodeID, ""), derefOr(d.CodeKind, ""))
	}
	if got := fmt.Sprint(e.lk.deletes); got != "[code-1]" {
		t.Fatalf("deletes=%s, want [code-1]", got)
	}
	if fmt.Sprint(e.lk.priorities) != "[normal critical]" {
		t.Fatalf("priorities=%v, want create normal then delete critical", e.lk.priorities)
	}
	if !e.audited("door_code_replaced", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_replaced not audited")
	}
	if len(e.alerts.resolved) == 0 || e.alerts.resolved[len(e.alerts.resolved)-1] != fmt.Sprintf("door_code_pin_unverified:%d", e.res) {
		t.Fatalf("pin_unverified alert not resolved: %v", e.alerts.resolved)
	}
	if len(e.mail.enqueued) <= mailBefore {
		t.Fatal("the moved code mail was not queued")
	}
}

func TestLcMovePeriodTakenFallsBackToCustomCode(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "", "", lcRefused(ttlock.KindPeriodTaken, -1026) }
	e.moveTick()
	d := e.row(e.dc)
	if derefOr(d.ProviderCodeID, "") != "custom-1" || derefOr(d.CodeKind, "") != "custom" {
		t.Fatalf("provider=%q kind=%q, want custom-1 custom", derefOr(d.ProviderCodeID, ""), derefOr(d.CodeKind, ""))
	}
	if e.notes.count("period_taken") != 1 {
		t.Fatalf("period_taken notices=%d, want 1", e.notes.count("period_taken"))
	}
	if e.mail.drained == 0 {
		t.Fatal("the mail queue was not drained before the custom code")
	}
	if fmt.Sprint(e.lk.deletes) != "[code-1]" {
		t.Fatalf("deletes=%v, want the old code-1", e.lk.deletes)
	}
}

func TestLcMoveBudgetWaitsSixtyMinutesAndDoesNotRetryEarly(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "", "", lcRefused(ttlock.KindBudget, 0) }
	start := e.clk.t
	e.moveTick()
	d := e.row(e.dc)
	wantLastError(t, d, "budget")
	wantNext(t, d, start.Add(60*time.Minute))
	if derefOr(d.ProviderCodeID, "") != "code-1" {
		t.Fatal("the guest keeps the old code while the move waits")
	}
	e.moveTick()
	if e.lk.creates != 1 {
		t.Fatalf("creates=%d, want 1: the row waits for next_attempt_at", e.lk.creates)
	}
}

func TestLcMovePriorityIsCriticalInsideTwentyFourHours(t *testing.T) {
	e := moveEnv(t)
	e.clk.t = time.Date(2026, 11, 15, 9, 0, 0, 0, time.UTC) // stay starts within 24 hours
	e.lk.priorities = nil
	e.moveTick()
	if len(e.lk.priorities) == 0 || e.lk.priorities[0] != ttlock.PriorityCritical {
		t.Fatalf("priorities=%v, want the create to be critical inside 24 hours", e.lk.priorities)
	}
}

func TestLcMoveDuringStayNoticesWithoutChanging(t *testing.T) {
	e := moveEnv(t)
	e.clk.t = time.Date(2026, 11, 15, 13, 30, 0, 0, time.UTC) // the guest has arrived
	e.moveTick()
	d := e.row(e.dc)
	if derefOr(d.ProviderCodeID, "") != "code-1" || e.lk.creates != 0 {
		t.Fatal("a move during the stay must not create or change a code")
	}
	if e.notes.count("moved_during_stay") != 1 {
		t.Fatalf("moved_during_stay notices=%d, want 1", e.notes.count("moved_during_stay"))
	}
}

func TestLcMovePermissionFailureStopsRetrying(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "", "", lcRefused(ttlock.KindPermission, 10005) }
	e.moveTick()
	d := e.row(e.dc)
	wantLastError(t, d, "permission:10005")
	if e.notes.count("failed") != 1 {
		t.Fatalf("failed notices=%d, want 1", e.notes.count("failed"))
	}
	e.moveTick()
	if e.lk.creates != 1 {
		t.Fatalf("creates=%d, want 1: brief 0037 stops the retry", e.lk.creates)
	}
}

func TestLcMoveLockSetupNoticesOncePerWindow(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "", "", lcRefused(ttlock.KindLockSetup, -1003) }
	start := e.clk.t
	e.moveTick()
	d := e.row(e.dc)
	wantLastError(t, d, "lock_setup:-1003")
	wantNext(t, d, start.Add(60*time.Minute))
	startMS, endMS := movedWindow(t)
	want := fmt.Sprintf("%d-%d", startMS, endMS)
	if len(e.notes.calls) == 0 || e.notes.calls[len(e.notes.calls)-1].Stage != "moved_failed" ||
		e.notes.calls[len(e.notes.calls)-1].Suffix != want {
		t.Fatalf("moved_failed notice with key %q missing: %v", want, e.notes.calls)
	}
}

func TestLcMoveStaleLockSetupFailureIsCleared(t *testing.T) {
	e := moveEnv(t)
	startMS, endMS := movedWindow(t)
	e.exec("UPDATE door_code SET valid_from = $1, valid_to = $2, last_error = 'lock_setup:-1003', "+
		"next_attempt_at = NULL WHERE id = $3", msToISO(startMS), msToISO(endMS), e.dc)
	e.moveTick()
	d := e.row(e.dc)
	if derefOr(d.LastError, "") != "" {
		t.Fatalf("last_error=%q, want cleared: the stay is back on its own window", derefOr(d.LastError, ""))
	}
	if e.lk.creates != 0 {
		t.Fatal("a stale failure must not trigger a new code")
	}
}

func TestLcMoveOldCodeNotDeletedNotifies(t *testing.T) {
	e := moveEnv(t)
	e.lk.create = func(string) (string, string, error) { return "123456", "code-2", nil }
	e.lk.del = func(string) error { return lcRefused(ttlock.KindPermission, 10005) }
	e.moveTick()
	d := e.row(e.dc)
	if derefOr(d.ProviderCodeID, "") != "code-2" || d.State != StateIssued {
		t.Fatalf("state=%s provider=%q, want the new code kept issued", d.State, derefOr(d.ProviderCodeID, ""))
	}
	if !e.audited("door_code_move_old_not_deleted", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_move_old_not_deleted not audited")
	}
	if e.notes.count("moved_not_deleted") != 1 {
		t.Fatalf("moved_not_deleted notices=%d, want 1", e.notes.count("moved_not_deleted"))
	}
}
