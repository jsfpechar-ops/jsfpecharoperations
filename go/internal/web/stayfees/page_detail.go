package stayfees

// GET /stay-fees/{apartment_id}: routes/stay_fees.py stay_fee_detail (lines
// 775-848) with _operator_line, _send_panel_context and _guest_lines (849-935)
// and the template stay_fee_detail.html. Brief 1582.

import (
	"context"
	"html/template"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// pgDetailLine is one entry of `lines` in the template.
type pgDetailLine struct {
	GuestID, ReservationID  int64
	Name, StayFrom, StayTo  string
	Nights                  int
	Status, StatusKey       string
	Amount                  int
	AmountDisplay           string
	Facts                   string
	LocalHint, ObecResident bool
	Review                  bool
	Reason                  string
	HasDecision             bool
}

type pgSendPanel struct {
	FilingID                     int64
	AuthorityName, Databox       string
	SubjectCS, BodyCS, Recipient string
}

type pgAdjustmentView struct {
	ID     int64
	Delta  int
	Reason string
	Sealed bool
}

type pgDetailData struct {
	ApartmentID  int64
	MonthKey     string
	Filter       pgFilterView
	Group        *stayfee.Group
	VS           string
	Issues       []string
	Pay          *stayfee.Payment
	PayQR        template.URL
	Frozen       bool
	Correcting   bool
	Version      int
	Lines        []pgDetailLine
	TotalDisplay string
	ExemptCats   []string
	Send         *pgSendPanel
	FilingID     int64
	Adjustments  []pgAdjustmentView
	FeeReturn    string
	SettingsURL  string
	OperatorURL  string
	ScopeRuling  bool
	NoVSOrAuth   map[string]bool
}

func init() {
	pageAdd("GET /stay-fees/{apartment_id}", func(d deps) http.HandlerFunc { return d.pgDetailPage })
}

// pgNotFound is HTTPException(404): FastAPI's JSON body.
func pgNotFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = w.Write([]byte(`{"detail":"Not Found"}`))
}

func (d deps) pgDetailPage(w http.ResponseWriter, r *http.Request) {
	// FastAPI checks the int path parameter before the login guard runs.
	id, ok := pathID(w, r, "apartment_id")
	if !ok {
		return
	}
	c := d.enter(w, r)
	if c == nil {
		return
	}
	if err := c.pgDetail(id); err != nil {
		c.fail(err)
	}
}

// redirectSee is RedirectResponse(url, status_code=303).
func pgRedirectSee(w http.ResponseWriter, location string) {
	w.Header().Set("Location", location)
	w.WriteHeader(http.StatusSeeOther)
}

