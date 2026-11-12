package calendar

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

type watchdogRunEmail struct {
	IdempotencyKey string  `json:"idempotency_key"`
	Kind           string  `json:"kind"`
	ReservationID  *int64  `json:"reservation_id"`
	ApartmentID    *int64  `json:"apartment_id"`
	OwnerUserID    *int64  `json:"owner_user_id"`
	ToEmail        string  `json:"to_email"`
	CCEmail        *string `json:"cc_email"`
	Subject        string  `json:"subject"`
	Payload        string  `json:"payload"`
	Text           string  `json:"text"`
	State          string  `json:"state"`
	Attempts       int64   `json:"attempts"`
}

type watchdogRunPush struct {
	IdempotencyKey string            `json:"idempotency_key"`
	SubscriptionID int64             `json:"subscription_id"`
	UserAccountID  int64             `json:"user_account_id"`
	Kind           string            `json:"kind"`
	Params         map[string]string `json:"params"`
	URL            string            `json:"url"`
	State          string            `json:"state"`
	Attempts       int64             `json:"attempts"`
}

type watchdogRunResult struct {
	AtRisk        int `json:"at_risk"`
	UnknownRisk   int `json:"unknown_risk"`
	AwaitingRetry int `json:"awaiting_retry"`
	HostMails     int `json:"host_mails"`
	Digest        int `json:"digest"`
}

type watchdogRunStep struct {
	At        string             `json:"at"`
	Before    map[string]string  `json:"before"`
	Result    watchdogRunResult  `json:"result"`
	Heartbeat string             `json:"heartbeat"`
	Emails    []watchdogRunEmail `json:"emails"`
	Pushes    []watchdogRunPush  `json:"pushes"`
	Mailed    map[string]*string `json:"mailed"`
	Setting   *string            `json:"setting"`
}

type watchdogBuilderRow struct {
	Workspace string `json:"workspace"`
	Property  string `json:"property"`
	Arrival   string `json:"arrival"`
	Deadline  string `json:"deadline"`
	Unfiled   int    `json:"unfiled"`
}

type watchdogBuilder struct {
	Name       string               `json:"name"`
	Stays      []watchdogBuilderRow `json:"stays"`
	Unknown    []watchdogBuilderRow `json:"unknown"`
	Subject    string               `json:"subject"`
	Text       string               `json:"text"`
	HTMLSHA256 string               `json:"html_sha256"`
}

type watchdogRunGolden struct {
	Env      map[string]string `json:"env"`
	Unset    string            `json:"unset"`
	Seed     []watchSeedTable  `json:"seed"`
	Runs     []watchdogRunStep `json:"runs"`
	Builders []watchdogBuilder `json:"builders"`
	Contacts []struct {
		Raw    string `json:"raw"`
		Python string `json:"python"`
	} `json:"contacts"`
}

func loadWatchdogRunGolden(t *testing.T) watchdogRunGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/filing_watchdog_run_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchdogRunGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) < 10 || len(g.Seed) == 0 || len(g.Builders) < 2 {
		t.Fatal("golden file has too few runs or builders, or no seed")
	}
	return g
}

