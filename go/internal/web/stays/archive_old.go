package stays

import (
	"context"
	_ "embed"
	"fmt"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed comfy_i18n.json
var comfyStaysJSON []byte

func init() {
	extra := hostweb.Load(comfyStaysJSON)
	for lang, kv := range extra {
		if catalog[lang] == nil {
			catalog[lang] = map[string]string{}
		}
		for k, v := range kv {
			catalog[lang][k] = v
		}
	}
}

// CountOldUnfilled counts owner's active, non-archived stays that checked out
// more than 7 days before today and have zero non-archived guest rows.
func CountOldUnfilled(ctx context.Context, pool *pgxpool.Pool, owner int64, today time.Time) (int, error) {
	cutoff := today.AddDate(0, 0, -7).Format("2006-01-02")
	var n int
	err := pool.QueryRow(ctx,
		`SELECT COUNT(*)
		 FROM reservation r
		 JOIN apartment a ON a.id = r.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1
		   AND a.archived_at IS NULL
		   AND r.archived_at IS NULL
		   AND r.status = 'active'
		   AND r.date_to < $2
		   AND NOT EXISTS (
		     SELECT 1 FROM guest g
		     WHERE g.reservation_id = r.id AND g.archived_at IS NULL
		   )`, owner, cutoff).Scan(&n)
	return n, err
}

// RegisterArchiveOld mounts POST /reservations/archive-old-unfilled.
func RegisterArchiveOld(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := postDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /reservations/archive-old-unfilled", wrap("/reservations/archive-old-unfilled", ArchiveOldUnfilledHandler(d)))
}

// ArchiveOldUnfilledHandler archives active stays checked out >7 days ago with 0 non-archived guests.
func ArchiveOldUnfilledHandler(d postDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		ctx := r.Context()
		today := pragueToday(c.at)
		cutoff := today.AddDate(0, 0, -7).Format("2006-01-02")
		stamp := isoStamp(c.at)
		tag, err := c.pool.Exec(ctx,
			`UPDATE reservation r
			 SET archived_at = $1, updated_at = $1
			 FROM apartment a
			 WHERE r.apartment_id = a.id
			   AND a.owner_user_id IS NOT DISTINCT FROM $2
			   AND a.archived_at IS NULL
			   AND r.archived_at IS NULL
			   AND r.status = 'active'
			   AND r.date_to < $3
			   AND NOT EXISTS (
			     SELECT 1 FROM guest g
			     WHERE g.reservation_id = r.id AND g.archived_at IS NULL
			   )`, stamp, c.owner, cutoff)
		if err != nil {
			serverError(w, err)
			return
		}
		count := tag.RowsAffected()
		if count > 0 {
			if err := c.editAudit(ctx, "reservations_archived_old_unfilled", fmt.Sprintf("count=%d cutoff=%s", count, cutoff)); err != nil {
				serverError(w, err)
				return
			}
			c.back("/reservations", c.flash("flash.stays.archived_old_unfilled", map[string]any{"count": count}), hostweb.Flash{})
			return
		}
		c.back("/reservations", c.flash("flash.stays.archived_old_unfilled.none", nil), hostweb.Flash{})
	}
}
