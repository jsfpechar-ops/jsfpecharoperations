package billingweb

// POST /predplatne (order, ARES fill) and POST /predplatne/zmena (change),
// routes/billing.py plan_order, _ares_fill and plan_change (lines 84-146),
// brief 1557.

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// aresMap is _ARES_MAP: the order form field and the ARES key that fills it.
var aresMap = [][2]string{
	{"buyer_name", "name"}, {"buyer_street", "street"}, {"buyer_city", "city"}, {"buyer_zip", "zip"}, {"buyer_dic", "dic"},
}

// lastForm is `str(form.get(key) or "")`: the last posted value, not stripped.
func lastForm(r *http.Request, key string) string {
	vals := r.PostForm[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}

// valueError is whether err is what Python raises as ValueError in an order:
// a billing refusal or one of the invoice sentinels.
func valueError(err error) bool {
	if billing.Code(err) != "" {
		return true
	}
	for _, e := range []error{billingjob.ErrBuyerMissing, billingjob.ErrNoPlan, billingjob.ErrBelowMinimum,
		billingjob.ErrNotAnInvoice, billingjob.ErrAlreadyVoided, billingjob.ErrPaid, billingjob.ErrWorkspaceDeleted} {
		if errors.Is(err, e) {
			return true
		}
	}
	return false
}

// hostPlanOrder serves POST /predplatne (plan_order, lines 84-109).
func (d deps) hostPlanOrder(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	owner := c.h.Workspace.ID
	if !billingOn(d.getenv) {
		c.back("/settings", hostweb.Flash{}, hostweb.Flash{})
		return
	}
	form := map[string]string{}
	for k := range r.PostForm {
		form[k] = lastForm(r, k)
	}
	values, errs := billing.ReadForm(form)
	if form["do"] == "ares" {
		note, err := c.aresFill(owner, &values)
		if err != nil {
			fail(w, err)
			return
		}
		c.renderPlan(owner, planPage{Values: values, Note: note})
		return
	}
	if len(errs) > 0 {
		c.renderPlan(owner, planPage{Values: values, Errors: errs, Status: http.StatusBadRequest})
		return
	}
	inv := &billingjob.Invoicer{Pool: d.pool}
	result, err := billing.Place(c.ctx(), d.pool, inv, owner, values, c.today(), billing.HostActor)
	if err != nil {
		if !valueError(err) {
			fail(w, err)
			return
		}
		c.back("/predplatne", hostweb.Flash{}, c.flash("billing.order.error.state", nil))
		return
	}
	key := "billing.order.done_pending"
	switch {
	case result.Starts == "now":
		key = "billing.order.done_now"
	case result.Date != "":
		key = "billing.order.done_trial"
	}
	c.back("/predplatne", c.flash(key, map[string]any{"date": fmtDate(result.Date)}), hostweb.Flash{})
}

// aresFill is _ares_fill (lines 112-130): fill the blank buyer fields from
// ARES; the note says what happened.
func (c *call) aresFill(owner int64, v *billing.OrderValues) (string, error) {
	ctx := c.r.Context()
	key := strconv.FormatInt(owner, 10)
	blocked, err := session.RateBlocked(ctx, c.pool, aresRateScope, key, aresRateLimit, aresRateWindow, c.at)
	if err != nil {
		return "", err
	}
	if blocked {
		return c.flash("ares.rate_limited", nil).Text, nil
	}
	if !billing.ICOOK(v.BuyerICO) {
		return c.flash("ares.failure", nil).Text, nil
	}
	if err := session.RateRecord(ctx, c.pool, aresRateScope, key, c.at); err != nil {
		return "", err
	}
	data := c.ares.Lookup(v.BuyerICO, c.at)
	if data == nil {
		return c.flash("ares.failure", nil).Text, nil
	}
	found := map[string]string{"name": data.Name, "street": data.Street, "city": data.City, "zip": data.Zip, "dic": data.DIC}
	target := map[string]*string{"buyer_name": &v.BuyerName, "buyer_street": &v.BuyerStreet, "buyer_city": &v.BuyerCity,
		"buyer_zip": &v.BuyerZip, "buyer_dic": &v.BuyerDIC}
	for _, m := range aresMap {
		if pyStrip(*target[m[0]]) == "" && found[m[1]] != "" {
			*target[m[0]] = found[m[1]]
		}
	}
	return c.flash("billing.order.ares_done", nil).Text, nil
}

// changeValues is _CHANGE_VALUES: the one change each small form sends.
var changeValues = map[string][]string{
	"plan":             billing.Plans,
	"billing_interval": billing.Intervals,
	"addon_ttlock":     {"0", "1"},
	"addon_whitelabel": {"0"},
}

// hostPlanChange serves POST /predplatne/zmena (plan_change, lines 133-146).
func (d deps) hostPlanChange(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	owner := c.h.Workspace.ID
	state := func() { c.back("/predplatne", hostweb.Flash{}, c.flash("billing.order.error.state", nil)) }
	var acc *billing.BillingAccount
	if billingOn(d.getenv) {
		var err error
		if acc, err = billing.Account(r.Context(), d.pool, owner); err != nil {
			fail(w, err)
			return
		}
	}
	if acc == nil || acc.Plan == "" || (acc.Status != "active" && acc.Status != "overdue") {
		state()
		return
	}
	field, value := lastForm(r, "field"), lastForm(r, "value")
	if !inList(changeValues[field], value) {
		state()
		return
	}
	var typed any = value
	if len(field) > 6 && field[:6] == "addon_" {
		typed, _ = strconv.Atoi(value) // value is "0" or "1" here
	}
	confirm := lastForm(r, "confirm") == "1"
	inv := &billingjob.Invoicer{Pool: d.pool}
	// A ValueError here is not caught in Python: it is a 500, as any error is here.
	result, err := billing.Change(c.ctx(), d.pool, inv, owner, field, typed, confirm, c.today(), billing.HostActor)
	if err != nil {
		fail(w, err)
		return
	}
	if !confirm {
		values, err := FormValues(r.Context(), d.pool, owner, nil)
		if err != nil {
			fail(w, err)
			return
		}
		c.renderPlan(owner, planPage{Values: values, Preview: &Preview{
			When: result.When, Field: field, Value: value,
			Before: kcWhole(result.PeriodTotalBefore), After: kcWhole(result.PeriodTotalAfter),
			Supplementary: kcWhole(result.SupplementaryCZK), SupplementaryCZK: result.SupplementaryCZK,
		}})
		return
	}
	c.back("/predplatne", c.flash("billing.change.saved_"+result.When, nil), hostweb.Flash{})
}
