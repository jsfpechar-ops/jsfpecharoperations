package ai

// leon_reply.go: leon.reply and leon._answer — one guest message in, one reply out, stored.

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guesthandoff"
)

const (
	leonHistoryTurns   = 6
	leonChatBurst      = 10
	leonAddrBurst      = 30
	leonRateWindow     = 15 * 60
	leonBusySeconds    = 60
	leonRefusalsPause  = 3
	leonPauseHours     = 24
	leonMaxPassedChars = 1000
	leonStayMaxDefault = 20
	leonQRMaxDefault   = 10
)

var leonClientID = regexp.MustCompile(`^[A-Za-z0-9_-]{8,40}$`)

// LeonReplyResult is the dict leon.reply returns.
type LeonReplyResult struct {
	Kind       string
	Text       string
	MessageID  *int64
	QuestionID *int64
}

// LeonChatRow is one guest_chat row.
type LeonChatRow struct {
	ID            int64
	ApartmentID   int64
	Door          string
	Lang          string
	ModelMessages int
	Refusals      int
	PausedUntil   string
	BusyUntil     string
}

func (s LeonStore) SwitchedOn(ctx context.Context, a LeonApartment) (bool, error) {
	if !a.Enabled || !LeonTermsCurrent(a) {
		return false, nil
	}
	return s.Offered(ctx, a)
}

func leonDoorCap(door string, env HavelEnv) int {
	name, def := "UBYHOST_LEON_QR_MAX", leonQRMaxDefault
	if door == "stay" {
		name, def = "UBYHOST_LEON_STAY_MAX", leonStayMaxDefault
	}
	if v, ok := env(name); ok {
		if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil {
			return n
		}
	}
	return def
}

func (s LeonStore) StayChat(ctx context.Context, apartmentID, resID int64, lang string, at time.Time) (*LeonChatRow, error) {
	var row LeonChatRow
	err := s.Pool.QueryRow(ctx, `SELECT id, apartment_id, door, COALESCE(lang,''), COALESCE(model_messages,0), COALESCE(refusals,0),
		COALESCE(paused_until,''), COALESCE(busy_until,'') FROM guest_chat WHERE door = 'stay' AND reservation_id = $1`, resID).
		Scan(&row.ID, &row.ApartmentID, &row.Door, &row.Lang, &row.ModelMessages, &row.Refusals, &row.PausedUntil, &row.BusyUntil)
	if err == nil {
		return &row, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return nil, err
	}
	stamp := at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
	err = s.Pool.QueryRow(ctx, `INSERT INTO guest_chat (apartment_id, door, reservation_id, lang, created_at, last_message_at)
		VALUES ($1, 'stay', $2, $3, $4, $4) RETURNING id, apartment_id, door, lang, model_messages, refusals, COALESCE(paused_until,''), COALESCE(busy_until,'')`,
		apartmentID, resID, lang, stamp).Scan(&row.ID, &row.ApartmentID, &row.Door, &row.Lang, &row.ModelMessages, &row.Refusals, &row.PausedUntil, &row.BusyUntil)
	return &row, err
}

func (s LeonStore) QRChat(ctx context.Context, apartmentID int64, cookie, lang string, at time.Time) (*LeonChatRow, error) {
	var row LeonChatRow
	err := s.Pool.QueryRow(ctx, `SELECT id, apartment_id, door, COALESCE(lang,''), COALESCE(model_messages,0), COALESCE(refusals,0),
		COALESCE(paused_until,''), COALESCE(busy_until,'') FROM guest_chat WHERE door = 'qr' AND apartment_id = $1 AND cookie_id = $2`,
		apartmentID, cookie).Scan(&row.ID, &row.ApartmentID, &row.Door, &row.Lang, &row.ModelMessages, &row.Refusals, &row.PausedUntil, &row.BusyUntil)
	if err == nil {
		return &row, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return nil, err
	}
	stamp := at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
	err = s.Pool.QueryRow(ctx, `INSERT INTO guest_chat (apartment_id, door, cookie_id, lang, created_at, last_message_at)
		VALUES ($1, 'qr', $2, $3, $4, $4) RETURNING id, apartment_id, door, lang, model_messages, refusals, COALESCE(paused_until,''), COALESCE(busy_until,'')`,
		apartmentID, cookie, lang, stamp).Scan(&row.ID, &row.ApartmentID, &row.Door, &row.Lang, &row.ModelMessages, &row.Refusals, &row.PausedUntil, &row.BusyUntil)
	return &row, err
}

