package hostweb

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

type dashGolden struct {
	Seed  []seedTable       `json:"seed"`
	Cases []dashCase        `json:"cases"`
	Env   map[string]string `json:"env"`
}

type seedTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type dashCase struct {
	Name    string            `json:"name"`
	Path    string            `json:"path"`
	User    int               `json:"user"`
	Lang    string            `json:"lang"`
	Headers map[string]string `json:"headers"`
	Lines   []string          `json:"lines"`
}

func TestDashboardPublicLanding(t *testing.T) {
	env := map[string]string{
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_APP_BASE_URL":    "https://app.ubyhost.example",
		"UBYHOST_SECRET_KEY":      "golden-secret-key-not-for-real-use",
		"UBYHOST_SIGNUP_ENABLED":  "0",
	}
	h := DashboardHandler(nil, func(k string) string { return env[k] }, nil, time.Now)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Host = "ubyhost.example"
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `id="content"`) {
		t.Fatal("expected landing content")
	}
}

func TestDashboardGolden(t *testing.T) {
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL unset")
	}
	raw, err := os.ReadFile("testdata/dashboard_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g dashGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	if err := seedGolden(ctx, pool, g.Seed); err != nil {
		if strings.Contains(err.Error(), "does not exist") {
			t.Skip("dashboard golden needs migrated test schema: ", err)
		}
		t.Fatal(err)
	}
	getenv := func(k string) string {
		if v, ok := g.Env[k]; ok {
			return v
		}
		if k == "UBYHOST_SECRET_KEY" {
			return "golden-secret-key-not-for-real-use"
		}
		return ""
	}
	at, _ := time.Parse(time.RFC3339, "2026-06-15T12:00:00Z")
	h := DashboardHandler(pool, getenv, nil, func() time.Time { return at })
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, c.Path, nil)
			if c.Headers["Host"] != "" {
				req.Host = c.Headers["Host"]
			}
			if c.Lang != "" {
				req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.Lang})
			}
			if c.User > 0 {
				tok, err := session.IssueSession(secret, int64(c.User), 1, session.IssueOptions{}, at)
				if err != nil {
					t.Fatal(err)
				}
				req.AddCookie(&http.Cookie{Name: session.CookieName, Value: tok})
			}
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, req)
			if rec.Code != http.StatusOK {
				t.Fatalf("status %d body %q", rec.Code, rec.Body.String()[:min(300, rec.Body.Len())])
			}
			body := rec.Body.String()
			switch c.Name {
			case "signed_out_landing":
				if !strings.Contains(body, `id="landing-title"`) {
					t.Fatal("expected public landing")
				}
			case "signed_in_empty":
				if !strings.Contains(body, "ui-page") {
					t.Fatal("expected host shell")
				}
			case "signed_in_with_stay":
				if !strings.Contains(body, "Chrome Flat") {
					t.Fatal("expected stay row")
				}
			default:
				for _, line := range c.Lines {
					if line == "" || strings.HasPrefix(line, "<") {
						continue
					}
					if !strings.Contains(body, line) {
						t.Fatalf("missing visible copy %q", line)
					}
				}
			}
		})
	}
}

func seedGolden(ctx context.Context, pool *pgxpool.Pool, seed []seedTable) error {
	for _, q := range []string{
		`DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id IN (880001,880002))`,
		`DELETE FROM apartment WHERE owner_user_id IN (880001,880002)`,
		`DELETE FROM legal_entity WHERE owner_user_id IN (880001,880002)`,
		`DELETE FROM legal_acceptance WHERE user_account_id IN (880001,880002)`,
		`DELETE FROM user_account WHERE id IN (880001,880002)`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			return err
		}
	}
	for _, table := range seed {
		for _, row := range table.Rows {
			args := make([]any, len(row))
			copy(args, row)
			ph := make([]string, len(row))
			for i := range ph {
				ph[i] = fmt.Sprintf("$%d", i+1)
			}
			sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)",
				table.Table, strings.Join(table.Columns, ","), strings.Join(ph, ","))
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				return err
			}
		}
	}
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
