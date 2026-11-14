package stayfees

// GET /stay-fees: routes/stay_fees.py stay_fees_list (lines 165-260) with the
// template stay_fees.html. Brief 1581.

import (
	"html/template"
	"net/http"
	"strconv"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// pgFeeStatuses is STAY_FEE_STATUSES: the status filter (value, label key).
var pgFeeStatuses = [][2]string{
	{"attention", "stay_fees.needs_setup"},
	{"waiting", "stay_fees.status.in_progress"},
	{"ready", "stay_fees.status.ready"},
	{"saved", "stay_fees.status.saved"},
}

const pgIssuePeriodRunning = "stay_fees.issue.period_running"

// rowStatus is _row_status.
func pgRowStatus(unset, frozen bool, issues []string) string {
	switch {
	case unset:
		return "attention"
	case frozen:
		return "saved"
	case len(issues) == 1 && issues[0] == pgIssuePeriodRunning:
		return "waiting"
	case len(issues) > 0:
		return "attention"
	}
	return "ready"
}

// pgCopySource is the property a not yet set up one can take its council setup from.
type pgCopySource struct {
	ID                         int64
	Name, Cadence, VS, Account string
	Rate                       int64
	AuthorityName, Databox     string
}

// pgListRow is one entry of `periods` in the template.
type pgListRow struct {
	ID                        int64
	Name, Obec                string
	Unset                     bool
	Status                    string
	Issues                    []string
	Step                      int
	Cadence                   string
	RateCZK                   int
	Liable, Exempt            int
	TotalDisplay              string
	Version                   int
	PeriodLabel               string
	TableLabel                string
	PayTotalCZK               int
	PayTotalDisplay           string
	PayQR                     template.URL
	PayAccount, PayVS         string
	CopyFrom                  *pgCopySource
	ReportURL, PDFURL, SetURL string
}

type pgListData struct {
	Tabs          []pageTab
	EmailsOn      bool
	Filter        pgFilterView
	Rows          []pgListRow
	MonthKey      string
	FeeReturn     string
	HasProperties bool
	FilterActive  bool
	BulkReady     []int64
	BulkSaved     int
	AllUnset      bool
}

// listApartments is the apartment query of the list: live, not archived properties by name.
func (c *call) pgListApartments() ([]apartment, map[int64]*pgCopySource, error) {
	rows, err := c.pool.Query(c.r.Context(),
		`SELECT id, COALESCE(internal_name, ''), COALESCE(addr_obec, ''), stay_fee_rate_czk,
		   COALESCE(stay_fee_cadence, ''), COALESCE(stay_fee_vs, ''), COALESCE(stay_fee_council_account, ''),
		   COALESCE(stay_fee_council_iban, ''), COALESCE(stay_fee_authority_name, ''),
		   COALESCE(stay_fee_authority_databox, '')
		 FROM apartment WHERE owner_user_id = $1 AND archived_at IS NULL AND active = 1
		 ORDER BY internal_name, id`, c.owner)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	var list []apartment
	sources := map[int64]*pgCopySource{}
	for rows.Next() {
		var a apartment
		var cadence, vs, account, iban, authority, databox string
		if err := rows.Scan(&a.ID, &a.Name, &a.Obec, &a.Rate, &cadence, &vs, &account, &iban, &authority, &databox); err != nil {
			return nil, nil, err
		}
		if account == "" {
			account = iban
		}
		list = append(list, a)
		sources[a.ID] = &pgCopySource{ID: a.ID, Name: a.Name, Cadence: cadence, VS: vs, Account: account,
			Rate: a.Rate, AuthorityName: authority, Databox: databox}
	}
	return list, sources, rows.Err()
}

func init() {
	pageAdd("GET /stay-fees", func(d deps) http.HandlerFunc { return d.pgListPage })
}

func (d deps) pgListPage(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r)
	if c == nil {
		return
	}
	if err := c.pgList(); err != nil {
		c.fail(err)
	}
}

