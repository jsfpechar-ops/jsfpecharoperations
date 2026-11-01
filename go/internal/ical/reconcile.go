package ical

import (
	"context"
	"errors"
	"fmt"
	"log"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// This file ports the reconcile helpers that sync_feed in App/app/icalsync.py
// uses. Nothing calls them yet: the sync itself is ported in a later slice.

// Feed is the part of an ical_feed row the reconcile helpers read.
type Feed struct {
	ID          int64
	ApartmentID int64
	OwnName     *string
	Label       *string
}

// SyncStats counts what one sync did. Only Cancelled is ported so far.
type SyncStats struct {
	Cancelled int
}

// reservationRow holds the reservation columns the sync reads.
type reservationRow struct {
	ID       int64
	Status   string
	DateFrom string
	DateTo   string
	UID      string
}

const (
	syntheticPrefix = "synthetic-"
	dateLayout      = "2006-01-02"
	guestSent       = "sent" // reporting.SENT
)

var syntheticDigestRe = regexp.MustCompile(`^[0-9a-f]{16}$`)

// syntheticDigest is _synthetic_digest (icalsync.py 249-253).
func syntheticDigest(uid string) string {
	if len(uid) < len(syntheticPrefix) {
		return ""
	}
	digest := strings.Split(uid[len(syntheticPrefix):], "-")[0]
	if !syntheticDigestRe.MatchString(digest) {
		return ""
	}
	return digest
}

// syntheticAliases is _synthetic_aliases (icalsync.py 280-294).
func syntheticAliases(uid, legacy, dateFrom string) []string {
	candidates := []string{legacy}
	if digest := syntheticDigest(uid); digest != "" {
		bare := syntheticPrefix + digest
		candidates = append(candidates, bare, bare+"-"+dateFrom)
	}
	var out []string
	for _, c := range candidates {
		if c != "" && c != uid {
			out = append(out, c)
		}
	}
	return out
}

// legacySyntheticUID is _legacy_synthetic_uid (icalsync.py 297-299). The
// summary is cut at 20 code points, not bytes.
func legacySyntheticUID(dateFrom, dateTo, summary string) string {
	runes := []rune(summary)
	if len(runes) > 20 {
		runes = runes[:20]
	}
	return fmt.Sprintf("synthetic-%s-%s-%s", dateFrom, dateTo, string(runes))
}

// epochSeconds is Python's time.time().
func epochSeconds() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}

// liveClaimAfter is the claimed_at threshold below which a claim is stale.
func liveClaimAfter() float64 {
	return epochSeconds() - ubyport.SubmissionClaimTTL.Seconds()
}

