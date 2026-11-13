package customers

// GET /admin/customers/{user_id}: the port of customer_detail and _quote_for in
// App/app/routes/admin_customers.py with admin_customer.html. Brief 1364.

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// fmtDate is validation.fmt_date: an ISO date as DD.MM.YYYY; anything that
// does not parse is passed through.
func fmtDate(v any) string {
	s := ""
	if v != nil {
		s = fmt.Sprint(v)
	}
	r := []rune(s)
	if len(r) > 10 {
		r = r[:10]
	}
	if d, err := time.Parse("2006-01-02", string(r)); err == nil {
		return d.Format("02.01.2006")
	}
	return s
}

// moneyCZK is templating._money_czk: haler as "1 234,50 Kč", thousands
// separated by a no-break space.
func moneyCZK(haler int64) string {
	sign := ""
	if haler < 0 {
		sign, haler = "-", -haler
	}
	digits := strconv.FormatInt(haler/100, 10)
	var b strings.Builder
	for i, c := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteString(" ")
		}
		b.WriteRune(c)
	}
	return fmt.Sprintf("%s%s,%02d Kč", sign, b.String(), haler%100)
}

// truthy is a column value's Python truth: nil, "", 0 are false.
func truthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case string:
		return x != ""
	case int64:
		return x != 0
	case int32:
		return x != 0
	case bool:
		return x
	}
	return true
}

// intOr is int(value or 0) for a column value.
func intOr(v any) (int, error) {
	if !truthy(v) {
		return 0, nil
	}
	n, err := asInt64(v, "number")
	return int(n), err
}

