package ical

import (
	"context"
	"errors"
	"net/netip"
	"testing"
)

// fakeResolver answers only the hosts it knows; it records every lookup so a
// test can see that each hop was resolved again.
type fakeResolver struct {
	hosts map[string][]netip.Addr
	seen  []string
}

func (f *fakeResolver) LookupNetIP(_ context.Context, _ string, host string) ([]netip.Addr, error) {
	f.seen = append(f.seen, host)
	addrs, ok := f.hosts[host]
	if !ok {
		return nil, errors.New("no such host")
	}
	return addrs, nil
}

func addrs(s ...string) []netip.Addr {
	out := make([]netip.Addr, 0, len(s))
	for _, a := range s {
		out = append(out, netip.MustParseAddr(a))
	}
	return out
}

func guardKey(t *testing.T, err error) string {
	t.Helper()
	var fe *FeedURLError
	if !errors.As(err, &fe) {
		t.Fatalf("want *FeedURLError, got %T %v", err, err)
	}
	return fe.Key
}

// Ported from App/tests/test_feed_url_ssrf.py: every URL here must be refused.
func TestResolveTargetRefusesInternalTargets(t *testing.T) {
	cases := []string{
		"http://127.0.0.1:8081/ws_uby/ws_uby.svc",
		"http://localhost/calendar.ics",
		"http://metadata.google.internal/computeMetadata/v1/",
		"http://LOCALHOST./c.ics",
		"http://2130706433/c.ics",
		"http://0177.0.0.1/c.ics",
		"http://0x7f000001/c.ics",
		"http://127.1/c.ics",
		"http://0x7f.1/c.ics",
		"http://[::1]/c.ics",
		"http://[::ffff:127.0.0.1]/c.ics",
		"http://169.254.169.254/latest/meta-data/",
		"http://10.0.0.5/c.ics",
		"http://192.168.1.1/c.ics",
		"http://172.16.0.1/c.ics",
		"http://0.0.0.0/c.ics",
		"http://user:pass@127.0.0.1/c.ics",
		"https://calendar-user:calendar-password@www.google.com/c.ics",
		"http://[::1/c.ics",
		"http://nas.local/c.ics",
		"http://100.64.0.1/c.ics",
		"http://100.127.255.254/c.ics",
		"http://[64:ff9b::a00:5]/c.ics",
	}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			r := &fakeResolver{hosts: map[string][]netip.Addr{}}
			_, err := ResolveTarget(context.Background(), raw, r, false)
			if err == nil {
				t.Fatalf("%s was accepted", raw)
			}
			if guardKey(t, err) == keyHostUnknown {
				t.Fatalf("%s was refused by DNS, not by the guard", raw)
			}
		})
	}
}

func TestBlockedAndAllowedAddresses(t *testing.T) {
	blocked := []string{
		// IPv4
		"0.1.2.3", "10.1.1.1", "127.0.0.2", "169.254.1.1", "172.16.5.5", "192.0.0.9",
		"192.0.2.1", "192.168.1.1", "198.18.0.1", "198.51.100.1", "203.0.113.1",
		"224.0.0.1", "240.0.0.1", "255.255.255.255", "100.64.0.1", "100.127.255.254",
		"0.0.0.0",
		// IPv6, one per Python reserved range
		"::2", "100::1", "200::1", "400::1", "800::1", "1000::1", "4000::1",
		"6000::1", "8000::1", "a000::1", "c000::1", "e000::1", "f000::1", "f800::1", "fe00::1",
		// IPv6, private, link-local, multicast, loopback, unspecified, mapped
		"fc00::1", "2001:db8::1", "2002::1", "3fff::1", "64:ff9b:1::1", "fe80::1",
		"ff02::1", "::1", "::", "::ffff:8.8.8.8", "::ffff:127.0.0.1",
	}
	for _, a := range blocked {
		if !blockedIP(netip.MustParseAddr(a)) {
			t.Errorf("%s should be blocked", a)
		}
	}
	allowed := []string{
		"8.8.8.8", "93.184.216.34", "1.1.1.1", "192.0.1.1", "100.128.0.1",
		"2606:4700:4700::1111", "2001:4860:4860::8888", "2001:20::1",
	}
	for _, a := range allowed {
		if blockedIP(netip.MustParseAddr(a)) {
			t.Errorf("%s should be allowed", a)
		}
	}
}

func TestHostnamesRefusedBeforeDNS(t *testing.T) {
	// The resolver would answer these publicly; the guard must refuse first.
	r := &fakeResolver{hosts: map[string][]netip.Addr{
		"localhost": addrs("93.184.216.34"),
		"nas.local": addrs("93.184.216.34"),
	}}
	for _, raw := range []string{"http://localhost/c.ics", "http://nas.local/c.ics"} {
		if _, err := ResolveTarget(context.Background(), raw, r, false); err == nil {
			t.Errorf("%s accepted", raw)
		}
	}
	if len(r.seen) != 0 {
		t.Errorf("DNS was asked for %v before the guard refused", r.seen)
	}
}

func TestLocalhostAllowedOnlyWithAllowPrivate(t *testing.T) {
	r := &fakeResolver{hosts: map[string][]netip.Addr{"localhost": addrs("127.0.0.1")}}
	if _, err := ResolveTarget(context.Background(), "http://localhost/c.ics", r, true); err != nil {
		t.Fatalf("allowPrivate should accept localhost: %v", err)
	}
}

