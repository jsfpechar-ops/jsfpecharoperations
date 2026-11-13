package cleaning

import (
	"bytes"
	"embed"
	"fmt"
	"html/template"
	"strings"
)

//go:embed templates/*.html
var templateFS embed.FS

// iconPaths are the three icons of _icons.html that these pages draw.
var iconPaths = map[string]string{
	"x":             `<path d="M18 6 6 18"/><path d="m6 6 12 12"/>`,
	"chevron-right": `<path d="m9 18 6-6-6-6"/>`,
	"sparkles":      `<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>`,
}

// icon is the icon macro of _icons.html.
func icon(name string, size int, cls string) template.HTML {
	width := "1.75"
	if size <= 16 {
		width = "2"
	}
	class := "ui-icon"
	if cls != "" {
		class += " " + cls
	}
	return template.HTML(fmt.Sprintf(`<svg class="%s" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="%s">%s</svg>`,
		class, size, size, width, name, iconPaths[name]))
}

// item is one cleaning as the templates read it: a missing value is "".
type item struct {
	EventID, PropertyID                              int64
	Property, Date, StartTime, EndTime               string
	Checkout, CheckoutTime, NextArrival, CheckinTime string
	Notes, Instructions, Code, CodeSource, Origin    string
	Overridden, Conflict, TimingUnavailable          bool
}

func itemOf(c *cleaningItem) item {
	return item{
		EventID: c.EventID, PropertyID: c.PropertyID, Property: c.Property, Date: c.Date,
		StartTime: str(c.StartTime), EndTime: str(c.EndTime), Checkout: str(c.Checkout),
		CheckoutTime: str(c.CheckoutTime), NextArrival: str(c.NextArrival), CheckinTime: str(c.CheckinTime),
		Notes: c.Notes, Instructions: c.Instructions, Code: c.Code, CodeSource: c.CodeSource, Origin: c.Origin,
		Overridden: c.Overridden, Conflict: c.Conflict, TimingUnavailable: c.TimingUnavailable,
	}
}

type group struct {
	Day   string
	Items []item
}

type section struct {
	Key   string
	Items []item
}

// phone is the part of _cleaning_table.html that the phone layout shows.
type phone struct {
	Today, Week, WeekHead, WeekRest, Later []item
	Hidden                                 int
	Headline, ShowMore                     string
}

// page is everything the cleaning templates read.
type page struct {
	Lang, Today, Tier, Source, From, To string
	Groups                              []group
	Sections                            []section
	Phone                               phone
	Props                               []propOut
	LabelsScript, CalScripts            template.HTML
}

// groupsOf is routes/cleaning._groups: consecutive cleanings of one date.
func groupsOf(list []*cleaningItem) []group {
	var out []group
	for _, c := range list {
		if n := len(out); n > 0 && out[n-1].Day == c.Date {
			out[n-1].Items = append(out[n-1].Items, itemOf(c))
			continue
		}
		out = append(out, group{Day: c.Date, Items: []item{itemOf(c)}})
	}
	return out
}

// sectionsOf is routes/cleaning._sections: today, this week, later; empty ones
// are left out except today.
func sectionsOf(list []*cleaningItem, todayISO string) []section {
	day, _ := parseDay(todayISO)
	weekEnd := iso(day.AddDate(0, 0, 6))
	buckets := map[string][]item{}
	for _, c := range list {
		switch {
		case c.Date == todayISO:
			buckets["today"] = append(buckets["today"], itemOf(c))
		case c.Date > todayISO && c.Date <= weekEnd:
			buckets["week"] = append(buckets["week"], itemOf(c))
		default:
			buckets["later"] = append(buckets["later"], itemOf(c))
		}
	}
	var out []section
	for _, key := range []string{"today", "week", "later"} {
		if len(buckets[key]) > 0 || key == "today" {
			out = append(out, section{Key: key, Items: buckets[key]})
		}
	}
	return out
}

func phoneOf(lang string, sections []section) phone {
	var p phone
	for _, s := range sections {
		switch s.Key {
		case "today":
			p.Today = s.Items
		case "week":
			p.Week = s.Items
		case "later":
			p.Later = s.Items
		}
	}
	p.WeekHead, p.WeekRest = p.Week, nil
	if len(p.Week) > 3 {
		p.WeekHead, p.WeekRest = p.Week[:3], p.Week[3:]
	}
	if extra := len(p.Week) - 3; extra > 0 {
		p.Hidden = extra
	}
	p.Hidden += len(p.Later)
	n := len(p.Today)
	key := "headline_many"
	switch {
	case n == 0:
		key = "headline_none"
	case n == 1:
		key = "headline_one"
	case n < 5:
		key = "headline_few"
	}
	p.Headline = formatCount(ct(lang, key), n)
	p.ShowMore = formatCount(ct(lang, "show_more"), p.Hidden)
	return p
}

// window is the time cell: the explicit window, else checkout to check-in.
func window(lang string, it item) string {
	switch {
	case it.StartTime != "" && it.EndTime != "":
		return it.StartTime + "–" + it.EndTime
	case it.CheckoutTime != "" && it.CheckinTime != "":
		return it.CheckoutTime + "–" + it.CheckinTime
	}
	return ct(lang, "time_missing")
}

func first(s string) string {
	for _, r := range s {
		return string(r)
	}
	return ""
}

var funcs = template.FuncMap{
	"ct": ct, "t": t, "cdate": cdate, "cday": cday, "cshort": cshort, "icon": icon,
	"window": window, "first": first,
	"color":  func(id int64) string { return []string{"teal", "blue", "purple"}[id%3] },
	"scales": func() []string { return []string{"month", "week", "year"} },
	"shows":  func() []string { return []string{"property", "label", "guests"} },
	"rowdata": func(lang string, it item) map[string]any {
		return map[string]any{"Lang": lang, "Item": it}
	},
}

var tmpl = template.Must(template.New("cleaning").Funcs(funcs).ParseFS(templateFS, "templates/*.html"))

func render(name string, p page) (string, error) {
	var b bytes.Buffer
	if err := tmpl.ExecuteTemplate(&b, name, p); err != nil {
		return "", err
	}
	return b.String(), nil
}

// labelsScript is the data-cleaning-labels element of _cleaning_screen.html.
func labelsScript(lang string) template.HTML {
	return template.HTML(`<script type="application/json" data-cleaning-labels>` + tojsonMap(texts.Words[lang]) + `</script>`)
}

// calScripts are the data-cal-properties and data-cal-labels elements of
// _dashboard_calendar.html.
func calScripts(lang string, props []propOut) template.HTML {
	parts := make([]string, 0, len(props))
	for _, p := range props {
		parts = append(parts, tojsonProperty(p.ID, p.Name))
	}
	return template.HTML(`<script type="application/json" data-cal-properties>[` + strings.Join(parts, ",") +
		"]</script>\n  <script type=\"application/json\" data-cal-labels>" + tojsonMap(texts.CalLabels[lang]) + "</script>")
}
