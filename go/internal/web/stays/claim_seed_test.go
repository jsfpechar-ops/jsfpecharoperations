package stays

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

type demoClaimGolden struct {
	Now   string `json:"now"`
	Cases []struct {
		Name   string `json:"name"`
		State  string `json:"state"`
		Email  string `json:"email"`
		Locked bool   `json:"locked"`
		Decl   *int64 `json:"declared_guests"`
		Kind   string `json:"outbox_kind"`
	} `json:"cases"`
}

func loadDemoClaimGolden(t *testing.T) demoClaimGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/demo_claim_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g demoClaimGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestDemoClaimGoldenFile(t *testing.T) {
	g := loadDemoClaimGolden(t)
	if len(g.Cases) < 3 {
		t.Fatalf("cases=%d", len(g.Cases))
	}
}

func TestClaimSeedParity(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC)
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('demo-claim-host','x','host',1,1,$1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, internal_name, active, permalink_token, created_at)
		VALUES ($1,'Demo',1,'tokdemo',$2) RETURNING id`, ownerID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1,'d1','2026-06-20','2026-06-22','active','demo',$2,$2) RETURNING id`, aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	getenv := func(k string) string {
		if k == "PUBLIC_BASE_URL" {
			return "https://ubyhost.example"
		}
		return os.Getenv(k)
	}
	d := ClaimSeedDeps{Pool: pool, Getenv: getenv, Now: func() time.Time { return now }}
	res := SeedReservation{ID: resID, ApartmentID: aptID, Status: "active"}
	apt := SeedApartment{ID: aptID, OwnerUserID: ownerID, Name: "Demo", PermalinkToken: "tokdemo"}
	if _, err := EnsureClaimRow(ctx, pool, resID, now); err != nil {
		t.Fatal(err)
	}
	ok, code, secret, err := StartClaim(ctx, d, res, apt, "guest@example.test", 2, "en", false)
	if err != nil || !ok || code != "" || secret == "" {
		t.Fatalf("start: ok=%v code=%q secret=%q err=%v", ok, code, secret, err)
	}
	row, _ := EnsureClaimRow(ctx, pool, resID, now)
	if row.State != claimStateProvisional {
		t.Fatalf("state=%s", row.State)
	}
	if !ConfirmClaimOK(ctx, d, res, secret, t, pool) {
		t.Fatal("confirm failed")
	}
	row, _ = EnsureClaimRow(ctx, pool, resID, now)
	if row.State != claimStateClaimed {
		t.Fatalf("after confirm state=%s", row.State)
	}
	if err := LockGuestAccess(ctx, pool, resID, now); err != nil {
		t.Fatal(err)
	}
	row, _ = EnsureClaimRow(ctx, pool, resID, now)
	if !row.GuestAccessLocked {
		t.Fatal("not locked")
	}
}

