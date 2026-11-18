// Package housebook serves GET /housebook (brief 1704a): routes/admin.py
// housebook_view, the house book page. The rows come from the exports
// package (LoadHousebookPage), the page body is templates/housebook.tmpl in
// the host layout (hostweb/layout). Nothing routes here until the owner adds
// the path to UBYHOST_GO_PATHS.
package housebook

import (
	"embed"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/exports"
)

//go:embed templates/housebook.tmpl
var templateFiles embed.FS

//go:embed i18n.json
var catalogJSON []byte

// catalog is the page catalog, written from host_i18n.py by
// App/scripts/go_host_i18n.py from i18n_keys.txt.
var catalog = hostweb.Load(catalogJSON)

// pages is parsed once; the layout clones it per request.
var pages = layout.MustParseFuncs(catalog, map[string]any{"date_cz": exports.DateCZ}, templateFiles, "templates/housebook.tmpl")

// maxInspectionPDFs is housebook.MAX_INSPECTION_PDFS.
const maxInspectionPDFs = 100

// purposeEN and purposeVI are validation.PURPOSES (en) and
// host_vi_i18n.PURPOSES; Czech comes from exports.PurposeLabelCS.
var purposeEN = map[string]string{
	"00": "Medical", "01": "Business", "02": "Cultural", "03": "Visiting family or friends", "04": "Invitation",
	"05": "Official (political)", "06": "Self-employment", "07": "Sport", "10": "Tourism",
	"11": "Study (training, internship)", "12": "Transit", "13": "Airport transit", "27": "Employment",
	"93": "ADS visa (Chinese nationals)", "99": "Other",
}

var purposeVI = map[string]string{
	"00": "Chữa bệnh", "01": "Kinh doanh", "02": "Văn hóa", "03": "Thăm gia đình hoặc bạn bè", "04": "Theo lời mời",
	"05": "Công vụ (chính trị)", "06": "Tự kinh doanh", "07": "Thể thao", "10": "Du lịch",
	"11": "Học tập (đào tạo, thực tập)", "12": "Quá cảnh", "13": "Quá cảnh sân bay", "27": "Làm việc",
	"93": "Thị thực ADS (công dân Trung Quốc)", "99": "Khác",
}

// purposeLabel is validation.purpose_label(code, lang) for the host languages.
func purposeLabel(code, lang string) string {
	switch lang {
	case "cs":
		return exports.PurposeLabelCS(code)
	case "vi":
		if v, ok := purposeVI[code]; ok {
			return v
		}
		if _, ok := purposeEN[code]; ok {
			return purposeEN[code]
		}
	default:
		if v, ok := purposeEN[code]; ok {
			return v
		}
	}
	return code
}

// rowView is one house-book row with every text the template prints.
type rowView struct {
	exports.HousebookRow
	Initial, FullName, FactsID                  string
	NationalityText, ResidenceText, PurposeText string
	Pill                                        string // ok | not_required | final | rejected | not_sent
}

type presetView struct {
	Key, Href string
	On        bool
}

// pageData is the housebook.html context.
type pageData struct {
	Rows        []rowView
	Archived    []exports.HousebookArchivedRow
	Apartments  []exports.HousebookApartment
	ApartmentID int64
	From, To    string
	Label       string // the chosen property, else host.filter.all_properties
	CSVParams   string // housebook_csv_params
	Presets     []presetView
	MaxPDFs     int
}

// reportedPill is the if-chain of the reported_pill macro on the text of
// housebook._housebook_export_row: only the exact "yes" is green, so a guest
// "yes - filed by hand in UbyPort" shows "not sent", as in Python.
func reportedPill(reported string) string {
	switch {
	case reported == "yes":
		return "ok"
	case strings.HasPrefix(reported, "not required"):
		return "not_required"
	case reported == "NO - rejected, cannot be corrected":
		return "final"
	case strings.HasPrefix(reported, "NO"):
		return "rejected"
	}
	return "not_sent"
}

// firstUpper is (text or ”)[:1] | upper.
func firstUpper(s string) string {
	r, n := utf8.DecodeRuneInString(s)
	if n == 0 {
		return ""
	}
	return strings.ToUpper(string(r))
}

