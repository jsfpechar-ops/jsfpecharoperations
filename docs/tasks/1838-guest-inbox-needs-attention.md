# 1838: Guest inbox under "needs attention": attach a held submission to a stay or dismiss it, deadline shown

Status: todo
Depends on: 1834, 1837 | Base commit: current tip of the working branch | Branch: task/1838-guest-inbox-needs-attention
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (guest data and filing deadline shown to host; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 3 rule 4, section 7 ("any `held` row" alert).

> **One PR mode, draft.** Commit each step as `1838 step k`. Never push to `main`, merge or deploy. The page ships dormant (not in `UBYHOST_GO_PATHS`) and stays a draft until 1838b (UX gate) is green.

## Open questions (orchestrator answers before execute)

Step 0 stops until each line below carries `Answer:`.

1. **Deadline anchor.** The filing code computes the deadline from a check-in date, never from a submission time: `ubyport.ReportingDeadline(checkIn)` (`go/internal/ubyport/collect.go` line 377), anchored on the earliest guest `stay_from`, else the stay's `date_from` (`reservationDeadlineAnchor`, same file). A `held` row may have no live stay, and the payload (brief 1835 `GuestForm`) has no stay dates. Recommended: anchor = the earlier of the row's live stay `date_from` and the Prague date of `received_at` (plan rule 2), passed to `ubyport.ReportingDeadline`. Never later than the real deadline; at worst early. Answer:
   Answer (orchestrator, 2026-11-17): the recommendation; display only, filing keeps `ubyport.ReportingDeadline` unchanged.
2. **Owner scope when the stay and the link are both gone.** `guest_inbox` has no `apartment_id` (1834 contract surface). The property comes from the live stay (`reservation_id`), else the link's `guest_form_snapshot.apartment_id`. If 1836 deletes the snapshot row of a revoked link, a `held` row of that link is invisible to every host and its alert never clears. Recommended: 1836 keeps a snapshot row while any `held` inbox row names its `token_hash` (no schema change). Alternative: migration `00021` adds `guest_inbox.apartment_id` (then this brief is revised). Answer:
   Answer: the recommendation; 1836 keeps snapshot rows while a held row names them (orchestrator adds this to 1836).
3. **Dismiss marker.** `status` allows only `new/done/held` (1834). Recommended, no migration: dismiss sets `status = 'done'`, `host_note = 'dismissed'`, `processed_at = now`, no guest rows; plan rule 7 deletes the payload 7 days later. Alternative: a `dismissed` status (new migration, 1834 check change). Answer: recommended, fixed by brief 1839 (retention): dismissed ends `done` with `processed_at` set and `host_note = 'dismissed'`, no new status, no schema change, so the 7-day payload purge applies; an attached row goes back to `new` with `reservation_id` set and the 1837 worker sets `done` and `processed_at`.
   Answer: as recommended (matches 1839).
4. **Contract with 1837 (write it into 1837).** (a) The worker reads the stay from the `reservation_id` column, not from the payload's `ReservationID`, so an attach takes effect. (b) A `done` row's `host_note` is one of `already_registered`, `over_count` (this page shows `guest_inbox.note.<value>`). (c) An attached row is `new` with `attempts = 0`, `processed_at = NULL`, `host_note = NULL`. Answer:
   Answer: yes; sent to the 1837 writer.
5. **UX gate for a Go-only page.** `App/tests/test_layout_lint_browser.py` and the geometry tests browse the Python app; `/guest-inbox` exists only in `ubyhost-web` (Caddy sends it to Go only when `UBYHOST_GO_PATHS` lists it). Open brief `1668-go-pages-layout-lint-harness.md` adds a Go-page harness; it is not merged. Recommended (1838b depends on 1668): this brief builds the page dormant with Go tests; **1838b** runs the UX gate against `ubyhost-web` (layout lint 0 findings, 0 skipped, 390/768/1280 screenshots, design-system checklist) and only then the owner switches the path on. Answer:
   Answer: yes; 1838b written later, depends on 1668.
6. **Where the host finds it.** The host dashboard `/` ("What needs you", `App/app/routes/admin.py` `dashboard`) is Python; go-first allows no Python feature change. Recommended: the `held` alert (1837/1848) links to `/guest-inbox`; a dashboard link waits for the dashboard port. Answer:
   Answer: yes; the held-row alert links to `/guest-inbox` until the dashboard is ported.

## 1. Objective

Add the Go page `/guest-inbox`: `held` guest submissions (who, property, received, file-by deadline) with "Attach" to one of the host's stays of that property or "Dismiss", plus `done` rows that carry a note for the host. Without it a `held` registration is never filed (plan rule 4), so the deadline must be on screen.

## 2. Context

Rules (AGENTS.md): 6 light mode, forms work without JavaScript; 7/10 UX gate (here: 1838b, Q5); 9 no sentence the button already says, "no tracking cookies"; 11 Go first ([go-first](../context/go-first.md): new feature, Go only; this brief changes no file under `App/app/`). Every query scoped by `apartment.owner_user_id` = the workspace id (Python: `access.owner_id`, `db.null_safe_eq('a.owner_user_id')`; Go: `h.Workspace.ID`).

Contract (1834, verbatim): `guest_inbox`: `id`, `idempotency_key`, `token_hash`, `reservation_id`, `contract_version`, `received_at`, `payload_enc`, `status` (`new`/`done`/`held`), `host_note`, `attempts`, `processed_at`. `reservation_id` has no foreign key. `payload_enc` may be NULL only when `done`. Timestamps `TIMESTAMPTZ`.

**Anchors** (Step 0 checks each; if one is missing or differs, STOP and report what you found):

| # | Command | Expected (verbatim in output) |
|---|---|---|
| A1 | `grep -n 'func ReportingDeadline' go/internal/ubyport/collect.go` | `func ReportingDeadline(checkIn time.Time) time.Time {` |
| A2 | `grep -n 'func LocalNow\|func ParseISODate' go/internal/deadlines/deadlines.go go/internal/validation/*.go` | `func LocalNow(now time.Time) time.Time {` and `func ParseISODate(` returning `(time.Time, bool)` |
| A3 | `grep -n 'func Login\|func CSRF' go/internal/hostweb/gate.go` | `func Login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (*session.Host, error) {` and `func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at time.Time) bool {` |
| A4 | `sed -n 150,157p go/internal/hostweb/gate.go` | the comment says that on `false` the response is already written |
| A5 | `grep -n 'func Back\|func Lang\|func Load' go/internal/hostweb/*.go` | `func Back(w http.ResponseWriter, r *http.Request, path string, msg, err Flash) {`, `func Lang(r *http.Request) string {`, a `func Load(` returning `Catalog` |
| A6 | `grep -n 'func MustParse\|func Render' go/internal/hostweb/layout/layout.go` | `func MustParse(cat hostweb.Catalog, fsys fs.FS, patterns ...string) *Templates {` and `func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, p Page, tpl *Templates, name string, data any) error {` |
| A7 | `grep -n 'layout.Render(\|{{define' go/internal/web/stayfees/page_*.go go/internal/web/stayfees/pagetemplates/stay_fees.tmpl` | `Render` is called with the template's `define` name, and `stay_fees.tmpl` uses `{{csrf}}`/`{{t "..."}}` (same as `stay_fee_detail.tmpl` line 7: `<input type="hidden" name="_csrf" value="{{csrf}}">`) |
| A8 | `grep -n 'type Account struct' -A3 go/internal/session/session.go` | an `ID int64` field |
| A9 | `grep -n '^func ' go/internal/secure/datakeys.go go/internal/guestcontract/payload.go` | `func LoadDataKeys(getenv func(string) string) (*MultiFernet, error)` and `func DecodeSubmission(keys *secure.MultiFernet, enc []byte) (Submission, error)` (brief 1835). Different name or signature: STOP, report both lines. |
| A10 | `grep -n 'func registerRoutes' go/cmd/ubyhost-web/*.go` | `func registerRoutes(f func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool))` (used by `register_web_stayfees.go`) |
| A11 | `grep -n 'CREATE TABLE public.apartment (' -A12 App/migrations_pg/00001_baseline.sql \| grep -n 'name text\|owner_user_id'` and `grep -n 'CREATE TABLE public.reservation (' -A40 App/migrations_pg/00001_baseline.sql \| grep -n 'archived_at\|summary'` | `name text`, `owner_user_id bigint`, `summary text`, `archived_at text` |
| A12 | `grep -n 'guest_inbox' App/migrations_pg/00020_guest_contract.sql \| head -3` | the table exists (1834 merged) |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guestinbox/inbox.go` | create | queries (owner-scoped), deadline, attach, dismiss |
| `go/internal/web/guestinbox/handlers.go` | create | routes, GET page, two POST actions |
| `go/internal/web/guestinbox/templates/guest_inbox.tmpl` | create | the page body, no JavaScript |
| `go/internal/web/guestinbox/i18n.json` | create | CS and EN copy |
| `go/internal/web/guestinbox/inbox_test.go` | create | deadline, scope, held-only, no-JS, catalog, routes |
| `go/cmd/ubyhost-web/register_web_guestinbox.go` | create | registers the dormant routes |

No other file may change. No file under `App/` changes (go-first: none of the three exceptions is needed).

## 4. Steps

### Step 0: stop check

Run: `grep -c '^.*Answer: .\+' docs/tasks/1838-guest-inbox-needs-attention.md`
Expected: `6`. Otherwise STOP (status `blocked`, reason "open questions"). Then run anchors A1 to A12 from §2 (one command per anchor is fine, or chain them with `;`). Expected: every line as in the table. Apply the answers: if answer 2 or 3 differs from the recommendation, STOP (the brief is revised first).

### Step 1: create `go/internal/web/guestinbox/inbox.go`

```go
// Package guestinbox serves /guest-inbox (brief 1838): the guest form
// submissions that need the host. A held row (plan guest-form-isolation,
// section 3 rule 4) is attached to a stay of its property or dismissed; a done
// row with a host note is shown for noteDays. Every query is scoped by the
// workspace owner (apartment.owner_user_id).
package guestinbox

import (
	"context"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// DismissedNote is the host_note of a held row the host dismissed: the row
// turns done with no guest rows, and retention deletes its payload 7 days later.
const DismissedNote = "dismissed"

// noteDays is how long a done row with a note stays on the page (the payload
// retention of plan section 3 rule 7).
const noteDays = 7

// Stay is a stay a held row can be attached to.
type Stay struct {
	ID                        int64
	DateFrom, DateTo, Summary string
}

// Row is one inbox row as the page shows it.
type Row struct {
	ID            int64
	Status        string
	ApartmentID   int64
	ApartmentName string
	ReceivedAt    time.Time
	StayFrom      string // date_from of the row's live stay, "" when none
	HostNote      string
	GuestName     string
	Deadline      time.Time
	Stays         []Stay
}

// ownerApartment is the property of an inbox row: the live stay's, else the link's.
const ownerApartment = `COALESCE(r.apartment_id, s.apartment_id)`

// rowJoins reach the property of inbox row i (alias r: live stay, s: link snapshot).
const rowJoins = `
  LEFT JOIN reservation r ON r.id = i.reservation_id AND r.archived_at IS NULL
  LEFT JOIN guest_form_snapshot s ON s.token_hash = i.token_hash
  JOIN apartment a ON a.id = ` + ownerApartment

const listSQL = `SELECT i.id, i.status, i.received_at, COALESCE(i.host_note, ''), i.payload_enc,
       a.id, a.name, COALESCE(r.date_from, '')
  FROM guest_inbox i` + rowJoins + `
 WHERE a.owner_user_id = $1
   AND (i.status = 'held'
        OR (i.status = 'done' AND i.host_note IS NOT NULL AND i.host_note <> '` + DismissedNote + `'
            AND i.processed_at > $2))
 ORDER BY i.status DESC, i.received_at`

const staysSQL = `SELECT r.id, r.date_from, r.date_to, COALESCE(r.summary, '')
  FROM reservation r JOIN apartment a ON a.id = r.apartment_id
 WHERE r.apartment_id = $1 AND a.owner_user_id = $2 AND r.archived_at IS NULL
   AND r.date_to >= $3
 ORDER BY r.date_from
 LIMIT 20`

const attachSQL = `UPDATE guest_inbox
   SET status = 'new', reservation_id = $2, host_note = NULL, attempts = 0, processed_at = NULL
 WHERE id = $1 AND status = 'held'
   AND EXISTS (SELECT 1 FROM reservation t JOIN apartment a ON a.id = t.apartment_id
                WHERE t.id = $2 AND t.archived_at IS NULL AND a.owner_user_id = $3
                  AND a.id = (SELECT ` + ownerApartment + ` FROM guest_inbox i
                               LEFT JOIN reservation r ON r.id = i.reservation_id AND r.archived_at IS NULL
                               LEFT JOIN guest_form_snapshot s ON s.token_hash = i.token_hash
                              WHERE i.id = $1))`

const dismissSQL = `UPDATE guest_inbox
   SET status = 'done', host_note = '` + DismissedNote + `', processed_at = $3
 WHERE id = $1 AND status = 'held'
   AND EXISTS (SELECT 1 FROM guest_inbox i` + rowJoins + `
                WHERE i.id = $1 AND a.owner_user_id = $2)`

// Deadline is the filing deadline shown for a row: ubyport.ReportingDeadline,
// the one the filing code uses, from the earlier of the live stay's date_from
// and the Prague date of received_at (brief 1838, open question 1).
func Deadline(stayFrom string, receivedAt time.Time) time.Time {
	l := deadlines.LocalNow(receivedAt)
	anchor := time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
	if d, ok := validation.ParseISODate(stayFrom); ok && d.Before(anchor) {
		anchor = d
	}
	return ubyport.ReportingDeadline(anchor)
}

// Load returns the owner's rows, held first. name turns a payload into the
// guest's name ("" when it cannot be read).
func Load(ctx context.Context, pool *pgxpool.Pool, owner int64, now time.Time, name func([]byte) string) ([]Row, error) {
	rows, err := pool.Query(ctx, listSQL, owner, now.Add(-noteDays*24*time.Hour))
	if err != nil {
		return nil, err
	}
	var out []Row
	for rows.Next() {
		var row Row
		var enc []byte
		if err := rows.Scan(&row.ID, &row.Status, &row.ReceivedAt, &row.HostNote, &enc,
			&row.ApartmentID, &row.ApartmentName, &row.StayFrom); err != nil {
			rows.Close()
			return nil, err
		}
		row.GuestName = strings.TrimSpace(name(enc))
		row.Deadline = Deadline(row.StayFrom, row.ReceivedAt)
		out = append(out, row)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for i := range out {
		if out[i].Status != "held" {
			continue
		}
		from := deadlines.LocalNow(out[i].ReceivedAt).AddDate(0, 0, -14).Format("2006-01-02")
		stays, err := pool.Query(ctx, staysSQL, out[i].ApartmentID, owner, from)
		if err != nil {
			return nil, err
		}
		for stays.Next() {
			var s Stay
			if err := stays.Scan(&s.ID, &s.DateFrom, &s.DateTo, &s.Summary); err != nil {
				stays.Close()
				return nil, err
			}
			out[i].Stays = append(out[i].Stays, s)
		}
		stays.Close()
		if err := stays.Err(); err != nil {
			return nil, err
		}
	}
	return out, nil
}

// Attach puts held row id back to new on stay, so the inbox worker (brief
// 1837) processes it. False when the row is not held, or the stay is not a
// live stay of the same property of this owner.
func Attach(ctx context.Context, pool *pgxpool.Pool, owner, id, stay int64) (bool, error) {
	tag, err := pool.Exec(ctx, attachSQL, id, stay, owner)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// Dismiss closes held row id without guest rows. False when it is not a held
// row of this owner.
func Dismiss(ctx context.Context, pool *pgxpool.Pool, owner, id int64, now time.Time) (bool, error) {
	tag, err := pool.Exec(ctx, dismissSQL, id, owner, now)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}
```

Run: `cd go && gofmt -l internal/web/guestinbox 2>&1 | head -5`
Expected: no output.

### Step 2: create `go/internal/web/guestinbox/handlers.go`

```go
package guestinbox

import (
	"embed"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Path is the page. Dormant until the owner adds "/guest-inbox /guest-inbox/*"
// to UBYHOST_GO_PATHS (after brief 1838b).
const Path = "/guest-inbox"

//go:embed i18n.json
var catalogJSON []byte

var catalog = hostweb.Load(catalogJSON)

//go:embed templates/*.tmpl
var files embed.FS

var tpl = layout.MustParse(catalog, files, "templates/*.tmpl")

// Route is one pattern and its handler.
type Route struct {
	Pattern string
	Handler http.Handler
}

// Routes are the page and its two actions.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return []Route{
		{"GET " + Path, page(pool, getenv, now)},
		{"POST " + Path + "/{id}/attach", act(pool, getenv, now, true)},
		{"POST " + Path + "/{id}/dismiss", act(pool, getenv, now, false)},
	}
}

type stayOption struct {
	ID    int64
	Label string
}

type item struct {
	ID                                             int64
	GuestName, ApartmentName, Received, Deadline, Note string
	Stays                                          []stayOption
}

type view struct {
	Held, Notes []item
}

func when(t time.Time) string { return deadlines.LocalNow(t).Format("2. 1. 2006 15:04") }

func build(rows []Row, lang string) view {
	var v view
	for _, r := range rows {
		it := item{ID: r.ID, GuestName: r.GuestName, ApartmentName: r.ApartmentName,
			Received: when(r.ReceivedAt), Deadline: when(r.Deadline)}
		if r.Status != "held" {
			it.Note = catalog.T(lang, "guest_inbox.note."+r.HostNote, nil)
			v.Notes = append(v.Notes, it)
			continue
		}
		for _, s := range r.Stays {
			label := s.DateFrom + " – " + s.DateTo
			if s.Summary != "" {
				label += " · " + s.Summary
			}
			it.Stays = append(it.Stays, stayOption{ID: s.ID, Label: label})
		}
		v.Held = append(v.Held, it)
	}
	return v
}

func fail(w http.ResponseWriter) {
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func page(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			fail(w)
			return
		}
		if h == nil {
			return
		}
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			fail(w)
			return
		}
		name := func(enc []byte) string {
			if len(enc) == 0 {
				return ""
			}
			sub, err := guestcontract.DecodeSubmission(keys, enc)
			if err != nil {
				return ""
			}
			return sub.Guest.Surname + " " + sub.Guest.FirstName
		}
		rows, err := Load(r.Context(), pool, h.Workspace.ID, at, name)
		if err != nil {
			fail(w)
			return
		}
		lang := hostweb.Lang(r)
		p := layout.Page{Title: catalog.T(lang, "guest_inbox.title", nil), Nav: "dashboard", BodyKind: "list"}
		env := layout.Env{Pool: pool, Getenv: getenv, Now: at}
		if err := layout.Render(w, r, env, h, p, tpl, "guest_inbox", build(rows, lang)); err != nil {
			fail(w)
		}
	})
}

