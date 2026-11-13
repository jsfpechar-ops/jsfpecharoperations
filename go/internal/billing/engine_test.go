package billing

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"reflect"
	"regexp"
	"sort"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// engine_golden.json is written by App/scripts/billing_engine_golden.py from
// the real Python. Every scenario seeds one account, apartments and invoices,
// runs one function and records its result or error code, the billing_account
// row afterwards, the audit rows and the Invoicer calls.

type goldenScenario struct {
	Name       string           `json:"name"`
	Owner      int64            `json:"owner"`
	Today      string           `json:"today"`
	Account    map[string]any   `json:"account"`
	Apartments []int            `json:"apartments"`
	Invoices   []map[string]any `json:"invoices"`
	Call       goldenCall       `json:"call"`
	Result     any              `json:"result"`
	Error      string           `json:"error"`
	AccountAft any              `json:"account_after"`
	Audit      []map[string]any `json:"audit"`
	Invoicer   [][]any          `json:"invoicer"`
	ActorCtx   *struct {
		UserID        int64  `json:"user_id"`
		Username      string `json:"username"`
		Impersonating bool   `json:"impersonating"`
	} `json:"actor_ctx"`
}

type goldenCall struct {
	Fn   string         `json:"fn"`
	Args map[string]any `json:"args"`
}

type goldenFile struct {
	Stamp     string           `json:"stamp"`
	Users     []map[string]any `json:"users"`
	Tables    map[string]any   `json:"tables"`
	Scenarios []goldenScenario `json:"scenarios"`
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/engine_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Scenarios) < 100 {
		t.Fatalf("golden file has %d scenarios", len(g.Scenarios))
	}
	return g
}

