package stays

import (
	"net/url"
	"sort"
	"strconv"
	"strings"
)

// Chip is one range pill on the stays list.
type Chip struct {
	Key, Label, Href string
	Current          bool
}

// View is the data side of GET /reservations (no template).
type View struct {
	Rows             []Row
	Total            int
	Page             int
	PageCount        int
	Chips            []Chip
	FilterSummary    string
	ResetHref        string
	PrevURL, NextURL string
	Params           Params
	ReadySendCount   int
	ManualSend       bool
}

// BuildView fills chips, pager URLs and filter metadata on top of a list query.
func BuildView(p Params, rows []Row, total, page, pageCount, readySend int, manualSend bool) View {
	v := View{
		Rows:           rows,
		Total:          total,
		Page:           page,
		PageCount:      pageCount,
		Params:         p,
		Chips:          buildChips(p),
		ResetHref:      resetHref(p),
		FilterSummary:  filterSummary(p),
		ReadySendCount: readySend,
		ManualSend:     manualSend,
	}
	if page > 1 {
		v.PrevURL = pageURL(p, page-1)
	}
	if page < pageCount {
		v.NextURL = pageURL(p, page+1)
	}
	return v
}

var chipDefs = [][2]string{
	{"upcoming", "stays.chip.upcoming"},
	{"current", "stays.chip.current"},
	{"past", "stays.chip.past"},
}

func buildChips(p Params) []Chip {
	out := make([]Chip, 0, 6)
	for _, def := range chipDefs {
		out = append(out, Chip{
			Key:     def[0],
			Label:   def[1],
			Href:    chipRangeHref(def[0], p.Status, p.ApartmentID),
			Current: p.DateRange == def[0] && p.Report != "failed" && !p.ShowArchive,
		})
	}
	out = append(out, Chip{
		Key:     "failed",
		Label:   "stays.chip.failed",
		Href:    chipReportFailedHref(p.Status, p.ApartmentID),
		Current: p.Report == "failed",
	})
	out = append(out, Chip{
		Key:     "archive",
		Label:   "stays.chip.archive",
		Href:    chipRangeHref("archive", p.Status, p.ApartmentID),
		Current: p.ShowArchive,
	})
	return out
}

func chipRangeHref(rangeKey, status string, apartmentID int64) string {
	var b strings.Builder
	b.WriteString("/reservations?range=")
	b.WriteString(url.QueryEscape(rangeKey))
	b.WriteString("&status=")
	b.WriteString(url.QueryEscape(status))
	b.WriteString("&apartment=")
	if apartmentID != 0 {
		b.WriteString(strconv.FormatInt(apartmentID, 10))
	}
	return b.String()
}

func chipReportFailedHref(status string, apartmentID int64) string {
	var b strings.Builder
	b.WriteString("/reservations?report=failed&status=")
	b.WriteString(url.QueryEscape(status))
	b.WriteString("&apartment=")
	if apartmentID != 0 {
		b.WriteString(strconv.FormatInt(apartmentID, 10))
	}
	return b.String()
}

func resetHref(p Params) string {
	if p.ShowArchive {
		return "/reservations?range=archive"
	}
	return "/reservations?range=all"
}

func filterSummary(p Params) string {
	// Template builds prose with i18n; the view carries the stable parts only.
	if p.DateRange == "custom" && (p.DateFrom != "" || p.DateTo != "") {
		if p.DateFrom != "" && p.DateTo != "" {
			return p.DateFrom + ".." + p.DateTo
		}
		if p.DateFrom != "" {
			return "from:" + p.DateFrom
		}
		return "to:" + p.DateTo
	}
	return ""
}

func pageURL(p Params, n int) string {
	return "/reservations?" + encodeQuery(p.Raw, n)
}

// encodeQuery keeps every filter key except page, then appends page=n
// (reservations_list page_url).
func encodeQuery(raw url.Values, page int) string {
	keys := make([]string, 0, len(raw))
	for key := range raw {
		if key != "page" {
			keys = append(keys, key)
		}
	}
	sort.Strings(keys)
	var parts []string
	for _, key := range keys {
		for _, v := range raw[key] {
			parts = append(parts, url.QueryEscape(key)+"="+url.QueryEscape(v))
		}
	}
	parts = append(parts, "page="+strconv.Itoa(page))
	return strings.Join(parts, "&")
}
