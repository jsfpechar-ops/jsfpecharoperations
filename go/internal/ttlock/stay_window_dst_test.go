package ttlock

import (
	"testing"
	"time"
)

func TestStayWindowAcrossEuropeanDST(t *testing.T) {
	loc, err := time.LoadLocation(stayZone)
	if err != nil {
		t.Fatal(err)
	}

	cases := []struct {
		name      string
		dateFrom  string
		dateTo    string
		cin       int
		cout      int
		buffer    int
		wantStart time.Time
		wantEnd   time.Time
		wantFrom  string
		wantUntil string
	}{
		{
			name:      "winter CET (UTC+1) with 1h buffer",
			dateFrom:  "2026-01-15",
			dateTo:    "2026-01-17",
			cin:       15,
			cout:      11,
			buffer:    1,
			wantStart: time.Date(2026, 1, 15, 13, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 1, 17, 11, 0, 0, 0, time.UTC),
			wantFrom:  "2026-01-15 14:00 CET",
			wantUntil: "2026-01-17 12:00 CET",
		},
		{
			name:      "summer CEST (UTC+2) with 1h buffer",
			dateFrom:  "2026-07-15",
			dateTo:    "2026-07-17",
			cin:       15,
			cout:      11,
			buffer:    1,
			wantStart: time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 7, 17, 10, 0, 0, 0, time.UTC),
			wantFrom:  "2026-07-15 14:00 CEST",
			wantUntil: "2026-07-17 12:00 CEST",
		},
		{
			name:      "crossing spring forward 2026 (no buffer)",
			dateFrom:  "2026-03-28",
			dateTo:    "2026-03-30",
			cin:       15,
			cout:      11,
			buffer:    0,
			wantStart: time.Date(2026, 3, 28, 14, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 3, 30, 9, 0, 0, 0, time.UTC),
			wantFrom:  "2026-03-28 15:00 CET",
			wantUntil: "2026-03-30 11:00 CEST",
		},
		{
			name:      "crossing spring forward 2026 (1h buffer)",
			dateFrom:  "2026-03-28",
			dateTo:    "2026-03-30",
			cin:       15,
			cout:      11,
			buffer:    1,
			wantStart: time.Date(2026, 3, 28, 13, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 3, 30, 10, 0, 0, 0, time.UTC),
			wantFrom:  "2026-03-28 14:00 CET",
			wantUntil: "2026-03-30 12:00 CEST",
		},
		{
			name:      "crossing fall back 2026 (no buffer)",
			dateFrom:  "2026-10-24",
			dateTo:    "2026-10-26",
			cin:       15,
			cout:      11,
			buffer:    0,
			wantStart: time.Date(2026, 10, 24, 13, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 10, 26, 10, 0, 0, 0, time.UTC),
			wantFrom:  "2026-10-24 15:00 CEST",
			wantUntil: "2026-10-26 11:00 CET",
		},
		{
			name:      "crossing fall back 2026 (1h buffer)",
			dateFrom:  "2026-10-24",
			dateTo:    "2026-10-26",
			cin:       15,
			cout:      11,
			buffer:    1,
			wantStart: time.Date(2026, 10, 24, 12, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2026, 10, 26, 11, 0, 0, 0, time.UTC),
			wantFrom:  "2026-10-24 14:00 CEST",
			wantUntil: "2026-10-26 12:00 CET",
		},
		{
			name:      "crossing spring forward 2027 (Mar 28, 1h buffer)",
			dateFrom:  "2027-03-27",
			dateTo:    "2027-03-29",
			cin:       15,
			cout:      10,
			buffer:    1,
			wantStart: time.Date(2027, 3, 27, 13, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2027, 3, 29, 9, 0, 0, 0, time.UTC),
			wantFrom:  "2027-03-27 14:00 CET",
			wantUntil: "2027-03-29 11:00 CEST",
		},
		{
			name:      "crossing fall back 2027 (Oct 31, 1h buffer)",
			dateFrom:  "2027-10-30",
			dateTo:    "2027-11-01",
			cin:       15,
			cout:      10,
			buffer:    1,
			wantStart: time.Date(2027, 10, 30, 12, 0, 0, 0, time.UTC),
			wantEnd:   time.Date(2027, 11, 1, 10, 0, 0, 0, time.UTC),
			wantFrom:  "2027-10-30 14:00 CEST",
			wantUntil: "2027-11-01 11:00 CET",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			startMS, endMS, err := StayWindow(tc.dateFrom, tc.dateTo, tc.cin, tc.cout, tc.buffer)
			if err != nil {
				t.Fatalf("StayWindow: %v", err)
			}
			if startMS != tc.wantStart.UnixMilli() || endMS != tc.wantEnd.UnixMilli() {
				t.Fatalf("got %d..%d, want %d..%d", startMS, endMS, tc.wantStart.UnixMilli(), tc.wantEnd.UnixMilli())
			}
			if err := wholeHour(startMS); err != nil {
				t.Fatalf("startMS not whole hour: %v", err)
			}
			if err := wholeHour(endMS); err != nil {
				t.Fatalf("endMS not whole hour: %v", err)
			}
			gotFrom := time.UnixMilli(startMS).In(loc).Format("2006-01-02 15:04 MST")
			gotUntil := time.UnixMilli(endMS).In(loc).Format("2006-01-02 15:04 MST")
			if gotFrom != tc.wantFrom || gotUntil != tc.wantUntil {
				t.Fatalf("local %q..%q, want %q..%q", gotFrom, gotUntil, tc.wantFrom, tc.wantUntil)
			}
		})
	}
}
