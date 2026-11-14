package stayfees

// Host HTML pages of the stay fee area (brief 1581: the list, brief 1582: the
// detail page). Python reference: App/app/routes/stay_fees.py and the
// templates stay_fees.html and stay_fee_detail.html, drawn inside the host
// layout (hostweb/layout). Every file of this part starts with "page". The
// routes are dormant until the owner routes the paths to Go.

import (
	"embed"
	"errors"
	"fmt"
	"html/template"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"time"
)

//go:embed page_i18n.json
var pageJSON []byte

// pageCatalog holds the host texts of the two pages (page_i18n_keys.txt lists the keys).
var pageCatalog = hostweb.Load(pageJSON)

//go:embed pagetemplates/*.tmpl
var pageFiles embed.FS

// pageFuncs are the Jinja filters and calls of the two templates. A page func
// may not reuse a layout func name.
var pageFuncs = template.FuncMap{
	"first_letter": pgFirstLetter,
}

var pageSet = layout.MustParseFuncs(pageCatalog, pageFuncs, pageFiles, "pagetemplates/*.tmpl")

// firstLetter is (value or '?')[:1].
func pgFirstLetter(s string) string {
	if s == "" {
		return "?"
	}
	r, _ := utf8.DecodeRuneInString(s)
	return string(r)
}

// pageT translates one key in lang with name/value pairs, like the template t().
func pageT(lang, key string, kv ...any) string {
	var params map[string]any
	if len(kv) > 0 {
		params = map[string]any{}
		for i := 0; i+1 < len(kv); i += 2 {
			params[kv[i].(string)] = kv[i+1]
		}
	}
	return pageCatalog.T(lang, key, params)
}

// pageRoute is one page of this part; each page file adds its own in init().
type pageRoute struct {
	pattern string
	build   func(deps) http.HandlerFunc
}

var pageRouteList []pageRoute

func pageAdd(pattern string, build func(deps) http.HandlerFunc) {
	pageRouteList = append(pageRouteList, pageRoute{pattern, build})
}

// PageRoutes are the host pages of this part: GET /stay-fees (brief 1581) and
// GET /stay-fees/{apartment_id} (brief 1582). The literal GET /stay-fees/pdfs.zip
// is more specific, so the mux keeps it away from the detail pattern.
func PageRoutes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	d := deps{pool, getenv, now}
	out := make([]Route, 0, len(pageRouteList))
	for _, r := range pageRouteList {
		out = append(out, Route{r.pattern, r.build(d)})
	}
	return out
}

// pyQuote is urllib.parse.quote(value, safe=""): everything but letters,
// digits and _.-~ is percent-encoded.
func pgPyQuote(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9', c == '_', c == '.', c == '-', c == '~':
			b.WriteByte(c)
		default:
			fmt.Fprintf(&b, "%%%02X", c)
		}
	}
	return b.String()
}

// feeSettingsURL is fee_settings_url: the property Settings, Reporting & fees.
func pgFeeSettingsURL(apartmentID int64, returnTo string) string {
	u := "/apartments/" + strconv.FormatInt(apartmentID, 10) + "?view=settings&section=reporting"
	if back := feeReturnPath(returnTo, apartmentID); back != "" {
		u += "&return_to=" + pgPyQuote(back)
	}
	return u + "#stay-fee-settings"
}

// feeOperatorURL is fee_operator_url: where a missing payer is fixed.
func pgFeeOperatorURL(apartmentID, legalEntityID int64, returnTo string) string {
	if legalEntityID != 0 {
		return "/entities?edit=" + strconv.FormatInt(legalEntityID, 10)
	}
	u := "/apartments/" + strconv.FormatInt(apartmentID, 10) + "?view=settings&section=property"
	if back := feeReturnPath(returnTo, apartmentID); back != "" {
		u += "&return_to=" + pgPyQuote(back)
	}
	return u + "#settings-property"
}

