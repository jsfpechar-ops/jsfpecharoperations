package stayfees

// Brief 1584: POST /stay-fees/{apartment_id}/adjustment, the port of
// stay_fee_adjustment_add and _adjustment_bed_days in
// App/app/routes/stay_fees.py (1008-1100). The write is
// stayfee.AddAdjustment; the undo route is UndoHandler in handlers.go.

import (
	_ "embed"
	"errors"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

//go:embed adjust_i18n.json
var adjustCatalogJSON []byte

// adjustCatalog holds the three flash texts i18n.json does not have. They are
// copied from App/app/host_i18n.py (cs, en, vi).
var adjustCatalog = hostweb.Load(adjustCatalogJSON)

func (c *call) adjustFlash(key string) hostweb.Flash {
	return hostweb.Flash{Text: adjustCatalog.T(c.lang, key, nil), Key: key}
}

// pyInt is int(text) for an already stripped string: an optional sign, ASCII
// digits, single underscores between digits. A number too large for int64 is
// returned as a huge value of the right sign, which every range check refuses.
func pyInt(text string) (int64, bool) {
	s := text
	neg := false
	if s != "" && (s[0] == '+' || s[0] == '-') {
		neg = s[0] == '-'
		s = s[1:]
	}
	if s == "" || s[0] == '_' || s[len(s)-1] == '_' || strings.Contains(s, "__") {
		return 0, false
	}
	s = strings.ReplaceAll(s, "_", "")
	if !isDigits(s) {
		return 0, false
	}
	n, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		n = math.MaxInt32
	}
	if neg {
		n = -n
	}
	return n, true
}

// formIntOr0 is int(_form_str(form, key) or "0").
func (c *call) formIntOr0(key string) (int64, bool) {
	v := c.formStr(key)
	if v == "" {
		return 0, true
	}
	return pyInt(v)
}

var errRange = errors.New("range")

// adjustmentBedDays is _adjustment_bed_days: the bed-days of the form, or an
// error where Python raises ValueError.
func (c *call) adjustmentBedDays() (int, error) {
	if c.formStr("mode") == "people" {
		people, ok1 := c.formIntOr0("people")
		nights, ok2 := c.formIntOr0("nights")
		if !ok1 || !ok2 || people < 1 || people > 99 || nights < 1 || nights > 366 {
			return 0, errRange
		}
		return int(people * nights), nil
	}
	days, ok := c.formIntOr0("bed_days")
	if !ok || days < 1 || days > 9999 {
		return 0, errRange
	}
	return int(days), nil
}

// AdjustmentAddHandler serves POST /stay-fees/{apartment_id}/adjustment
// (stay_fee_adjustment_add).
func AdjustmentAddHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.pathApartment(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		// An archived property with a rate passes here, as in Python.
		if apt == nil || !isActive(apt.Rate) {
			c.noSuchApartment()
			return
		}
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			c.fail(err)
			return
		}
		dec := stayfee.FernetDecrypter(keys)
		full, err := stayfee.LoadApartment(ctx, pool, apt.ID)
		if err != nil {
			c.fail(err)
			return
		}
		u := c.at.UTC()
		scheduleToday := stayfee.Day(u.Year(), u.Month(), u.Day())

		month := c.month()
		back := monthPath(apt.ID, month)
		var period *stayfee.Period
		var key string
		if c.formStr("correct") == "1" {
			// A correction keeps the sealed period's cadence and key.
			sealed, err := stayfee.Covering(ctx, pool, apt.ID, month)
			if err != nil {
				c.fail(err)
				return
			}
			if sealed == nil {
				c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.report_blocked", nil))
				return
			}
			back += "&correct=1"
			anchor, err := stayfee.PeriodAnchor(sealed.PeriodKey)
			if err != nil {
				c.fail(err)
				return
			}
			rate, err := stayfee.CorrectionRate(ctx, pool, full, sealed, scheduleToday)
			if err != nil {
				c.fail(err)
				return
			}
			period, err = stayfee.PropertyPeriod(ctx, pool, dec, full, anchor,
				stayfee.Opts{LiveOnly: true, Cadence: sealed.Cadence, Rate: rate, ScheduleToday: scheduleToday})
			if err != nil {
				c.fail(err)
				return
			}
			key = stayfee.PeriodKey(sealed.Cadence, anchor)
		} else {
			period, err = stayfee.PropertyPeriod(ctx, pool, dec, full, month, stayfee.Opts{ScheduleToday: scheduleToday})
			if err != nil {
				c.fail(err)
				return
			}
			if period != nil && period.Frozen {
				c.back(back, hostweb.Flash{}, c.adjustFlash("flash.stay_fees.adjust_frozen"))
				return
			}
			key = stayfee.PeriodKey(stayfee.CadenceOf(full), month)
		}

		direction := c.formStr("direction")
		mode := c.formStr("mode")
		reason := c.formStr("reason")
		if (direction != "add" && direction != "remove") || (mode != "people" && mode != "bed_days") || len([]rune(reason)) < 3 {
			c.back(back, hostweb.Flash{}, c.adjustFlash("flash.stay_fees.adjust_invalid"))
			return
		}
		days, err := c.adjustmentBedDays()
		if err != nil {
			c.back(back, hostweb.Flash{}, c.adjustFlash("flash.stay_fees.adjust_invalid"))
			return
		}
		current, err := stayfee.NetBedDays(ctx, pool, dec, apt.ID, key)
		if err != nil {
			c.fail(err)
			return
		}
		guestNights := 0
		if period != nil {
			guestNights = period.GuestLiableNights
		}
		delta := days
		if direction == "remove" {
			delta = -days
		}
		if guestNights+current+delta < 0 {
			c.back(back, hostweb.Flash{}, c.adjustFlash("flash.stay_fees.adjust_negative"))
			return
		}
		in := stayfee.AdjustmentInput{
			ApartmentID: apt.ID, PeriodKey: key, Direction: direction, Mode: mode,
			BedDays: days, Reason: truncRunes(reason, 200), CreatedBy: c.owner,
		}
		if mode == "people" {
			people, _ := c.formIntOr0("people")
			nights, _ := c.formIntOr0("nights")
			in.PeopleCount, in.Nights = int(people), int(nights)
		}
		if _, err := stayfee.AddAdjustment(ctx, pool, stayfee.FernetEncrypter(keys), in, c.at); err != nil {
			c.fail(err)
			return
		}
		detail := "apartment_id=" + strconv.FormatInt(apt.ID, 10) + " period=" + key + " direction=" + direction +
			" days=" + strconv.Itoa(days)
		if err := c.audit("stay_fee_adjustment", detail); err != nil {
			c.fail(err)
			return
		}
		c.back(back, c.flash("flash.stay_fees.saved", nil), hostweb.Flash{})
	}
}

// AdjustRoutes is the one route of brief 1584.
func AdjustRoutes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return []Route{
		{"POST /stay-fees/{apartment_id}/adjustment", AdjustmentAddHandler(pool, getenv, now)},
	}
}
