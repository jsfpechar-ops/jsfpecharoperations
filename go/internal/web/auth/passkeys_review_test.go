package auth

// Security review additions for brief 1760: an admin previewing a host acts on
// their own account, and the app host is an accepted origin for the same RP ID.

import (
	"net/http"
	"testing"
)

// An admin who previews bob's workspace adds a passkey to the admin's own
// account, never to bob's (passkeys._owner).
func TestPasskeyRegisterIgnoresImpersonation(t *testing.T) {
	h := newPkHarness(t)
	if _, err := h.pool.Exec(h.ctx, `UPDATE user_account SET role = 'admin' WHERE id = $1`, h.alice); err != nil {
		t.Fatal(err)
	}
	preview := sessionToken(t, pkTestSecret, map[string]int64{"uid": h.alice, "iat": -60, "as": h.bob, "ast": -30}, h.now)
	a := newSoftAuthenticator(t)
	rec := h.registerFor(preview, a, pkOrigin, pkRPID, "Admin key")
	if rec.Code != http.StatusOK {
		t.Fatalf("register while previewing: %d %s", rec.Code, rec.Body.String())
	}
	if n := h.passkeyCount(h.bob); n != 0 {
		t.Errorf("bob has %d passkeys after an admin preview, want 0", n)
	}
	if n := h.passkeyCount(h.alice); n != 1 {
		t.Errorf("admin has %d passkeys, want 1", n)
	}
	var owner int64
	if err := h.pool.QueryRow(h.ctx, `SELECT user_account_id FROM webauthn_challenge ORDER BY id DESC LIMIT 1`).Scan(&owner); err != nil {
		t.Fatal(err)
	}
	if owner != h.alice {
		t.Errorf("challenge bound to account %d, want the admin %d", owner, h.alice)
	}
}

// The app host (app.<public host>) is accepted as an origin: the RP ID stays
// the public host, so a passkey made on one host works on the other.
func TestPasskeyRegisterFromAppHostOrigin(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	rec := h.registerFor(h.aliceS, a, "https://app.ubyhost.example.test", pkRPID, "App host key")
	if rec.Code != http.StatusOK {
		t.Fatalf("register from the app origin: %d %s", rec.Code, rec.Body.String())
	}
	b := newSoftAuthenticator(t)
	rec = h.registerFor(h.aliceS, b, "https://evil.example", pkRPID, "Evil key")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("register from a foreign origin: %d, want 400", rec.Code)
	}
	if n := h.passkeyCount(h.alice); n != 1 {
		t.Errorf("alice has %d passkeys, want 1", n)
	}
}
