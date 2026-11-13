package stayfee

// golden_test.go replays testdata/stay_fee_golden.json, written by
// App/scripts/stay_fee_golden.py from the real Python. TestGoldenHelpers pins
// the pure helpers. TestGoldenPure feeds the seed rows to the pure layer through
// an in-memory backend that does what the loader's SQL does. TestGoldenLoader
// loads the same seed into PostgreSQL and runs the real loader; it skips
// without UBYHOST_TEST_DATABASE_URL (CI sets it).

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// scheduleToday stands in for Python's date.today() in schedule_for: any day
// after the seeded periods gives the same figures.
var scheduleToday = Day(2026, 11, 13)

type golden struct {
	Seed            map[string][]map[string]any `json:"seed"`
	Cases           []goldenCase                `json:"cases"`
	ApartmentChecks []map[string]any            `json:"apartment_checks"`
	Helpers         map[string]any              `json:"helpers"`
}

type goldenCase struct {
	Name        string         `json:"name"`
	ApartmentID int64          `json:"apartment_id"`
	Month       string         `json:"month"`
	Today       string         `json:"today"`
	Cadence     *string        `json:"cadence"`
	Rate        *int           `json:"rate"`
	LiveOnly    bool           `json:"live_only"`
	Out         map[string]any `json:"out"`
}

func loadGolden(t *testing.T) *golden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "stay_fee_golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return &g
}

// same compares got, through a JSON round trip, with the Python value.
func same(t *testing.T, name string, got, want any) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal: %v", name, err)
	}
	var norm any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal: %v", name, err)
	}
	if !reflect.DeepEqual(norm, want) {
		w, _ := json.Marshal(want)
		t.Errorf("%s:\n got %s\nwant %s", name, raw, w)
	}
}

func day(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatalf("date %q: %v", s, err)
	}
	return d
}

func isoOrNil(d time.Time, ok bool) any {
	if !ok {
		return nil
	}
	return ISO(d)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// --- seed rows ----------------------------------------------------------------

func sv(m map[string]any, k string) string {
	switch v := m[k].(type) {
	case nil:
		return ""
	case string:
		return v
	case float64:
		return strconv.FormatInt(int64(v), 10)
	case bool:
		return strconv.FormatBool(v)
	}
	return fmt.Sprint(m[k])
}

func iv(m map[string]any, k string) int64 {
	if v, ok := m[k].(float64); ok {
		return int64(v)
	}
	return 0
}

func seedApartment(m map[string]any) *Apartment {
	return &Apartment{
		ID: iv(m, "id"), LegalEntityID: iv(m, "legal_entity_id"), InternalName: sv(m, "internal_name"),
		StayFeeRateCZK: int(iv(m, "stay_fee_rate_czk")), StayFeeCadence: sv(m, "stay_fee_cadence"),
		StayFeeVS: sv(m, "stay_fee_vs"), AuthorityName: sv(m, "stay_fee_authority_name"),
		AuthorityAddress: sv(m, "stay_fee_authority_address"), AuthorityContact: sv(m, "stay_fee_authority_contact"),
		Payee: sv(m, "stay_fee_payee"), Instruction: sv(m, "stay_fee_instruction"),
		CouncilAccount: sv(m, "stay_fee_council_account"), CouncilIBAN: sv(m, "stay_fee_council_iban"),
		ScopeRule: sv(m, "stay_fee_scope_rule"), ScopeReference: sv(m, "stay_fee_scope_reference"),
		Collect: iv(m, "stay_fee_collect") != 0, GuestRails: sv(m, "stay_fee_guest_rails"),
		GuestDefaultRail: sv(m, "stay_fee_guest_default_rail"), RevolutLink: sv(m, "stay_fee_guest_revolut_link"),
		CashNote: sv(m, "stay_fee_guest_cash_note"), AddrObec: sv(m, "addr_obec"), CityEN: sv(m, "city_en"),
		AddrStreet: sv(m, "addr_street"), AddrHouseNo: sv(m, "addr_house_no"),
		AddrOrientNo: sv(m, "addr_orient_no"), AddrZip: sv(m, "addr_zip"), ArchivedAt: sv(m, "archived_at"),
	}
}

func seedFiling(m map[string]any) *FilingRow {
	return &FilingRow{
		ID: iv(m, "id"), ApartmentID: iv(m, "apartment_id"), PeriodKey: sv(m, "period_key"),
		Version: int(iv(m, "version")), Cadence: sv(m, "cadence"), RateCZK: int(iv(m, "rate_czk")),
		LiableDays: int(iv(m, "liable_days")), ExemptDays: int(iv(m, "exempt_days")),
		TotalDueCZK: int(iv(m, "total_due_czk")), TotalCollectedCZK: int(iv(m, "total_collected_czk")),
		PayloadEnc: sv(m, "payload"), CreatedAt: sv(m, "created_at"), SupersededAt: sv(m, "superseded_at"),
		SentAt: sv(m, "sent_at"), SentMessageID: sv(m, "sent_message_id"), PaidAt: sv(m, "paid_at"),
	}
}

func plain(token string) (string, error) { return token, nil }

// --- the two backends -----------------------------------------------------------

type backend interface {
	apartment(id int64) (*Apartment, error)
	entity(id int64, withSignature bool) (*Entity, error)
	propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error)
	check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error)
	unsigned(apartmentID int64, first, last time.Time, p *Period) (int, error)
	register(p *Period) ([]RegisterRow, error)
	hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error)
	netBedDays(apartmentID int64, key string) (int, error)
	schedule(ap *Apartment) ([]RateStep, error)
	filingByID(id int64) (*FilingRow, error)
	latest(apartmentID int64, key string) (*FilingRow, error)
	covering(apartmentID int64, month time.Time) (*FilingRow, error)
	foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error)
}

