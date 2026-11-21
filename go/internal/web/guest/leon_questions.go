package guest

// Brief 1726: ports App/app/routes/guest_leon.py and guest_questions.py.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"testing/fstest"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

const (
	leonCookieName   = "ubyhost_leon"
	leonCookieDays   = 30
	leonMaxMsg       = 500
	handoffAnswerMax = 1000
	handoffListLimit = 50
)

var leonHarden = map[string]string{
	"Cache-Control":   "no-store",
	"X-Robots-Tag":    "noindex, nofollow",
	"Referrer-Policy": "no-referrer",
}

var lqPathID = regexp.MustCompile(`^([+-]?[0-9]+(?:_[0-9]+)*)(?:\.0+)?$`)
var lqClientID = regexp.MustCompile(`^[a-zA-Z0-9_-]{8,64}$`)

// LeonQuestionRoute is one registered pattern.
type LeonQuestionRoute struct {
	Pattern string
	Label   string
	Handler http.HandlerFunc
}

type lqServer struct {
	pool      *pgxpool.Pool
	getenv    func(string) string
	lookupEnv func(string) (string, bool)
	now       func() time.Time
	model     ai.HavelModel
}

type lqHostReq struct {
	host *session.Host
	apt  int64
	qid  int64
	lang string
	at   time.Time
	r    *http.Request
}

var lqI18n = []byte(`{
  "en": {
    "guest_questions.title": "Guest questions",
    "guest_questions.open": "%(n)s waiting for your answer",
    "guest_questions.none_open": "Nothing is waiting for you",
    "guest_questions.empty.title": "No questions yet",
    "guest_questions.empty.body": "Your reply appears on the guest guide.",
    "guest_questions.col.question": "Question",
    "guest_questions.col.state": "State",
    "guest_questions.door.qr": "QR page",
    "guest_questions.door.stay": "stay link",
    "guest_questions.state.open": "Waiting",
    "guest_questions.state.answered": "Answered",
    "guest_questions.state.dismissed": "Dismissed",
    "guest_questions.badge.urgent": "Urgent",
    "guest_questions.badge.unread": "Not read by Leon (AI)",
    "guest_question.title": "Guest question",
    "guest_question.asked": "The guest asked",
    "guest_question.summary": "In short:",
    "guest_question.your_answer": "Your answer",
    "guest_question.answer_placeholder": "Write your answer for the guest",
    "guest_question.dismiss": "Dismiss",
    "guest_question.send": "Send to guest",
    "guest_question.add_to_guide": "Add answer to guide",
    "guest_question.topic": "Topic",
    "flash.guest_question.sent": "Answer sent.",
    "flash.guest_question.dismissed": "Question dismissed.",
    "flash.guest_question.card": "Added to the guide.",
    "flash.error.guest_question_empty": "Write an answer first.",
    "flash.error.guest_question_gone": "That question no longer exists.",
    "flash.error.guest_question_too_long": "The answer is too long. Shorten it to 1000 characters.",
    "flash.error.guest_question_not_answered": "Answer the question first, then add it to the guide."
  },
  "cs": {
    "guest_questions.title": "Dotazy hostů",
    "guest_questions.open": "%(n)s čeká na vaši odpověď",
    "guest_questions.none_open": "Nic na vás nečeká",
    "guest_questions.empty.title": "Zatím žádné dotazy",
    "guest_questions.empty.body": "Odpověď se hostovi zobrazí v průvodci.",
    "guest_questions.col.question": "Dotaz",
    "guest_questions.col.state": "Stav",
    "guest_questions.door.qr": "QR stránka",
    "guest_questions.door.stay": "odkaz na pobyt",
    "guest_questions.state.open": "Čeká",
    "guest_questions.state.answered": "Zodpovězeno",
    "guest_questions.state.dismissed": "Zamítnuto",
    "guest_questions.badge.urgent": "Naléhavé",
    "guest_questions.badge.unread": "Leon (AI) nečetl",
    "guest_question.title": "Dotaz hosta",
    "guest_question.asked": "Host se zeptal",
    "guest_question.summary": "Stručně:",
    "guest_question.your_answer": "Vaše odpověď",
    "guest_question.answer_placeholder": "Napište odpověď pro hosta",
    "guest_question.dismiss": "Zamítnout",
    "guest_question.send": "Odeslat hostovi",
    "guest_question.add_to_guide": "Přidat odpověď do průvodce",
    "guest_question.topic": "Téma",
    "flash.guest_question.sent": "Odpověď odeslána.",
    "flash.guest_question.dismissed": "Dotaz zamítnut.",
    "flash.guest_question.card": "Přidáno do průvodce.",
    "flash.error.guest_question_empty": "Nejdřív napište odpověď.",
    "flash.error.guest_question_gone": "Tento dotaz už neexistuje.",
    "flash.error.guest_question_too_long": "Odpověď je příliš dlouhá.",
    "flash.error.guest_question_not_answered": "Nejdřív odpovězte."
  }
}`)

