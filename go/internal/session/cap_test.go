package session

import (
	"context"
	"testing"
	"time"
)

// TestVerifyMatchesPythonReads runs the auth.json read cases (written by
// App/scripts/auth_golden.py from auth._session_payload) through Verify,
// which Load uses (brief 1281).
func TestVerifyMatchesPythonReads(t *testing.T) {
	g := loadAuthGolden(t)
	if len(g.Reads) == 0 {
		t.Fatal("no read cases")
	}
	for _, c := range g.Reads {
		if _, ok := Verify(g.Secret, c.Token, time.Unix(c.At, 0)); ok != c.OK {
			t.Errorf("%s: Verify ok=%v, Python %v", c.Name, ok, c.OK)
		}
	}
}

// TestLoadSessionCapDatabase: Load refuses remember-me cookies past 30 days
// sliding or 90 days absolute, as current_user does.
func TestLoadSessionCapDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version)
		VALUES (2, 'host01', 'x', '2026-01-01T00:00:00+00:00', 'host', 1, 1)`); err != nil {
		t.Fatal(err)
	}
	base := time.Unix(1798761600, 0)
	opt := IssueOptions{Remember: true}
	tok, err := IssueSession(dbSecret, 2, 1, opt, base)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		at   time.Duration
		want bool
	}{{29 * 24 * time.Hour, true}, {30*24*time.Hour + time.Second, false}, {400 * 24 * time.Hour, false}} {
		h, err := Load(ctx, pool, tok, base.Add(c.at), dbEnv)
		if err != nil || (h != nil) != c.want {
			t.Errorf("remember cookie at %v: host %v err %v", c.at, h != nil, err)
		}
	}
	iat := base.Unix()
	opt.IssuedAt = &iat
	late, err := IssueSession(dbSecret, 2, 1, opt, base.Add(80*24*time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if h, _ := Load(ctx, pool, late, base.Add(90*24*time.Hour), dbEnv); h == nil {
		t.Error("refreshed cookie refused at 90 days from iat")
	}
	if h, _ := Load(ctx, pool, late, base.Add(90*24*time.Hour+time.Second), dbEnv); h != nil {
		t.Error("cookie accepted past 90 days from iat")
	}
}