// memBackend answers from the seed with the pure layer, doing in Go what the
// loader's SQL does.
type memBackend struct {
	seed map[string][]map[string]any
}

func (m memBackend) apartment(id int64) (*Apartment, error) {
	for _, row := range m.seed["apartments"] {
		if iv(row, "id") == id {
			return seedApartment(row), nil
		}
	}
	return nil, ErrNotFound
}

func (m memBackend) entity(id int64, withSignature bool) (*Entity, error) {
	for _, row := range m.seed["legal_entities"] {
		if id != 0 && iv(row, "id") == id {
			e := &Entity{ID: id, Name: sv(row, "name"), Seat: sv(row, "seat"), ICO: sv(row, "ico"),
				ContactEmail: sv(row, "contact_email"), IBAN: sv(row, "iban"), BankAccount: sv(row, "bank_account"),
				SignatureName: sv(row, "signature_name")}
			if withSignature {
				e.SignaturePNG = sv(row, "signature_png")
			}
			return e, nil
		}
	}
	return nil, nil
}

func (m memBackend) guests(match func(g GuestRow, res map[string]any) bool) []GuestRow {
	res := map[int64]map[string]any{}
	for _, r := range m.seed["reservations"] {
		res[iv(r, "id")] = r
	}
	var out []GuestRow
	for _, row := range m.seed["guests"] {
		r := res[iv(row, "reservation_id")]
		g := GuestRow{ID: iv(row, "id"), ReservationID: iv(row, "reservation_id"), Surname: sv(row, "surname"),
			FirstName: sv(row, "first_name"), BirthDate: sv(row, "birth_date"), Nationality: sv(row, "nationality"),
			DocType: sv(row, "doc_type"), DocNumber: sv(row, "doc_number"), ResStreet: sv(row, "res_street"),
			ResCity: sv(row, "res_city"), ResCountry: sv(row, "res_country"), StayFrom: sv(row, "stay_from"),
			StayTo: sv(row, "stay_to"), FeeHostDecision: sv(row, "fee_host_decision"),
			FeeHostReason: sv(row, "fee_host_reason"), SignaturePNG: sv(row, "signature_png"),
			Restricted: sv(row, "restricted_at") != "", ResFrom: sv(r, "date_from"), ResTo: sv(r, "date_to")}
		if sv(row, "archived_at") != "" && match != nil {
			continue
		}
		if match == nil || match(g, r) {
			out = append(out, g)
		}
	}
	return out
}

