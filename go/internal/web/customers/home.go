package customers

// GET /admin, the operator console home (routes/admin_customers.admin_home,
// App/app/routes/admin_customers.py 25-40, template admin_home.html): what needs
// attention today. Read only; every figure comes from queries that already exist
// in Go (billingweb.OperatorQueue and GetPortfolio, Summary) or from ops.go.

import (
	"fmt"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	billingweb "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/billing"
)

type homeProblem struct {
	Anchor, Title string
	Count         int64
}

type homeOverdue struct {
	ID, OwnerID       int64
	Number, Amount    string
	Late, CustomerStr string
}

type homePerson struct {
	ID    int64
	Name  string
	Date  string
	Link  string
	Plain string
}

type homeView struct {
	Today                         string
	Tabs                          [][]any
	BillingOn                     bool
	Stats                         [][]any
	Problems                      []homeProblem
	QueuesEmpty                   bool
	Overdue                       []homeOverdue
	Trials, Unverified, Ending    []homePerson
	OverdueColumns, TrialsColumns [][]any
	UnverifiedColumns             [][]any
	EndingColumns                 [][]any
}

// nameOr is `display_name or fallback` in the template: an empty name falls back.
func nameOr(name *string, fallback string) string {
	if name != nil && *name != "" {
		return *name
	}
	return fallback
}

// HomeHandler serves GET /admin (admin_home).
func HomeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		ctx := r.Context()
		day := pragueDay(at)
		queue, err := billingweb.OperatorQueue(ctx, pool, day)
		if err != nil {
			serverError(w, err)
			return
		}
		summary, err := Summary(ctx, pool, day)
		if err != nil {
			serverError(w, err)
			return
		}
		view := homeView{Today: day.Format("2006-01-02"), BillingOn: billingOn(getenv)}
		lang := tr(hostweb.Lang(r))
		view.Tabs = adminTabs(lang, "today")
		if view.BillingOn {
			portfolio, err := billingweb.GetPortfolio(ctx, pool, day)
			if err != nil {
				serverError(w, err)
				return
			}
			view.Stats = [][]any{
				{"/admin/fakturace", moneyCZK(portfolio.MRRCZK), lang.t("home.admin.mrr")},
				{"/admin/fakturace", moneyCZK(portfolio.ARRCZK), lang.t("home.admin.arr")},
				{"/admin/customers?state=overdue", summary["overdue"], lang.t("customers.state.overdue")},
				{"/admin/customers?state=trialing", summary["trialing"], lang.t("home.admin.trialing")},
			}
		}
		ops, err := Ops(ctx, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		review, err := ReviewAlertCount(ctx, pool)
		if err != nil {
			serverError(w, err)
			return
		}
		for _, p := range []homeProblem{
			{"ops-filings", lang.t("ops.filings.title"), ops.Filings},
			{"ops-filings", lang.t("ops.stuck.title"), ops.Stuck},
			{"ops-feeds", lang.t("ops.feeds.title"), ops.Feeds},
			{"ops-jobs", lang.t("ops.jobs.title"), ops.Jobs},
			{"ops-mail", lang.t("ops.mail.title"), ops.Mail},
			{"ops-alerts", lang.t("ops.alerts.title"), ops.Alerts},
			{"incidents", lang.t("incidents.review_title"), review},
		} {
			if p.Count != 0 {
				view.Problems = append(view.Problems, p)
			}
		}
		view.QueuesEmpty = len(queue.Overdue) == 0 && len(queue.TrialsEnding) == 0 &&
			len(queue.Unverified) == 0 && len(queue.Ending) == 0
		for _, inv := range queue.Overdue {
			view.Overdue = append(view.Overdue, homeOverdue{ID: inv.ID, OwnerID: inv.OwnerUserID, Number: inv.Number,
				Amount: moneyCZK(inv.TotalHaler), Late: lang.t("home.admin.days_late", "n", inv.DaysLate),
				CustomerStr: nameOr(inv.DisplayName, fmt.Sprint(inv.OwnerUserID))})
		}
		for _, row := range queue.TrialsEnding {
			trial := ""
			if row.TrialEndsAt != nil {
				trial = *row.TrialEndsAt
			}
			view.Trials = append(view.Trials, homePerson{ID: row.OwnerUserID, Name: nameOr(row.DisplayName, fmt.Sprint(row.OwnerUserID)),
				Date: fmtDate(trial), Link: fmt.Sprintf("/admin/customers/%d", row.OwnerUserID)})
		}
		for _, row := range queue.Unverified {
			// The Python row has no username key, so `display_name or username` prints an empty name.
			view.Unverified = append(view.Unverified, homePerson{ID: row.ID, Name: nameOr(row.DisplayName, ""),
				Date: fmtDate(row.CreatedAt), Link: fmt.Sprintf("/admin/customers/%d", row.ID)})
		}
		for _, row := range queue.Ending {
			end := ""
			if row.PeriodEnd != nil {
				end = *row.PeriodEnd
			}
			view.Ending = append(view.Ending, homePerson{ID: row.OwnerUserID, Name: nameOr(row.DisplayName, fmt.Sprint(row.OwnerUserID)),
				Date: fmtDate(end), Link: fmt.Sprintf("/admin/customers/%d", row.OwnerUserID)})
		}
		view.OverdueColumns = [][]any{{lang.t("customers.invoice"), ""}, {lang.t("customers.amount"), "r"},
			{lang.t("home.admin.late"), ""}, {lang.t("home.admin.customer"), ""}}
		view.TrialsColumns = [][]any{{lang.t("home.admin.customer"), ""}, {lang.t("customers.trial_end"), ""}, {lang.t("home.admin.open"), ""}}
		view.UnverifiedColumns = [][]any{{lang.t("home.admin.customer"), ""}, {lang.t("customers.created"), ""}, {lang.t("home.admin.open"), ""}}
		view.EndingColumns = [][]any{{lang.t("home.admin.customer"), ""}, {lang.t("customers.period_end"), ""}}
		p := layout.Page{Title: lang.t("home.admin.title"), Nav: "admin", BodyKind: "list", V2: true, AdminWorkspace: true}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, p, pages, "admin_home", view); err != nil {
			serverError(w, err)
		}
	}
}
