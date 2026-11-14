package main

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// pythonCustomerRoutes reads the route decorators of App/app/routes/admin_customers.py
// and returns "METHOD /path" for each, with {user_id} replaced by 2.
func pythonCustomerRoutes(t *testing.T) []string {
	t.Helper()
	src, err := os.ReadFile("../../../App/app/routes/admin_customers.py")
	if err != nil {
		t.Fatal(err)
	}
	re := regexp.MustCompile(`@router\.(get|post)\((?:(PAGE)(?: \+ )?)?(?:"([^"]*)")?\)`)
	var out []string
	for _, m := range re.FindAllStringSubmatch(string(src), -1) {
		path := m[3]
		if m[2] != "" {
			path = "/admin/customers" + path
		}
		out = append(out, strings.ToUpper(m[1])+" "+strings.ReplaceAll(path, "{user_id}", "2"))
	}
	return out
}

// TestCustomerRoutesAllServedByGo: Caddy routes by path only, so a path can go to
// Go only if Go answers every method Python answers on it. Every route of
// admin_customers.py must have a Go pattern of its own (not the catch-all).
func TestCustomerRoutesAllServedByGo(t *testing.T) {
	routes := pythonCustomerRoutes(t)
	if len(routes) != 10 {
		t.Fatalf("admin_customers.py has %d routes, the brief counted 10: %v", len(routes), routes)
	}
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, route := range append(routes, "GET /admin/funnel") {
		method, path, _ := strings.Cut(route, " ")
		_, pattern := mux.Handler(httptest.NewRequest(method, path, nil))
		if pattern == "" || pattern == "/" || !strings.HasPrefix(pattern, method+" ") {
			t.Errorf("%s is not served by Go (pattern %q)", route, pattern)
		}
	}
}

// TestCustomerRoutesNeedLogin sends every route through the real mux without a
// session: a signed-out visitor is sent to the login page by the admin gate
// (after the CSRF check for POST), and nothing reaches the database (the pool is nil).
func TestCustomerRoutesNeedLogin(t *testing.T) {
	const secret = "customers-wiring-test-secret-0123456789"
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	const cookie = "wiring-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(secret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, route := range append(pythonCustomerRoutes(t), "GET /admin/funnel") {
		method, path, _ := strings.Cut(route, " ")
		req := httptest.NewRequest(method, path, strings.NewReader("percent=1"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
		req.Header.Set("X-CSRF-Token", token)
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next="+path {
			t.Errorf("%s signed out: %d %q", route, rec.Code, rec.Header().Get("Location"))
		}
	}
}

// TestGoServiceGetsInvoiceEnv: the plan, discount and assign actions issue invoices
// inside the Go service (billingjob.Invoicer), which reads the seller's details from
// these variables. compose passes the Go service only the variables listed under its
// "environment:", so each one must be listed there.
func TestGoServiceGetsInvoiceEnv(t *testing.T) {
	raw, err := os.ReadFile("../../../deploy/lightsail/docker-compose.yml")
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	start := strings.Index(text, "\n  ubyhost-go:\n")
	if start < 0 {
		t.Fatal("no ubyhost-go service in docker-compose.yml")
	}
	block := text[start+1:]
	// The service ends where the next service starts: a line with two spaces and a letter.
	if next := regexp.MustCompile(`(?m)^  [a-z]`).FindAllStringIndex(block, 2); len(next) == 2 {
		block = block[:next[1][0]]
	}
	for _, name := range []string{
		"UBYHOST_BILLING_BANK_ACCOUNT", "UBYHOST_BILLING_IBAN", "UBYHOST_BILLING_VAT_STATUS",
		"UBYHOST_OPERATOR_ADDRESS", "UBYHOST_OPERATOR_DIC", "UBYHOST_OPERATOR_EMAIL",
		"UBYHOST_OPERATOR_ICO", "UBYHOST_OPERATOR_NAME",
	} {
		if !strings.Contains(block, "\n      "+name+":") {
			t.Errorf("%s is not passed to the ubyhost-go service", name)
		}
	}
}
