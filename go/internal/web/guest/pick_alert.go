package guest

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

func alertControllerMissing(ctx context.Context, pool *pgxpool.Pool, apt pickApartment) {
	if pool == nil {
		return
	}
	ok, err := controllerComplete(ctx, pool, apt)
	if err != nil || ok {
		return
	}
	owner := int64(0)
	if apt.OwnerUserID != nil {
		owner = *apt.OwnerUserID
	}
	aptID := apt.ID
	_ = ubyport.RaiseAlert(ctx, pool, "critical", "controller_missing",
		"The guest form cannot name who controls the guest's data.",
		"Add the data controller's name, address or IČO and contact e-mail.",
		"controller_missing:"+apt.PermalinkToken, &aptID, nil, &owner, nil)
}

func controllerComplete(ctx context.Context, pool *pgxpool.Pool, apt pickApartment) (bool, error) {
	entityID := int64(0)
	if apt.DataControllerID != nil && *apt.DataControllerID > 0 {
		entityID = *apt.DataControllerID
	} else if apt.LegalEntityID != nil {
		entityID = *apt.LegalEntityID
	}
	if entityID == 0 {
		return false, nil
	}
	var name, seat, ico, email string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(name,''), COALESCE(seat,''), COALESCE(ico,''), COALESCE(contact_email,'')
		 FROM legal_entity WHERE id = $1`, entityID).
		Scan(&name, &seat, &ico, &email)
	if err == pgx.ErrNoRows {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return name != "" && email != "" && (ico != "" || seat != ""), nil
}
