package guest

// Guest Leon JSON chat (brief 2039). Routes stay in leon_questions.go; reply logic in ai/leon_reply.go.

import (
	"regexp"
	"strings"
	"time"

	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"net/http"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

var leonClientID = regexp.MustCompile(`^[A-Za-z0-9_-]{8,40}$`)

// leonStayReady mirrors guest_leon stay gate: any failed check means 404 JSON, never the early redirect body.
func leonStayReady(r *http.Request, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, token string, resID int64) (lang string, apt *GuideApartment, res *GuideReservation, ok bool) {
	lang = Language(r)
	aptRow, link, early := OpenLink(r, pool, token, lang)
	if early != nil || aptRow == nil {
		return lang, nil, nil, false
	}
	sh := shellDeps{pool: pool, getenv: getenv, now: now}
	if requirePinSilent(r, sh, link, aptRow) {
		return lang, nil, nil, false
	}
	stay, code := stayReservationForGuest(r, pool, getenv, now, aptRow, link, resID, true)
	if code != 0 || stay == nil {
		return lang, nil, nil, false
	}
	row, err := EnsureClaimRow(r.Context(), pool, resID, isoNow(now()))
	if err != nil {
		return lang, nil, nil, false
	}
	if !GuestAccessOpen(stay.status, row.guestAccessLock) {
		return lang, nil, nil, false
	}
	if billingjob.MailEnabled() && !(guestAccess{pool: pool, getenv: getenv, now: now}).hostOwns(r.Context(), r, aptRow.OwnerUserID) {
		if row.state != claimStateClaimed || !DeviceHoldsClaim(r, getenv, resID, row.tokenVersion) {
			return lang, nil, nil, false
		}
	}
	gRes, err := guideReservationDates(r.Context(), pool, resID, aptRow.ID)
	if err != nil || gRes == nil {
		return lang, nil, nil, false
	}
	return lang, &GuideApartment{ID: aptRow.ID, OwnerUserID: aptRow.OwnerUserID, Name: aptRow.InternalName}, gRes, true
}

func requirePinSilent(r *http.Request, sh shellDeps, link string, apt *Apartment) bool {
	if !guestPinRequired(sh.getenv) {
		return false
	}
	if apt == nil {
		return true
	}
	access := guestAccess{pool: sh.pool, getenv: sh.getenv, now: sh.now}
	if access.hostOwns(r.Context(), r, apt.OwnerUserID) {
		return false
	}
	lockToken := apt.PermalinkToken
	if lockToken == "" {
		lockToken = link
	}
	return !PinSessionValid(r, sh.getenv, lockToken, strings.TrimSpace(apt.PermalinkPIN), sh.now())
}

func (s *lqServer) leonQRReady(r *http.Request, token string) (lang string, apt *GuideApartment, ok bool) {
	lang = Language(r)
	key := clientip.Key(r, s.getenv, "guide_qr")
	if RateBlocked(r.Context(), s.pool, "guide_qr", key, QRMaxViews, s.now()) {
		return lang, nil, false
	}
	var row GuideApartment
	err := s.pool.QueryRow(r.Context(), `SELECT id, owner_user_id, COALESCE(internal_name,'')
		FROM apartment WHERE guide_token = $1 AND active = 1 AND COALESCE(archived_at,'') = ''`, token).
		Scan(&row.ID, &row.OwnerUserID, &row.Name)
	if errors.Is(err, pgx.ErrNoRows) || err != nil {
		return lang, nil, false
	}
	return lang, &row, true
}

func (s *lqServer) leonApartment(ctx context.Context, id int64) (ai.LeonApartment, string, error) {
	var a ai.LeonApartment
	var name string
	err := s.pool.QueryRow(ctx, `SELECT id, owner_user_id, COALESCE(internal_name,''), leon_enabled <> 0, COALESCE(leon_terms_version,'')
		FROM apartment WHERE id = $1`, id).Scan(&a.ID, &a.OwnerID, &name, &a.Enabled, &a.TermsVersion)
	if err != nil {
		return a, "", err
	}
	var host string
	_ = s.pool.QueryRow(ctx, `SELECT COALESCE(le.name,'') FROM apartment a LEFT JOIN legal_entity le ON le.id = a.legal_entity_id WHERE a.id = $1`, id).Scan(&host)
	a.Name = name
	return a, host, nil
}

func (s *lqServer) leonSwitched(ctx context.Context, a ai.LeonApartment) (bool, error) {
	ls := ai.LeonStore{HavelStore: ai.HavelStore{Pool: s.pool, Env: s.lookupEnv}}
	return ls.SwitchedOn(ctx, a)
}

func leonNewCookieID() string {
	b := make([]byte, 18)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)[:24]
}

func (s *lqServer) guestLeonPost(ctx context.Context, aptID int64, door string, resID int64, cookie, lang, message, clientID, addrKey, level, propertyName string) (map[string]any, error) {
	ls := ai.LeonStore{HavelStore: ai.HavelStore{Pool: s.pool, Env: s.lookupEnv}}
	la, hostName, err := s.leonApartment(ctx, aptID)
	if err != nil {
		return nil, err
	}
	var chat *ai.LeonChatRow
	if door == "stay" {
		chat, err = ls.StayChat(ctx, aptID, resID, lang, s.now())
	} else {
		chat, err = ls.QRChat(ctx, aptID, cookie, lang, s.now())
	}
	if err != nil {
		return nil, err
	}
	res, err := ls.Reply(ctx, s.model, chat, la, message, level, propertyName, hostName, addrKey, lang, clientID, s.now())
	if err != nil {
		return nil, err
	}
	out := map[string]any{"kind": res.Kind, "text": res.Text, "asked_host": res.QuestionID != nil}
	return out, nil
}