func act(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, attach bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			fail(w)
			return
		}
		if h == nil || !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		lang := hostweb.Lang(r)
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		ok, done := false, "guest_inbox.dismissed"
		if err == nil && attach {
			done = "guest_inbox.attached"
			stay, perr := strconv.ParseInt(r.FormValue("reservation_id"), 10, 64)
			if perr == nil {
				ok, err = Attach(r.Context(), pool, h.Workspace.ID, id, stay)
			}
		} else if err == nil {
			ok, err = Dismiss(r.Context(), pool, h.Workspace.ID, id, at)
		}
		if err != nil {
			fail(w)
			return
		}
		if !ok {
			hostweb.Back(w, r, Path, hostweb.Flash{}, hostweb.Flash{Text: catalog.T(lang, "guest_inbox.gone", nil), Key: "guest_inbox.gone"})
			return
		}
		hostweb.Back(w, r, Path, hostweb.Flash{Text: catalog.T(lang, done, nil), Key: done}, hostweb.Flash{})
	})
}
```

If anchor A7 showed that `Render` takes the file name (for example `"stay_fees.tmpl"`) instead of the `define` name, replace `"guest_inbox"` with `"guest_inbox.tmpl"` in the `layout.Render` call; that is the only allowed change.

Run: `cd go && gofmt -l internal/web/guestinbox 2>&1 | head -5`
Expected: no output.

### Step 3: create `go/internal/web/guestinbox/templates/guest_inbox.tmpl`

```html
{{- /* Brief 1838. /guest-inbox body. No JavaScript: two plain POST forms per held row. */ -}}
{{define "guest_inbox"}}
<div class="ui-page-narrow">
  {{if not (or .Held .Notes)}}<p class="ui-note-strip">{{t "guest_inbox.empty"}}</p>{{end}}
  {{if .Held}}
  <section class="ui-section-card" aria-labelledby="inbox-held">
    <div class="ui-section-head"><h2 id="inbox-held" class="ui-section-h">{{t "guest_inbox.held"}}</h2></div>
    <p class="ui-note-strip">{{t "guest_inbox.held_lede"}}</p>
    {{range .Held}}
    <article class="ui-kv" id="inbox-{{.ID}}">
      <h3>{{if .GuestName}}{{.GuestName}}{{else}}{{t "guest_inbox.unnamed"}}{{end}}</h3>
      <div class="ui-kv-row"><span>{{t "guest_inbox.property"}}</span><span>{{.ApartmentName}}</span></div>
      <div class="ui-kv-row"><span>{{t "guest_inbox.received"}}</span><span>{{.Received}}</span></div>
      <div class="ui-kv-row"><span>{{t "guest_inbox.deadline"}}</span><span><strong>{{.Deadline}}</strong></span></div>
      {{if .Stays}}
      <form method="post" action="/guest-inbox/{{.ID}}/attach" class="ui-field">
        <input type="hidden" name="_csrf" value="{{csrf}}">
        <label for="stay-{{.ID}}">{{t "guest_inbox.stay"}}</label>
        <select id="stay-{{.ID}}" name="reservation_id" required>
          {{range .Stays}}<option value="{{.ID}}">{{.Label}}</option>{{end}}
        </select>
        <button class="ui-btn ui-btn-primary" type="submit">{{t "guest_inbox.attach"}}</button>
      </form>
      {{else}}
      <p class="ui-note-strip">{{t "guest_inbox.no_stays"}}</p>
      {{end}}
      <form method="post" action="/guest-inbox/{{.ID}}/dismiss">
        <input type="hidden" name="_csrf" value="{{csrf}}">
        <button class="ui-btn ui-btn-secondary" type="submit">{{t "guest_inbox.dismiss"}}</button>
      </form>
    </article>
    {{end}}
  </section>
  {{end}}
  {{if .Notes}}
  <section class="ui-section-card" aria-labelledby="inbox-notes">
    <div class="ui-section-head"><h2 id="inbox-notes" class="ui-section-h">{{t "guest_inbox.notes"}}</h2></div>
    {{range .Notes}}
    <article class="ui-kv" id="inbox-{{.ID}}">
      <h3>{{if .GuestName}}{{.GuestName}}{{else}}{{t "guest_inbox.unnamed"}}{{end}}</h3>
      <div class="ui-kv-row"><span>{{t "guest_inbox.property"}}</span><span>{{.ApartmentName}}</span></div>
      <div class="ui-kv-row"><span>{{t "guest_inbox.received"}}</span><span>{{.Received}}</span></div>
      <p class="ui-note-strip">{{.Note}}</p>
    </article>
    {{end}}
  </section>
  {{end}}
