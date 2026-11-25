package guest

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// An archived apartment must not serve its QR guide: the Python guide_token
// lookup already filters archived_at IS NULL and the Go query must match.
func TestArchivedApartmentQRGuideAnswers404(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		t.Skip("no test database")
	}
	ctx := t.Context()
	aptID := int64(83000000 + time.Now().UnixNano()%1000000)
	tok := fmt.Sprintf("archivedguidetoken%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, '2026-01-01T00:00:00Z') ON CONFLICT DO NOTHING`, aptID, fmt.Sprintf("a%d@example.test", aptID))
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, created_at, guide_token, archived_at)
		VALUES ($1, $1, 'Archived Flat', 'Prague', 1, '2026-01-01T00:00:00Z', $2, '2026-01-02T00:00:00Z')`, aptID, tok)

	mux := http.NewServeMux()
	RegisterGuideView(mux, pool, func(string) string { return "" }, time.Now, func(_ string, f http.HandlerFunc) http.Handler { return f })
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/g/"+tok, nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("archived apartment QR guide = %d, want 404", rec.Code)
	}
}
