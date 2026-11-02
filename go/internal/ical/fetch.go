package ical

import (
	"context"
	"errors"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	userAgent          = "UbyHost/1.0 (+self-hosted Czech foreign-police reporting)"
	fetchTimeout       = 45 * time.Second
	totalTimeout       = 60 * time.Second
	maxFeedBytes       = 5 * 1024 * 1024
	maxRedirects       = 3
	maxValidatorLength = 256
)

// FetchError carries the English calendar download wording (the sync log
// stores it). It has no translation key: the Python fetch has none either.
type FetchError struct {
	Msg string
}

func (e *FetchError) Error() string { return e.Msg }

// Fetched is one download: the text, or NotModified when a 304 answered a
// request that carried validators.
type Fetched struct {
	Text         string
	ETag         string
	LastModified string
	NotModified  bool
}

// FetchOptions holds the DNS resolver and the private-target switch. Dial, if
// set, replaces the socket dial to each pinned address (tests only).
type FetchOptions struct {
	Resolver     Resolver
	AllowPrivate bool
	Dial         func(ctx context.Context, network, addr string) (net.Conn, error)
}

// CleanValidator trims an ETag or Last-Modified value and drops it unless it is
// printable ASCII (0x20-0x7E) of at most 256 characters. Such a value is safe to
// store and send back as a header.
func CleanValidator(value string) string {
	value = strings.TrimSpace(value)
	if value == "" || len(value) > maxValidatorLength {
		return ""
	}
	for i := 0; i < len(value); i++ {
		if value[i] < 0x20 || value[i] > 0x7E {
			return ""
		}
	}
	return value
}

