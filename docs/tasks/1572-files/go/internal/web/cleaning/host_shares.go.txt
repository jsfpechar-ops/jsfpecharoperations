package cleaning

// Share links for the cleaning team (brief 1572): GET and POST /cleaning/shares,
// routes/cleaning.share_settings (332-335), create_share (338-351), _shares
// (318-329) and cleaning.new_share (App/app/cleaning.py 293-308). The link is
// shown once; only its SHA-256 is stored.

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"net/http"
	"sort"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// sharesPage is what cleaning_shares.tmpl reads.
type sharesPage struct {
	Lang, ShareURL, Error string
	Homes                 []home
	Shares                []shareRow
}

type shareRow struct {
	ID        int64
	ExpiresAt string
}

// pyISO is datetime.isoformat() of a UTC time: microseconds only when not zero.
func pyISO(t time.Time) string {
	t = t.UTC()
	if t.Nanosecond()/1000 == 0 {
		return t.Format("2006-01-02T15:04:05") + "+00:00"
	}
	return t.Format("2006-01-02T15:04:05.000000") + "+00:00"
}

// renderShares is routes/cleaning._shares.
func (s *hostServer) renderShares(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, token, errKey string, status int) {
	ctx := r.Context()
	owner := ownerID(h)
	rows, err := s.pool.Query(ctx,
		`SELECT id, expires_at FROM cleaning_share WHERE owner_user_id IS NOT DISTINCT FROM $1
		  AND revoked_at IS NULL AND expires_at > $2 ORDER BY id DESC`, owner, stamp(at))
	if err != nil {
		serverError(w)
		return
	}
	shares := []shareRow{}
	for rows.Next() {
		var row shareRow
		if err := rows.Scan(&row.ID, &row.ExpiresAt); err != nil {
			rows.Close()
			serverError(w)
			return
		}
		shares = append(shares, row)
	}
	rows.Close()
	if rows.Err() != nil {
		serverError(w)
		return
	}
	homes, err := properties(ctx, s.pool, owner, nil)
	if err != nil {
		serverError(w)
		return
	}
	lang := hostweb.Lang(r)
	url := ""
	if token != "" {
		// TLS ends at the proxy: the link comes from the configured public URL, never from the Host header.
		url = hostweb.PublicBase(s.getenv) + "/cleaning/shared/" + token
	}
	s.page(w, r, h, at, status, ct(lang, "share")+suffix, "cleaning_shares", "list",
		sharesPage{Lang: lang, ShareURL: url, Error: errKey, Homes: homes, Shares: shares})
}

func init() { hostAdd("GET /cleaning/shares", (*hostServer).shareSettings) }

// shareSettings is routes/cleaning.share_settings.
func (s *hostServer) shareSettings() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		s.renderShares(w, r, h, at, "", "", 0)
	}
}

// newShare is cleaning.new_share: nil token and key "property" when the ids are
// empty or not all the owner's active properties.
func (s *hostServer) newShare(ctx context.Context, owner *int64, ids []int64, at time.Time) (token, key string, err error) {
	allowed, err := properties(ctx, s.pool, owner, nil)
	if err != nil {
		return "", "", err
	}
	known := map[int64]bool{}
	for _, h := range allowed {
		known[h.ID] = true
	}
	unique := map[int64]bool{}
	for _, id := range ids {
		if !known[id] {
			return "", keyProperty, nil
		}
		unique[id] = true
	}
	if len(unique) == 0 {
		return "", keyProperty, nil
	}
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", "", err
	}
	token = base64.RawURLEncoding.EncodeToString(raw)
	sum := sha256.Sum256([]byte(token))
	list := make([]int64, 0, len(unique))
	for id := range unique {
		list = append(list, id)
	}
	sort.Slice(list, func(i, j int) bool { return list[i] < list[j] })
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	var shareID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO cleaning_share (owner_user_id, token_hash, expires_at, created_at) VALUES ($1, $2, $3, $4) RETURNING id`,
		owner, hex.EncodeToString(sum[:]), pyISO(at.AddDate(0, 0, 30)), stamp(at)).Scan(&shareID); err != nil {
		return "", "", err
	}
	for _, id := range list {
		if _, err := tx.Exec(ctx, `INSERT INTO cleaning_share_property (share_id, apartment_id) VALUES ($1, $2)`, shareID, id); err != nil {
			return "", "", err
		}
	}
	return token, "", tx.Commit(ctx)
}

func init() { hostAdd("POST /cleaning/shares", (*hostServer).createShare) }

// createShare is routes/cleaning.create_share.
func (s *hostServer) createShare() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		if !s.csrf(w, r, at) {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		if !parseHostForm(w, r) {
			return
		}
		if stagingNoLogin(s.getenv) {
			s.renderShares(w, r, h, at, "", "login_required", http.StatusUnprocessableEntity)
			return
		}
		ids := []int64{}
		for _, raw := range r.PostForm["properties"] {
			n, numeric := pyInt(raw)
			if !numeric {
				s.renderShares(w, r, h, at, "", keyProperty, http.StatusUnprocessableEntity)
				return
			}
			ids = append(ids, n)
		}
		token, key, err := s.newShare(r.Context(), ownerID(h), ids, at)
		if err != nil {
			serverError(w)
			return
		}
		if key != "" {
			s.renderShares(w, r, h, at, "", key, http.StatusUnprocessableEntity)
			return
		}
		s.renderShares(w, r, h, at, token, "", 0)
	}
}
