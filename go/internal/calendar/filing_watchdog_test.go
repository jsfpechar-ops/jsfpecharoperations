package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

// watchdogStayRecord is one stay as App/scripts/filing_watchdog_golden.py
// stay_record writes it.
type watchdogStayRecord struct {
	ReservationID       int64   `json:"reservation_id"`
	DateFrom            string  `json:"date_from"`
	ApartmentID         int64   `json:"apartment_id"`
	Property            string  `json:"property"`
	LegalEntityID       *int64  `json:"legal_entity_id"`
	OwnerUserID         *int64  `json:"owner_user_id"`
	Workspace           string  `json:"workspace"`
	MailedAt            *string `json:"mailed_at"`
	Unfiled             int     `json:"unfiled"`
	AwaitingRetryGuests int     `json:"awaiting_retry_guests"`
	AwaitingRetry       bool    `json:"awaiting_retry"`
	SendFailed          bool    `json:"send_failed"`
	NoGuests            bool    `json:"no_guests"`
	Arrival             string  `json:"arrival"`
	Deadline            string  `json:"deadline"`
	Overdue             bool    `json:"overdue"`
}

type watchdogInstant struct {
	At            string               `json:"at"`
	AtRisk        []watchdogStayRecord `json:"at_risk"`
	AtRiskDefault []int64              `json:"at_risk_default"`
	UnknownRisk   []watchdogStayRecord `json:"unknown_risk"`
}

type watchdogHeartbeat struct {
	URL    string `json:"url"`
	AtRisk bool   `json:"at_risk"`
	Ping   string `json:"ping"`
}

type watchdogGolden struct {
	Env               map[string]string   `json:"env"`
	RetryGraceMinutes int                 `json:"retry_grace_minutes"`
	Seed              []watchSeedTable    `json:"seed"`
	Instants          []watchdogInstant   `json:"instants"`
	Heartbeats        []watchdogHeartbeat `json:"heartbeats"`
}

func loadWatchdogGolden(t *testing.T) watchdogGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/filing_watchdog_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchdogGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Instants) < 15 || len(g.Seed) == 0 || len(g.Heartbeats) == 0 {
		t.Fatal("golden file has too few instants, no seed or no heartbeats")
	}
	return g
}

// watchdogGetenv serves the golden's environment, as the Python process saw it.
func watchdogGetenv(env map[string]string) func(string) string {
	return func(k string) string { return env[k] }
}

// watchdogLookup is os.LookupEnv over the same map: a missing key is unset.
func watchdogLookup(env map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := env[k]
		return v, ok
	}
}

// watchdogRecord is stay_record for a Go stay.
func watchdogRecord(s WatchdogStay) watchdogStayRecord {
	return watchdogStayRecord{
		ReservationID:       s.ReservationID,
		DateFrom:            s.DateFrom,
		ApartmentID:         s.ApartmentID,
		Property:            s.Property,
		LegalEntityID:       s.LegalEntityID,
		OwnerUserID:         s.OwnerUserID,
		Workspace:           s.Workspace,
		MailedAt:            s.MailedAt,
		Unfiled:             s.Unfiled,
		AwaitingRetryGuests: s.AwaitingRetryGuests,
		AwaitingRetry:       s.AwaitingRetry,
		SendFailed:          s.SendFailed,
		NoGuests:            s.NoGuests,
		Arrival:             s.Arrival.Format("2006-01-02"),
		Deadline:            s.Deadline.Format("2006-01-02T15:04:05"),
		Overdue:             s.Overdue,
	}
}