// Fetch downloads an iCal feed. Each hop is validated, its host resolved once,
// and the connection pinned to the validated addresses. Redirects are followed
// by hand, up to maxRedirects.
func Fetch(ctx context.Context, rawURL, etag, lastModified string, opt FetchOptions) (Fetched, error) {
	current, err := ResolveTarget(ctx, rawURL, opt.Resolver, opt.AllowPrivate)
	if err != nil {
		return Fetched{}, &FetchError{Msg: err.Error()}
	}
	etag = CleanValidator(etag)
	lastModified = CleanValidator(lastModified)
	conditional := etag != "" || lastModified != ""
	headers := http.Header{}
	if etag != "" {
		headers.Set("If-None-Match", etag)
	}
	if lastModified != "" {
		headers.Set("If-Modified-Since", lastModified)
	}

	var resp *http.Response
	var release func()
	defer func() {
		if release != nil {
			release()
		}
	}()
	for hop := 0; ; hop++ {
		r, done, err := get(ctx, current, headers, opt)
		if err != nil {
			return Fetched{}, err
		}
		if !isRedirect(r.StatusCode) {
			resp, release = r, done
			break
		}
		if hop >= maxRedirects {
			r.Body.Close()
			done()
			return Fetched{}, &FetchError{Msg: "Calendar redirected too many times."}
		}
		location := r.Header.Get("Location")
		status := r.StatusCode
		r.Body.Close()
		done()
		if location == "" {
			return Fetched{}, &FetchError{Msg: fmt.Sprintf("Calendar redirect missing Location (HTTP %d).", status)}
		}
		next, err := ResolveRedirect(ctx, current.URL, location, opt.Resolver, opt.AllowPrivate)
		if err != nil {
			return Fetched{}, &FetchError{Msg: err.Error()}
		}
		current = next
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotModified && conditional {
		return Fetched{
			ETag:         pickValidator(CleanValidator(resp.Header.Get("ETag")), etag),
			LastModified: pickValidator(CleanValidator(resp.Header.Get("Last-Modified")), lastModified),
			NotModified:  true,
		}, nil
	}
	if resp.StatusCode != http.StatusOK {
		return Fetched{}, &FetchError{Msg: fmt.Sprintf("Calendar returned HTTP %d.", resp.StatusCode)}
	}
	if cl := resp.Header.Get("Content-Length"); isDigits(cl) {
		n, perr := strconv.ParseInt(cl, 10, 64)
		if perr != nil || n > maxFeedBytes {
			return Fetched{}, &FetchError{Msg: "Calendar is too large."}
		}
	}

	body, err := readCapped(resp.Body)
	if err != nil {
		return Fetched{}, err
	}
	text := decodeBody(body, resp.Header.Get("Content-Type"))
	if !strings.Contains(strings.ToUpper(text), "BEGIN:VCALENDAR") {
		return Fetched{}, &FetchError{Msg: "That URL did not return an iCal calendar. Check you copied the whole export link " +
			"(it contains '/ical/' and usually ends with '.ics')."}
	}
	return Fetched{
		Text:         text,
		ETag:         CleanValidator(resp.Header.Get("ETag")),
		LastModified: CleanValidator(resp.Header.Get("Last-Modified")),
	}, nil
}

// get performs one GET to the pinned addresses of t. The returned done func
// cancels the per-hop context and closes idle connections.
func get(ctx context.Context, t Target, headers http.Header, opt FetchOptions) (*http.Response, func(), error) {
	hopCtx, cancel := context.WithTimeout(ctx, totalTimeout)
	tr := pinnedTransport(t, opt)
	done := func() {
		cancel()
		tr.CloseIdleConnections()
	}
	req, err := http.NewRequestWithContext(hopCtx, http.MethodGet, t.URL, nil)
	if err != nil {
		done()
		return nil, nil, &FetchError{Msg: "Calendar URL is malformed."}
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "text/calendar")
	for k, vs := range headers {
		req.Header[k] = vs
	}
	client := &http.Client{
		Transport: tr,
		// Never follow redirects inside the client: each hop is validated here.
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	resp, err := client.Do(req)
	if err != nil {
		done()
		return nil, nil, &FetchError{Msg: "Could not download the calendar: " + err.Error()}
	}
	return resp, done, nil
}

// pinnedTransport dials only the validated addresses, in order, whatever host
// the request names. TLS still verifies the request host (SNI and certificate).
func pinnedTransport(t Target, opt FetchOptions) *http.Transport {
	dial := opt.Dial
	if dial == nil {
		d := &net.Dialer{Timeout: fetchTimeout}
		dial = d.DialContext
	}
	return &http.Transport{
		Proxy:                 nil,
		DisableKeepAlives:     true,
		TLSHandshakeTimeout:   fetchTimeout,
		ResponseHeaderTimeout: fetchTimeout,
		DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			_, port, err := net.SplitHostPort(addr)
			if err != nil {
				return nil, err
			}
			var lastErr error = errors.New("no pinned address")
			for _, ip := range t.IPs {
				conn, derr := dial(ctx, network, net.JoinHostPort(ip.String(), port))
				if derr == nil {
					return conn, nil
				}
				lastErr = derr
			}
			return nil, lastErr
		},
	}
}

// readCapped reads the body until EOF, refusing more than maxFeedBytes and
// stopping at the total body deadline.
func readCapped(body io.Reader) ([]byte, error) {
	deadline := time.Now().Add(totalTimeout)
	var out []byte
	buf := make([]byte, 64*1024)
	for {
		n, rerr := body.Read(buf)
		out = append(out, buf[:n]...)
		if len(out) > maxFeedBytes {
			return nil, &FetchError{Msg: "Calendar is too large."}
		}
		if time.Now().After(deadline) {
			return nil, &FetchError{Msg: "Calendar download took too long."}
		}
		if rerr == io.EOF {
			return out, nil
		}
		if rerr != nil {
			if errors.Is(rerr, context.DeadlineExceeded) {
				return nil, &FetchError{Msg: "Calendar download took too long."}
			}
			return nil, &FetchError{Msg: "Could not download the calendar: " + rerr.Error()}
		}
	}
}

// decodeBody reads UTF-8 unless the Content-Type declares a charset. Invalid
// bytes become U+FFFD, and leading BOMs are dropped. Only ISO-8859-1 and
// latin-1 are decoded as declared; other charsets fall back to UTF-8.
func decodeBody(body []byte, contentType string) string {
	var text string
	switch declaredCharset(contentType) {
	case "iso-8859-1", "latin-1", "latin1":
		runes := make([]rune, len(body))
		for i, b := range body {
			runes[i] = rune(b)
		}
		text = string(runes)
	default:
		text = decodeUTF8Replacing(body)
	}
	// Python's lstrip("\uFEFF") after decoding: every leading BOM goes.
	return strings.TrimLeft(text, "\uFEFF")
}

func declaredCharset(contentType string) string {
	if !strings.Contains(strings.ToLower(contentType), "charset") {
		return ""
	}
	_, params, err := mime.ParseMediaType(contentType)
	if err != nil {
		return ""
	}
	return strings.ToLower(strings.Trim(params["charset"], `"`))
}

func decodeUTF8Replacing(b []byte) string {
	var sb strings.Builder
	sb.Grow(len(b))
	for len(b) > 0 {
		r, size := utf8.DecodeRune(b)
		if r == utf8.RuneError && size == 1 {
			sb.WriteRune(utf8.RuneError)
		} else {
			sb.Write(b[:size])
		}
		b = b[size:]
	}
	return sb.String()
}

func isRedirect(status int) bool {
	switch status {
	case http.StatusMovedPermanently, http.StatusFound, http.StatusSeeOther,
		http.StatusTemporaryRedirect, http.StatusPermanentRedirect:
		return true
	}
	return false
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func pickValidator(fromResponse, sent string) string {
	if fromResponse != "" {
		return fromResponse
	}
	return sent
}