// quoteFor is routes/admin_customers._quote_for: nil without a plan.
func quoteFor(c map[string]any) (*billing.Price, error) {
	plan := text(c, "plan")
	if plan == "" {
		return nil, nil
	}
	apartments, err := intOr(c["apartments_billed"])
	if err != nil {
		return nil, err
	}
	discount, err := intOr(c["discount_percent"])
	if err != nil {
		return nil, err
	}
	interval := text(c, "billing_interval")
	if interval == "" {
		interval = "month"
	}
	p, err := billing.Quote(apartments, plan, interval, truthy(c["addon_ttlock"]), truthy(c["addon_whitelabel"]), discount)
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// orNot is fmt_date(v) if v else customers.not_recorded.
func orNot(lang tr, v any) string {
	if truthy(v) {
		return fmtDate(v)
	}
	return lang.t("customers.not_recorded")
}

func yesNo(lang tr, v any) string {
	if truthy(v) {
		return lang.t("customers.yes")
	}
	return lang.t("customers.no")
}

type buyer struct{ Name, Street, City, Zip, ICO, DIC, Email string }

type activityRow struct{ When, Kind, Detail, Extra string }

type opRow struct{ When, Action, Detail, Actor string }

type invoiceRow struct {
	ID                            int64
	Number, Amount, Due, StateKey string
}

type detailView struct {
	ID                                       int64
	Name, Username, Email, State, StateLabel string
	Active, BillingOn, NotSelf, Meta, Google bool
	HasQuote                                 bool
	DiscountValue, DiscountReason            string
	Tabs, AccountFacts, BillingFacts         [][]any
	MoneyFacts                               [][]any
	ActivityColumns, OpLogColumns            [][]any
	InvoiceColumns                           [][]any
	Buyer                                    buyer
	Activity                                 []activityRow
	OpLog                                    []opRow
	Invoices                                 []invoiceRow
}

// rowsOf reads a list Detail stored under key.
func rowsOf(c map[string]any, key string) ([]map[string]any, error) {
	rows, ok := c[key].([]map[string]any)
	if !ok {
		return nil, fmt.Errorf("customers: %s is %T", key, c[key])
	}
	return rows, nil
}

func buildDetail(lang tr, c map[string]any, consent Consent, adminID int64, billingEnabled bool) (detailView, error) {
	id, err := asInt64(c["id"], "id")
	if err != nil {
		return detailView{}, err
	}
	props, err := asInt64(c["active_properties"], "active_properties")
	if err != nil {
		return detailView{}, err
	}
	state := text(c, "customer_state")
	v := detailView{
		ID: id, Name: text(c, "display_name"), Username: text(c, "username"), Email: text(c, "email"),
		State: state, StateLabel: lang.t("customers.state." + state), Active: truthy(c["active"]),
		BillingOn: billingEnabled, NotSelf: id != adminID, Meta: consent.Meta != 0, Google: consent.Google != 0,
		Tabs:           adminTabs(lang, "customers"),
		DiscountReason: text(c, "discount_reason"),
	}
	if v.Name == "" {
		v.Name = v.Username
	}
	email := lang.t("customers.not_recorded")
	if v.Email != "" {
		email = v.Email
	}
	v.AccountFacts = [][]any{
		{lang.t("customers.search"), email},
		{lang.t("customers.created"), fmtDate(c["created_at"])},
		{lang.t("customers.verified"), orNot(lang, c["email_verified_at"])},
		{lang.t("customers.last_login"), orNot(lang, c["last_login_at"])},
		{lang.t("customers.properties"), props},
	}
	interval := text(c, "billing_interval")
	v.BillingFacts = [][]any{
		{lang.t("customers.plan"), planName(lang, text(c, "plan"))},
		{lang.t("customers.period"), period(lang, interval)},
		{lang.t("customers.trial_start"), orNot(lang, c["trial_started_at"])},
		{lang.t("customers.trial_end"), orNot(lang, c["trial_ends_at"])},
		{lang.t("customers.period_start"), orNot(lang, c["period_start"])},
		{lang.t("customers.period_end"), orNot(lang, c["period_end"])},
		{lang.t("customers.ttlock"), yesNo(lang, c["addon_ttlock"])},
		{lang.t("customers.whitelabel"), yesNo(lang, c["addon_whitelabel"])},
	}
	quote, err := quoteFor(c)
	if err != nil {
		return detailView{}, err
	}
	discount, err := intOr(c["discount_percent"])
	if err != nil {
		return detailView{}, err
	}
	v.DiscountValue = strconv.Itoa(discount)
	if quote != nil {
		v.HasQuote = true
		disc := lang.t("customers.money.no_discount")
		if discount != 0 {
			disc = strconv.Itoa(discount) + " %"
		}
		monthly := quote.Total
		if interval != "month" {
			monthly = quote.Total / 12 // floor: totals are never negative
		}
		v.MoneyFacts = [][]any{
			{lang.t("customers.money.list"), strconv.Itoa(quote.List) + " Kč"},
			{lang.t("customers.money.discount"), disc},
			{lang.t("customers.money.net"), strconv.Itoa(quote.Total) + " Kč"},
			{lang.t("customers.money.monthly"), strconv.Itoa(monthly) + " Kč"},
		}
	}
	prefill, ok := c["buyer_prefill"].(map[string]string)
	if !ok {
		return detailView{}, fmt.Errorf("customers: buyer_prefill is %T", c["buyer_prefill"])
	}
	v.Buyer = buyer{Name: prefill["buyer_name"], Street: prefill["buyer_street"], City: prefill["buyer_city"],
		Zip: prefill["buyer_zip"], ICO: prefill["buyer_ico"], DIC: prefill["buyer_dic"], Email: prefill["buyer_email"]}
	if v.Buyer.Name == "" {
		v.Buyer.Name = text(c, "display_name")
	}
	if v.Buyer.Email == "" {
		v.Buyer.Email = v.Email
	}
	when := lang.t("customers.activity.when")
	v.ActivityColumns = [][]any{{when, ""}, {lang.t("customers.activity.kind"), ""}, {lang.t("customers.activity.what"), ""}}
	v.OpLogColumns = [][]any{{when, ""}, {lang.t("customers.oplog.action"), ""}, {lang.t("customers.oplog.who"), ""}}
	v.InvoiceColumns = [][]any{{lang.t("customers.invoice"), ""}, {lang.t("customers.amount"), "r"},
		{lang.t("customers.due"), ""}, {lang.t("customers.state"), ""}}
	activity, err := rowsOf(c, "activity")
	if err != nil {
		return detailView{}, err
	}
	for _, ev := range activity {
		v.Activity = append(v.Activity, activityRow{When: fmtDate(ev["at"]), Kind: text(ev, "kind"),
			Detail: text(ev, "detail"), Extra: text(ev, "extra")})
	}
	oplog, err := rowsOf(c, "operator_log")
	if err != nil {
		return detailView{}, err
	}
	for _, row := range oplog {
		v.OpLog = append(v.OpLog, opRow{When: fmtDate(row["at"]), Action: text(row, "action"),
			Detail: text(row, "detail"), Actor: text(row, "actor")})
	}
	invoices, err := rowsOf(c, "invoices")
	if err != nil {
		return detailView{}, err
	}
	for _, inv := range invoices {
		invID, err := asInt64(inv["id"], "id")
		if err != nil {
			return detailView{}, err
		}
		total, err := asInt64(inv["total_haler"], "total_haler")
		if err != nil {
			return detailView{}, err
		}
		key := "billing.invoices.state.open"
		switch {
		case truthy(inv["voided"]) || text(inv, "kind") == "storno":
			key = "billing.invoices.state.void"
		case truthy(inv["paid_on"]):
			key = "billing.invoices.state.paid"
		}
		v.Invoices = append(v.Invoices, invoiceRow{ID: invID, Number: text(inv, "number"),
			Amount: moneyCZK(total), Due: fmtDate(inv["due_date"]), StateKey: key})
	}
	return v, nil
}

// notFound is HTTPException(404) as FastAPI answers it.
func notFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
}

// DetailHandler serves GET /admin/customers/{user_id} (customer_detail).
// billing.account is not read: the template uses no column of it.
func DetailHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		userID, err := strconv.ParseInt(r.PathValue("user_id"), 10, 64)
		if err != nil {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return
		}
		ctx := r.Context()
		c, err := Detail(ctx, pool, userID)
		if err != nil {
			serverError(w, err)
			return
		}
		if c == nil {
			notFound(w)
			return
		}
		consent, err := ConsentCounts(ctx, pool, userID)
		if err != nil {
			serverError(w, err)
			return
		}
		lang := tr(hostweb.Lang(r))
		view, err := buildDetail(lang, c, consent, host.Account.ID, billingOn(getenv))
		if err != nil {
			serverError(w, err)
			return
		}
		p := layout.Page{Title: view.Name, Nav: "users", BodyKind: "detail", V2: true, AdminWorkspace: true,
			BackURL: page}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, p, pages, "admin_customer", view); err != nil {
			serverError(w, err)
		}
	}
}
