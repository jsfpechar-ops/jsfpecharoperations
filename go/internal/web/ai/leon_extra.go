package ai

// leon_extra.go: POST /apartments/{id}/leon/setup/try, the port of setup_try
// in App/app/routes/leon_setup.py (lines 122-149): one test message to Leon,
// as a booked guest would ask it. Nothing is stored. Replaces brief 1435's
// empty file.
//
// What is sent to the model: only what LeonSystemBlocks and LeonUserTurn build
// (see leon_core.go): the constant character text, the guide cards a booked
// guest may read (never host-only cards, never drafts' text) and the host's
// test message with e-mail addresses, phone numbers and ID-like runs replaced
// by [email], [phone] and [number].

import (
	"context"
	"errors"
	"io"
	"net/http"
	"strings"

	"github.com/jackc/pgx/v5"
)

func (d HavelDeps) leonExtraRoutes() []HavelRoute {
	return []HavelRoute{{"POST /apartments/{id}/leon/setup/try", "/apartments/{id}/leon/setup/try", d.leonTry}}
}

// hostName is _host_contact(apartment).get("name", ""): the name of the
// property's legal entity.
func (c *leonCall) hostName(ctx context.Context) (string, error) {
	if c.apt.LegalEntityID == 0 {
		return "", nil
	}
	var name string
	err := c.store.Pool.QueryRow(ctx, `SELECT COALESCE(name, '') FROM legal_entity WHERE id = $1`, c.apt.LegalEntityID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	return name, err
}

func (d HavelDeps) leonTry(w http.ResponseWriter, r *http.Request) {
	c := d.leonEnter(w, r)
	if c == nil {
		return
	}
	ctx := r.Context()
	// leon.switched_on: the host ticked yes and accepted the current terms
	// (the owner's test-list entry was checked by _offered).
	if !c.apt.Enabled || !LeonTermsCurrent(*c.apt) {
		leonNotFound(w)
		return
	}
	f, err := c.ls.Facts(ctx, c.id)
	if err != nil {
		havelServerError(w, err)
		return
	}
	if !f.Live {
		leonNotFound(w)
		return
	}
	message := c.form("message")
	guestLang := "en"
	if c.lang == "cs" {
		guestLang = "cs"
	}
	host, err := c.hostName(ctx)
	if err != nil {
		havelServerError(w, err)
		return
	}
	result, err := c.ls.TryReply(ctx, d.Model, *c.apt, message, guestLang, host, c.at)
	if err != nil {
		havelServerError(w, err)
		return
	}
	text := result.Text
	switch result.Kind {
	case "cap":
		text = c.leonT("leon_setup.try.cap")
	case "no_guide":
		text = c.leonT("leon_page.not_live")
	}
	note := ""
	if result.WouldAsk {
		note = c.leonT("leon_setup.try.would_ask")
	}
	if strings.Contains(r.Header.Get("Accept"), "application/json") {
		cap := ""
		if result.Left <= 0 && result.Kind != "cap" {
			cap = c.leonT("leon_setup.try.cap")
		}
		b := func(v bool) string {
			if v {
				return "true"
			}
			return "false"
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = io.WriteString(w, `{"kind":`+havelPyString(result.Kind)+`,"text":`+havelPyString(text)+`,"would_ask":`+b(result.WouldAsk)+
			`,"blocked":`+b(result.Left <= 0)+`,"note":`+havelPyString(note)+`,"cap":`+havelPyString(cap)+`}`)
		return
	}
	c.stepPage("try", havelClip(message, 500), &LeonAnswer{Text: text, WouldAsk: result.WouldAsk})
}
