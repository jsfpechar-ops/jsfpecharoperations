package anthropic

// ai.go is the port of the part of App/app/ai.py that one feature needs:
// switches, the three spend caps, the usage ledger and call(). Same SQL
// effects (ai_usage upsert), same refusal reasons, same request bodies.

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"math"
	"strconv"
	"strings"
	"sync"
	"time"
	_ "time/tzdata" // Europe/Prague must load on a slim image

	"github.com/jackc/pgx/v5/pgxpool"
)

// Error is a failed, refused or unusable call (Python AIError and subclasses).
type Error struct {
	Reason   string
	Disabled bool // AIDisabled: the feature is off or has no key
	Budget   bool // AIBudgetError: Reason is month, day or key
}

func (e *Error) Error() string { return e.Reason }

// AsError returns the *Error inside err, or nil.
func AsError(err error) *Error {
	var e *Error
	if errors.As(err, &e) {
		return e
	}
	return nil
}

// Prices are USD per million tokens.
type Prices struct{ Input, Output, CacheRead, CacheWrite float64 }

// Config is config.py's AI block, read once from the environment.
type Config struct {
	Provider       string // "anthropic" or "mistral"
	Features       map[string]bool
	AnthropicKey   string
	MistralKey     string
	Model          string
	MistralModel   string
	MaxTokens      int
	MaxInputTokens int
	LongContext    int64
	Prices         Prices
	TimeZone       string
	lookup         func(string) (string, bool)
}

// ConfigFromEnv reads the same variables and defaults as config.py. A value
// that does not parse falls back to its default (Python would stop at import).
func ConfigFromEnv(lookup func(string) (string, bool)) Config {
	get := func(name, def string) string {
		if v, ok := lookup(name); ok {
			return v
		}
		return def
	}
	getInt := func(name string, def int) int {
		n, err := strconv.Atoi(strings.TrimSpace(get(name, strconv.Itoa(def))))
		if err != nil {
			return def
		}
		return n
	}
	provider := strings.ToLower(strings.TrimSpace(get("UBYHOST_AI_PROVIDER", "anthropic")))
	if provider != "anthropic" && provider != "mistral" {
		provider = "anthropic"
	}
	defaults := map[string]Prices{
		"anthropic": {Input: 0.10, Output: 0.50, CacheRead: 0.01, CacheWrite: 0.125},
		"mistral":   {Input: 0.10, Output: 0.30, CacheRead: 0.01, CacheWrite: 0.10},
	}[provider]
	price := func(name string, def float64) float64 {
		v, err := strconv.ParseFloat(strings.TrimSpace(get(name, "")), 64)
		if err != nil {
			return def
		}
		return v
	}
	features := map[string]bool{}
	for _, part := range strings.Split(get("UBYHOST_AI_FEATURES", ""), ",") {
		if p := strings.ToLower(strings.TrimSpace(part)); p != "" {
			features[p] = true
		}
	}
	return Config{
		Provider:       provider,
		Features:       features,
		AnthropicKey:   strings.TrimSpace(get("UBYHOST_ANTHROPIC_API_KEY", "")),
		MistralKey:     strings.TrimSpace(get("UBYHOST_MISTRAL_API_KEY", "")),
		Model:          get("UBYHOST_AI_MODEL", "claude-haiku-5-5"),
		MistralModel:   get("UBYHOST_MISTRAL_MODEL", "mistral-small-latest"),
		MaxTokens:      getInt("UBYHOST_AI_MAX_TOKENS", 4000),
		MaxInputTokens: min(getInt("UBYHOST_AI_MAX_INPUT_TOKENS", 60000), 60000),
		LongContext:    100000,
		Prices: Prices{
			Input:      price("UBYHOST_AI_PRICE_INPUT", defaults.Input),
			Output:     price("UBYHOST_AI_PRICE_OUTPUT", defaults.Output),
			CacheRead:  price("UBYHOST_AI_PRICE_CACHE_READ", defaults.CacheRead),
			CacheWrite: price("UBYHOST_AI_PRICE_CACHE_WRITE", defaults.CacheWrite),
		},
		TimeZone: "Europe/Prague",
		lookup:   lookup,
	}
}

func (c Config) capEnv(prefix, feature, def string) float64 {
	raw := def
	if c.lookup != nil {
		if v, ok := c.lookup(prefix + strings.ToUpper(feature)); ok {
			raw = v
		}
	}
	f, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
	if err != nil {
		f, _ = strconv.ParseFloat(def, 64)
	}
	return f
}

