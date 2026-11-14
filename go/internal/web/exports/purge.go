package exports

// Brief 1609: POST /settings/purge-expired (exports.purge_expired_records),
// the Settings button that deletes what the retention schedule no longer
// covers for the signed-in workspace. It deletes data: the steps are exactly
// Python's, in Python's order, each one the Go port that its own golden pins
// (retention.RunAs, photosweep.PurgeStalePhotos, photosweep.PurgeSubmissionPayloads).

import (
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/photosweep"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention"
)

// purgeParts is the confirmation of purge_expired_records: the non-zero
// counts in Python's order and wording (English in every language, as there).
func purgeParts(guests, photos, envelopes, invoices int) string {
	var parts []string
	if guests > 0 {
		parts = append(parts, fmt.Sprintf("%d guest record(s) past the retention period", guests))
	}
	if photos > 0 {
		parts = append(parts, fmt.Sprintf("%d passport image(s) no longer needed", photos))
	}
	if envelopes > 0 {
		parts = append(parts, fmt.Sprintf("%d submission envelope(s) no longer needed", envelopes))
	}
	if invoices > 0 {
		parts = append(parts, fmt.Sprintf("%d invoice(s) past the retention period", invoices))
	}
	return strings.Join(parts, " and ")
}

// countOf is summary["counts"].get(name, 0).
func countOf(s retention.Summary, name string) int {
	for _, c := range s.Counts {
		if c.Name == name {
			return c.Count
		}
	}
	return 0
}

// PurgeExpiredHandler is exports.purge_expired_records:
//
//  1. retention.run(claim.prague_today(), dry_run=False, owner_user_id=owner):
//     every owner-scoped retention step, for real whatever
//     UBYHOST_RETENTION_AUTOPURGE says (the button forces it);
//  2. passport_photos.purge_stale(owner_user_id=owner);
//  3. reporting.purge_submission_payloads(owner_user_id=owner);
//
// then a 303 to /settings with what was deleted. A failed step is a 500 after
// the steps before it, as the Python exception is. Stricter than Python: with
// UBYHOST_DATA_DIR unset it deletes nothing and answers 500 (Python would
// look for photos under its default directory).
func PurgeExpiredHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		h, at, ok := d.beginPost(w, r)
		if !ok {
			return
		}
		if _, ok := requireOwner(w, h); !ok {
			return
		}
		owner := h.Workspace.ID
		dataDir := getenv("UBYHOST_DATA_DIR")
		if dataDir == "" {
			serverError(w, errors.New("purge-expired: UBYHOST_DATA_DIR is not set; nothing deleted"))
			return
		}
		cfg, err := retention.ConfigFromEnv(func(k string) (string, bool) {
			v := getenv(k)
			return v, v != ""
		})
		if err != nil {
			serverError(w, err)
			return
		}
		cfg.DryRun = false
		cfg.DataDir = dataDir
		actor := retention.Actor{UserID: h.Account.ID, Username: h.Account.Username, OwnerUserID: &owner}
		if h.Impersonating {
			id := h.Account.ID
			actor.ImpersonatorID = &id
		}
		ctx := r.Context()
		sum, err := retention.RunAs(ctx, pool, cfg, deadlines.LocalNow(at), at, &owner, &actor)
		if err != nil {
			serverError(w, err)
			return
		}
		photos, err := photosweep.PurgeStalePhotos(ctx, pool, dataDir, owner, at.Local(), at)
		if err != nil {
			serverError(w, err)
			return
		}
		envelopes, err := photosweep.PurgeSubmissionPayloads(ctx, pool, owner, at, actor)
		if err != nil {
			serverError(w, err)
			return
		}
		parts := purgeParts(countOf(sum, "guests"), photos, envelopes, countOf(sum, "invoices"))
		if parts == "" {
			hostweb.Back(w, r, "/settings", flash(r, "flash.settings.nothing_to_purge", nil), hostweb.Flash{})
			return
		}
		hostweb.Back(w, r, "/settings", flash(r, "flash.settings.purged", map[string]any{"parts": parts}), hostweb.Flash{})
	}
}
