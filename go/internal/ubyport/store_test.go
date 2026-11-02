package ubyport

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	storeNow   = "2026-11-01T10:00:00+00:00"
	storeLater = "2026-11-01T10:05:00+00:00"
)

// storeTestCrypto returns a real MultiFernet with a fixed test key and the
// FieldEncrypter that wraps it.
func storeTestCrypto(t *testing.T) (*secure.MultiFernet, FieldEncrypter) {
	t.Helper()
	key := []byte(base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32)))
	mf, err := secure.NewMultiFernet(key)
	if err != nil {
		t.Fatal(err)
	}
	return mf, func(plain string) (string, error) { return mf.Encrypt([]byte(plain)) }
}

// storeDecrypt returns the plain text of an encrypted column read by storeRead.
// "<nil>" (SQL NULL) is returned as it is.
func storeDecrypt(t *testing.T, mf *secure.MultiFernet, token string) string {
	t.Helper()
	if token == "<nil>" {
		return token
	}
	raw, err := mf.Decrypt(token, 0, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}

// storeRead returns the named columns of one row as text. SQL NULL is "<nil>".
func storeRead(t *testing.T, pool *pgxpool.Pool, table string, id int64, cols ...string) map[string]string {
	t.Helper()
	sel := make([]string, len(cols))
	dest := make([]any, len(cols))
	vals := make([]*string, len(cols))
	for i, c := range cols {
		sel[i] = c + "::text"
		dest[i] = &vals[i]
	}
	query := fmt.Sprintf("SELECT %s FROM %s WHERE id = $1", strings.Join(sel, ", "), table)
	if err := pool.QueryRow(context.Background(), query, id).Scan(dest...); err != nil {
		t.Fatal(err)
	}
	out := make(map[string]string, len(cols))
	for i, c := range cols {
		if vals[i] == nil {
			out[c] = "<nil>"
		} else {
			out[c] = *vals[i]
		}
	}
	return out
}

// storeApartmentOf returns the apartment that a seedGuest guest belongs to.
func storeApartmentOf(t *testing.T, pool *pgxpool.Pool, guestID int64) int64 {
	t.Helper()
	var apt int64
	if err := pool.QueryRow(context.Background(),
		`SELECT r.apartment_id FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id = $1`,
		guestID).Scan(&apt); err != nil {
		t.Fatal(err)
	}
	return apt
}

func TestStoreInsertSubmission(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	id, err := InsertSubmission(ctx, pool, storeApartmentOf(t, pool, g1), "auto",
		[]int64{3, 4}, "https://example.test/ubyport", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	row := storeRead(t, pool, "submission", id, "state", "created_at", "guest_ids", "mode", "endpoint")
	want := map[string]string{
		"state":      "running",
		"created_at": storeNow,
		"guest_ids":  "[3, 4]",
		"mode":       "auto",
		"endpoint":   "https://example.test/ubyport",
	}
	for k, v := range want {
		if row[k] != v {
			t.Errorf("%s = %q, want %q", k, row[k], v)
		}
	}
}

func TestStoreOutcomeUnknown(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	mf, enc := storeTestCrypto(t)
	g1 := seedGuest(t, pool)
	g2 := seedGuest(t, pool)
	apt := storeApartmentOf(t, pool, g1)
	sub, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g1, g2}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	envelope := "<Envelope>passport-123</Envelope>"
	if err := RecordOutcomeUnknown(ctx, pool, enc, sub, []int64{g1, g2}, "timeout", envelope, storeLater); err != nil {
		t.Fatal(err)
	}
	row := storeRead(t, pool, "submission", sub, "state", "finished_at", "error_text", "request_xml", "request_xml_enc")
	if row["state"] != "outcome_unknown" || row["finished_at"] != storeLater || row["error_text"] != "timeout" {
		t.Errorf("submission fields = %v", row)
	}
	if row["request_xml"] != "<nil>" {
		t.Errorf("request_xml = %q, want NULL", row["request_xml"])
	}
	if got := storeDecrypt(t, mf, row["request_xml_enc"]); got != envelope {
		t.Errorf("request_xml_enc decrypts to %q, want %q", got, envelope)
	}
	for _, g := range []int64{g1, g2} {
		if got := storeRead(t, pool, "guest", g, "submission_id")["submission_id"]; got != fmt.Sprint(sub) {
			t.Errorf("guest %d submission_id = %q, want %d", g, got, sub)
		}
	}

	empty, err := InsertSubmission(ctx, pool, apt, "auto", []int64{}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if err := RecordOutcomeUnknown(ctx, pool, enc, empty, nil, "timeout", "", storeLater); err != nil {
		t.Fatal(err)
	}
	row = storeRead(t, pool, "submission", empty, "request_xml", "request_xml_enc")
	if row["request_xml"] != "<nil>" || row["request_xml_enc"] != "<nil>" {
		t.Errorf("empty envelope gave request_xml=%q request_xml_enc=%q, want both NULL",
			row["request_xml"], row["request_xml_enc"])
	}
}

func TestStoreTransportError(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	sub, err := InsertSubmission(ctx, pool, storeApartmentOf(t, pool, g1), "auto", []int64{g1}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if err := RecordTransportError(ctx, pool, sub, "connection reset", storeLater); err != nil {
		t.Fatal(err)
	}
	row := storeRead(t, pool, "submission", sub, "state", "finished_at", "error_text")
	if row["state"] != "transport_error" || row["finished_at"] != storeLater || row["error_text"] != "connection reset" {
		t.Errorf("submission fields = %v", row)
	}
	if got := storeRead(t, pool, "guest", g1, "submission_id")["submission_id"]; got != "<nil>" {
		t.Errorf("guest submission_id = %q, want NULL (guests untouched)", got)
	}
}

func TestStoreOutcome(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	mf, enc := storeTestCrypto(t)
	g1 := seedGuest(t, pool)
	g2 := seedGuest(t, pool)
	sub, err := InsertSubmission(ctx, pool, storeApartmentOf(t, pool, g1), "auto", []int64{g1, g2}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	// The refused guest has a submitted_at on file that its write does not carry.
	const priorSubmittedAt = "2026-10-01T00:00:00+00:00"
	if _, err := pool.Exec(ctx,
		`UPDATE guest SET submit_state = 'pending', submitted_at = $1 WHERE id = $2`,
		priorSubmittedAt, g2); err != nil {
		t.Fatal(err)
	}
	guests := []OutcomeGuest{{ID: g1}, {ID: g2}}
	res := SubmitResult{
		RecordErrors: []string{"", "106;"},
		RequestXML:   "<req/>",
		ResponseXML:  "<resp/>",
	}
	plan := PlanOutcome(guests, res, sub, storeLater, nil, nil, func(*int64) *int64 { return nil })
	if err := RecordOutcome(ctx, pool, enc, sub, plan, res, storeLater); err != nil {
		t.Fatal(err)
	}

	for _, w := range plan.GuestWrites {
		cols := make([]string, 0, len(w.Values))
		for k := range w.Values {
			cols = append(cols, k)
		}
		row := storeRead(t, pool, "guest", w.ID, cols...)
		for _, k := range cols {
			if want := fmt.Sprint(w.Values[k]); row[k] != want {
				t.Errorf("guest %d %s = %q, want %q", w.ID, k, row[k], want)
			}
		}
	}
	if got := storeRead(t, pool, "guest", g2, "submitted_at")["submitted_at"]; got != priorSubmittedAt {
		t.Errorf("refused guest submitted_at = %q, want it kept as %q", got, priorSubmittedAt)
	}

	row := storeRead(t, pool, "submission", sub, "state", "finished_at", "header_errors", "record_errors",
		"pseudo_stamp", "receipt_pdf", "error_pdf", "request_xml", "request_xml_enc", "response_xml")
	checks := map[string]string{
		"state":         plan.State,
		"finished_at":   storeLater,
		"header_errors": "",
		"record_errors": `["", "106;"]`,
		"pseudo_stamp":  "",
		"receipt_pdf":   "<nil>",
		"error_pdf":     "<nil>",
		"request_xml":   "<nil>",
		"response_xml":  "<resp/>",
	}
	for k, want := range checks {
		if row[k] != want {
			t.Errorf("submission %s = %q, want %q", k, row[k], want)
		}
	}
	if got := storeDecrypt(t, mf, row["request_xml_enc"]); got != "<req/>" {
		t.Errorf("request_xml_enc decrypts to %q, want %q", got, "<req/>")
	}
}

func TestStoreOutcomeRollsBack(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, enc := storeTestCrypto(t)
	g1 := seedGuest(t, pool)
	g2 := seedGuest(t, pool)
	sub, err := InsertSubmission(ctx, pool, storeApartmentOf(t, pool, g1), "auto", []int64{g1, g2}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'pending' WHERE id = $1`, g1); err != nil {
		t.Fatal(err)
	}
	plan := OutcomePlan{
		State: "failed",
		GuestWrites: []GuestWrite{
			{ID: g1, Values: map[string]any{"submit_state": "sent", "updated_at": storeLater}},
			{ID: g2, Values: map[string]any{"submit_state": "sent", "not_a_column": "x"}},
		},
	}
	if err := RecordOutcome(ctx, pool, enc, sub, plan, SubmitResult{RecordErrors: []string{}}, storeLater); err == nil {
		t.Fatal("want an error for a column outside the allowed list")
	}
	if got := storeRead(t, pool, "guest", g1, "submit_state")["submit_state"]; got != "pending" {
		t.Errorf("first guest submit_state = %q, want unchanged pending", got)
	}
	if got := storeRead(t, pool, "submission", sub, "state")["state"]; got != "running" {
		t.Errorf("submission state = %q, want unchanged running", got)
	}
}

func TestStoreReceiptLookup(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	g2 := seedGuest(t, pool)
	apt := storeApartmentOf(t, pool, g1)
	held, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g1}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	bare, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g2}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE submission SET receipt_pdf = 'JVBERi0' WHERE id = $1`, held); err != nil {
		t.Fatal(err)
	}
	guests := []OutcomeGuest{{ID: g1, SubmissionID: &held}, {ID: g2, SubmissionID: &bare}}
	lookup, err := ReceiptLookup(ctx, pool, guests)
	if err != nil {
		t.Fatal(err)
	}
	if got := lookup(&held); got == nil || *got != held {
		t.Errorf("lookup(held) = %v, want %d", got, held)
	}
	if got := lookup(&bare); got != nil {
		t.Errorf("lookup(no receipt) = %d, want nil", *got)
	}
	if got := lookup(nil); got != nil {
		t.Errorf("lookup(nil) = %d, want nil", *got)
	}
	zero := int64(0)
	if got := lookup(&zero); got != nil {
		t.Errorf("lookup(0) = %d, want nil", *got)
	}
}

func TestPyJSONDumps(t *testing.T) {
	cases := []struct {
		name string
		in   any
		want string
	}{
		{"ints", []int64{3, 4}, "[3, 4]"},
		{"no ints", []int64{}, "[]"},
		{"empty strings", []string{}, "[]"},
		{"strings", []string{"", "106;"}, `["", "106;"]`},
		{"non-ascii and markup", []string{"á", "<x>", "😀"}, `["\u00e1", "<x>", "\ud83d\ude00"]`},
		{"escapes", []string{"a\"b\\c\n"}, `["a\"b\\c\n"]`},
	}
	for _, c := range cases {
		if got := pyJSONDumps(c.in); got != c.want {
			t.Errorf("%s: pyJSONDumps = %s, want %s", c.name, got, c.want)
		}
	}
}
