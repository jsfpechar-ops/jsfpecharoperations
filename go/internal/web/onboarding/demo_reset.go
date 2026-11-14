package onboarding

// POST /demo/reset (brief 1596): routes/onboarding.py reset_demo and
// demo.clear (App/app/demo.py 880-942). It removes only the built-in demo
// dataset of the signed-in workspace: the two demo entities by name, every
// property that carries a demo name or points at a demo entity, the rows that
// hang on those properties, and the passport photo files of their guests.
// Nothing routes here until the owner adds the path to UBYHOST_GO_PATHS.

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// The names demo.seed writes and demo.clear matches on (demo.py 19-22).
const (
	demoEntityName     = "Josef Novák (demo)"
	demoControllerName = "Demo Controller s.r.o."
	demoStudioName     = "Vinohrady Studio (demo)"
	demoLoftName       = "Karlín Loft (demo)"
)

// demoClearTables are the feature rows demo.clear deletes by apartment_id
// before the apartment itself (the cascade does not reach all of them), in
// Python's order.
var demoClearTables = []string{
	"payment_request",
	"stay_fee_adjustment",
	"stay_fee_filing",
	"stay_fee_rate",
	"door_code",
	"cleaning_event",
	"cleaning_property",
	"cleaning_code",
	"property_page",
	"property_slug",
	"property_slug_history",
	"site_booking",
	"booking_hold",
}

// demoPhotoExtensions is passport_photos.ALL_EXTENSIONS (sorted).
var demoPhotoExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

// demoDeletePhoto is passport_photos.delete_photo: every encrypted and legacy
// file name the guest's photo can have under <data dir>/passport_photos (the
// twin of retention.deletePhoto). A name that is not a regular file is left.
func demoDeletePhoto(dataDir string, guestID int64) error {
	dir := filepath.Join(dataDir, "passport_photos")
	for _, ext := range demoPhotoExtensions {
		base := strconv.FormatInt(guestID, 10) + ext
		for _, name := range []string{base + ".enc", base} {
			path := filepath.Join(dir, name)
			info, err := os.Stat(path)
			if errors.Is(err, fs.ErrNotExist) {
				continue
			}
			if err != nil {
				return fmt.Errorf("demo: photo of guest %d not checked: %w", guestID, err)
			}
			if !info.Mode().IsRegular() {
				continue
			}
			if err := os.Remove(path); err != nil {
				return fmt.Errorf("demo: photo of guest %d not removed: %w", guestID, err)
			}
		}
	}
	return nil
}

// errDemoDataDir stops a clear before anything is deleted: the photos of the
// demo guests could not be found, so no row may go either.
var errDemoDataDir = errors.New("demo: UBYHOST_DATA_DIR is not set; nothing deleted")

// demoClear is demo.clear(owner). false means there was no demo to clear
// (no demo entity, or no property that belongs to one). The photo files go
// first, as in Python; the rows then go in one transaction with the audit
// row, so a failed delete leaves every row in place.
func demoClear(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, h *session.Host, at time.Time) (bool, error) {
	owner := h.Workspace.ID
	entityIDs, err := demoIDs(ctx, pool, `SELECT id FROM legal_entity WHERE name IN ($1, $2) AND owner_user_id = $3 ORDER BY id`,
		demoEntityName, demoControllerName, owner)
	if err != nil || len(entityIDs) == 0 {
		return false, err
	}
	apartmentIDs, err := demoIDs(ctx, pool, `SELECT id FROM apartment
WHERE (internal_name IN ($1, $2) OR legal_entity_id = ANY($3) OR data_controller_entity_id = ANY($3))
AND owner_user_id = $4 ORDER BY id`, demoStudioName, demoLoftName, entityIDs, owner)
	if err != nil || len(apartmentIDs) == 0 {
		return false, err
	}
	guestIDs, err := demoIDs(ctx, pool, `SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id
WHERE r.apartment_id = ANY($1) ORDER BY g.id`, apartmentIDs)
	if err != nil {
		return false, err
	}
	if len(guestIDs) > 0 {
		dataDir := getenv("UBYHOST_DATA_DIR")
		if dataDir == "" {
			return false, errDemoDataDir
		}
		for _, id := range guestIDs {
			if err := demoDeletePhoto(dataDir, id); err != nil {
				return false, err
			}
		}
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after a successful commit
	for _, id := range apartmentIDs {
		statements := []string{`DELETE FROM alert WHERE apartment_id = $1`, `DELETE FROM apartment_slug WHERE apartment_id = $1`}
		for _, table := range demoClearTables {
			statements = append(statements, "DELETE FROM "+table+" WHERE apartment_id = $1")
		}
		statements = append(statements, `DELETE FROM apartment WHERE id = $1`)
		for _, sql := range statements {
			if _, err := tx.Exec(ctx, sql, id); err != nil {
				return false, err
			}
		}
	}
	for _, id := range entityIDs {
		if _, err := tx.Exec(ctx, `DELETE FROM legal_entity WHERE id = $1`, id); err != nil {
			return false, err
		}
	}
	var impersonator any
	if h.Impersonating {
		impersonator = h.Account.ID
	}
	if _, err := tx.Exec(ctx, auditSQL, stamp(at), h.Account.Username, "demo_cleared", "", owner, h.Account.ID, impersonator); err != nil {
		return false, err
	}
	return true, tx.Commit(ctx)
}

// demoIDs runs a query that returns one bigint column.
func demoIDs(ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) ([]int64, error) {
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowTo[int64])
}

// demoFlash is admin_helpers.flash: the key's text in the request language.
func demoFlash(r *http.Request, key string) hostweb.Flash {
	return hostweb.Flash{Text: onboardingPageStrings.T(hostweb.Lang(r), key, nil), Key: key}
}

// DemoResetHandler serves POST /demo/reset (routes/onboarding.py reset_demo):
// CSRF, require_login, demo.clear, then a 303 to / with the flash.
func DemoResetHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, ok := guard(w, r, pool, getenv, now)
		if !ok {
			return
		}
		cleared, err := demoClear(r.Context(), pool, getenv, h, now())
		if err != nil {
			serverError(w, err)
			return
		}
		if !cleared {
			hostweb.Back(w, r, "/", hostweb.Flash{}, demoFlash(r, "flash.error.demo_missing"))
			return
		}
		hostweb.Back(w, r, "/", demoFlash(r, "flash.demo.cleared"), hostweb.Flash{})
	}
}
