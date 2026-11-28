package doorcodes

import (
	"context"
	"errors"
	"fmt"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// recFakeLifecycle records the phase-2 calls in order. before runs first in each call, so a test
// can look at the database at that point of the tick.
type recFakeLifecycle struct {
	calls     []string
	cancelErr error
	before    func(call string)
}

func (f *recFakeLifecycle) HandleCancellations(_ context.Context, _ string) error {
	f.calls = append(f.calls, "cancellations")
	if f.before != nil {
		f.before("cancellations")
	}
	return f.cancelErr
}

func (f *recFakeLifecycle) HandleMoves(_ context.Context, _ string) error {
	f.calls = append(f.calls, "moves")
	if f.before != nil {
		f.before("moves")
	}
	return nil
}

type recFakeBudget struct {
	used int64
}

func (b *recFakeBudget) CallsThisMonth(_ context.Context) (int64, error) { return b.used, nil }

type recFakeLocks struct {
	remote  func() (int64, error)
	adjusts int
}

func (l *recFakeLocks) QueryLockTime(_ context.Context, _ int64, _ string) (int64, error) {
	return l.remote()
}

func (l *recFakeLocks) AdjustLockTime(_ context.Context, _ int64, _ string) (int64, error) {
	l.adjusts++
	return 0, nil
}

type recFakeDelayed struct {
	notices []string
	missing []int64
}

func (d *recFakeDelayed) DoorCodeDelayedNotice(_ context.Context, reservationID int64, reason string) error {
	d.notices = append(d.notices, reason)
	return nil
}

func (d *recFakeDelayed) DoorCodeMissing(_ context.Context, reservationID int64) error {
	d.missing = append(d.missing, reservationID)
	return nil
}

// recReconciler wires the fixture's Service with fakes for the phase-2 and the other collaborators.
func recReconciler(f *fixture, lc *recFakeLifecycle) (*Reconciler, *recFakeLocks, *recFakeDelayed) {
	locks := &recFakeLocks{remote: func() (int64, error) { return f.now.UnixMilli(), nil }}
	delayed := &recFakeDelayed{}
	return &Reconciler{
		Svc:         f.svc,
		Lifecycle:   lc,
		Budget:      &recFakeBudget{},
		BudgetLimit: 30000,
		Locks:       locks,
		Delayed:     delayed,
	}, locks, delayed
}

func TestReconcileOrderAndCounters(t *testing.T) {
	f := newFixture(t)
	f.insertReservation("2026-11-16", "2026-11-19") // eligible, no row yet
	issuedBeforeCancel := false
	lc := &recFakeLifecycle{}
	lc.before = func(call string) {
		if call == "cancellations" {
			issuedBeforeCancel = f.row(f.dc).State == StateIssued
		}
	}
	r, locks, _ := recReconciler(f, lc)

	c, err := r.Reconcile(f.ctx)
	if err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	if !reflect.DeepEqual(lc.calls, []string{"cancellations", "moves"}) {
		t.Fatalf("phase-2 calls %v", lc.calls)
	}
	if !issuedBeforeCancel {
		t.Fatal("issuing must finish before the cancellations phase")
	}
	want := ReconcileCounts{Created: 1, Issued: 2, ClockChecked: 1}
	if c != want {
		t.Fatalf("counts %+v, want %+v", c, want)
	}
	if locks.adjusts != 0 {
		t.Fatalf("clock adjusted without drift")
	}
	if len(f.alerts.raised) != 0 {
		t.Fatalf("unexpected alerts: %+v", f.alerts.raised)
	}
}

func TestReconcileDisabledDoesNothing(t *testing.T) {
	f := newFixture(t)
	f.svc.Settings.Enabled = false
	lc := &recFakeLifecycle{}
	r, _, _ := recReconciler(f, lc)
	c, err := r.Reconcile(f.ctx)
	if err != nil || c != (ReconcileCounts{}) || len(lc.calls) != 0 {
		t.Fatalf("disabled: counts=%+v err=%v calls=%v", c, err, lc.calls)
	}
	if got := f.row(f.dc).State; got != StatePending {
		t.Fatalf("state %s, want pending", got)
	}
}

func TestReconcilePhaseFailureContinues(t *testing.T) {
	f := newFixture(t)
	f.exec("UPDATE door_code SET state = $1, valid_to = $2 WHERE id = $3", StateIssued, iso(f.now.Add(-time.Hour)), f.dc)
	lc := &recFakeLifecycle{cancelErr: errors.New("boom")}
	r, _, _ := recReconciler(f, lc)
	c, err := r.Reconcile(f.ctx)
	if err != nil {
		t.Fatalf("a failed phase must not fail the tick: %v", err)
	}
	if !reflect.DeepEqual(lc.calls, []string{"cancellations", "moves"}) {
		t.Fatalf("moves must run after a failed cancellations: %v", lc.calls)
	}
	if c.Expired != 1 {
		t.Fatalf("expired=%d, want 1 (the expiry statement runs after the phase-2 failure)", c.Expired)
	}
}

func TestReconcileMissingLifecycleIsLoggedNotFatal(t *testing.T) {
	f := newFixture(t)
	r, _, _ := recReconciler(f, nil)
	r.Lifecycle = nil
	c, err := r.Reconcile(f.ctx)
	if err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	if c.Issued != 1 {
		t.Fatalf("issue phase must still run: %+v", c)
	}
}

func TestReconcileLeaseExpiresToRetrying(t *testing.T) {
	f := newFixture(t)
	f.exec("UPDATE door_code SET state = $1, claimed_at = $2 WHERE id = $3",
		StateIssuing, iso(f.now.Add(-10*time.Minute)), f.dc)
	r, _, _ := recReconciler(f, &recFakeLifecycle{})
	if _, err := r.Reconcile(f.ctx); err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	d := f.row(f.dc)
	if d.State != StateRetrying || d.ClaimedAt != nil {
		t.Fatalf("state=%s claimed=%v, want retrying with no claim", d.State, d.ClaimedAt)
	}
}

func TestReconcileCountsFailedRows(t *testing.T) {
	f := newFixture(t)
	f.exec("UPDATE door_code SET state = $1 WHERE id = $2", StateFailed, f.dc)
	r, _, _ := recReconciler(f, &recFakeLifecycle{})
	c, err := r.Reconcile(f.ctx)
	if err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	if c.Failed != 1 {
		t.Fatalf("failed=%d, want 1", c.Failed)
	}
}

func TestAlertDelayedNotifiesHostOnce(t *testing.T) {
	f := newFixture(t)
	r, _, delayed := recReconciler(f, &recFakeLifecycle{})
	n, err := r.alertDelayed(f.ctx)
	if err != nil {
		t.Fatalf("alertDelayed: %v", err)
	}
	if n != 1 {
		t.Fatalf("matched %d stays, want 1", n)
	}
	if len(f.alerts.raised) != 1 {
		t.Fatalf("raised %d alerts", len(f.alerts.raised))
	}
	a := f.alerts.raised[0]
	if a.Kind != "door_code_delayed" || a.DedupeKey != fmt.Sprintf("door_code_delayed:%d", f.res) || a.Detail != "reason=waiting" {
		t.Fatalf("alert %+v", a)
	}
	if !reflect.DeepEqual(delayed.notices, []string{"waiting"}) || !reflect.DeepEqual(delayed.missing, []int64{f.res}) {
		t.Fatalf("notices %v missing %v", delayed.notices, delayed.missing)
	}
}

func TestBudgetAlerts(t *testing.T) {
	cases := []struct {
		name  string
		used  int64
		limit int64
		kind  string
		key   string
	}{
		{"95 percent is critical", 29000, 30000, "critical", "ttlock_budget:2026-11:95"},
		{"80 percent is a warning", 25000, 30000, "warning", "ttlock_budget:2026-11:80"},
		{"below 80 percent is quiet", 1000, 30000, "", ""},
		{"zero limit switches the alerts off", 29000, 0, "", ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newFixture(t)
			r, _, _ := recReconciler(f, &recFakeLifecycle{})
			r.Budget = &recFakeBudget{used: tc.used}
			r.BudgetLimit = tc.limit
			if err := r.budgetAlerts(f.ctx); err != nil {
				t.Fatal(err)
			}
			if tc.kind == "" {
				if len(f.alerts.raised) != 0 {
					t.Fatalf("raised %+v", f.alerts.raised)
				}
				return
			}
			if len(f.alerts.raised) != 1 || f.alerts.raised[0].Level != tc.kind || f.alerts.raised[0].DedupeKey != tc.key {
				t.Fatalf("raised %+v, want %s %s", f.alerts.raised, tc.kind, tc.key)
			}
		})
	}
}

