package stays

// Brief 1734: guest_restrict/unrestrict, verify-identity, passport-photo, reveal-identity
// (App/app/routes/admin.py 4844-4998).

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

var passportPhotoExt = []string{".jpg", ".pdf", ".png", ".webp"}

type privacyGuest struct {
	id, reservationID int64
	nationality       string
	identityVerAt     string
	passportPhotoAt   string
	enteredBy         string
}

func privacyDataDir(getenv func(string) string) string {
	if d := strings.TrimSpace(getenv("UBYHOST_DATA_DIR")); d != "" {
		return d
	}
	return "data"
}

func guestHasPassportPhoto(getenv func(string) string, g privacyGuest) bool {
	if g.nationality == "" || strings.ToUpper(g.nationality) == "CZE" || strings.TrimSpace(g.enteredBy) == "host" {
		return false
	}
	if g.id == 0 || g.passportPhotoAt == "" {
		return false
	}
	dir := filepath.Join(privacyDataDir(getenv), "passport_photos")
	id := strconv.FormatInt(g.id, 10)
	for _, ext := range passportPhotoExt {
		for _, name := range []string{id + ext + ".enc", id + ext} {
			if info, err := os.Stat(filepath.Join(dir, name)); err == nil && info.Mode().IsRegular() {
				return true
			}
		}
	}
	return false
}

func deleteGuestPhoto(getenv func(string) string, guestID int64) error {
	dir := filepath.Join(privacyDataDir(getenv), "passport_photos")
	id := strconv.FormatInt(guestID, 10)
	for _, ext := range passportPhotoExt {
		for _, name := range []string{id + ext + ".enc", id + ext} {
			path := filepath.Join(dir, name)
			info, err := os.Stat(path)
			if errors.Is(err, fs.ErrNotExist) {
				continue
			}
			if err != nil {
				return err
			}
			if info.Mode().IsRegular() {
				if err := os.Remove(path); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func ctypeForExt(ext string) string {
	switch ext {
	case ".jpg":
		return "image/jpeg"
	case ".png":
		return "image/png"
	case ".webp":
		return "image/webp"
	case ".pdf":
		return "application/pdf"
	default:
		return "application/octet-stream"
	}
}

func readGuestPassportPhoto(getenv func(string) string, keys *secure.MultiFernet, guestID int64) ([]byte, string, bool) {
	dir := filepath.Join(privacyDataDir(getenv), "passport_photos")
	id := strconv.FormatInt(guestID, 10)
	for _, ext := range passportPhotoExt {
		enc := filepath.Join(dir, id+ext+".enc")
		if info, err := os.Stat(enc); err == nil && info.Mode().IsRegular() {
			raw, err := os.ReadFile(enc)
			if err != nil || keys == nil {
				return nil, "", false
			}
			plain, err := keys.Decrypt(string(raw), 0, time.Now())
			if err != nil {
				return nil, "", false
			}
			return plain, ctypeForExt(ext), true
		}
		leg := filepath.Join(dir, id+ext)
		if info, err := os.Stat(leg); err == nil && info.Mode().IsRegular() {
			raw, err := os.ReadFile(leg)
			if err != nil {
				return nil, "", false
			}
			return raw, ctypeForExt(ext), true
		}
	}
	return nil, "", false
}

func passportDownloadFilename(guestID int64, mediaType string) string {
	ext := map[string]string{"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}[mediaType]
	if ext == "" {
		ext = ".bin"
	}
	return fmt.Sprintf("passport-%d%s", guestID, ext)
}

func (d guestEditDeps) loadPrivacyGuest(ctx context.Context, owner, guestID int64) (*privacyGuest, bool, error) {
	var g privacyGuest
	err := d.pool.QueryRow(ctx, `SELECT g.id, g.reservation_id, COALESCE(g.nationality,''),
		COALESCE(g.identity_verified_at,''), COALESCE(g.passport_photo_at,''), COALESCE(g.entered_by,'')
		FROM guest g JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id
		WHERE g.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`, guestID, owner).
		Scan(&g.id, &g.reservationID, &g.nationality, &g.identityVerAt, &g.passportPhotoAt, &g.enteredBy)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	return &g, err == nil, err
}

func recordHostIdentityConfirmation(ctx context.Context, c *guestEditCall, guestID int64, g *privacyGuest) error {
	if !validation.GuestIsReportable(g.nationality) || g.identityVerAt != "" {
		return nil
	}
	now := isoStamp(c.at)
	if err := deleteGuestPhoto(c.getenv, guestID); err != nil {
		return err
	}
	_, err := c.pool.Exec(ctx, `UPDATE guest SET identity_verified_at = $1, identity_verified_by = $2,
		passport_photo_at = NULL, updated_at = $1 WHERE id = $3`, now, c.owner, guestID)
	if err != nil {
		return err
	}
	return c.audit(ctx, "guest_identity_verified", fmt.Sprintf("id=%d", guestID))
}

func sessionIssuedAtPtr(payload map[string]any) *int64 {
	if iat, ok := payload["iat"].(int64); ok {
		return &iat
	}
	return nil
}

// RegisterGuestPrivacy wires the privacy routes (dormant until UBYHOST_GO_PATHS).
func RegisterGuestPrivacy(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := guestEditDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /guests/{guest_id}/restrict", wrap("/guests/{guest_id}/restrict", guestRestrictHandler(d)))
	mux.Handle("POST /guests/{guest_id}/unrestrict", wrap("/guests/{guest_id}/unrestrict", guestUnrestrictHandler(d)))
	mux.Handle("POST /guests/{guest_id}/verify-identity", wrap("/guests/{guest_id}/verify-identity", guestVerifyIdentityHandler(d)))
	mux.Handle("GET /guests/{guest_id}/passport-photo", wrap("/guests/{guest_id}/passport-photo", guestPassportPhotoHandler(d)))
	mux.Handle("POST /guests/{guest_id}/reveal-identity", wrap("/guests/{guest_id}/reveal-identity", guestRevealIdentityHandler(d)))
}

func guestRestrictHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadPrivacyGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		now := isoStamp(c.at)
		if _, err = c.pool.Exec(r.Context(), `UPDATE guest SET restricted_at = $1, restricted_reason = $2, updated_at = $1 WHERE id = $3`,
			now, formStr(r, "reason"), id); err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_restricted", fmt.Sprintf("id=%d", id))
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", g.reservationID), c.flash("flash.guest.restricted", nil), hostweb.Flash{})
	}
}

func guestUnrestrictHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadPrivacyGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		now := isoStamp(c.at)
		if _, err = c.pool.Exec(r.Context(), `UPDATE guest SET restricted_at = NULL, restricted_reason = NULL, updated_at = $1 WHERE id = $2`, now, id); err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_unrestricted", fmt.Sprintf("id=%d", id))
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", g.reservationID), c.flash("flash.guest.unrestricted", nil), hostweb.Flash{})
	}
}

func guestVerifyIdentityHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		g, found, err := d.loadPrivacyGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		if !validation.GuestIsReportable(g.nationality) {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", id), hostweb.Flash{}, c.flash("flash.error.czech_no_verification", nil))
			return
		}
		if g.identityVerAt != "" {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", id), c.flash("flash.guests.identity_verified", nil), hostweb.Flash{})
			return
		}
		var resID int64
		if err := c.pool.QueryRow(r.Context(), `SELECT id FROM reservation WHERE id = $1`, g.reservationID).Scan(&resID); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_stay", nil))
				return
			}
			guestEditServerError(w, err)
			return
		}
		if err := recordHostIdentityConfirmation(r.Context(), c, id, g); err != nil {
			guestEditServerError(w, err)
			return
		}
		hostweb.Back(w, r, editFormReturnTo(r, fmt.Sprintf("/guests/%d", id)), c.flash("flash.guests.id_check_recorded", nil), hostweb.Flash{})
	}
}

func guestPassportPhotoHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		at := d.now()
		h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if h == nil {
			return
		}
		g, found, err := d.loadPrivacyGuest(r.Context(), h.Workspace.ID, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found || !guestHasPassportPhoto(d.getenv, *g) {
			http.Error(w, "Not found.", http.StatusNotFound)
			return
		}
		if !guestIdentityVisible(guestRevealFromHost(h), id) {
			w.Header().Set("Cache-Control", "no-store")
			http.Error(w, hostweb.HostStrings.T(hostweb.Lang(r), "identity.hidden", nil), http.StatusForbidden)
			return
		}
		keys, err := secure.LoadDataKeys(d.getenv)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		body, media, okRead := readGuestPassportPhoto(d.getenv, keys, id)
		if !okRead {
			http.Error(w, "Not found.", http.StatusNotFound)
			return
		}
		var impersonator any
		if h.Impersonating {
			impersonator = h.Account.ID
		}
		_, _ = d.pool.Exec(r.Context(), guestEditAuditSQL, isoStamp(at), h.Account.Username, "passport_photo_viewed",
			fmt.Sprintf("guest_id=%d", id), h.Workspace.ID, h.Account.ID, impersonator)
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, passportDownloadFilename(id, media)))
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "sandbox; default-src 'none'")
		w.Header().Set("Content-Type", media)
		_, _ = w.Write(body)
	}
}

func guestRevealIdentityHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		_, found, err := d.loadPrivacyGuest(r.Context(), c.owner, id)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		returnTo := editFormReturnTo(r, fmt.Sprintf("/guests/%d", id))
		if !c.host.Impersonating {
			hostweb.Back(w, r, returnTo, hostweb.Flash{}, hostweb.Flash{})
			return
		}
		reason := strings.TrimSpace(formStr(r, "reason"))
		revealed := append([]int64{}, guestRevealFromHost(c.host).Revealed...)
		revealed = append(revealed, id)
		secret := strings.TrimSpace(d.getenv("UBYHOST_SECRET"))
		if secret == "" {
			guestEditServerError(w, errors.New("missing secret"))
			return
		}
		ast := sessionIssuedAtPtr(c.host.Payload)
		token, err := session.IssueSession(secret, c.host.Account.ID, c.host.Account.SessionVersion, session.IssueOptions{
			Workspace: c.host.Workspace.ID, Remember: true, ImpersonationStartedAt: ast, RevealedGuestIDs: revealed, IssuedAt: ast,
		}, c.at)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		hostweb.Back(w, r, returnTo, c.flash("flash.identity.revealed", nil), hostweb.Flash{})
		http.SetCookie(w, session.SessionCookie(token, true, hostweb.SecureCookies(d.getenv)))
		_ = c.audit(r.Context(), "guest_identity_revealed", fmt.Sprintf("guest_id=%d reason=%s", id, reason))
	}
}
