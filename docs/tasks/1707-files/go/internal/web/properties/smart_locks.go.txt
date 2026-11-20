package properties

// Brief 1707: POST /smart-locks/setup, /smart-locks/refresh, /smart-locks/remove.

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

//go:embed smartlocks/i18n.json
var smartLocksJSON []byte

var smartLocksCatalog = hostweb.Load(smartLocksJSON)

const doorCodeTermsVersion = "2026-10-12"

var smartLockSectionAnchors = map[string]string{
	"how": "smart-locks-how", "share": "smart-locks-share", "add-more": "smart-locks-add-more", "list": "smart-locks-list",
}

func RegisterSmartLocks(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /smart-locks/setup", wrap("/smart-locks/setup", s.smartLocksSetup))
	mux.Handle("POST /smart-locks/refresh", wrap("/smart-locks/refresh", s.smartLocksRefresh))
	mux.Handle("POST /smart-locks/remove", wrap("/smart-locks/remove", s.smartLocksRemove))
}

func smartLocksFlash(q *request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: smartLocksCatalog.T(q.lang, key, params), Key: key}
}

func smartLocksPlural(r *http.Request, base string, n int) hostweb.Flash {
	lang := hostweb.Lang(r)
	p := map[string]any{"count": n, "n": n}
	return hostweb.Flash{Text: smartLocksCatalog.T(lang, pluralFlashKey(base, n, lang), p), Key: base, Count: n}
}

func (s *server) enterSmartLocks(w http.ResponseWriter, r *http.Request) (*request, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, false
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		fail(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	_ = r.ParseMultipartForm(32 << 20)
	return &request{host: h, lang: hostweb.Lang(r), at: at}, true
}

func (s *server) ttlockDeps(ctx context.Context) (ttlock.AccountStore, *ttlock.Client, error) {
	cfg, err := ttlock.ConfigFromEnv(s.getenv)
	if err != nil {
		return nil, nil, err
	}
	keys, err := secure.LoadDataKeys(s.getenv)
	if err != nil {
		return nil, nil, err
	}
	store := doorcodes.NewAccountStore(s.pool, keys)
	budget := ttlock.NewPGBudget(s.pool, cfg.MonthlyCalls, s.now)
	client := ttlock.New(cfg, ttlock.Options{Accounts: store, Budget: budget})
	return store, client, nil
}

func smartLocksReturnTo(r *http.Request, def string) string {
	path := safeLocalPath(formReturnTo(r, def, false), "/smart-locks")
	if path == "/smart-locks" || strings.HasPrefix(path, "/apartments") {
		return path
	}
	return "/smart-locks"
}

func (s *server) lockPropertyReturn(ctx context.Context, owner int64, returnTo string) string {
	path := strings.SplitN(strings.SplitN(returnTo, "#", 2)[0], "?", 2)[0]
	m := lockPropertyPath.FindStringSubmatch(path)
	if m == nil {
		return ""
	}
	id, err := strconv.ParseInt(m[1], 10, 64)
	if err != nil {
		return ""
	}
	var one int
	switch err := s.pool.QueryRow(ctx, ownApartmentSQL, id, owner).Scan(&one); {
	case err == nil:
		return fmt.Sprintf("/apartments/%d?view=settings&section=lock&sec=lock#sec-lock", id)
	default:
		return ""
	}
}

func (s *server) lockTabURL(ctx context.Context, owner int64, returnTo, anchor string) (string, error) {
	if own := s.lockPropertyReturn(ctx, owner, returnTo); own != "" {
		return strings.SplitN(own, "#", 2)[0] + "#sec-lock", nil
	}
	var first int64
	switch err := s.pool.QueryRow(ctx, firstActiveSQL, owner).Scan(&first); {
	case err == nil:
		return fmt.Sprintf("/apartments/%d?view=settings&section=lock#%s", first, anchor), nil
	case errors.Is(err, pgx.ErrNoRows):
		return "/apartments", nil
	default:
		return "", err
	}
}

func smartLocksURL(ctx context.Context, s *server, owner int64, returnTo, section string) (string, error) {
	anchor := smartLockSectionAnchors[section]
	if anchor == "" {
		anchor = "smart-locks-how"
	}
	return s.lockTabURL(ctx, owner, returnTo, anchor)
}

func smartLocksSection(r *http.Request, hasLocks bool) string {
	switch formStr(r, "section") {
	case "share", "add-more", "list":
		return formStr(r, "section")
	}
	if hasLocks {
		return "list"
	}
	return "share"
}

const ttlockSetupWindow = 15 * 60

func (s *server) defaultOnFirstLock(ctx context.Context, q *request, lockID string) error {
	owner := q.host.Workspace.ID
	rows, err := s.pool.Query(ctx,
		`SELECT id FROM apartment WHERE owner_user_id = $1 AND lock_provider IS NULL AND lock_id IS NULL
		 AND checkin_hour IS NOT NULL AND checkout_hour IS NOT NULL`, owner)
	if err != nil {
		return err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return err
		}
		ids = append(ids, id)
	}
	if len(ids) != 1 {
		return rows.Err()
	}
	var other int
	if err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM apartment WHERE owner_user_id = $1 AND lock_provider = 'ttlock' AND lock_id = $2 AND id <> $3`,
		owner, lockID, ids[0]).Scan(&other); err != nil {
		return err
	}
	if other > 0 {
		return nil
	}
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET lock_provider = 'ttlock', lock_id = $1 WHERE id = $2`, lockID, ids[0]); err != nil {
		return err
	}
	return s.audit(ctx, q, "door_codes_on", fmt.Sprintf("apartment=%d", ids[0]))
}