// MonthlyUSD is config.ai_monthly_usd: UBYHOST_AI_MONTHLY_USD_<FEATURE>, default 10 (guide_translate 2).
func (c Config) MonthlyUSD(feature string) float64 {
	def := "10"
	if feature == "guide_translate" {
		def = "2"
	}
	return c.capEnv("UBYHOST_AI_MONTHLY_USD_", feature, def)
}

// KeyDailyUSD is config.ai_key_daily_usd: UBYHOST_AI_KEY_DAILY_USD_<FEATURE>, default 0 (guide_translate 0.05); 0 means no cap.
func (c Config) KeyDailyUSD(feature string) float64 {
	def := "0"
	if feature == "guide_translate" {
		def = "0.05"
	}
	return c.capEnv("UBYHOST_AI_KEY_DAILY_USD_", feature, def)
}

// Enabled is ai.enabled: the feature is listed and the provider's key is set.
func (c Config) Enabled(feature string) bool {
	key := c.AnthropicKey
	if c.Provider == "mistral" {
		key = c.MistralKey
	}
	return c.Features[feature] && key != ""
}

// Tokens is a sum over ai_usage rows.
type Tokens struct{ In, CacheWrite, CacheRead, Out int64 }

// USD prices a token sum (ai._usd; the same float operations in the same order).
func (p Prices) USD(t Tokens) float64 {
	return (float64(t.In)*p.Input +
		float64(t.CacheWrite)*p.CacheWrite +
		float64(t.CacheRead)*p.CacheRead +
		float64(t.Out)*p.Output) / 1_000_000
}

// Service is ai.call for one process. Pool is used only inside methods.
type Service struct {
	Pool      *pgxpool.Pool
	Cfg       Config
	Anthropic Doer
	Mistral   MistralDoer
	Now       func() time.Time // default time.Now

	sum    func(ctx context.Context, feature, fromDay, toDay string, key *string) (Tokens, error)
	rec    func(ctx context.Context, feature, key string, u Usage) error
	mu     sync.Mutex
	warned map[string]bool
}

// NewService wires the real clients. It does not touch the pool or the network.
func NewService(pool *pgxpool.Pool, cfg Config) *Service {
	return &Service{Pool: pool, Cfg: cfg, Anthropic: NewClient(cfg.AnthropicKey), Mistral: NewMistralClient(cfg.MistralKey)}
}

// Enabled reports whether the feature may call a model.
func (s *Service) Enabled(feature string) bool { return s.Cfg.Enabled(feature) }

func (s *Service) now() time.Time {
	if s.Now != nil {
		return s.Now()
	}
	return time.Now()
}

func (s *Service) loc() *time.Location {
	l, err := time.LoadLocation(s.Cfg.TimeZone)
	if err != nil {
		return time.UTC
	}
	return l
}

// Today is ai.today(): the calendar date in config.TIMEZONE, as midnight.
func (s *Service) Today() time.Time {
	n := s.now().In(s.loc())
	return time.Date(n.Year(), n.Month(), n.Day(), 0, 0, 0, 0, n.Location())
}

func isoDay(d time.Time) string { return d.Format("2006-01-02") }

func (s *Service) tokens(ctx context.Context, feature, from, to string, key *string) (Tokens, error) {
	if s.sum != nil {
		return s.sum(ctx, feature, from, to, key)
	}
	q := `SELECT COALESCE(SUM(input_tokens), 0)::bigint, COALESCE(SUM(cache_write_tokens), 0)::bigint,
		COALESCE(SUM(cache_read_tokens), 0)::bigint, COALESCE(SUM(output_tokens), 0)::bigint
		FROM ai_usage WHERE feature = $1 AND day >= $2 AND day <= $3`
	args := []any{feature, from, to}
	if key != nil {
		q += " AND key = $4"
		args = append(args, *key)
	}
	var t Tokens
	err := s.Pool.QueryRow(ctx, q, args...).Scan(&t.In, &t.CacheWrite, &t.CacheRead, &t.Out)
	return t, err
}

// MonthSpendUSD is ai.month_spend_usd.
func (s *Service) MonthSpendUSD(ctx context.Context, feature string, day time.Time) (float64, error) {
	first := time.Date(day.Year(), day.Month(), 1, 0, 0, 0, 0, day.Location())
	t, err := s.tokens(ctx, feature, isoDay(first), isoDay(day), nil)
	return s.Cfg.Prices.USD(t), err
}

// DaySpendUSD is ai.day_spend_usd.
func (s *Service) DaySpendUSD(ctx context.Context, feature string, day time.Time) (float64, error) {
	t, err := s.tokens(ctx, feature, isoDay(day), isoDay(day), nil)
	return s.Cfg.Prices.USD(t), err
}

