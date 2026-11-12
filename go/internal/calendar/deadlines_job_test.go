package calendar

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// deadlinesFake records what runDeadlines called, in order.
type deadlinesFake struct {
	calls    []string
	checkErr error
	dsrErr   error
	wdErr    error
	wd       WatchdogResult
	url      string
}

func (f *deadlinesFake) steps() deadlinesSteps {
	return deadlinesSteps{
		check: func() (int, error) {
			f.calls = append(f.calls, "check")
			return 2, f.checkErr
		},
		dsrDue: func() (int, error) {
			f.calls = append(f.calls, "dsr")
			return 1, f.dsrErr
		},
		watchdog: func() (WatchdogResult, error) {
			f.calls = append(f.calls, "watchdog")
			return f.wd, f.wdErr
		},
		raiseFailed: func() error {
			f.calls = append(f.calls, "failed")
			return nil
		},
		ping: func(url string) { f.calls = append(f.calls, "ping "+url) },
		getenv: func(name string) string {
			if name == "UBYHOST_HEARTBEAT_FILING_URL" {
				return f.url
			}
			return ""
		},
	}
}

// TestRunDeadlinesOrderMatchesPython walks every branch of _job_deadlines.
func TestRunDeadlinesOrderMatchesPython(t *testing.T) {
	boom := errors.New("boom")
	cases := []struct {
		name    string
		fake    deadlinesFake
		calls   string
		wantErr bool
	}{
		{"all well", deadlinesFake{url: "https://hb.example/f"},
			"check,dsr,watchdog,ping https://hb.example/f", false},
		{"at risk pings fail", deadlinesFake{url: "https://hb.example/f/", wd: WatchdogResult{AtRisk: 1}},
			"check,dsr,watchdog,ping https://hb.example/f/fail", false},
		{"no heartbeat url", deadlinesFake{},
			"check,dsr,watchdog", false},
		{"check fails skips dsr", deadlinesFake{url: "https://hb.example/f", checkErr: boom},
			"check,failed,watchdog,ping https://hb.example/f/fail", true},
		{"dsr fails", deadlinesFake{url: "https://hb.example/f", dsrErr: boom},
			"check,dsr,failed,watchdog,ping https://hb.example/f/fail", true},
		{"watchdog fails, no ping", deadlinesFake{url: "https://hb.example/f", wdErr: boom},
			"check,dsr,watchdog,failed", true},
		{"both fail, no ping", deadlinesFake{url: "https://hb.example/f", checkErr: boom, wdErr: boom},
			"check,failed,watchdog,failed", true},
	}
	for _, c := range cases {
		f := c.fake
		_, err := runDeadlines(f.steps())
		if got := strings.Join(f.calls, ","); got != c.calls {
			t.Errorf("%s: calls %q, want %q", c.name, got, c.calls)
		}
		if (err != nil) != c.wantErr {
			t.Errorf("%s: error %v, want error %v", c.name, err, c.wantErr)
		}
	}
}

func TestRunDeadlinesSummary(t *testing.T) {
	f := deadlinesFake{wd: WatchdogResult{AtRisk: 3, Digest: 1}}
	sum, err := runDeadlines(f.steps())
	if err != nil {
		t.Fatal(err)
	}
	want := DeadlinesSummary{Alerts: 2, RequestsDue: 1, Watchdog: WatchdogResult{AtRisk: 3, Digest: 1}}
	if sum != want {
		t.Fatalf("summary %+v, want %+v", sum, want)
	}
}

// TestRunDeadlinesJobOnDatabase runs the real passes on an empty schema, then
// with the request table gone: the watchdog still runs, the heartbeat goes to
// /fail and the critical job_failed alert is open, as in Python.
func TestRunDeadlinesJobOnDatabase(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	env := map[string]string{"UBYHOST_HEARTBEAT_FILING_URL": "https://hb.example/f"}
	lookup := func(name string) (string, bool) {
		v, ok := env[name]
		return v, ok
	}
	var pinged []string
	ping := func(url string) { pinged = append(pinged, url) }
	at := time.Date(2026, 11, 12, 9, 0, 0, 0, time.UTC)
	sum, err := RunDeadlinesJob(ctx, pool, lookup, at, ping)
	if err != nil {
		t.Fatalf("empty run: %v", err)
	}
	if sum != (DeadlinesSummary{}) {
		t.Fatalf("empty run summary %+v, want zero", sum)
	}
	if _, err := pool.Exec(ctx, "DROP TABLE data_subject_request CASCADE"); err != nil {
		t.Fatal(err)
	}
	if _, err := RunDeadlinesJob(ctx, pool, lookup, at, ping); err == nil {
		t.Fatal("run without the request table returned no error")
	}
	if strings.Join(pinged, ",") != "https://hb.example/f,https://hb.example/f/fail" {
		t.Fatalf("pings %v, want the plain URL then /fail", pinged)
	}
	var level, message string
	if err := pool.QueryRow(ctx,
		"SELECT level, message FROM alert WHERE dedupe_key = 'job_failed:deadlines' AND resolved_at IS NULL").Scan(&level, &message); err != nil {
		t.Fatal(err)
	}
	if level != "critical" || message != "Background job 'deadline watch' failed." {
		t.Fatalf("alert %q %q, want critical and the English deadlines name", level, message)
	}
}
