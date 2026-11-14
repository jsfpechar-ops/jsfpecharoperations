package stayfees

// Brief 1586: POST /stay-fees/confirm-ready (stay_fee_confirm_ready in
// App/app/routes/stay_fees.py). Seals the clean period of every listed
// apartment for one month (the steps of stayfee.Confirm, with the audit row of
// a signed-in request, event "stay_fee_finalize") and flashes the count.
//
// Answer without a renderer: flash.stay_fees.bulk_none (nothing was saved) and
// redirect, with nothing sealed and no audit row.

import (
	_ "embed"
	"errors"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

//go:embed confirm_i18n.json
var confirmCatalogJSON []byte

var confirmCatalog = hostweb.Load(confirmCatalogJSON)

// ConfirmReadyHandler serves POST /stay-fees/confirm-ready. renderer draws
// the hlášení PDF; nil seals nothing.
func ConfirmReadyHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, renderer stayfee.PDFRenderer) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		ctx := r.Context()
		today := pragueDay(c.at)
		month := c.month()
		if month.After(monthStart(today.Year(), int(today.Month()))) {
			month = defaultMonth(today)
		}
		back := feeReturnPath(c.formStr("return_to"), 0)
		if back == "" {
			back = "/stay-fees"
		}
		none := func() {
			c.back(back, hostweb.Flash{}, hostweb.Flash{Text: confirmCatalog.T(c.lang, "flash.stay_fees.bulk_none", nil), Key: "flash.stay_fees.bulk_none"})
		}
		if renderer == nil {
			log.Printf("stayfees confirm-ready: no PDF renderer set, nothing sealed")
			none()
			return
		}
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			c.fail(err)
			return
		}
		u := c.at.UTC()
		save := stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
			Renderer: renderer, Now: now, ScheduleToday: stayfee.Day(u.Year(), u.Month(), u.Day())}
		saved := 0
		seen := map[string]bool{}
		for _, raw := range c.r.PostForm["apartment_id"] {
			text := strings.TrimSpace(raw)
			if !isDigits(text) || seen[text] {
				continue
			}
			seen[text] = true
			id, err := strconv.ParseInt(text, 10, 64)
			if err != nil {
				continue // beyond int64: no such row
			}
			row, err := c.apartmentOf(ctx, id)
			if err != nil {
				c.fail(err)
				return
			}
			if row == nil || !isActive(row.Rate) || row.Archived {
				continue
			}
			var live bool
			if err := pool.QueryRow(ctx, `SELECT active <> 0 FROM apartment WHERE id = $1`, row.ID).Scan(&live); err != nil {
				c.fail(err)
				return
			}
			if !live {
				continue
			}
			ap, err := stayfee.LoadApartment(ctx, pool, row.ID)
			if err != nil {
				c.fail(err)
				return
			}
			sealed, err := c.confirmOne(save, ap, month, today)
			if err != nil {
				c.fail(err)
				return
			}
			if sealed {
				saved++
			}
		}
		if saved == 0 {
			none()
			return
		}
		c.back(back, hostweb.Flash{Text: confirmCatalog.T(c.lang, "flash.stay_fees.bulk_saved", map[string]any{"count": saved}),
			Key: "flash.stay_fees.bulk_saved", Count: saved}, hostweb.Flash{})
	}
}

// confirmOne is stayfee.Confirm with the audit row of a signed-in request:
// db.audit writes the username as actor, the account id and the impersonator
// (stayfee.Confirm writes the job's actor "host" instead). Same checks, same
// refusals: a blocked, already sealed or refused period returns false.
func (c *call) confirmOne(save stayfee.SaveDeps, ap *stayfee.Apartment, month, today time.Time) (bool, error) {
	ctx := c.r.Context()
	checked, err := stayfee.Check(ctx, c.pool, save.Dec, ap, month, today, stayfee.Opts{ScheduleToday: save.ScheduleToday})
	if err != nil || len(checked.Issues) > 0 {
		return false, err
	}
	latest, err := stayfee.Latest(ctx, c.pool, ap.ID, checked.Key)
	if err != nil || latest != nil {
		return false, err
	}
	collected := map[int64]int{}
	if checked.Period != nil {
		for _, line := range checked.Period.Lines {
			collected[line.GuestID] = line.AmountCZK
		}
	}
	_, err = stayfee.Save(ctx, c.pool, save, ap, stayfee.SaveArgs{Month: checked.Group.First, Collected: collected,
		IssuedOn: today, Cadence: checked.Group.Cadence})
	if err != nil {
		if errors.Is(err, stayfee.ErrInactive) || errors.Is(err, stayfee.ErrOverlap) || errors.Is(err, stayfee.ErrChanged) ||
			errors.Is(err, stayfee.ErrDuplicate) || confirmIntegrity(err) {
			return false, nil
		}
		return false, err
	}
	return true, c.audit("stay_fee_finalize", "apartment_id="+strconv.FormatInt(ap.ID, 10)+" period="+checked.Key)
}

// confirmIntegrity is db.integrity_errors(): any SQLSTATE of class 23.
func confirmIntegrity(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && len(pgErr.Code) >= 2 && pgErr.Code[:2] == "23"
}
