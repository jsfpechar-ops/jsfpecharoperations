package guest

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// formNoticeVersion is config.GUEST_NOTICE_VERSION.
func formNoticeVersion(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_GUEST_NOTICE_VERSION")); v != "" {
		return v
	}
	return "1.0"
}

func formGuestFieldMap(g *formGuestRow) map[string]string {
	if g == nil {
		return nil
	}
	return map[string]string{
		"first_name":  g.firstName,
		"surname":     g.surname,
		"nationality": g.nationality,
	}
}

func formPagesFillU15(ctx context.Context, d formPageDeps, view *formView, res formResRow, guest *formGuestRow, r *http.Request) {
	var guestID int64
	if guest != nil {
		guestID = guest.id
	}
	signers, pending := formU15Lists(ctx, d.pool, res.id, guestID, formPagesOwnedIDs(r, d.getenv), d.getenv, d.now)
	view.PendingChildren = pending
	if len(pending) > 0 {
		names := make([]string, len(pending))
		for i, c := range pending {
			names[i] = c.Name
		}
		view.PendingChildrenNames = strings.Join(names, ", ")
	}
	view.ChildSigners = signers
	view.AdultSigner = len(signers) > 0
}

func formU15Lists(ctx context.Context, pool *pgxpool.Pool, resID, guestID int64, owned map[int64]bool, getenv func(string) string, now func() time.Time) (adults, pending []formChildEntry) {
	if len(owned) == 0 || pool == nil {
		return nil, nil
	}
	rows, err := pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(signature_png,''), COALESCE(signature_png_enc,''), COALESCE(signed_for_guest_id,0)
		FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var first, surname, birthEnc, birthPlain, sigPlain, sigEnc string
		var signedFor int64
		if err := rows.Scan(&id, &first, &surname, &birthEnc, &birthPlain, &sigPlain, &sigEnc, &signedFor); err != nil {
			return nil, nil
		}
		if !owned[id] || id == guestID {
			continue
		}
		name := strings.TrimSpace(first + " " + surname)
		birth := birthPlain
		if birthEnc != "" {
			if plain, err := decryptGuestField(getenv, now, birthEnc, birthPlain); err == nil {
				birth = plain
			}
		}
		sig := sigPlain
		if sigEnc != "" {
			if plain, err := decryptGuestField(getenv, now, sigEnc, sigPlain); err == nil {
				sig = plain
			}
		}
		entry := formChildEntry{ID: id, Name: name}
		if strings.HasPrefix(sig, "data:image/") || sig == "imported" {
			adults = append(adults, entry)
			continue
		}
		if signedFor == 0 && formGuestUnder15(birth) {
			pending = append(pending, entry)
		}
	}
	return adults, pending
}

func formGuestUnder15(birth string) bool {
	t, ok := validation.ParseISODate(birth)
	if !ok {
		// Police filing stores DDMMYYYY without punctuation too.
		if len(birth) == 8 {
			iso := birth[4:] + "-" + birth[2:4] + "-" + birth[0:2]
			t, ok = validation.ParseISODate(iso)
		}
	}
	if !ok {
		return false
	}
	age := time.Now().UTC().Year() - t.Year()
	return age < 15
}