func (c *call) pgDetail(p pathInt) error {
	ctx := c.r.Context()
	today := pragueDay(c.at)
	def := defaultMonth(today)
	month, ok := parseMonth(pgLastQuery(c.r.URL.Query(), "month"))
	switch {
	case !ok:
		month = def
	case month.After(monthStart(today.Year(), int(today.Month()))):
		pgRedirectSee(c.w, "/stay-fees/"+p.text+"?month="+monthKey(def))
		return nil
	}
	if p.none {
		pgNotFound(c.w)
		return nil
	}
	owned, err := c.apartmentOf(ctx, p.id)
	if err != nil {
		return err
	}
	if owned == nil {
		pgNotFound(c.w)
		return nil
	}
	keys, err := secure.LoadDataKeys(c.getenv)
	if err != nil {
		return err
	}
	dec := stayfee.FernetDecrypter(keys)
	ap, err := stayfee.LoadApartment(ctx, c.pool, p.id)
	if err != nil {
		return err
	}
	covering, err := stayfee.Covering(ctx, c.pool, ap.ID, month)
	if err != nil {
		return err
	}
	if !stayfee.IsActive(ap) && covering == nil {
		c.noSuchApartment()
		return nil
	}
	u := c.at.UTC()
	scheduleToday := stayfee.Day(u.Year(), u.Month(), u.Day())
	correcting := pgLastQuery(c.r.URL.Query(), "correct") == "1"
	var sealed *stayfee.FilingRow
	if correcting {
		sealed = covering
	}
	var period *stayfee.Period
	if correcting && sealed != nil {
		anchor, err := stayfee.PeriodAnchor(sealed.PeriodKey)
		if err != nil {
			return err
		}
		rate, err := stayfee.CorrectionRate(ctx, c.pool, ap, sealed, scheduleToday)
		if err != nil {
			return err
		}
		period, err = stayfee.PropertyPeriod(ctx, c.pool, dec, ap, anchor,
			stayfee.Opts{LiveOnly: true, Cadence: sealed.Cadence, Rate: rate, ScheduleToday: scheduleToday})
		if err != nil {
			return err
		}
	} else {
		period, err = stayfee.PropertyPeriod(ctx, c.pool, dec, ap, month,
			stayfee.Opts{LiveOnly: correcting, ScheduleToday: scheduleToday})
		if err != nil {
			return err
		}
	}
	group := stayfee.ReportGroup(ap, month, period, "")
	frozen := period != nil && period.Frozen && !correcting
	var issues []string
	if !frozen {
		ic, err := stayfee.LoadIssueContext(ctx, c.pool, dec, group)
		if err != nil {
			return err
		}
		issues = stayfee.ReportIssues(group, today, ic)
		n, err := stayfee.UnsignedStays(ctx, c.pool, dec, ap.ID, group.First, group.Last, period)
		if err != nil {
			return err
		}
		if n > 0 {
			issues = append(issues, "stay_fees.issue.unsigned")
		}
		issues = pgDedupe(issues)
	}
	idq := strconv.FormatInt(ap.ID, 10)
	monthQ := monthKey(month)
	feeReturn := "/stay-fees/" + idq + "?month=" + monthQ
	data := pgDetailData{
		ApartmentID: ap.ID, MonthKey: monthQ, Group: group, VS: group.VS, Issues: issues, Frozen: frozen,
		Correcting: correcting, TotalDisplay: stayfee.FormatCZK(group.TotalCZK), ExemptCats: exemptCategories,
		FeeReturn: feeReturn, SettingsURL: pgFeeSettingsURL(ap.ID, feeReturn),
		OperatorURL: pgFeeOperatorURL(ap.ID, ap.LegalEntityID, feeReturn),
		Filter:      pgFilterContext(c.lang, pageFilter{Month: month}, "/stay-fees/"+idq, today, nil, nil),
	}
	if period != nil {
		data.Version = period.Version
	}
	for _, i := range issues {
		if i == "stay_fees.issue.scope_ruling" {
			data.ScopeRuling = true
		}
	}
	if frozen {
		if data.Pay = stayfee.PaymentDetails(group); data.Pay != nil {
			if data.PayQR, err = pgQrOf(data.Pay.SPAYD); err != nil {
				return err
			}
		}
		if covering != nil {
			data.FilingID = covering.ID
			if data.Send, err = c.pgSendPanelFor(ap, period, group, covering, dec); err != nil {
				return err
			}
		}
	}
	if period != nil {
		if data.Lines, err = c.pgGuestLines(ap, period, dec); err != nil {
			return err
		}
		if !frozen {
			if data.Adjustments, err = c.pgAdjustmentViews(ap.ID, period); err != nil {
				return err
			}
		}
	}
	// The toolbar filter has no month required message; the page state is the month.
	title := ap.InternalName + " (" + pgPeriodLabel(c.lang, group.Cadence, month) + ")"
	page := layout.Page{Title: title, Nav: "stay_fees", BodyKind: "detail", BackURL: "/stay-fees?month=" + monthQ}
	return c.pgRender(page, "stay_fee_detail", data)
}

func pgDedupe(in []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(in))
	for _, s := range in {
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}

// operatorLine is _operator_line.
func pgOperatorLine(ctx context.Context, c *call, ap *stayfee.Apartment, dec stayfee.Decrypter) (string, error) {
	e, err := stayfee.LoadEntity(ctx, c.pool, dec, ap.LegalEntityID, false)
	if err != nil {
		return "", err
	}
	name, ico := ap.InternalName, ""
	if e != nil {
		if e.Name != "" {
			name = e.Name
		}
		ico = e.ICO
	}
	if strings.TrimSpace(ico) != "" {
		return name + ", IČO " + strings.TrimSpace(ico), nil
	}
	return name, nil
}

