package layout

// shelldata.go is the rest of templating.render's shell context that 1380
// left out: the billing line (billing_trial.banner), Havel (havel_on,
// _havel_panel_state, havel_topics.ordered) and the security prompt
// (_security_prompt). Brief 1381.

import (
	"context"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// billingOn is billing.enabled() (UBYHOST_BILLING_ENABLED), as hostweb reads it.
func billingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// billingRow is the billing_account columns the shell reads; Status "" is no row.
type billingRow struct {
	Status      string `json:"status"`
	Plan        string `json:"plan"`
	TrialEndsAt string `json:"trial_ends_at"`
	PeriodEnd   string `json:"period_end"`
}

// billingLine is billing_trial.banner's dict.
type billingLine struct {
	Kind    string
	Warning bool
	Date    string
}

// billingBanner is billing_trial.banner for the workspace's row. today is the
// Prague date. A trial row whose end date will not parse shows nothing
// (Python raises there).
func billingBanner(on bool, acc billingRow, today time.Time) *billingLine {
	if !on || acc.Status == "" {
		return nil
	}
	switch acc.Status {
	case "trialing":
		if acc.Plan != "" {
			return nil
		}
		ends, err := time.Parse("2006-01-02", first(acc.TrialEndsAt, 10))
		if err != nil {
			return nil
		}
		left := int(ends.Sub(today).Hours() / 24)
		return &billingLine{Kind: "trial", Warning: left <= 3, Date: ends.Format("02.01.2006")}
	case "overdue", "paused":
		return &billingLine{Kind: acc.Status, Warning: true}
	case "canceling":
		return &billingLine{Kind: "canceling", Date: fmtDate(first(acc.PeriodEnd, 10))}
	}
	return nil
}

func first(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

// aiMultiplier is billing.entitlements(uid).ai_multiplier.
func aiMultiplier(on bool, acc billingRow) int {
	if !on || acc.Status == "" {
		return 1
	}
	switch acc.Status {
	case "paused":
		return 0
	case "trial_pending", "trialing":
		return 1
	}
	if acc.Plan == "max" {
		return 5
	}
	return 1
}

func csvSet(raw string) map[string]bool {
	out := map[string]bool{}
	for _, part := range strings.Split(raw, ",") {
		if p := strings.ToLower(strings.TrimSpace(part)); p != "" {
			out[p] = true
		}
	}
	return out
}

// havelOn is templating._havel_on: ai.enabled_for("havel", email): the feature
// is listed in UBYHOST_AI_FEATURES, the provider's key is set, and the
// signed-in account is on UBYHOST_AI_TEST_EMAILS while that list is set.
func havelOn(getenv func(string) string, email string) bool {
	if !csvSet(getenv("UBYHOST_AI_FEATURES"))["havel"] {
		return false
	}
	key := "UBYHOST_ANTHROPIC_API_KEY"
	if strings.ToLower(strings.TrimSpace(getenv("UBYHOST_AI_PROVIDER"))) == "mistral" {
		key = "UBYHOST_MISTRAL_API_KEY"
	}
	if strings.TrimSpace(getenv(key)) == "" {
		return false
	}
	list := csvSet(getenv("UBYHOST_AI_TEST_EMAILS"))
	return len(list) == 0 || list[strings.ToLower(strings.TrimSpace(email))]
}

// havel limits: havel.REFUSALS_MAX, BURST_MAX/BURST_WINDOW, config.HAVEL_*.
const (
	havelRefusalsMax = 3
	havelBurstMax    = 5
	havelBurstWindow = 600
)

func envInt(getenv func(string) string, key string, def int) int {
	if n, err := strconv.Atoi(strings.TrimSpace(getenv(key))); err == nil {
		return n
	}
	return def
}

// havelWindows is havel._since_week_start and _since_month_start for now.
func havelWindows(now time.Time) (week, month int64) {
	p := now.In(prague)
	day := time.Date(p.Year(), p.Month(), p.Day(), 0, 0, 0, 0, prague)
	weekStart := day.AddDate(0, 0, -((int(p.Weekday()) + 6) % 7))
	monthStart := time.Date(p.Year(), p.Month(), 1, 0, 0, 0, 0, prague)
	week = max(1, int64(p.Sub(weekStart).Seconds())+1)
	month = max(1, int64(p.Sub(monthStart).Seconds())+1)
	return week, month
}

// havelCountsSQL counts the four rate_limit_event scopes limit_state reads.
// Python prunes rows older than each window first (a DELETE); this read
// counts only the rows inside the window, which is the same number.
const havelCountsSQL = `SELECT
  COUNT(*) FILTER (WHERE scope = 'havel_refuse' AND at >= $2),
  COUNT(*) FILTER (WHERE scope = 'havel_burst' AND at >= $3),
  COUNT(*) FILTER (WHERE scope = 'havel_week' AND at >= $2),
  COUNT(*) FILTER (WHERE scope = 'havel_month' AND at >= $4)
  FROM rate_limit_event
 WHERE key = $1 AND scope IN ('havel_refuse', 'havel_burst', 'havel_week', 'havel_month')`

// havelCounts are the in-window event counts: refuse, burst, week, month.
type havelCounts [4]int64

func loadHavelCounts(ctx context.Context, pool *pgxpool.Pool, uid int64, now time.Time) (havelCounts, error) {
	week, month := havelWindows(now)
	t := float64(now.UnixNano()) / 1e9
	var c havelCounts
	err := pool.QueryRow(ctx, havelCountsSQL, strconv.FormatInt(uid, 10),
		t-float64(week), t-float64(havelBurstWindow), t-float64(month)).Scan(&c[0], &c[1], &c[2], &c[3])
	return c, err
}

// havelLimitState is havel.limit_state: "" when the host may send.
func havelLimitState(getenv func(string) string, c havelCounts, scale int) string {
	switch {
	case c[0] >= havelRefusalsMax:
		return "paused"
	case c[1] >= havelBurstMax:
		return "limit_burst"
	case c[2] >= int64(envInt(getenv, "UBYHOST_HAVEL_WEEKLY", 8)*scale):
		return "limit_week"
	case c[3] >= int64(envInt(getenv, "UBYHOST_HAVEL_MONTHLY", 15)*scale):
		return "limit_month"
	}
	return ""
}

// havelTopic is one entry of havel_topics.TOPICS as the panel shows it.
type havelTopic struct{ ID, Icon, Label string }

var havelTopics = []havelTopic{
	{"stays", "calendar-days", "havel.topic.stays"},
	{"guest_link", "external-link", "havel.topic.guest_link"},
	{"reporting", "send", "havel.topic.reporting"},
	{"calendars", "refresh-cw", "havel.topic.calendars"},
	{"wrong", "triangle-alert", "havel.topic.wrong"},
}

// havelFirstForNav is havel_topics.FIRST_FOR_NAV.
var havelFirstForNav = map[string]string{
	"cleaning": "stays", "reservations": "stays", "submissions": "reporting", "housebook": "reporting",
	"apartments": "guest_link", "dashboard": "reporting",
}

// orderedHavelTopics is havel_topics.ordered(nav).
func orderedHavelTopics(nav string) []havelTopic {
	out := append([]havelTopic{}, havelTopics...)
	firstID := havelFirstForNav[nav]
	sort.SliceStable(out, func(i, j int) bool { return out[i].ID == firstID && out[j].ID != firstID })
	return out
}

// pyQuote is urllib.parse.quote(s) (Jinja's urlencode filter on a string).
func pyQuote(s string) string {
	const hexDigits = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9', strings.IndexByte("_.-~/", c) >= 0:
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hexDigits[c>>4])
			b.WriteByte(hexDigits[c&15])
		}
	}
	return b.String()
}