// periodGuests is periodGuestsWhere plus its ORDER BY.
func (m memBackend) periodGuests(apartmentID int64, first, last time.Time) []GuestRow {
	out := m.guests(func(g GuestRow, r map[string]any) bool {
		from, to := g.StayFrom, g.StayTo
		if from == "" {
			from = g.ResFrom
		}
		if to == "" {
			to = g.ResTo
		}
		return iv(r, "apartment_id") == apartmentID && sv(r, "status") == "active" && sv(r, "source") != "demo" &&
			from <= ISO(last) && to >= ISO(first)
	})
	start := func(g GuestRow) string {
		if g.StayFrom != "" {
			return g.StayFrom
		}
		return g.ResFrom
	}
	sort.SliceStable(out, func(i, j int) bool {
		if a, b := start(out[i]), start(out[j]); a != b {
			return a < b
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func (m memBackend) adjustments(apartmentID int64, key string) (int, []Adjustment) {
	out := []Adjustment{}
	total := 0
	for _, row := range m.seed["adjustments"] {
		if iv(row, "apartment_id") != apartmentID || sv(row, "period_key") != key || sv(row, "reversed_at") != "" {
			continue
		}
		a := Adjustment{ID: iv(row, "id"), Direction: sv(row, "direction"), Mode: sv(row, "mode"),
			BedDays: int(iv(row, "bed_days")), Reason: sv(row, "reason")}
		a.Delta = a.BedDays
		if a.Direction == "remove" {
			a.Delta = -a.Delta
		}
		total += a.Delta
		out = append(out, a)
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return total, out
}

func (m memBackend) rateRows(apartmentID int64) []RateRow {
	var out []RateRow
	for _, row := range m.seed["rates"] {
		if iv(row, "apartment_id") == apartmentID {
			out = append(out, RateRow{EffectiveFrom: sv(row, "effective_from"), RateCZK: int(iv(row, "rate_czk"))})
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].EffectiveFrom < out[j].EffectiveFrom })
	return out
}

func (m memBackend) propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error) {
	if !o.LiveOnly {
		row, err := m.covering(ap.ID, month)
		if err != nil {
			return nil, err
		}
		if row != nil {
			return FrozenSummary(row, ap, plain)
		}
	}
	chosen := ChooseCadence(ap, o.Cadence)
	first, last := PeriodBounds(chosen, month)
	in := PeriodInput{ScheduleToday: o.ScheduleToday, Guests: m.periodGuests(ap.ID, first, last)}
	if o.Rate == nil {
		in.RateRows = m.rateRows(ap.ID)
	}
	_, in.Adjustments = m.adjustments(ap.ID, PeriodKey(chosen, month))
	return BuildPeriod(ap, month, chosen, o.Rate, in)
}

func (m memBackend) check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	o.LiveOnly = true
	period, err := m.propertyPeriod(ap, month, o)
	if err != nil {
		return nil, err
	}
	group := ReportGroup(ap, month, period, o.Cadence)
	var ic IssueContext
	if ic.Entity, err = m.entity(ap.LegalEntityID, false); err != nil {
		return nil, err
	}
	row, err := m.foreignOverlap(ap.ID, group.Cadence, group.First)
	if err != nil {
		return nil, err
	}
	ic.ForeignOverlap = row != nil
	issues := ReportIssues(group, today, ic)
	unsigned, err := m.unsigned(ap.ID, group.First, group.Last, period)
	if err != nil {
		return nil, err
	}
	if unsigned > 0 {
		issues = append(issues, "stay_fees.issue.unsigned")
	}
	return &Checked{Period: period, Group: group, Issues: issues, Key: PeriodKey(group.Cadence, group.First)}, nil
}

func (m memBackend) unsigned(apartmentID int64, first, last time.Time, p *Period) (int, error) {
	if p != nil && !p.Frozen && p.First.Equal(first) && p.Last.Equal(last) && p.Apartment.ID == apartmentID {
		return p.UnsignedGuests, nil
	}
	n := 0
	for _, g := range m.periodGuests(apartmentID, first, last) {
		if !guestSignatureSettled(g) {
			n++
		}
	}
	return n, nil
}

func (m memBackend) register(p *Period) ([]RegisterRow, error) {
	byID := map[int64]GuestRow{}
	for _, g := range m.guests(nil) {
		byID[g.ID] = g
	}
	return RegisterRows(p, byID)
}

func (m memBackend) hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error) {
	e, err := m.entity(g.Anchor.LegalEntityID, true)
	if err != nil {
		return nil, err
	}
	return MakeHlaseni(g, issuedOn, e)
}

func (m memBackend) netBedDays(apartmentID int64, key string) (int, error) {
	total, _ := m.adjustments(apartmentID, key)
	return total, nil
}

func (m memBackend) schedule(ap *Apartment) ([]RateStep, error) {
	return ScheduleFor(ap.StayFeeRateCZK, m.rateRows(ap.ID), scheduleToday)
}

func (m memBackend) filings() []*FilingRow {
	var out []*FilingRow
	for _, row := range m.seed["filings"] {
		out = append(out, seedFiling(row))
	}
	return out
}

func (m memBackend) filingByID(id int64) (*FilingRow, error) {
	for _, f := range m.filings() {
		if f.ID == id {
			return f, nil
		}
	}
	return nil, ErrNotFound
}

func (m memBackend) active(apartmentID int64, keys []string) *FilingRow {
	var best *FilingRow
	for _, f := range m.filings() {
		if f.ApartmentID != apartmentID || f.SupersededAt != "" || !inList(keys, f.PeriodKey) {
			continue
		}
		if best == nil || f.CreatedAt > best.CreatedAt || (f.CreatedAt == best.CreatedAt && f.ID > best.ID) {
			best = f
		}
	}
	return best
}

func (m memBackend) latest(apartmentID int64, key string) (*FilingRow, error) {
	var best *FilingRow
	for _, f := range m.filings() {
		if f.ApartmentID == apartmentID && f.PeriodKey == key && f.SupersededAt == "" &&
			(best == nil || f.Version > best.Version) {
			best = f
		}
	}
	return best, nil
}

func (m memBackend) covering(apartmentID int64, month time.Time) (*FilingRow, error) {
	return m.active(apartmentID, OverlapKeys("monthly", month)), nil
}

func (m memBackend) foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	own := PeriodKey(cadence, month)
	var keys []string
	for _, k := range OverlapKeys(cadence, month) {
		if k != own {
			keys = append(keys, k)
		}
	}
	return m.active(apartmentID, keys), nil
}

