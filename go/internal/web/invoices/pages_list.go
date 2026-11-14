package invoices

// GET /invoices: routes/invoices.py invoices_list, lines 370-441, with the
// template invoices.html and the shared list filter.

import (
	"embed"
	"html/template"
	"net/http"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// pageFuncs are the template helpers the Jinja filters and calls become.
var pageFuncs = template.FuncMap{
	// values.get(key, default): the default only when the key is absent.
	"vget": func(m map[string]string, key, def string) string {
		if v, ok := m[key]; ok {
			return v
		}
		return def
	},
	"money_czk": func(haler int64) string { return moneyCZK(haler, 1) },
	"money_qty": moneyCZK,
	"or_zero": func(p *int64) int64 {
		if p == nil {
			return 0
		}
		return *p
	},
	"str":      func(n int64) string { return strconv.FormatInt(n, 10) },
	"safehtml": func(s string) template.HTML { return template.HTML(s) },
}

var pages = layout.MustParseFuncs(catalog, pageFuncs, templateFS, "templates/*.tmpl")

func init() { addRoutes(listRoutes) }

func listRoutes(d deps) []Route {
	return []Route{{"GET /invoices", "/invoices", d.listHandler}}
}

// The status filter: INVOICE_STATUSES with _STATUS_SQL.
var invoiceStatuses = [][2]string{
	{"unpaid", "invoice.state.unpaid"},
	{"paid", "invoice.state.paid"},
	{"correction", "invoices.filter.corrections"},
}

const (
	cancelledSQL = `EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id AND c.kind = 'storno')`
	paidSQL      = `(paid_on IS NOT NULL OR marked_paid_at IS NOT NULL)`
)

var statusSQL = map[string]string{
	"unpaid":     `kind = 'invoice' AND NOT ` + paidSQL + ` AND NOT ` + cancelledSQL,
	"paid":       `kind = 'invoice' AND ` + paidSQL,
	"correction": `kind IN ('storno', 'corrective')`,
}

type listRow struct {
	ID        int64
	Number    string
	IssueDate string
	BuyerName string
	Kind      string
	State     string
	Total     string
	Avatar    string
}

type listData struct {
	SettingsURL string
	Filter      filterView
	Rows        []listRow
	Page, Pages int
	PrevURL     string
	NextURL     string
}

// invoiceDetailsURL is access.invoice_details_url: where "Invoice settings"
// opens.
func invoiceDetailsURL(list []entity) string {
	if len(list) == 1 {
		return "/entities?edit=" + itoa(list[0].ID) + "&next=/invoices#entity-invoice"
	}
	return "/entities"
}

func (d deps) listHandler(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r)
	if c == nil {
		return
	}
	if err := c.list(); err != nil {
		c.fail(err)
	}
}

func (c *call) list() error {
	ctx := c.r.Context()
	today := pragueDay(c.at)
	props, err := c.properties()
	if err != nil {
		return err
	}
	ids := make([]int64, len(props))
	for i, p := range props {
		ids[i] = p.ID
	}
	statusKeys := make([]string, len(invoiceStatuses))
	for i, s := range invoiceStatuses {
		statusKeys[i] = s[0]
	}
	q := c.r.URL.Query()
	view := parseFilter(q, today, statusKeys, ids)
	const pageSize = 50
	pageNo := 1
	if n, err := strconv.Atoi(strings.TrimSpace(queryLast(q, "page"))); err == nil && n > 1 {
		pageNo = n
	}
	where := []string{`owner_user_id IS NOT DISTINCT FROM $1::bigint`}
	args := []any{ownerArg(c.owner)}
	next := func(v any) string {
		args = append(args, v)
		return "$" + strconv.Itoa(len(args))
	}
	if view.Month != nil {
		first, last := stayfee.PeriodBounds("monthly", *view.Month)
		where = append(where, "issue_date >= "+next(first.Format("2006-01-02"))+" AND issue_date <= "+next(last.Format("2006-01-02")))
	}
	if view.ApartmentID != nil {
		where = append(where, "apartment_id = "+next(*view.ApartmentID))
	}
	if view.Status != "" {
		where = append(where, statusSQL[view.Status])
	}
	if view.Q != "" {
		needle := strings.ToLower(view.Q)
		a, b := next(needle), next(needle)
		where = append(where, "(strpos(lower(number), "+a+") > 0 OR strpos(lower(buyer_name), "+b+") > 0)")
	}
	clause := strings.Join(where, " AND ")
	var total int64
	if err := c.pool.QueryRow(ctx, `SELECT COUNT(*) FROM invoice WHERE `+clause, args...).Scan(&total); err != nil {
		return err
	}
	limit, offset := next(int64(pageSize)), next(int64((pageNo-1)*pageSize))
	rows, err := c.pool.Query(ctx,
		`SELECT id, number, issue_date, buyer_name, kind, total_haler,
		   CASE WHEN kind != 'invoice' THEN 'correction' WHEN `+paidSQL+` THEN 'paid'
		        WHEN `+cancelledSQL+` THEN 'cancelled' ELSE 'unpaid' END AS state
		 FROM invoice WHERE `+clause+` ORDER BY issue_date DESC, id DESC LIMIT `+limit+` OFFSET `+offset, args...)
	if err != nil {
		return err
	}
	data := listData{Page: pageNo}
	for rows.Next() {
		var r listRow
		var haler int64
		var issue string
		if err := rows.Scan(&r.ID, &r.Number, &issue, &r.BuyerName, &r.Kind, &haler, &r.State); err != nil {
			rows.Close()
			return err
		}
		r.IssueDate, r.Total = fmtDate(issue), moneyCZK(haler, 1)
		first := r.BuyerName
		if first == "" {
			first = r.Number
		}
		if rs := []rune(first); len(rs) > 0 {
			r.Avatar = strings.ToUpper(string(rs[0]))
		}
		data.Rows = append(data.Rows, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	data.Pages = max(int((total+pageSize-1)/pageSize), 1)
	query := view.query()
	pageHref := "/invoices?"
	if query != "" {
		pageHref += query + "&"
	}
	pageHref += "page="
	if pageNo > 1 {
		data.PrevURL = pageHref + strconv.Itoa(pageNo-1)
	}
	if pageNo < data.Pages {
		data.NextURL = pageHref + strconv.Itoa(pageNo+1)
	}
	list, err := entities(ctx, c.pool, c.owner)
	if err != nil {
		return err
	}
	data.SettingsURL = invoiceDetailsURL(list)
	data.Filter = c.filterContext(view, today, props, invoiceStatuses)
	page := layout.Page{Title: c.t("invoices.title", nil), Nav: "invoices", BodyKind: "list", V2: true, HowKey: "invoices"}
	return layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, page, pages, "invoices", data)
}

// properties is the apartment query of the list: live properties by name.
func (c *call) properties() ([]property, error) {
	rows, err := c.pool.Query(c.r.Context(),
		`SELECT id, COALESCE(internal_name,'') FROM apartment
		 WHERE owner_user_id IS NOT DISTINCT FROM $1::bigint AND archived_at IS NULL ORDER BY internal_name, id`,
		ownerArg(c.owner))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []property
	for rows.Next() {
		var p property
		if err := rows.Scan(&p.ID, &p.Name); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}
