package ical

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

func icsDoc(events ...string) string {
	return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n" + strings.Join(events, "") + "END:VCALENDAR\r\n"
}

func icsEvent(uid, from, to, summary string, extra ...string) string {
	s := "BEGIN:VEVENT\r\nUID:" + uid + "\r\nDTSTART;VALUE=DATE:" + from +
		"\r\nDTEND;VALUE=DATE:" + to + "\r\nSUMMARY:" + summary + "\r\n"
	for _, e := range extra {
		s += e + "\r\n"
	}
	return s + "END:VEVENT\r\n"
}

func newIcalFeed(t *testing.T, pool *pgxpool.Pool, apartmentID int64, url string) Feed {
	t.Helper()
	var id int64
	must(t, pool.QueryRow(context.Background(),
		`INSERT INTO ical_feed (apartment_id, url, created_at) VALUES ($1, $2, $3) RETURNING id`,
		apartmentID, url, ubyport.UTCNow()).Scan(&id))
	return reloadFeed(t, pool, id)
}

func reloadFeed(t *testing.T, pool *pgxpool.Pool, id int64) Feed {
	t.Helper()
	var f Feed
	must(t, pool.QueryRow(context.Background(),
		`SELECT id, apartment_id, url, own_name, label, last_status, body_sha256, etag, last_modified
		   FROM ical_feed WHERE id = $1`, id).Scan(&f.ID, &f.ApartmentID, &f.URL, &f.OwnName,
		&f.Label, &f.LastStatus, &f.BodySHA256, &f.ETag, &f.LastModified))
	return f
}

// seedStay inserts an active stay that came from the feed.
func seedStay(t *testing.T, pool *pgxpool.Pool, apartmentID, feedID int64, uid, from, to string) int64 {
	t.Helper()
	var id int64
	must(t, pool.QueryRow(context.Background(),
		`INSERT INTO reservation (apartment_id, ical_feed_id, source, uid, date_from, date_to,
		   status, created_at, updated_at)
		 VALUES ($1, $2, 'ical', $3, $4, $5, 'active', $6, $6) RETURNING id`,
		apartmentID, feedID, uid, from, to, ubyport.UTCNow()).Scan(&id))
	return id
}

// runSync reconciles calendar text supplied directly, so no network is used.
func runSync(t *testing.T, pool *pgxpool.Pool, feed Feed, text string) SyncStats {
	t.Helper()
	stats, err := SyncFeed(context.Background(), pool, noEnv, feed, FetchOptions{}, &text)
	must(t, err)
	return stats
}

func TestBodyDigest(t *testing.T) {
	const want = "b4391efc6d114e800bf5a7eea843edbfdaa2ccfcb99d597a50dc2b0e42443c18" // Python body_digest
	if got := BodyDigest("BEGIN:VCALENDAR\r\nDTSTAMP:20260101T000000Z\r\nUID:a\r\nEND:VCALENDAR\r\n"); got != want {
		t.Errorf("digest = %s, want %s", got, want)
	}
	if got := BodyDigest("BEGIN:VCALENDAR\r\ndtstamp;TZID=UTC:20990101T000000Z\r\nUID:a\r\nEND:VCALENDAR\r\n"); got != want {
		t.Errorf("DTSTAMP must not change the digest: %s", got)
	}
	if got := BodyDigest("BEGIN:VCALENDAR\nUID:a\nEND:VCALENDAR\n"); got != want {
		t.Errorf("CRLF must normalise to LF: %s", got)
	}
}