var lqTmpl = []byte(`{{define "guest_questions.html"}}<div class="ui-page" data-body-kind="list"><div class="ui-body ui-body-list"><div class="head"><div><a class="guide-back" href="/apartments/{{.ApartmentID}}">{{.ApartmentName}}</a><h1 class="big">{{lqT .Lang "guest_questions.title"}}</h1>{{if gt .OpenCount 0}}<p class="sub">{{lqT .Lang "guest_questions.open" "n" .OpenCount}}</p>{{else}}<p class="sub">{{lqT .Lang "guest_questions.none_open"}}</p>{{end}}</div></div>{{if not .Questions}}<p class="empty-hd">{{lqT .Lang "guest_questions.empty.title"}}</p><p>{{lqT .Lang "guest_questions.empty.body"}}</p>{{else}}<table class="ui-table"><thead><tr><th>{{lqT .Lang "guest_questions.col.question"}}</th><th>{{lqT .Lang "guest_questions.col.state"}}</th></tr></thead><tbody>{{range .Questions}}<tr><td><a href="{{$.Base}}/{{.ID}}">{{if .Summary}}{{.Summary}}{{else}}{{.Question}}{{end}}</a></td><td>{{if eq .Door "qr"}}{{lqT $.Lang "guest_questions.door.qr"}}{{else}}{{lqT $.Lang "guest_questions.door.stay"}}{{end}} · {{lqT $.Lang (printf "guest_questions.state.%s" .Status)}}</td></tr>{{end}}</tbody></table>{{end}}</div></div>{{end}}
{{define "guest_question.html"}}<div class="ui-page" data-body-kind="detail"><div class="ui-body ui-body-detail"><div class="head"><div><a class="guide-back" href="{{.Base}}">{{lqT .Lang "guest_questions.title"}}</a><h1 class="big">{{lqT .Lang "guest_question.title"}}</h1></div></div>{{if .Error}}<p class="form-error">{{lqT .Lang .Error}}</p>{{end}}<p class="sub">{{lqT .Lang "guest_question.asked"}}</p><blockquote class="guest-q">{{.QuestionText}}</blockquote>{{if .Summary}}<p><strong>{{lqT .Lang "guest_question.summary"}}</strong> {{.Summary}}</p>{{end}}<form method="post" action="{{.Base}}/{{.QuestionID}}" class="stack"><input type="hidden" name="_csrf" value="{{csrf}}"><label for="answer">{{lqT .Lang "guest_question.your_answer"}}</label><textarea class="ui-input" id="answer" name="answer" rows="6" maxlength="{{.MaxChars}}" placeholder="{{lqT .Lang "guest_question.answer_placeholder"}}">{{.AnswerDraft}}</textarea><div class="form-acts"><button class="btn" type="submit">{{lqT .Lang "guest_question.send"}}</button><button class="btn secondary" formaction="{{.Base}}/{{.QuestionID}}/dismiss" formmethod="post">{{lqT .Lang "guest_question.dismiss"}}</button></div></form>{{if .Answered}}<form method="post" action="{{.Base}}/{{.QuestionID}}/card" class="stack"><input type="hidden" name="_csrf" value="{{csrf}}"><label for="topic">{{lqT .Lang "guest_question.topic"}}</label><select id="topic" name="topic">{{range .Topics}}<option value="{{.}}">{{.}}</option>{{end}}</select><button class="btn secondary" type="submit">{{lqT .Lang "guest_question.add_to_guide"}}</button></form>{{end}}</div></div>{{end}}
`)

var hostCatalog = hostweb.Load(lqI18n)

var lqPages = layout.MustParseFuncs(hostCatalog, template.FuncMap{
	"lqT": func(lang, key string, kv ...any) string {
		params := map[string]any{}
		for i := 0; i+1 < len(kv); i += 2 {
			if s, ok := kv[i].(string); ok {
				params[s] = kv[i+1]
			}
		}
		return hostCatalog.T(lang, key, params)
	},
}, fstest.MapFS{"lq_templates.tmpl": &fstest.MapFile{Data: lqTmpl}}, "lq_templates.tmpl")