// KeyDaySpendUSD is ai.key_day_spend_usd.
func (s *Service) KeyDaySpendUSD(ctx context.Context, feature, key string, day time.Time) (float64, error) {
	t, err := s.tokens(ctx, feature, isoDay(day), isoDay(day), &key)
	return s.Cfg.Prices.USD(t), err
}

// DailyAllowanceUSD is ai.daily_allowance_usd: the budget left at the start of
// today, spread evenly over the days left in the month, today included.
func (s *Service) DailyAllowanceUSD(ctx context.Context, feature string, day time.Time) (float64, error) {
	daysLeft := time.Date(day.Year(), day.Month()+1, 0, 0, 0, 0, 0, day.Location()).Day() - day.Day() + 1
	month, err := s.MonthSpendUSD(ctx, feature, day)
	if err != nil {
		return 0, err
	}
	today, err := s.DaySpendUSD(ctx, feature, day)
	if err != nil {
		return 0, err
	}
	left := s.Cfg.MonthlyUSD(feature) - (month - today)
	return math.Max(0.0, left/float64(daysLeft)), nil
}

// BudgetFraction is ai.budget_fraction.
func (s *Service) BudgetFraction(ctx context.Context, feature string, day time.Time) (float64, error) {
	capUSD := s.Cfg.MonthlyUSD(feature)
	if capUSD <= 0 {
		return 1.0, nil
	}
	spent, err := s.MonthSpendUSD(ctx, feature, day)
	return spent / capUSD, err
}

// BudgetState is ai.budget_state: "ok", "month", "day" or "key". key is nil
// for a feature without a per-key cap.
func (s *Service) BudgetState(ctx context.Context, feature string, key *string, day time.Time) (string, error) {
	month, err := s.MonthSpendUSD(ctx, feature, day)
	if err != nil {
		return "", err
	}
	if month >= s.Cfg.MonthlyUSD(feature) {
		return "month", nil
	}
	today, err := s.DaySpendUSD(ctx, feature, day)
	if err != nil {
		return "", err
	}
	allowance, err := s.DailyAllowanceUSD(ctx, feature, day)
	if err != nil {
		return "", err
	}
	if today >= allowance {
		return "day", nil
	}
	keyCap := s.Cfg.KeyDailyUSD(feature)
	if key != nil && keyCap > 0 {
		spent, err := s.KeyDaySpendUSD(ctx, feature, *key, day)
		if err != nil {
			return "", err
		}
		if spent >= keyCap {
			return "key", nil
		}
	}
	return "ok", nil
}

// record is ai._record: one upsert per call.
func (s *Service) record(ctx context.Context, feature, key string, u Usage) error {
	if s.rec != nil {
		return s.rec(ctx, feature, key, u)
	}
	_, err := s.Pool.Exec(ctx,
		`INSERT INTO ai_usage (day, feature, key, requests, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens)
		 VALUES ($1, $2, $3, 1, $4, $5, $6, $7)
		 ON CONFLICT (day, feature, key) DO UPDATE SET
		 requests = ai_usage.requests + 1,
		 input_tokens = ai_usage.input_tokens + excluded.input_tokens,
		 cache_write_tokens = ai_usage.cache_write_tokens + excluded.cache_write_tokens,
		 cache_read_tokens = ai_usage.cache_read_tokens + excluded.cache_read_tokens,
		 output_tokens = ai_usage.output_tokens + excluded.output_tokens`,
		isoDay(s.Today()), feature, key, u.InputTokens, u.CacheCreationInputTokens, u.CacheReadInputTokens, u.OutputTokens)
	return err
}

// warnBudget stands in for ai._warn_budget. PARITY GAP: Python mails the
// operator once a month at 80 percent (mail_notify.ai_budget builds an HTML
// mail and calls mail.enqueue); that builder is in go/internal/mail, which is
// not this package's to use. Go logs one warning per feature and month instead.
func (s *Service) warnBudget(ctx context.Context, feature string) {
	frac, err := s.BudgetFraction(ctx, feature, s.Today())
	if err != nil {
		slog.Warn("ai budget check failed", "feature", feature)
		return
	}
	if frac < 0.8 {
		return
	}
	month := s.Today().Format("2006-01")
	s.mu.Lock()
	if s.warned == nil {
		s.warned = map[string]bool{}
	}
	seen := s.warned[feature+month]
	s.warned[feature+month] = true
	s.mu.Unlock()
	if !seen {
		slog.Warn("ai budget at 80 percent or more; operator mail is not sent by the Go port", "feature", feature, "month", month, "fraction", frac)
	}
}