func TestCheckLockClocksAdjustsMonthlyAndOnDST(t *testing.T) {
	f := newFixture(t)
	r, locks, _ := recReconciler(f, &recFakeLifecycle{})
	locks.remote = func() (int64, error) { return f.clk.Now().UnixMilli() + 200_000, nil }

	out, err := r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 1 || out.adjusted != 1 || locks.adjusts != 1 {
		t.Fatalf("first check: %+v err=%v adjusts=%d", out, err, locks.adjusts)
	}
	var detail string
	if err := f.svc.Pool.QueryRow(f.ctx,
		"SELECT detail FROM audit WHERE action = 'lock_clock_adjusted' ORDER BY id DESC LIMIT 1").Scan(&detail); err != nil {
		t.Fatal(err)
	}
	if detail != "lock=555 drift_s=200" {
		t.Fatalf("audit detail %q", detail)
	}
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 0 {
		t.Fatalf("second check immediately: %+v err=%v", out, err)
	}
	// Still skipped after 7 days and 29 days (monthly cadence).
	f.clk.t = f.now.Add(7 * 24 * time.Hour)
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 0 {
		t.Fatalf("check at 7 days: %+v err=%v", out, err)
	}
	f.clk.t = f.now.Add(29 * 24 * time.Hour)
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 0 {
		t.Fatalf("check at 29 days: %+v err=%v", out, err)
	}
	// Due at 30 days.
	f.clk.t = f.now.Add(30 * 24 * time.Hour)
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 1 || out.adjusted != 1 {
		t.Fatalf("check at 30 days: %+v err=%v", out, err)
	}
	// Even if checked 5 days earlier, spring-forward (2027-03-28 01:00 UTC) triggers an immediate sweep.
	if err := r.writeSetting(f.ctx, "ttlock_clock_checked:555", "2027-03-23T10:00:00+00:00"); err != nil {
		t.Fatal(err)
	}
	f.clk.t = time.Date(2027, 3, 28, 1, 5, 0, 0, time.UTC)
	locks.remote = func() (int64, error) { return f.clk.Now().UnixMilli() - 3_600_000, nil }
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 1 || out.adjusted != 1 {
		t.Fatalf("post-DST check: %+v err=%v", out, err)
	}
	// Once checked after the transition, the next tick is skipped again.
	f.clk.t = f.clk.t.Add(5 * time.Minute)
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 0 {
		t.Fatalf("second post-DST check: %+v err=%v", out, err)
	}
	f.clk.t = f.now
}

