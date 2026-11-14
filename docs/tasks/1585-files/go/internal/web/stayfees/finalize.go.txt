package stayfees

// Brief 1585: POST /stay-fees/{apartment_id}/finalize (stay_fee_finalize in
// App/app/routes/stay_fees.py). Seals one period through stayfee.Save,
// including a correction (ReplacingID) of a sealed period.
//
// Answer without a renderer: the handler flashes flash.stay_fees.report_blocked
// (the flash Python shows when save() refuses) and redirects, with nothing
// sealed and no audit row. Production sets the renderer in
// go/cmd/ubyhost-web/register_job_stay_fee_mail.go (brief 1580).

import (
	_ "embed"
	"errors"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

//go:embed finalize_i18n.json
var finalizeCatalogJSON []byte

// finalizeCatalog holds the three flashes only this route uses; the others
// (report_blocked, no_such_apartment) come from catalog.
var finalizeCatalog = hostweb.Load(finalizeCatalogJSON)

func (c *call) finalizeFlash(key string) hostweb.Flash {
	return hostweb.Flash{Text: finalizeCatalog.T(c.lang, key, nil), Key: key}
}

// finalizeIntegrity is db.integrity_errors(): any SQLSTATE of class 23.
func finalizeIntegrity(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && len(pgErr.Code) >= 2 && pgErr.Code[:2] == "23"
}

// FinalizeHandler serves POST /stay-fees/{apartment_id}/finalize. renderer
// draws the hlášení PDF; nil refuses every request that would seal.
func FinalizeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, renderer stayfee.PDFRenderer) http.HandlerFunc {
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
		today := pragueDay(c.at)
		row, err := c.pathApartment(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if row == nil || !isActive(row.Rate) {
			c.noSuchApartment()
			return
		}
		ap, err := stayfee.LoadApartment(ctx, pool, row.ID)
		if err != nil {
			c.fail(err)
			return
		}
		month := c.month()
		aptText := strconv.FormatInt(row.ID, 10)
		back := monthPath(row.ID, month)
		if p := feeReturnPath(c.formStr("return_to"), row.ID); p != "" {
			back = p
		}
		blocked := func() { c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.report_blocked", nil)) }
		correcting := c.formStr("correct") == "1"
		sealed, err := stayfee.Covering(ctx, pool, row.ID, month)
		if err != nil {
			c.fail(err)
			return
		}
		u := c.at.UTC()
		scheduleToday := stayfee.Day(u.Year(), u.Month(), u.Day())
		cadence := stayfee.CadenceOf(ap)
		calcMonth := month
		var rate *int
		if correcting {
			if sealed == nil {
				blocked()
				return
			}
			cadence = sealed.Cadence
			if calcMonth, err = stayfee.PeriodAnchor(sealed.PeriodKey); err != nil {
				c.fail(err)
				return
			}
			if rate, err = stayfee.CorrectionRate(ctx, pool, ap, sealed, scheduleToday); err != nil {
				c.fail(err)
				return
			}
		}
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			c.fail(err)
			return
		}
		save := stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
			Renderer: renderer, Now: now, ScheduleToday: scheduleToday}
		checked, err := stayfee.Check(ctx, pool, save.Dec, ap, calcMonth, today,
			stayfee.Opts{Cadence: cadence, Rate: rate, ScheduleToday: scheduleToday})
		if err != nil {
			c.fail(err)
			return
		}
		if len(checked.Issues) > 0 {
			blocked()
			return
		}
		latest, err := stayfee.Latest(ctx, pool, row.ID, checked.Key)
		if err != nil {
			c.fail(err)
			return
		}
		if latest != nil && !correcting {
			c.back(back, hostweb.Flash{}, c.finalizeFlash("flash.stay_fees.already_saved"))
			return
		}
		collected := map[int64]int{}
		if checked.Period != nil {
			for _, line := range checked.Period.Lines {
				raw := c.formStr("collected_" + strconv.FormatInt(line.GuestID, 10))
				amount := line.AmountCZK
				if raw != "" {
					parsed, ok := stayfee.ParseCZKInt(raw)
					if !ok {
						blocked()
						return
					}
					amount = parsed
				}
				collected[line.GuestID] = amount
			}
			if len(checked.Period.Lines) > 0 && c.formStr("confirm_collected") != "1" {
				c.back(back, hostweb.Flash{}, c.finalizeFlash("flash.stay_fees.confirm_collected"))
				return
			}
		}
		if renderer == nil {
			log.Printf("stayfees finalize: no PDF renderer set, nothing sealed")
			blocked()
			return
		}
		args := stayfee.SaveArgs{Month: checked.Group.First, RateCZK: rate, Collected: collected,
			IssuedOn: today, Cadence: checked.Group.Cadence}
		if correcting {
			id := sealed.ID
			args.ReplacingID = &id
		}
		if _, err := stayfee.Save(ctx, pool, save, ap, args); err != nil {
			switch finalizeSaveOutcome(err) {
			case "blocked":
				blocked()
			case "already_saved":
				c.back(back, hostweb.Flash{}, c.finalizeFlash("flash.stay_fees.already_saved"))
			default:
				c.fail(err)
			}
			return
		}
		if err := c.audit("stay_fee_finalize", "apartment_id="+aptText+" period="+checked.Key); err != nil {
			c.fail(err)
			return
		}
		c.back(back, c.finalizeFlash("flash.stay_fees.period_saved"), hostweb.Flash{})
	}
}

// finalizeSaveOutcome maps the error of stayfee.Save as stay_fee_finalize does:
// ValueError (inactive, overlap, changed) is "blocked", a database integrity
// error (the duplicate version) is "already_saved", anything else is "".
func finalizeSaveOutcome(err error) string {
	switch {
	case errors.Is(err, stayfee.ErrInactive), errors.Is(err, stayfee.ErrOverlap), errors.Is(err, stayfee.ErrChanged):
		return "blocked"
	case errors.Is(err, stayfee.ErrDuplicate), finalizeIntegrity(err):
		return "already_saved"
	}
	return ""
}
