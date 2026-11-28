package doorcodes

import (
	"testing"
	"time"
)

func TestLastPragueDSTTransition(t *testing.T) {
	cases := []struct {
		name string
		now  time.Time
		want time.Time
	}{
		{
			name: "winter before 2026 spring forward",
			now:  time.Date(2026, 3, 29, 0, 59, 59, 0, time.UTC),
			want: time.Date(2025, 10, 26, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "exact 2026 spring forward instant",
			now:  time.Date(2026, 3, 29, 1, 0, 0, 0, time.UTC),
			want: time.Date(2026, 3, 29, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "summer 2026",
			now:  time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC),
			want: time.Date(2026, 3, 29, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "summer before 2026 fall back",
			now:  time.Date(2026, 10, 25, 0, 59, 59, 0, time.UTC),
			want: time.Date(2026, 3, 29, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "exact 2026 fall back instant",
			now:  time.Date(2026, 10, 25, 1, 0, 0, 0, time.UTC),
			want: time.Date(2026, 10, 25, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "after 2027 spring forward (Mar 28)",
			now:  time.Date(2027, 3, 28, 1, 5, 0, 0, time.UTC),
			want: time.Date(2027, 3, 28, 1, 0, 0, 0, time.UTC),
		},
		{
			name: "after 2027 fall back (Oct 31)",
			now:  time.Date(2027, 10, 31, 1, 5, 0, 0, time.UTC),
			want: time.Date(2027, 10, 31, 1, 0, 0, 0, time.UTC),
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := lastPragueDSTTransition(tc.now)
			if !got.Equal(tc.want) {
				t.Fatalf("lastPragueDSTTransition(%s) = %s, want %s", tc.now.Format(time.RFC3339), got.UTC().Format(time.RFC3339), tc.want.Format(time.RFC3339))
			}
		})
	}
}

func TestClockCheckDueMonthlyAndDST(t *testing.T) {
	springBefore := time.Date(2026, 3, 29, 0, 59, 59, 0, time.UTC)
	springAfter := time.Date(2026, 3, 29, 1, 5, 0, 0, time.UTC)
	autumnBefore := time.Date(2026, 10, 25, 0, 59, 59, 0, time.UTC)
	autumnAfter := time.Date(2026, 10, 25, 1, 5, 0, 0, time.UTC)

	cases := []struct {
		name        string
		now         time.Time
		lastChecked string
		retryAfter  string
		want        bool
	}{
		{
			name: "never checked",
			now:  time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC),
			want: true,
		},
		{
			name:        "unparseable lastChecked is due",
			now:         time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC),
			lastChecked: "not-a-timestamp",
			want:        true,
		},
		{
			name:        "7 days elapsed is not due under monthly cadence",
			now:         time.Date(2026, 11, 22, 10, 0, 0, 0, time.UTC),
			lastChecked: "2026-11-15T10:00:00+00:00",
			want:        false,
		},
		{
			name:        "29d23h59m elapsed is not due",
			now:         time.Date(2026, 12, 15, 9, 59, 0, 0, time.UTC),
			lastChecked: "2026-11-15T10:00:00+00:00",
			want:        false,
		},
		{
			name:        "30 days elapsed is due",
			now:         time.Date(2026, 12, 15, 10, 0, 0, 0, time.UTC),
			lastChecked: "2026-11-15T10:00:00+00:00",
			want:        true,
		},
		{
			name:        "1s before spring forward stays on monthly cadence",
			now:         springBefore,
			lastChecked: "2026-03-24T10:00:00+00:00",
			want:        false,
		},
		{
			name:        "5m after spring forward forces immediate sweep",
			now:         springAfter,
			lastChecked: "2026-03-24T10:00:00+00:00",
			want:        true,
		},
		{
			name:        "already checked after spring forward is not due again",
			now:         springAfter.Add(5 * time.Minute),
			lastChecked: iso(springAfter),
			want:        false,
		},
		{
			name:        "1s before fall back stays on monthly cadence",
			now:         autumnBefore,
			lastChecked: "2026-10-20T10:00:00+00:00",
			want:        false,
		},
		{
			name:        "5m after fall back forces immediate sweep",
			now:         autumnAfter,
			lastChecked: "2026-10-20T10:00:00+00:00",
			want:        true,
		},
		{
			name:        "already checked after fall back is not due again",
			now:         autumnAfter.Add(5 * time.Minute),
			lastChecked: iso(autumnAfter),
			want:        false,
		},
		{
			name:        "transient retry backoff holds even across DST boundary",
			now:         springAfter.Add(5 * time.Minute),
			lastChecked: "2026-03-24T10:00:00+00:00",
			retryAfter:  iso(springAfter.Add(24 * time.Hour)),
			want:        false,
		},
		{
			name:        "transient retry backoff opens after 24h",
			now:         springAfter.Add(24 * time.Hour),
			lastChecked: "2026-03-24T10:00:00+00:00",
			retryAfter:  iso(springAfter.Add(24 * time.Hour)),
			want:        true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := clockCheckDue(tc.now, tc.lastChecked, tc.retryAfter); got != tc.want {
				t.Fatalf("clockCheckDue(%s, %q, %q) = %v, want %v", tc.now.Format(time.RFC3339), tc.lastChecked, tc.retryAfter, got, tc.want)
			}
		})
	}
}