// sendPanelFor is _send_panel_context.
func (c *call) pgSendPanelFor(ap *stayfee.Apartment, period *stayfee.Period, group *stayfee.Group, row *stayfee.FilingRow, dec stayfee.Decrypter) (*pgSendPanel, error) {
	label := ""
	if period != nil {
		label = period.Label
	}
	op, err := pgOperatorLine(c.r.Context(), c, ap, dec)
	if err != nil {
		return nil, err
	}
	var databox string
	if err := c.pool.QueryRow(c.r.Context(), `SELECT COALESCE(stay_fee_authority_databox, '') FROM apartment WHERE id = $1`,
		ap.ID).Scan(&databox); err != nil {
		return nil, err
	}
	amount := stayfee.FormatCZK(group.TotalCZK)
	p := &pgSendPanel{
		FilingID: row.ID, AuthorityName: ap.AuthorityName, Databox: databox,
		SubjectCS: "Ohlášení poplatku z pobytu – " + label + " – " + ap.InternalName,
		BodyCS:    strings.Join([]string{op, label, "Částka k úhradě: " + amount + ". Podrobnosti v příloze."}, "\n"),
	}
	p.Recipient = p.AuthorityName
	if databox != "" {
		p.Recipient += " (" + databox + ")"
	}
	return p, nil
}

// adjustmentViews lists the open adjustments with whether a filing took them.
func (c *call) pgAdjustmentViews(apartmentID int64, period *stayfee.Period) ([]pgAdjustmentView, error) {
	if len(period.Adjustments) == 0 {
		return nil, nil
	}
	rows, err := c.pool.Query(c.r.Context(),
		`SELECT id, COALESCE(filing_id, 0) <> 0 FROM stay_fee_adjustment WHERE apartment_id = $1 AND period_key = $2 AND reversed_at IS NULL`,
		apartmentID, stayfee.PeriodKey(period.Cadence, period.First))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	sealed := map[int64]bool{}
	for rows.Next() {
		var id int64
		var s bool
		if err := rows.Scan(&id, &s); err != nil {
			return nil, err
		}
		sealed[id] = s
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var out []pgAdjustmentView
	for _, a := range period.Adjustments {
		out = append(out, pgAdjustmentView{ID: a.ID, Delta: a.Delta, Reason: a.Reason, Sealed: sealed[a.ID]})
	}
	return out, nil
}

// parseBirthDate is validation.parse_birth_date: a full DDMMYYYY that is a real date.
func pgParseBirthDate(s string) (time.Time, bool) {
	if len(s) != 8 {
		return time.Time{}, false
	}
	day, err1 := strconv.Atoi(s[:2])
	month, err2 := strconv.Atoi(s[2:4])
	year, err3 := strconv.Atoi(s[4:])
	if err1 != nil || err2 != nil || err3 != nil || day == 0 || month == 0 || year == 0 ||
		strings.ContainsAny(s, "+- _") {
		return time.Time{}, false
	}
	t := time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
	if t.Year() != year || int(t.Month()) != month || t.Day() != day {
		return time.Time{}, false
	}
	return t, true
}

// displayBirthDate is validation.display_birth_date: DD.MM.YYYY.
func pgDisplayBirthDate(v string) string {
	n := stayfee.NormaliseBirthDate(v)
	if len(n) == 8 && isDigits(n) {
		return n[:2] + "." + n[2:4] + "." + n[4:]
	}
	return strings.TrimSpace(v)
}

type pgGuestFacts struct {
	Birth, Nationality string
	Age                *int
}

// factsFor reads the display-only facts of the line guests: birth date, age at check-in, nationality.
func (c *call) pgFactsFor(ids []int64, dec stayfee.Decrypter) (map[int64]pgGuestFacts, error) {
	out := map[int64]pgGuestFacts{}
	if len(ids) == 0 {
		return out, nil
	}
	rows, err := c.pool.Query(c.r.Context(),
		`SELECT g.id, COALESCE(g.birth_date, ''), COALESCE(g.birth_date_enc, ''), COALESCE(g.nationality, ''),
		   COALESCE(COALESCE(g.stay_from, r.date_from), '')
		 FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id = ANY($1)`, ids)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var plain, enc, nat, checkIn string
		if err := rows.Scan(&id, &plain, &enc, &nat, &checkIn); err != nil {
			return nil, err
		}
		birthText := plain
		if enc != "" {
			if birthText, err = dec(enc); err != nil {
				return nil, err
			}
		}
		f := pgGuestFacts{Nationality: nat}
		if birthText != "" {
			f.Birth = pgDisplayBirthDate(birthText)
		}
		if birth, ok := pgParseBirthDate(birthText); ok && checkIn != "" {
			head := checkIn
			if len(head) > 10 {
				head = head[:10]
			}
			if when, err := time.Parse("2006-01-02", head); err == nil {
				age := stayfee.AgeOn(birth, when)
				f.Age = &age
			}
		}
		out[id] = f
	}
	return out, rows.Err()
}

