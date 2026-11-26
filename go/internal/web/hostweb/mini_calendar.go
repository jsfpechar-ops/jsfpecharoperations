package hostweb

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"html/template"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

//go:embed calendar_i18n.json
var calI18nJSON []byte

type calI18nFile struct {
	Host           map[string]map[string]string `json:"host"`
	CalendarLabels map[string]map[string]string `json:"calendar_labels"`
}

var calWidgetLabels map[string]map[string]string

func init() {
	var f calI18nFile
	if err := json.Unmarshal(calI18nJSON, &f); err != nil {
		panic("hostweb: bad calendar_i18n.json: " + err.Error())
	}
	calWidgetLabels = f.CalendarLabels
	for lang, kv := range f.Host {
		if dashStrings[lang] == nil {
			dashStrings[lang] = map[string]string{}
		}
		for k, v := range kv {
			if _, exists := dashStrings[lang][k]; !exists {
				dashStrings[lang][k] = v
			}
		}
	}
}

// calPropIndexCard is one Airbnb-minimal row in the phone Calendar Property Index.
type calPropIndexCard struct {
	ID      int64
	Name    string
	Href    string
	MiniSVG template.HTML
}

// calPageView drives the interactive calendar view & phone property index (Brief 2089).
type calPageView struct {
	ShowPicker     bool
	SingleProperty bool
	ShowBackToAll  bool
	PropertyID     int64
	PropertyName   string
	IndexCards     []calPropIndexCard
	CalScripts     template.HTML
}

func buildCalendarView(data DashboardData, rawCalProp string, today time.Time) calPageView {
	var active []apartmentRow
	for _, a := range data.Apartments {
		if a.Active {
			active = append(active, a)
		}
	}
	var out calPageView
	if len(active) == 0 {
		return out
	}

	var selected *apartmentRow
	if id, err := strconv.ParseInt(strings.TrimSpace(rawCalProp), 10, 64); err == nil && id > 0 {
		for i := range active {
			if active[i].ID == id {
				selected = &active[i]
				break
			}
		}
	}

	if selected != nil {
		out.SingleProperty = true
		out.ShowBackToAll = len(active) >= 2
		out.PropertyID = selected.ID
		out.PropertyName = selected.Name
	} else if len(active) == 1 {
		out.SingleProperty = true
		out.ShowBackToAll = false
		out.PropertyID = active[0].ID
		out.PropertyName = active[0].Name
	} else {
		out.ShowPicker = true
		byApt := make(map[int64][]stays.Row, len(active))
		for _, r := range data.Rows {
			byApt[r.Reservation.ApartmentID] = append(byApt[r.Reservation.ApartmentID], r)
		}
		out.IndexCards = make([]calPropIndexCard, 0, len(active))
		for _, a := range active {
			out.IndexCards = append(out.IndexCards, calPropIndexCard{
				ID:      a.ID,
				Name:    a.Name,
				Href:    fmt.Sprintf("/?cal_view=calendar&cal_property=%d", a.ID),
				MiniSVG: RenderMiniMonthSVG(byApt[a.ID], today),
			})
		}
	}

	out.CalScripts = buildCalendarScripts(active, data.Lang)
	return out
}

func buildCalendarScripts(active []apartmentRow, lang string) template.HTML {
	type propJSON struct {
		ID   int64  `json:"id"`
		Name string `json:"name"`
	}
	props := make([]propJSON, 0, len(active))
	for _, a := range active {
		props = append(props, propJSON{ID: a.ID, Name: a.Name})
	}
	pb, _ := json.Marshal(props)
	labels := calWidgetLabels[lang]
	if len(labels) == 0 {
		labels = calWidgetLabels["en"]
	}
	lb, _ := json.Marshal(labels)
	escJSON := func(b []byte) string {
		return strings.ReplaceAll(string(b), "</", `<\/`)
	}
	return template.HTML(
		`<script type="application/json" data-cal-properties>` + escJSON(pb) + `</script>` + "\n" +
			`<script type="application/json" data-cal-labels>` + escJSON(lb) + `</script>`,
	)
}

// RenderMiniMonthSVG renders a quiet, zero-text 5-week Monday-first dot/bar
// mini-calendar SVG (112x66) for one property starting on Monday of today's week.
func RenderMiniMonthSVG(rows []stays.Row, today time.Time) template.HTML {
	t := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	wd := (int(t.Weekday()) + 6) % 7 // Mon=0..Sun=6
	start := t.AddDate(0, 0, -wd)
	const (
		weeks = 5
		days  = 35
		colW  = 16
		rowH  = 13
	)
	end := start.AddDate(0, 0, days-1)

	var b strings.Builder
	b.WriteString(`<svg class="mini-cal-svg" width="112" height="66" viewBox="0 0 112 66" aria-hidden="true" focusable="false">`)

	// Base subtle dots for all 35 days.
	for i := 0; i < days; i++ {
		cx := (i%7)*colW + 8
		cy := (i/7)*rowH + 7
		fmt.Fprintf(&b, `<circle class="mini-cal-dot" cx="%d" cy="%d" r="2"/>`, cx, cy)
	}

	// Stay bars split across Monday-first week rows.
	for _, r := range rows {
		if r.Reservation.Status != "" && r.Reservation.Status != "active" {
			continue
		}
		from, ok1 := validation.ParseISODate(r.Reservation.DateFrom)
		to, ok2 := validation.ParseISODate(r.Reservation.DateTo)
		if !ok1 || !ok2 {
			continue
		}
		lastNight := to.AddDate(0, 0, -1)
		if lastNight.Before(from) {
			lastNight = from
		}
		if lastNight.Before(start) || from.After(end) {
			continue
		}
		sIdx := int(from.Sub(start).Hours() / 24)
		if sIdx < 0 {
			sIdx = 0
		}
		eIdx := int(lastNight.Sub(start).Hours() / 24)
		if eIdx >= days {
			eIdx = days - 1
		}
		cls := "mini-cal-bar mini-cal-bar-calm"
		if miniStayNeedsAttention(r, t) {
			cls = "mini-cal-bar mini-cal-bar-warn"
		}
		for cur := sIdx; cur <= eIdx; {
			wk := cur / 7
			wkEnd := wk*7 + 6
			segEnd := eIdx
			if segEnd > wkEnd {
				segEnd = wkEnd
			}
			c1 := cur % 7
			c2 := segEnd % 7
			x := c1*colW + 3
			w := (c2-c1+1)*colW - 6
			y := wk*rowH + 4
			fmt.Fprintf(&b, `<rect class="%s" x="%d" y="%d" width="%d" height="6" rx="3"/>`, cls, x, y, w)
			cur = segEnd + 1
		}
	}

	// Today indicator ring.
	tx := wd*colW + 8
	ty := 7
	fmt.Fprintf(&b, `<circle class="mini-cal-today" cx="%d" cy="%d" r="4.8" fill="none" stroke-width="1.5"/>`, tx, ty)
	b.WriteString(`</svg>`)
	return template.HTML(b.String())
}

func miniStayNeedsAttention(r stays.Row, today time.Time) bool {
	st := r.Progress.Status
	if st == "reported" || st == "not_required" {
		return false
	}
	if st == "failed" || r.Progress.Cell.Level == "overdue" || st == "incomplete" {
		return true
	}
	if st == "awaiting_guest" {
		if from, ok := validation.ParseISODate(r.Reservation.DateFrom); ok {
			return !from.After(today.AddDate(0, 0, 7))
		}
	}
	return false
}