</div>
{{end}}
```

Run: `grep -c 'name="_csrf"' go/internal/web/guestinbox/templates/guest_inbox.tmpl`
Expected: `2`.

### Step 4: create `go/internal/web/guestinbox/i18n.json`

```json
{
 "cs": {
  "guest_inbox.title": "Registrace k zařazení",
  "guest_inbox.held": "Nepřiřazené registrace",
  "guest_inbox.held_lede": "Nepodařilo se je přiřadit k pobytu. Dokud je nepřiřadíte, nenahlásí se.",
  "guest_inbox.notes": "Poznámky k registracím",
  "guest_inbox.unnamed": "Host bez jména",
  "guest_inbox.property": "Ubytování",
  "guest_inbox.received": "Přijato",
  "guest_inbox.deadline": "Nahlásit do",
  "guest_inbox.stay": "Pobyt",
  "guest_inbox.attach": "Přiřadit",
  "guest_inbox.dismiss": "Zahodit",
  "guest_inbox.no_stays": "Žádný pobyt k přiřazení. Přidejte pobyt a vraťte se sem.",
  "guest_inbox.empty": "Nic k zařazení.",
  "guest_inbox.attached": "Přiřazeno. Registrace se zpracuje během minuty.",
  "guest_inbox.dismissed": "Zahozeno.",
  "guest_inbox.gone": "Tato registrace už je vyřízená.",
  "guest_inbox.note.already_registered": "Host už byl na tomto pobytu registrován, uložen jednou.",
  "guest_inbox.note.over_count": "Více hostů, než pobyt čekal. Registrován a nahlášen jako ostatní."
 },
 "en": {
  "guest_inbox.title": "Registrations to sort",
  "guest_inbox.held": "Not attached to a stay",
  "guest_inbox.held_lede": "These could not be matched to a stay. They are not filed until you attach them.",
  "guest_inbox.notes": "Notes on registrations",
  "guest_inbox.unnamed": "Guest without a name",
  "guest_inbox.property": "Property",
  "guest_inbox.received": "Received",
  "guest_inbox.deadline": "File by",
  "guest_inbox.stay": "Stay",
  "guest_inbox.attach": "Attach",
  "guest_inbox.dismiss": "Dismiss",
  "guest_inbox.no_stays": "No stay to attach to. Add the stay, then come back here.",
  "guest_inbox.empty": "Nothing to sort.",
  "guest_inbox.attached": "Attached. The registration is processed within a minute.",
  "guest_inbox.dismissed": "Dismissed.",
  "guest_inbox.gone": "This registration is already handled.",
  "guest_inbox.note.already_registered": "This guest was already registered on this stay and is kept once.",
  "guest_inbox.note.over_count": "More guests than the stay expected. Registered and filed like the others."
 }
}
```

Run: `python3 -c "import json;d=json.load(open('go/internal/web/guestinbox/i18n.json'));print(sorted(d['cs'])==sorted(d['en']))"`
Expected: `True`.

### Step 5: create `go/internal/web/guestinbox/inbox_test.go`

```go
package guestinbox

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func prague(t *testing.T) *time.Location {
	t.Helper()
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		t.Fatal(err)
	}
	return loc
}

