package calendar

import "testing"

// Pure cause mapping; the DB-backed scenarios (cap plus grace, one mail per
// day, resolve when filed) are still to be written (see the PR description).
func TestFilingStalledCauseOrder(t *testing.T) {
	cases := []struct {
		name   string
		open   map[string]string
		files  bool
		mode   string
		failed bool
		want   string
	}{
		{"no police field", map[string]string{}, false, "scheduled", false, "setup"},
		{"setup alert open", map[string]string{"apartment_setup:1": "critical"}, true, "scheduled", false, "setup"},
		{"login refused", map[string]string{"ubyport_auth_failed:1": "critical"}, true, "scheduled", false, "auth"},
		{"manual mode", map[string]string{}, true, "manual", false, "manual"},
		{"failed send alert", map[string]string{"submission_transport:1": "warning"}, true, "scheduled", false, "failed"},
		{"failed guest row", map[string]string{}, true, "scheduled", true, "failed"},
		{"nothing known", map[string]string{}, true, "scheduled", false, ""},
	}
	for _, c := range cases {
		if got := filingStalledCause(c.open, 1, c.files, c.mode, c.failed); got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
}
