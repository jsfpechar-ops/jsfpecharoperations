package ubyport

import (
	"context"
	"fmt"
	"testing"
	"time"
)

// The same table as App/tests/test_ubyport_transport_retry.py (A1b P1).
var backoffNow = time.Date(2026, 11, 16, 12, 0, 0, 0, time.UTC)

func tr(minutesAgo int) TransportRow {
	t := backoffNow.Add(-time.Duration(minutesAgo) * time.Minute)
	return TransportRow{State: "transport_error", Cause: "dial", FinishedAt: t.Format(time.RFC3339)}
}

func TestTransportBackoffGaps10_30_60(t *testing.T) {
	cases := []struct {
		name string
		rows []TransportRow
		want time.Duration
	}{
		{"n1", []TransportRow{tr(5)}, 5 * time.Minute},
		{"n2", []TransportRow{tr(5), tr(40)}, 25 * time.Minute},
		{"n3", []TransportRow{tr(5), tr(40), tr(90)}, 55 * time.Minute},
		{"n5", []TransportRow{tr(5), tr(40), tr(90), tr(150), tr(200)}, 55 * time.Minute},
	}
	for _, tc := range cases {
		got, ok := TransportBackoffFromRows(tc.rows, backoffNow)
		if !ok || !got.Equal(backoffNow.Add(tc.want)) {
			t.Errorf("%s: got %v ok=%v, want %v", tc.name, got, ok, backoffNow.Add(tc.want))
		}
	}
}

func TestTransportDailyCapMovesNextTryToNextDay(t *testing.T) {
	var twentyFour, twentyThree, manual []TransportRow
	for m := 1; m <= 24; m++ {
		twentyFour = append(twentyFour, tr(m))
		r := tr(m)
		r.Mode = "manual_bulk"
		manual = append(manual, r)
		if m <= 23 {
			twentyThree = append(twentyThree, tr(m))
		}
	}
	// 23:10 UTC on 16 November is 00:10 Prague on 17 November.
	got, _ := TransportBackoffFromRows(twentyFour, backoffNow)
	if want := time.Date(2026, 11, 16, 23, 10, 0, 0, time.UTC); !got.Equal(want) {
		t.Errorf("cap: got %v, want %v", got, want)
	}
	got, _ = TransportBackoffFromRows(twentyThree, backoffNow)
	if want := backoffNow.Add(59 * time.Minute); !got.Equal(want) {
		t.Errorf("23 rows: got %v, want %v", got, want)
	}
	// Manual rows never count toward the cap, so the n=24 gap (60 min) applies.
	got, _ = TransportBackoffFromRows(manual, backoffNow)
	if want := backoffNow.Add(59 * time.Minute); !got.Equal(want) {
		t.Errorf("manual rows: got %v, want %v", got, want)
	}
}

func TestTransportChainResetsAndAuthIsNotBackedOff(t *testing.T) {
	ok := TransportRow{State: "ok", FinishedAt: backoffNow.Add(-10 * time.Minute).Format(time.RFC3339)}
	if got, _ := TransportBackoffFromRows([]TransportRow{tr(5), ok, tr(20)}, backoffNow); !got.Equal(backoffNow.Add(5 * time.Minute)) {
		t.Errorf("reset: got %v", got)
	}
	auth := TransportRow{State: "transport_error", Cause: "auth", FinishedAt: backoffNow.Add(-5 * time.Minute).Format(time.RFC3339)}
	if _, owed := TransportBackoffFromRows([]TransportRow{auth}, backoffNow); owed {
		t.Error("auth at the head must not be backed off as transport")
	}
	if got, _ := TransportBackoffFromRows([]TransportRow{tr(5), {State: "transport_error", Cause: "auth", FinishedAt: backoffNow.Add(-10 * time.Minute).Format(time.RFC3339)}}, backoffNow); !got.Equal(backoffNow.Add(5 * time.Minute)) {
		t.Errorf("auth ends the chain: got %v", got)
	}
	if got, owed := TransportBackoffFromRows([]TransportRow{{State: "transport_error", FinishedAt: ""}}, backoffNow); !owed || !got.Equal(backoffNow.Add(10*time.Minute)) {
		t.Errorf("malformed finished_at must fail closed: got %v owed=%v", got, owed)
	}
}

