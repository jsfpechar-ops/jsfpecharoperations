package stays

import (
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// PageSize is reservations_list RESERVATION_PAGE_SIZE.
const PageSize = 5

// reservationRanges is RESERVATION_RANGES plus archive.
var reservationRanges = map[string]struct{}{
	"upcoming": {}, "current": {}, "past": {}, "all": {}, "archive": {},
}

// Params is the parsed GET /reservations query.
type Params struct {
	Status      string
	ApartmentID int64
	DateFrom    string
	DateTo      string
	DateRange   string
	ShowArchive bool
	Report      string
	Page        int
	Raw         url.Values
}

// ParseParams reads the query string like reservations_list (admin.py).
// today is the Prague civil date (calendar day only).
func ParseParams(q url.Values, today time.Time) Params {
	raw := cloneValues(q)
	p := Params{
		Status: strings.TrimSpace(q.Get("status")),
		Report: strings.TrimSpace(q.Get("report")),
		Raw:    raw,
	}
	if p.Status == "" {
		p.Status = "active"
	}
	switch p.Status {
	case "active", "cancelled", "ignored", "all":
	default:
		p.Status = "active"
	}
	p.ApartmentID = queryInt(q, "apartment")
	p.DateFrom = queryDate(q, "from")
	p.DateTo = queryDate(q, "to")
	dateRange := strings.TrimSpace(q.Get("range"))
	archiveScope := q.Get("archive_scope") == "1"
	p.ShowArchive = dateRange == "archive" || archiveScope
	if _, ok := reservationRanges[dateRange]; !ok {
		if p.DateFrom != "" || p.DateTo != "" || (archiveScope && dateRange == "custom") {
			dateRange = "custom"
		} else {
			dateRange = "upcoming"
		}
	}
	p.DateRange = dateRange
	applyRangeDates(&p, today)
	if n := queryInt(q, "page"); n > 0 {
		p.Page = int(n)
	} else {
		p.Page = 1
	}
	return p
}

func applyRangeDates(p *Params, today time.Time) {
	tISO := formatISODate(today)
	yesterday := formatISODate(today.AddDate(0, 0, -1))
	switch p.DateRange {
	case "upcoming":
		p.DateFrom, p.DateTo = tISO, ""
	case "past":
		p.DateFrom, p.DateTo = "", yesterday
	case "current":
		p.DateFrom, p.DateTo = tISO, tISO
	case "all", "archive":
		p.DateFrom, p.DateTo = "", ""
	}
}

func queryDate(q url.Values, key string) string {
	raw := strings.TrimSpace(q.Get(key))
	t, ok := validation.ParseISODate(raw)
	if !ok {
		return ""
	}
	return t.Format("2006-01-02")
}

func queryInt(q url.Values, key string) int64 {
	raw := strings.TrimSpace(q.Get(key))
	if raw == "" {
		return 0
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0
	}
	return n
}

func cloneValues(q url.Values) url.Values {
	out := make(url.Values, len(q))
	for k, vs := range q {
		cp := make([]string, len(vs))
		copy(cp, vs)
		out[k] = cp
	}
	return out
}

func formatISODate(t time.Time) string {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC).Format("2006-01-02")
}