func sha256Hex(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

// watchdogApply is the golden script's _apply: the digest setting and the
// environment the run reads.
func watchdogApply(t *testing.T, pool *pgxpool.Pool, env map[string]string, unset string, before map[string]string) {
	t.Helper()
	ctx := context.Background()
	if v, ok := before["setting"]; ok {
		var err error
		if v == unset {
			_, err = pool.Exec(ctx, `DELETE FROM settings WHERE key = $1`, watchdogDigestSetting)
		} else {
			_, err = pool.Exec(ctx, `INSERT INTO settings (key, value) VALUES ($1, $2)
				ON CONFLICT(key) DO UPDATE SET value = excluded.value`, watchdogDigestSetting, v)
		}
		if err != nil {
			t.Fatal(err)
		}
	}
	if v, ok := before["mail_backend"]; ok {
		env["UBYHOST_MAIL_BACKEND"] = v
	}
	if v, ok := before["operator_email"]; ok {
		env["UBYHOST_OPERATOR_EMAIL"] = v
	}
}

func watchdogNewEmails(t *testing.T, pool *pgxpool.Pool, seen map[string]bool) []watchdogRunEmail {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email,
		cc_email, subject, payload, state, attempts FROM email_outbox ORDER BY idempotency_key`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []watchdogRunEmail{}
	for rows.Next() {
		var e watchdogRunEmail
		if err := rows.Scan(&e.IdempotencyKey, &e.Kind, &e.ReservationID, &e.ApartmentID, &e.OwnerUserID,
			&e.ToEmail, &e.CCEmail, &e.Subject, &e.Payload, &e.State, &e.Attempts); err != nil {
			t.Fatal(err)
		}
		if seen[e.IdempotencyKey] {
			continue
		}
		seen[e.IdempotencyKey] = true
		var payload struct {
			Text string `json:"text"`
		}
		if err := json.Unmarshal([]byte(e.Payload), &payload); err != nil {
			t.Fatal(err)
		}
		e.Text = payload.Text
		e.Payload = sha256Hex(e.Payload)
		out = append(out, e)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogNewPushes(t *testing.T, pool *pgxpool.Pool, seen map[string]bool) []watchdogRunPush {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT idempotency_key, subscription_id, user_account_id, kind, params, url, state, attempts
		FROM push_outbox ORDER BY idempotency_key`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []watchdogRunPush{}
	for rows.Next() {
		var p watchdogRunPush
		var params string
		if err := rows.Scan(&p.IdempotencyKey, &p.SubscriptionID, &p.UserAccountID, &p.Kind, &params,
			&p.URL, &p.State, &p.Attempts); err != nil {
			t.Fatal(err)
		}
		if seen[p.IdempotencyKey] {
			continue
		}
		seen[p.IdempotencyKey] = true
		if err := json.Unmarshal([]byte(params), &p.Params); err != nil {
			t.Fatal(err)
		}
		out = append(out, p)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogMailed(t *testing.T, pool *pgxpool.Pool) map[string]*string {
	t.Helper()
	rows, err := pool.Query(context.Background(), `SELECT id, at_risk_mailed_at FROM reservation ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := map[string]*string{}
	for rows.Next() {
		var id int64
		var stamp *string
		if err := rows.Scan(&id, &stamp); err != nil {
			t.Fatal(err)
		}
		out[strconv.FormatInt(id, 10)] = stamp
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func watchdogSetting(t *testing.T, pool *pgxpool.Pool) *string {
	t.Helper()
	var v *string
	err := pool.QueryRow(context.Background(), `SELECT value FROM settings WHERE key = $1`, watchdogDigestSetting).Scan(&v)
	if err != nil {
		return nil
	}
	return v
}

func watchdogDiff(t *testing.T, label string, got, want any) {
	t.Helper()
	a, b := watchdogJSON(t, got), watchdogJSON(t, want)
	if a != b {
		t.Errorf("%s differs from Python\n got:\n%s\nwant:\n%s", label, a, b)
	}
}

// TestRunFilingWatchdogMatchesPython seeds the golden rows and replays every
// golden run in order: the result, the heartbeat URL, the mail and push rows
// each run added (payload by sha256), every at_risk_mailed_at and the digest
// setting must be what filing_watchdog.run left.
func TestRunFilingWatchdogMatchesPython(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	env := map[string]string{}
	for k, v := range g.Env {
		env[k] = v
	}
	getenv := watchdogGetenv(env)
	lookup := watchdogLookup(env)
	pool := dbPool(t)
	watchSeed(t, pool, watchGolden{Seed: g.Seed})
	seenMail, seenPush := map[string]bool{}, map[string]bool{}
	for i, run := range g.Runs {
		label := run.At
		watchdogApply(t, pool, env, g.Unset, run.Before)
		at, err := time.Parse(time.RFC3339, run.At)
		if err != nil {
			t.Fatal(err)
		}
		res, err := RunFilingWatchdog(context.Background(), pool, lookup, at)
		if err != nil {
			t.Fatalf("run %d (%s): %v", i+1, label, err)
		}
		got := watchdogRunResult{res.AtRisk, res.UnknownRisk, res.AwaitingRetry, res.HostMails, res.Digest}
		watchdogDiff(t, label+" result", got, run.Result)
		if hb := FilingHeartbeatURL(getenv, res.AtRisk > 0); hb != run.Heartbeat {
			t.Errorf("%s heartbeat %q, Python %q", label, hb, run.Heartbeat)
		}
		wantEmails := run.Emails
		if wantEmails == nil {
			wantEmails = []watchdogRunEmail{}
		}
		watchdogDiff(t, label+" emails", watchdogNewEmails(t, pool, seenMail), wantEmails)
		wantPushes := run.Pushes
		if wantPushes == nil {
			wantPushes = []watchdogRunPush{}
		}
		watchdogDiff(t, label+" pushes", watchdogNewPushes(t, pool, seenPush), wantPushes)
		if m := watchdogMailed(t, pool); !reflect.DeepEqual(m, run.Mailed) {
			watchdogDiff(t, label+" at_risk_mailed_at", m, run.Mailed)
		}
		watchdogDiff(t, label+" digest setting", watchdogSetting(t, pool), run.Setting)
	}
}

func watchdogBuilderRows(in []watchdogBuilderRow) []mail.DigestRow {
	out := []mail.DigestRow{}
	for _, r := range in {
		out = append(out, mail.DigestRow{Workspace: r.Workspace, Property: r.Property,
			Arrival: r.Arrival, Deadline: r.Deadline, Unfiled: r.Unfiled})
	}
	return out
}

// TestBuildDeadlineDigestMatchesPython needs no database: the digest for
// inputs no run reaches (more than 50 rows, unknown stays only).
func TestBuildDeadlineDigestMatchesPython(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	names := []string{}
	for _, b := range g.Builders {
		names = append(names, b.Name)
		c, err := mail.BuildDeadlineDigest(g.Env["UBYHOST_PUBLIC_BASE_URL"], "en",
			watchdogBuilderRows(b.Stays), watchdogBuilderRows(b.Unknown))
		if err != nil {
			t.Fatal(err)
		}
		if c.Subject != b.Subject {
			t.Errorf("%s subject %q, Python %q", b.Name, c.Subject, b.Subject)
		}
		if c.Text != b.Text {
			t.Errorf("%s text differs\n got:\n%s\nwant:\n%s", b.Name, c.Text, b.Text)
		}
		if h := sha256Hex(c.HTML); h != b.HTMLSHA256 {
			t.Errorf("%s html sha256 %s, Python %s", b.Name, h, b.HTMLSHA256)
		}
	}
	sort.Strings(names)
	if strings.Join(names, ",") != "digest_at_risk_only,digest_overflow,digest_unknown_only" {
		t.Errorf("builder cases %v", names)
	}
}

// TestWatchdogAddressNeverDivergesSilently needs no database: for every
// contact form in the golden, Go gives Python's address, or none with the value
// flagged unreadable (logged at error level, the stay left unmailed). Go never
// mails an address Python would not, and a blank value is not flagged.
func TestWatchdogAddressNeverDivergesSilently(t *testing.T) {
	g := loadWatchdogRunGolden(t)
	if len(g.Contacts) < 25 {
		t.Fatal("golden file has too few contact forms")
	}
	same, flagged := 0, 0
	for _, c := range g.Contacts {
		got, unreadable := watchdogAddress(c.Raw)
		blank := strings.TrimSpace(c.Raw) == ""
		switch {
		case got != "" && got == c.Python && !unreadable:
			same++
		case got == "" && unreadable && !blank:
			flagged++
		case got == "" && c.Python == "" && blank && !unreadable:
		default:
			t.Errorf("contact %q: Go %q (unreadable %v), Python %q", c.Raw, got, unreadable, c.Python)
		}
	}
	if same != 19 || flagged != 20 {
		t.Errorf("%d forms read like Python and %d flagged, want 19 and 20", same, flagged)
	}
	t.Logf("%d forms read like Python, %d flagged and logged", same, flagged)
}

// TestRunFilingWatchdogRefusesBadSweepMinutes needs no database: Python's
// int() refuses the value at start-up, so the Go pass fails before any query.
func TestRunFilingWatchdogRefusesBadSweepMinutes(t *testing.T) {
	env := map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": "abc"}
	_, err := RunFilingWatchdog(context.Background(), nil, watchdogLookup(env), time.Now())
	if err == nil || !strings.Contains(err.Error(), "UBYHOST_SUBMIT_SWEEP_MINUTES") {
		t.Fatalf("got %v, want an error naming UBYHOST_SUBMIT_SWEEP_MINUTES", err)
	}
}