// The deadline uses the earlier of the stay's date_from and the received date.
func TestDeadlineAnchor(t *testing.T) {
	loc := prague(t)
	received := time.Date(2026, 11, 18, 9, 0, 0, 0, time.UTC) // Wednesday
	cases := []struct {
		stayFrom string
		want     time.Time
	}{
		{"2026-11-16", time.Date(2026, 11, 18, 23, 59, 59, 0, loc)}, // Monday stay: Mon, Tue, Wed
		{"", time.Date(2026, 11, 20, 23, 59, 59, 0, loc)},           // no stay: Wed, Thu, Fri
		{"2026-11-25", time.Date(2026, 11, 20, 23, 59, 59, 0, loc)}, // later stay: received date wins
	}
	for _, c := range cases {
		if got := Deadline(c.stayFrom, received); !got.Equal(c.want) {
			t.Errorf("Deadline(%q) = %v, want %v", c.stayFrom, got, c.want)
		}
	}
}

func TestEveryQueryIsOwnerScoped(t *testing.T) {
	for name, want := range map[string]string{
		listSQL: "a.owner_user_id = $1", staysSQL: "a.owner_user_id = $2",
		attachSQL: "a.owner_user_id = $3", dismissSQL: "a.owner_user_id = $2",
	} {
		if !strings.Contains(name, want) {
			t.Errorf("query lacks %q:\n%s", want, name)
		}
	}
}

