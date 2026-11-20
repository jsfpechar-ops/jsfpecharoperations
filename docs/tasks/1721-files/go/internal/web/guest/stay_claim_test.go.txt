package guest

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestClaimTokenHash(t *testing.T) {
	secret := "abc"
	want := sha256.Sum256([]byte(secret))
	if claimTokenHash(secret) != hex.EncodeToString(want[:]) {
		t.Fatal("hash mismatch")
	}
}

func TestGuestAccessOpen(t *testing.T) {
	if !guestAccessOpen("active", false) {
		t.Fatal("active open")
	}
	if guestAccessOpen("active", true) || guestAccessOpen("cancelled", false) {
		t.Fatal("locked/cancelled closed")
	}
}

func TestCookieHeldEmpty(t *testing.T) {
	if len(CookieHeld("")) != 0 {
		t.Fatal("empty")
	}
}

type stayClaimGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		Body     string `json:"body"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		BodyHas  string `json:"body_has"`
	} `json:"cases"`
}

func loadStayClaimGolden(t *testing.T) stayClaimGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/stay_claim_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g stayClaimGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestStayClaimGoldenShape(t *testing.T) {
	g := loadStayClaimGolden(t)
	if len(g.Cases) < 4 {
		t.Fatalf("cases %d", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Status == 0 {
			t.Errorf("%s: status", c.Name)
		}
	}
}

func TestConfirmClaimRace(t *testing.T) {
	pool := testPool(t)
	if pool == nil {
		t.Skip("UBYHOST_TEST_DATABASE_URL")
	}
	ctx := context.Background()
	secret, err := newClaimSecret()
	if err != nil {
		t.Fatal(err)
	}
	stamp := isoNow(time.Now().UTC())
	hash := claimTokenHash(secret)
	resID := int64(172101)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at)
		VALUES (172101, 1, 'Flat', 'claimtok', 1, $1) ON CONFLICT (id) DO NOTHING`, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, apartment_id, status, source, date_from, date_to, created_at)
		VALUES ($1, 172101, 'active', 'ical', '2026-06-01', '2026-06-05', $2) ON CONFLICT (id) DO NOTHING`, resID, stamp)
	mustExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
		VALUES ($1, $2, $3, 1, $4, $4) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state, token_hash = EXCLUDED.token_hash`,
		resID, claimStateProvisional, hash, stamp)
	stay := &scStay{id: resID, status: "active"}
	apt := &scApt{id: 172101, token: "claimtok"}
	var wg sync.WaitGroup
	okCh := make(chan bool, 2)
	at := time.Now().UTC()
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ok, err := confirmClaim(ctx, pool, resID, secret, apt, stay, at)
			if err != nil {
				t.Error(err)
				return
			}
			okCh <- ok
		}()
	}
	wg.Wait()
	close(okCh)
	var wins int
	for v := range okCh {
		if v {
			wins++
		}
	}
	if wins != 1 {
		t.Fatalf("race wins %d", wins)
	}
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		return nil
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatal(err)
	}
	return pool
}

func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatal(err)
	}
}
