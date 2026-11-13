package session

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// These tests need UBYHOST_TEST_DATABASE_URL (testPool skips without it).

func mustAccount(t *testing.T, ctx context.Context, id int64, a *LoginAccount, err error) *LoginAccount {
	t.Helper()
	if err != nil || a == nil || a.ID != id {
		t.Fatalf("account %d: %+v %v", id, a, err)
	}
	return a
}

func TestAccountsDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0)
	id, err := CreateAccount(ctx, pool, " Anna@Example.com ", " Anna ", "host", "", now)
	if err != nil {
		t.Fatal(err)
	}
	got, err := AccountByEmail(ctx, pool, "anna@example.com")
	a := mustAccount(t, ctx, id, got, err)
	if *a.Email != "anna@example.com" || *a.DisplayName != "Anna" || a.SessionVersion != 1 || a.Role != "host" ||
		a.CreatedAt != "2027-01-01T00:00:00+00:00" || !UsernameIsValid(a.Username) {
		t.Fatalf("created row %+v", a)
	}
	got, err = AccountByUsername(ctx, pool, "  "+a.Username+" ")
	mustAccount(t, ctx, id, got, err)
	if got, _ := AccountByEmail(ctx, pool, "ANNA@example.com"); got != nil {
		t.Error("account_by_email is case-sensitive in Python")
	}
	if _, err := CreateAccount(ctx, pool, "x@y", "", "host", strings.ToUpper(a.Username), now); err == nil {
		t.Error("duplicate username accepted") // the unique index refuses it, as in Python
	}
	for _, c := range []struct {
		email, role, user string
		want              error
	}{{"nope", "host", "", ErrEmailInvalid}, {"a@b", "boss", "", ErrUnknownRole}, {"a@b", "host", "x", ErrUsername}} {
		if _, err := CreateAccount(ctx, pool, c.email, "", c.role, c.user, now); err != c.want {
			t.Errorf("%v: %v", c, err)
		}
	}
	if taken, _ := EmailTaken(ctx, pool, "anna@example.com", id); taken {
		t.Error("own address counts as taken")
	}
	if taken, _ := EmailTaken(ctx, pool, "anna@example.com", 0); !taken {
		t.Error("address not taken")
	}
	// SetAccountEmail: replacing an address bumps session_version and spends links.
	tok, err := IssueLoginLink(ctx, pool, a, PurposeLogin, "", false, "", now)
	if err != nil {
		t.Fatal(err)
	}
	if err := SetAccountEmail(ctx, pool, id, "new@example.com", now); err != nil {
		t.Fatal(err)
	}
	b, _ := AccountByID(ctx, pool, id)
	if b.SessionVersion != 2 || *b.Email != "new@example.com" || b.EmailVerifiedAt != nil {
		t.Errorf("after set email %+v", b)
	}
	if row, _ := PeekLoginLink(ctx, pool, tok, nil, now); row != nil {
		t.Error("link survived the address change")
	}
	if err := EndAllSessions(ctx, pool, id); err != nil {
		t.Fatal(err)
	}
	if b, _ = AccountByID(ctx, pool, id); b.SessionVersion != 3 {
		t.Error("EndAllSessions did not bump")
	}
}

func TestLoginLinkDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0)
	id, err := CreateAccount(ctx, pool, "host@example.com", "", "host", "hosty", now)
	if err != nil {
		t.Fatal(err)
	}
	a, _ := AccountByID(ctx, pool, id)
	first, err := IssueLoginLink(ctx, pool, a, PurposeLogin, "", true, "/x", now)
	if err != nil || len(first) != 43 {
		t.Fatalf("token %q %v", first, err)
	}
	second, _ := issueLink(ctx, pool, a, PurposeLogin, " HOST@example.com ", false, "", now, "fixed-token")
	if row, _ := PeekLoginLink(ctx, pool, first, nil, now); row != nil {
		t.Error("older link still live")
	}
	row, err := PeekLoginLink(ctx, pool, second, nil, now)
	if err != nil || row == nil || row.Email != "host@example.com" || *row.NextPath != "/" || row.Remember != 0 ||
		row.TokenHash != linkHash("fixed-token") || row.ExpiresAt != "2027-01-01T00:15:00+00:00" {
		t.Fatalf("row %+v %v", row, err)
	}
	if r, _ := PeekLoginLink(ctx, pool, second, []string{PurposeEmailChange}, now); r != nil {
		t.Error("purpose filter")
	}
	if r, _ := PeekLoginLink(ctx, pool, second, nil, now.Add(15*time.Minute)); r != nil {
		t.Error("expired link live")
	}
	spent, err := ConsumeLoginLink(ctx, pool, second, nil, now)
	if err != nil || spent == nil || spent.ID != row.ID {
		t.Fatalf("consume %v %v", spent, err)
	}
	if again, _ := ConsumeLoginLink(ctx, pool, second, nil, now); again != nil {
		t.Error("link spent twice")
	}
	if acc, _ := AccountForLink(ctx, pool, spent); acc == nil || acc.ID != id {
		t.Error("account_for")
	}
	change := *spent
	change.Purpose = PurposeEmailChange
	if acc, _ := AccountForLink(ctx, pool, &change); acc != nil {
		t.Error("email_change to the same address")
	}
	if _, err := IssueLoginLink(ctx, pool, a, "bogus", "", false, "", now); err == nil {
		t.Error("unknown purpose accepted")
	}
	// Rate limits: 3 per address in 15 minutes.
	for i := range 3 {
		if b, _ := LinkRequestBlocked(ctx, pool, "ip1", "host@example.com", now); b {
			t.Fatalf("blocked after %d", i)
		}
		if err := LinkRecordRequest(ctx, pool, "ip1", "host@example.com", now); err != nil {
			t.Fatal(err)
		}
	}
	if b, _ := LinkRequestBlocked(ctx, pool, "ip2", "host@example.com", now); !b {
		t.Error("fourth request not blocked")
	}
	if b, _ := LinkRequestBlocked(ctx, pool, "ip2", "host@example.com", now.Add(15*time.Minute+time.Second)); b {
		t.Error("window did not slide")
	}
	if b, _ := RateBlocked(ctx, pool, "x", "", 5, 60, now); !b {
		t.Error("empty key must be blocked")
	}
}

func TestSecondFactorDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0)
	id, err := CreateAccount(ctx, pool, "totp@example.com", "", "host", "totpy", now)
	if err != nil {
		t.Fatal(err)
	}
	secret := NewTOTPSecret()
	codes := []string{"AAAA-1111", "BBBB-2222"}
	if err := EnableTOTP(ctx, pool, dbEnv, id, secret, codes); err != nil {
		t.Fatal(err)
	}
	a, _ := AccountByID(ctx, pool, id)
	keys, err := secure.LoadDataKeys(dbEnv)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := keys.Decrypt(*a.TOTPSecretEnc, 0, now)
	if err != nil || string(plain) != secret || a.TOTPEnabled != 1 || a.SessionVersion != 2 ||
		*a.RecoveryCodesHash != recoveryHashesJSON(dbSecret, codes) {
		t.Fatalf("enable_totp row %+v", a)
	}
	code, _ := totpAt(secret, now.Unix()/30+1)
	if ok, err := VerifySecondFactor(ctx, pool, dbEnv, a, " "+code[:3]+" "+code[3:], now); !ok || err != nil {
		t.Fatalf("next-step code refused: %v", err)
	}
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, code, now); ok {
		t.Error("code replayed")
	}
	old, _ := totpAt(secret, now.Unix()/30)
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, old, now); ok {
		t.Error("earlier step accepted after a later one")
	}
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, "１２３４５６", now); ok {
		t.Error("full-width digits accepted")
	}
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, "bbbb 2222", now); !ok {
		t.Error("recovery code refused")
	}
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, "BBBB-2222", now); ok {
		t.Error("recovery code spent twice (stale row)")
	}
	a, _ = AccountByID(ctx, pool, id)
	var left []string
	if err := json.Unmarshal([]byte(*a.RecoveryCodesHash), &left); err != nil || len(left) != 1 ||
		*a.RecoveryCodesHash != pyDumpsList([]string{RecoveryCodeHash(dbSecret, "AAAA-1111")}) {
		t.Errorf("recovery list %q", *a.RecoveryCodesHash)
	}
	if err := StageTOTP(ctx, pool, dbEnv, id, NewTOTPSecret()); err != nil {
		t.Fatal(err)
	}
	a, _ = AccountByID(ctx, pool, id)
	if a.TOTPEnabled != 0 || a.TOTPLastStep != nil || a.SessionVersion != 2 {
		t.Errorf("stage_totp row %+v", a)
	}
	if err := ResetTOTP(ctx, pool, id); err != nil {
		t.Fatal(err)
	}
	a, _ = AccountByID(ctx, pool, id)
	if a.TOTPSecretEnc != nil || a.RecoveryCodesHash != nil || a.SessionVersion != 3 {
		t.Errorf("reset_totp row %+v", a)
	}
	if ok, _ := VerifySecondFactor(ctx, pool, dbEnv, a, "AAAA-1111", now); ok {
		t.Error("recovery code after reset")
	}
}

func TestDeviceDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0)
	id, err := CreateAccount(ctx, pool, "dev@example.com", "", "host", "devvy", now)
	if err != nil {
		t.Fatal(err)
	}
	tok, _ := DeviceToken(dbSecret, id, 1, NewDeviceID(), now)
	if ok, err := TrustedDevice(ctx, pool, dbSecret, tok, "dev@example.com", now); !ok || err != nil {
		t.Fatalf("trusted_device %v", err)
	}
	if ok, _ := TrustedDevice(ctx, pool, dbSecret, tok, "other@example.com", now); ok {
		t.Error("other address trusted")
	}
	if ok, _ := DeviceCookieValid(ctx, pool, dbSecret, tok, now); !ok {
		t.Error("device_cookie_valid")
	}
	if ok, _ := DeviceCookieValid(ctx, pool, dbSecret, tok, now.Add((DeviceMaxAge+1)*time.Second)); ok {
		t.Error("device cookie older than 30 days")
	}
	_ = EndAllSessions(ctx, pool, id)
	if ok, _ := DeviceCookieValid(ctx, pool, dbSecret, tok, now); ok {
		t.Error("device cookie outlived session_version bump")
	}
}
