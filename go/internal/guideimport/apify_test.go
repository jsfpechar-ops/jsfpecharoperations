package guideimport

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

type apifyGolden struct {
	Requests []struct {
		Endpoint string            `json:"endpoint"`
		Query    string            `json:"query"`
		Headers  map[string]string `json:"headers"`
		Body     string            `json:"body"`
		Redirect bool              `json:"allow_redirects"`
		Source   string            `json:"source"`
		URL      string            `json:"url"`
	} `json:"requests"`
	Fetch []struct {
		Name     string `json:"name"`
		Status   any    `json:"status"`
		Body     string `json:"body"`
		BodyKind string `json:"body_kind"`
		Result   struct {
			Item  map[string]any `json:"item"`
			Error string         `json:"error"`
		} `json:"result"`
	} `json:"fetch"`
	APIBase  string `json:"api_base"`
	MaxBytes int    `json:"max_bytes"`
}

func TestApifyRequestMatchesPython(t *testing.T) {
	g := load(t).Apify
	if apifyAPI != g.APIBase || maxResponse != g.MaxBytes {
		t.Error("api base or size cap differs")
	}
	for _, r := range g.Requests {
		var gotPath, gotQuery, gotBody string
		var gotHdr http.Header
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			b, _ := io.ReadAll(req.Body)
			gotPath, gotQuery, gotBody, gotHdr = req.URL.Path, req.URL.RawQuery, string(b), req.Header
			w.Write([]byte(`[{"name": "X"}]`))
		}))
		a := NewApify("test-token", 120)
		a.BaseURL = srv.URL + "/v2/acts/"
		if _, err := a.Fetch(context.Background(), r.Source, r.URL); err != nil {
			t.Fatal(err)
		}
		srv.Close()
		if want := strings.TrimPrefix(r.Endpoint, "https://api.apify.com"); gotPath != want {
			t.Errorf("path %s, want %s", gotPath, want)
		}
		if gotQuery != r.Query || gotBody != r.Body {
			t.Errorf("query/body differ: %q %q", gotQuery, gotBody)
		}
		for k, v := range r.Headers {
			if gotHdr.Get(k) != v {
				t.Errorf("header %s = %q, want %q", k, gotHdr.Get(k), v)
			}
		}
	}
}

func TestApifyFetchMatchesPython(t *testing.T) {
	for _, c := range load(t).Apify.Fetch {
		var srv *httptest.Server
		base := ""
		if c.Status == "network" {
			srv = httptest.NewServer(http.NotFoundHandler())
			base = srv.URL
			srv.Close()
		} else {
			status := 0
			if n, ok := c.Status.(interface{ Int64() (int64, error) }); ok {
				v, _ := n.Int64()
				status = int(v)
			}
			body := c.Body
			if c.BodyKind == "big" {
				body = `[{"a": "` + strings.Repeat("x", 4*1024*1024) + `"}]`
			}
			srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
				w.WriteHeader(status)
				w.Write([]byte(body))
			}))
			defer srv.Close()
			base = srv.URL
		}
		a := NewApify("t", 120)
		a.BaseURL = base + "/v2/acts/"
		item, err := a.Fetch(context.Background(), "booking", "https://www.booking.com/hotel/cz/vltava-view.html")
		if c.Result.Error != "" {
			ie, ok := err.(*Error)
			if !ok || ie.Key != c.Result.Error {
				t.Errorf("%s: err %v, want %s", c.Name, err, c.Result.Error)
			}
			continue
		}
		if err != nil || !reflect.DeepEqual(item, c.Result.Item) {
			t.Errorf("%s: item %v err %v, want %v", c.Name, item, err, c.Result.Item)
		}
	}
}
