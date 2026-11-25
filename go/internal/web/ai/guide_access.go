package ai

// GET and POST /apartments/{id}/access (brief 2036): entry codes for hosts,
// guest-order preview, TTLock door-code status. No outbound requests.

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/apartmententrycode"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func init() {
	guideAdd("GET", "/apartments/{id}/access", (*guideServer).accessPage)
	guideAdd("POST", "/apartments/{id}/access", (*guideServer).accessPost)
}

var (
	accessCodeTypes = []string{"gate", "building_entrance", "garage", "bike_room", "other"}
	accessCodeRe    = regexp.MustCompile(`^[A-Za-z0-9*#-]{1,32}$`)
)

// accessCode is one row on the host page (masked, never plaintext).
type accessCode struct {
	Position      int
	Type, Label   string
	Masked, Until string
	ValidUntilISO string
	Expired       bool
}

type accessPreviewLine struct {
	Label, Masked string
	Door          bool
}

type accessForm struct {
	Open                              bool
	Position                          int
	CodeType, CustomLabel, ValidUntil string
	Errors                            map[string]string
	IsNew                             bool
}

type accessData struct {
	Apartment           *guideApartment
	Base, GuideBase     string
	Codes               []accessCode
	Preview             []accessPreviewLine
	PreviewExternalHost string
	PreviewEmpty        bool
	HasLock             bool
	CanAdd              bool
	Form                *accessForm
	TypeOptions         [][]string
}

func (s *guideServer) accessKeys() (*secure.MultiFernet, error) {
	return secure.LoadDataKeys(s.getenv)
}

func accessMask(plain string) string {
	plain = strings.TrimSpace(plain)
	if plain == "" {
		return "••••"
	}
	runes := []rune(plain)
	return "••••" + string(runes[len(runes)-1])
}

func accessDisplayDate(iso string, loc *time.Location) string {
	if iso == "" {
		return ""
	}
	d, err := time.ParseInLocation("2006-01-02", iso[:10], loc)
	if err != nil {
		return ""
	}
	return d.Format("02.01.2006")
}

func accessToday(at time.Time, loc *time.Location) string {
	return at.In(loc).Format("2006-01-02")
}

func accessTypeLabel(t func(string) string, codeType, custom string) string {
	if codeType == "other" && custom != "" {
		return custom
	}
	return t("access_page.type." + codeType)
}