// roundTrip turns any Go value into the generic form json.Unmarshal gives.
func roundTrip(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

// fakeInvoicer records calls like the Python recorder and answers the same:
// IssueForPeriod 1000+n, IssueSupplementary 2000+n, Storno 3000+id.
type fakeInvoicer struct {
	calls         [][]any
	issued        int64
	supplementary int64
	failSend      bool
}

func (f *fakeInvoicer) IssueForPeriod(_ context.Context, owner int64, from, to string, today time.Time) (int64, error) {
	f.issued++
	f.calls = append(f.calls, []any{"issue_for_period", owner, from, to, today.Format("2006-01-02")})
	return 1000 + f.issued, nil
}

func (f *fakeInvoicer) IssueSupplementary(_ context.Context, owner int64, amount int64, description, from, to string, today time.Time) (int64, error) {
	f.supplementary++
	f.calls = append(f.calls, []any{"issue_supplementary", owner, amount, description, from, to, today.Format("2006-01-02")})
	return 2000 + f.supplementary, nil
}

func (f *fakeInvoicer) Storno(_ context.Context, id int64, reason string, today time.Time) (int64, error) {
	f.calls = append(f.calls, []any{"storno", id, reason, today.Format("2006-01-02")})
	return 3000 + id, nil
}

func (f *fakeInvoicer) Send(_ context.Context, id int64) error {
	f.calls = append(f.calls, []any{"send", id})
	if f.failSend {
		return errors.New("mail down")
	}
	return nil
}

func num(v any) int64 { return int64(v.(float64)) }

func parseDate(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

func toStringMap(t *testing.T, v any) map[string]string {
	t.Helper()
	out := map[string]string{}
	for k, x := range v.(map[string]any) {
		out[k] = x.(string)
	}
	return out
}

// acctMap is the golden form of an Account: NULL text collapses to "", flags
// are 0 or 1, updated_at is "seed" or "run".
func acctMap(a *BillingAccount, stamp string) any {
	if a == nil {
		return nil
	}
	updated := "run"
	if a.UpdatedAt == stamp {
		updated = "seed"
	}
	return map[string]any{
		"owner_user_id": a.OwnerUserID, "status": a.Status, "plan": a.Plan,
		"billing_interval": a.BillingInterval, "payment_method": a.PaymentMethod,
		"founder": flag(a.Founder), "addon_ttlock": flag(a.AddonTTLock),
		"addon_whitelabel": flag(a.AddonWhitelabel), "apartments_billed": a.ApartmentsBilled,
		"trial_started_at": a.TrialStartedAt, "trial_ends_at": a.TrialEndsAt,
		"period_start": a.PeriodStart, "period_end": a.PeriodEnd,
		"cancel_at_period_end": flag(a.CancelAtPeriodEnd), "pending_change_json": a.PendingChangeJSON,
		"carry_czk": a.CarryCZK, "buyer_name": a.BuyerName, "buyer_street": a.BuyerStreet,
		"buyer_city": a.BuyerCity, "buyer_zip": a.BuyerZip, "buyer_ico": a.BuyerICO,
		"buyer_dic": a.BuyerDIC, "buyer_email": a.BuyerEmail, "discount_percent": a.DiscountPercent,
		"discount_reason": a.DiscountReason, "updated_at": updated,
	}
}

// pureResult runs the scenarios that need no database.
func pureResult(t *testing.T, sc goldenScenario) (any, bool) {
	t.Helper()
	switch sc.Call.Fn {
	case "read_form":
		form := toStringMap(t, sc.Call.Args["form"])
		values, errs := ReadForm(form)
		return map[string]any{"values": roundTrip(t, values), "errors": roundTrip(t, errs)}, true
	case "period_end":
		start := parseDate(t, sc.Call.Args["start"].(string))
		return isoDay(PeriodEnd(start, sc.Call.Args["interval"].(string))), true
	}
	return nil, false
}

func TestEnginePureMatchesPython(t *testing.T) {
	g := loadGolden(t)
	seen := 0
	for _, sc := range g.Scenarios {
		got, ok := pureResult(t, sc)
		if !ok {
			continue
		}
		seen++
		if !reflect.DeepEqual(got, sc.Result) {
			t.Errorf("%s: got %v, Python %v", sc.Name, got, sc.Result)
		}
	}
	if seen < 20 {
		t.Fatalf("only %d pure scenarios", seen)
	}
}

func strList(v any) []string {
	out := []string{}
	for _, x := range v.([]any) {
		out = append(out, x.(string))
	}
	return out
}

func TestEngineTablesMatchPython(t *testing.T) {
	g := loadGolden(t)
	tb := g.Tables
	if !reflect.DeepEqual(strList(tb["statuses"]), Statuses) {
		t.Errorf("statuses differ")
	}
	if !reflect.DeepEqual(strList(tb["plans"]), Plans) || !reflect.DeepEqual(strList(tb["intervals"]), Intervals) {
		t.Errorf("plans or intervals differ")
	}
	if !reflect.DeepEqual(strList(tb["orderable"]), Orderable) || !reflect.DeepEqual(strList(tb["buyer_fields"]), BuyerFields) {
		t.Errorf("orderable or buyer fields differ")
	}
	if int(tb["supplementary_min_czk"].(float64)) != SupplementaryMinCZK {
		t.Errorf("supplementary minimum differs")
	}
	cols := map[string]string{}
	for k, v := range tb["change_columns"].(map[string]any) {
		cols[k] = v.(string)
	}
	if !reflect.DeepEqual(cols, ChangeColumns) {
		t.Errorf("change columns differ")
	}
	for from, tos := range tb["transitions"].(map[string]any) {
		got := append([]string{}, Transitions[from]...)
		sort.Strings(got)
		if !reflect.DeepEqual(got, strList(tos)) {
			t.Errorf("transitions from %s differ: %v", from, got)
		}
	}
	if len(Transitions) != len(tb["transitions"].(map[string]any)) {
		t.Errorf("transition count differs")
	}
}

func TestErrorCodes(t *testing.T) {
	all := []*Error{ErrUnknownStatus, ErrOneChange, ErrNoOrderedPlan, ErrWhitelabelUnavailable,
		ErrDiscountOutOfRange, ErrReasonMissing, ErrNoPlan, ErrNoAccount, ErrAlreadyOrdered,
		ErrBadDays, ErrUnknownPlan, ErrBadValue}
	seen := map[string]bool{}
	for _, e := range all {
		if seen[e.Error()] || e.Error() == "" {
			t.Errorf("code %q is empty or repeated", e.Error())
		}
		seen[e.Error()] = true
		wrapped := fmt.Errorf("%w: detail", e)
		if !errors.Is(wrapped, e) || Code(wrapped) != e.Error() {
			t.Errorf("%q does not survive wrapping", e.Error())
		}
	}
	if Code(errors.New("plain")) != "" || Code(nil) != "" {
		t.Error("a non-billing error has a code")
	}
	if errors.Is(ErrNoPlan, ErrNoAccount) {
		t.Error("distinct sentinels are equal")
	}
}

func TestICOOK(t *testing.T) {
	for ico, want := range map[string]bool{
		"27082440": true, "25596641": true, "12345678": false, "1234567": false,
		"2708244x": false, " 27082440 ": true, "": false,
	} {
		if got := ICOOK(ico); got != want {
			t.Errorf("ICOOK(%q) = %v, want %v", ico, got, want)
		}
	}
}

var stampRE = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$`)

func dbValue(v any) any {
	switch x := v.(type) {
	case float64:
		return int64(x)
	}
	return v
}

func insertRow(t *testing.T, pool *pgxpool.Pool, table string, row map[string]any) {
	t.Helper()
	cols := make([]string, 0, len(row))
	for c := range row {
		cols = append(cols, c)
	}
	sort.Strings(cols)
	sql := "INSERT INTO " + table + " ("
	marks := ""
	args := make([]any, 0, len(cols))
	for i, c := range cols {
		if i > 0 {
			sql += ", "
			marks += ", "
		}
		sql += c
		marks += fmt.Sprintf("$%d", i+1)
		args = append(args, dbValue(row[c]))
	}
	if _, err := pool.Exec(context.Background(), sql+") VALUES ("+marks+")", args...); err != nil {
		t.Fatalf("insert %s: %v", table, err)
	}
}

func seedScenario(t *testing.T, pool *pgxpool.Pool, g goldenFile, sc goldenScenario) {
	t.Helper()
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `TRUNCATE audit, platform_invoice, billing_account, apartment RESTART IDENTITY CASCADE`); err != nil {
		t.Fatal(err)
	}
	if sc.Account != nil {
		row := map[string]any{"owner_user_id": sc.Owner, "updated_at": g.Stamp}
		for k, v := range sc.Account {
			row[k] = v
		}
		insertRow(t, pool, "billing_account", row)
	}
	id := 0
	for i, flagValue := range []int{1, 0} {
		for n := 0; n < sc.Apartments[i]; n++ {
			id++
			insertRow(t, pool, "apartment", map[string]any{
				"id": float64(id), "owner_user_id": sc.Owner, "internal_name": fmt.Sprintf("flat %d", id),
				"active": float64(flagValue), "created_at": g.Stamp,
			})
		}
	}
	if sc.Apartments[0] > 0 {
		other := float64(1)
		if sc.Owner == 1 {
			other = 2
		}
		insertRow(t, pool, "apartment", map[string]any{
			"id": float64(900), "owner_user_id": other, "internal_name": "foreign",
			"active": float64(1), "created_at": g.Stamp,
		})
	}
	for _, inv := range sc.Invoices {
		insertRow(t, pool, "platform_invoice", inv)
	}
}

// rawAccount reads the row with NULLs kept, in the golden "account_after" form.
func rawAccount(t *testing.T, pool *pgxpool.Pool, owner int64, stamp string) any {
	t.Helper()
	cols := []string{"status", "plan", "billing_interval", "payment_method", "founder", "addon_ttlock",
		"addon_whitelabel", "apartments_billed", "trial_started_at", "trial_ends_at", "period_start",
		"period_end", "cancel_at_period_end", "pending_change_json", "carry_czk", "buyer_name",
		"buyer_street", "buyer_city", "buyer_zip", "buyer_ico", "buyer_dic", "buyer_email",
		"discount_percent", "discount_reason"}
	ints := map[string]bool{"founder": true, "addon_ttlock": true, "addon_whitelabel": true,
		"apartments_billed": true, "cancel_at_period_end": true, "carry_czk": true, "discount_percent": true}
	list := ""
	for _, c := range cols {
		list += c + ", "
	}
	rows, err := pool.Query(context.Background(), "SELECT owner_user_id, "+list+"updated_at FROM billing_account WHERE owner_user_id = $1", owner)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	if !rows.Next() {
		return nil
	}
	vals, err := rows.Values()
	if err != nil {
		t.Fatal(err)
	}
	out := map[string]any{"owner_user_id": vals[0]}
	for i, c := range cols {
		out[c] = vals[i+1]
		if ints[c] && vals[i+1] == nil {
			out[c] = int64(0)
		}
	}
	updated := vals[len(cols)+1].(string)
	if updated == stamp {
		out["updated_at"] = "seed"
	} else {
		if !stampRE.MatchString(updated) {
			t.Errorf("updated_at %q is not db.utcnow form", updated)
		}
		out["updated_at"] = "run"
	}
	return roundTrip(t, out)
}

func auditRows(t *testing.T, pool *pgxpool.Pool) []map[string]any {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		"SELECT at, action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var at, action, detail, actor string
		var owner int64
		var actorID, impID *int64
		if err := rows.Scan(&at, &action, &detail, &actor, &owner, &actorID, &impID); err != nil {
			t.Fatal(err)
		}
		if !stampRE.MatchString(at) {
			t.Errorf("audit row %s: at %q is not db.utcnow form", action, at)
		}
		out = append(out, map[string]any{"action": action, "detail": detail, "actor": actor,
			"owner_user_id": owner, "actor_user_id": actorID, "impersonator_user_id": impID})
	}
	return out
}

// runDB runs one database scenario through the Go engine. The returned value is
// in the golden form; a billing error comes back as its code.
func runDB(t *testing.T, pool *pgxpool.Pool, inv *fakeInvoicer, g goldenFile, sc goldenScenario) (any, string) {
	t.Helper()
	ctx := context.Background()
	if c := sc.ActorCtx; c != nil {
		var imp *int64
		if c.Impersonating {
			imp = &c.UserID
		}
		ctx = WithAuditActor(ctx, c.UserID, c.Username, imp)
	}
	a := sc.Call.Args
	owner := sc.Owner
	today := parseDate(t, sc.Today)
	fail := func(err error) (any, string) {
		if c := Code(err); c != "" {
			return nil, c
		}
		t.Fatalf("%s: %v", sc.Name, err)
		return nil, ""
	}
	switch sc.Call.Fn {
	case "account":
		acc, err := Account(ctx, pool, owner)
		if err != nil {
			return fail(err)
		}
		return roundTrip(t, acctMap(acc, g.Stamp)), ""
	case "ensure_account":
		acc, err := EnsureAccount(ctx, pool, owner)
		if err != nil {
			return fail(err)
		}
		return roundTrip(t, acctMap(acc, g.Stamp)), ""
	case "apartment_count":
		n, err := ApartmentCount(ctx, pool, owner)
		if err != nil {
			return fail(err)
		}
		return roundTrip(t, n), ""
	case "set_status":
		ok, err := SetStatus(ctx, pool, owner, a["new"].(string), a["actor"].(string))
		if err != nil {
			return fail(err)
		}
		return ok, ""
	case "operator_pause":
		ok, err := OperatorPause(ctx, pool, owner, a["actor"].(string))
		if err != nil {
			return fail(err)
		}
		return ok, ""
	case "apply_change", "change":
		var field string
		var value any
		confirm := a["confirm"].(bool)
		if sc.Call.Fn == "apply_change" {
			change := a["change"].(map[string]any)
			// Python's "exactly one key" rule: any other size has no field.
			for k, v := range change {
				if len(change) == 1 {
					field = k
					switch x := v.(type) {
					case string:
						value = x
					case float64:
						value = int(x)
					}
				}
			}
		} else {
			field, value = a["field"].(string), nil
			switch v := a["value"].(type) {
			case string:
				value = v
			case float64:
				value = int(v)
			}
		}
		var res ChangeResult
		var err error
		if sc.Call.Fn == "apply_change" {
			res, err = ApplyChange(ctx, pool, owner, field, value, today, confirm, a["actor"].(string))
		} else {
			res, err = Change(ctx, pool, inv, owner, field, value, confirm, today, HostActor)
		}
		if err != nil {
			return fail(err)
		}
		m := roundTrip(t, res).(map[string]any)
		if sc.Call.Fn == "apply_change" {
			delete(m, "invoice_id")
		} else if res.InvoiceID == 0 {
			m["invoice_id"] = nil
		}
		return m, ""
	case "apply_discount":
		res, err := ApplyDiscount(ctx, pool, inv, owner, int(a["percent"].(float64)), a["reason"].(string), a["actor"].(string), today)
		if err != nil {
			return fail(err)
		}
		return roundTrip(t, res), ""
	case "place", "place_for_operator":
		raw, _ := json.Marshal(a["values"])
		var values OrderValues
		if err := json.Unmarshal(raw, &values); err != nil {
			t.Fatal(err)
		}
		var res PlaceResult
		var err error
		if sc.Call.Fn == "place" {
			res, err = Place(ctx, pool, inv, owner, values, today, HostActor)
		} else {
			res, err = PlaceForOperator(ctx, pool, inv, owner, values, today, a["actor"].(string))
		}
		if err != nil {
			return fail(err)
		}
		m := roundTrip(t, res).(map[string]any)
		if res.InvoiceID == 0 {
			m["invoice_id"] = nil
		}
		return m, ""
	case "cancel":
		ok, err := Cancel(ctx, pool, owner, HostActor)
		if err != nil {
			return fail(err)
		}
		return ok, ""
	case "resume":
		ok, err := Resume(ctx, pool, owner, HostActor)
		if err != nil {
			return fail(err)
		}
		return ok, ""
	case "extend_trial":
		s, err := ExtendTrial(ctx, pool, owner, int(a["days"].(float64)), a["actor"].(string), today)
		if err != nil {
			return fail(err)
		}
		return s, ""
	}
	t.Fatalf("%s: unknown fn %s", sc.Name, sc.Call.Fn)
	return nil, ""
}

func TestEngineMatchesPython(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	for _, u := range g.Users {
		if _, err := pool.Exec(context.Background(),
			`INSERT INTO user_account (id, username, password_hash, created_at) VALUES ($1, $2, 'x', $3)`,
			dbValue(u["id"]), u["username"], g.Stamp); err != nil {
			t.Fatal(err)
		}
	}
	ran := 0
	for _, sc := range g.Scenarios {
		if _, pure := pureResult(t, sc); pure {
			continue
		}
		sc := sc
		t.Run(sc.Name, func(t *testing.T) {
			seedScenario(t, pool, g, sc)
			inv := &fakeInvoicer{}
			got, code := runDB(t, pool, inv, g, sc)
			if code != sc.Error {
				t.Fatalf("error code %q, Python %q", code, sc.Error)
			}
			if sc.Error == "" && !reflect.DeepEqual(got, sc.Result) {
				t.Errorf("result\n got  %v\n want %v", got, sc.Result)
			}
			if after := rawAccount(t, pool, sc.Owner, g.Stamp); !reflect.DeepEqual(after, sc.AccountAft) {
				t.Errorf("account after\n got  %v\n want %v", after, sc.AccountAft)
			}
			audit := auditRows(t, pool)
			if want := roundTrip(t, sc.Audit); !reflect.DeepEqual(roundTrip(t, audit), want) {
				t.Errorf("audit\n got  %v\n want %v", audit, want)
			}
			calls := roundTrip(t, inv.calls)
			if inv.calls == nil {
				calls = roundTrip(t, [][]any{})
			}
			if want := roundTrip(t, sc.Invoicer); !reflect.DeepEqual(calls, want) {
				t.Errorf("invoicer calls\n got  %v\n want %v", calls, want)
			}
		})
		ran++
	}
	if ran < 100 {
		t.Fatalf("only %d database scenarios", ran)
	}
}

// A failing Send leaves the placed order in the database and reports the error.
func TestPlaceSendFailureKeepsOrder(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at)
		VALUES (1, 'a', 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO billing_account (owner_user_id, status, updated_at)
		VALUES (1, 'paused', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	values, errs := ReadForm(map[string]string{
		"plan": "standard", "billing_interval": "month", "buyer_name": "A", "buyer_street": "B",
		"buyer_city": "C", "buyer_zip": "11000", "buyer_email": "a@example.test",
	})
	if len(errs) != 0 {
		t.Fatal(errs)
	}
	inv := &fakeInvoicer{failSend: true}
	_, err := Place(ctx, pool, inv, 1, values, time.Date(2026, 11, 13, 0, 0, 0, 0, time.UTC), HostActor)
	if err == nil || err.Error() != "mail down" {
		t.Fatalf("err = %v", err)
	}
	acc, err := Account(ctx, pool, 1)
	if err != nil || acc.Status != "active" || acc.Plan != "standard" || acc.PeriodEnd != "2026-12-12" {
		t.Fatalf("account %+v err %v", acc, err)
	}
}

// ubyport.NormaliseEmail refuses a quoted display name ("Q" <q@x.cz>) where
// Python's parseaddr accepts it. The order form then shows its email error:
// stricter, never looser. This pins that known gap.
func TestReadFormRefusesQuotedEmailName(t *testing.T) {
	_, errs := ReadForm(map[string]string{
		"plan": "standard", "billing_interval": "year", "buyer_name": "A", "buyer_street": "B",
		"buyer_city": "C", "buyer_zip": "11000", "buyer_email": "\"Q\" <q@x.cz>",
	})
	if errs["buyer_email"] != "billing.order.error.email" {
		t.Fatalf("errors %v", errs)
	}
}

// Without WithAuditActor the audit row keeps the actor as given and NULL ids;
// with it, "host" becomes the username and both ids are filled (db.audit).
func TestAuditActorContext(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at) VALUES
		(1, 'owner', 'x', '2026-01-01T00:00:00+00:00'), (7, 'ann', 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	imp := int64(7)
	if err := audit(ctx, pool, "host", "plain", "", 1); err != nil {
		t.Fatal(err)
	}
	if err := audit(WithAuditActor(ctx, 7, "ann", nil), pool, "host", "named", "", 1); err != nil {
		t.Fatal(err)
	}
	if err := audit(WithAuditActor(ctx, 7, "ann", &imp), pool, "system", "inside", "", 1); err != nil {
		t.Fatal(err)
	}
	want := []string{"host|<nil>|<nil>", "ann|7|<nil>", "system|7|7"}
	rows := auditRows(t, pool)
	if len(rows) != len(want) {
		t.Fatalf("rows %v", rows)
	}
	for i, r := range rows {
		deref := func(p *int64) any {
			if p == nil {
				return nil
			}
			return *p
		}
		got := fmt.Sprintf("%v|%v|%v", r["actor"], deref(r["actor_user_id"].(*int64)), deref(r["impersonator_user_id"].(*int64)))
		if got != want[i] {
			t.Errorf("row %d: %s, want %s", i, got, want[i])
		}
	}
}
