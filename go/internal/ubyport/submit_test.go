package ubyport

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// batchFakeSender answers with a fixed result or error and counts the calls.
type batchFakeSender struct {
	res   SubmitResult
	err   error
	calls int
}

func (f *batchFakeSender) Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) {
	f.calls++
	return f.res, f.err
}

// batchSetup seeds one apartment with an owner and contact address, one stay and one guest.
func batchSetup(t *testing.T, enc FieldEncrypter) (*pgxpool.Pool, BatchDeps, ApartmentRef, []BatchPair) {
	t.Helper()
	pool := claimTestPool(t)
	ref := notifyApartment(t, pool, ptrString("host@example.test"))
	res, guest := notifyStay(t, pool, ref.ID, "uid-batch-1", "2026-12-01", "2026-12-03")
	d := BatchDeps{
		Pool: pool,
		Enc:  enc,
		Getenv: notifyEnv(map[string]string{
			"UBYHOST_MAIL_BACKEND": "console",
			"UBYHOST_WEB_PUSH":     "1",
		}),
		AppBaseURL:    "https://app.example.test",
		PublicBaseURL: "https://example.test",
		Endpoint:      "https://ubyport.example.test/ws",
		Codebook:      map[string]string{"105": "Missing birth date"},
		Severities:    map[string]int{"105": 9},
		Now:           func() time.Time { return time.Date(2026, 11, 1, 10, 0, 0, 0, time.UTC) },
	}
	pair := BatchPair{
		Guest: Guest{
			Surname:     "Novak",
			FirstName:   "Jan",
			BirthDate:   "1980-01-02",
			Nationality: "CZE",
			DocNumber:   "AB123456",
			ResCountry:  "CZE",
		},
		Reservation: Reservation{DateFrom: "2026-12-01", DateTo: "2026-12-03"},
		Outcome:     OutcomeGuest{ID: guest, ReservationID: &res},
	}
	return pool, d, ref, []BatchPair{pair}
}

var batchApartment = Apartment{UbyIdub: "123", UbyName: "Test flat", UbyMark: "MRK"}

func batchOpenAlert(t *testing.T, pool *pgxpool.Pool, key string) int {
	t.Helper()
	return effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key)
}