func (s *guideServer) accessLoad(ctx context.Context, apt int64, lang string, at time.Time) (*accessData, error) {
	t := func(key string) string { return guideCatalog.T(lang, key, nil) }
	loc := at.Location()
	var lockID, extURL string
	if err := s.pool.QueryRow(ctx, `SELECT COALESCE(lock_id, ''), COALESCE(guide_external_url, '') FROM apartment WHERE id = $1`, apt).
		Scan(&lockID, &extURL); err != nil {
		return nil, err
	}
	hasLock := strings.TrimSpace(lockID) != ""
	keys, err := s.accessKeys()
	if err != nil {
		return nil, err
	}
	rows, err := s.pool.Query(ctx, `SELECT position, code_type, COALESCE(custom_label, ''), code_enc, COALESCE(valid_until, '')
FROM apartment_entry_code WHERE apartment_id = $1 ORDER BY position`, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var codes []accessCode
	var orderRows []apartmententrycode.Row
	today := accessToday(at, loc)
	for rows.Next() {
		var c accessCode
		var enc, until string
		if err := rows.Scan(&c.Position, &c.Type, &c.Label, &enc, &until); err != nil {
			return nil, err
		}
		plain, err := keys.DecryptField(enc, at)
		if err != nil {
			return nil, err
		}
		c.Masked = accessMask(plain)
		c.ValidUntilISO = until
		c.Until = accessDisplayDate(until, loc)
		if until != "" && until < today {
			c.Expired = true
		}
		codes = append(codes, c)
		orderRows = append(orderRows, apartmententrycode.Row{Position: c.Position, CodeType: c.Type})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	byPos := make(map[int]accessCode, len(codes))
	for _, c := range codes {
		byPos[c.Position] = c
	}
	var preview []accessPreviewLine
	for _, slot := range apartmententrycode.EntryCodeGuestOrder(orderRows, hasLock) {
		if slot.Door {
			preview = append(preview, accessPreviewLine{Label: t("access_page.preview.door"), Door: true})
			continue
		}
		c := byPos[slot.Row.Position]
		preview = append(preview, accessPreviewLine{Label: accessTypeLabel(t, c.Type, c.Label), Masked: c.Masked})
	}
	extHost := ""
	if extURL != "" {
		if u, err := url.Parse(extURL); err == nil {
			extHost = strings.ToLower(u.Hostname())
		}
	}
	previewEmpty := len(preview) == 0
	typeOpts := make([][]string, 0, len(accessCodeTypes))
	for _, typ := range accessCodeTypes {
		typeOpts = append(typeOpts, []string{typ, t("access_page.type." + typ)})
	}
	return &accessData{
		Codes: codes, Preview: preview, PreviewExternalHost: extHost, PreviewEmpty: previewEmpty,
		HasLock: hasLock, CanAdd: len(codes) < 3, TypeOptions: typeOpts,
	}, nil
}

func accessOpenForm(r *http.Request, codes []accessCode) *accessForm {
	if guideQueryValue(r, "add") == "1" && len(codes) < 3 {
		return &accessForm{Open: true, IsNew: true, Errors: map[string]string{}}
	}
	raw := guideQueryValue(r, "edit")
	if raw == "" {
		return nil
	}
	pos, err := strconv.Atoi(raw)
	if err != nil || pos < 1 || pos > 3 {
		return nil
	}
	for _, c := range codes {
		if c.Position == pos {
			return &accessForm{Open: true, Position: pos, CodeType: c.Type, CustomLabel: c.Label, ValidUntil: c.ValidUntilISO, Errors: map[string]string{}}
		}
	}
	return &accessForm{Open: true, Position: pos, IsNew: true, Errors: map[string]string{}}
}

func (s *guideServer) accessPage(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	base := "/apartments/" + strconv.FormatInt(a.ID, 10) + "/access"
	data, err := s.accessLoad(r.Context(), a.ID, q.lang, q.at)
	if err != nil {
		guideFail(w, err)
		return
	}
	data.Apartment = a
	data.Base = base
	data.GuideBase = "/apartments/" + strconv.FormatInt(a.ID, 10) + "/guide"
	data.Form = accessOpenForm(r, data.Codes)
	t := func(key string) string { return guideCatalog.T(q.lang, key, nil) }
	page := layout.Page{
		Title:    t("access_page.title") + " · " + a.InternalName + " · UbyHost",
		BodyKind: "form", V2: true, BackURL: "/apartments/" + strconv.FormatInt(a.ID, 10),
	}
	s.render(w, q, "access", page, http.StatusOK, data)
}

func accessErrKey(field string) string {
	return "flash.error.access_page." + field
}

func accessValidate(form *accessForm, code string, at time.Time, loc *time.Location) {
	today := accessToday(at, loc)
	form.Errors = map[string]string{}
	typ := form.CodeType
	okType := false
	for _, t := range accessCodeTypes {
		if t == typ {
			okType = true
			break
		}
	}
	if !okType {
		form.Errors["code_type"] = accessErrKey("type")
	}
	label := strings.TrimSpace(form.CustomLabel)
	if typ == "other" {
		if label == "" {
			form.Errors["custom_label"] = accessErrKey("other_label")
		} else if len([]rune(label)) > 60 {
			form.Errors["custom_label"] = accessErrKey("other_label")
		}
	}
	if code == "" || !accessCodeRe.MatchString(code) {
		form.Errors["code"] = accessErrKey("code")
	}
	until := strings.TrimSpace(form.ValidUntil)
	if until != "" {
		if _, err := time.ParseInLocation("2006-01-02", until, loc); err != nil {
			form.Errors["valid_until"] = accessErrKey("valid_until")
		} else if until < today {
			form.Errors["valid_until"] = accessErrKey("valid_until")
		}
	} else {
		until = ""
	}
	form.ValidUntil = until
}

func (s *guideServer) accessLowestFree(ctx context.Context, apt int64) (int, error) {
	var used [4]bool
	rows, err := s.pool.Query(ctx, `SELECT position FROM apartment_entry_code WHERE apartment_id = $1`, apt)
	if err != nil {
		return 0, err
	}
	defer rows.Close()
	n := 0
	for rows.Next() {
		var p int
		if err := rows.Scan(&p); err != nil {
			return 0, err
		}
		if p >= 1 && p <= 3 {
			used[p] = true
		}
		n++
	}
	if n >= 3 {
		return 0, nil
	}
	for i := 1; i <= 3; i++ {
		if !used[i] {
			return i, rows.Err()
		}
	}
	return 0, rows.Err()
}

func (s *guideServer) accessSave(ctx context.Context, q *guideReq, a *guideApartment, form *accessForm, code string) (bool, error) {
	keys, err := s.accessKeys()
	if err != nil {
		return false, err
	}
	enc, err := keys.EncryptField(code)
	if err != nil {
		return false, err
	}
	pos := form.Position
	existed := false
	if pos < 1 || pos > 3 {
		pos, err = s.accessLowestFree(ctx, a.ID)
		if err != nil || pos == 0 {
			return false, fmt.Errorf("limit")
		}
		form.IsNew = true
	} else {
		var n int
		err = s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id = $1 AND position = $2`, a.ID, pos).Scan(&n)
		if err != nil {
			return false, err
		}
		existed = n > 0
	}
	var label *string
	if form.CodeType == "other" {
		l := strings.TrimSpace(form.CustomLabel)
		label = &l
	}
	until := form.ValidUntil
	var untilVal any
	if until == "" {
		untilVal = nil
	} else {
		untilVal = until
	}
	stamp := guideStamp(q.at)
	_, err = s.pool.Exec(ctx, `INSERT INTO apartment_entry_code (apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
ON CONFLICT (apartment_id, position) DO UPDATE SET code_type = $3, custom_label = $4, code_enc = $5, valid_until = $6, updated_at = $7`,
		a.ID, pos, form.CodeType, label, enc, untilVal, stamp)
	if err != nil {
		return false, err
	}
	detail := fmt.Sprintf("apartment=%d position=%d type=%s", a.ID, pos, form.CodeType)
	if err := s.audit(ctx, q, "entry_code_set", detail); err != nil {
		return false, err
	}
	return existed, nil
}

func (s *guideServer) accessClear(ctx context.Context, q *guideReq, apt int64, pos int) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx) //nolint:errcheck
	var typ string
	err = tx.QueryRow(ctx, `DELETE FROM apartment_entry_code WHERE apartment_id = $1 AND position = $2 RETURNING code_type`, apt, pos).Scan(&typ)
	if errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	if err != nil {
		return err
	}
	// UNIQUE (apartment_id, position) is immediate. A single
	// SET position = position - 1 on two remaining rows can collide
	// (3->2 while 2 still exists). Shift lowest-first into the hole.
	for next := pos + 1; next <= 3; next++ {
		if _, err := tx.Exec(ctx, `UPDATE apartment_entry_code SET position = $3 WHERE apartment_id = $1 AND position = $2`, apt, next, next-1); err != nil {
			return err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return err
	}
	detail := fmt.Sprintf("apartment=%d position=%d type=%s", apt, pos, typ)
	return s.audit(ctx, q, "entry_code_cleared", detail)
}

func (s *guideServer) accessPost(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	page := "/apartments/" + strconv.FormatInt(a.ID, 10) + "/access"
	action, _ := guideFormValue(r, "action")
	switch action {
	case "clear":
		raw, ok := guideFormValue(r, "position")
		if !ok {
			q.back(w, page, hostweb.Flash{}, hostweb.Flash{})
			return
		}
		pos, _ := strconv.Atoi(raw)
		if err := s.accessClear(r.Context(), q, a.ID, pos); err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				q.back(w, page, hostweb.Flash{}, hostweb.Flash{})
				return
			}
			guideFail(w, err)
			return
		}
		q.back(w, page, q.flash("flash.access_page.cleared", nil), hostweb.Flash{})
		return
	case "save":
		form := &accessForm{Errors: map[string]string{}}
		if raw, ok := guideFormValue(r, "position"); ok && raw != "" {
			form.Position, _ = strconv.Atoi(raw)
		}
		form.CodeType, _ = guideFormValue(r, "code_type")
		form.CustomLabel, _ = guideFormValue(r, "custom_label")
		form.ValidUntil, _ = guideFormValue(r, "valid_until")
		code, _ := guideFormValue(r, "code")
		loc := q.at.Location()
		accessValidate(form, code, q.at, loc)
		if len(form.Errors) > 0 {
			back := page + "?add=1#entry-codes"
			if form.Position >= 1 {
				back = fmt.Sprintf("%s?edit=%d#entry-codes", page, form.Position)
			}
			var errKey string
			for _, k := range []string{"code_type", "custom_label", "code", "valid_until"} {
				if key, ok := form.Errors[k]; ok {
					errKey = key
					break
				}
			}
			q.back(w, back, hostweb.Flash{}, q.flash(errKey, nil))
			return
		}
		var n int64
		if err := s.pool.QueryRow(r.Context(), `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id = $1`, a.ID).Scan(&n); err != nil {
			guideFail(w, err)
			return
		}
		if form.Position < 1 && n >= 3 {
			q.back(w, page+"?add=1#entry-codes", hostweb.Flash{}, q.flash("flash.error.access_page.limit", nil))
			return
		}
		replaced, err := s.accessSave(r.Context(), q, a, form, code)
		if err != nil {
			if err.Error() == "limit" {
				q.back(w, page, hostweb.Flash{}, q.flash("flash.error.access_page.limit", nil))
				return
			}
			guideFail(w, err)
			return
		}
		key := "flash.access_page.saved"
		if replaced {
			key = "flash.access_page.replaced"
		}
		q.back(w, page+"#entry-codes", q.flash(key, nil), hostweb.Flash{})
		return
	default:
		q.back(w, page, hostweb.Flash{}, hostweb.Flash{})
	}
}