// RegisterLeonQuestions wires all nine routes (dormant until UBYHOST_GO_PATHS).
func RegisterLeonQuestions(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	s := &lqServer{pool: pool, getenv: getenv, lookupEnv: lookupEnv, now: now, model: anthropic.NewService(pool, anthropic.ConfigFromEnv(lookupEnv))}
	routes := []struct {
		method, path, label string
		h                   http.HandlerFunc
	}{
		{http.MethodGet, "/l/{token}/{reservation_id}/guide/leon", "GET /l/{token}/{reservation_id}/guide/leon", s.stayLeonGet},
		{http.MethodPost, "/l/{token}/{reservation_id}/guide/leon", "POST /l/{token}/{reservation_id}/guide/leon", s.stayLeonPost},
		{http.MethodGet, "/g/{token}/leon", "GET /g/{token}/leon", s.qrLeonGet},
		{http.MethodPost, "/g/{token}/leon", "POST /g/{token}/leon", s.qrLeonPost},
		{http.MethodGet, "/apartments/{apartment_id}/guide/questions", "GET /apartments/{apartment_id}/guide/questions", s.questionsIndex},
		{http.MethodGet, "/apartments/{apartment_id}/guide/questions/{question_id}", "GET /apartments/{apartment_id}/guide/questions/{question_id}", s.questionPage},
		{http.MethodPost, "/apartments/{apartment_id}/guide/questions/{question_id}", "POST /apartments/{apartment_id}/guide/questions/{question_id}", s.questionAnswer},
		{http.MethodPost, "/apartments/{apartment_id}/guide/questions/{question_id}/dismiss", "POST /apartments/{apartment_id}/guide/questions/{question_id}/dismiss", s.questionDismiss},
		{http.MethodPost, "/apartments/{apartment_id}/guide/questions/{question_id}/card", "POST /apartments/{apartment_id}/guide/questions/{question_id}/card", s.questionCard},
	}
	for _, rt := range routes {
		pattern := rt.method + " " + rt.path
		mux.Handle(pattern, wrap(rt.label, rt.h))
	}
}

func (s *lqServer) stamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

func lqParseID(raw string) (int64, bool) {
	m := lqPathID.FindStringSubmatch(strings.Trim(raw, " \t\n\r\v\f"))
	if m == nil {
		return 0, false
	}
	id, err := strconv.ParseInt(strings.ReplaceAll(m[1], "_", ""), 10, 64)
	if err != nil {
		return 0, true
	}
	return id, true
}

func (s *lqServer) hostEnter(w http.ResponseWriter, r *http.Request) (*lqHostReq, bool) {
	at := s.now()
	if r.Method == http.MethodPost && !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, false
	}
	q := &lqHostReq{lang: hostweb.Lang(r), at: at, r: r}
	if raw := r.PathValue("apartment_id"); raw != "" {
		id, ok := lqParseID(raw)
		if !ok {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return nil, false
		}
		q.apt = id
	}
	if raw := r.PathValue("question_id"); raw != "" {
		id, ok := lqParseID(raw)
		if !ok {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return nil, false
		}
		q.qid = id
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		lqFail(w, err)
		return nil, false
	}
	if h == nil {
		return nil, false
	}
	q.host = h
	if r.Method == http.MethodPost {
		_ = r.ParseForm()
	}
	return q, true
}

