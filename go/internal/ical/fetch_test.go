package ical

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"net/netip"
	"net/url"
	"strings"
	"testing"
)

const (
	feedHost = "feed.example"
	feedIP   = "93.184.216.34"
)

// newFeed starts a test server and returns the public-looking feed base URL.
// feed.example resolves to a public address, and the dial to that address is
// routed to the test server, so the guard runs with allowPrivate false. dialed
// records each address the transport tried.
func newFeed(t *testing.T, h http.HandlerFunc) (base string, opt FetchOptions, dialed *[]string) {
	t.Helper()
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	u, err := url.Parse(srv.URL)
	if err != nil {
		t.Fatal(err)
	}
	var seen []string
	opt = FetchOptions{
		Resolver: &fakeResolver{hosts: map[string][]netip.Addr{feedHost: addrs(feedIP)}},
		Dial: func(ctx context.Context, network, addr string) (net.Conn, error) {
			seen = append(seen, addr)
			var d net.Dialer
			return d.DialContext(ctx, network, u.Host)
		},
	}
	return "http://" + feedHost + ":" + u.Port(), opt, &seen
}

const validICS = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"

func TestFetchReturnsBodyAndValidators(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("ETag", `"v1"`)
		w.Header().Set("Last-Modified", "Mon, 02 Jan 2006 15:04:05 GMT")
		fmt.Fprint(w, validICS)
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err != nil {
		t.Fatal(err)
	}
	if got.Text != validICS || got.NotModified {
		t.Errorf("text %q notModified %v", got.Text, got.NotModified)
	}
	if got.ETag != `"v1"` || got.LastModified != "Mon, 02 Jan 2006 15:04:05 GMT" {
		t.Errorf("validators %q %q", got.ETag, got.LastModified)
	}
}

func TestFetch304WithValidatorsSent(t *testing.T) {
	var gotINM, gotIMS string
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		gotINM = r.Header.Get("If-None-Match")
		gotIMS = r.Header.Get("If-Modified-Since")
		w.WriteHeader(http.StatusNotModified)
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", `"v1"`, "Mon, 02 Jan 2006 15:04:05 GMT", opt)
	if err != nil {
		t.Fatal(err)
	}
	if !got.NotModified || got.Text != "" {
		t.Errorf("want not modified, got %+v", got)
	}
	if gotINM != `"v1"` || gotIMS != "Mon, 02 Jan 2006 15:04:05 GMT" {
		t.Errorf("sent If-None-Match %q If-Modified-Since %q", gotINM, gotIMS)
	}
	if got.ETag != `"v1"` {
		t.Errorf("sent ETag should be kept, got %q", got.ETag)
	}
}

func TestFetch304WithoutValidatorsIsAnError(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotModified)
	})
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || err.Error() != "Calendar returned HTTP 304." {
		t.Fatalf("got %v", err)
	}
}

func TestFetchDropsUnsafeValidatorsBeforeSending(t *testing.T) {
	var gotINM string
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		gotINM = r.Header.Get("If-None-Match")
		fmt.Fprint(w, validICS)
	})
	if _, err := Fetch(context.Background(), base+"/cal.ics", "bad\x01tag", "", opt); err != nil {
		t.Fatal(err)
	}
	if gotINM != "" {
		t.Errorf("unsafe validator was sent: %q", gotINM)
	}
}

func TestCleanValidator(t *testing.T) {
	cases := map[string]string{
		"":                       "",
		"  \"abc\"  ":            "\"abc\"",
		"bad\x01":                "",
		"tab\there":              "",
		"é":                      "",
		strings.Repeat("a", 256): strings.Repeat("a", 256),
		strings.Repeat("a", 257): "",
	}
	for in, want := range cases {
		if got := CleanValidator(in); got != want {
			t.Errorf("CleanValidator(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestFetchRedirectToBlockedHostRefused(t *testing.T) {
	cases := map[string]string{
		"http://169.254.169.254/latest/meta-data/": "Calendar URL must point to a public internet host, not a private or internal address.",
		"http://localhost/x.ics":                   "That calendar host is not allowed.",
	}
	for loc, want := range cases {
		base, opt, dialed := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
			http.Redirect(w, r, loc, http.StatusFound)
		})
		_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
		if err == nil || err.Error() != want {
			t.Errorf("%s: got %v", loc, err)
		}
		if len(*dialed) != 1 {
			t.Errorf("%s: only the first hop may be dialed, got %v", loc, *dialed)
		}
	}
}

func TestFetchFollowsThreeRedirects(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/cal.ics":
			http.Redirect(w, r, "/r1", http.StatusFound)
		case "/r1":
			http.Redirect(w, r, "/r2", http.StatusFound)
		case "/r2":
			http.Redirect(w, r, "/r3", http.StatusFound)
		default:
			fmt.Fprint(w, validICS)
		}
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err != nil || got.Text != validICS {
		t.Fatalf("three redirects: %v %q", err, got.Text)
	}
}