// pgBackend runs the real loader.
type pgBackend struct {
	ctx context.Context
	q   Querier
}

func (p pgBackend) apartment(id int64) (*Apartment, error) { return LoadApartment(p.ctx, p.q, id) }
func (p pgBackend) entity(id int64, withSignature bool) (*Entity, error) {
	return LoadEntity(p.ctx, p.q, plain, id, withSignature)
}
func (p pgBackend) propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error) {
	return PropertyPeriod(p.ctx, p.q, plain, ap, month, o)
}
func (p pgBackend) check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	return Check(p.ctx, p.q, plain, ap, month, today, o)
}
func (p pgBackend) unsigned(apartmentID int64, first, last time.Time, period *Period) (int, error) {
	return UnsignedStays(p.ctx, p.q, plain, apartmentID, first, last, period)
}
func (p pgBackend) register(period *Period) ([]RegisterRow, error) {
	return RegisterFor(p.ctx, p.q, plain, period)
}
func (p pgBackend) hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error) {
	return HlaseniFor(p.ctx, p.q, plain, g, issuedOn)
}
func (p pgBackend) netBedDays(apartmentID int64, key string) (int, error) {
	return NetBedDays(p.ctx, p.q, plain, apartmentID, key)
}
func (p pgBackend) schedule(ap *Apartment) ([]RateStep, error) {
	return LoadSchedule(p.ctx, p.q, ap, scheduleToday)
}
func (p pgBackend) filingByID(id int64) (*FilingRow, error) {
	return queryFiling(p.ctx, p.q, `SELECT `+filingColumns+` FROM stay_fee_filing WHERE id = $1`, id)
}
func (p pgBackend) latest(apartmentID int64, key string) (*FilingRow, error) {
	return Latest(p.ctx, p.q, apartmentID, key)
}
func (p pgBackend) covering(apartmentID int64, month time.Time) (*FilingRow, error) {
	return Covering(p.ctx, p.q, apartmentID, month)
}
func (p pgBackend) foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	return ForeignOverlap(p.ctx, p.q, apartmentID, cadence, month)
}