func lqFail(w http.ResponseWriter, err error) {
	log.Printf("leon_questions: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func (s *lqServer) hostApartment(ctx context.Context, owner, apt int64) (string, error) {
	var name string
	err := s.pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2 AND COALESCE(archived_at, '') = ''`, apt, owner).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", pgx.ErrNoRows
	}
	return name, err
}

func (s *lqServer) questionsIndex(w http.ResponseWriter, r *http.Request) {
	q, ok := s.hostEnter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	name, err := s.hostApartment(ctx, q.host.Workspace.ID, q.apt)
	if errors.Is(err, pgx.ErrNoRows) {
		http.NotFound(w, r)
		return
	}
	if err != nil {
		lqFail(w, err)
		return
	}
	_ = s.handoffRefreshAlert(ctx, q.apt)
	rows, open, err := s.handoffList(ctx, q.apt)
	if err != nil {
		lqFail(w, err)
		return
	}
	data := map[string]any{
		"Lang": q.lang, "ApartmentID": q.apt, "ApartmentName": name, "OpenCount": open,
		"Questions": rows, "Base": fmt.Sprintf("/apartments/%d/guide/questions", q.apt),
	}
	s.renderHost(w, r, q, "guest_questions.html", data)
}

func (s *lqServer) questionPage(w http.ResponseWriter, r *http.Request) {
	q, ok := s.hostEnter(w, r)
	if !ok {
		return
	}
	s.renderQuestion(w, r, q, "", http.StatusOK)
}

func (s *lqServer) questionAnswer(w http.ResponseWriter, r *http.Request) {
	q, ok := s.hostEnter(w, r)
	if !ok {
		return
	}
	ans := strings.TrimSpace(r.FormValue("answer"))
	if ans == "" {
		s.renderQuestion(w, r, q, "flash.error.guest_question_empty", http.StatusUnprocessableEntity)
		return
	}
	if len(ans) > handoffAnswerMax {
		s.renderQuestion(w, r, q, "flash.error.guest_question_too_long", http.StatusUnprocessableEntity)
		return
	}
	if err := s.handoffAnswer(r.Context(), q.apt, q.qid, ans, s.now()); err != nil {
		if errors.Is(err, errHandoffGone) {
			s.renderQuestion(w, r, q, "flash.error.guest_question_gone", http.StatusUnprocessableEntity)
			return
		}
		lqFail(w, err)
		return
	}
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/guide/questions/%d", q.apt, q.qid), hostweb.Flash{Text: hostCatalog.T(q.lang, "flash.guest_question.sent", nil), Key: "flash.guest_question.sent"}, hostweb.Flash{})
}

func (s *lqServer) questionDismiss(w http.ResponseWriter, r *http.Request) {
	q, ok := s.hostEnter(w, r)
	if !ok {
		return
	}
	if err := s.handoffDismiss(r.Context(), q.apt, q.qid, s.now()); err != nil && !errors.Is(err, errHandoffGone) {
		lqFail(w, err)
		return
	}
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/guide/questions", q.apt), hostweb.Flash{Text: hostCatalog.T(q.lang, "flash.guest_question.dismissed", nil), Key: "flash.guest_question.dismissed"}, hostweb.Flash{})
}

func (s *lqServer) questionCard(w http.ResponseWriter, r *http.Request) {
	q, ok := s.hostEnter(w, r)
	if !ok {
		return
	}
	topic := strings.TrimSpace(r.FormValue("topic"))
	item, err := s.handoffAddGuide(r.Context(), q.apt, q.qid, topic)
	if err != nil {
		key := ""
		if errors.Is(err, errHandoffGone) {
			key = "flash.error.guest_question_gone"
		} else if errors.Is(err, errHandoffNotAnswered) {
			key = "flash.error.guest_question_not_answered"
		} else {
			lqFail(w, err)
			return
		}
		s.renderQuestion(w, r, q, key, http.StatusUnprocessableEntity)
		return
	}
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/guide/%d", q.apt, item), hostweb.Flash{Text: hostCatalog.T(q.lang, "flash.guest_question.card", nil), Key: "flash.guest_question.card"}, hostweb.Flash{})
}

var errHandoffGone = errors.New("gone")
var errHandoffNotAnswered = errors.New("not_answered")

type handoffRow struct {
	ID, ChatID                      int64
	Summary, Status, Door, Question string
	Urgent, Triaged                 int
	Answer                          string
}

func (s *lqServer) handoffList(ctx context.Context, apt int64) ([]handoffRow, int, error) {
	const q = `SELECT q.id, q.chat_id, COALESCE(q.summary,''), q.status, COALESCE(c.door,''), COALESCE(m.text,''), COALESCE(q.urgent,0), COALESCE(q.triaged,0), COALESCE(q.answer,'')
		FROM guest_question q JOIN guest_chat c ON c.id = q.chat_id JOIN guest_chat_message m ON m.id = q.message_id
		WHERE q.apartment_id = $1 ORDER BY CASE q.status WHEN 'open' THEN 0 ELSE 1 END,
		CASE q.status WHEN 'open' THEN -q.urgent ELSE 0 END,
		CASE q.status WHEN 'open' THEN q.id ELSE -q.id END LIMIT $2`
	rows, err := s.pool.Query(ctx, q, apt, handoffListLimit)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	var out []handoffRow
	open := 0
	for rows.Next() {
		var row handoffRow
		if err := rows.Scan(&row.ID, &row.ChatID, &row.Summary, &row.Status, &row.Door, &row.Question, &row.Urgent, &row.Triaged, &row.Answer); err != nil {
			return nil, 0, err
		}
		if row.Status == "open" {
			open++
		}
		out = append(out, row)
	}
	return out, open, rows.Err()
}

func (s *lqServer) handoffGet(ctx context.Context, apt, qid int64) (*handoffRow, error) {
	const q = `SELECT q.id, q.chat_id, COALESCE(q.summary,''), q.status, COALESCE(c.door,''), COALESCE(m.text,''), COALESCE(q.urgent,0), COALESCE(q.triaged,0), COALESCE(q.answer,'')
		FROM guest_question q JOIN guest_chat c ON c.id = q.chat_id JOIN guest_chat_message m ON m.id = q.message_id
		WHERE q.id = $1 AND q.apartment_id = $2`
	var row handoffRow
	err := s.pool.QueryRow(ctx, q, qid, apt).Scan(&row.ID, &row.ChatID, &row.Summary, &row.Status, &row.Door, &row.Question, &row.Urgent, &row.Triaged, &row.Answer)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, errHandoffGone
	}
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func (s *lqServer) handoffRefreshAlert(ctx context.Context, apt int64) error {
	var n, urg int64
	err := s.pool.QueryRow(ctx, `SELECT COUNT(*), COALESCE(SUM(urgent),0) FROM guest_question WHERE apartment_id = $1 AND status = 'open'`, apt).Scan(&n, &urg)
	if err != nil {
		return err
	}
	if n == 0 {
		_, err = s.pool.Exec(ctx, `UPDATE alert SET status = 'resolved' WHERE dedupe_key = $1 AND status != 'resolved'`, fmt.Sprintf("guest_question:%d", apt))
		return err
	}
	level := "warning"
	if urg > 0 {
		level = "critical"
	}
	_, err = s.pool.Exec(ctx, `INSERT INTO alert (level, kind, title, detail, dedupe_key, apartment_id, created_at, status)
		VALUES ($1, 'guest_question', 'guest questions', '', $2, $3, $4, 'open')
		ON CONFLICT (dedupe_key) DO UPDATE SET level = EXCLUDED.level, status = 'open'`, level, fmt.Sprintf("guest_question:%d", apt), apt, s.stamp(s.now()))
	return err
}

func (s *lqServer) handoffAnswer(ctx context.Context, apt, qid int64, text string, at time.Time) error {
	row, err := s.handoffGet(ctx, apt, qid)
	if err != nil {
		return err
	}
	stamp := s.stamp(at)
	_, err = s.pool.Exec(ctx, `INSERT INTO guest_chat_message (chat_id, role, kind, text, sources, created_at) VALUES ($1, 'host', 'answer', $2, '', $3)`, row.ChatID, text, stamp)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(ctx, `UPDATE guest_chat SET last_message_at = $1 WHERE id = $2`, stamp, row.ChatID)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(ctx, `UPDATE guest_question SET answer = $1, answered_at = $2, status = 'answered' WHERE id = $3`, text, stamp, qid)
	if err != nil {
		return err
	}
	return s.handoffRefreshAlert(ctx, apt)
}

func (s *lqServer) handoffDismiss(ctx context.Context, apt, qid int64, at time.Time) error {
	row, err := s.handoffGet(ctx, apt, qid)
	if err != nil {
		return err
	}
	if row.Status == "open" {
		_, err = s.pool.Exec(ctx, `UPDATE guest_question SET status = 'dismissed', answered_at = $1 WHERE id = $2`, s.stamp(at), qid)
		if err != nil {
			return err
		}
	}
	return s.handoffRefreshAlert(ctx, apt)
}

func (s *lqServer) handoffAddGuide(ctx context.Context, apt, qid int64, topic string) (int64, error) {
	row, err := s.handoffGet(ctx, apt, qid)
	if err != nil {
		return 0, err
	}
	if row.Status != "answered" || row.Answer == "" {
		return 0, errHandoffNotAnswered
	}
	title := row.Summary
	if title == "" {
		title = row.Question
	}
	if len(title) > 120 {
		title = title[:120]
	}
	vis := "booked"
	if row.Door == "qr" {
		vis = "everyone"
	}
	var itemID int64
	err = s.pool.QueryRow(ctx, `INSERT INTO guide_item (apartment_id, kind, topic, title, state, visibility, source, created_at, updated_at)
		VALUES ($1, 'custom', $2, $3, 'done', $4, 'host', $5, $5) RETURNING id`, apt, topic, title, vis, s.stamp(s.now())).Scan(&itemID)
	if err != nil {
		return 0, err
	}
	_, err = s.pool.Exec(ctx, `INSERT INTO guide_card (item_id, steps) VALUES ($1, $2) ON CONFLICT (item_id) DO UPDATE SET steps = EXCLUDED.steps`, itemID, row.Answer)
	return itemID, err
}

func (s *lqServer) renderHost(w http.ResponseWriter, r *http.Request, q *lqHostReq, name string, data map[string]any) {
	p := layout.Page{Nav: "apartments", Status: http.StatusOK}
	w.Header().Set("Cache-Control", "no-store")
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: q.at}
	if err := layout.Render(w, r, env, q.host, p, lqPages, name, data); err != nil {
		lqFail(w, err)
	}
}

func (s *lqServer) renderQuestion(w http.ResponseWriter, r *http.Request, q *lqHostReq, errKey string, status int) {
	ctx := r.Context()
	if _, err := s.hostApartment(ctx, q.host.Workspace.ID, q.apt); errors.Is(err, pgx.ErrNoRows) {
		http.NotFound(w, r)
		return
	} else if err != nil {
		lqFail(w, err)
		return
	}
	row, err := s.handoffGet(ctx, q.apt, q.qid)
	if err != nil {
		if errors.Is(err, errHandoffGone) {
			http.NotFound(w, r)
			return
		}
		lqFail(w, err)
		return
	}
	data := map[string]any{
		"Lang": q.lang, "QuestionID": q.qid, "Base": fmt.Sprintf("/apartments/%d/guide/questions", q.apt),
		"QuestionText": row.Question, "Summary": row.Summary, "AnswerDraft": r.FormValue("answer"),
		"Error": errKey, "MaxChars": handoffAnswerMax,
		"Answered": row.Status == "answered" && row.Answer != "",
		"Topics":   []string{"arrival", "keys", "rules", "amenities", "checkout", "emergency", "other"},
	}
	p := layout.Page{Nav: "apartments", Status: status}
	w.Header().Set("Cache-Control", "no-store")
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: q.at}
	if err := layout.Render(w, r, env, q.host, p, lqPages, "guest_question.html", data); err != nil {
		lqFail(w, err)
	}
}

// --- Leon JSON doors (guest_leon.py) ---

func (s *lqServer) leonJSON(w http.ResponseWriter, body any, status int) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	for k, v := range leonHarden {
		w.Header().Set(k, v)
	}
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func (s *lqServer) leonGone(w http.ResponseWriter) {
	s.leonJSON(w, map[string]string{"error": "not_found"}, http.StatusNotFound)
}

type leonApt struct {
	ID                      int64
	Name, Checkin, Checkout string
	LeonEnabled             bool
	LeonTermsVer            string
	Permalink               string
}

func (s *lqServer) guideLive(ctx context.Context, apt int64) (bool, error) {
	var answered, total int64
	err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FILTER (WHERE state = 'done'), COUNT(*) FROM guide_item WHERE apartment_id = $1 AND kind != 'placeholder'`, apt).Scan(&answered, &total)
	if err != nil {
		return false, err
	}
	return answered >= 1 && total > 0, nil
}

