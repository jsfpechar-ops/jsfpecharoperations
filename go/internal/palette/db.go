package palette

import (
	"context"
	"strconv"

	"github.com/jackc/pgx/v5"
)

// apartment is the subset of an apartment row the palette reads.
type apartment struct {
	id             int64
	internalName   string
	ubyName        string
	cityEn         string
	permalinkToken string
}

// stay is a reservation row joined to its apartment (the palette's stays query).
type stay struct {
	id           int64
	apartmentID  int64
	dateFrom     string
	dateTo       string
	summary      string
	internalName string
}

// submission is a submission row joined to its apartment (the palette's submissions query).
type submission struct {
	id           int64
	apartmentID  int64
	createdAt    string
	state        string
	internalName string
}

// apartmentRows is access.apartments: non-archived rows of the workspace owner,
// NULL-safe on the owner, ordered by internal name.
func apartmentRows(ctx context.Context, pool pgxPool, owner *int64) ([]apartment, error) {
	rows, err := pool.Query(ctx,
		`SELECT id, internal_name, COALESCE(uby_name, ''), COALESCE(city_en, ''), COALESCE(permalink_token, '')
		   FROM apartment
		  WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL
		  ORDER BY internal_name`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []apartment
	for rows.Next() {
		var a apartment
		if err := rows.Scan(&a.id, &a.internalName, &a.ubyName, &a.cityEn, &a.permalinkToken); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// invoiceDetailsURL is access.invoice_details_url: one business opens its
// Invoice details, several (or none) open the business list.
func invoiceDetailsURL(ctx context.Context, pool pgxPool, owner *int64) (string, error) {
	rows, err := pool.Query(ctx,
		`SELECT id FROM legal_entity
		  WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL
		  ORDER BY name LIMIT 2`, owner)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return "", err
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}
	if len(ids) == 1 {
		return "/entities?edit=" + itoa(ids[0]) + "&next=/invoices#entity-invoice", nil
	}
	return "/entities", nil
}

// lockAccountExists is ttlock.account_for(owner) is not None.
func lockAccountExists(ctx context.Context, pool pgxPool, owner *int64) (bool, error) {
	if owner == nil {
		return false, nil
	}
	var one int
	err := pool.QueryRow(ctx,
		`SELECT 1 FROM lock_account WHERE owner_user_id = $1 AND provider = 'ttlock' LIMIT 1`, *owner).Scan(&one)
	if err == pgx.ErrNoRows {
		return false, nil
	}
	return err == nil, err
}

// linkKey is guest_slug.link_key for an apartment with a permalink token: the
// current slug (created by ensure if missing), else the permanent token.
func linkKey(ctx context.Context, pool pgxPool, a apartment) (string, error) {
	slug, err := ensure(ctx, pool, a)
	if err != nil {
		return "", err
	}
	if slug != "" {
		return slug, nil
	}
	return a.permalinkToken, nil
}

// stayRows is the palette's stays query: 80 newest non-archived reservations.
func stayRows(ctx context.Context, pool pgxPool, owner *int64) ([]stay, error) {
	rows, err := pool.Query(ctx,
		`SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.summary, ''), a.internal_name
		   FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		  WHERE r.archived_at IS NULL AND ($1::bigint IS NULL OR a.owner_user_id = $1)
		  ORDER BY r.date_from DESC LIMIT 80`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []stay
	for rows.Next() {
		var s stay
		if err := rows.Scan(&s.id, &s.apartmentID, &s.dateFrom, &s.dateTo, &s.summary, &s.internalName); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// submissionRows is the palette's submissions query: 40 newest submissions.
func submissionRows(ctx context.Context, pool pgxPool, owner *int64) ([]submission, error) {
	rows, err := pool.Query(ctx,
		`SELECT s.id, s.apartment_id, s.created_at, s.state, a.internal_name
		   FROM submission s JOIN apartment a ON a.id = s.apartment_id
		  WHERE ($1::bigint IS NULL OR a.owner_user_id = $1)
		  ORDER BY s.id DESC LIMIT 40`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []submission
	for rows.Next() {
		var s submission
		if err := rows.Scan(&s.id, &s.apartmentID, &s.createdAt, &s.state, &s.internalName); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func itoa(n int64) string {
	return strconv.FormatInt(n, 10)
}

// accountEmailOf is user["email"] for the signed-in account (empty when none).
func accountEmailOf(ctx context.Context, pool pgxPool, id int64) (string, error) {
	var email *string
	err := pool.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, id).Scan(&email)
	if err == pgx.ErrNoRows || (err == nil && email == nil) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return *email, nil
}
