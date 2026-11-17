package properties

// GET /apartments/ruian-suggest (brief 1700d): routes/admin.py
// apartments_ruian_suggest on the local ruian_address table (brief 1700c)
// instead of the live ČÚZK call of App/app/ruian.py. The answer is the same
// JSON, [{label, fields}], read by App/app/static/ruian_suggest.js. Nothing
// the host types leaves the server: no outbound request, and the typed text
// is never logged. Nothing routes here until the owner adds the exact path to
// UBYHOST_GO_PATHS. The credit line (ruian.Attribution) is not part of the
// JSON; where it is shown is the owner question of the 1700d report.

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	ruianRateScope  = "ruian" // ruian.py _RATE_SCOPE, shared with Python's rate_limit_event rows
	ruianRateMax    = 60      // _RATE_LIMIT
	ruianRateWin    = 60 * 60 // _RATE_WINDOW, seconds
	ruianMinChars   = 3       // _MIN_CHARS
	ruianMaxResults = 6       // _MAX_RESULTS
	ruianMaxTokens  = 8       // Go only: more words than this cannot narrow a street address
)

// ruianFields are the keys ruian_suggest.js reads, in the order of the form.
// An empty value is left out.
type ruianFields struct {
	Street   string `json:"addr_street,omitempty"`
	HouseNo  string `json:"addr_house_no,omitempty"`
	OrientNo string `json:"addr_orient_no,omitempty"`
	Zip      string `json:"addr_zip,omitempty"`
	Obec     string `json:"addr_obec,omitempty"`
	ObecCast string `json:"addr_obec_cast,omitempty"`
	Okres    string `json:"addr_okres,omitempty"`
}

type ruianItem struct {
	Label  string      `json:"label"`
	Fields ruianFields `json:"fields"`
}

// ruianRow is one ruian_address row, the columns the answer needs.
type ruianRow struct {
	Street, HouseNo, OrientNo, Zip, Obec, Part, District, Okres string
	IsEvid                                                      bool
}

// RegisterRuianSuggest adds GET /apartments/ruian-suggest. It only builds the
// handler; it must not use the pool. The exact pattern is more specific than
// any "/apartments/{id}" pattern, so it wins in the mux (0884 on the Python side).
func RegisterRuianSuggest(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &Pages{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /apartments/ruian-suggest", wrap("/apartments/ruian-suggest", s.ruianSuggest))
}

// ruianEnabled is ruian.enabled: on unless UBYHOST_RUIAN_ENABLED is 0, false, no or off.
func ruianEnabled(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_RUIAN_ENABLED"))) {
	case "0", "false", "no", "off":
		return false
	}
	return true
}

// ruianUsableQuery is ruian.usable_query: white space collapsed, at least
// three characters, else "".
func ruianUsableQuery(q string) string {
	text := strings.Join(strings.Fields(q), " ")
	if utf8.RuneCountInString(text) < ruianMinChars {
		return ""
	}
	return text
}