func TestActionsOnlyTouchHeldRows(t *testing.T) {
	for _, q := range []string{attachSQL, dismissSQL} {
		if !strings.Contains(q, "status = 'held'") {
			t.Errorf("action not limited to held rows:\n%s", q)
		}
	}
	if !strings.Contains(attachSQL, "SET status = 'new', reservation_id = $2") {
		t.Error("attach must hand the row back to the worker with the chosen stay")
	}
}

func TestPageWorksWithoutJavaScript(t *testing.T) {
	b, err := files.ReadFile("templates/guest_inbox.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	for _, bad := range []string{"<script", "onclick", "style=", "data-"} {
		if strings.Contains(s, bad) {
			t.Errorf("template contains %q", bad)
		}
	}
	if strings.Count(s, `method="post"`) != 2 || strings.Count(s, `name="_csrf"`) != 2 {
		t.Error("want two POST forms, each with _csrf")
	}
}

func TestCatalogCsAndEn(t *testing.T) {
	var d map[string]map[string]string
	if err := json.Unmarshal(catalogJSON, &d); err != nil {
		t.Fatal(err)
	}
	for _, pair := range [][2]string{{"cs", "en"}, {"en", "cs"}} {
		for k, v := range d[pair[0]] {
			if _, ok := d[pair[1]][k]; !ok {
				t.Errorf("%s lacks %s", pair[1], k)
			}
			if strings.Contains(v, "—") {
				t.Errorf("em dash in %s %s", pair[0], k)
			}
		}
	}
}

