package ubyport

import (
	"context"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

const notifyTS = "2026-11-01T00:00:00+00:00"

// notifyEnv returns a getenv over a fixed map (unset keys are "").
func notifyEnv(vals map[string]string) func(string) string {
	return func(k string) string { return vals[k] }
}

var notifyMailOn = notifyEnv(map[string]string{"UBYHOST_MAIL_BACKEND": "console"})
var notifyPushOn = notifyEnv(map[string]string{"UBYHOST_WEB_PUSH": "1"})

// notifyApartment seeds a user, a legal entity with the given contact e-mail
// (nil is NULL) and one apartment owned by that user.
func notifyApartment(t *testing.T, pool *pgxpool.Pool, contact *string) ApartmentRef {
	t.Helper()
	ctx := context.Background()
	var user, entity, apt int64
	name := fmt.Sprintf("Notify flat %d", time.Now().UnixNano())
	if err := pool.QueryRow(ctx,
		`INSERT INTO user_account (username, password_hash, created_at) VALUES ($1, $2, $3) RETURNING id`,
		fmt.Sprintf("notify-%d", time.Now().UnixNano()), "not-a-hash", notifyTS).Scan(&user); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO legal_entity (name, vat_status, invoice_due_days, business_type, created_at, contact_email)
		 VALUES ('Notify s.r.o.', 'none', 14, 'company', $1, $2) RETURNING id`,
		notifyTS, contact).Scan(&entity); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO apartment (internal_name, owner_user_id, legal_entity_id, created_at)
		 VALUES ($1, $2, $3, $4) RETURNING id`,
		name, user, entity, notifyTS).Scan(&apt); err != nil {
		t.Fatal(err)
	}
	return ApartmentRef{ID: apt, LegalEntityID: &entity, OwnerUserID: &user, InternalName: name}
}

// notifyStay seeds one reservation with one guest and returns the reservation id and guest id.
func notifyStay(t *testing.T, pool *pgxpool.Pool, apt int64, uid, from, to string) (int64, int64) {
	t.Helper()
	ctx := context.Background()
	var res, guest int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $5) RETURNING id`,
		apt, uid, from, to, notifyTS).Scan(&res); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, $2, $2) RETURNING id`,
		res, notifyTS).Scan(&guest); err != nil {
		t.Fatal(err)
	}
	return res, guest
}

// notifySubmission seeds a submission whose frozen guest batch is guests.
func notifySubmission(t *testing.T, pool *pgxpool.Pool, apt int64, guests ...int64) int64 {
	t.Helper()
	ids := make([]string, len(guests))
	for i, g := range guests {
		ids[i] = fmt.Sprint(g)
	}
	var sub int64
	if err := pool.QueryRow(context.Background(),
		`INSERT INTO submission (apartment_id, created_at, state, guest_ids) VALUES ($1, $2, 'running', $3) RETURNING id`,
		apt, notifyTS, "["+strings.Join(ids, ", ")+"]").Scan(&sub); err != nil {
		t.Fatal(err)
	}
	return sub
}