func decodeObject(text string) (map[string]any, bool) {
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		return nil, false
	}
	m, ok := v.(map[string]any)
	return m, ok
}

// Call is ai.call: one structured-output request, the parsed JSON object back.
// key groups usage for the per-key cap (nil: no key). maxTokens 0 means the
// global cap. Errors are *Error for every refusal and model failure; a
// database error comes back as it is.
func (s *Service) Call(ctx context.Context, feature string, system []string, messages []Message, schema json.RawMessage, key *string, maxTokens int) (map[string]any, error) {
	if !s.Cfg.Enabled(feature) {
		return nil, &Error{Reason: "disabled", Disabled: true}
	}
	keyText := ""
	if key != nil {
		keyText = *key
	}
	state, err := s.BudgetState(ctx, feature, key, s.Today())
	if err != nil {
		return nil, err
	}
	if state != "ok" {
		return nil, &Error{Reason: state, Budget: true}
	}
	if EstimateInputTokens(system, messages) > s.Cfg.MaxInputTokens {
		slog.Warn("ai call refused", "feature", feature, "reason", "input_too_large")
		return nil, &Error{Reason: "input_too_large"}
	}
	limit := s.Cfg.MaxTokens
	if maxTokens > 0 && maxTokens < limit {
		limit = maxTokens
	}
	if s.Cfg.Provider == "mistral" {
		return s.callMistral(ctx, feature, keyText, system, messages, schema, limit)
	}
	started := time.Now()
	resp, err := s.Anthropic.Create(ctx, Request{Model: s.Cfg.Model, MaxTokens: limit, System: system, Messages: messages, Schema: schema})
	if err != nil {
		slog.Warn("ai call failed", "feature", feature, "error", errKind(err))
		return nil, &Error{Reason: "api"}
	}
	if err := s.record(ctx, feature, keyText, resp.Usage); err != nil {
		return nil, err
	}
	s.warnBudget(ctx, feature)
	totalIn := resp.Usage.InputTokens + resp.Usage.CacheCreationInputTokens + resp.Usage.CacheReadInputTokens
	if totalIn > s.Cfg.LongContext {
		slog.Error("ai long context", "feature", feature, "in_total", totalIn)
	}
	slog.Info("ai call", "feature", feature, "request_id", resp.RequestID, "stop", resp.StopReason,
		"in", resp.Usage.InputTokens, "cache_w", resp.Usage.CacheCreationInputTokens,
		"cache_r", resp.Usage.CacheReadInputTokens, "out", resp.Usage.OutputTokens,
		"ms", time.Since(started).Milliseconds())
	switch resp.StopReason {
	case "refusal":
		return nil, &Error{Reason: "refusal"}
	case "max_tokens":
		return nil, &Error{Reason: "max_tokens"}
	}
	if !resp.HasText {
		return nil, &Error{Reason: "no_text"}
	}
	data, ok := decodeObject(resp.Text)
	if !ok {
		return nil, &Error{Reason: "json"}
	}
	return data, nil
}

func errKind(err error) string {
	var se *StatusError
	if errors.As(err, &se) {
		return "status_" + strconv.Itoa(se.Status)
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return "timeout"
	}
	return "network"
}

func (s *Service) callMistral(ctx context.Context, feature, key string, system []string, messages []Message, schema json.RawMessage, limit int) (map[string]any, error) {
	started := time.Now()
	resp, err := s.Mistral.Post(ctx, MistralRequest{
		Model: s.Cfg.MistralModel, MaxTokens: limit, System: strings.Join(system, "\n\n"), Messages: messages, Schema: schema,
	})
	if err != nil {
		slog.Warn("ai call failed", "provider", "mistral", "feature", feature, "error", errKind(err))
		return nil, &Error{Reason: "api"}
	}
	usage := Usage{InputTokens: resp.PromptTokens, OutputTokens: resp.CompletionTokens}
	if err := s.record(ctx, feature, key, usage); err != nil {
		return nil, err
	}
	s.warnBudget(ctx, feature)
	slog.Info("ai call", "provider", "mistral", "feature", feature, "stop", resp.FinishReason,
		"in", usage.InputTokens, "out", usage.OutputTokens, "ms", time.Since(started).Milliseconds())
	if resp.FinishReason == "length" || resp.FinishReason == "model_length" {
		return nil, &Error{Reason: "max_tokens"}
	}
	text, isString := resp.Content.(string)
	if !isString || strings.TrimSpace(text) == "" {
		return nil, &Error{Reason: "no_text"}
	}
	data, ok := decodeObject(text)
	if !ok {
		return nil, &Error{Reason: "json"}
	}
	return data, nil
}