// noSecurityPrompt is templating._NO_SECURITY_PROMPT.
var noSecurityPrompt = []string{"/account/2fa", "/settings", "/account/accept"}

// securityPromptDelay is SECURITY_PROMPT_DELAY_DAYS.
const securityPromptDelay = 7 * 24 * time.Hour

// parsePyISO is datetime.fromisoformat for the stored stamps; naive is UTC.
func parsePyISO(s string) (time.Time, bool) {
	for _, layout := range []string{
		"2006-01-02T15:04:05.999999999Z07:00", "2006-01-02 15:04:05.999999999Z07:00",
		"2006-01-02T15:04:05.999999999", "2006-01-02 15:04:05.999999999",
		"2006-01-02T15:04", "2006-01-02",
	} {
		if t, err := time.Parse(layout, s); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

// securityPrompt is _security_prompt()(): nil, or whether passkeys are offered.
// An unparseable signup_at shows nothing (Python raises there).
func securityPrompt(sh shell, path string, now time.Time, passkeys bool) *bool {
	if !sh.SignedIn || sh.TwoFactorDone || !sh.AccountIsWorkspace {
		return nil
	}
	for _, p := range noSecurityPrompt {
		if strings.HasPrefix(path, p) {
			return nil
		}
	}
	if sh.SignupAt != "" {
		started, ok := parsePyISO(sh.SignupAt)
		if !ok || now.Sub(started) < securityPromptDelay {
			return nil
		}
	}
	return &passkeys
}
