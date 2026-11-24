package guest

// Brief 1726: ports App/app/routes/guest_leon.py and guest_questions.py.

import (
	"context"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guesthandoff"
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
var lqClientID = leonClientID

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
    "guest_guide.title": "Guest guide",
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
    "guest_question.dismiss": "Dismiss without answering",
    "guest_question.urgent_banner": "Leon (AI) read this as an emergency and showed the guest the emergency number and your emergency card. Call or write to the guest now if you can.",
    "guest_question.shown_to_guest": "The guest sees this on the guide page, word for word.",
    "guest_question.field.answer": "Answer",
    "guest_question.field.answer_help": "Plain text, up to %(max)s characters. Write it the way you would say it; no need to sign.",
    "guest_question.dismiss_help": "For a question that needs no answer. The guest is not told.",
    "guest_question.dismissed_banner": "You dismissed this question. You can still answer it.",
    "guest_question.card.title": "Add to guide",
    "guest_question.card.help": "Save this answer as a guide card, so Leon (AI) answers the next guest himself. You can edit the card afterwards.",
    "guest_question.card.button": "Add to guide",
    "guest_question.card.done": "This answer is in your guide.",
    "guest_question.card.open": "Open the card",
    "guest_guide.add.topic": "Topic",
    "guest_guide.more.title": "More",
    "guest_guide.topic.arrival": "Arrival and getting here",
    "guest_guide.topic.wifi": "Wi-Fi and TV",
    "guest_guide.topic.heating": "Heating and hot water",
    "guest_guide.topic.kitchen": "Kitchen",
    "guest_guide.topic.rooms": "Bedrooms",
    "guest_guide.topic.bathroom": "Bathroom and laundry",
    "guest_guide.topic.rules": "House rules",
    "guest_guide.topic.trash": "Trash",
    "guest_guide.topic.checkout": "Checkout",
    "guest_guide.topic.area": "Nearby",
    "guest_guide.topic.emergency": "Emergencies",
    "guest_question.send": "Send to guest",
    "guest_question.add_to_guide": "Add answer to guide",
    "guest_question.topic": "Topic",
    "flash.guest_question.sent": "Answer sent. The guest sees it on the guide page.",
    "flash.guest_question.dismissed": "Question dismissed.",
    "flash.guest_question.card": "Added to your guide. Check the card and save.",
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
    "guest_questions.empty.body": "Odpověď uvidí host v průvodci.",
    "guest_guide.title": "Průvodce pro hosty",
    "guest_questions.col.question": "Dotaz",
    "guest_questions.col.state": "Stav",
    "guest_questions.door.qr": "QR stránka",
    "guest_questions.door.stay": "odkaz na pobyt",
    "guest_questions.state.open": "Čeká",
    "guest_questions.state.answered": "Zodpovězeno",
    "guest_questions.state.dismissed": "Odloženo",
    "guest_questions.badge.urgent": "Naléhavé",
    "guest_questions.badge.unread": "Leon (AI) nečetl",
    "guest_question.title": "Dotaz hosta",
    "guest_question.asked": "Host se ptá",
    "guest_question.summary": "Stručně:",
    "guest_question.your_answer": "Vaše odpověď",
    "guest_question.answer_placeholder": "Napište odpověď pro hosta",
    "guest_question.dismiss": "Odložit bez odpovědi",
    "guest_question.urgent_banner": "Leon (AI) to vyhodnotil jako nouzi a ukázal hostovi tísňové číslo a vaši kartu Nouze. Pokud můžete, hostovi hned zavolejte nebo napište.",
    "guest_question.shown_to_guest": "Host ji uvidí na stránce průvodce slovo od slova.",
    "guest_question.field.answer": "Odpověď",
    "guest_question.field.answer_help": "Prostý text, nejvýše %(max)s znaků. Napište ji tak, jak byste ji řekli; podpis není třeba.",
    "guest_question.dismiss_help": "Pro dotaz, který odpověď nepotřebuje. Host se nic nedozví.",
    "guest_question.dismissed_banner": "Tento dotaz jste odložili. Pořád na něj můžete odpovědět.",
    "guest_question.card.title": "Přidat do průvodce",
    "guest_question.card.help": "Uložte odpověď jako kartu průvodce, aby příštímu hostovi odpověděl Leon (AI) sám. Kartu pak můžete upravit.",
    "guest_question.card.button": "Přidat do průvodce",
    "guest_question.card.done": "Tato odpověď je ve vašem průvodci.",
    "guest_question.card.open": "Otevřít kartu",
    "guest_guide.add.topic": "Téma",
    "guest_guide.more.title": "Další možnosti",
    "guest_guide.topic.arrival": "Příjezd a cesta",
    "guest_guide.topic.wifi": "Wi-Fi a televize",
    "guest_guide.topic.heating": "Topení a teplá voda",
    "guest_guide.topic.kitchen": "Kuchyně",
    "guest_guide.topic.rooms": "Ložnice",
    "guest_guide.topic.bathroom": "Koupelna a praní",
    "guest_guide.topic.rules": "Domácí pravidla",
    "guest_guide.topic.trash": "Odpad",
    "guest_guide.topic.checkout": "Odjezd",
    "guest_guide.topic.area": "V okolí",
    "guest_guide.topic.emergency": "Nouzové situace",
    "guest_question.send": "Odeslat hostovi",
    "guest_question.add_to_guide": "Přidat odpověď do průvodce",
    "guest_question.topic": "Téma",
    "flash.guest_question.sent": "Odpověď odeslána. Host ji uvidí na stránce průvodce.",
    "flash.guest_question.dismissed": "Dotaz odložen.",
    "flash.guest_question.card": "Přidáno do průvodce. Zkontrolujte kartu a uložte.",
    "flash.error.guest_question_empty": "Nejdřív napište odpověď.",
    "flash.error.guest_question_gone": "Tento dotaz už neexistuje.",
    "flash.error.guest_question_too_long": "Odpověď je příliš dlouhá. Zkraťte ji na 1000 znaků.",
    "flash.error.guest_question_not_answered": "Nejdřív na dotaz odpovězte, pak ho přidejte do průvodce."
  }
}`)

//go:embed templates/leon_questions.tmpl
var leonQuestionsFS embed.FS

var hostCatalog = hostweb.Load(lqI18n)

var lqPages = layout.MustParseFuncs(hostCatalog, template.FuncMap{
	"lqT": func(lang, key string, kv ...any) string {
		params := map[string]any{}
		for i := 0; i+1 < len(kv); i += 2 {
			if s, ok := kv[i].(string); ok {
				params[s] = kv[i+1]
			}
		}
		text := hostCatalog.T(lang, key, params)
		if text == key {
			text = hostweb.HostStrings.T(lang, key, params)
		}
		return text
	},
}, leonQuestionsFS, "templates/leon_questions.tmpl")

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
		h := rt.h
		if rt.method == http.MethodPost && (strings.HasPrefix(rt.path, "/l/") || strings.HasPrefix(rt.path, "/g/")) {
			h = WithPOSTCSRF(s.getenv, s.now, rt.h)
		}
		mux.Handle(pattern, wrap(rt.label, h))
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
	if _, err := s.handoffGet(r.Context(), q.apt, q.qid); err != nil {
		if errors.Is(err, errHandoffGone) {
			http.NotFound(w, r)
			return
		}
		lqFail(w, err)
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
	CreatedAt                       string
}

func (s *lqServer) handoffList(ctx context.Context, apt int64) ([]handoffRow, int, error) {
	const q = `SELECT q.id, q.chat_id, COALESCE(q.summary,''), q.status, COALESCE(c.door,''), COALESCE(m.text,''), COALESCE(q.urgent,0), COALESCE(q.triaged,0), COALESCE(q.answer,''), COALESCE(q.created_at,'')
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
		if err := rows.Scan(&row.ID, &row.ChatID, &row.Summary, &row.Status, &row.Door, &row.Question, &row.Urgent, &row.Triaged, &row.Answer, &row.CreatedAt); err != nil {
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
	const q = `SELECT q.id, q.chat_id, COALESCE(q.summary,''), q.status, COALESCE(c.door,''), COALESCE(m.text,''), COALESCE(q.urgent,0), COALESCE(q.triaged,0), COALESCE(q.answer,''), COALESCE(q.created_at,'')
		FROM guest_question q JOIN guest_chat c ON c.id = q.chat_id JOIN guest_chat_message m ON m.id = q.message_id
		WHERE q.id = $1 AND q.apartment_id = $2`
	var row handoffRow
	err := s.pool.QueryRow(ctx, q, qid, apt).Scan(&row.ID, &row.ChatID, &row.Summary, &row.Status, &row.Door, &row.Question, &row.Urgent, &row.Triaged, &row.Answer, &row.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, errHandoffGone
	}
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func (s *lqServer) handoffCardID(ctx context.Context, apt int64, row *handoffRow) (int64, error) {
	title := ""
	for _, text := range []string{row.Summary, row.Question} {
		if f := strings.Fields(text); len(f) > 0 {
			title = strings.Join(f, " ")
			break
		}
	}
	if title == "" {
		title = "Guest question"
	}
	if r := []rune(title); len(r) > 120 {
		title = strings.TrimSpace(string(r[:120]))
	}
	var id int64
	err := s.pool.QueryRow(ctx, `SELECT id FROM guide_item WHERE apartment_id = $1 AND kind = 'custom' AND title = $2 ORDER BY id DESC LIMIT 1`, apt, title).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	return id, err
}

var lqTopics = []string{"arrival", "wifi", "heating", "kitchen", "rooms", "bathroom", "rules", "trash", "checkout", "area", "emergency"}

func lqTopicOptions(lang string) [][]any {
	var out [][]any
	for _, t := range lqTopics {
		out = append(out, []any{t, hostCatalog.T(lang, "guest_guide.topic."+t, nil)})
	}
	return out
}

func lqDay(ts string) string {
	if len(ts) > 10 {
		return ts[:10]
	}
	return ts
}

func lqLines(text string) []string {
	var out []string
	for _, line := range strings.Split(text, "\n") {
		if strings.TrimSpace(line) != "" {
			out = append(out, line)
		}
	}
	return out
}

func (s *lqServer) handoffRefreshAlert(ctx context.Context, apt int64) error {
	_, err := guesthandoff.RefreshAlert(ctx, s.pool, s.getenv, s.now, apt)
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

func (s *lqServer) lqPageTitle(lang, name, aptName string) string {
	key := "guest_questions.title"
	if name == "guest_question.html" {
		key = "guest_question.title"
	}
	return hostCatalog.T(lang, key, nil) + " · " + aptName + " · UbyHost"
}

func (s *lqServer) lqBodyKind(name string) string {
	if name == "guest_question.html" {
		return "form"
	}
	return "list"
}

func (s *lqServer) renderHost(w http.ResponseWriter, r *http.Request, q *lqHostReq, name string, data map[string]any) {
	aptName, _ := data["ApartmentName"].(string)
	if aptName == "" {
		aptName = "…"
	}
	p := layout.Page{
		Title: s.lqPageTitle(q.lang, name, aptName), Nav: "apartments",
		BodyKind: s.lqBodyKind(name), V2: true, BackURL: fmt.Sprintf("/apartments/%d/page", q.apt),
		Status: http.StatusOK,
	}
	w.Header().Set("Cache-Control", "no-store")
	env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: q.at}
	if err := layout.Render(w, r, env, q.host, p, lqPages, name, data); err != nil {
		lqFail(w, err)
	}
}

func (s *lqServer) renderQuestion(w http.ResponseWriter, r *http.Request, q *lqHostReq, errKey string, status int) {
	ctx := r.Context()
	aptName, err := s.hostApartment(ctx, q.host.Workspace.ID, q.apt)
	if errors.Is(err, pgx.ErrNoRows) {
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
	var cardID int64
	if row.Status == "answered" {
		cardID, err = s.handoffCardID(ctx, q.apt, row)
		if err != nil {
			lqFail(w, err)
			return
		}
	}
	data := map[string]any{
		"Lang": q.lang, "QuestionID": q.qid, "ApartmentName": aptName,
		"Base":         fmt.Sprintf("/apartments/%d/guide/questions", q.apt),
		"QuestionText": row.Question, "Summary": row.Summary, "AnswerDraft": r.FormValue("answer"),
		"Error": errKey, "MaxChars": handoffAnswerMax,
		"Answered": row.Status == "answered" && row.Answer != "",
		"Status":   row.Status, "Urgent": row.Urgent == 1 && row.Status == "open", "Triaged": row.Triaged != 0,
		"Door": row.Door, "CreatedDay": lqDay(row.CreatedAt), "AnswerText": row.Answer, "CardID": cardID,
		"QuestionLines": lqLines(row.Question), "SummaryLines": lqLines(row.Summary), "AnswerLines": lqLines(row.Answer),
		"SummaryDiffers": row.Summary != "" && row.Summary != row.Question,
		"TopicOptions":   lqTopicOptions(q.lang), "ApartmentID": q.apt,
	}
	p := layout.Page{
		Title: s.lqPageTitle(q.lang, "guest_question.html", aptName), Nav: "apartments",
		BodyKind: "form", V2: true, BackURL: fmt.Sprintf("/apartments/%d/page", q.apt), Status: status,
	}
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
	lang, apt, res, ok := leonStayReady(r, s.pool, s.getenv, s.now, r.PathValue("token"), resID)
	if !ok || apt == nil {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live {
		s.leonGone(w)
		return
	}
	la, _, _ := s.leonApartment(ctx, apt.ID)
	on, err := s.leonSwitched(ctx, la)
	if err != nil || !on {
		s.leonGone(w)
		return
	}
	var chatID int64
	_ = s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'stay' AND reservation_id = $1`, res.ID).Scan(&chatID)
	body, err := s.conversation(ctx, chatID)
	if err != nil {
		lqFail(w, err)
		return
	}
	_ = lang
	_ = res
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) stayLeonPost(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	resID, _ := lqParseID(r.PathValue("reservation_id"))
	lang, apt, res, ok := leonStayReady(r, s.pool, s.getenv, s.now, r.PathValue("token"), resID)
	if !ok || apt == nil {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live {
		s.leonGone(w)
		return
	}
	la, _, _ := s.leonApartment(ctx, apt.ID)
	on, err := s.leonSwitched(ctx, la)
	if err != nil || !on {
		s.leonGone(w)
		return
	}
	_ = r.ParseForm()
	level := BookedLevel(res.DateFrom, res.DateTo, PragueToday(s.now))
	body, err := s.guestLeonPost(ctx, apt.ID, "stay", res.ID, "", lang, r.FormValue("message"), r.FormValue("client_id"), clientip.Key(r, s.getenv, "leon"), level, apt.Name)
	if err != nil {
		lqFail(w, err)
		return
	}
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) qrLeonGet(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	token := r.PathValue("token")
	lang, apt, ok := s.leonQRReady(r, token)
	if !ok || apt == nil {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live {
		s.leonGone(w)
		return
	}
	la, _, _ := s.leonApartment(ctx, apt.ID)
	on, err := s.leonSwitched(ctx, la)
	if err != nil || !on {
		s.leonGone(w)
		return
	}
	cid := ""
	for _, c := range r.Cookies() {
		if c.Name == leonCookieName {
			cid = c.Value
		}
	}
	var chatID int64
	if cid != "" && leonClientID.MatchString(cid) {
		_ = s.pool.QueryRow(ctx, `SELECT id FROM guest_chat WHERE door = 'qr' AND apartment_id = $1 AND cookie_id = $2`, apt.ID, cid).Scan(&chatID)
	}
	body, err := s.conversation(ctx, chatID)
	if err != nil {
		lqFail(w, err)
		return
	}
	_ = lang
	s.leonJSON(w, body, http.StatusOK)
}

func (s *lqServer) qrLeonPost(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	token := r.PathValue("token")
	lang, apt, ok := s.leonQRReady(r, token)
	if !ok || apt == nil {
		s.leonGone(w)
		return
	}
	live, err := s.guideLive(ctx, apt.ID)
	if err != nil || !live {
		s.leonGone(w)
		return
	}
	la, _, _ := s.leonApartment(ctx, apt.ID)
	on, err := s.leonSwitched(ctx, la)
	if err != nil || !on {
		s.leonGone(w)
		return
	}
	RateRecord(ctx, s.pool, "guide_qr", clientip.Key(r, s.getenv, "guide_qr"), s.now())
	_ = r.ParseForm()
	cid := ""
	for _, c := range r.Cookies() {
		if c.Name == leonCookieName {
			cid = c.Value
		}
	}
	fresh := cid == "" || !leonClientID.MatchString(cid)
	if fresh {
		cid = leonNewCookieID()
	}
	body, err := s.guestLeonPost(ctx, apt.ID, "qr", 0, cid, lang, r.FormValue("message"), r.FormValue("client_id"), clientip.Key(r, s.getenv, "leon"), "everyone", apt.Name)
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
