package doorcleaning

import (
	"context"
	"testing"
)

type eventRow struct {
	apt, revision, overridden int64
	scheduled, sourceDate     string
	state                     string
}

func (w *world) event(reservationID int64) eventRow {
	w.t.Helper()
	var e eventRow
	err := w.pool.QueryRow(context.Background(),
		"SELECT apartment_id, revision, overridden, scheduled_date, source_date, state "+
			"FROM cleaning_event WHERE source_reservation_id = $1", reservationID).
		Scan(&e.apt, &e.revision, &e.overridden, &e.scheduled, &e.sourceDate, &e.state)
	if err != nil {
		w.t.Fatal(err)
	}
	return e
}

func (w *world) eventTotal() int64 {
	w.t.Helper()
	var n int64
	if err := w.pool.QueryRow(context.Background(), "SELECT COUNT(*) FROM cleaning_event").Scan(&n); err != nil {
		w.t.Fatal(err)
	}
	return n
}

func reconcileOnce(t *testing.T, w *world) int {
	t.Helper()
	n, err := Reconcile(context.Background(), w.pool, w.clock)
	if err != nil {
		t.Fatalf("Reconcile: %v", err)
	}
	return n
}

func TestReconcileCreatesOnceAndIsIdempotent(t *testing.T) {
	w := newWorld(t)
	r := w.reservation(w.apt, "uid-1", "2026-11-10", "2026-11-16", "manual", "active")

	if n := reconcileOnce(t, w); n != 1 {
		t.Fatalf("first pass changed %d, want 1", n)
	}
	e := w.event(r)
	if e.apt != w.apt || e.scheduled != "2026-11-16" || e.sourceDate != "2026-11-16" ||
		e.state != "scheduled" || e.revision != 1 || e.overridden != 0 {
		t.Fatalf("event = %+v", e)
	}
	if n := reconcileOnce(t, w); n != 0 {
		t.Fatalf("second pass changed %d, want 0 (idempotent)", n)
	}
}

func TestReconcileSkipsIneligibleStays(t *testing.T) {
	w := newWorld(t)
	w.reservation(w.apt, "demo", "2026-11-10", "2026-11-16", "demo", "active")
	archived := w.reservation(w.apt, "archived", "2026-11-10", "2026-11-16", "manual", "active")
	w.exec("UPDATE reservation SET archived_at = $1 WHERE id = $2", iso(testStart), archived)
	w.reservation(w.apt, "cancelled", "2026-11-10", "2026-11-16", "manual", "cancelled")
	w.reservation(w.apt, "old", "2026-09-01", "2026-10-01", "manual", "active")
	inactive := w.apartment("Invented Flat Idle", "202", 0)
	w.reservation(inactive, "idle", "2026-11-10", "2026-11-16", "manual", "active")

	if n := reconcileOnce(t, w); n != 0 {
		t.Fatalf("changed %d, want 0", n)
	}
	if total := w.eventTotal(); total != 0 {
		t.Fatalf("events = %d, want 0", total)
	}
}

func TestReconcileMovesUnpinnedEndDateAndKeepsOverride(t *testing.T) {
	w := newWorld(t)
	r1 := w.reservation(w.apt, "uid-1", "2026-11-10", "2026-11-16", "manual", "active")
	r2 := w.reservation(w.apt, "uid-2", "2026-11-18", "2026-11-20", "manual", "active")
	if n := reconcileOnce(t, w); n != 2 {
		t.Fatalf("create changed %d, want 2", n)
	}
	// The host pinned r2's cleaning to 21 November; the booking end moves to 22 November.
	w.exec("UPDATE cleaning_event SET overridden = 1, scheduled_date = '2026-11-21' WHERE source_reservation_id = $1", r2)
	w.exec("UPDATE reservation SET date_to = '2026-11-17' WHERE id = $1", r1)
	w.exec("UPDATE reservation SET date_to = '2026-11-22' WHERE id = $1", r2)

	if n := reconcileOnce(t, w); n != 2 {
		t.Fatalf("date change changed %d, want 2", n)
	}
	e1 := w.event(r1)
	if e1.scheduled != "2026-11-17" || e1.sourceDate != "2026-11-17" || e1.revision != 2 {
		t.Fatalf("unpinned event = %+v", e1)
	}
	e2 := w.event(r2)
	if e2.scheduled != "2026-11-21" || e2.sourceDate != "2026-11-22" || e2.revision != 2 || e2.overridden != 1 {
		t.Fatalf("pinned event = %+v", e2)
	}
}

func TestReconcileCancelRestoreAndDismissal(t *testing.T) {
	w := newWorld(t)
	r1 := w.reservation(w.apt, "uid-1", "2026-11-10", "2026-11-16", "manual", "active")
	r2 := w.reservation(w.apt, "uid-2", "2026-11-18", "2026-11-20", "manual", "active")
	reconcileOnce(t, w)
	w.exec("UPDATE cleaning_event SET state = 'dismissed' WHERE source_reservation_id = $1", r2)

	// Both bookings are cancelled. Only the scheduled event is marked; the dismissal stays.
	w.exec("UPDATE reservation SET status = 'cancelled' WHERE id IN ($1, $2)", r1, r2)
	if n := reconcileOnce(t, w); n != 1 {
		t.Fatalf("cancel changed %d, want 1", n)
	}
	if s := w.event(r1).state; s != "source_cancelled" {
		t.Fatalf("r1 state = %q, want source_cancelled", s)
	}
	if s := w.event(r2).state; s != "dismissed" {
		t.Fatalf("r2 state = %q, want dismissed (a dismissal survives cancellation)", s)
	}

	// Both bookings come back. The cancelled event is scheduled again; the dismissal is not.
	w.exec("UPDATE reservation SET status = 'active' WHERE id IN ($1, $2)", r1, r2)
	if n := reconcileOnce(t, w); n != 1 {
		t.Fatalf("restore changed %d, want 1", n)
	}
	if s := w.event(r1).state; s != "scheduled" {
		t.Fatalf("r1 state after restore = %q, want scheduled", s)
	}
	if s := w.event(r2).state; s != "dismissed" {
		t.Fatalf("r2 state after restore = %q, want dismissed", s)
	}
}
