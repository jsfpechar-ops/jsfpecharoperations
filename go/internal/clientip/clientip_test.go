package clientip

import (
	"encoding/json"
	"net"
	"net/http/httptest"
	"os"
	"testing"
)

// TestGolden: Host and Key equal request.client.host and rate_limit.client_key
// after client_ip.apply_visitor_client, for every case of
// App/scripts/auth_shared_golden.py (testdata/clientip.json).
func TestGolden(t *testing.T) {
	raw, err := os.ReadFile("testdata/clientip.json")
	if err != nil {
		t.Fatal(err)
	}
	var g struct {
		Cases []struct {
			CIDRs     string  `json:"cidrs"`
			Peer      *string `json:"peer"`
			Header    *string `json:"header"`
			Host      string  `json:"host"`
			Key       string  `json:"key"`
			KeySuffix string  `json:"key_suffix"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 300 {
		t.Fatalf("%d cases, want at least 300", len(g.Cases))
	}
	for _, c := range g.Cases {
		r := httptest.NewRequest("POST", "/login", nil)
		r.RemoteAddr = ""
		if c.Peer != nil && *c.Peer != "" {
			r.RemoteAddr = net.JoinHostPort(*c.Peer, "1234")
		}
		if c.Header != nil {
			r.Header.Set("CF-Connecting-IP", *c.Header)
		}
		env := func(k string) string {
			if k == "UBYHOST_TRUSTED_PROXY_CIDRS" {
				return c.CIDRs
			}
			return ""
		}
		host, key, suffix := Host(r, env), Key(r, env, ""), Key(r, env, "host_login")
		if host != c.Host || key != c.Key || suffix != c.KeySuffix {
			t.Errorf("cidrs=%q peer=%v header=%v: got %q %q %q, want %q %q %q",
				c.CIDRs, c.Peer, c.Header, host, key, suffix, c.Host, c.Key, c.KeySuffix)
		}
	}
}

// TestBadCIDRTrustsNobody: an unreadable UBYHOST_TRUSTED_PROXY_CIDRS (Python
// raises on every request) makes Go trust no peer.
func TestBadCIDRTrustsNobody(t *testing.T) {
	r := httptest.NewRequest("POST", "/login", nil)
	r.RemoteAddr = "172.18.0.3:1234"
	r.Header.Set("CF-Connecting-IP", "203.0.113.9")
	env := func(k string) string {
		if k == "UBYHOST_TRUSTED_PROXY_CIDRS" {
			return "172.16.0.0/12,not-a-net"
		}
		return ""
	}
	if got := Host(r, env); got != "172.18.0.3" {
		t.Fatalf("Host = %q, want the peer", got)
	}
}
