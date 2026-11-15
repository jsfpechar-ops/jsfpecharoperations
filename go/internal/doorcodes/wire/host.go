package doorwire

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// HostNotices implements doorcodes.HostNotices: mail_notify.door_code_notice(door_code_id, stage,
// key_suffix). Python's function never raises: it logs the failure and returns None. So does this.
type HostNotices struct {
	Mailer *Mailer
	Log    *slog.Logger // nil means slog.Default()
}

var _ doorcodes.HostNotices = HostNotices{}

// DoorCodeNotice sends the host notice; a failure is logged and the caller carries on.
func (h HostNotices) DoorCodeNotice(ctx context.Context, doorCodeID int64, stage, keySuffix string) error {
	if err := h.Mailer.DoorCodeNoticeKeyed(ctx, doorCodeID, stage, keySuffix); err != nil {
		hostLog(h.Log).Error(fmt.Sprintf("door_code_notice_failed door_code=%d variant=%s err=%v", doorCodeID, stage, err))
	}
	return nil
}

// Delayed implements doorcodes.DelayedNotifier: mail_notify.door_code_delayed_notice (the host mail,
// support in copy) and push.door_code_missing (one push per stay). Both log and never raise.
type Delayed struct {
	Pool   *pgxpool.Pool
	Mailer *Mailer
	Push   doorcodes.Push
	Log    *slog.Logger // nil means slog.Default()
}

var _ doorcodes.DelayedNotifier = Delayed{}

// DoorCodeDelayedNotice is mail_notify.door_code_delayed_notice(reservation_id, reason).
func (d Delayed) DoorCodeDelayedNotice(ctx context.Context, reservationID int64, reason string) error {
	if err := d.Mailer.DelayedNotice(ctx, reservationID, reason); err != nil {
		hostLog(d.Log).Error(fmt.Sprintf("door_code_delayed_notice_failed reservation_id=%d err=%v", reservationID, err))
	}
	return nil
}

// DoorCodeMissing is push.door_code_missing(reservation_id): kind door_code, key = the reservation id,
// url /reservations/<id>, params property and the stay day as dd.mm.yyyy.
func (d Delayed) DoorCodeMissing(ctx context.Context, reservationID int64) error {
	var id int64
	var dateFrom string
	var owner *int64
	var name *string
	err := d.Pool.QueryRow(ctx,
		"SELECT r.id, r.date_from, a.owner_user_id, a.internal_name "+
			"FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1", reservationID).
		Scan(&id, &dateFrom, &owner, &name)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		hostLog(d.Log).Error(fmt.Sprintf("push_door_code_failed reservation_id=%d err=%v", reservationID, err))
		return nil
	}
	var ownerID int64
	if owner != nil {
		ownerID = *owner
	}
	_, err = d.Push.QueueDoorCode(ctx, ownerID, strconv.FormatInt(id, 10),
		fmt.Sprintf("/reservations/%d", id),
		ubyport.AlertParams{"property": deref(name), "date": stayDayText(dateFrom)})
	if err != nil {
		hostLog(d.Log).Error(fmt.Sprintf("push_door_code_failed reservation_id=%d err=%v", reservationID, err))
	}
	return nil
}

// stayDayText is _day / the mail stay_day: datetime.fromisoformat(value).strftime("%d.%m.%Y"), and the
// raw value when it does not parse.
func stayDayText(raw string) string {
	if len(raw) < 10 {
		return raw
	}
	t, err := time.Parse("2006-01-02", raw[:10])
	if err != nil {
		return raw
	}
	return t.Format("02.01.2006")
}

func hostLog(l *slog.Logger) *slog.Logger {
	if l != nil {
		return l
	}
	return slog.Default()
}