func notifyCount(t *testing.T, pool *pgxpool.Pool, query string, args ...any) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), query, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// notifyDevice seeds one push subscription for a user.
func notifyDevice(t *testing.T, pool *pgxpool.Pool, owner int64) {
	t.Helper()
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO push_subscription (user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc,
		   lang, device, failures, created_at, last_seen_at)
		 VALUES ($1, $2, 'x', 'x', 'x', 'en', 'phone', 0, $3, $3)`,
		owner, fmt.Sprintf("hash-%d", time.Now().UnixNano()), notifyTS); err != nil {
		t.Fatal(err)
	}
}

func TestNotifyMailOffOrNoContact(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	mailAddr := "host@example.cz"
	apt := notifyApartment(t, pool, &mailAddr)
	_, guest := notifyStay(t, pool, apt.ID, "uid-off", "2026-12-01", "2026-12-03")
	sub := notifySubmission(t, pool, apt.ID, guest)
	now := time.Date(2026, 12, 1, 10, 0, 0, 0, time.UTC)

	id, err := QueueSubmissionProblemMail(ctx, pool, notifyEnv(map[string]string{"UBYHOST_MAIL_BACKEND": "disabled"}),
		"https://app.example", "https://example.com", apt, sub, "rejected", "x", false, now)
	if err != nil || id != 0 {
		t.Fatalf("mail off: id=%d err=%v", id, err)
	}
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM email_outbox`); n != 0 {
		t.Fatalf("mail off wrote %d rows", n)
	}

	for _, contact := range []*string{nil, ptrString("not an address")} {
		noContact := notifyApartment(t, pool, contact)
		id, err := QueueSubmissionProblemMail(ctx, pool, notifyMailOn,
			"https://app.example", "https://example.com", noContact, sub, "rejected", "x", false, now)
		if err != nil || id != 0 {
			t.Fatalf("no contact: id=%d err=%v", id, err)
		}
	}
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM email_outbox`); n != 0 {
		t.Fatalf("no contact wrote %d rows", n)
	}
}

func ptrString(s string) *string { return &s }

func TestNotifyMailRowPayloadAndIdempotency(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	contact := "Host <Host@Example.CZ>"
	apt := notifyApartment(t, pool, &contact)
	res, guest := notifyStay(t, pool, apt.ID, "uid-row", "2026-12-01", "2026-12-03")
	sub := notifySubmission(t, pool, apt.ID, guest)
	const base, appURL, pubURL = "rejected", "https://app.example", "https://example.com"

	// 22:30 UTC on 1 December is 23:30 in Prague on 1 December.
	first := time.Date(2026, 12, 1, 22, 30, 0, 0, time.UTC)
	id, err := QueueSubmissionProblemMail(ctx, pool, notifyMailOn, appURL, pubURL, apt, sub, base, "Bad postcode", false, first)
	if err != nil || id == 0 {
		t.Fatalf("queue: id=%d err=%v", id, err)
	}

	stays, err := StaysForSubmission(ctx, pool, sub)
	if err != nil || len(stays) != 1 || stays[0].ID != res {
		t.Fatalf("stays: %+v err=%v", stays, err)
	}
	content, err := mail.BuildSubmissionProblem(appURL, pubURL, "en", apt.InternalName, base, "Bad postcode", false, stays, sub)
	if err != nil {
		t.Fatal(err)
	}
	var to, kind, subject, payload, state, key string
	var reservationID *int64
	var attempts int
	if err := pool.QueryRow(ctx,
		`SELECT to_email, kind, subject, payload, state, attempts, reservation_id, idempotency_key
		   FROM email_outbox WHERE id = $1`, id).
		Scan(&to, &kind, &subject, &payload, &state, &attempts, &reservationID, &key); err != nil {
		t.Fatal(err)
	}
	wantKey := fmt.Sprintf("submission_problem:%d:%s:2026-12-01", apt.ID, base)
	if to != "host@example.cz" || kind != "submission_problem" || state != "queued" || attempts != 0 {
		t.Fatalf("row: to=%q kind=%q state=%q attempts=%d", to, kind, state, attempts)
	}
	if key != wantKey {
		t.Fatalf("key %q, want %q", key, wantKey)
	}
	if subject != content.Subject {
		t.Fatalf("subject %q, want %q", subject, content.Subject)
	}
	if reservationID == nil || *reservationID != res {
		t.Fatalf("reservation_id %v, want %d", reservationID, res)
	}
	var wantPayload strings.Builder
	wantPayload.WriteString(`{"text": `)
	writePyString(&wantPayload, content.Text)
	wantPayload.WriteString(`, "html": `)
	writePyString(&wantPayload, content.HTML)
	wantPayload.WriteString(`, "lang": "en"}`)
	if payload != wantPayload.String() {
		t.Fatalf("payload bytes differ from the renderer")
	}

	// Same day, 21:00 UTC is 22:00 in Prague: same row.
	again, err := QueueSubmissionProblemMail(ctx, pool, notifyMailOn, appURL, pubURL, apt, sub, base, "Bad postcode",
		false, time.Date(2026, 12, 1, 21, 0, 0, 0, time.UTC))
	if err != nil || again != id {
		t.Fatalf("same day: id=%d want %d err=%v", again, id, err)
	}
	// A different state is a new row.
	other, err := QueueSubmissionProblemMail(ctx, pool, notifyMailOn, appURL, pubURL, apt, sub, "partial", "", false, first)
	if err != nil || other == 0 || other == id {
		t.Fatalf("other state: id=%d err=%v", other, err)
	}
	// 23:30 UTC on 1 December is 00:30 in Prague on 2 December: new row.
	nextDay, err := QueueSubmissionProblemMail(ctx, pool, notifyMailOn, appURL, pubURL, apt, sub, base, "Bad postcode",
		false, time.Date(2026, 12, 1, 23, 30, 0, 0, time.UTC))
	if err != nil || nextDay == 0 || nextDay == id {
		t.Fatalf("next day: id=%d err=%v", nextDay, err)
	}
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE apartment_id = $1`, apt.ID); n != 3 {
		t.Fatalf("rows %d, want 3", n)
	}
}

