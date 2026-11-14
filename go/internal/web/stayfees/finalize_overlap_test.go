package stayfees

import (
	"context"
	"testing"
)

// A live quarterly filing that contains the month: sealing the month is refused.
func TestFinalizeOverlap(t *testing.T) {
	g := newFinalizeRig(t, true)
	if _, err := g.pool.Exec(context.Background(), `INSERT INTO stay_fee_filing (apartment_id, period_key, version, cadence,
		rate_czk, liable_days, exempt_days, total_due_czk, total_collected_czk, created_at)
		VALUES (1, '2026-Q3', 1, 'quarterly', 20, 1, 0, 20, 20, '2026-10-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	before := g.wrote()
	_, _, errText := finalizeAnswer(t, g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1")))
	if errText == "" {
		t.Fatal("overlapping month was sealed")
	}
	if after := g.wrote(); after != before {
		t.Errorf("rows written: %v -> %v", before, after)
	}
	if n := g.count(`SELECT COUNT(*) FROM stay_fee_filing WHERE apartment_id = 1 AND period_key = '2026-09'`); n != 0 {
		t.Errorf("month filing exists: %d", n)
	}
}