func (s *lqServer) leonOn(a leonApt) bool {
	return a.LeonEnabled && ai.LeonTermsCurrent(ai.LeonApartment{TermsVersion: a.LeonTermsVer})
}

func (s *lqServer) stayGate(ctx context.Context, token string, resID int64) (*leonApt, string, bool) {
	var a leonApt
	err := s.pool.QueryRow(ctx, `SELECT a.id, COALESCE(a.internal_name,''), COALESCE(a.permalink_token,''),
		a.leon_enabled <> 0, COALESCE(a.leon_terms_version,'')
		FROM apartment a WHERE a.permalink_token = $1 AND a.active = 1 AND COALESCE(a.archived_at,'') = ''`, token).Scan(&a.ID, &a.Name, &a.Permalink, &a.LeonEnabled, &a.LeonTermsVer)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, "en", false
	}
	if err != nil {
		return nil, "", false
	}
	var rid int64
	err = s.pool.QueryRow(ctx, `SELECT id FROM reservation WHERE id = $1 AND apartment_id = $2 AND status = 'active'`, resID, a.ID).Scan(&rid)
	if err != nil {
		return nil, "en", false
	}
	return &a, "en", true
}

func (s *lqServer) qrGate(ctx context.Context, token string) (*leonApt, string, bool) {
	var a leonApt
	err := s.pool.QueryRow(ctx, `SELECT id, COALESCE(internal_name,''), leon_enabled <> 0, COALESCE(leon_terms_version,'')
		FROM apartment WHERE guide_token = $1 AND active = 1 AND COALESCE(archived_at,'') = ''`, token).Scan(&a.ID, &a.Name, &a.LeonEnabled, &a.LeonTermsVer)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, "en", false
	}
	if err != nil {
		return nil, "", false
	}
	return &a, "en", true
}