func watchdogJSON(t *testing.T, v any) string {
	t.Helper()
	b, err := json.MarshalIndent(v, "", " ")
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

// TestWatchdogStaysMatchPython seeds the golden rows and compares AtRiskStays
// (with and without the stays awaiting the resend) and UnknownRiskStays with
// what filing_watchdog.py returned for the same rows at every golden instant.
func TestWatchdogStaysMatchPython(t *testing.T) {
	g := loadWatchdogGolden(t)
	lookup := watchdogLookup(g.Env)
	grace, err := watchdogRetryGrace(lookup)
	if err != nil || int(grace/time.Minute) != g.RetryGraceMinutes {
		t.Fatalf("retry grace %v (%v), Python %d min", grace, err, g.RetryGraceMinutes)
	}
	pool := dbPool(t)
	watchSeed(t, pool, watchGolden{Seed: g.Seed})
	ctx := context.Background()
	for _, in := range g.Instants {
		at, err := time.Parse(time.RFC3339, in.At)
		if err != nil {
			t.Fatal(err)
		}
		every, err := AtRiskStays(ctx, pool, lookup, at, true)
		if err != nil {
			t.Fatalf("%s at risk: %v", in.At, err)
		}
		got := []watchdogStayRecord{}
		for _, s := range every {
			got = append(got, watchdogRecord(s))
		}
		want := in.AtRisk
		if want == nil {
			want = []watchdogStayRecord{}
		}
		if a, b := watchdogJSON(t, got), watchdogJSON(t, want); a != b {
			t.Errorf("%s at-risk stays differ from Python\n got:\n%s\nwant:\n%s", in.At, a, b)
		}
		plain, err := AtRiskStays(ctx, pool, lookup, at, false)
		if err != nil {
			t.Fatalf("%s at risk (default): %v", in.At, err)
		}
		ids := []int64{}
		for _, s := range plain {
			ids = append(ids, s.ReservationID)
		}
		wantIDs := in.AtRiskDefault
		if wantIDs == nil {
			wantIDs = []int64{}
		}
		if a, b := watchdogJSON(t, ids), watchdogJSON(t, wantIDs); a != b {
			t.Errorf("%s at-risk ids without awaiting differ: got %s want %s", in.At, a, b)
		}
		unknown, err := UnknownRiskStays(ctx, pool, at)
		if err != nil {
			t.Fatalf("%s unknown risk: %v", in.At, err)
		}
		gotU := []watchdogStayRecord{}
		for _, s := range unknown {
			gotU = append(gotU, watchdogRecord(s))
		}
		wantU := in.UnknownRisk
		if wantU == nil {
			wantU = []watchdogStayRecord{}
		}
		if a, b := watchdogJSON(t, gotU), watchdogJSON(t, wantU); a != b {
			t.Errorf("%s unknown-risk stays differ from Python\n got:\n%s\nwant:\n%s", in.At, a, b)
		}
	}
}

// TestFilingHeartbeatURLMatchesPython needs no database.
func TestFilingHeartbeatURLMatchesPython(t *testing.T) {
	g := loadWatchdogGolden(t)
	for _, h := range g.Heartbeats {
		env := map[string]string{"UBYHOST_HEARTBEAT_FILING_URL": h.URL}
		if got := FilingHeartbeatURL(watchdogGetenv(env), h.AtRisk); got != h.Ping {
			t.Errorf("heartbeat %q at_risk=%v: got %q, Python %q", h.URL, h.AtRisk, got, h.Ping)
		}
	}
}

// TestWatchdogRetryGrace is RETRY_GRACE = 2 x max(1, int(SUBMIT_SWEEP_MINUTES))
// minutes: unset is 10; a set value Python's int() refuses is an error.
func TestWatchdogRetryGrace(t *testing.T) {
	ok := map[string]time.Duration{
		"10": 20 * time.Minute, " 7 ": 14 * time.Minute, "+3": 6 * time.Minute,
		"1_0": 20 * time.Minute, "+1_5": 30 * time.Minute, "-1_0": 2 * time.Minute,
		"0": 2 * time.Minute, "-5": 2 * time.Minute,
	}
	for raw, want := range ok {
		got, err := watchdogRetryGrace(watchdogLookup(map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": raw}))
		if err != nil || got != want {
			t.Errorf("sweep %q: grace %v (%v), want %v", raw, got, err, want)
		}
	}
	if got, err := watchdogRetryGrace(watchdogLookup(map[string]string{})); err != nil || got != 20*time.Minute {
		t.Errorf("unset: grace %v (%v), want 20m", got, err)
	}
	for _, raw := range []string{"abc", "", "  ", "1.5", "10m", "1__0", "_10", "10_", "+_1"} {
		env := map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": raw}
		if _, err := watchdogRetryGrace(watchdogLookup(env)); err == nil {
			t.Errorf("sweep %q: want an error, as Python int() raises", raw)
		}
		// AtRiskStays refuses before it touches the database.
		_, err := AtRiskStays(context.Background(), nil, watchdogLookup(env), time.Now(), true)
		if err == nil || !strings.Contains(err.Error(), "UBYHOST_SUBMIT_SWEEP_MINUTES") {
			t.Errorf("sweep %q: AtRiskStays error %v, want one naming the variable", raw, err)
		}
	}
}

// TestWatchdogAwaitingRetry pins the grace window ends without a database.
func TestWatchdogAwaitingRetry(t *testing.T) {
	now := time.Date(2026, 9, 17, 10, 0, 0, 0, time.UTC)
	grace := 20 * time.Minute
	cases := []struct {
		state, retried, finished string
		want                     bool
	}{
		{"outcome_unknown", "", "2026-09-17T09:40:00+00:00", true},
		{"outcome_unknown", "", "2026-09-17T09:39:59+00:00", false},
		{"outcome_unknown", "", "2026-09-17T10:00:00+00:00", true},
		{"outcome_unknown", "", "2026-09-17T10:00:01+00:00", false},
		{"outcome_unknown", "", "2026-09-17T11:50:00+02:00", true},
		{"outcome_unknown", "", "2026-09-17 09:50:00", true},
		{"outcome_unknown", "2026-09-17T09:55:00+00:00", "2026-09-17T09:50:00+00:00", false},
		{"error", "", "2026-09-17T09:50:00+00:00", false},
		{"outcome_unknown", "", "", false},
		{"outcome_unknown", "", "None", false},
	}
	for _, c := range cases {
		if got := watchdogAwaitingRetry(c.state, c.retried, c.finished, now, grace); got != c.want {
			t.Errorf("%+v: got %v", c, got)
		}
	}
}