// periodPresets is housebook.period_presets(today): this month, last month, this year.
func periodPresets(today time.Time) [][3]string {
	first := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, time.UTC)
	lastMonthEnd := first.AddDate(0, 0, -1)
	thisMonthEnd := time.Date(today.Year(), today.Month()+1, 0, 0, 0, 0, 0, time.UTC)
	day := func(t time.Time) string { return t.Format("2006-01-02") }
	return [][3]string{
		{"housebook.preset.this_month", day(first), day(thisMonthEnd)},
		{"housebook.preset.last_month", day(time.Date(lastMonthEnd.Year(), lastMonthEnd.Month(), 1, 0, 0, 0, 0, time.UTC)), day(lastMonthEnd)},
		{"housebook.preset.this_year", day(time.Date(today.Year(), 1, 1, 0, 0, 0, 0, time.UTC)), day(time.Date(today.Year(), 12, 31, 0, 0, 0, 0, time.UTC))},
	}
}

// buildPage turns the exports data into the template data.
func buildPage(p *exports.HousebookPage, lang string, at time.Time) pageData {
	d := pageData{Archived: p.Archived, Apartments: p.Apartments, ApartmentID: p.ApartmentID, From: p.From, To: p.To, MaxPDFs: maxInspectionPDFs}
	d.Label = catalog.T(lang, "host.filter.all_properties", nil)
	for _, a := range p.Apartments {
		if p.ApartmentID != 0 && a.ID == p.ApartmentID {
			d.Label = a.Name
		}
	}
	d.CSVParams = "apartment="
	if p.ApartmentID != 0 {
		d.CSVParams += fmt.Sprint(p.ApartmentID)
	}
	l := deadlines.LocalNow(at)
	today := time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
	for _, ps := range periodPresets(today) {
		href := "/housebook?"
		if p.ApartmentID != 0 {
			href += fmt.Sprintf("apartment=%d&", p.ApartmentID)
		}
		href += "from=" + ps[1] + "&to=" + ps[2]
		d.Presets = append(d.Presets, presetView{Key: ps[0], Href: href, On: p.From == ps[1] && p.To == ps[2]})
	}
	for _, r := range p.Rows {
		v := rowView{HousebookRow: r, Initial: firstUpper(r.Surname), Pill: reportedPill(r.Reported),
			FactsID: fmt.Sprintf("housebook-facts-%d", r.GuestID), NationalityText: "—", PurposeText: "—"}
		v.FullName = strings.TrimSpace(r.FirstName + " " + r.Surname)
		if r.Nationality != "" {
			v.NationalityText = countries.Name(r.Nationality, lang) + " (" + r.Nationality + ")"
		}
		var parts []string
		if r.ResStreet != "" {
			parts = append(parts, r.ResStreet)
		}
		if r.ResCity != "" {
			parts = append(parts, r.ResCity)
		}
		if r.ResCountry != "" {
			parts = append(parts, countries.Name(r.ResCountry, lang)+" ("+r.ResCountry+")")
		}
		v.ResidenceText = "—"
		if len(parts) > 0 {
			v.ResidenceText = strings.Join(parts, ", ")
		}
		if label := purposeLabel(r.PurposeCode, lang); label != "" {
			v.PurposeText = label
		}
		d.Rows = append(d.Rows, v)
	}
	return d
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("housebook route failed: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// Handler serves GET /housebook (routes/admin.py housebook_view):
// require_login, then housebook.html in the host layout (nav housebook, body
// kind list, v2, no page header).
func Handler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		w.Header().Set("Cache-Control", "no-store, private")
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if h == nil {
			return
		}
		p, err := exports.LoadHousebookPage(r.Context(), pool, getenv, h, r)
		if err != nil {
			serverError(w, err)
			return
		}
		lang := hostweb.Lang(r)
		page := layout.Page{
			Title:    catalog.T(lang, "housebook.title", nil),
			Nav:      "housebook",
			BodyKind: "list",
			V2:       true,
			HowKey:   "housebook",
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, page, pages, "housebook", buildPage(p, lang, at)); err != nil {
			serverError(w, err)
		}
	}
}