func TestSubmitBatchAccepted(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	apt := fmt.Sprintf("submission_transport:%d", ref.ID)
	if err := RaiseAlert(ctx, pool, "critical", "submission_transport", "m", "d", apt, &ref.ID, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if err := RaiseAlert(ctx, pool, "critical", "submission_rejected", "m", "d",
		fmt.Sprintf("submission_rejected:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	sender := &batchFakeSender{res: SubmitResult{RecordErrors: []string{""}, PseudoStamp: "STAMP-1", ReceiptPDF: "PDF"}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "ok" || got.Submitted != 1 || got.SubmissionID == 0 {
		t.Fatalf("result = %+v, want state ok, submitted 1", got)
	}
	if got.Stamp != "STAMP-1" {
		t.Errorf("stamp = %q", got.Stamp)
	}
	if n := batchOpenAlert(t, pool, apt); n != 0 {
		t.Errorf("submission_transport still open: %d", n)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_rejected:%d", ref.ID)); n != 0 {
		t.Errorf("submission_rejected still open: %d", n)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("receipt_missing:%d", ref.ID)); n != 0 {
		t.Errorf("receipt_missing raised though a stamp came back: %d", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM email_outbox`); n != 0 {
		t.Errorf("mail queued for an accepted batch: %d", n)
	}
	if got := effectsText(t, pool, `SELECT state FROM submission WHERE id = $1`, got.SubmissionID); got != "ok" {
		t.Errorf("submission state = %q", got)
	}
	want := fmt.Sprintf("apartment=%d submission=%d state=ok accepted=1 failed=0 blocked=0", ref.ID, got.SubmissionID)
	if detail := effectsText(t, pool, `SELECT detail FROM audit WHERE action = 'ubyport_submit' ORDER BY id DESC LIMIT 1`); detail != want {
		t.Errorf("audit detail = %q, want %q", detail, want)
	}
}

func TestSubmitBatchRejected(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	notifyDevice(t, pool, *ref.OwnerUserID)
	sender := &batchFakeSender{res: SubmitResult{RecordErrors: []string{"105"}}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State == "ok" || got.State == "ok_duplicate" {
		t.Fatalf("state = %q, want a refusal", got.State)
	}
	refused := got.Failed + got.Blocked
	if refused != 1 {
		t.Fatalf("failed+blocked = %d, want 1", refused)
	}
	key := fmt.Sprintf("submission_rejected:%d", ref.ID)
	if n := batchOpenAlert(t, pool, key); n != 1 {
		t.Fatalf("submission_rejected open = %d, want 1", n)
	}
	wantParams := fmt.Sprintf(`{"blocked": %d, "count": 1, "failed": %d, "header": "", "property": %q}`,
		got.Blocked, got.Failed, ref.InternalName)
	if p := effectsText(t, pool, `SELECT params FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key); p != wantParams {
		t.Errorf("params = %s, want %s", p, wantParams)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM email_outbox`); n != 1 {
		t.Errorf("email_outbox rows = %d, want 1", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM push_outbox`); n != 1 {
		t.Errorf("push_outbox rows = %d, want 1", n)
	}
}

func TestSubmitBatchOutcomeUnknown(t *testing.T) {
	mf, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	const envelope = "<Envelope>batch</Envelope>"
	sender := &batchFakeSender{err: &Error{Kind: ErrOutcomeUnknown, Msg: "no answer", RequestXML: envelope}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "outcome_unknown" || got.Error != "no answer" || got.SubmissionID == 0 {
		t.Fatalf("result = %+v", got)
	}
	row := storeRead(t, pool, "submission", got.SubmissionID, "state", "request_xml", "request_xml_enc")
	if row["state"] != "outcome_unknown" {
		t.Errorf("submission state = %q", row["state"])
	}
	if row["request_xml"] != "<nil>" {
		t.Errorf("plain request_xml = %q, want NULL", row["request_xml"])
	}
	if plain := storeDecrypt(t, mf, row["request_xml_enc"]); plain != envelope {
		t.Errorf("stored envelope does not decrypt to the sent envelope")
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM guest WHERE submission_id = $1`, got.SubmissionID); n != 1 {
		t.Errorf("guests pointing at the in-doubt batch = %d, want 1", n)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); n != 1 {
		t.Errorf("submission_outcome_unknown open = %d, want 1", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM email_outbox`); n != 1 {
		t.Errorf("email_outbox rows = %d, want 1", n)
	}
}

func TestSubmitBatchAuthError(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	sender := &batchFakeSender{err: &Error{Kind: ErrAuth, Msg: "login refused"}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "transport_error" {
		t.Fatalf("state = %q", got.State)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_transport:%d", ref.ID)); n != 1 {
		t.Errorf("submission_transport open = %d, want 1", n)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("ubyport_auth_failed:%d", ref.ID)); n != 1 {
		t.Errorf("ubyport_auth_failed open = %d, want 1", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM guest WHERE submission_id = $1`, got.SubmissionID); n != 0 {
		t.Errorf("guests moved by a transport error: %d", n)
	}
}

func TestSubmitBatchTransportError(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	sender := &batchFakeSender{err: &Error{Kind: ErrTransport, Msg: "connection refused"}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "transport_error" || got.Error != "connection refused" {
		t.Fatalf("result = %+v", got)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_transport:%d", ref.ID)); n != 1 {
		t.Errorf("submission_transport open = %d, want 1", n)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("ubyport_auth_failed:%d", ref.ID)); n != 0 {
		t.Errorf("ubyport_auth_failed raised for a non-auth error: %d", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM guest WHERE submission_id = $1`, got.SubmissionID); n != 0 {
		t.Errorf("guests moved by a transport error: %d", n)
	}
}

func TestSubmitBatchAcceptedWithoutReceipt(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	sender := &batchFakeSender{res: SubmitResult{RecordErrors: []string{""}}}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "ok" {
		t.Fatalf("state = %q", got.State)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("receipt_missing:%d", ref.ID)); n != 1 {
		t.Errorf("receipt_missing open = %d, want 1", n)
	}
	want := fmt.Sprintf(`{"count": 1, "property": %q, "submission": %d}`, ref.InternalName, got.SubmissionID)
	if p := effectsText(t, pool, `SELECT params FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`,
		fmt.Sprintf("receipt_missing:%d", ref.ID)); p != want {
		t.Errorf("params = %s, want %s", p, want)
	}
}

func TestSubmitBatchAllDemoIsNoop(t *testing.T) {
	_, enc := storeTestCrypto(t)
	pool, d, ref, pairs := batchSetup(t, enc)
	ctx := context.Background()
	pairs[0].Source = "demo"
	sender := &batchFakeSender{}

	got, err := SubmitBatch(ctx, d, sender, batchApartment, ref, pairs, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if got.State != "noop" || got.SubmissionID != 0 {
		t.Fatalf("result = %+v, want noop", got)
	}
	if sender.calls != 0 {
		t.Errorf("UbyPort called %d times for demo stays", sender.calls)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM submission`); n != 0 {
		t.Errorf("submission rows = %d, want 0", n)
	}
}