// residence reads res_country and res_city of one guest, for a sealed line that does not carry them.
func (c *call) pgResidence(guestID int64, dec stayfee.Decrypter) (string, string, error) {
	var country, plain, enc string
	err := c.pool.QueryRow(c.r.Context(),
		`SELECT COALESCE(res_country, ''), COALESCE(res_city, ''), COALESCE(res_city_enc, '') FROM guest WHERE id = $1`,
		guestID).Scan(&country, &plain, &enc)
	if err != nil {
		if pgIsNoRows(err) {
			return "", "", nil
		}
		return "", "", err
	}
	if enc != "" {
		if plain, err = dec(enc); err != nil {
			return "", "", err
		}
	}
	return country, plain, nil
}

// guestLines is _guest_lines.
func (c *call) pgGuestLines(ap *stayfee.Apartment, period *stayfee.Period, dec stayfee.Decrypter) ([]pgDetailLine, error) {
	ids := make([]int64, 0, len(period.Lines))
	for _, l := range period.Lines {
		ids = append(ids, l.GuestID)
	}
	facts, err := c.pgFactsFor(ids, dec)
	if err != nil {
		return nil, err
	}
	place := foldPlace(ap.AddrObec)
	out := make([]pgDetailLine, 0, len(period.Lines))
	for _, l := range period.Lines {
		country, city := l.ResCountry, l.ResCity
		if country == "" && city == "" {
			// A sealed line from before these keys: Python reads the guest row.
			if country, city, err = c.pgResidence(l.GuestID, dec); err != nil {
				return nil, err
			}
		}
		localHint := strings.ToUpper(country) == "CZE" && foldPlace(city) != "" && foldPlace(city) == place && !l.AutoObecResident
		statusKey := "stay_fees.status.not_subject"
		switch {
		case l.Status == "liable":
			statusKey = "stay_fees.status.liable"
		case l.AutoMinor:
			statusKey = "stay_fees.status.under_18"
		case l.Status == "exempt":
			statusKey = "stay_fees.status.exempt"
		}
		f := facts[l.GuestID]
		var parts []string
		if f.Birth != "" && pgGuestIdentityVisible(c, l.GuestID) {
			parts = append(parts, pageT(c.lang, "stay.detail.guests.born")+" "+f.Birth)
		}
		if f.Age != nil {
			parts = append(parts, pageT(c.lang, "stay_fees.guest.age", "age", *f.Age))
		}
		if f.Nationality != "" {
			name := countries.Name(f.Nationality, c.lang)
			if name == "" {
				name = f.Nationality
			}
			parts = append(parts, name)
		}
		out = append(out, pgDetailLine{
			GuestID: l.GuestID, ReservationID: l.ReservationID, Name: l.Name, StayFrom: l.StayFrom, StayTo: l.StayTo,
			Nights: l.Nights, Status: l.Status, StatusKey: statusKey, Amount: l.AmountCZK,
			AmountDisplay: stayfee.FormatCZK(l.AmountCZK), Facts: strings.Join(parts, " · "),
			LocalHint: localHint, ObecResident: l.AutoObecResident, Review: l.AutoMinor || localHint,
			Reason: l.Reason, HasDecision: l.Decision != nil && *l.Decision != "",
		})
	}
	return out, nil
}

// guestIdentityVisible is access.identity_visible(request, guest_id): an admin
// and a host in their own workspace always, an impersonation only for a
// guest the admin revealed (auth.revealed_guest_ids: the integers in "rv").
func pgGuestIdentityVisible(c *call, guestID int64) bool {
	if c.h.Account.Role == "admin" || !c.h.Impersonating {
		return true
	}
	list, _ := c.h.Payload["rv"].([]any)
	for _, v := range list {
		switch n := v.(type) {
		case float64:
			if int64(n) == guestID {
				return true
			}
		case int64:
			if n == guestID {
				return true
			}
		case int:
			if int64(n) == guestID {
				return true
			}
		}
	}
	return false
}
