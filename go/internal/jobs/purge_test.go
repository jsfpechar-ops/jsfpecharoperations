package jobs

import (
	"context"
	"testing"
	"time"
)

func TestPurgeDeletesFinishedRowsByAge(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()

	insert := func(kind string, runAt, doneAt, deadAt any) int64 {
		t.Helper()
		var id int64
		err := pool.QueryRow(ctx,
			`INSERT INTO job (kind, run_at, payload, created_at, done_at, dead_at)
			 VALUES ($1, $2, '{}', $2, $3, $4) RETURNING id`,
			kind, runAt, doneAt, deadAt).Scan(&id)
		if err != nil {
			t.Fatal(err)
		}
		return id
	}

	a := insert("push", Now(-8*24*time.Hour), Now(-8*24*time.Hour), nil)   // done 8 days: deleted
	b := insert("push", Now(-6*24*time.Hour), Now(-6*24*time.Hour), nil)   // done 6 days: kept
	c := insert("mail", Now(-8*24*time.Hour), nil, Now(-8*24*time.Hour))   // dead 8 days: kept
	d := insert("mail", Now(-31*24*time.Hour), nil, Now(-31*24*time.Hour)) // dead 31 days: deleted
	e := insert("submit", Now(-40*24*time.Hour), nil, nil)                 // open 40 days: kept

	removed, err := Purge(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	if removed != 2 {
		t.Fatalf("removed %d rows, want 2", removed)
	}
	want := map[string]bool{"a": false, "b": true, "c": true, "d": false, "e": true}
	ids := map[string]int64{"a": a, "b": b, "c": c, "d": d, "e": e}
	for label, keep := range want {
		var n int
		if err := pool.QueryRow(ctx, "SELECT count(*) FROM job WHERE id = $1", ids[label]).Scan(&n); err != nil {
			t.Fatal(err)
		}
		if (n == 1) != keep {
			t.Errorf("row %s: present=%v, want %v", label, n == 1, keep)
		}
	}
}

func TestPurgeRunsInBatches(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()

	if _, err := pool.Exec(ctx,
		`INSERT INTO job (kind, run_at, payload, created_at, done_at)
		 SELECT 'push', $1, '{}', $1, $1 FROM generate_series(1, $2)`,
		Now(-8*24*time.Hour), PurgeBatch*2+10); err != nil {
		t.Fatal(err)
	}
	removed, err := Purge(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	if removed != PurgeBatch*2+10 {
		t.Fatalf("removed %d rows, want %d", removed, PurgeBatch*2+10)
	}
	var left int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM job").Scan(&left); err != nil {
		t.Fatal(err)
	}
	if left != 0 {
		t.Fatalf("%d rows left, want 0", left)
	}
}