func TestCheckLockClocksRetriesTransientNextTick(t *testing.T) {
	f := newFixture(t)
	r, locks, _ := recReconciler(f, &recFakeLifecycle{})
	// Checked before spring-forward, now 5m after spring-forward, and lock is offline.
	if err := r.writeSetting(f.ctx, "ttlock_clock_checked:555", "2027-03-23T10:00:00+00:00"); err != nil {
		t.Fatal(err)
	}
	f.clk.t = time.Date(2027, 3, 28, 1, 5, 0, 0, time.UTC)
	locks.remote = func() (int64, error) { return 0, &ttlock.TTLockError{Kind: ttlock.KindOffline} }
	out, err := r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 1 {
		t.Fatalf("offline: %+v err=%v", out, err)
	}
	// Backoff holds 5 minutes later even though last_checked is still before the DST transition.
	f.clk.t = f.clk.t.Add(5 * time.Minute)
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 0 {
		t.Fatalf("offline must not be retried at once: %+v err=%v", out, err)
	}
	// Opens 24 hours after the failure and clears retry_after once it succeeds.
	f.clk.t = time.Date(2027, 3, 29, 1, 5, 0, 0, time.UTC)
	locks.remote = func() (int64, error) { return f.clk.Now().UnixMilli(), nil }
	out, err = r.checkLockClocks(f.ctx)
	if err != nil || out.checked != 1 {
		t.Fatalf("offline must be retried one day later: %+v err=%v", out, err)
	}
	retryVal, err := r.readSetting(f.ctx, "ttlock_clock_retry_after:555")
	if err != nil || retryVal != "" {
		t.Fatalf("retry_after should be cleared on success, got %q err=%v", retryVal, err)
	}
	f.clk.t = f.now
}