// ruianLikeEscape makes a token safe inside LIKE: the backslash, % and _ lose
// their meaning.
func ruianLikeEscape(tok string) string {
	return strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`).Replace(tok)
}

// ruianSearchSQL builds the lookup for the folded query and its tokens: every
// token must be in `search` (trigram index), best similarity first, then code.
// All user text goes in as parameters.
func ruianSearchSQL(folded string, tokens []string) (string, []any) {
	var b strings.Builder
	b.WriteString(`SELECT street, house_no, orient_no, zip, obec, part, district, okres, is_evid FROM ruian_address WHERE `)
	args := []any{folded}
	for i, tok := range tokens {
		if i > 0 {
			b.WriteString(" AND ")
		}
		args = append(args, "%"+ruianLikeEscape(tok)+"%")
		fmt.Fprintf(&b, "search LIKE $%d", i+2)
	}
	fmt.Fprintf(&b, " ORDER BY similarity(search, $1::text) DESC, code LIMIT %d", ruianMaxResults)
	return b.String(), args
}

func ruianSearch(ctx context.Context, pool *pgxpool.Pool, text string) ([]ruianRow, error) {
	folded := ruian.Fold(text)
	tokens := strings.Fields(folded)
	if len(tokens) == 0 {
		return nil, nil
	}
	if len(tokens) > ruianMaxTokens {
		tokens = tokens[:ruianMaxTokens]
	}
	sql, args := ruianSearchSQL(folded, tokens)
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (ruianRow, error) {
		var r ruianRow
		err := row.Scan(&r.Street, &r.HouseNo, &r.OrientNo, &r.Zip, &r.Obec, &r.Part, &r.District, &r.Okres, &r.IsEvid)
		return r, err
	})
}

// ruianItemOf maps a row to {label, fields}. The part of the municipality is
// a field only when it differs from the municipality (Python's rule). The
// label is "street no/orient, part, zip district" (for a village without a
// street: "part no, zip obec"; an evidence number reads "č.ev. 12").
func ruianItemOf(r ruianRow) ruianItem {
	part := r.Part
	if part == r.Obec {
		part = ""
	}
	no := r.HouseNo
	if r.OrientNo != "" {
		no += "/" + r.OrientNo
	}
	if r.IsEvid {
		no = "č.ev. " + no
	}
	var segments []string
	if r.Street != "" {
		segments = append(segments, r.Street+" "+no)
		if part != "" {
			segments = append(segments, part)
		}
	} else {
		place := part
		if place == "" {
			place = r.Obec
		}
		segments = append(segments, place+" "+no)
	}
	town := r.District
	if town == "" {
		town = r.Obec
	}
	segments = append(segments, strings.TrimSpace(r.Zip+" "+town))
	return ruianItem{
		Label: strings.Join(segments, ", "),
		Fields: ruianFields{Street: r.Street, HouseNo: r.HouseNo, OrientNo: r.OrientNo, Zip: r.Zip,
			Obec: r.Obec, ObecCast: part, Okres: r.Okres},
	}
}

// writeRuian answers JSON like Starlette's JSONResponse: compact, UTF-8, and
// "[]" (never "null") for nothing.
func writeRuian(w http.ResponseWriter, status int, items []ruianItem) {
	if items == nil {
		items = []ruianItem{}
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(items)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimRight(buf.Bytes(), "\n"))
}

// ruianSuggest is apartments_ruian_suggest. Order: signed out is 401 []; a
// disabled switch, a short query or a rate-limited owner is 200 [] without a
// record; else the lookup is recorded and the rows answered. A database error
// is 200 [] and one log line without the typed text.
func (s *Pages) ruianSuggest(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	at := s.now()
	h, err := session.Load(ctx, s.pool, hostweb.Cookie(r, session.CookieName), at, s.getenv)
	if err != nil {
		log.Printf("ruian suggest: session lookup failed: %v", err)
		writeRuian(w, http.StatusOK, nil)
		return
	}
	if h == nil {
		writeRuian(w, http.StatusUnauthorized, nil)
		return
	}
	if !ruianEnabled(s.getenv) {
		writeRuian(w, http.StatusOK, nil)
		return
	}
	text := ruianUsableQuery(queryLast(r, "q"))
	if text == "" {
		writeRuian(w, http.StatusOK, nil)
		return
	}
	owner := itoa64(h.Workspace.ID)
	limited, err := rateBlocked(ctx, s.pool, ruianRateScope, owner, ruianRateMax, ruianRateWin, at)
	if err != nil {
		log.Printf("ruian suggest: rate check failed: %v", err)
		writeRuian(w, http.StatusOK, nil)
		return
	}
	if limited {
		writeRuian(w, http.StatusOK, nil)
		return
	}
	if err := rateRecord(ctx, s.pool, ruianRateScope, owner, at); err != nil {
		log.Printf("ruian suggest: rate record failed: %v", err)
		writeRuian(w, http.StatusOK, nil)
		return
	}
	rows, err := ruianSearch(ctx, s.pool, text)
	if err != nil {
		log.Printf("ruian suggest: lookup failed: %v", err)
		writeRuian(w, http.StatusOK, nil)
		return
	}
	items := make([]ruianItem, 0, len(rows))
	for _, row := range rows {
		items = append(items, ruianItemOf(row))
	}
	writeRuian(w, http.StatusOK, items)
}