func TestURLShapeErrorsKeepPythonKeys(t *testing.T) {
	cases := map[string]string{
		"ftp://example.com/x.ics":               keyURLScheme,
		"http:///x.ics":                         keyURLNoHost,
		"https://user:pw@www.example.com/c.ics": keyURLCredential,
		"http://www.example.com:0/c.ics":        keyURLPort,
		"http://www.example.com:99999/c.ics":    keyURLMalformed,
		"http://www.example.com:abc/c.ics":      keyURLMalformed,
		"http://[::1/c.ics":                     keyURLMalformed,
	}
	for raw, want := range cases {
		_, err := ResolveTarget(context.Background(), raw, &fakeResolver{}, false)
		if err == nil {
			t.Errorf("%s accepted", raw)
			continue
		}
		if got := guardKey(t, err); got != want {
			t.Errorf("%s: key %q, want %q", raw, got, want)
		}
	}
}

func TestDNSAnswersAreAllValidated(t *testing.T) {
	r := &fakeResolver{hosts: map[string][]netip.Addr{
		"mixed.example": addrs("127.0.0.1", "93.184.216.34"),
	}}
	_, err := ResolveTarget(context.Background(), "https://mixed.example/c.ics", r, false)
	if guardKey(t, err) != keyHostPrivate {
		t.Fatalf("one blocked address must refuse the host, got %v", err)
	}
	_, err = ResolveTarget(context.Background(), "https://empty.example/c.ics", &fakeResolver{}, false)
	if guardKey(t, err) != keyHostUnknown {
		t.Fatalf("unresolvable host: got %v", err)
	}
}

func TestResolveTargetPinsPublicAddresses(t *testing.T) {
	r := &fakeResolver{hosts: map[string][]netip.Addr{
		"www.example.com": addrs("93.184.216.34", "93.184.216.34", "2606:4700:4700::1111"),
	}}
	got, err := ResolveTarget(context.Background(), " https://WWW.example.com./calendar/x.ics ", r, false)
	if err != nil {
		t.Fatal(err)
	}
	if got.Host != "www.example.com" || got.Port != 443 || got.Scheme != "https" {
		t.Errorf("target = %+v", got)
	}
	if len(got.IPs) != 2 {
		t.Errorf("pinned IPs = %v, want the two distinct addresses", got.IPs)
	}
	if got.URL != "https://WWW.example.com./calendar/x.ics" {
		t.Errorf("URL = %q", got.URL)
	}
}

func TestResolveRedirectRevalidatesEachHop(t *testing.T) {
	r := &fakeResolver{hosts: map[string][]netip.Addr{
		"www.example.com": addrs("93.184.216.34"),
	}}
	ctx := context.Background()
	got, err := ResolveRedirect(ctx, "https://www.example.com/calendar/ical/x.ics", "/calendar/ical/y.ics", r, false)
	if err != nil || got.URL != "https://www.example.com/calendar/ical/y.ics" {
		t.Fatalf("relative redirect: %v %+v", err, got)
	}
	if _, err := ResolveRedirect(ctx, "https://www.example.com/x.ics", "http://169.254.169.254/", r, false); err == nil {
		t.Error("redirect to metadata address accepted")
	}
	if _, err := ResolveRedirect(ctx, "https://www.example.com/x.ics", "http://localhost/x", r, false); err == nil {
		t.Error("redirect to localhost accepted")
	}
}

func TestRedirectThatDropsHTTPSIsRefused(t *testing.T) {
	r := &fakeResolver{hosts: map[string][]netip.Addr{
		"www.example.com": addrs("93.184.216.34"),
	}}
	ctx := context.Background()
	_, err := ResolveRedirect(ctx, "https://www.example.com/x.ics", "http://www.example.com/x.ics", r, false)
	if guardKey(t, err) != keyRedirectHTTP {
		t.Fatalf("https to http redirect: %v", err)
	}
	if _, err := ResolveRedirect(ctx, "http://www.example.com/x.ics", "https://www.example.com/y.ics", r, false); err != nil {
		t.Errorf("http to https redirect refused: %v", err)
	}
	if _, err := ResolveRedirect(ctx, "http://www.example.com/x.ics", "http://www.example.com/y.ics", r, false); err != nil {
		t.Errorf("http to http redirect refused: %v", err)
	}
}

func TestAllowPrivateReadsFlagAndDeployment(t *testing.T) {
	cases := []struct {
		flag, deployment string
		want             bool
	}{
		{"1", "", true},
		{"TRUE", "staging", true},
		{"yes", "local", true},
		{"yes", "production", false},
		{"yes", "PRODUCTION", false},
		{"on", "local", false},
		{"", "local", false},
	}
	for _, c := range cases {
		env := map[string]string{
			"UBYHOST_ICAL_ALLOW_PRIVATE": c.flag,
			"UBYHOST_DEPLOYMENT":         c.deployment,
		}
		got := AllowPrivate(func(k string) string { return env[k] })
		if got != c.want {
			t.Errorf("flag=%q deployment=%q: got %v, want %v", c.flag, c.deployment, got, c.want)
		}
	}
}