func TestRoutes(t *testing.T) {
	var got []string
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		got = append(got, r.Pattern)
	}
	want := "GET /guest-inbox|POST /guest-inbox/{id}/attach|POST /guest-inbox/{id}/dismiss"
	if strings.Join(got, "|") != want {
		t.Errorf("routes = %v", got)
	}
}
```

Run: `cd go && go test ./internal/web/guestinbox/... 2>&1 | tail -30`
Expected: `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guestinbox`.

### Step 6: create `go/cmd/ubyhost-web/register_web_guestinbox.go`

```go
package main

// Brief 1838 owns this file: /guest-inbox (go/internal/web/guestinbox). Caddy
// keeps the paths off Go until UBYHOST_GO_PATHS names them (after 1838b).

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guestinbox"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		for _, r := range guestinbox.Routes(pool, os.Getenv, time.Now) {
			_, path, _ := strings.Cut(r.Pattern, " ")
			mux.Handle(r.Pattern, m.wrap(path, r.Handler))
		}
	})
}
```

Run: `cd go && go vet ./internal/web/guestinbox/ ./cmd/ubyhost-web/ 2>&1 | tail -30 && go test ./cmd/ubyhost-web/... 2>&1 | tail -30`
Expected: no vet output; `ok  	.../go/cmd/ubyhost-web`. If a cmd test lists every route (a golden or path list) and fails, STOP (the file to change is not in §3).

### Step 7: lint

Run: `python3 scripts/context_lint.py 2>&1 | tail -30`
Expected: no finding for this brief or the new files.

## 5. Do not touch

- Anything under `App/` (go-first; the dashboard link waits for Q6), `deploy/`, `caddy/`, migrations, `docs/ENVIRONMENT.md`.
- Rule 3: no guest data in fixtures or logs; the tests use no names. Rule 5: no schema change (Q2, Q3). Rule 6: no JavaScript, light mode. Rule 9: copy as given, no extra sentences.

## 6. Commands

From `go/` (test-map row "Go filing alarms" plus the new package):

```
gofmt -l internal/web/guestinbox cmd/ubyhost-web 2>&1 | head -5          # no output
go vet ./internal/web/guestinbox/ ./cmd/ubyhost-web/ 2>&1 | tail -30      # no output
go test ./internal/web/guestinbox/... ./cmd/ubyhost-web/... ./internal/hostweb/... 2>&1 | tail -30   # ok lines only
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The six files of §3 exist; `git diff --stat` names no other file.
- [ ] `go test` for the three packages above: `ok`, 0 failures.
- [ ] Every SQL statement carries `a.owner_user_id` (TestEveryQueryIsOwnerScoped).
- [ ] Attach and dismiss change only `held` rows; attach sets `new` and the chosen stay.
- [ ] The deadline is `ubyport.ReportingDeadline` from the anchor of Q1 (TestDeadlineAnchor).
- [ ] The template has no script, inline style or `data-` hook; two POST forms with `_csrf`.
- [ ] PR is a draft; body says "dormant; UX gate in 1838b" and pastes the design-system checklist below unticked (ticked in 1838b):
  - [ ] Page extends the host layout; no own shell, `<style>`, `style=""` or raw colour/spacing.
  - [ ] Header has one aligned action row: at most one primary, at most two secondary, rest in ⋮; on phone primary full width.
  - [ ] Each form has one Save; no floating Save bar; no repeated heading.
  - [ ] No fine print; every help "?" is inline after its label.
  - [ ] Nothing closer than 12 px to a neighbour; labels 6 px above inputs; no truncated label.
  - [ ] 390, 768 and 1280 px: table to cards on phone, tablet layout at 768, no sideways scroll.
  - [ ] `test_layout_lint_browser.py` green, 0 skipped; screenshots at 390/768/1280 opened; PR says per page what was seen.
  - [ ] CS and EN keys added together; no em dash in UI copy.
  - [ ] CI watched to the end; red fixed at once.