func TestFaultCodeFor(t *testing.T) {
	cases := map[[2]string]string{
		{"http4xx", "HTTP 404"}:       "http_404",
		{"redirect", "HTTP 302"}:      "http_302",
		{"fault", "clean fault text"}: "",
		{"dial", ""}:                  "",
	}
	for in, want := range cases {
		if got := FaultCodeFor(in[0], in[1]); got != want {
			t.Errorf("FaultCodeFor(%q,%q) = %q, want %q", in[0], in[1], got, want)
		}
	}
}

func TestTransportErrorStoresCauseAndErrorCode(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	aptID := storeApartmentOf(t, pool, g1)
	sub, err := InsertSubmission(ctx, pool, aptID, "auto", []int64{g1}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if err := RecordTransportError(ctx, pool, sub, "HTTP 404", storeLater, "http4xx", FaultCodeFor("http4xx", "HTTP 404")); err != nil {
		t.Fatal(err)
	}
	row := storeRead(t, pool, "submission", sub, "cause", "error_code")
	if row["cause"] != "http4xx" || row["error_code"] != "http_404" {
		t.Errorf("http4xx: got %v", row)
	}
	dial, err := InsertSubmission(ctx, pool, aptID, "auto", []int64{g1}, "ep", storeNow)
	if err != nil {
		t.Fatal(err)
	}
	if err := RecordTransportError(ctx, pool, dial, "connection reset", storeLater, "dial", ""); err != nil {
		t.Fatal(err)
	}
	row = storeRead(t, pool, "submission", dial, "cause", "error_code")
	if row["cause"] != "dial" || row["error_code"] != "<nil>" {
		t.Errorf("dial: got %v, want error_code NULL", row)
	}
}

func TestTransportEscalationMailOnceAtThree(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	aptID := storeApartmentOf(t, pool, g1)
	// The mail goes to the legal entity's contact address; without one nothing is queued.
	var entity int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO legal_entity (name, vat_status, invoice_due_days, business_type, created_at, contact_email)
		 VALUES ('Escalation s.r.o.', 'none', 14, 'company', $1, 'contact@example.test') RETURNING id`,
		storeNow).Scan(&entity); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE apartment SET legal_entity_id = $1 WHERE id = $2`, entity, aptID); err != nil {
		t.Fatal(err)
	}
	apt, err := LoadApartment(ctx, pool, aptID)
	if err != nil || apt == nil {
		t.Fatal("apartment not loaded")
	}
	d := BatchDeps{
		Pool: pool,
		Getenv: func(k string) string {
			if k == "UBYHOST_MAIL_BACKEND" {
				return "console"
			}
			return ""
		},
		AppBaseURL:    "https://app.example.test",
		PublicBaseURL: "https://example.test",
	}
	keyCount := func(key string) int {
		var n int
		if err := pool.QueryRow(ctx, "SELECT count(*) FROM email_outbox WHERE idempotency_key = $1", key).Scan(&n); err != nil {
			t.Fatal(err)
		}
		return n
	}
	var subs []int64
	for i := 1; i <= 3; i++ {
		sub, err := InsertSubmission(ctx, pool, aptID, "auto", []int64{g1}, "ep", storeNow)
		if err != nil {
			t.Fatal(err)
		}
		if err := RecordTransportError(ctx, pool, sub, "connection reset", storeLater, "dial", ""); err != nil {
			t.Fatal(err)
		}
		subs = append(subs, sub)
		escalateTransportChain(ctx, d, apt.Ref, sub, "connection reset", "dial")
		if i < 3 && keyCount(keyOf(sub)) != 0 {
			t.Errorf("chain %d: mail queued before the third failure", i)
		}
	}
	if n := keyCount(keyOf(subs[2])); n != 1 {
		t.Errorf("third failure: %d mails, want 1", n)
	}
	escalateTransportChain(ctx, d, apt.Ref, subs[2], "connection reset", "dial")
	if n := keyCount(keyOf(subs[2])); n != 1 {
		t.Errorf("repeat call: %d mails, want still 1", n)
	}
}

