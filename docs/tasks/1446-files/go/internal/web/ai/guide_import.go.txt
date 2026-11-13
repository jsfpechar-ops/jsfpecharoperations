package ai

// POST /apartments/{id}/guide/import (brief 1446): App/app/routes/guest_guide.py
// guide_import (180-195) with guest_guide_import.normalise_url and
// request_imports. The route only checks the links and queues rows in
// guide_import; the job that fetches them (go/internal/guideimport, or the
// Python worker) runs later. No request leaves the web service here.

import (
	"context"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

func init() {
	guideAdd("POST", "/apartments/{id}/guide/import", (*guideServer).importPost)
}

// guideMaxURLLength is guest_guide_import.MAX_URL_LENGTH.
const guideMaxURLLength = 2048

var (
	guideBookingPath = regexp.MustCompile(`(?i)^/hotel/([a-z]{2})/([a-z0-9][a-z0-9._-]{0,200})\.html$`)
	guideAirbnbHost  = regexp.MustCompile(`^(?:www\.|m\.)?airbnb\.(?:com|cz|sk|de|at|pl|fr|it|es|nl|ch|hu|ie|ca|co\.uk|com\.au)$`)
	guideAirbnbPath  = regexp.MustCompile(`^/rooms/(?:plus/)?([0-9]{1,20})/?$`)
)

var guideBookingHosts = map[string]bool{"booking.com": true, "www.booking.com": true, "m.booking.com": true}

// guideLink is the {"source", "url"} of an allowed listing link.
type guideLink struct{ Source, URL string }

const guideLinkErr = "flash.error.guide_import_link"

// guideNormaliseURL is guest_guide_import.normalise_url: the link rebuilt from
// the matched parts only (fixed scheme and host, matched path); anything else
// is refused with a flash key. Python's urlsplit would raise ValueError (a 500)
// for a bad port or unbalanced bracket; Go refuses those as a bad link.
func guideNormaliseURL(raw string) (guideLink, error) {
	text := guidePyStrip(raw)
	if text == "" || utf8Len(text) > guideMaxURLLength || !guideASCII(text) {
		return guideLink{}, guideErr(guideLinkErr)
	}
	if strings.ContainsAny(text, `@\`) || strings.IndexFunc(text, guideIsPySpace) >= 0 {
		return guideLink{}, guideErr(guideLinkErr)
	}
	// urlsplit: leading C0 controls and spaces go, the scheme ends at the first ":".
	text = strings.TrimLeft(text, "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f ")
	scheme, rest, found := strings.Cut(text, ":")
	if !found || strings.ToLower(scheme) != "https" || !strings.HasPrefix(rest, "//") {
		return guideLink{}, guideErr(guideLinkErr)
	}
	rest = rest[2:]
	netloc := rest
	path := ""
	if i := strings.IndexAny(rest, "/?#"); i >= 0 {
		netloc, path = rest[:i], rest[i:]
	}
	if i := strings.IndexAny(path, "?#"); i >= 0 {
		path = path[:i]
	}
	if strings.ContainsAny(netloc, "[]") {
		return guideLink{}, guideErr(guideLinkErr) // an IPv6 literal, never a listing host
	}
	host, port, _ := strings.Cut(netloc, ":")
	if port != "" {
		n, err := strconv.Atoi(port)
		if err != nil || n > 65535 {
			return guideLink{}, guideErr(guideLinkErr)
		}
		if n != 0 { // parts.port is falsy for 0
			return guideLink{}, guideErr(guideLinkErr)
		}
	}
	host = strings.TrimRight(strings.ToLower(host), ".")
	if host == "" || guideAllDigits(strings.ReplaceAll(host, ".", "")) {
		return guideLink{}, guideErr(guideLinkErr)
	}
	if path == "" {
		path = "/"
	}
	if guideBookingHosts[host] {
		m := guideBookingPath.FindStringSubmatch(path)
		if m == nil {
			return guideLink{}, guideErr("flash.error.guide_import_booking_path")
		}
		return guideLink{"booking", "https://www.booking.com/hotel/" + strings.ToLower(m[1]) + "/" + m[2] + ".html"}, nil
	}
	if guideAirbnbHost.MatchString(host) {
		m := guideAirbnbPath.FindStringSubmatch(path)
		if m == nil {
			return guideLink{}, guideErr("flash.error.guide_import_airbnb_path")
		}
		return guideLink{"airbnb", "https://www.airbnb.com/rooms/" + m[1]}, nil
	}
	return guideLink{}, guideErr(guideLinkErr)
}

func utf8Len(s string) int { return len([]rune(s)) }

func guideASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 {
			return false
		}
	}
	return true
}

// guideIsPySpace is str.isspace for one character (the \x1c-\x1f separators too).
func guideIsPySpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

func guideAllDigits(s string) bool {
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

// runsThisMonth is guest_guide_import.runs_this_month (UTC month key).
func (s *guideServer) runsThisMonth(ctx context.Context, at time.Time) (int, error) {
	var calls *int64
	err := s.pool.QueryRow(ctx, `SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = 'apify'`, at.UTC().Format("2006-01")).Scan(&calls)
	if err != nil && err != pgx.ErrNoRows {
		return 0, err
	}
	if calls == nil {
		return 0, nil
	}
	return int(*calls), nil
}

// requestImports is guest_guide_import.request_imports: every check runs
// before any row is written, so a refusal queues nothing. A flash key comes
// back as a guideError.
func (s *guideServer) requestImports(ctx context.Context, apt int64, urls []string, at time.Time) error {
	cfg := guideimport.ConfigFromEnv(s.lookupEnv)
	if cfg.Token == "" {
		return guideErr("flash.error.guide_import_off")
	}
	var raws []string
	for _, u := range urls {
		if guidePyStrip(u) != "" {
			raws = append(raws, u)
		}
	}
	if len(raws) == 0 {
		return guideErr("flash.error.guide_import_empty")
	}
	var links []guideLink
	seen := map[string]bool{}
	for _, raw := range raws {
		link, err := guideNormaliseURL(raw)
		if err != nil {
			return err
		}
		links = append(links, link)
	}
	for _, l := range links {
		if seen[l.Source] {
			return guideErr("flash.error.guide_import_same")
		}
		seen[l.Source] = true
	}
	var busy int64
	if err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM guide_import WHERE apartment_id = $1 AND status IN ('queued', 'running')`, apt).Scan(&busy); err != nil {
		return err
	}
	if busy > 0 {
		return guideErr("flash.error.guide_import_busy")
	}
	used, err := s.usedSources(ctx, apt)
	if err != nil {
		return err
	}
	for src := range seen {
		if used[src] {
			return guideErr("flash.error.guide_import_limit")
		}
	}
	if cfg.MonthlyRuns > 0 {
		runs, err := s.runsThisMonth(ctx, at)
		if err != nil {
			return err
		}
		if runs+len(links) > cfg.MonthlyRuns {
			return guideErr("flash.error.guide_import_budget")
		}
	}
	now := guideStamp(at)
	for _, l := range links {
		if _, err := s.pool.Exec(ctx, `INSERT INTO guide_import (apartment_id, source, url, status, created_at) VALUES ($1, $2, $3, 'queued', $4)`,
			apt, l.Source, l.URL, now); err != nil {
			return err
		}
	}
	return nil
}

// importPost is POST /apartments/{id}/guide/import.
func (s *guideServer) importPost(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	var urls []string
	for _, name := range []string{"booking_url", "airbnb_url", "url"} {
		v, _ := guideFormValue(r, name)
		urls = append(urls, guideTruncate(v, guideMaxURLLength))
	}
	target := q.base() + "#import"
	if next, _ := guideFormValue(r, "next"); next == "leon" {
		target = "/apartments/" + strconv.FormatInt(a.ID, 10) + "/leon/setup/import"
	}
	if err := s.requestImports(r.Context(), a.ID, urls, q.at); err != nil {
		if key := guideErrKey(err); key != "" {
			q.back(w, target, hostweb.Flash{}, q.flash(key, nil))
			return
		}
		guideFail(w, err)
		return
	}
	q.back(w, target, q.flash("flash.guest_guide.import_queued", nil), hostweb.Flash{})
}
