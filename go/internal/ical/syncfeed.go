package ical

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// feedCompletenessThreshold is FEED_COMPLETENESS_THRESHOLD (icalsync.py 114).
const feedCompletenessThreshold = 0.5

var dtstampLine = regexp.MustCompile(`(?im)^DTSTAMP[;:].*\n?`)

// BodyDigest is body_digest (icalsync.py 155-158): the hash of the feed with
// line endings normalised and DTSTAMP lines removed.
func BodyDigest(text string) string {
	normalised := dtstampLine.ReplaceAllString(strings.ReplaceAll(text, "\r\n", "\n"), "")
	sum := sha256.Sum256([]byte(normalised))
	return hex.EncodeToString(sum[:])
}

// nz is a nullable text column as a string; NULL and empty both read as "".
func nz(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// trustedForSkip is _trusted_for_skip (icalsync.py 168-174).
func trustedForSkip(feed Feed) bool {
	return nz(feed.LastStatus) == "ok" && nz(feed.BodySHA256) != ""
}

// validatorValues is _validator_values (icalsync.py 186-192).
func validatorValues(f Fetched) map[string]any {
	vals := map[string]any{}
	if f.ETag != "" {
		vals["etag"] = f.ETag
	}
	if f.LastModified != "" {
		vals["last_modified"] = f.LastModified
	}
	return vals
}

// downloadFeed is _download (icalsync.py 177-185): validators are sent only
// when the feed may skip and at least one is stored.
func downloadFeed(ctx context.Context, feed Feed, opt FetchOptions) (Fetched, error) {
	if trustedForSkip(feed) {
		etag, lastModified := nz(feed.ETag), nz(feed.LastModified)
		if etag != "" || lastModified != "" {
			return Fetch(ctx, feed.URL, etag, lastModified, opt)
		}
	}
	return Fetch(ctx, feed.URL, "", "", opt)
}

// updateRow writes the given columns of one row. Column names are fixed in
// this package, so they are placed in the SQL directly.
func updateRow(ctx context.Context, pool *pgxpool.Pool, table string, id int64, cols map[string]any) error {
	keys := make([]string, 0, len(cols))
	for k := range cols {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	sets := make([]string, len(keys))
	args := make([]any, 0, len(keys)+1)
	for i, k := range keys {
		sets[i] = fmt.Sprintf("%s = $%d", k, i+1)
		args = append(args, cols[k])
	}
	args = append(args, id)
	_, err := pool.Exec(ctx,
		fmt.Sprintf("UPDATE %s SET %s WHERE id = $%d", table, strings.Join(sets, ", "), len(keys)+1),
		args...)
	return err
}

func anyStr(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// sameValue compares a stored nullable column with a payload value, NULL-safe.
func sameValue(stored *string, v any) bool {
	if v == nil {
		return stored == nil
	}
	s, ok := v.(string)
	return ok && stored != nil && *stored == s
}

// stayRow is the reservation columns sync_feed compares and writes.
type stayRow struct {
	ID             int64
	Status         string
	DateFrom       string
	DateTo         string
	Summary        *string
	ReservationURL *string
	PhoneLast4     *string
	GuestEmail     *string
	FeedID         *string
}

func loadStay(ctx context.Context, pool *pgxpool.Pool, id int64) (stayRow, error) {
	var s stayRow
	err := pool.QueryRow(ctx,
		`SELECT id, status, date_from, date_to, summary, reservation_url, phone_last4,
		        guest_email, ical_feed_id::text
		   FROM reservation WHERE id = $1`, id).Scan(
		&s.ID, &s.Status, &s.DateFrom, &s.DateTo, &s.Summary, &s.ReservationURL,
		&s.PhoneLast4, &s.GuestEmail, &s.FeedID)
	return s, err
}

func countGuests(ctx context.Context, pool *pgxpool.Pool, reservationID int64, state string) (int64, error) {
	var n int64
	err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND submit_state = $2`,
		reservationID, state).Scan(&n)
	return n, err
}

// feedIncompleteCopy is the en host_i18n text for notification.feed_incomplete
// (host_i18n.py 8196-8197).
func feedIncompleteCopy(property string) (string, string) {
	return fmt.Sprintf("%s: your calendar link sent almost no bookings.", property),
		"We kept all your stays, so nothing was cancelled. Check that the calendar link is still right before the next sync."
}

// failFeedSync records a fetch or parse error and returns it in the stats, as
// Python does. The Go error is reserved for database failures.
func failFeedSync(ctx context.Context, pool *pgxpool.Pool, feed Feed, cause error, stats SyncStats) (SyncStats, error) {
	if err := recordFeedFailure(ctx, pool, feed, cause); err != nil {
		return stats, err
	}
	stats.Error = cause.Error()
	return stats, nil
}

// SyncFeed is sync_feed (icalsync.py 664-953). A non-nil icsText replaces the
// download, as Python's ics_text does.
func SyncFeed(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	feed Feed, opt FetchOptions, icsText *string) (SyncStats, error) {
	now := ubyport.UTCNow()
	stats := SyncStats{Outcome: "changed"}

	var fetched Fetched
	var text string
	if icsText != nil {
		text = *icsText
	} else {
		f, err := downloadFeed(ctx, feed, opt)
		if err != nil {
			return failFeedSync(ctx, pool, feed, err, stats)
		}
		fetched = f
		if f.NotModified {
			// 304: only the check is recorded; last_sync_at keeps the last read.
			vals := validatorValues(f)
			vals["last_checked_at"] = now
			if err := updateRow(ctx, pool, "ical_feed", feed.ID, vals); err != nil {
				return stats, err
			}
			stats.Outcome = "not_modified"
			return stats, nil
		}
		text = f.Text
	}
	digest := BodyDigest(text)
	if trustedForSkip(feed) && digest == nz(feed.BodySHA256) {
		vals := validatorValues(fetched)
		vals["last_checked_at"] = now
		if err := updateRow(ctx, pool, "ical_feed", feed.ID, vals); err != nil {
			return stats, err
		}
		stats.Outcome = "unchanged"
		return stats, nil
	}
	events, err := ParseEvents(text)
	if err != nil {
		return failFeedSync(ctx, pool, feed, err, stats)
	}
	// Written with the status at the end, so a half-finished read is never
	// mistaken for a good one to skip next time.
	read := validatorValues(fetched)
	read["last_checked_at"] = now
	read["body_sha256"] = digest

	if err := ubyport.ResolveAlert(ctx, pool, fmt.Sprintf("feed_error:%d", feed.ID)); err != nil {
		return stats, err
	}
	platform := PlatformOf(feed.URL, text)
	seen := map[string]bool{}
	handled := map[string]bool{}
	var duplicateUIDs, recurringUIDs []string
	deferredInFlight := false

	for _, ev := range events {
		if handled[ev.UID] {
			// The first event of a UID wins; the host is told (F6).
			duplicateUIDs = append(duplicateUIDs, ev.UID)
			continue
		}
		handled[ev.UID] = true
		if ev.IsBlock {
			stats.BlocksSkipped++
			blocked, found, err := selectReservation(ctx, pool, feed.ApartmentID, ev.UID)
			if err != nil {
				return stats, err
			}
			if found && blocked.Status == "active" {
				// F13: a block counts only as proof the stay still exists.
				seen[ev.UID] = true
				log.Printf("ical_block_summary_kept_existing_stay apartment_id=%d reservation_id=%d",
					feed.ApartmentID, blocked.ID)
			}
			continue
		}
		if ev.IsCancelled {
			if err := cancelExistingStay(ctx, pool, getenv, feed.ApartmentID, ev.UID, &stats); err != nil {
				return stats, err
			}
			continue
		}
		seen[ev.UID] = true
		if ev.Recurring {
			recurringUIDs = append(recurringUIDs, ev.UID)
		}
		summary := ev.Summary
		if summary == "" {
			summary = ev.NameHint
		}
		payload := map[string]any{
			"date_from":       ev.DateFrom,
			"date_to":         ev.DateTo,
			"summary":         nilIfEmpty(summary),
			"reservation_url": anyStr(ev.ReservationURL),
			"phone_last4":     anyStr(ev.PhoneLast4),
			"ical_feed_id":    strconv.FormatInt(feed.ID, 10),
		}

		ref, found, err := existingReservation(ctx, pool, feed.ApartmentID, ev)
		if err != nil {
			return stats, err
		}
		if !found {
			if _, err := pool.Exec(ctx,
				`INSERT INTO reservation (apartment_id, ical_feed_id, source, uid, date_from, date_to,
				   summary, reservation_url, phone_last4, guest_email, status, created_at, updated_at)
				 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active', $11, $11)`,
				feed.ApartmentID, feed.ID, platform, ev.UID, ev.DateFrom, ev.DateTo,
				payload["summary"], payload["reservation_url"], payload["phone_last4"],
				anyStr(ev.GuestEmail), now); err != nil {
				return stats, err
			}
			stats.Created++
			continue
		}
		s, err := loadStay(ctx, pool, ref.ID)
		if err != nil {
			return stats, err
		}
		// A host decision to ignore a range is never undone by a re-sync.
		if s.Status == "ignored" {
			continue
		}
		datesChanged := s.DateFrom != ev.DateFrom || s.DateTo != ev.DateTo
		if datesChanged {
			inFlight, err := sendInFlight(ctx, pool, s.ID)
			if err != nil {
				return stats, err
			}
			if inFlight {
				// Keep the stored window until the send is resolved (F-in-flight).
				payload["date_from"] = s.DateFrom
				payload["date_to"] = s.DateTo
				datesChanged = false
				deferredInFlight = true
				log.Printf("ical_dates_deferred_in_flight apartment_id=%d reservation_id=%d stored=%s..%s calendar=%s..%s",
					feed.ApartmentID, s.ID, s.DateFrom, s.DateTo, ev.DateFrom, ev.DateTo)
			}
		}
		stored := map[string]*string{
			"date_from":       &s.DateFrom,
			"date_to":         &s.DateTo,
			"summary":         s.Summary,
			"reservation_url": s.ReservationURL,
			"phone_last4":     s.PhoneLast4,
			"ical_feed_id":    s.FeedID,
		}
		changed := map[string]any{}
		for k, v := range payload {
			if !sameValue(stored[k], v) {
				changed[k] = v
			}
		}
		if s.Status == "cancelled" {
			changed["status"] = "active"
		}
		if len(changed) > 0 {
			changed["updated_at"] = now
			if err := updateRow(ctx, pool, "reservation", s.ID, changed); err != nil {
				return stats, err
			}
			stats.Updated++
		}
		if s.Status == "cancelled" {
			// The stay is back: reopen guest access that the cancellation closed.
			ok, err := reopenGuestAccess(ctx, pool, s.ID)
			if err != nil {
				return stats, err
			}
			if ok {
				log.Printf("ical_revival_reopened_guest_access apartment_id=%d reservation_id=%d",
					feed.ApartmentID, s.ID)
			}
		}
		if datesChanged {
			moved, err := fitUnsentGuestWindows(ctx, pool, s.ID, feed.ApartmentID, ev.DateFrom, ev.DateTo)
			if err != nil {
				return stats, err
			}
			if moved > 0 {
				log.Printf("ical_dates_moved_guests apartment_id=%d reservation_id=%d guests=%d",
					feed.ApartmentID, s.ID, moved)
			}
			reported, err := countGuests(ctx, pool, s.ID, guestSent)
			if err != nil {
				return stats, err
			}
			if reported > 0 {
				// F5: a filed stay keeps its filed dates; only the host can decide.
				aid, rid := feed.ApartmentID, s.ID
				if err := ubyport.RaiseAlert(ctx, pool, "warning", "moved_after_report",
					fmt.Sprintf("A stay reported to the police for %s to %s has moved in the calendar to %s to %s.",
						s.DateFrom, s.DateTo, ev.DateFrom, ev.DateTo),
					fmt.Sprintf("%d filed guest record(s) still carry the old dates. Check the booking, correct the guest's dates and resend.", reported),
					fmt.Sprintf("moved_after_report:%d", s.ID), &aid, &rid, nil, nil); err != nil {
					return stats, err
				}
				log.Printf("ical_moved_after_report apartment_id=%d reservation_id=%d guests=%d",
					feed.ApartmentID, s.ID, reported)
			}
		}
		if ev.GuestEmail != nil && *ev.GuestEmail != "" && nz(s.GuestEmail) == "" {
			if err := updateRow(ctx, pool, "reservation", s.ID, map[string]any{"guest_email": *ev.GuestEmail}); err != nil {
				return stats, err
			}
		}
	}

	if err := reportImportLimits(ctx, pool, feed, duplicateUIDs, recurringUIDs, events); err != nil {
		return stats, err
	}

	// A future stay that has vanished from the feed was cancelled upstream.
	// Past stays are left alone: they may already be reported to the police.
	cutoff := time.Now().In(prague).Format(dateLayout)
	rows, err := pool.Query(ctx,
		`SELECT id, uid, date_from FROM reservation
		  WHERE apartment_id = $1 AND ical_feed_id = $2 AND status = 'active' AND date_from >= $3`,
		feed.ApartmentID, feed.ID, cutoff)
	if err != nil {
		return stats, err
	}
	var candidates []reservationRow
	for rows.Next() {
		var r reservationRow
		if err := rows.Scan(&r.ID, &r.UID, &r.DateFrom); err != nil {
			rows.Close()
			return stats, err
		}
		candidates = append(candidates, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return stats, err
	}

	// F-completeness: a feed returning a fraction of the stored stays is more
	// likely broken than cancelling nine guests at once, so nothing is cancelled.
	matched := map[string]bool{}
	for _, r := range candidates {
		if seen[r.UID] {
			matched[r.UID] = true
		}
	}
	if len(candidates) > 0 && float64(len(matched)) < feedCompletenessThreshold*float64(len(candidates)) {
		vals := map[string]any{"last_sync_at": now, "last_status": "suspect", "last_error": nil}
		for k, v := range read {
			vals[k] = v
		}
		if err := updateRow(ctx, pool, "ical_feed", feed.ID, vals); err != nil {
			return stats, err
		}
		title, reason := feedIncompleteCopy(feedName(feed))
		aid := feed.ApartmentID
		if err := ubyport.RaiseAlert(ctx, pool, "warning", "feed_incomplete", title, reason,
			fmt.Sprintf("feed_incomplete:%d", feed.ID), &aid, nil, nil, nil); err != nil {
			return stats, err
		}
		log.Printf("ical_incomplete_feed_retained apartment_id=%d feed_id=%d retained_stays=%d returned_events=%d matched_stays=%d",
			feed.ApartmentID, feed.ID, len(candidates), len(seen), len(matched))
		return stats, nil
	}
	if err := ubyport.ResolveAlert(ctx, pool, fmt.Sprintf("feed_incomplete:%d", feed.ID)); err != nil {
		return stats, err
	}
	for _, r := range candidates {
		if seen[r.UID] {
			continue
		}
		reported, err := countGuests(ctx, pool, r.ID, guestSent)
		if err != nil {
			return stats, err
		}
		if reported > 0 {
			aid, rid := feed.ApartmentID, r.ID
			if err := ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_after_report",
				fmt.Sprintf("A stay from %s disappeared from the calendar after it had already been reported to the police.", r.DateFrom),
				"Check whether the booking was cancelled or merely moved.",
				fmt.Sprintf("cancelled_after_report:%d", r.ID), &aid, &rid, nil,
				ubyport.AlertParams{"date": r.DateFrom, "variant": "disappeared"}); err != nil {
				return stats, err
			}
			continue
		}
		if err := updateRow(ctx, pool, "reservation", r.ID, map[string]any{"status": "cancelled", "updated_at": now}); err != nil {
			return stats, err
		}
		if err := expireOnCancel(ctx, pool, r.ID); err != nil {
			return stats, err
		}
		if err := warnIfGuestsRegistered(ctx, pool, getenv,
			reservationRow{ID: r.ID, DateFrom: r.DateFrom}, feed.ApartmentID, "disappeared"); err != nil {
			return stats, err
		}
		stats.Cancelled++
	}

	feedUpdate := map[string]any{"last_sync_at": now, "last_status": "ok", "last_error": nil}
	for k, v := range read {
		feedUpdate[k] = v
	}
	if deferredInFlight {
		// Do not store the digest or validators: the next poll must reconcile
		// again once the send is resolved, or the date move is lost.
		delete(feedUpdate, "body_sha256")
		delete(feedUpdate, "etag")
		delete(feedUpdate, "last_modified")
	}
	if err := updateRow(ctx, pool, "ical_feed", feed.ID, feedUpdate); err != nil {
		return stats, err
	}
	return stats, nil
}