func TestSyncFeedCreatesAndUpdates(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")

	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A")))
	if st.Created != 1 || st.Outcome != "changed" || st.Error != "" {
		t.Fatalf("first sync: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE uid = 'u1'`); got != "2027-03-01" {
		t.Errorf("date_from = %q", got)
	}
	if got := scalarText(t, pool, `SELECT last_status FROM ical_feed WHERE id = $1`, feed.ID); got != "ok" {
		t.Errorf("last_status = %q", got)
	}

	feed = reloadFeed(t, pool, feed.ID)
	st = runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270302", "20270306", "Guest A")))
	if st.Updated != 1 || st.Created != 0 {
		t.Fatalf("date move: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE uid = 'u1'`); got != "2027-03-02" {
		t.Errorf("moved date_from = %q", got)
	}
}

func TestSyncFeedUnchangedAndRevive(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	text := icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A"))
	runSync(t, pool, feed, text)

	feed = reloadFeed(t, pool, feed.ID)
	if st := runSync(t, pool, feed, text); st.Outcome != "unchanged" {
		t.Fatalf("second identical run: %+v", st)
	}

	// The stay was cancelled, then the calendar lists it again with new wording.
	_, err := pool.Exec(context.Background(), `UPDATE reservation SET status = 'cancelled' WHERE uid = 'u1'`)
	must(t, err)
	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A renamed")))
	if st.Updated != 1 {
		t.Fatalf("revive: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE uid = 'u1'`); got != "active" {
		t.Errorf("revived status = %q", got)
	}
}

func TestSyncFeedBlockKeepsStay(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u1", "2027-03-01", "2027-03-05")

	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270301", "20270305", "Not available")))
	if st.BlocksSkipped != 1 || st.Created != 0 {
		t.Fatalf("block: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "active" {
		t.Errorf("stay status after block = %q", got)
	}
}

func TestSyncFeedCancelEvent(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u1", "2027-03-01", "2027-03-05")

	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A", "STATUS:CANCELLED")))
	if st.Cancelled != 1 {
		t.Fatalf("cancel event: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" {
		t.Errorf("status = %q", got)
	}
}

func TestSyncFeedDuplicateUIDAlert(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")

	st := runSync(t, pool, feed, icsDoc(
		icsEvent("d1", "20270301", "20270305", "Guest A"),
		icsEvent("d1", "20270310", "20270312", "Guest B")))
	if st.Created != 1 {
		t.Fatalf("duplicate uid: %+v", st)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("feed_duplicate_uid:%d", feed.ID)); n != 1 {
		t.Errorf("duplicate alert open = %d, want 1", n)
	}
}

func TestSyncFeedMovedAfterReport(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u1", "2027-03-01", "2027-03-05")
	seedGuest(t, pool, stay, "sent", "2027-03-01", "2027-03-05")

	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270302", "20270306", "Guest A")))
	if st.Updated != 1 {
		t.Fatalf("move: %+v", st)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("moved_after_report:%d", stay)); n != 1 {
		t.Errorf("moved_after_report open = %d, want 1", n)
	}
}

func TestSyncFeedDatesInFlightKeepsDigest(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u1", "2027-03-01", "2027-03-05")
	g := seedGuest(t, pool, stay, "pending", "2027-03-01", "2027-03-05")
	var sub int64
	must(t, pool.QueryRow(ctx,
		`INSERT INTO submission (apartment_id, created_at, state) VALUES ($1, $2, 'running') RETURNING id`,
		aid, ubyport.UTCNow()).Scan(&sub))
	_, err := pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = $2`, sub, g)
	must(t, err)

	runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270302", "20270306", "Guest A")))
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2027-03-01" {
		t.Errorf("in-flight stay moved to %q", got)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored while in flight: %q", got)
	}
}

func TestSyncFeedIncompleteKeepsStays(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	for _, uid := range []string{"u1", "u2", "u3", "u4"} {
		seedStay(t, pool, aid, feed.ID, uid, "2027-03-01", "2027-03-05")
	}

	st := runSync(t, pool, feed, icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A")))
	if st.Cancelled != 0 {
		t.Fatalf("incomplete feed cancelled %d stays", st.Cancelled)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE ical_feed_id = $1 AND status = 'active'`, feed.ID); n != 4 {
		t.Errorf("active stays = %d, want 4", n)
	}
	if got := scalarText(t, pool, `SELECT last_status FROM ical_feed WHERE id = $1`, feed.ID); got != "suspect" {
		t.Errorf("last_status = %q, want suspect", got)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("feed_incomplete:%d", feed.ID)); n != 1 {
		t.Errorf("feed_incomplete open = %d, want 1", n)
	}
}

func TestSyncFeedVanishedStayCancelled(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cal.ics")
	seedStay(t, pool, aid, feed.ID, "u1", "2027-03-01", "2027-03-05")
	seedStay(t, pool, aid, feed.ID, "u2", "2027-04-01", "2027-04-05")

	st := runSync(t, pool, feed, icsDoc(
		icsEvent("u1", "20270301", "20270305", "Guest A"),
		icsEvent("u3", "20270501", "20270505", "Guest C")))
	if st.Created != 1 || st.Cancelled != 1 {
		t.Fatalf("vanished: %+v", st)
	}
	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE uid = 'u2'`); got != "cancelled" {
		t.Errorf("u2 status = %q", got)
	}
	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE uid = 'u1'`); got != "active" {
		t.Errorf("u1 status = %q", got)
	}
}

func TestSyncFeedNotModified(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	body := icsDoc(icsEvent("u1", "20270301", "20270305", "Guest A"))
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("If-None-Match") == `"v1"` {
			w.WriteHeader(http.StatusNotModified)
			return
		}
		w.Header().Set("ETag", `"v1"`)
		fmt.Fprint(w, body)
	})
	feed := newIcalFeed(t, pool, aid, base+"/cal.ics")

	st, err := SyncFeed(ctx, pool, noEnv, feed, opt, nil)
	must(t, err)
	if st.Outcome != "changed" || st.Created != 1 {
		t.Fatalf("first fetch: %+v", st)
	}
	feed = reloadFeed(t, pool, feed.ID)
	st, err = SyncFeed(ctx, pool, noEnv, feed, opt, nil)
	must(t, err)
	if st.Outcome != "not_modified" || st.Error != "" {
		t.Fatalf("conditional fetch: %+v", st)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE ical_feed_id = $1`, feed.ID); n != 1 {
		t.Errorf("reservations = %d, want 1", n)
	}
}
