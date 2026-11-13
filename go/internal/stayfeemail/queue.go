package stayfeemail

// mail_notify.queue_stay_fee_report / queue_stay_fee_blocked with
// mail.enqueue's gates, and stay_fee.reconcile_no_pay_way_alert /
// reconcile_all_no_pay_way (brief 1242).

import (
	"context"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// NoPayWayKind is stay_fee.NO_PAY_WAY_KIND.
const NoPayWayKind = "stay_fee_no_pay_way"

const noPayWayMessage = "Guests cannot pay the stay fee: add a bank account"

func appBase(getenv func(string) string) string    { return hostweb.AppBase(getenv) }
func publicBase(getenv func(string) string) string { return hostweb.PublicBase(getenv) }

// mailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND console or ses.
func mailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

// guestPayOn is config.STAY_FEE_GUEST_PAY.
func guestPayOn(getenv func(string) string) bool {
	return strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
}

// entityContactEmail is mail_notify._entity_contact_email.
func (r *runner) entityContactEmail(ctx context.Context, legalEntityID int64) (string, error) {
	if legalEntityID == 0 {
		return "", nil
	}
	rows, err := r.pool.Query(ctx, `SELECT COALESCE(contact_email, '') FROM legal_entity WHERE id = $1`, legalEntityID)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	if !rows.Next() {
		return "", rows.Err()
	}
	var raw string
	if err := rows.Scan(&raw); err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(raw), nil
}

// enqueue is mail.enqueue for a host kind: nothing when mail is off or there
// is no address. Python logs an insert failure and returns the row that is
// there, if any; here that is EnqueueMail's error, logged, and 0.
func (r *runner) enqueue(ctx context.Context, kind, key, to, subject, payload string, apartmentID, owner int64) int64 {
	if !r.mailOn {
		slog.Info("mail disabled; skip enqueue", "kind", kind)
		return 0
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return 0
	}
	id, err := ubyport.EnqueueMail(ctx, r.pool, ubyport.OutboxMail{Kind: kind, Key: key, ApartmentID: &apartmentID,
		OwnerUserID: &owner, To: to, Subject: subject, Payload: payload})
	if err != nil {
		slog.Error("mail enqueue failed", "kind", kind, "error", err)
		return 0
	}
	return id
}

func propertyName(ap *stayfee.Apartment) string {
	if ap.InternalName == "" {
		return "UbyHost"
	}
	return ap.InternalName
}

func (r *runner) reportURL(apartmentID int64, month string) string {
	return fmt.Sprintf("%s/stay-fees/%d?month=%s", r.appBase, apartmentID, month)
}

// queueReport is mail_notify.queue_stay_fee_report with lang None.
func (r *runner) queueReport(ctx context.Context, ap *stayfee.Apartment, owner int64, row *stayfee.FilingRow) (int64, error) {
	to, err := r.entityContactEmail(ctx, ap.LegalEntityID)
	if err != nil || to == "" {
		return 0, err
	}
	lang := hostMailLanguage
	month, err := stayfee.PeriodAnchor(row.PeriodKey)
	if err != nil {
		return 0, err
	}
	total := row.TotalDueCZK
	group := &stayfee.Group{Anchor: ap, VS: stayfee.VSOf(ap), TotalCZK: total}
	details := stayfee.PaymentDetails(group)
	hasQR := details != nil && details.SPAYD != ""
	var databox string
	if err := r.pool.QueryRow(ctx, `SELECT COALESCE(stay_fee_authority_databox, '') FROM apartment WHERE id = $1`,
		ap.ID).Scan(&databox); err != nil {
		return 0, err
	}
	account, vs := "", group.VS
	if details != nil {
		account = details.Account
		if details.VS != "" {
			vs = details.VS
		}
	}
	built := BuildStayFeeReport(r.appBase, r.publicBase, lang, StayFeeReport{
		PropertyName: propertyName(ap),
		Period:       PeriodLabel(lang, row.Cadence, month.Year(), int(month.Month())),
		Amount:       stayfee.FormatCZK(total),
		TotalCZK:     total,
		Authority:    ap.AuthorityName,
		Databox:      databox,
		Account:      account,
		VS:           vs,
		HasQR:        hasQR,
		ReportURL:    r.reportURL(ap.ID, stayfee.MonthKey(month)),
	})
	var b strings.Builder
	b.WriteString(`{"text": ` + ubyport.PyString(built.Text) + `, "html": ` + ubyport.PyString(built.HTML) +
		`, "lang": ` + ubyport.PyString(lang) + `, "stay_fee_filing_id": ` + strconv.FormatInt(row.ID, 10))
	if hasQR {
		b.WriteString(`, "qr_spayd": ` + ubyport.PyString(details.SPAYD))
	}
	b.WriteString("}")
	key := fmt.Sprintf("stay_fee_report:%d:%s:v%d", ap.ID, row.PeriodKey, row.Version)
	return r.enqueue(ctx, "stay_fee_report", key, to, built.Subject, b.String(), ap.ID, owner), nil
}

// queueBlocked is mail_notify.queue_stay_fee_blocked with lang None.
func (r *runner) queueBlocked(ctx context.Context, ap *stayfee.Apartment, owner int64, g *stayfee.Group, issues []string) (int64, error) {
	to, err := r.entityContactEmail(ctx, ap.LegalEntityID)
	if err != nil || to == "" {
		return 0, err
	}
	lang := hostMailLanguage
	key := stayfee.PeriodKey(g.Cadence, g.First)
	reportURL := r.reportURL(ap.ID, stayfee.MonthKey(g.First))
	built := BuildStayFeeBlocked(r.appBase, r.publicBase, lang, propertyName(ap),
		PeriodLabel(lang, g.Cadence, g.First.Year(), int(g.First.Month())), append([]string(nil), issues...), reportURL)
	payload := `{"text": ` + ubyport.PyString(built.Text) + `, "html": ` + ubyport.PyString(built.HTML) +
		`, "lang": ` + ubyport.PyString(lang) + `}`
	return r.enqueue(ctx, "stay_fee_blocked", fmt.Sprintf("stay_fee_blocked:%d:%s", ap.ID, key), to,
		built.Subject, payload, ap.ID, owner), nil
}

// ReconcileNoPayWay is stay_fee.reconcile_no_pay_way_alert: raise the host
// alert while no pay way works, resolve it once one does or collection is off.
func ReconcileNoPayWay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apartmentID int64) error {
	key := fmt.Sprintf("%s:%d", NoPayWayKind, apartmentID)
	ap, err := stayfee.LoadApartment(ctx, pool, apartmentID)
	if err != nil && err != stayfee.ErrNotFound {
		return err
	}
	noPay := false
	if ap != nil {
		entity, err := stayfee.LoadEntity(ctx, pool, nil, ap.LegalEntityID, false)
		if err != nil {
			return err
		}
		noPay = stayfee.NoPayWay(ap, entity, guestPayOn(getenv))
	}
	if !noPay {
		return ubyport.ResolveAlert(ctx, pool, key)
	}
	id := apartmentID
	return ubyport.RaiseAlert(ctx, pool, "warning", NoPayWayKind, noPayWayMessage, "", key, &id, nil, nil,
		ubyport.AlertParams{"property": ap.InternalName})
}

// ReconcileAllNoPayWay is stay_fee.reconcile_all_no_pay_way: every collecting,
// unarchived apartment and every apartment with an open alert of the kind, in
// id order (Python iterates a set). It returns how many it checked and stops
// at the first error, as Python does.
func ReconcileAllNoPayWay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string) (int, error) {
	collecting, err := queryIDs(ctx, pool, `SELECT id FROM apartment WHERE stay_fee_collect = 1 AND archived_at IS NULL`)
	if err != nil {
		return 0, err
	}
	alerted, err := queryIDs(ctx, pool, `SELECT apartment_id FROM alert WHERE kind = $1 AND resolved_at IS NULL
		AND apartment_id IS NOT NULL`, NoPayWayKind)
	if err != nil {
		return 0, err
	}
	seen := map[int64]bool{}
	var ids []int64
	for _, id := range append(collecting, alerted...) {
		if !seen[id] {
			seen[id] = true
			ids = append(ids, id)
		}
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for _, id := range ids {
		if err := ReconcileNoPayWay(ctx, pool, getenv, id); err != nil {
			return 0, err
		}
	}
	return len(ids), nil
}
