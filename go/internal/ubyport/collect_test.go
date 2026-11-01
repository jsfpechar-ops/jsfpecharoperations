package ubyport

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

var collectNowTime = time.Date(2026, 11, 1, 10, 0, 0, 0, time.UTC)

// collectValidGuest is the golden "valid" guest of validation/testdata, so the
// fixture is one the validator already accepts.
func collectValidGuest(t *testing.T) map[string]any {
	t.Helper()
	raw, err := os.ReadFile("../validation/testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var gd struct {
		Guest []struct {
			Name  string            `json:"name"`
			Guest map[string]string `json:"guest"`
		} `json:"guest"`
	}
	if err := json.Unmarshal(raw, &gd); err != nil {
		t.Fatal(err)
	}
	for _, c := range gd.Guest {
		if c.Name == "valid" {
			out := map[string]any{}
			for k, v := range c.Guest {
				out[k] = v
			}
			return out
		}
	}
	t.Fatal("golden valid guest missing")
	return nil
}

// collectSet writes the given columns of one row. Keys are test-controlled names.
func collectSet(t *testing.T, pool *pgxpool.Pool, table string, id int64, set map[string]any) {
	t.Helper()
	if len(set) == 0 {
		return
	}
	args := []any{id}
	parts := []string{}
	for k, v := range set {
		args = append(args, v)
		parts = append(parts, fmt.Sprintf("%s = $%d", k, len(args)))
	}
	q := fmt.Sprintf("UPDATE %s SET %s WHERE id = $1", table, strings.Join(parts, ", "))
	if _, err := pool.Exec(context.Background(), q, args...); err != nil {
		t.Fatal(err)
	}
}

func collectNewApt(t *testing.T, pool *pgxpool.Pool, apt map[string]any) int64 {
	t.Helper()
	var id int64
	if err := pool.QueryRow(context.Background(),
		`INSERT INTO apartment (internal_name, created_at) VALUES ('Test flat', $1) RETURNING id`,
		"2026-11-01T00:00:00+00:00").Scan(&id); err != nil {
		t.Fatal(err)
	}
	collectSet(t, pool, "apartment", id, apt)
	return id
}

// collectAddStay adds a reservation with one guest. The guest starts from the
// valid golden guest, sendable in the default setup (scheduled, completed two days ago).
func collectAddStay(t *testing.T, pool *pgxpool.Pool, aptID int64, res, guest map[string]any) int64 {
	t.Helper()
	ctx := context.Background()
	const ts = "2026-11-01T00:00:00+00:00"
	var resID, guestID int64
	uid := fmt.Sprintf("uid-%d", time.Now().UnixNano())
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, created_at, updated_at) VALUES ($1, $2, $3, $3) RETURNING id`,
		aptID, uid, ts).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	r := map[string]any{"date_from": "2026-12-01", "date_to": "2026-12-03", "registration_completed_at": "2026-10-30T10:00:00+00:00"}
	for k, v := range res {
		r[k] = v
	}
	collectSet(t, pool, "reservation", resID, r)
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, $2, $2) RETURNING id`,
		resID, ts).Scan(&guestID); err != nil {
		t.Fatal(err)
	}
	g := collectValidGuest(t)
	for k, v := range guest {
		g[k] = v
	}
	collectSet(t, pool, "guest", guestID, g)
	return guestID
}

func collectDecrypter(t *testing.T) (FieldDecrypter, FieldEncrypter) {
	t.Helper()
	mf, enc := storeTestCrypto(t)
	return func(token string) (string, error) {
		raw, err := mf.Decrypt(token, 0, time.Now())
		if err != nil {
			return "", err
		}
		return string(raw), nil
	}, enc
}

func collectIDs(pairs []BatchPair) []int64 {
	var ids []int64
	for _, p := range pairs {
		ids = append(ids, p.Outcome.ID)
	}
	return ids
}

type collectCase struct {
	name      string
	apt       map[string]any
	res       map[string]any
	guest     map[string]any
	opts      CollectOptions
	now       time.Time
	setup     func(t *testing.T, pool *pgxpool.Pool, guestID int64)
	want      bool
	wantState string
}

