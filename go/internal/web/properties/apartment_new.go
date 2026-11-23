package properties

// GET /apartments/new (brief 1700a): routes/admin.py apartment_new and
// _render_apartment_new, the short Add property page. The body is the Go twin
// of apartment_form.html (create branch) with _property_create.html,
// _copy_settings_dialog.html, _property_identity_fields.html,
// _property_operator.html and _property_address_fields.html, drawn in the host
// layout (hostweb/layout). The page strings are their own catalog
// (apartmentnew/i18n.json, written by App/scripts/go_host_i18n.py).
//
// RenderApartmentNew is the one renderer of the form. Brief 1700b (POST
// /apartments) calls it again for a refused create with the typed values and
// the errors. Nothing routes here until the owner adds the path to
// UBYHOST_GO_PATHS. The RUIAN suggest script and its data attributes stay as
// Python writes them; /apartments/ruian-suggest is brief 1700c.

import (
	"context"
	"embed"
	"errors"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed apartmentnew/apartment_new.tmpl
var apartmentNewFiles embed.FS

//go:embed apartmentnew/i18n.json
var apartmentNewJSON []byte

// apartmentNewStrings is the page catalog, written from host_i18n.py by
// App/scripts/go_host_i18n.py from apartmentnew/i18n_keys.txt.
var apartmentNewStrings = hostweb.Load(apartmentNewJSON)

// apartmentNewTemplates is parsed once; the layout clones it per request.
var apartmentNewTemplates = layout.MustParse(apartmentNewStrings, apartmentNewFiles, "apartmentnew/apartment_new.tmpl")

// ApartmentNewOption is one operator (legal entity) or one property in a select.
type ApartmentNewOption struct {
	ID   int64
	Name string
}

// ApartmentNewForm is what the page shows: the context of _render_apartment_new.
// A GET fills the copy fields from the query; 1700b fills Draft, the errors and
// Status from a refused POST. A zero ID means "none" (Python's None or 0).
type ApartmentNewForm struct {
	Entities         []ApartmentNewOption // access.entities: the host's live operators, by name
	Peers            []ApartmentNewOption // copy_property_peers: the host's live properties, by name
	SelectedEntityID int64                // selected_entity_id
	CopyFromID       int64                // copy_from_id
	CopiedFromName   string               // copied_from_name; "" shows no notice and no hidden copy fields
	CopyOpen         bool                 // ?copy=choose opens the dialog
	// Prefill is property_prefill without the two entity ids: only keys that
	// are present are written as hidden fields. A GET holds the non-empty
	// copied values; a refusal holds every submitted key, even an empty one.
	Prefill             map[string]string
	PrefillEntityID     int64
	PrefillControllerID int64
	// Draft is what the host typed (internal_name, city_en, addr_*); empty on a GET.
	Draft             map[string]string
	DraftEntityID     int64
	DraftControllerID int64
	OperatorError     string            // an i18n key, or "" (apartment.form.operator.* or flash.error.no_such_controller)
	NameError         bool              // a create refused for a blank name
	AddressErrors     map[string]string // field name -> the message text, already in the host's language
	Status            int               // 0 is 200; 1700b sends 400 for a refusal
}

type apartmentNewAddr struct {
	Name, LabelKey, HintKey     string
	Optional, Required, Suggest bool
	MaxLength                   int
	InputMode, Autocap          string
	Placeholder, Value, Error   string
	Described                   string
}

type apartmentNewHidden struct{ Name, Value string }

type apartmentNewView struct {
	ApartmentNewForm
	TitleHead, TitleLast string
	DefaultPurpose       string
	Hidden               []apartmentNewHidden
	OperatorSelected     int64
	OperatorErr          string
	ControllerCurrent    int64
	ControllerErr        bool
	AddrRow1, AddrRow2   []apartmentNewAddr
}

// The hidden fields a copy carries, in the order of _property_create.html.
var (
	apartmentNewHiddenAutomation = []string{"automation_mode", "submit_after_hours", "permalink_window_days", "permalink_reachback_days"}
	apartmentNewHiddenFee        = []string{"stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_authority_name", "stay_fee_authority_address",
		"stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction", "stay_fee_council_account"}
)

func (f ApartmentNewForm) view(title string) apartmentNewView {
	v := apartmentNewView{ApartmentNewForm: f, TitleLast: title}
	// (t('property_create.title')).rsplit(' ', 1)
	if i := strings.LastIndex(title, " "); i >= 0 {
		v.TitleHead, v.TitleLast = title[:i], title[i+1:]
	}
	if v.DefaultPurpose = f.Prefill["default_purpose"]; v.DefaultPurpose == "" {
		v.DefaultPurpose = "10"
	}
	for _, key := range apartmentNewHiddenAutomation {
		if val, ok := f.Prefill[key]; ok {
			v.Hidden = append(v.Hidden, apartmentNewHidden{key, val})
		}
	}
	if f.Prefill["stay_fee_rate_czk"] != "" {
		for _, key := range apartmentNewHiddenFee {
			if val, ok := f.Prefill[key]; ok {
				v.Hidden = append(v.Hidden, apartmentNewHidden{key, val})
			}
		}
	}
	// _property_operator.html: the stored, submitted or copied id when it is
	// one of the host's operators, else the only operator, else none.
	current := f.DraftEntityID
	if current == 0 {
		current = f.SelectedEntityID
	}
	if current == 0 {
		current = f.PrefillEntityID
	}
	for _, e := range f.Entities {
		if e.ID == current {
			v.OperatorSelected = current
		}
	}
	if v.OperatorSelected == 0 && len(f.Entities) == 1 {
		v.OperatorSelected = f.Entities[0].ID
	}
	if strings.HasPrefix(f.OperatorError, "apartment.form.operator.") {
		v.OperatorErr = f.OperatorError
	}
	v.ControllerErr = f.OperatorError == "flash.error.no_such_controller"
	if v.ControllerCurrent = f.DraftControllerID; v.ControllerCurrent == 0 {
		v.ControllerCurrent = f.PrefillControllerID
	}
	addr := func(a apartmentNewAddr) apartmentNewAddr {
		a.Value = f.Draft[a.Name]
		a.Error = f.AddressErrors[a.Name]
		var described []string
		if a.HintKey != "" {
			described = append(described, a.Name+"-help")
		}
		if a.Error != "" {
			described = append(described, a.Name+"-error")
		}
		a.Described = strings.Join(described, " ")
		return a
	}
	k := "apartment.form.addr."
	v.AddrRow1 = []apartmentNewAddr{
		addr(apartmentNewAddr{Name: "addr_street", LabelKey: k + "street", HintKey: k + "street_hint", MaxLength: 48, Required: true, Suggest: true, Autocap: "words", Placeholder: "Vinohradská"}),
		addr(apartmentNewAddr{Name: "addr_house_no", LabelKey: k + "house_no", HintKey: k + "house_no_hint", MaxLength: 5, Required: true, Placeholder: "12"}),
		addr(apartmentNewAddr{Name: "addr_orient_no", LabelKey: k + "orient_no", HintKey: k + "orient_no_hint", Optional: true, MaxLength: 4, Placeholder: "5"}),
		addr(apartmentNewAddr{Name: "addr_zip", LabelKey: k + "zip", HintKey: k + "zip_hint", MaxLength: 6, InputMode: "numeric", Required: true, Placeholder: "12000"}),
	}
	v.AddrRow2 = []apartmentNewAddr{
		addr(apartmentNewAddr{Name: "addr_obec", LabelKey: k + "obec", MaxLength: 48, Required: true, Autocap: "words", Placeholder: "Praha"}),
		addr(apartmentNewAddr{Name: "addr_obec_cast", LabelKey: k + "obec_cast", Optional: true, MaxLength: 48, Autocap: "words", Placeholder: "Vinohrady"}),
		addr(apartmentNewAddr{Name: "addr_okres", LabelKey: k + "okres", HintKey: k + "okres_hint", Optional: true, MaxLength: 32, Autocap: "words", Placeholder: "Praha"}),
	}
	return v
}

// RenderApartmentNew draws the new-property form for form in the host layout.
// It writes the response (status form.Status, 200 when 0); an error means
// nothing was written.
func RenderApartmentNew(w http.ResponseWriter, r *http.Request, env layout.Env, host *session.Host, form ApartmentNewForm) error {
	title := apartmentNewStrings.T(hostweb.Lang(r), "property_create.title", nil)
	page := layout.Page{Title: title, Nav: "apartments", BodyKind: "form", V2: true, HowKey: "property", BackURL: "/apartments", Status: form.Status}
	return layout.Render(w, r, env, host, page, apartmentNewTemplates, "apartmentnew", form.view(title))
}

// RegisterApartmentNew adds GET /apartments/new. It only builds the handler;
// the pool is first used inside a request.
func RegisterApartmentNew(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &Pages{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /apartments/new", wrap("/apartments/new", s.apartmentNew))
}

const (
	apartmentNewEntitiesSQL = `SELECT id, name FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY name`
	apartmentNewPeersSQL    = `SELECT id, COALESCE(internal_name, '') FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY internal_name`
	apartmentNewSourceSQL   = `SELECT COALESCE(internal_name, ''), legal_entity_id, data_controller_entity_id, automation_mode, submit_after_hours,
  default_purpose, permalink_window_days, permalink_reachback_days, stay_fee_rate_czk, stay_fee_cadence, stay_fee_authority_name,
  stay_fee_authority_address, stay_fee_authority_contact, stay_fee_payee, stay_fee_instruction, stay_fee_council_account
FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
)

func apartmentNewOptions(ctx context.Context, pool *pgxpool.Pool, sql string, workspace int64) ([]ApartmentNewOption, error) {
	rows, err := pool.Query(ctx, sql, workspace)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, func(row pgx.CollectableRow) (ApartmentNewOption, error) {
		var o ApartmentNewOption
		err := row.Scan(&o.ID, &o.Name)
		return o, err
	})
}

// loadApartmentNewChoices reads the two lists of the form for a workspace:
// access.entities and access.apartments. 1700b uses it for a refusal.
func loadApartmentNewChoices(ctx context.Context, pool *pgxpool.Pool, workspace int64) (entities, peers []ApartmentNewOption, err error) {
	if entities, err = apartmentNewOptions(ctx, pool, apartmentNewEntitiesSQL, workspace); err != nil {
		return nil, nil, err
	}
	if peers, err = apartmentNewOptions(ctx, pool, apartmentNewPeersSQL, workspace); err != nil {
		return nil, nil, err
	}
	return entities, peers, nil
}

var apartmentNewIntRE = regexp.MustCompile(`^[+-]?[0-9]+(?:_[0-9]+)*$`)

// apartmentNewQueryInt is admin_helpers.query_int: the stripped last value of
// the key as an int, 0 for none or a value int() rejects. ok is false for a
// value this port does not judge (a non-ASCII digit string, or one past 64
// bits); the caller then answers 501 with the Caddy fallback header.
func apartmentNewQueryInt(r *http.Request, key string) (n int64, ok bool) {
	raw := pyStrip(queryLast(r, key))
	if raw == "" {
		return 0, true
	}
	for _, c := range raw {
		if c > unicode.MaxASCII {
			return 0, false
		}
	}
	if !apartmentNewIntRE.MatchString(raw) {
		return 0, true
	}
	n, err := strconv.ParseInt(strings.ReplaceAll(raw, "_", ""), 10, 64)
	if err != nil {
		return 0, false
	}
	return n, true
}

// apartmentNewSource is _property_copy_values of access.apartment(copy_from):
// the 15 copy keys without the empty ones (0, NULL or blank text).
func apartmentNewSource(ctx context.Context, pool *pgxpool.Pool, workspace, id int64, form *ApartmentNewForm) (found bool, err error) {
	var name string
	var legal, controller, submit, window, reach, rate *int64
	var mode, purpose, cadence, authName, authAddress, authContact, payee, instruction, account *string
	err = pool.QueryRow(ctx, apartmentNewSourceSQL, id, workspace).Scan(&name, &legal, &controller, &mode, &submit, &purpose, &window, &reach,
		&rate, &cadence, &authName, &authAddress, &authContact, &payee, &instruction, &account)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	prefill := map[string]string{}
	text := func(key string, v *string) {
		if v != nil && pyStrip(*v) != "" {
			prefill[key] = *v
		}
	}
	number := func(key string, v *int64) {
		if v != nil && *v != 0 {
			prefill[key] = strconv.FormatInt(*v, 10)
		}
	}
	text("automation_mode", mode)
	number("submit_after_hours", submit)
	text("default_purpose", purpose)
	number("permalink_window_days", window)
	number("permalink_reachback_days", reach)
	number("stay_fee_rate_czk", rate)
	text("stay_fee_cadence", cadence)
	text("stay_fee_authority_name", authName)
	text("stay_fee_authority_address", authAddress)
	text("stay_fee_authority_contact", authContact)
	text("stay_fee_payee", payee)
	text("stay_fee_instruction", instruction)
	text("stay_fee_council_account", account)
	form.CopiedFromName = name
	form.Prefill = prefill
	if legal != nil {
		form.PrefillEntityID = *legal
	}
	if controller != nil {
		form.PrefillControllerID = *controller
	}
	return true, nil
}

func (s *Pages) apartmentNew(w http.ResponseWriter, r *http.Request) {
	now := s.now()
	host, err := hostweb.Login(w, r, s.pool, s.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	selected, ok1 := apartmentNewQueryInt(r, "legal_entity_id")
	copyID, ok2 := apartmentNewQueryInt(r, "copy_from")
	if !ok1 || !ok2 {
		hostweb.NotFoundPage(w, r)
		return
	}
	ctx := r.Context()
	ws := host.Workspace.ID
	form := ApartmentNewForm{CopyFromID: copyID, CopyOpen: queryLast(r, "copy") == "choose", Prefill: map[string]string{}}
	if form.Entities, form.Peers, err = loadApartmentNewChoices(ctx, s.pool, ws); err != nil {
		fail(w, err)
		return
	}
	for _, e := range form.Entities {
		if e.ID == selected {
			form.SelectedEntityID = selected
		}
	}
	if copyID != 0 {
		found, err := apartmentNewSource(ctx, s.pool, ws, copyID, &form)
		if err != nil {
			fail(w, err)
			return
		}
		if !found {
			hostweb.NotFoundPage(w, r)
			return
		}
	}
	if form.SelectedEntityID == 0 {
		form.SelectedEntityID = form.PrefillEntityID
	}
	if err := RenderApartmentNew(w, r, layout.Env{Pool: s.pool, Getenv: s.getenv, Now: now}, host, form); err != nil {
		fail(w, err)
	}
}