// --- views: the Python dict shapes of the golden ---------------------------------

func lineView(lines []Line) []Line {
	out := make([]Line, len(lines))
	for i, l := range lines {
		if l.RateNights == nil {
			l.RateNights = [][2]int{}
		}
		out[i] = l
	}
	return out
}

func periodView(p *Period) any {
	if p == nil {
		return nil
	}
	v := map[string]any{"cadence": p.Cadence, "first": ISO(p.First), "last": ISO(p.Last), "label": p.Label,
		"rate_czk": p.RateCZK, "lines": lineView(p.Lines), "liable_nights": p.LiableNights,
		"exempt_nights": p.ExemptNights, "total_czk": p.TotalCZK, "rate_segments": p.RateSegments,
		"period_key": p.PeriodKey, "adjustments": []Adjustment{}}
	if p.Frozen {
		v["frozen"] = true
		v["filing_id"] = p.FilingID
		v["version"] = p.Version
		v["total_collected_czk"] = p.TotalCollectedCZK
		v["sent_at"] = nilIfEmpty(p.SentAt)
		v["paid_at"] = nilIfEmpty(p.PaidAt)
		v["sent_message_id"] = nilIfEmpty(p.SentMessageID)
		return v
	}
	v["guest_liable_nights"] = p.GuestLiableNights
	v["adjustment_bed_days"] = p.AdjustmentBedDays
	v["adjustments"] = p.Adjustments
	v["unsigned_guests"] = p.UnsignedGuests
	return v
}

func groupView(g *Group) any {
	periods := []any{}
	for _, p := range g.Periods {
		periods = append(periods, periodView(p))
	}
	return map[string]any{"cadence": g.Cadence, "first": ISO(g.First), "last": ISO(g.Last), "label": g.Label,
		"vs": g.VS, "liable_nights": g.LiableNights, "exempt_nights": g.ExemptNights, "total_czk": g.TotalCZK,
		"periods": periods}
}

func filingID(f *FilingRow) any {
	if f == nil {
		return nil
	}
	return f.ID
}

// --- the replay -------------------------------------------------------------------

func runCases(t *testing.T, g *golden, b backend) {
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			ap, err := b.apartment(c.ApartmentID)
			if err != nil {
				t.Fatal(err)
			}
			month, today := day(t, c.Month), day(t, c.Today)
			o := Opts{LiveOnly: c.LiveOnly, Rate: c.Rate, ScheduleToday: scheduleToday}
			if c.Cadence != nil {
				o.Cadence = *c.Cadence
			}
			period, err := b.propertyPeriod(ap, month, o)
			if err != nil {
				t.Fatal(err)
			}
			same(t, "period", periodView(period), c.Out["period"])
			if !c.LiveOnly {
				return
			}
			checked, err := b.check(ap, month, today, o)
			if err != nil {
				t.Fatal(err)
			}
			grp := checked.Group
			same(t, "group", groupView(grp), c.Out["group"])
			same(t, "issues", checked.Issues, c.Out["issues"])
			same(t, "key", checked.Key, c.Out["key"])
			n, err := b.unsigned(ap.ID, grp.First, grp.Last, nil)
			if err != nil {
				t.Fatal(err)
			}
			same(t, "unsigned_query", n, c.Out["unsigned_query"])
			if n, err = b.unsigned(ap.ID, grp.First, grp.Last, checked.Period); err != nil {
				t.Fatal(err)
			}
			same(t, "unsigned_shortcut", n, c.Out["unsigned_shortcut"])
			same(t, "payment", PaymentDetails(grp), c.Out["payment"])
			rows, csv := []RegisterRow{}, ""
			if checked.Period != nil {
				if rows, err = b.register(checked.Period); err != nil {
					t.Fatal(err)
				}
				csv = base64.StdEncoding.EncodeToString(RegisterCSV(rows))
			}
			same(t, "register_rows", rows, c.Out["register_rows"])
			same(t, "register_csv_b64", csv, c.Out["register_csv_b64"])
			h, err := b.hlaseni(grp, today)
			if err != nil && ap.LegalEntityID != 0 {
				t.Fatal(err)
			}
			if h == nil {
				same(t, "hlaseni", nil, c.Out["hlaseni"])
			} else {
				same(t, "hlaseni", h, c.Out["hlaseni"])
			}
		})
	}
}