func TestNotifyMailTwoStaysHasNoReservation(t *testing.T) {
	pool := claimTestPool(t)
	contact := "host@example.cz"
	apt := notifyApartment(t, pool, &contact)
	_, g1 := notifyStay(t, pool, apt.ID, "uid-two-a", "2026-12-01", "2026-12-03")
	_, g2 := notifyStay(t, pool, apt.ID, "uid-two-b", "2026-12-05", "2026-12-07")
	sub := notifySubmission(t, pool, apt.ID, g1, g2)
	id, err := QueueSubmissionProblemMail(context.Background(), pool, notifyMailOn,
		"https://app.example", "https://example.com", apt, sub, "rejected", "", true,
		time.Date(2026, 12, 1, 10, 0, 0, 0, time.UTC))
	if err != nil || id == 0 {
		t.Fatalf("queue: id=%d err=%v", id, err)
	}
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE id = $1 AND reservation_id IS NULL`, id); n != 1 {
		t.Fatalf("reservation_id not NULL for two stays")
	}
}

func TestNotifyMailAddressForms(t *testing.T) {
	cases := map[string]string{
		"Host <A@B.CZ>":          "a@b.cz",
		"  plain@example.cz  ":   "plain@example.cz",
		"a@b.cz, c@d.cz":         "",
		"Name <a@b.cz> <c@d.cz>": "",
		"\"Name\" <a@b.cz>":      "",
		"nobody":                 "",
		"Name <a@b.cz> trailing": "",
	}
	for raw, want := range cases {
		if got := normaliseEmail(raw); got != want {
			t.Errorf("normaliseEmail(%q) = %q, want %q", raw, got, want)
		}
	}
}

func TestNotifyPush(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	contact := "host@example.cz"
	apt := notifyApartment(t, pool, &contact)
	_, g1 := notifyStay(t, pool, apt.ID, "uid-push-a", "2026-12-01", "2026-12-03")
	sub := notifySubmission(t, pool, apt.ID, g1)
	notifyDevice(t, pool, *apt.OwnerUserID)
	notifyDevice(t, pool, *apt.OwnerUserID)
	now := time.Date(2026, 12, 1, 10, 0, 0, 0, time.UTC)

	if n, err := QueueFilingProblemPush(ctx, pool, notifyEnv(map[string]string{"UBYHOST_WEB_PUSH": "0"}), apt, sub, now); err != nil || n != 0 {
		t.Fatalf("push off: n=%d err=%v", n, err)
	}
	if n, err := QueueFilingProblemPush(ctx, pool, notifyPushOn, apt, sub, now); err != nil || n != 2 {
		t.Fatalf("two devices: n=%d err=%v", n, err)
	}
	if n, err := QueueFilingProblemPush(ctx, pool, notifyPushOn, apt, sub, now); err != nil || n != 0 {
		t.Fatalf("repeat same day: n=%d err=%v", n, err)
	}
	stayURL := fmt.Sprintf("/reservations/%d", notifyStayID(t, pool, sub))
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM push_outbox WHERE user_account_id = $1 AND url = $2`,
		*apt.OwnerUserID, stayURL); n != 2 {
		t.Fatalf("one stay: url not /reservations/<id> on both rows")
	}
}

// notifyStayID returns the reservation id of the first stay of a submission.
func notifyStayID(t *testing.T, pool *pgxpool.Pool, sub int64) int64 {
	t.Helper()
	stays, err := StaysForSubmission(context.Background(), pool, sub)
	if err != nil || len(stays) == 0 {
		t.Fatalf("stays: %v", err)
	}
	return stays[0].ID
}

func TestNotifyPushLongNameAndTwoStays(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	contact := "host@example.cz"
	apt := notifyApartment(t, pool, &contact)
	_, g1 := notifyStay(t, pool, apt.ID, "uid-long-a", "2026-12-01", "2026-12-03")
	_, g2 := notifyStay(t, pool, apt.ID, "uid-long-b", "2026-12-05", "2026-12-07")
	sub := notifySubmission(t, pool, apt.ID, g1, g2)
	notifyDevice(t, pool, *apt.OwnerUserID)
	apt.InternalName = strings.Repeat("a", 130)
	now := time.Date(2026, 12, 1, 10, 0, 0, 0, time.UTC)

	if n, err := QueueFilingProblemPush(ctx, pool, notifyPushOn, apt, sub, now); err != nil || n != 1 {
		t.Fatalf("queue: n=%d err=%v", n, err)
	}
	if n := notifyCount(t, pool, `SELECT COUNT(*) FROM push_outbox WHERE url = '/reservations'`); n != 1 {
		t.Fatalf("two stays: url is not /reservations")
	}
	want := `{"property": "` + strings.Repeat("a", 120) + `"}`
	var params string
	if err := pool.QueryRow(ctx, `SELECT params FROM push_outbox WHERE user_account_id = $1`, *apt.OwnerUserID).Scan(&params); err != nil {
		t.Fatal(err)
	}
	if params != want {
		t.Fatalf("params not cut to 120 characters")
	}
}