func TestCollectSendableBranches(t *testing.T) {
	pool := claimTestPool(t)
	dec, _ := collectDecrypter(t)
	cases := []collectCase{
		{name: "eligible", want: true},
		{name: "demo stay", res: map[string]any{"source": "demo"}},
		{name: "restricted blocks when on", guest: map[string]any{"restricted_at": "2026-10-01T00:00:00+00:00"},
			opts: CollectOptions{RestrictedBlocksFiling: true}},
		{name: "restricted sent when off", guest: map[string]any{"restricted_at": "2026-10-01T00:00:00+00:00"}, want: true},
		{name: "czech set not_required", guest: map[string]any{"nationality": "CZE"}, wantState: "not_required"},
		{name: "hand filed never resent", guest: map[string]any{"submit_state": "sent", "manual_filed_at": "2026-10-31T09:00:00+00:00"},
			opts: CollectOptions{AllowResend: true}},
		{name: "sent resent with allow_resend", guest: map[string]any{"submit_state": "sent"},
			opts: CollectOptions{AllowResend: true}, want: true},
		{name: "sent skipped without allow_resend", guest: map[string]any{"submit_state": "sent"}},
		{name: "blocked skipped", guest: map[string]any{"submit_state": "blocked"}},
		{name: "blocked with allow_resend", guest: map[string]any{"submit_state": "blocked"},
			opts: CollectOptions{AllowResend: true}, want: true},
		{name: "blocked as duplicate stays out", guest: map[string]any{"submit_state": "blocked", "last_errors": "duplicate record"},
			opts: CollectOptions{AllowResend: true}},
		{name: "attempts cap for sweep", guest: map[string]any{"submit_attempts": 1}},
		{name: "attempts cap lifted by host", guest: map[string]any{"submit_attempts": 1},
			opts: CollectOptions{IgnoreAutomation: true}, want: true},
		{name: "in doubt pointer blocks sweep", setup: func(t *testing.T, pool *pgxpool.Pool, guestID int64) {
			apt := storeApartmentOf(t, pool, guestID)
			subID, err := InsertSubmission(context.Background(), pool, apt, "scheduled", []int64{guestID}, "e", "2026-11-01T00:00:00+00:00")
			if err != nil {
				t.Fatal(err)
			}
			collectSet(t, pool, "submission", subID, map[string]any{"state": "outcome_unknown"})
			collectSet(t, pool, "guest", guestID, map[string]any{"submission_id": subID})
		}},
		{name: "incomplete", guest: map[string]any{"surname": ""}},
		{name: "stale signature dates", guest: map[string]any{"stay_from": "2026-11-25"}},
		{name: "manual mode waits for host", apt: map[string]any{"automation_mode": "manual"}},
		{name: "manual mode host send", apt: map[string]any{"automation_mode": "manual"},
			opts: CollectOptions{IgnoreAutomation: true}, want: true},
		{name: "no completion", res: map[string]any{"registration_completed_at": nil}},
		{name: "no completion, ignore schedule", res: map[string]any{"registration_completed_at": nil},
			opts: CollectOptions{IgnoreSchedule: boolPtr(true)}, want: true},
		{name: "delay not reached", res: map[string]any{"registration_completed_at": "2026-10-31T12:00:00+00:00"}},
		{name: "immediate", apt: map[string]any{"automation_mode": "immediate"},
			res: map[string]any{"registration_completed_at": "2026-11-01T09:59:00+00:00"}, want: true},
		{name: "deadline margin pulls send earlier", now: time.Date(2026, 10, 30, 17, 0, 0, 0, time.UTC),
			res: map[string]any{"date_from": "2026-10-28", "date_to": "2026-10-30"}, want: true},
	}
	for _, c := range cases {
		c := c
		t.Run(c.name, func(t *testing.T) {
			aptID := collectNewApt(t, pool, c.apt)
			guestID := collectAddStay(t, pool, aptID, c.res, c.guest)
			if c.setup != nil {
				c.setup(t, pool, guestID)
			}
			opts := c.opts
			opts.Decrypt = dec
			now := collectNowTime
			if !c.now.IsZero() {
				now = c.now
			}
			opts.Now = func() time.Time { return now }
			got, err := CollectSendable(context.Background(), pool, aptID, opts)
			if err != nil {
				t.Fatal(err)
			}
			found := false
			for _, id := range collectIDs(got) {
				found = found || id == guestID
			}
			if found != c.want {
				t.Fatalf("sendable = %v, want %v", found, c.want)
			}
			if c.wantState != "" {
				if st := storeRead(t, pool, "guest", guestID, "submit_state")["submit_state"]; st != c.wantState {
					t.Fatalf("submit_state = %q, want %q", st, c.wantState)
				}
			}
		})
	}
}

