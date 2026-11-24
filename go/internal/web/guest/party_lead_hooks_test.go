package guest

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// recordingHooks records completion-hook calls in order (brief 2066 step 5).
type recordingHooks struct {
	calls []string
}

func (h *recordingHooks) OnRegistrationComplete(_ context.Context, resID int64) {
	h.calls = append(h.calls, fmt.Sprintf("on:%d", resID))
}

func (h *recordingHooks) MaybeNotifyCompletion(_ context.Context, resID, aptID int64, force bool) error {
	h.calls = append(h.calls, fmt.Sprintf("notify:%d:%d:%t", resID, aptID, force))
	return nil
}

// seedLeadStay inserts a host, an apartment and a reservation declaring two guests.
func seedLeadStay(t *testing.T, pool *pgxpool.Pool, offset int64) (aptID, resID int64) {
	t.Helper()
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	aptID = time.Now().UnixNano()%8000000000 + offset
	userID := aptID
	resID = aptID + 1
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("lh%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, fmt.Sprintf("leadhooks%d", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, 2, $6, $6)`, resID, aptID, fmt.Sprintf("lead-%d", resID), "2026-06-10", "2026-06-12", stamp)
	t.Cleanup(func() {
		bg := context.Background()
		_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
		_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
		_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
	})
	return aptID, resID
}

func leadDeps(pool *pgxpool.Pool, live bool, hooks CompletionHooks) partyDeps {
	liveVal := "0"
	if live {
		liveVal = "1"
	}
	return partyDeps{
		pool:   pool,
		getenv: func(k string) string {
			if k == "UBYHOST_HEADCOUNT_LEAD_LIVE" {
				return liveVal
			}
			return os.Getenv(k)
		},
		now:   func() time.Time { return time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC) },
		hooks: hooks,
	}
}

// The lead-in handler calls afterLeadChange only for lowered or restored codes.
// These tests call changeByLead and then that same branch.
func TestLeadLoweredAndRestoredRunCompletionHooks(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	aptID, resID := seedLeadStay(t, pool, 9100000)
	h := &recordingHooks{}
	d := leadDeps(pool, true, h)
	ctx := context.Background()

	code, err := d.changeByLead(ctx, resID, 1, 2)
	if err != nil || code != codeLowered {
		t.Fatalf("lower: code %q err %v", code, err)
	}
	if code == codeLowered || code == codeRestored {
		d.afterLeadChange(ctx, aptID, resID)
	}
	want := []string{fmt.Sprintf("on:%d", resID), fmt.Sprintf("notify:%d:%d:false", resID, aptID)}
	if fmt.Sprint(h.calls) != fmt.Sprint(want) {
		t.Fatalf("lowered hook calls %v want %v", h.calls, want)
	}

	h.calls = nil
	code, err = d.changeByLead(ctx, resID, 2, 1)
	if err != nil || code != codeRestored {
		t.Fatalf("restore: code %q err %v", code, err)
	}
	d.afterLeadChange(ctx, aptID, resID)
	if fmt.Sprint(h.calls) != fmt.Sprint(want) {
		t.Fatalf("restored hook calls %v want %v", h.calls, want)
	}
}

func TestLeadUnchangedCountRunsNoHooks(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	_, resID := seedLeadStay(t, pool, 9200000)
	h := &recordingHooks{}
	d := leadDeps(pool, true, h)
	code, err := d.changeByLead(context.Background(), resID, 2, 2)
	if err != nil || code != codeUnchanged {
		t.Fatalf("unchanged: code %q err %v", code, err)
	}
	if len(h.calls) != 0 {
		t.Fatalf("unchanged must not call hooks: %v", h.calls)
	}
}

func TestLeadFeatureOffRunsNoHooks(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	_, resID := seedLeadStay(t, pool, 9300000)
	h := &recordingHooks{}
	d := leadDeps(pool, false, h)
	code, err := d.changeByLead(context.Background(), resID, 1, 2)
	if err != nil || code != codeFeatureOff {
		t.Fatalf("feature off: code %q err %v", code, err)
	}
	if len(h.calls) != 0 {
		t.Fatalf("feature off must not call hooks: %v", h.calls)
	}
}

func TestAfterLeadChangeNilHooksDoesNotPanic(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	aptID, resID := seedLeadStay(t, pool, 9400000)
	d := leadDeps(pool, true, nil)
	d.afterLeadChange(context.Background(), aptID, resID)
}