func keyOf(sub int64) string {
	return fmt.Sprintf("submission_transport_repeated:%d", sub)
}

func TestManualModesBypassTheTransportGate(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	aptID := storeApartmentOf(t, pool, g1)
	now := time.Now().UTC()
	for i := 0; i < 2; i++ {
		sub, err := InsertSubmission(ctx, pool, aptID, "auto", []int64{g1}, "ep", storeNow)
		if err != nil {
			t.Fatal(err)
		}
		if err := RecordTransportError(ctx, pool, sub, "connection reset", now.Format(time.RFC3339), "dial", ""); err != nil {
			t.Fatal(err)
		}
	}
	until, owed, err := TransportBackoffUntil(ctx, pool, aptID, now)
	if err != nil || !owed || !until.After(now) {
		t.Fatalf("automatic path: until=%v owed=%v err=%v, want a backoff in force", until, owed, err)
	}
	for _, m := range []string{"manual", "manual_bulk", "manual_resend"} {
		if !isManualMode(m) {
			t.Errorf("%s must bypass the gate", m)
		}
	}
	for _, m := range []string{"auto", "completion_immediate", "auto_resend"} {
		if isManualMode(m) {
			t.Errorf("%s must not bypass the gate", m)
		}
	}
}

func TestTransportCapAcrossDSTChanges(t *testing.T) {
	cases := []struct{ now, want time.Time }{
		{time.Date(2026, 10, 25, 12, 0, 0, 0, time.UTC), time.Date(2026, 10, 25, 23, 10, 0, 0, time.UTC)},
		{time.Date(2026, 3, 29, 12, 0, 0, 0, time.UTC), time.Date(2026, 3, 29, 22, 10, 0, 0, time.UTC)},
	}
	for _, c := range cases {
		var rows []TransportRow
		for m := 1; m <= 24; m++ {
			rows = append(rows, TransportRow{State: "transport_error", Cause: "dial", Mode: "auto",
				FinishedAt: c.now.Add(-time.Duration(m) * time.Minute).Format(time.RFC3339)})
		}
		got, owed := TransportBackoffFromRows(rows, c.now)
		if !owed || !got.Equal(c.want) {
			t.Errorf("now %v: got %v owed=%v, want %v", c.now, got, owed, c.want)
		}
	}
}

func TestAutoResendIsNotHeldByTheBackoff(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	aptID := storeApartmentOf(t, pool, g1)
	now := time.Now().UTC()
	for i := 0; i < 3; i++ {
		sub, err := InsertSubmission(ctx, pool, aptID, "auto", []int64{g1}, "ep", storeNow)
		if err != nil {
			t.Fatal(err)
		}
		if err := RecordTransportError(ctx, pool, sub, "connection reset", now.Format(time.RFC3339), "dial", ""); err != nil {
			t.Fatal(err)
		}
	}
	if held, err := transportGateHolds(ctx, pool, aptID, "auto", now); err != nil || !held {
		t.Fatalf("auto: held=%v err=%v, want held", held, err)
	}
	for _, mode := range []string{autoResendMode, "manual", "manual_bulk"} {
		if held, err := transportGateHolds(ctx, pool, aptID, mode, now); err != nil || held {
			t.Errorf("%s: held=%v err=%v, want not held", mode, held, err)
		}
	}
}