## 8. Stop and ask

Stop, and write the report, if:

- Step 0 finds fewer than 6 answers, or an anchor differs;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change (for example a route list in `go/cmd/ubyhost-web`);
- §5 would be touched;
- a step is unclear;
- you need push to `main`, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1838-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations (the A7 render-name choice), questions, owner steps left.

## 1838b (orchestrator writes after Q5)

UX gate for `/guest-inbox`: run the layout lint and geometry checks against `ubyhost-web` with a seeded owner (one `held` row with stays, one without, one `done` note), 0 findings, 0 skipped; screenshots `guest-inbox-{390,768,1280}.png` opened; PR text per width; checklist above ticked. Test files come from the [test-map](../context/test-map.md) row "Host pages, templates, CSS": `App/tests/test_host_*.py`, `App/tests/test_host_geometry.py`, plus `App/tests/test_layout_lint_browser.py` (`UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots`). Only after it is green does the PR leave draft.

## Risk list (for the reviewer)

- `go/internal/web/guestinbox/inbox.go`: owner scope of all four statements; the attach subquery that pins the stay to the row's own property; `Deadline` anchor.
- `go/internal/web/guestinbox/handlers.go`: Login before CSRF before any write; payload decrypted only to show the name, never logged.
- `go/internal/web/guestinbox/templates/guest_inbox.tmpl`: no JavaScript, escaping by `html/template`.

## Owner steps

None for 1838 (dormant, draft). After 1838b is merged:

1. Open the Lightsail console, connect to the server with the browser terminal.
2. Run `cd ~/ubyhost/deploy/lightsail && nano .env`.
3. On the `UBYHOST_GO_PATHS="..."` line, add ` /guest-inbox /guest-inbox/*` before the closing quote. Save with Ctrl+O, Enter, then Ctrl+X.
4. Run `./scripts/deploy.sh 2>&1 | tail -30` and wait for the healthy line.
5. Open `https://<your app address>/guest-inbox` while signed in: you see "Registrations to sort".