func TestCheckLockClocksRaisesAlertOnHardErrorAndResolvesOnRecovery(t *testing.T) {
	f := newFixture(t)
	r, locks, _ := recReconciler(f, &recFakeLifecycle{})
	locks.remote = func() (int64, error) { return 0, &ttlock.TTLockError{Kind: ttlock.KindLockSetup} }
	if _, err := r.checkLockClocks(f.ctx); err != nil {
		t.Fatal(err)
	}
	if len(f.alerts.raised) != 1 || f.alerts.raised[0].Kind != "door_code_clock" ||
		f.alerts.raised[0].ApartmentID != f.apt || f.alerts.raised[0].DedupeKey != "door_code_clock:555" {
		t.Fatalf("raised %+v", f.alerts.raised)
	}
	// When the next scheduled check succeeds, the alert is resolved.
	f.clk.t = f.now.Add(30 * 24 * time.Hour)
	locks.remote = func() (int64, error) { return f.clk.Now().UnixMilli(), nil }
	if _, err := r.checkLockClocks(f.ctx); err != nil {
		t.Fatal(err)
	}
	if len(f.alerts.resolved) != 1 || f.alerts.resolved[0] != "door_code_clock:555" {
		t.Fatalf("resolved %+v, want [door_code_clock:555]", f.alerts.resolved)
	}
	f.clk.t = f.now
}

func TestOnRegistrationCompleteIssues(t *testing.T) {
	f := newFixture(t)
	res := f.insertReservation("2026-11-20", "2026-11-22")
	f.svc.OnRegistrationComplete(f.ctx, res)
	var state string
	if err := f.svc.Pool.QueryRow(f.ctx, "SELECT state FROM door_code WHERE reservation_id = $1", res).Scan(&state); err != nil {
		t.Fatal(err)
	}
	if state != StateIssued {
		t.Fatalf("state %s, want issued", state)
	}
}

func TestReconcileCountsTotal(t *testing.T) {
	c := ReconcileCounts{Created: 1, Issued: 2, Failed: 3, Expired: 4, Delayed: 5, ClockChecked: 6, ClockAdjusted: 7}
	if c.Total() != 28 {
		t.Fatalf("total %d", c.Total())
	}
	if clockFloorDiv(-1500, 1000) != -2 || clockFloorDiv(1500, 1000) != 1 {
		t.Fatal("clockFloorDiv must floor like Python //")
	}
	if !strings.Contains(errNoLifecycle.Error(), "lifecycle") {
		t.Fatal("errNoLifecycle text")
	}
}