// listReturn is _list_return: this fee list with its query, without ?lang=.
func pgListReturn(rawQuery string) string {
	// Python re-encodes the pairs in order with urlencode; keep the order of the raw query.
	var parts []string
	for _, pair := range strings.Split(rawQuery, "&") {
		if pair == "" {
			continue
		}
		key, _, _ := strings.Cut(pair, "=")
		if k, err := url.QueryUnescape(key); err == nil && k == "lang" {
			continue
		}
		parts = append(parts, pair)
	}
	enc := make([]string, 0, len(parts))
	for _, pair := range parts {
		k, v, _ := strings.Cut(pair, "=")
		ku, err1 := url.QueryUnescape(k)
		vu, err2 := url.QueryUnescape(v)
		if err1 != nil || err2 != nil {
			enc = append(enc, pair)
			continue
		}
		enc = append(enc, pgPyQuotePlus(ku)+"="+pgPyQuotePlus(vu))
	}
	if len(enc) == 0 {
		return "/stay-fees"
	}
	return "/stay-fees?" + strings.Join(enc, "&")
}

// pyQuotePlus is urllib.parse.quote_plus (urlencode's quoting): space is +.
func pgPyQuotePlus(s string) string {
	return strings.ReplaceAll(pgPyQuote(s), "%20", "+")
}

// pageTabs is page_tabs() for the invoices section: the tabs that are not
// the current one (Invoices and Invoice settings), as (href, label key).
type pageTab struct{ Href, Key string }

// invoiceTabs is _template_section_tabs(request, "invoices", "stay_fees").
func (c *call) pgInvoiceTabs() ([]pageTab, error) {
	href := "/entities"
	rows, err := c.pool.Query(c.r.Context(),
		`SELECT id FROM legal_entity WHERE owner_user_id = $1 AND archived_at IS NULL ORDER BY name`, c.owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(ids) == 1 {
		href = "/entities?edit=" + strconv.FormatInt(ids[0], 10) + "&next=/invoices#entity-invoice"
	}
	return []pageTab{{"/invoices", "nav.invoices"}, {href, "host.invoice_settings"}}, nil
}

// periodLabel is _ui_period_label: the period name in the host's language.
func pgPeriodLabel(lang, cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return pageT(lang, "stay_fees.quarter", "n", (int(month.Month())-1)/3+1, "year", month.Year())
	}
	return pageT(lang, "month."+strconv.Itoa(int(month.Month()))) + " " + strconv.Itoa(month.Year())
}

// render draws one page of this part inside the host layout.
func (c *call) pgRender(page layout.Page, name string, data any) error {
	return layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, page, pageSet, name, data)
}

// ---- list filter (list_filter.py: parse and context, month only / month, property, status)

const pgFilterMinMonth = "2000-01"

type pageFilter struct {
	Month       time.Time
	ApartmentID int64 // 0 = none
	Status      string
}

func pgLastQuery(q url.Values, key string) string {
	v := q[key]
	if len(v) == 0 {
		return ""
	}
	return v[len(v)-1]
}

// parseFilter is list_filter.parse (default month given, no search).
func pgParseFilter(q url.Values, today, def time.Time, statuses []string, apartmentIDs []int64) pageFilter {
	f := pageFilter{Month: def}
	if m, ok := parseMonth(pgLastQuery(q, "month")); ok {
		if !m.Before(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)) && !m.After(monthStart(today.Year(), int(today.Month()))) {
			f.Month = m
		}
	}
	if raw := strings.TrimSpace(pgLastQuery(q, "apartment")); isDigits(raw) {
		if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
			for _, known := range apartmentIDs {
				if known == id {
					f.ApartmentID = id
				}
			}
		}
	}
	status := strings.TrimSpace(pgLastQuery(q, "status"))
	for _, s := range statuses {
		if s == status {
			f.Status = status
		}
	}
	return f
}

type pgFilterChoice struct {
	Value, Label string
	Selected     bool
}

type pgFilterProperty struct {
	ID       int64
	Name     string
	Selected bool
}

type pgMonthChoice struct {
	Key, Label        string
	Selected, Disable bool
}

// pgFilterView is list_filter.context plus what _list_filter.html computes
// inline (the compact variant), with the labels already translated.
type pgFilterView struct {
	Action, PeriodLabelKey string
	MonthKey, MaxMonth     string
	HasNext                bool
	GridYear               int
	MonthChoices           []pgMonthChoice
	PeriodSummary          string
	Properties             []pgFilterProperty
	Statuses               []pgFilterChoice
	SecondaryActive        bool
	ResetHref              string
}

