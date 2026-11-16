package ubyport

import (
	"encoding/json"
	"os"
	"testing"
	"time"
)

// Reads the same fixture as App/tests/test_ubyport_transport_golden.py (A1b P1).
type policyFixture struct {
	Now     string `json:"now"`
	Backoff []struct {
		Name string `json:"name"`
		Rows []struct {
			State      string `json:"state"`
			Cause      string `json:"cause"`
			Mode       string `json:"mode"`
			MinutesAgo int    `json:"minutes_ago"`
		} `json:"rows"`
		NextMinutes *int    `json:"next_minutes"`
		NextUTC     *string `json:"next_utc"`
	} `json:"backoff"`
	Faults []struct {
		Cause  string  `json:"cause"`
		Detail string  `json:"detail"`
		Code   *string `json:"code"`
	} `json:"faults"`
}

func TestTransportPolicyMatchesSharedFixture(t *testing.T) {
	raw, err := os.ReadFile("testdata/transport_policy.json")
	if err != nil {
		t.Fatal(err)
	}
	var fx policyFixture
	if err := json.Unmarshal(raw, &fx); err != nil {
		t.Fatal(err)
	}
	now, err := time.Parse(time.RFC3339, fx.Now)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range fx.Backoff {
		var rows []TransportRow
		for _, r := range c.Rows {
			rows = append(rows, TransportRow{
				State: r.State, Cause: r.Cause, Mode: r.Mode,
				FinishedAt: now.Add(-time.Duration(r.MinutesAgo) * time.Minute).Format(time.RFC3339),
			})
		}
		got, owed := TransportBackoffFromRows(rows, now)
		switch {
		case c.NextMinutes != nil:
			if want := now.Add(time.Duration(*c.NextMinutes) * time.Minute); !owed || !got.Equal(want) {
				t.Errorf("%s: got %v owed=%v, want %v", c.Name, got, owed, want)
			}
		case c.NextUTC != nil:
			want, err := time.Parse(time.RFC3339, *c.NextUTC)
			if err != nil {
				t.Fatal(err)
			}
			if !owed || !got.Equal(want) {
				t.Errorf("%s: got %v owed=%v, want %v", c.Name, got, owed, want)
			}
		default:
			if owed {
				t.Errorf("%s: got %v, want no backoff", c.Name, got)
			}
		}
	}
	for _, f := range fx.Faults {
		want := ""
		if f.Code != nil {
			want = *f.Code
		}
		if got := FaultCodeFor(f.Cause, f.Detail); got != want {
			t.Errorf("FaultCodeFor(%q,%q) = %q, want %q", f.Cause, f.Detail, got, want)
		}
	}
}