func (s LeonStore) Reply(ctx context.Context, model HavelModel, chat *LeonChatRow, a LeonApartment, text, level, propertyName, hostName, addrKey, lang, clientID string, at time.Time) (LeonReplyResult, error) {
	chatID := chat.ID
	if lang == "" {
		lang = chat.Lang
	}
	if lang == "" {
		lang = "en"
	}
	text = havelStrip(text)
	local := func(kind, body string, store bool) (LeonReplyResult, error) {
		var mid *int64
		if store && body != "" {
			id, err := s.storeLeonMessage(ctx, chatID, "leon", kind, body, nil, "", at)
			if err != nil {
				return LeonReplyResult{}, err
			}
			mid = &id
		}
		return LeonReplyResult{Kind: kind, Text: body, MessageID: mid}, nil
	}
	if text == "" || havelLen(text) > LeonMaxMessageChars {
		return local("too_long", leonFixed(lang, "leon_too_long", map[string]any{"n": LeonMaxMessageChars}), false)
	}
	if chat.PausedUntil != "" && chat.PausedUntil > stampIso(at) {
		return local("paused", leonFixed(lang, "leon_paused", nil), false)
	}
	blocked, err := s.Blocked(ctx, "leon_chat", strconv.FormatInt(chatID, 10), leonChatBurst, leonRateWindow, at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	if blocked {
		return local("slow_down", leonFixed(lang, "leon_slow_down", nil), false)
	}
	blocked, err = s.Blocked(ctx, "leon_addr", addrKey, leonAddrBurst, leonRateWindow, at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	if blocked {
		return local("slow_down", leonFixed(lang, "leon_slow_down", nil), false)
	}
	until, took, err := s.takeLeonTurn(ctx, chatID, at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	if !took {
		return local("busy", leonFixed(lang, "leon_busy", nil), false)
	}
	defer func() {
		_, _ = s.Pool.Exec(ctx, `UPDATE guest_chat SET busy_until = NULL WHERE id = $1 AND busy_until = $2`, chatID, until)
	}()
	if clientID != "" && leonClientID.MatchString(clientID) {
		if rep, ok, err := s.leonReplay(ctx, chatID, clientID); err != nil {
			return LeonReplyResult{}, err
		} else if ok {
			return rep, nil
		}
	} else {
		clientID = ""
	}
	if clientID != "" {
		var exists int
		_ = s.Pool.QueryRow(ctx, `SELECT 1 FROM guest_chat_message WHERE chat_id = $1 AND client_id = $2 LIMIT 1`, chatID, clientID).Scan(&exists)
		if exists == 1 {
			clientID = ""
		}
	}
	return s.leonAnswer(ctx, model, chat, a, text, level, propertyName, hostName, addrKey, lang, clientID, at)
}

func stampIso(at time.Time) string {
	return at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

func (s LeonStore) takeLeonTurn(ctx context.Context, chatID int64, at time.Time) (until string, ok bool, err error) {
	now := stampIso(at)
	until = at.UTC().Add(leonBusySeconds*time.Second).Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
	tag, err := s.Pool.Exec(ctx, `UPDATE guest_chat SET busy_until = $1 WHERE id = $2 AND (busy_until IS NULL OR busy_until < $3)`,
		until, chatID, now)
	if err != nil {
		return "", false, err
	}
	return until, tag.RowsAffected() == 1, nil
}

func (s LeonStore) leonReplay(ctx context.Context, chatID int64, clientID string) (LeonReplyResult, bool, error) {
	var guestID int64
	err := s.Pool.QueryRow(ctx, `SELECT id FROM guest_chat_message WHERE chat_id = $1 AND client_id = $2`, chatID, clientID).Scan(&guestID)
	if errors.Is(err, pgx.ErrNoRows) {
		return LeonReplyResult{}, false, nil
	}
	if err != nil {
		return LeonReplyResult{}, false, err
	}
	var mid int64
	var kind, body string
	err = s.Pool.QueryRow(ctx, `SELECT id, kind, text FROM guest_chat_message WHERE chat_id = $1 AND role = 'leon' AND id > $2 ORDER BY id LIMIT 1`,
		chatID, guestID).Scan(&mid, &kind, &body)
	if errors.Is(err, pgx.ErrNoRows) {
		return LeonReplyResult{}, false, nil
	}
	if err != nil {
		return LeonReplyResult{}, false, err
	}
	var qid *int64
	var q int64
	err = s.Pool.QueryRow(ctx, `SELECT id FROM guest_question WHERE chat_id = $1 AND status = 'open' ORDER BY id DESC LIMIT 1`, chatID).Scan(&q)
	if err == nil {
		qid = &q
	}
	return LeonReplyResult{Kind: kind, Text: body, MessageID: &mid, QuestionID: qid}, true, nil
}

func (s LeonStore) storeLeonMessage(ctx context.Context, chatID int64, role, kind, text string, sources []int64, clientID string, at time.Time) (int64, error) {
	stamp := stampIso(at)
	src := ""
	if len(sources) > 0 {
		parts := make([]string, len(sources))
		for i, id := range sources {
			parts[i] = fmt.Sprintf("c%d", id)
		}
		src = strings.Join(parts, ",")
	}
	var mid int64
	err := s.Pool.QueryRow(ctx, `INSERT INTO guest_chat_message (chat_id, role, kind, text, sources, created_at, client_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`,
		chatID, role, kind, text, src, stamp, nullStr(clientID)).Scan(&mid)
	if err != nil {
		return 0, err
	}
	_, err = s.Pool.Exec(ctx, `UPDATE guest_chat SET last_message_at = $1 WHERE id = $2`, stamp, chatID)
	return mid, err
}

func nullStr(v string) any {
	if v == "" {
		return nil
	}
	return v
}

func (s LeonStore) leonHistory(ctx context.Context, chatID int64) ([]anthropic.Message, error) {
	rows, err := s.Pool.Query(ctx, `SELECT role, kind, text FROM guest_chat_message WHERE chat_id = $1 ORDER BY id DESC LIMIT $2`, chatID, leonHistoryTurns)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	type row struct{ role, kind, text string }
	var rev []row
	for rows.Next() {
		var r row
		if err := rows.Scan(&r.role, &r.kind, &r.text); err != nil {
			return nil, err
		}
		rev = append(rev, r)
	}
	var out []anthropic.Message
	merge := func(role, content string) {
		if len(out) > 0 && out[len(out)-1].Role == role {
			out[len(out)-1].Content += "\n" + content
			return
		}
		out = append(out, anthropic.Message{Role: role, Content: content})
	}
	for i := len(rev) - 1; i >= 0; i-- {
		r := rev[i]
		switch r.role {
		case "guest":
			merge("user", "<guest_message>\n"+leonClean(r.text)+"\n</guest_message>")
		case "leon":
			if r.kind == "answer" {
				merge("assistant", r.text)
			}
		case "host":
			merge("assistant", "(The host answered on the page: "+leonClean(r.text)+")")
		}
	}
	if len(out) > 0 && out[0].Role == "assistant" {
		out = out[1:]
	}
	if len(out) > 0 && out[len(out)-1].Role == "user" {
		out = out[:len(out)-1]
	}
	return out, nil
}

func (s LeonStore) leonAnswer(ctx context.Context, model HavelModel, chat *LeonChatRow, a LeonApartment, text, level, propertyName, hostName, addrKey, lang, clientID string, at time.Time) (LeonReplyResult, error) {
	chatID := chat.ID
	_ = s.Record(ctx, "leon_chat", strconv.FormatInt(chatID, 10), at)
	_ = s.Record(ctx, "leon_addr", addrKey, at)
	if small := LeonSmalltalkKind(text); small != "" {
		_, _ = s.storeLeonMessage(ctx, chatID, "guest", "", LeonRedact(text), nil, clientID, at)
		k := "leon_thanks"
		if small == "hi" {
			k = "leon_hi"
		}
		return s.replyLocal(ctx, chatID, "smalltalk", leonFixed(lang, k, nil), lang, true, at)
	}
	if LeonIsNoise(text) {
		_, _ = s.storeLeonMessage(ctx, chatID, "guest", "", LeonRedact(text), nil, clientID, at)
		return s.replyLocal(ctx, chatID, "unclear", leonFixed(lang, "leon_unclear", nil), lang, true, at)
	}
	redacted := LeonRedact(text)
	guestMID, err := s.storeLeonMessage(ctx, chatID, "guest", "", redacted, nil, clientID, at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	if twin, err := s.leonTwin(ctx, chatID, leonFold(redacted)); err != nil {
		return LeonReplyResult{}, err
	} else if twin != nil {
		if twin.status == "answered" {
			return s.replyLocal(ctx, chatID, "answered", leonFixed(lang, "leon_see_above", nil), lang, true, at)
		}
		body := leonFixed(lang, "leon_asked_already", nil)
		mid, err := s.storeLeonMessage(ctx, chatID, "leon", "ask_host", body, nil, "", at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		return LeonReplyResult{Kind: "ask_host", Text: body, MessageID: &mid, QuestionID: &twin.id}, nil
	}
	cards, err := s.GuestCards(ctx, a.ID, level)
	if err != nil {
		return LeonReplyResult{}, err
	}
	reason := ""
	var verdict *LeonVerdict
	used := chat.ModelMessages
	if len(cards) == 0 {
		reason = "no_guide"
	} else if mult, err := s.PlanMultiplier(ctx, a.ID); err != nil {
		return LeonReplyResult{}, err
	} else if mult <= 0 {
		reason = "cap"
	} else if used >= leonDoorCap(chat.Door, s.Env)*mult {
		reason = "cap"
	} else {
		history, err := s.leonHistory(ctx, chatID)
		if err != nil {
			return LeonReplyResult{}, err
		}
		history = append(history, anthropic.Message{Role: "user", Content: LeonUserTurn(redacted, lang)})
		key := strconv.FormatInt(a.ID, 10)
		data, err := model.Call(ctx, LeonFeature, LeonSystemBlocks(cards, propertyName), history, LeonSchema(), &key, LeonMaxTokens)
		if err != nil {
			if anthropic.AsError(err) == nil {
				return LeonReplyResult{}, err
			}
			reason = anthropic.AsError(err).Reason
		} else {
			_, _ = s.Pool.Exec(ctx, `UPDATE guest_chat SET model_messages = $1 WHERE id = $2`, used+1, chatID)
			v := LeonValidate(data, cards, redacted)
			verdict = &v
		}
	}
	if verdict == nil {
		_ = reason
		return s.leonPassed(ctx, chatID, a.ID, guestMID, redacted, hostName, lang, cards, at)
	}
	kind := verdict.Kind
	switch kind {
	case "refuse":
		refusals := chat.Refusals + 1
		paused := ""
		if refusals >= leonRefusalsPause {
			paused = at.UTC().Add(leonPauseHours*time.Hour).Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
			refusals = 0
		}
		_, _ = s.Pool.Exec(ctx, `UPDATE guest_chat SET refusals = $1, paused_until = $2 WHERE id = $3`, refusals, nullStr(paused), chatID)
		return s.replyLocal(ctx, chatID, "refuse", leonFixed(lang, "leon_refuse", nil), lang, true, at)
	case "about_me":
		return s.replyLocal(ctx, chatID, "about_me", leonFixed(lang, "leon_about", nil), lang, true, at)
	case "unclear":
		return s.replyLocal(ctx, chatID, "unclear", leonFixed(lang, "leon_unclear", nil), lang, true, at)
	case "answer":
		body := verdict.Text
		if verdict.Summary != "" {
			body += "\n" + leonFixed(lang, "leon_asked_host_part", nil)
		}
		var qid *int64
		if verdict.Summary != "" {
			id, err := s.openLeonQuestion(ctx, chatID, a.ID, guestMID, verdict.Summary, false, true, at)
			if err != nil {
				return LeonReplyResult{}, err
			}
			qid = &id
		}
		mid, err := s.storeLeonMessage(ctx, chatID, "leon", kind, body, verdict.Sources, "", at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		return LeonReplyResult{Kind: kind, Text: body, MessageID: &mid, QuestionID: qid}, nil
	case "emergency":
		body := LeonEmergencyText(lang, cards)
		qid, err := s.openLeonQuestion(ctx, chatID, a.ID, guestMID, verdict.Summary, true, true, at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		mid, err := s.storeLeonMessage(ctx, chatID, "leon", kind, body, nil, "", at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		return LeonReplyResult{Kind: kind, Text: body, MessageID: &mid, QuestionID: &qid}, nil
	default:
		body := leonNamed(lang, "leon_asked_host_sorry", hostName)
		if !verdict.Upset {
			body = leonNamed(lang, "leon_asked_host", hostName)
		}
		if verdict.Reason == "entry_code" {
			body = leonFixed(lang, "leon_entry_code_pointer", nil)
		}
		summary := verdict.Summary
		if summary == "" {
			summary = havelClip(redacted, LeonMaxSummaryChars)
		}
		qid, err := s.openLeonQuestion(ctx, chatID, a.ID, guestMID, summary, false, true, at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		k := "ask_host"
		if kind == "emergency" {
			k = kind
		}
		mid, err := s.storeLeonMessage(ctx, chatID, "leon", k, body, nil, "", at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		return LeonReplyResult{Kind: k, Text: body, MessageID: &mid, QuestionID: &qid}, nil
	}
}

func (s LeonStore) replyLocal(ctx context.Context, chatID int64, kind, body, lang string, store bool, at time.Time) (LeonReplyResult, error) {
	if !store {
		return LeonReplyResult{Kind: kind, Text: body}, nil
	}
	mid, err := s.storeLeonMessage(ctx, chatID, "leon", kind, body, nil, "", at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	return LeonReplyResult{Kind: kind, Text: body, MessageID: &mid}, nil
}

type leonTwin struct {
	id     int64
	status string
}

func (s LeonStore) leonTwin(ctx context.Context, chatID int64, folded string) (*leonTwin, error) {
	rows, err := s.Pool.Query(ctx, `SELECT q.id, q.status, m.text FROM guest_question q JOIN guest_chat_message m ON m.id = q.message_id
		WHERE q.chat_id = $1 AND q.status IN ('open', 'answered') ORDER BY q.id DESC LIMIT 20`, chatID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var status, text string
		if err := rows.Scan(&id, &status, &text); err != nil {
			return nil, err
		}
		if leonFold(text) == folded {
			return &leonTwin{id: id, status: status}, nil
		}
	}
	return nil, nil
}

func (s LeonStore) leonPassed(ctx context.Context, chatID, aptID, guestMID int64, redacted, hostName, lang string, cards []LeonCard, at time.Time) (LeonReplyResult, error) {
	urgent := LeonLooksDangerous(redacted)
	var pendingID int64
	var summary string
	err := s.Pool.QueryRow(ctx, `SELECT id, summary FROM guest_question WHERE chat_id = $1 AND status = 'open' AND triaged = 0 ORDER BY id DESC LIMIT 1`, chatID).Scan(&pendingID, &summary)
	if err == nil && !urgent {
		sum := havelClip(summary+"\n"+redacted, leonMaxPassedChars)
		_, _ = s.Pool.Exec(ctx, `UPDATE guest_question SET summary = $1 WHERE id = $2`, sum, pendingID)
		body := leonNamed(lang, "leon_passed_to_host", hostName)
		mid, err := s.storeLeonMessage(ctx, chatID, "leon", "passed", body, nil, "", at)
		if err != nil {
			return LeonReplyResult{}, err
		}
		return LeonReplyResult{Kind: "passed", Text: body, MessageID: &mid, QuestionID: &pendingID}, nil
	}
	if errors.Is(err, pgx.ErrNoRows) {
		err = nil
	}
	qid, err := s.openLeonQuestion(ctx, chatID, aptID, guestMID, havelClip(redacted, LeonMaxSummaryChars), urgent, !urgent, at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	kind := "passed"
	body := leonNamed(lang, "leon_passed_to_host", hostName)
	if urgent {
		kind = "emergency"
		body = LeonEmergencyText(lang, cards)
	}
	mid, err := s.storeLeonMessage(ctx, chatID, "leon", kind, body, nil, "", at)
	if err != nil {
		return LeonReplyResult{}, err
	}
	return LeonReplyResult{Kind: kind, Text: body, MessageID: &mid, QuestionID: &qid}, nil
}

func (s LeonStore) openLeonQuestion(ctx context.Context, chatID, aptID, msgID int64, summary string, urgent, triaged bool, at time.Time) (int64, error) {
	stamp := stampIso(at)
	var id int64
	u, t := 0, 0
	if urgent {
		u = 1
	}
	if triaged {
		t = 1
	}
	err := s.Pool.QueryRow(ctx, `INSERT INTO guest_question (chat_id, apartment_id, message_id, summary, status, answer, urgent, triaged, created_at)
		VALUES ($1, $2, $3, $4, 'open', '', $5, $6, $7) RETURNING id`,
		chatID, aptID, msgID, summary, u, t, stamp).Scan(&id)
	if err == nil {
		guesthandoff.OnNewQuestion(ctx, s.Pool, leonGetenv(s.Env), func() time.Time { return at }, id)
	}
	return id, err
}

func leonGetenv(env HavelEnv) func(string) string {
	return func(k string) string {
		v, _ := env(k)
		return v
	}
}

var leonDangerRE = regexp.MustCompile(`(?i)\b(fire|smoke|gas|flood\w*|blood|bleed\w*|unconscious|not breathing|hoří|požár|kouř|plyn|krev|krvác\w*|nedýchá|feuer|rauch|blut|bewusstlos|fuego|humo|sangre|incendie|fumée|sang|пожеж\w*|дим|газ|кров|112|150|155|158)\b`)

// LeonLooksDangerous is leon.looks_dangerous.
func LeonLooksDangerous(text string) bool {
	return leonDangerRE.MatchString(text)
}

// NewLeonCookieID matches leon.new_cookie_id shape.
func NewLeonCookieID() string {
	b := make([]byte, 18)
	_, _ = rand.Read(b)
	return base64URLEncode(b)
}

func base64URLEncode(b []byte) string {
	const alpha = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
	out := make([]byte, 24)
	for i := range out {
		out[i] = alpha[int(b[i%len(b)])%len(alpha)]
	}
	return string(out)
}