// filterContext is list_filter.context(compact) for the page. props and
// statuses are empty on the detail page.
func pgFilterContext(lang string, f pageFilter, action string, today time.Time, props []apartment, statuses [][2]string) pgFilterView {
	maxMonth := monthStart(today.Year(), int(today.Month()))
	v := pgFilterView{
		Action: action, PeriodLabelKey: "stay_fees.filter.period",
		MonthKey: monthKey(f.Month), MaxMonth: monthKey(maxMonth),
		ResetHref: action,
	}
	v.HasNext = !shiftMonth(f.Month, 1).After(maxMonth)
	v.GridYear = f.Month.Year()
	v.PeriodSummary = pageT(lang, "month."+strconv.Itoa(int(f.Month.Month()))) + " " + strconv.Itoa(f.Month.Year())
	for n := 1; n <= 12; n++ {
		v.MonthChoices = append(v.MonthChoices, pgMonthChoice{
			Key:      fmt.Sprintf("%04d-%02d", v.GridYear, n),
			Label:    pageT(lang, "month."+strconv.Itoa(n)),
			Selected: int(f.Month.Month()) == n,
			Disable:  v.GridYear < 2000 || v.GridYear > maxMonth.Year() || (v.GridYear == maxMonth.Year() && n > int(maxMonth.Month())),
		})
	}
	for _, p := range props {
		v.Properties = append(v.Properties, pgFilterProperty{ID: p.ID, Name: p.Name, Selected: f.ApartmentID == p.ID})
	}
	for _, s := range statuses {
		v.Statuses = append(v.Statuses, pgFilterChoice{Value: s[0], Label: pageT(lang, s[1]), Selected: f.Status == s[0]})
	}
	v.SecondaryActive = f.ApartmentID != 0 || (len(statuses) > 0 && f.Status != "")
	return v
}

// ownerPeriods is stay_fee.owner_periods: the live properties plus the
// disabled ones that still have a sealed period, with their period.
func (c *call) pgOwnerPeriods(dec stayfee.Decrypter, month time.Time) ([]*stayfee.Period, error) {
	ctx := c.r.Context()
	rows, err := c.pool.Query(ctx, stayfee.ApartmentSelect+
		` WHERE owner_user_id = $1 AND archived_at IS NULL AND (stay_fee_rate_czk > 0 OR id IN (
		SELECT apartment_id FROM stay_fee_filing WHERE superseded_at IS NULL)) ORDER BY internal_name, id`, c.owner)
	if err != nil {
		return nil, err
	}
	var aps []*stayfee.Apartment
	for rows.Next() {
		ap, err := stayfee.ScanApartment(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		aps = append(aps, ap)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	u := c.at.UTC()
	opts := stayfee.Opts{ScheduleToday: stayfee.Day(u.Year(), u.Month(), u.Day())}
	var out []*stayfee.Period
	for _, ap := range aps {
		p, err := stayfee.PropertyPeriod(ctx, c.pool, dec, ap, month, opts)
		if err != nil {
			return nil, err
		}
		if p != nil {
			out = append(out, p)
		}
	}
	return out, nil
}

// qrOf is payments.qr_data_uri for a payload; "" for none. It is a URL value
// so html/template keeps the data: scheme.
func pgQrOf(payload string) (template.URL, error) {
	if payload == "" {
		return "", nil
	}
	u, err := payments.QRDataURI(payload)
	return template.URL(u), err
}

// pgSortByName sorts apartments by (internal_name, id), as Python's sort does.
func pgSortByName[T any](rows []T, name func(T) string, id func(T) int64) {
	sort.SliceStable(rows, func(i, j int) bool {
		a, b := name(rows[i]), name(rows[j])
		if a != b {
			return a < b
		}
		return id(rows[i]) < id(rows[j])
	})
}

// isNoRows reports pgx no rows error.
func pgIsNoRows(err error) bool { return errors.Is(err, pgx.ErrNoRows) }
