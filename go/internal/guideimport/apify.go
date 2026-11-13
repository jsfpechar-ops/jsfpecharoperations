package guideimport

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

const (
	// apifyAPI is the only URL this package opens for a listing (outbound
	// reason: fetch the host's own public listing the host pasted).
	apifyAPI       = "https://api.apify.com/v2/acts/"
	maxResponse    = 4 * 1024 * 1024
	connectTimeout = 10 * time.Second
	readTimeout    = 150 * time.Second
)

var actors = map[string]string{
	"booking": "voyager~booking-scraper",
	"airbnb":  "tri_angle~airbnb-rooms-urls-scraper",
}

// Error is a short failure code the import row stores (GuideImportError.key).
type Error struct{ Key string }

func (e *Error) Error() string { return e.Key }

// Fetcher runs one actor and returns its first dataset item.
type Fetcher interface {
	Fetch(ctx context.Context, source, url string) (map[string]any, error)
}

// Apify is the Fetcher for the real service. BaseURL and HTTP are replaced in tests.
type Apify struct {
	Token       string
	TimeoutSecs int
	BaseURL     string // default apifyAPI
	HTTP        *http.Client
}

// NewApify returns an Apify with the Python timeouts: 10 s to connect, 150 s
// to wait for the answer (the actor timeout we ask for is shorter, so Apify's
// own 408 arrives first), redirects never followed.
func NewApify(token string, timeoutSecs int) *Apify {
	return &Apify{
		Token:       token,
		TimeoutSecs: timeoutSecs,
		BaseURL:     apifyAPI,
		HTTP: &http.Client{
			Timeout: 5 * time.Minute,
			Transport: &http.Transport{
				DialContext:           (&net.Dialer{Timeout: connectTimeout}).DialContext,
				TLSHandshakeTimeout:   connectTimeout,
				ResponseHeaderTimeout: readTimeout,
				Proxy:                 http.ProxyFromEnvironment,
			},
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
		},
	}
}

// ActorBody is json.dumps(_actor_input(source, url)): Python's default separators.
func ActorBody(source, url string) string {
	s := `{"startUrls": [{"url": ` + anthropic.PyJSONString(url) + `}]`
	if source == "booking" {
		s += `, "maxItems": 1, "language": "en-gb", "currency": "CZK"`
	}
	return s + "}"
}

// Query is the query string in the order requests sends it.
func (a *Apify) Query() string {
	return "timeout=" + strconv.Itoa(a.TimeoutSecs) + "&maxItems=1&clean=true&format=json"
}

// Fetch is _fetch(): one synchronous actor run. It returns *Error with a short code.
func (a *Apify) Fetch(ctx context.Context, source, url string) (map[string]any, error) {
	base := a.BaseURL
	if base == "" {
		base = apifyAPI
	}
	endpoint := base + actors[source] + "/run-sync-get-dataset-items?" + a.Query()
	httpc := a.HTTP
	if httpc == nil {
		httpc = NewApify("", 0).HTTP
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(ActorBody(source, url)))
	if err != nil {
		return nil, &Error{"network"}
	}
	req.Header.Set("Authorization", "Bearer "+a.Token)
	req.Header.Set("Content-Type", "application/json")
	res, err := httpc.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, &Error{"network"}
	}
	defer res.Body.Close()
	if res.StatusCode == 408 {
		return nil, &Error{"timeout"}
	}
	if res.StatusCode != 200 && res.StatusCode != 201 {
		return nil, &Error{"http_" + strconv.Itoa(res.StatusCode)}
	}
	body, err := io.ReadAll(io.LimitReader(res.Body, maxResponse+1))
	if err != nil {
		return nil, &Error{"network"}
	}
	if len(body) > maxResponse {
		return nil, &Error{"too_large"}
	}
	return firstItem(body)
}

// firstItem is the tail of _fetch(): the body must be a JSON list whose first
// element is an object.
func firstItem(body []byte) (map[string]any, error) {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, &Error{"bad_json"}
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return nil, &Error{"bad_json"}
	}
	items, ok := v.([]any)
	if !ok || len(items) == 0 {
		return nil, &Error{"empty"}
	}
	first, ok := items[0].(map[string]any)
	if !ok {
		return nil, &Error{"empty"}
	}
	return first, nil
}