func (s *lqServer) conversation(ctx context.Context, chatID int64) (map[string]any, error) {
	if chatID == 0 {
		return map[string]any{"messages": []any{}, "open_questions": 0, "answering": false}, nil
	}
	var open int
	_ = s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest_question WHERE chat_id = $1 AND status = 'open'`, chatID).Scan(&open)
	rows, err := s.pool.Query(ctx, `SELECT role, kind, text, created_at FROM guest_chat_message WHERE chat_id = $1 ORDER BY id DESC LIMIT 60`, chatID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var msgs []map[string]string
	for rows.Next() {
		var role, kind, text, at string
		if err := rows.Scan(&role, &kind, &text, &at); err != nil {
			return nil, err
		}
		msgs = append(msgs, map[string]string{"role": role, "kind": kind, "text": text, "at": at})
	}
	for i, j := 0, len(msgs)-1; i < j; i, j = i+1, j-1 {
		msgs[i], msgs[j] = msgs[j], msgs[i]
	}
	var busy string
	_ = s.pool.QueryRow(ctx, `SELECT COALESCE(busy_until,'') FROM guest_chat WHERE id = $1`, chatID).Scan(&busy)
	answering := busy != "" && busy > s.stamp(s.now())
	return map[string]any{"messages": msgs, "open_questions": open, "answering": answering}, nil
}

func (s *lqServer) stayLeonGet(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	resID, _ := lqParseID(r.PathValue("reservation_id"))
	apt, lang, ok := s.stayGate(ctx, r.PathValue("token"), resID)
	if !ok {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live || !s.leonOn(*apt) {
		s.leonGone(w)
		return
	}
	var chatID int64
	_ = s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'stay' AND reservation_id = $1`, resID).Scan(&chatID)
	body, err := s.conversation(ctx, chatID)
	if err != nil {
		lqFail(w, err)
		return
	}
	_ = lang
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) stayLeonPost(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	resID, _ := lqParseID(r.PathValue("reservation_id"))
	apt, lang, ok := s.stayGate(ctx, r.PathValue("token"), resID)
	if !ok {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live || !s.leonOn(*apt) {
		s.leonGone(w)
		return
	}
	_ = r.ParseForm()
	body, err := s.guestLeonPost(ctx, apt, "stay", resID, "", lang, r.FormValue("message"), r.FormValue("client_id"), clientip.Key(r, s.getenv, "leon"))
	if err != nil {
		lqFail(w, err)
		return
	}
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) qrLeonGet(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	apt, lang, ok := s.qrGate(ctx, r.PathValue("token"))
	if !ok {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live || !s.leonOn(*apt) {
		s.leonGone(w)
		return
	}
	token := r.PathValue("token")
	cookie := r.Cookies()
	var cid string
	for _, c := range cookie {
		if c.Name == leonCookieName {
			cid = c.Value
			break
		}
	}
	var chatID int64
	if cid != "" && lqClientID.MatchString(cid) {
		_ = s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'qr' AND apartment_id = $1 AND cookie_id = $2`, apt.ID, cid).Scan(&chatID)
	}
	body, err := s.conversation(ctx, chatID)
	if err != nil {
		lqFail(w, err)
		return
	}
	_ = lang
	_ = token
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) qrLeonPost(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	token := r.PathValue("token")
	apt, lang, ok := s.qrGate(ctx, token)
	if !ok {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live || !s.leonOn(*apt) {
		s.leonGone(w)
		return
	}
	_ = s.qrRateRecord(ctx, clientip.Key(r, s.getenv, "guide_qr"))
	_ = r.ParseForm()
	cid := ""
	for _, c := range r.Cookies() {
		if c.Name == leonCookieName {
			cid = c.Value
		}
	}
	fresh := cid == "" || !lqClientID.MatchString(cid)
	if fresh {
		cid = newLeonCookieID()
	}
	body, err := s.guestLeonPost(ctx, apt, "qr", 0, cid, lang, r.FormValue("message"), r.FormValue("client_id"), clientip.Key(r, s.getenv, "leon"))
	if err != nil {
		lqFail(w, err)
		return
	}
	if fresh {
		http.SetCookie(w, &http.Cookie{
			Name: leonCookieName, Value: cid, Path: "/g/" + token, MaxAge: leonCookieDays * 24 * 3600,
			HttpOnly: true, SameSite: http.SameSiteLaxMode, Secure: s.getenv("UBYHOST_SECURE_COOKIES") == "1",
		})
	}
	s.leonJSON(w, body, http.StatusOK)
}

func newLeonCookieID() string {
	return fmt.Sprintf("lq%x", time.Now().UnixNano())
}

func (s *lqServer) qrRateRecord(ctx context.Context, key string) error {
	store := ai.HavelStore{Pool: s.pool}
	return store.Record(ctx, "guide_qr", key, s.now())
}

func (s *lqServer) guestLeonPost(ctx context.Context, apt *leonApt, door string, resID int64, cookie, lang, message, clientID, addrKey string) (map[string]any, error) {
	chatID, err := s.ensureChat(ctx, apt.ID, door, resID, cookie, lang)
	if err != nil {
		return nil, err
	}
	ls := ai.LeonStore{HavelStore: ai.HavelStore{Pool: s.pool, Env: s.lookupEnv}}
	host := ""
	var hostName string
	_ = s.pool.QueryRow(ctx, `SELECT COALESCE(le.name,'') FROM apartment a LEFT JOIN legal_entity le ON le.id = a.legal_entity_id WHERE a.id = $1`, apt.ID).Scan(&hostName)
	_ = host
	la := ai.LeonApartment{ID: apt.ID, Name: apt.Name, Enabled: apt.LeonEnabled, TermsVersion: apt.LeonTermsVer}
	level := "everyone"
	if door == "stay" {
		level = "booked"
	}
	res, err := ls.TryReply(ctx, s.model, la, message, lang, hostName, s.now())
	if err != nil {
		return nil, err
	}
	out := map[string]any{"kind": res.Kind, "text": res.Text, "asked_host": res.WouldAsk}
	if message == "" || len(message) > leonMaxMsg {
		return map[string]any{"kind": "too_long", "text": "Message too long.", "asked_host": false}, nil
	}
	if res.Kind == "too_long" || res.Kind == "smalltalk" || res.Kind == "unclear" {
		return out, nil
	}
	if res.Kind == "cap" || res.Kind == "no_guide" || res.Text == "" {
		out["text"] = res.Text
		if res.Kind == "passed" || res.WouldAsk {
			out["asked_host"] = true
		}
		return out, nil
	}
	// store guest + leon turn when we would on the live server
	stamp := s.stamp(s.now())
	_, _ = s.pool.Exec(ctx, `INSERT INTO guest_chat_message (chat_id, role, kind, text, sources, created_at, client_id) VALUES ($1, 'guest', '', $2, '', $3, $4)`, chatID, ai.LeonRedact(message), stamp, clientID)
	_, _ = s.pool.Exec(ctx, `INSERT INTO guest_chat_message (chat_id, role, kind, text, sources, created_at) VALUES ($1, 'leon', $2, $3, '', $4)`, chatID, res.Kind, res.Text, stamp)
	_ = level
	return out, nil
}

func (s *lqServer) ensureChat(ctx context.Context, apt int64, door string, resID int64, cookie, lang string) (int64, error) {
	var id int64
	if door == "stay" {
		err := s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'stay' AND reservation_id = $1`, resID).Scan(&id)
		if err == nil {
			return id, nil
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, err
		}
	} else {
		err := s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'qr' AND apartment_id = $1 AND cookie_id = $2`, apt, cookie).Scan(&id)
		if err == nil {
			return id, nil
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, err
		}
	}
	stamp := s.stamp(s.now())
	err := s.pool.QueryRow(ctx, `INSERT INTO guest_chat (apartment_id, door, reservation_id, cookie_id, lang, created_at, last_message_at)
		VALUES ($1, $2, $3, $4, $5, $6, $6) RETURNING id`, apt, door, sqlNullInt(resID), sqlNullStr(cookie), lang, stamp).Scan(&id)
	return id, err
}

func sqlNullInt(v int64) any {
	if v == 0 {
		return nil
	}
	return v
}

func sqlNullStr(v string) any {
	if v == "" {
		return nil
	}
	return v
}
