package photosweep

// Brief 1609: the two sweep steps the Settings button "delete expired records"
// (exports.purge_expired_records) runs for one workspace after
// retention.run: passport_photos.purge_stale(owner_user_id=owner) and
// reporting.purge_submission_payloads(owner_user_id=owner). They are the
// global steps of files.go and db.go with the owner filter of the Python
// queries; the global sweep does not call them.

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention"
)

// staleOwnerGuestsSQL is the query of passport_photos.purge_stale with its
// "? IS NULL OR a.owner_user_id = ?" filter for one owner.
const staleOwnerGuestsSQL = `SELECT g.id, g.passport_photo_at FROM guest g
	JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE (g.identity_verified_at IS NOT NULL
	OR COALESCE(ubyhost_sqlite_date(g.stay_from), ubyhost_sqlite_date(r.date_from)) <= $1
	OR ubyhost_sqlite_date(g.passport_photo_at) <= $2)
	AND a.owner_user_id = $3
	ORDER BY g.id`

// auditRetentionOwner is db.audit_retention(class, count, cutoff,
// owner_user_id=owner): the owner goes into the detail only.
func auditRetentionOwner(ctx context.Context, pool *pgxpool.Pool, now time.Time, class string, count int, cutoff string, owner int64) error {
	detail := `{"class": ` + pyJSONString(class) + `, "count": ` + strconv.Itoa(count) +
		`, "cutoff": ` + pyJSONString(cutoff) + `, "dry_run": false, "owner_user_id": ` + strconv.FormatInt(owner, 10) + `}`
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail) VALUES ($1, 'system', 'retention_delete', $2)`,
		iso(now), detail)
	return err
}

// PurgeStalePhotos is passport_photos.purge_stale(owner_user_id=owner): the
// passport photos of the owner's guests that are verified, checked in more
// than 7 days before today or uploaded more than 30 days before today are
// deleted and passport_photo_at is cleared. Orphan files belong to no
// workspace and are left for the global sweep. today is the server-local
// date (Python's date.today()). It returns the number of photos removed and
// writes the retention audit line, zero included. dataDir must be writable
// when there is a photo to remove.
func PurgeStalePhotos(ctx context.Context, pool *pgxpool.Pool, dataDir string, owner int64, today, now time.Time) (int, error) {
	dir := photosDir(dataDir)
	day := func(back int) string {
		return time.Date(today.Year(), today.Month(), today.Day()-back, 0, 0, 0, 0, time.UTC).Format("2006-01-02")
	}
	checkin, uploaded := day(photoAfterCheckinDays), day(photoMaxAgeDays)
	rows, err := pool.Query(ctx, staleOwnerGuestsSQL, checkin, uploaded, owner)
	if err != nil {
		return 0, err
	}
	type stale struct {
		id     int64
		marked *string
	}
	var list []stale
	for rows.Next() {
		var s stale
		if err := rows.Scan(&s.id, &s.marked); err != nil {
			rows.Close()
			return 0, err
		}
		list = append(list, s)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	removed := 0
	for _, s := range list {
		id := strconv.FormatInt(s.id, 10)
		has, err := hasPhoto(dir, id)
		if err != nil {
			return removed, err
		}
		if has {
			if err := deletePhoto(dir, id); err != nil {
				return removed, err
			}
			removed++
		}
		// Python: `if row["marked"]`, so an empty string is left as it is.
		if s.marked != nil && *s.marked != "" {
			if _, err := pool.Exec(ctx, `UPDATE guest SET passport_photo_at = NULL WHERE id = $1`, s.id); err != nil {
				return removed, err
			}
		}
	}
	cutoff := "check-in on or before " + checkin + "; upload on or before " + uploaded + "; or verified"
	if err := auditRetentionOwner(ctx, pool, now, "passport_photos", removed, cutoff, owner); err != nil {
		return removed, err
	}
	return removed, nil
}

// PurgeSubmissionPayloads is reporting.purge_submission_payloads(owner_user_id=owner)
// inside a request: the request and response envelopes of the owner's
// settled submissions older than 90 days are blanked. It returns the number
// of rows blanked. The submission_payload_purge row carries actor as
// db.audit does in a request (the username for "host", the workspace and the
// two user ids); the retention line is written on every run, zero included.
func PurgeSubmissionPayloads(ctx context.Context, pool *pgxpool.Pool, owner int64, now time.Time, actor retention.Actor) (int, error) {
	cutoff := iso(now.Add(-submissionPayloadDays * 24 * time.Hour))
	rows, err := pool.Query(ctx,
		`SELECT s.id FROM submission s JOIN apartment a ON a.id = s.apartment_id
		 WHERE s.created_at < $1 AND s.state = ANY($2) AND a.owner_user_id = $3
		 AND (s.request_xml IS NOT NULL OR s.request_xml_enc IS NOT NULL OR s.response_xml IS NOT NULL)
		 ORDER BY s.id`,
		cutoff, terminalSubmissionStates, owner)
	if err != nil {
		return 0, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	if len(ids) == 0 {
		return 0, auditRetentionOwner(ctx, pool, now, "ubyport_xml", 0, cutoff, owner)
	}
	if _, err := pool.Exec(ctx,
		`UPDATE submission SET request_xml = NULL, request_xml_enc = NULL, response_xml = NULL
		 WHERE id = ANY($1)`, ids); err != nil {
		return 0, err
	}
	detail := fmt.Sprintf("blanked the request and response envelope on %d submission(s) older than %d days",
		len(ids), submissionPayloadDays)
	var ownerID, impersonator any
	if actor.OwnerUserID != nil {
		ownerID = *actor.OwnerUserID
	}
	if actor.ImpersonatorID != nil {
		impersonator = *actor.ImpersonatorID
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, $2, 'submission_payload_purge', $3, $4, $5, $6)`,
		iso(now), actor.Username, detail, ownerID, actor.UserID, impersonator); err != nil {
		return 0, err
	}
	if err := auditRetentionOwner(ctx, pool, now, "ubyport_xml", len(ids), cutoff, owner); err != nil {
		return 0, err
	}
	return len(ids), nil
}
