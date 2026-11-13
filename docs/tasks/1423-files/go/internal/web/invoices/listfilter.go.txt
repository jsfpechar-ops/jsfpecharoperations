package invoices

// The month, property, status and search filter of the invoice list:
// App/app/list_filter.py (parse, query, context) for the one page that uses
// it here. The month is optional on this page (default_month None).

import (
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

const searchMax = 60

type listFilter struct {
	Month       *time.Time
	ApartmentID *int64
	Status      string
	Q           string
}

// queryLast is request.query_params.get: the last value of a key.
func queryLast(q url.Values, key string) string {
	v := q[key]
	if len(v) == 0 {
		return ""
	}
	return v[len(v)-1]
}

// parseFilter is list_filter.parse for default_month None.
func parseFilter(q url.Values, today time.Time, statuses []string, apartmentIDs []int64) listFilter {
	var f listFilter
	if m, ok := stayfee.ParseMonth(queryLast(q, "month")); ok {
		first := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, time.UTC)
		if !m.Before(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)) && !m.After(first) {
			f.Month = &m
		}
	}
	if raw := strings.TrimSpace(queryLast(q, "apartment")); isDigits(raw) {
		if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
			for _, known := range apartmentIDs {
				if known == id {
					f.ApartmentID = &id
				}
			}
		}
	}
	status := strings.TrimSpace(queryLast(q, "status"))
	for _, s := range statuses {
		if s == status {
			f.Status = status
		}
	}
	f.Q = cut(strings.Join(strings.Fields(queryLast(q, "q")), " "), searchMax)
	return f
}

func (f listFilter) monthKey() string {
	if f.Month == nil {
		return ""
	}
	return stayfee.MonthKey(*f.Month)
}

// active is active_count: filters that differ from the default view.
func (f listFilter) active() int {
	n := 0
	if f.Month != nil {
		n++
	}
	if f.ApartmentID != nil {
		n++
	}
	if f.Status != "" {
		n++
	}
	if f.Q != "" {
		n++
	}
	return n
}

// query is ListFilter.query: month, apartment, status, q, urlencoded.
func (f listFilter) query() string {
	var parts []string
	if f.Month != nil {
		parts = append(parts, "month="+url.QueryEscape(f.monthKey()))
	}
	if f.ApartmentID != nil {
		parts = append(parts, "apartment="+strconv.FormatInt(*f.ApartmentID, 10))
	}
	if f.Status != "" {
		parts = append(parts, "status="+url.QueryEscape(f.Status))
	}
	if f.Q != "" {
		parts = append(parts, "q="+url.QueryEscape(f.Q))
	}
	return strings.Join(parts, "&")
}

type filterChoice struct {
	Value    string
	Label    string
	Selected bool
}

type filterProperty struct {
	ID       int64
	Name     string
	Selected bool
}

type monthChoice struct {
	Key      string
	Label    string
	Selected bool
	Disabled bool
}

// filterView is list_filter.context plus what _list_filter.html computes
// inline, with the labels already translated.
type filterView struct {
	Action         string
	PeriodLabelKey string
	MonthOptional  string
	CurrentMonth   string
	MaxMonth       string
	MonthKey       string
	HasMonth       bool
	NextHref       string
	GridYear       int
	MonthChoices   []monthChoice
	PeriodSummary  string
	PropertyLabel  string
	StatusLabel    string
	Status         string
	Q              string
	Properties     []filterProperty
	Statuses       []filterChoice
	Active         int
	ResetHref      string
}

type property struct {
	ID   int64
	Name string
}

// filterContext is list_filter.context(search=True) rendered for the template.
func (c *call) filterContext(f listFilter, today time.Time, props []property, statusKeys [][2]string) filterView {
	maxMonth := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, time.UTC)
	maxKey := stayfee.MonthKey(maxMonth)
	v := filterView{
		Action: "/invoices", PeriodLabelKey: "invoices.filter.period", MonthOptional: "true",
		MaxMonth: maxKey, MonthKey: f.monthKey(), HasMonth: f.Month != nil, Status: f.Status, Q: f.Q,
		Active: f.active(), ResetHref: "/invoices",
	}
	v.CurrentMonth = v.MonthKey
	if v.CurrentMonth == "" {
		v.CurrentMonth = maxKey
	}
	anchor := maxMonth
	if f.Month != nil {
		anchor = *f.Month
	}
	if f.Month != nil {
		if next := stayfee.ShiftMonth(anchor, 1); !next.After(maxMonth) {
			v.NextHref = "/invoices?" + (listFilter{Month: &next, ApartmentID: f.ApartmentID, Status: f.Status, Q: f.Q}).query()
		}
	}
	v.GridYear = maxMonth.Year()
	v.PeriodSummary = c.t("host.filter.all_dates", nil)
	if f.Month != nil {
		v.GridYear = f.Month.Year()
		v.PeriodSummary = c.t("month."+strconv.Itoa(int(f.Month.Month())), nil) + " " + strconv.Itoa(f.Month.Year())
	}
	for n := 1; n <= 12; n++ {
		v.MonthChoices = append(v.MonthChoices, monthChoice{
			Key:      pad4(v.GridYear) + "-" + pad2(int64(n)),
			Label:    c.t("month."+strconv.Itoa(n), nil),
			Selected: f.Month != nil && int(f.Month.Month()) == n,
			Disabled: v.GridYear < 2000 || v.GridYear > maxMonth.Year() || (v.GridYear == maxMonth.Year() && n > int(maxMonth.Month())),
		})
	}
	v.PropertyLabel = c.t("host.filter.all_properties", nil)
	for _, p := range props {
		sel := f.ApartmentID != nil && *f.ApartmentID == p.ID
		v.Properties = append(v.Properties, filterProperty{ID: p.ID, Name: p.Name, Selected: sel})
		if sel {
			v.PropertyLabel = p.Name
		}
	}
	v.StatusLabel = c.t("host.filter.all_statuses", nil)
	for _, s := range statusKeys {
		sel := f.Status == s[0]
		v.Statuses = append(v.Statuses, filterChoice{Value: s[0], Label: c.t(s[1], nil), Selected: sel})
		if sel {
			v.StatusLabel = c.t(s[1], nil)
		}
	}
	return v
}

func pad4(n int) string {
	s := strconv.Itoa(n)
	for len(s) < 4 {
		s = "0" + s
	}
	return s
}
