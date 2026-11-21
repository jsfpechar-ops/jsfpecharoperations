package guest

import (
	"context"
	"fmt"
	"testing"
	"time"

)

func TestRateCountWindowed(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	scope := "pin_fail"
	key := fmt.Sprintf("k-%d", time.Now().UnixNano())
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	old := now.Add(-20 * time.Minute)
	if err := rateRecord(ctx, pool, scope, key, old); err != nil {
		t.Fatal(err)
	}
	if err := rateRecord(ctx, pool, scope, key, now); err != nil {
		t.Fatal(err)
	}
	n, err := rateCount(ctx, pool, scope, key, pinWindowSec, now)
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("count %d, want 1 (stale event outside window)", n)
	}
}