func (s *server) smartLocksSetup(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enterSmartLocks(w, r)
	if !ok {
		return
	}
	if !doorCodesEnabled(s.getenv) {
		q.back(w, r, "/apartments", hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_unavailable", nil))
		return
	}
	ctx := r.Context()
	returnTo := smartLocksReturnTo(r, "/smart-locks")
	setupPage, err := smartLocksURL(ctx, s, q.host.Workspace.ID, returnTo, "how")
	if err != nil {
		fail(w, err)
		return
	}
	if formStr(r, "terms") != "1" {
		q.back(w, r, setupPage, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_terms", nil))
		return
	}
	owner := q.host.Workspace.ID
	key := fmt.Sprintf("user:%d", owner)
	if blocked, err := rateBlocked(ctx, s.pool, "ttlock_setup", key, 5, ttlockSetupWindow, q.at); err != nil {
		fail(w, err)
		return
	} else if blocked {
		q.back(w, r, setupPage, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_rate_limited", nil))
		return
	}
	if err := rateRecord(ctx, s.pool, "ttlock_setup", key, q.at); err != nil {
		fail(w, err)
		return
	}
	_, client, err := s.ttlockDeps(ctx)
	if err != nil {
		fail(w, err)
		return
	}
	if _, err := client.CreateAccount(ctx, owner); err != nil {
		if _, ok := ttlock.AsError(err); ok {
			q.back(w, r, setupPage, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_failed", nil))
			return
		}
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "door_code_terms_accepted", "version="+doorCodeTermsVersion); err != nil {
		fail(w, err)
		return
	}
	share, err := smartLocksURL(ctx, s, owner, returnTo, "share")
	if err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, share, smartLocksFlash(q, "flash.ok.smart_locks_ready", nil), hostweb.Flash{})
}

func (s *server) smartLocksRefresh(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enterSmartLocks(w, r)
	if !ok {
		return
	}
	if !doorCodesEnabled(s.getenv) {
		q.back(w, r, "/apartments", hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_unavailable", nil))
		return
	}
	ctx := r.Context()
	returnTo := smartLocksReturnTo(r, "/smart-locks")
	owner := q.host.Workspace.ID
	store, client, err := s.ttlockDeps(ctx)
	if err != nil {
		fail(w, err)
		return
	}
	account, err := store.ForOwner(ctx, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if account == nil {
		how, err := smartLocksURL(ctx, s, owner, returnTo, "how")
		if err != nil {
			fail(w, err)
			return
		}
		q.back(w, r, how, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_missing_account", nil))
		return
	}
	locks, _ := ttlock.ParseLocks(account.LocksJSON)
	here, err := smartLocksURL(ctx, s, owner, returnTo, smartLocksSection(r, len(locks) > 0))
	if err != nil {
		fail(w, err)
		return
	}
	locks, plain, err := client.CheckLocks(ctx, account.ID)
	if err != nil {
		if te, ok := ttlock.AsError(err); ok {
			switch te.Kind {
			case ttlock.KindBudget:
				q.back(w, r, here, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_budget", nil))
				return
			case ttlock.KindReauth:
				q.back(w, r, here, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_reauth", nil))
				return
			}
			q.back(w, r, here, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_failed", nil))
			return
		}
		fail(w, err)
		return
	}
	share, err := smartLocksURL(ctx, s, owner, returnTo, "share")
	if err != nil {
		fail(w, err)
		return
	}
	if len(locks) == 0 && plain > 0 {
		q.back(w, r, share, hostweb.Flash{}, hostweb.Flash{Text: smartLocksCatalog.T(q.lang, "flash.error.smart_locks_plain_key", nil), Key: "flash.error.smart_locks_plain_key", Fix: "lock_guide"})
		return
	}
	if len(locks) == 0 {
		q.back(w, r, share, smartLocksFlash(q, "flash.ok.smart_locks_none_yet", nil), hostweb.Flash{Fix: "lock_guide"})
		return
	}
	if len(locks) == 1 {
		if err := s.defaultOnFirstLock(ctx, q, locks[0].LockID); err != nil {
			fail(w, err)
			return
		}
	}
	target := s.lockPropertyReturn(ctx, owner, returnTo)
	if target == "" {
		target, err = smartLocksURL(ctx, s, owner, returnTo, "list")
		if err != nil {
			fail(w, err)
			return
		}
	}
	q.back(w, r, target, smartLocksPlural(r, "flash.ok.smart_locks_found", len(locks)), hostweb.Flash{})
}

func (s *server) smartLocksRemove(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enterSmartLocks(w, r)
	if !ok {
		return
	}
	if !doorCodesEnabled(s.getenv) {
		q.back(w, r, "/apartments", hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_unavailable", nil))
		return
	}
	ctx := r.Context()
	returnTo := smartLocksReturnTo(r, "/smart-locks")
	owner := q.host.Workspace.ID
	store, client, err := s.ttlockDeps(ctx)
	if err != nil {
		fail(w, err)
		return
	}
	account, err := store.ForOwner(ctx, owner)
	if err != nil {
		fail(w, err)
		return
	}
	if account == nil {
		how, err := smartLocksURL(ctx, s, owner, returnTo, "how")
		if err != nil {
			fail(w, err)
			return
		}
		q.back(w, r, how, hostweb.Flash{}, smartLocksFlash(q, "flash.error.smart_locks_missing_account", nil))
		return
	}
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET lock_provider = NULL, updated_at = $1 WHERE owner_user_id = $2`, stamp(q.at), owner); err != nil {
		fail(w, err)
		return
	}
	localOnly := false
	if err := client.DeleteAccount(ctx, account.ID); err != nil {
		if _, ok := ttlock.AsError(err); ok {
			localOnly = true
		} else {
			fail(w, err)
			return
		}
	}
	if err := s.audit(ctx, q, "smart_locks_removed", ""); err != nil {
		fail(w, err)
		return
	}
	key := "flash.ok.smart_locks_removed"
	if localOnly {
		key = "flash.ok.smart_locks_removed_local"
	}
	how, err := smartLocksURL(ctx, s, owner, returnTo, "how")
	if err != nil {
		fail(w, err)
		return
	}
	q.back(w, r, how, smartLocksFlash(q, key, nil), hostweb.Flash{})
}