func (c *call) pgList() error {
	ctx := c.r.Context()
	today := pragueDay(c.at)
	apartments, sources, err := c.pgListApartments()
	if err != nil {
		return err
	}
	ids := make([]int64, len(apartments))
	for i, a := range apartments {
		ids[i] = a.ID
	}
	statusKeys := make([]string, len(pgFeeStatuses))
	for i, s := range pgFeeStatuses {
		statusKeys[i] = s[0]
	}
	def := defaultMonth(today)
	view := pgParseFilter(c.r.URL.Query(), today, def, statusKeys, ids)
	month := view.Month

	keys, err := secure.LoadDataKeys(c.getenv)
	if err != nil {
		return err
	}
	dec := stayfee.FernetDecrypter(keys)
	periods, err := c.pgOwnerPeriods(dec, month)
	if err != nil {
		return err
	}
	feeReturn := pgListReturn(c.r.URL.RawQuery)
	monthQ := monthKey(month)
	var rows []pgListRow
	configured := map[int64]bool{}
	for _, p := range periods {
		ap := p.Apartment
		configured[ap.ID] = true
		group := stayfee.ReportGroup(ap, month, p, "")
		ic, err := stayfee.LoadIssueContext(ctx, c.pool, dec, group)
		if err != nil {
			return err
		}
		issues := stayfee.ReportIssues(group, today, ic)
		if !p.Frozen && !p.First.IsZero() {
			n, err := stayfee.UnsignedStays(ctx, c.pool, dec, ap.ID, p.First, p.Last, p)
			if err != nil {
				return err
			}
			if n > 0 {
				issues = append(issues, "stay_fees.issue.unsigned")
			}
		}
		row := pgListRow{
			ID: ap.ID, Name: ap.InternalName, Obec: ap.AddrObec, Issues: issues,
			Cadence: p.Cadence, RateCZK: p.RateCZK, Liable: p.LiableNights, Exempt: p.ExemptNights,
			TotalDisplay: stayfee.FormatCZK(p.TotalCZK), Version: p.Version,
			PeriodLabel: pgPeriodLabel(c.lang, group.Cadence, month), TableLabel: pgPeriodLabel(c.lang, p.Cadence, month),
			PayTotalCZK: group.TotalCZK, PayTotalDisplay: stayfee.FormatCZK(group.TotalCZK),
		}
		if p.Frozen {
			if pay := stayfee.PaymentDetails(group); pay != nil {
				if row.PayQR, err = pgQrOf(pay.SPAYD); err != nil {
					return err
				}
				row.PayAccount, row.PayVS = pay.Account, pay.VS
				if row.PayAccount == "" {
					row.PayAccount = pay.IBANDisplay
				}
			}
			row.Step = 2
			if p.PaidAt != "" {
				row.Step = 3
			}
		} else {
			row.Step = 1
		}
		row.Status = pgRowStatus(false, p.Frozen, issues)
		rows = append(rows, row)
	}
	for _, a := range apartments {
		if configured[a.ID] {
			continue
		}
		row := pgListRow{ID: a.ID, Name: a.Name, Obec: a.Obec, Unset: true, Status: "attention"}
		for _, cand := range apartments {
			if feeCopySource(a, cand) {
				row.CopyFrom = sources[cand.ID]
				break
			}
		}
		rows = append(rows, row)
	}
	kept := rows[:0]
	for _, row := range rows {
		if (view.ApartmentID == 0 || row.ID == view.ApartmentID) && (view.Status == "" || row.Status == view.Status) {
			kept = append(kept, row)
		}
	}
	rows = kept
	pgSortByName(rows, func(r pgListRow) string { return r.Name }, func(r pgListRow) int64 { return r.ID })

	data := pgListData{
		Filter:   pgFilterContext(c.lang, view, "/stay-fees", today, apartments, pgFeeStatuses),
		MonthKey: monthQ, FeeReturn: feeReturn, HasProperties: len(apartments) > 0,
		FilterActive: month != def || view.ApartmentID != 0 || view.Status != "",
		AllUnset:     true,
	}
	for i := range rows {
		row := &rows[i]
		idq := strconv.FormatInt(row.ID, 10)
		row.SetURL = pgFeeSettingsURL(row.ID, feeReturn)
		row.ReportURL = "/stay-fees/" + idq + "?month=" + monthQ
		row.PDFURL = "/stay-fees/" + idq + "/pdf?month=" + monthQ
		if row.Unset {
			continue
		}
		data.AllUnset = false
		switch row.Status {
		case "ready":
			data.BulkReady = append(data.BulkReady, row.ID)
		case "saved":
			data.BulkSaved++
		}
	}
	data.Rows = rows
	if data.EmailsOn, err = c.pgEmailsEnabled(); err != nil {
		return err
	}
	if data.Tabs, err = c.pgInvoiceTabs(); err != nil {
		return err
	}
	page := layout.Page{Title: pageT(c.lang, "stay_fees.title"), Nav: "stay_fees", BodyKind: "list", V2: true, HowKey: "stay_fees"}
	return c.pgRender(page, "stay_fees", data)
}

// emailsEnabled is stay_fee_auto.emails_enabled for the workspace owner.
func (c *call) pgEmailsEnabled() (bool, error) {
	var optOut int64
	err := c.pool.QueryRow(c.r.Context(), `SELECT COALESCE(stay_fee_emails_opt_out, 0) FROM user_account WHERE id = $1`,
		c.owner).Scan(&optOut)
	if err != nil {
		if pgIsNoRows(err) {
			return false, nil
		}
		return false, err
	}
	return optOut == 0, nil
}