func TestClaimMailOutbox(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	pool := dbPool(t)
	ctx := context.Background()
	stamp := "2026-06-15T14:00:00+00:00"
	var owner int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username,password_hash,role,active,session_version,created_at) VALUES ('claim-mail-owner','x','host',1,1,$1) RETURNING id`, stamp).Scan(&owner); err != nil {
		t.Fatal(err)
	}
	var entity int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (name,owner_user_id,created_at,contact_email) VALUES ('Mail host',$1,$2,' HOST@example.test ') RETURNING id`, owner, stamp).Scan(&entity); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id,internal_name,active,permalink_token,legal_entity_id,created_at) VALUES ($1,'Mail & stay',1,'mailtoken',$2,$3) RETURNING id`, owner, entity, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id,uid,date_from,date_to,status,source,created_at,updated_at) VALUES ($1,'claim-mail-test','2026-06-20','2026-06-22','active','demo',$2,$2) RETURNING id`, aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	getenv := func(k string) string {
		switch k {
		case "PUBLIC_BASE_URL":
			return "https://ubyhost.example"
		case "UBYHOST_DATA_KEYS":
			return "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
		case "UBYHOST_DATA_KEY_LEGACY":
			return "off"
		default:
			return os.Getenv(k)
		}
	}
	d := claimOpsDeps{pool: pool, getenv: getenv, now: func() time.Time { return time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC) }}
	st := &claimStay{id: resID, apartmentID: aptID, status: "active", source: "demo"}
	apt := &claimApt{id: aptID, ownerID: owner, permalink: "mailtoken", name: "Mail & stay", legalEntityID: &entity}
	if err := enqueueClaimStart(ctx, d, st, apt, "guest@example.test", "en", "synthetic-claim-secret", 1, false, stamp); err != nil {
		t.Fatal(err)
	}
	if err := enqueueClaimStart(ctx, d, st, apt, "guest@example.test", "en", "synthetic-claim-secret", 1, false, stamp); err != nil {
		t.Fatal(err)
	}
	if err := enqueueClaimResend(ctx, d, st, apt, "host-resend@example.test", "cs", "synthetic-resend-secret", 2, 2, stamp); err != nil {
		t.Fatal(err)
	}
	key1, key2 := fmt.Sprintf("claim:%d:v1", resID), fmt.Sprintf("claim_resend:%d:v2", resID)
	check := func(key, kind, to string) {
		t.Helper()
		var gotKind, gotTo, subject, payload string
		if err := pool.QueryRow(ctx, `SELECT kind,to_email,subject,payload FROM email_outbox WHERE idempotency_key=$1`, key).Scan(&gotKind, &gotTo, &subject, &payload); err != nil {
			t.Fatal(err)
		}
		if gotKind != kind || gotTo != to || subject == "" {
			t.Fatalf("outbox metadata mismatch kind=%q to=%q subject_empty=%v", gotKind, gotTo, subject == "")
		}
		var parts map[string]any
		if err := json.Unmarshal([]byte(payload), &parts); err != nil {
			t.Fatal(err)
		}
		if parts["reply_to"] != "host@example.test" {
			t.Fatalf("reply_to=%v", parts["reply_to"])
		}
		enc, ok := parts[mail.ClaimSecretPayloadKey].(string)
		if !ok || enc == "" || strings.Contains(payload, "synthetic-") {
			t.Fatal("claim token was not protected in the outbox payload")
		}
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := keys.DecryptField(enc, time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC))
		if err != nil || plain == "" {
			t.Fatal("encrypted claim token did not decrypt")
		}
		if !strings.Contains(parts["text"].(string), claimSecretMarker) || !strings.Contains(parts["html"].(string), claimSecretMarker) {
			t.Fatal("claim marker missing from text or HTML")
		}
		if strings.Contains(parts["html"].(string), "<script") || !strings.Contains(parts["html"].(string), "&amp;") {
			t.Fatal("claim HTML shell escaping missing")
		}
	}
	check(key1, "claim", "guest@example.test")
	check(key2, "claim_resend", "host-resend@example.test")
	var count int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox WHERE idempotency_key=$1`, key1).Scan(&count); err != nil || count != 1 {
		t.Fatalf("replay rows=%d err=%v", count, err)
	}
	var noReplyAptID, noReplyResID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id,internal_name,active,permalink_token,created_at) VALUES ($1,'No reply stay',1,'noreplytoken',$2) RETURNING id`, owner, stamp).Scan(&noReplyAptID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id,uid,date_from,date_to,status,source,created_at,updated_at) VALUES ($1,'claim-mail-no-reply','2026-06-20','2026-06-22','active','demo',$2,$2) RETURNING id`, noReplyAptID, stamp).Scan(&noReplyResID); err != nil {
		t.Fatal(err)
	}
	noReplyApt := &claimApt{id: noReplyAptID, ownerID: owner, permalink: "noreplytoken", name: "No reply stay"}
	noReplyStay := &claimStay{id: noReplyResID, apartmentID: noReplyAptID, status: "active", source: "demo"}
	if err := enqueueClaimStart(ctx, d, noReplyStay, noReplyApt, "noreply@example.test", "en", "synthetic-no-reply-secret", 1, false, stamp); err != nil {
		t.Fatal(err)
	}
	var noReplyPayload string
	if err := pool.QueryRow(ctx, `SELECT payload FROM email_outbox WHERE idempotency_key=$1`, fmt.Sprintf("claim:%d:v1", noReplyResID)).Scan(&noReplyPayload); err != nil {
		t.Fatal(err)
	}
	var noReplyParts map[string]any
	if err := json.Unmarshal([]byte(noReplyPayload), &noReplyParts); err != nil {
		t.Fatal(err)
	}
	if _, exists := noReplyParts["reply_to"]; exists {
		t.Fatal("reply_to present without an eligible host address")
	}
}

func ConfirmClaimOK(ctx context.Context, d ClaimSeedDeps, res SeedReservation, secret string, t *testing.T, pool *pgxpool.Pool) bool {
	t.Helper()
	ok, err := ConfirmClaim(ctx, d, res, secret)
	if err != nil || !ok {
		t.Fatalf("confirm: ok=%v err=%v", ok, err)
	}
	return true
}