func boolPtr(b bool) *bool { return &b }

func TestCollectSendableDecryptsAndOrders(t *testing.T) {
	pool := claimTestPool(t)
	dec, enc := collectDecrypter(t)
	token, err := enc("C01X00T47")
	if err != nil {
		t.Fatal(err)
	}
	aptID := collectNewApt(t, pool, nil)
	// The later stay is created first: order must follow stay start, then guest id.
	late := collectAddStay(t, pool, aptID, map[string]any{"date_from": "2026-12-05", "date_to": "2026-12-07"}, nil)
	early := collectAddStay(t, pool, aptID, nil, map[string]any{"doc_number": "", "doc_number_enc": token})
	opts := CollectOptions{Decrypt: dec, Now: func() time.Time { return collectNowTime }}
	got, err := CollectSendable(context.Background(), pool, aptID, opts)
	if err != nil {
		t.Fatal(err)
	}
	ids := collectIDs(got)
	if len(ids) != 2 || ids[0] != early || ids[1] != late {
		t.Fatalf("order = %v, want [%d %d]", ids, early, late)
	}
	if got[0].Guest.DocNumber != "C01X00T47" {
		t.Fatalf("doc number not read back plain: %q", got[0].Guest.DocNumber)
	}
	only := opts
	only.OnlyGuestIDs = []int64{late}
	got, err = CollectSendable(context.Background(), pool, aptID, only)
	if err != nil {
		t.Fatal(err)
	}
	if ids := collectIDs(got); len(ids) != 1 || ids[0] != late {
		t.Fatalf("only_guest_ids = %v, want [%d]", ids, late)
	}
}

func TestCollectSendableBadTokenIsError(t *testing.T) {
	pool := claimTestPool(t)
	dec, _ := collectDecrypter(t)
	aptID := collectNewApt(t, pool, nil)
	collectAddStay(t, pool, aptID, nil, map[string]any{"doc_number": "", "doc_number_enc": "not-a-token"})
	if _, err := CollectSendable(context.Background(), pool, aptID, CollectOptions{Decrypt: dec}); err == nil {
		t.Fatal("a token that will not decrypt must be an error")
	}
}

func TestReportingDeadline(t *testing.T) {
	cases := []struct{ checkIn, want string }{
		{"2026-11-02", "2026-11-04T22:59:59Z"}, // Monday: Wednesday, CET
		{"2026-10-30", "2026-11-03T22:59:59Z"}, // Friday: Tuesday, CET
		{"2026-10-31", "2026-11-04T22:59:59Z"}, // Saturday: count opens Monday 2 Nov, Wednesday 4 Nov
		{"2026-11-01", "2026-11-04T22:59:59Z"}, // Sunday: same count
		{"2026-10-22", "2026-10-26T22:59:59Z"}, // across DST end (25 Oct): Thursday, Monday 26 Oct, CET
		{"2026-06-01", "2026-06-03T21:59:59Z"}, // summer: Monday, Wednesday, CEST
	}
	for _, c := range cases {
		in, err := time.Parse("2006-01-02", c.checkIn)
		if err != nil {
			t.Fatal(err)
		}
		if got := ReportingDeadline(in).UTC().Format(time.RFC3339); got != c.want {
			t.Errorf("check-in %s: deadline %s, want %s", c.checkIn, got, c.want)
		}
	}
}