func runApartmentChecks(t *testing.T, g *golden, b backend) {
	for _, want := range g.ApartmentChecks {
		id := iv(want, "apartment_id")
		ap, err := b.apartment(id)
		if err != nil {
			t.Fatal(err)
		}
		e, err := b.entity(ap.LegalEntityID, false)
		if err != nil {
			t.Fatal(err)
		}
		account, payee := PayoutAccount(e)
		got := map[string]any{"apartment_id": id, "is_active": IsActive(ap), "cadence_of": CadenceOf(ap),
			"vs_of": VSOf(ap), "usable_rail_keys": UsableRailKeys(ap, e), "payout_account": []string{account, payee},
			"no_pay_way_on": NoPayWay(ap, e, true), "no_pay_way_off": NoPayWay(ap, e, false)}
		same(t, fmt.Sprintf("apartment_checks %d", id), got, want)
	}
}

func list(t *testing.T, h map[string]any, key string) [][]any {
	t.Helper()
	raw, ok := h[key].([]any)
	if !ok {
		t.Fatalf("helpers.%s missing", key)
	}
	out := make([][]any, 0, len(raw))
	for _, r := range raw {
		if row, ok := r.([]any); ok {
			out = append(out, row)
		} else {
			out = append(out, []any{r})
		}
	}
	return out
}

func str(v any) string {
	s, _ := v.(string)
	return s
}

func num(v any) int {
	f, _ := v.(float64)
	return int(f)
}

// runDBHelpers replays the helpers that read rows: adjustments, filings, schedules.
func runDBHelpers(t *testing.T, g *golden, b backend) {
	h := g.Helpers
	for _, r := range list(t, h, "net_bed_days") {
		n, err := b.netBedDays(int64(num(r[0])), str(r[1]))
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("net_bed_days ", r[:2]), n, r[2])
	}
	for _, raw := range h["filing_reads"].([]any) {
		r := raw.(map[string]any)
		apt := iv(r, "apartment_id")
		var f *FilingRow
		var err error
		switch call := str(r["call"]); call {
		case "latest":
			f, err = b.latest(apt, str(r["key"]))
		case "covering":
			f, err = b.covering(apt, day(t, str(r["key"])))
		default:
			f, err = b.foreignOverlap(apt, strings.TrimPrefix(call, "foreign_overlap:"), day(t, str(r["key"])))
		}
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("filing_reads ", r), filingID(f), r["id"])
	}
	for _, raw := range h["correction_rate"].([]any) {
		r := raw.(map[string]any)
		f, err := b.filingByID(iv(r, "filing_id"))
		if err != nil {
			t.Fatal(err)
		}
		ap, err := b.apartment(f.ApartmentID)
		if err != nil {
			t.Fatal(err)
		}
		schedule, err := b.schedule(ap)
		if err != nil {
			t.Fatal(err)
		}
		rate, err := CorrectionRateFor(schedule, f)
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("correction_rate ", r["filing_id"]), rate, r["rate"])
	}
	for _, raw := range h["schedule_uniform"].([]any) {
		r := raw.(map[string]any)
		ap, err := b.apartment(iv(r, "apartment_id"))
		if err != nil {
			t.Fatal(err)
		}
		schedule, err := b.schedule(ap)
		if err != nil {
			t.Fatal(err)
		}
		first, last := day(t, str(r["first"])), day(t, str(r["last"]))
		got := map[string]any{"apartment_id": ap.ID, "first": r["first"], "last": r["last"],
			"uniform": IsUniform(schedule, first, last), "rate_last": RateOn(schedule, last)}
		same(t, fmt.Sprint("schedule_uniform ", r), got, r)
	}
}