func TestFetchRefusesFourRedirects(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/cal.ics":
			http.Redirect(w, r, "/r1", http.StatusFound)
		case "/r1":
			http.Redirect(w, r, "/r2", http.StatusFound)
		case "/r2":
			http.Redirect(w, r, "/r3", http.StatusFound)
		case "/r3":
			http.Redirect(w, r, "/r4", http.StatusFound)
		default:
			fmt.Fprint(w, validICS)
		}
	})
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || err.Error() != "Calendar redirected too many times." {
		t.Fatalf("got %v", err)
	}
}

func TestFetchRedirectsResolveEachHop(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/cal.ics" {
			http.Redirect(w, r, "/ok.ics", http.StatusFound)
			return
		}
		fmt.Fprint(w, validICS)
	})
	resolver := opt.Resolver.(*fakeResolver)
	if _, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt); err != nil {
		t.Fatal(err)
	}
	if len(resolver.seen) != 2 {
		t.Errorf("DNS lookups %v, want one per hop", resolver.seen)
	}
}

func TestFetchRefusesOversizeByHeader(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "5242881")
		w.WriteHeader(http.StatusOK)
	})
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || err.Error() != "Calendar is too large." {
		t.Fatalf("got %v", err)
	}
}

func TestFetchRefusesOversizeByStream(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		chunk := []byte(strings.Repeat("x", 64*1024))
		for i := 0; i < 81; i++ {
			if _, err := w.Write(chunk); err != nil {
				return
			}
		}
	})
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || err.Error() != "Calendar is too large." {
		t.Fatalf("got %v", err)
	}
}

func TestFetchNon200(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	})
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || err.Error() != "Calendar returned HTTP 503." {
		t.Fatalf("got %v", err)
	}
}

func TestFetchStripsBOM(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/calendar; charset=utf-8")
		fmt.Fprint(w, "\uFEFF"+validICS)
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err != nil {
		t.Fatal(err)
	}
	if got.Text != validICS {
		t.Errorf("text %q", got.Text)
	}
}

func TestFetchReplacesInvalidUTF8(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "BEGIN:VCALENDAR\nSUMMARY:Ren\xffe\nEND:VCALENDAR\n")
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(got.Text, "Ren�e") {
		t.Errorf("invalid byte not replaced: %q", got.Text)
	}
}

func TestFetchDeclaredLatin1(t *testing.T) {
	base, opt, _ := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/calendar; charset=iso-8859-1")
		fmt.Fprint(w, "BEGIN:VCALENDAR\nSUMMARY:Jos\xe9\nEND:VCALENDAR\n")
	})
	got, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(got.Text, "José") {
		t.Errorf("latin-1 not decoded: %q", got.Text)
	}
}

func TestFetchRefusesWhenDNSHasBlockedAddress(t *testing.T) {
	base, opt, dialed := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, validICS)
	})
	opt.Resolver = &fakeResolver{hosts: map[string][]netip.Addr{feedHost: addrs("127.0.0.1", feedIP)}}
	_, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt)
	if err == nil || !strings.Contains(err.Error(), "public internet host") {
		t.Fatalf("got %v", err)
	}
	if len(*dialed) != 0 {
		t.Errorf("dialed despite a blocked address: %v", *dialed)
	}
}

func TestFetchPinsValidatedAddress(t *testing.T) {
	base, opt, dialed := newFeed(t, func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, validICS)
	})
	u, _ := url.Parse(base)
	if _, err := Fetch(context.Background(), base+"/cal.ics", "", "", opt); err != nil {
		t.Fatal(err)
	}
	want := feedIP + ":" + u.Port()
	if len(*dialed) != 1 || (*dialed)[0] != want {
		t.Errorf("dialed %v, want [%s]", *dialed, want)
	}
}

func TestFetchLoopbackOnlyWithAllowPrivate(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, validICS)
	}))
	t.Cleanup(srv.Close)
	if _, err := Fetch(context.Background(), srv.URL+"/cal.ics", "", "", FetchOptions{}); err == nil {
		t.Fatal("loopback accepted without allowPrivate")
	}
	got, err := Fetch(context.Background(), srv.URL+"/cal.ics", "", "", FetchOptions{AllowPrivate: true})
	if err != nil || got.Text != validICS {
		t.Fatalf("allowPrivate: %v %q", err, got.Text)
	}
}