// exists reports whether the query returns at least one row.
func exists(ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) (bool, error) {
	var n int
	err := pool.QueryRow(ctx, sql, args...).Scan(&n)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

// selectReservation returns the stored stay with this UID, if any.
func selectReservation(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, uid string) (reservationRow, bool, error) {
	var r reservationRow
	err := pool.QueryRow(ctx,
		`SELECT id, status, date_from, date_to, uid FROM reservation WHERE apartment_id = $1 AND uid = $2`,
		apartmentID, uid).Scan(&r.ID, &r.Status, &r.DateFrom, &r.DateTo, &r.UID)
	if errors.Is(err, pgx.ErrNoRows) {
		return reservationRow{}, false, nil
	}
	if err != nil {
		return reservationRow{}, false, err
	}
	return r, true, nil
}

// sendInFlight is _send_in_flight (icalsync.py 372-405): true while a live
// claim, or a running or outcome_unknown submission, still covers the stay.
func sendInFlight(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (bool, error) {
	live, err := exists(ctx, pool,
		`SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL AND c.claimed_at >= $2 LIMIT 1`,
		reservationID, liveClaimAfter())
	if err != nil || live {
		return live, err
	}
	return exists(ctx, pool,
		`SELECT 1 FROM guest g JOIN submission s ON s.id = g.submission_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL
		    AND g.submit_state <> $2 AND s.state IN ('running', 'outcome_unknown') LIMIT 1`,
		reservationID, guestSent)
}

// pyStr renders a nullable text column the way Python's str() would.
func pyStr(s *string) string {
	if s == nil {
		return "None"
	}
	return *s
}

func maxDate(a, b time.Time) time.Time {
	if a.After(b) {
		return a
	}
	return b
}

func minDate(a, b time.Time) time.Time {
	if a.Before(b) {
		return a
	}
	return b
}

// fitUnsentGuestWindows is _fit_unsent_guest_windows (icalsync.py 408-466).
// Each guest update is a compare-and-set; an audit row is written only when
// the update changed one row.
func fitUnsentGuestWindows(ctx context.Context, pool *pgxpool.Pool, reservationID, apartmentID int64, newFrom, newTo string) (int, error) {
	newStart, okStart := validation.ParseISODate(newFrom)
	newEnd, okEnd := validation.ParseISODate(newTo)
	if !okStart || !okEnd {
		return 0, nil
	}
	var owner *int64
	err := pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&owner)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return 0, err
	}
	type guestWindow struct {
		id          int64
		stayFrom    *string
		stayTo      *string
		submitState string
	}
	rows, err := pool.Query(ctx,
		`SELECT id, stay_from, stay_to, submit_state FROM guest
		  WHERE reservation_id = $1 AND archived_at IS NULL AND submit_state <> $2`,
		reservationID, guestSent)
	if err != nil {
		return 0, err
	}
	var guests []guestWindow
	for rows.Next() {
		var g guestWindow
		if err := rows.Scan(&g.id, &g.stayFrom, &g.stayTo, &g.submitState); err != nil {
			rows.Close()
			return 0, err
		}
		guests = append(guests, g)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	parseOr := func(s *string, fallback time.Time) time.Time {
		if s != nil {
			if t, ok := validation.ParseISODate(*s); ok {
				return t
			}
		}
		return fallback
	}
	liveAfter := liveClaimAfter()
	moved := 0
	for _, g := range guests {
		sf := parseOr(g.stayFrom, newStart)
		st := parseOr(g.stayTo, newEnd)
		fromT := maxDate(sf, newStart)
		toT := minDate(st, newEnd)
		if !fromT.Before(toT) {
			fromT, toT = newStart, newEnd
		}
		newSF, newST := fromT.Format(dateLayout), toT.Format(dateLayout)
		if g.stayFrom != nil && g.stayTo != nil && *g.stayFrom == newSF && *g.stayTo == newST {
			continue
		}
		oldWindow := pyStr(g.stayFrom) + ".." + pyStr(g.stayTo)
		tag, err := pool.Exec(ctx,
			`UPDATE guest SET stay_from = $1, stay_to = $2, updated_at = $3
			  WHERE id = $4 AND submit_state = $5
			    AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $4 AND claimed_at >= $6)
			    AND (submission_id IS NULL OR NOT EXISTS (
			      SELECT 1 FROM submission WHERE id = guest.submission_id
			        AND state IN ('running', 'outcome_unknown')))`,
			newSF, newST, ubyport.UTCNow(), g.id, g.submitState, liveAfter)
		if err != nil {
			return moved, err
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		detail := fmt.Sprintf("guest=%d reservation=%d was=%s now=%s..%s",
			g.id, reservationID, oldWindow, newSF, newST)
		if err := ubyport.Audit(ctx, pool, "guest_stay_window_fitted", detail, owner); err != nil {
			return moved, err
		}
		moved++
	}
	return moved, nil
}

// warnIfGuestsRegistered is _warn_if_guests_registered (icalsync.py 469-493).
// Mail and push errors are logged and do not fail the caller, as in Python.
func warnIfGuestsRegistered(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	res reservationRow, apartmentID int64, variant string) error {
	var n int64
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL
		  AND submit_state NOT IN ('sent', 'not_required')`, res.ID).Scan(&n); err != nil {
		return err
	}
	if n == 0 {
		return nil
	}
	aid, rid := apartmentID, res.ID
	if err := ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_with_guests",
		fmt.Sprintf("A stay from %s with guest forms was cancelled in the calendar.", res.DateFrom),
		"Nothing will be reported for it. If the booking only moved, set the stay back to Active.",
		fmt.Sprintf("cancelled_with_guests:%d", res.ID), &aid, &rid, nil,
		ubyport.AlertParams{"date": res.DateFrom, "variant": variant}); err != nil {
		return err
	}
	if _, err := ubyport.QueueCancelledWithGuestsMail(ctx, pool, getenv, apartmentID, res.ID, variant); err != nil {
		log.Printf("ical cancelled_with_guests mail not queued reservation_id=%d: %v", res.ID, err)
	}
	if _, err := ubyport.QueueCancelledWithGuestsPush(ctx, pool, getenv, apartmentID, res.ID); err != nil {
		log.Printf("ical cancelled_with_guests push not queued reservation_id=%d: %v", res.ID, err)
	}
	return nil
}

// expireOnCancel is claim.expire_on_cancel (claim.py 705-720). Nothing happens
// when the stay has no claim row.
func expireOnCancel(ctx context.Context, pool *pgxpool.Pool, reservationID int64) error {
	has, err := exists(ctx, pool, `SELECT 1 FROM reservation_claim WHERE reservation_id = $1 LIMIT 1`, reservationID)
	if err != nil || !has {
		return err
	}
	now := ubyport.UTCNow()
	if _, err := pool.Exec(ctx,
		`UPDATE reservation_claim SET token_hash = NULL, guest_access_locked_at = $1,
		   guest_access_reopened_at = NULL, updated_at = $1 WHERE reservation_id = $2`,
		now, reservationID); err != nil {
		return err
	}
	_, err = pool.Exec(ctx,
		`UPDATE email_outbox SET state = 'failed', updated_at = $1
		  WHERE reservation_id = $2 AND state = 'queued'`,
		now, reservationID)
	return err
}

// cancelExistingStay is _cancel_existing_stay (icalsync.py 497-529). A stay
// that already has a sent guest is not cancelled; an alert is raised instead.
func cancelExistingStay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	apartmentID int64, uid string, stats *SyncStats) error {
	res, found, err := selectReservation(ctx, pool, apartmentID, uid)
	if err != nil || !found || res.Status != "active" {
		return err
	}
	today := time.Now().In(prague).Format(dateLayout)
	if res.DateFrom < today {
		return nil
	}
	reported, err := exists(ctx, pool,
		`SELECT 1 FROM guest WHERE reservation_id = $1 AND submit_state = $2 LIMIT 1`,
		res.ID, guestSent)
	if err != nil {
		return err
	}
	if reported {
		aid, rid := apartmentID, res.ID
		return ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_after_report",
			fmt.Sprintf("A stay from %s was cancelled in the calendar after it had already been reported to the police.", res.DateFrom),
			"Check whether the booking was cancelled or merely moved.",
			fmt.Sprintf("cancelled_after_report:%d", res.ID), &aid, &rid, nil,
			ubyport.AlertParams{"date": res.DateFrom, "variant": "cancelled"})
	}
	if _, err := pool.Exec(ctx,
		`UPDATE reservation SET status = 'cancelled', updated_at = $1 WHERE id = $2`,
		ubyport.UTCNow(), res.ID); err != nil {
		return err
	}
	if err := expireOnCancel(ctx, pool, res.ID); err != nil {
		return err
	}
	if err := warnIfGuestsRegistered(ctx, pool, getenv, res, apartmentID, "cancelled"); err != nil {
		return err
	}
	stats.Cancelled++
	return nil
}

// existingReservation is _existing_reservation (icalsync.py 532-569). A
// pre-W4.6 synthetic row is re-keyed to the new UID when its aliases match.
func existingReservation(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, ev Event) (reservationRow, bool, error) {
	uid := ev.UID
	row, found, err := selectReservation(ctx, pool, apartmentID, uid)
	if err != nil || found || !strings.HasPrefix(uid, syntheticPrefix) {
		return row, found, err
	}
	legacy := legacySyntheticUID(ev.DateFrom, ev.DateTo, ev.Summary)
	for _, candidate := range syntheticAliases(uid, legacy, ev.DateFrom) {
		cand, ok, err := selectReservation(ctx, pool, apartmentID, candidate)
		if err != nil {
			return reservationRow{}, false, err
		}
		if !ok {
			continue
		}
		// An alias other than the dated legacy key must match the dates too.
		if candidate != legacy && (cand.DateFrom != ev.DateFrom || cand.DateTo != ev.DateTo) {
			continue
		}
		if _, err := pool.Exec(ctx,
			`UPDATE reservation SET uid = $1, updated_at = $2 WHERE id = $3`,
			uid, ubyport.UTCNow(), cand.ID); err != nil {
			return reservationRow{}, false, err
		}
		cand.UID = uid
		log.Printf("ical_synthetic_uid_rekeyed apartment_id=%d reservation_id=%d", apartmentID, cand.ID)
		return cand, true, nil
	}
	return reservationRow{}, false, nil
}

// reopenGuestAccess is _reopen_guest_access (icalsync.py 572-588). It reopens
// only a stay whose guest access is locked, and reports whether it did.
func reopenGuestAccess(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (bool, error) {
	var locked *string
	err := pool.QueryRow(ctx,
		`SELECT guest_access_locked_at FROM reservation_claim WHERE reservation_id = $1`,
		reservationID).Scan(&locked)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if locked == nil || *locked == "" {
		return false, nil
	}
	// claim.reopen_guest_access (claim.py 695-702), inlined.
	now := ubyport.UTCNow()
	if _, err := pool.Exec(ctx,
		`UPDATE reservation_claim SET guest_access_locked_at = NULL,
		   guest_access_reopened_at = $1, updated_at = $1 WHERE reservation_id = $2`,
		now, reservationID); err != nil {
		return false, err
	}
	return true, nil
}

// feedName is own_name, else label, else the id; empty strings count as missing.
func feedName(f Feed) string {
	if f.OwnName != nil && *f.OwnName != "" {
		return *f.OwnName
	}
	if f.Label != nil && *f.Label != "" {
		return *f.Label
	}
	return strconv.FormatInt(f.ID, 10)
}

// importLimitCopy is the en host_i18n text for notification.<kind>
// (host_i18n.py 654-657).
func importLimitCopy(kind, property string) (string, string) {
	if kind == "feed_duplicate_uid" {
		return fmt.Sprintf("%s: one booking is listed twice.", property),
			"The calendar returns the same booking ID more than once. Only the first entry of each was imported – check the portal, because one of the two stays may be missing."
	}
	return fmt.Sprintf("%s: a booking repeats.", property),
		"The calendar repeats a booking, but only the first occurrence was imported. Add the other stays by hand."
}

// reportImportLimits is _report_import_limits (icalsync.py 591-628). An empty
// list resolves the alert for that kind; a non-empty one raises it.
func reportImportLimits(ctx context.Context, pool *pgxpool.Pool, feed Feed,
	duplicateUIDs, recurringUIDs []string, events []Event) error {
	summaries := map[string]string{}
	for _, ev := range events {
		summaries[ev.UID] = ev.Summary
	}
	property := feedName(feed)
	kinds := []struct {
		kind string
		uids []string
	}{
		{"feed_duplicate_uid", duplicateUIDs},
		{"feed_recurring_event", recurringUIDs},
	}
	for _, k := range kinds {
		key := fmt.Sprintf("%s:%d", k.kind, feed.ID)
		if len(k.uids) == 0 {
			if err := ubyport.ResolveAlert(ctx, pool, key); err != nil {
				return err
			}
			continue
		}
		title, reason := importLimitCopy(k.kind, property)
		aid := feed.ApartmentID
		if err := ubyport.RaiseAlert(ctx, pool, "warning", k.kind, title, reason, key, &aid, nil, nil, nil); err != nil {
			return err
		}
		var parts []string
		for i, uid := range k.uids {
			if i == 5 {
				break
			}
			s := summaries[uid]
			if s == "" {
				s = uid
			}
			parts = append(parts, s)
		}
		log.Printf("ical_%s apartment_id=%d feed_id=%d count=%d summaries=%s",
			k.kind, feed.ApartmentID, feed.ID, len(k.uids), strings.Join(parts, "; "))
	}
	return nil
}

// recordFeedFailure is _record_feed_failure (icalsync.py 631-661).
func recordFeedFailure(ctx context.Context, pool *pgxpool.Pool, feed Feed, cause error) error {
	now := ubyport.UTCNow()
	msg := cause.Error()
	if _, err := pool.Exec(ctx,
		`UPDATE ical_feed SET last_sync_at = $1, last_checked_at = $1,
		   last_status = 'error', last_error = $2 WHERE id = $3`,
		now, msg, feed.ID); err != nil {
		return err
	}
	name := feedName(feed)
	aid := feed.ApartmentID
	return ubyport.RaiseAlert(ctx, pool, "warning", "feed_error",
		fmt.Sprintf("Calendar '%s' could not be synchronised.", name), msg,
		fmt.Sprintf("feed_error:%d", feed.ID), &aid, nil, nil,
		ubyport.AlertParams{"feed": name, "error": msg})
}