func TestGoldenPure(t *testing.T) {
	g := loadGolden(t)
	b := memBackend{seed: g.Seed}
	runCases(t, g, b)
	runApartmentChecks(t, g, b)
	runDBHelpers(t, g, b)
}

func TestGoldenHelpers(t *testing.T) {
	g := loadGolden(t)
	h := g.Helpers
	for _, r := range list(t, h, "shift_month") {
		same(t, fmt.Sprint("shift_month ", r), ISO(ShiftMonth(day(t, str(r[0])), num(r[1]))), r[2])
	}
	for _, r := range list(t, h, "previous_month") {
		same(t, fmt.Sprint("previous_month ", r), ISO(PreviousMonth(day(t, str(r[0])))), r[1])
	}
	for _, r := range list(t, h, "period_bounds") {
		a, b := PeriodBounds(str(r[0]), day(t, str(r[1])))
		same(t, fmt.Sprint("period_bounds ", r), []string{ISO(a), ISO(b)}, r[2])
	}
	for _, r := range list(t, h, "month_key") {
		same(t, fmt.Sprint("month_key ", r), MonthKey(day(t, str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "period_label_cs") {
		same(t, fmt.Sprint("period_label_cs ", r), PeriodLabelCS(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "period_complete") {
		got := PeriodComplete(str(r[0]), day(t, str(r[1])), day(t, str(r[2])))
		same(t, fmt.Sprint("period_complete ", r), got, r[3])
	}
	for _, r := range list(t, h, "parse_month") {
		same(t, fmt.Sprintf("parse_month %q", r[0]), isoOrNil(ParseMonth(str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "parse_czk_int") {
		n, ok := ParseCZKInt(str(r[0]))
		var got any
		if ok {
			got = n
		}
		same(t, fmt.Sprintf("parse_czk_int %q", r[0]), got, r[1])
	}
	for _, r := range list(t, h, "clamp_rate") {
		same(t, fmt.Sprintf("clamp_rate %q", r[0]), ClampRate(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "format_czk") {
		same(t, fmt.Sprint("format_czk ", r[0]), FormatCZK(num(r[0])), r[1])
	}
	for _, r := range list(t, h, "counted_days_in") {
		got := CountedDaysIn(day(t, str(r[0])), day(t, str(r[1])), day(t, str(r[2])), day(t, str(r[3])))
		same(t, fmt.Sprint("counted_days_in ", r), got, r[4])
	}
	for _, r := range list(t, h, "obec_key") {
		same(t, fmt.Sprintf("obec_key %q", r[0]), ObecKey(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "fold_text") {
		same(t, fmt.Sprintf("fold_text %q", r[0]), FoldText(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "conservative_birth") {
		same(t, fmt.Sprintf("conservative_birth %q", r[0]), isoOrNil(ConservativeBirth(str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "default_doc_type") {
		same(t, fmt.Sprintf("default_doc_type %q", r[0]), DefaultDocType(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "period_key") {
		same(t, fmt.Sprint("period_key ", r), PeriodKey(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "overlap_keys") {
		same(t, fmt.Sprint("overlap_keys ", r), OverlapKeys(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "period_anchor") {
		var got any = "error"
		if a, err := PeriodAnchor(str(r[0])); err == nil {
			got = ISO(a)
		}
		same(t, fmt.Sprint("period_anchor ", r[0]), got, r[1])
	}
	for _, r := range list(t, h, "spayd") {
		same(t, fmt.Sprint("spayd ", r[:4]), SPAYD(str(r[0]), num(r[1]), str(r[2]), str(r[3])), r[4])
	}
}

// TestPackageConstants pins the exported constants against stay_fee.py.
func TestPackageConstants(t *testing.T) {
	same(t, "decisions", Decisions, []any{"exempt", "charge"})
	same(t, "exempt_categories", ExemptCategories, []any{"disability", "diplomat", "local_rule", "other_statutory"})
	same(t, "scope_rules", ScopeRules, []any{"calendar_days", "nights"})
	if ReasonMax != 120 || MaxRateCZK != 50 || ThresholdNights != 60 {
		t.Errorf("constants: %d %d %d", ReasonMax, MaxRateCZK, ThresholdNights)
	}
}

// --- PostgreSQL --------------------------------------------------------------------

// testPool is a copy of ical's testPool: a fresh database with the PostgreSQL
// migrations applied. It skips without UBYHOST_TEST_DATABASE_URL.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_stayfee_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	_, err = admin.Exec(ctx, "CREATE DATABASE "+name)
	_ = admin.Close(ctx)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatalf("no migrations found: %v", err)
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

// insert writes one seed row; renames maps a seed key to its column ("" drops
// it) and extra adds columns. Encrypted columns get the plain text, which the
// plain Decrypter returns as is (the golden script encrypts them in SQLite).
func insert(t *testing.T, pool *pgxpool.Pool, table string, row map[string]any, renames map[string]string,
	extra map[string]any) {
	t.Helper()
	cols, args, marks := []string{}, []any{}, []string{}
	add := func(col string, v any) {
		if f, ok := v.(float64); ok {
			v = int64(f)
		}
		cols = append(cols, col)
		args = append(args, v)
		marks = append(marks, "$"+strconv.Itoa(len(args)))
	}
	keys := make([]string, 0, len(row))
	for k := range row {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		col := k
		if r, ok := renames[k]; ok {
			col = r
		}
		if col != "" {
			add(col, row[k])
		}
	}
	for k, v := range extra {
		add(k, v)
	}
	sql := "INSERT INTO " + table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", table, err)
	}
}

func TestGoldenLoader(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	stamp := "2026-09-01T00:00:00+00:00"
	for _, r := range g.Seed["legal_entities"] {
		insert(t, pool, "legal_entity", r, map[string]string{"signature_png": "signature_png_enc"},
			map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["apartments"] {
		insert(t, pool, "apartment", r, nil, map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["rates"] {
		insert(t, pool, "stay_fee_rate", r, nil, map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["reservations"] {
		insert(t, pool, "reservation", r, nil, map[string]any{"uid": fmt.Sprintf("uid-%d", iv(r, "id")),
			"created_at": stamp, "updated_at": stamp})
	}
	for _, r := range g.Seed["guests"] {
		insert(t, pool, "guest", r, nil, map[string]any{"created_at": stamp, "updated_at": stamp})
	}
	for _, r := range g.Seed["adjustments"] {
		insert(t, pool, "stay_fee_adjustment", r, map[string]string{"reason": "reason_enc"},
			map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["filings"] {
		insert(t, pool, "stay_fee_filing", r, map[string]string{"payload": "payload_enc"}, nil)
	}
	b := pgBackend{ctx: context.Background(), q: pool}
	runCases(t, g, b)
	runApartmentChecks(t, g, b)
	runDBHelpers(t, g, b)
}

func TestFernetDecrypter(t *testing.T) {
	keys, err := secure.LoadDataKeys(func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "golden-secret-key-not-for-real-use"
		}
		return ""
	})
	if err != nil {
		t.Skipf("data keys: %v", err)
	}
	token, err := keys.EncryptString("Host not recorded")
	if err != nil {
		t.Fatal(err)
	}
	dec := FernetDecrypter(keys)
	if got, err := dec(token); err != nil || got != "Host not recorded" {
		t.Errorf("decrypt: %q %v", got, err)
	}
	if _, err := dec("not-a-token"); err == nil {
		t.Error("a bad token must be an error")
	}
}
