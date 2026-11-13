package mail

// Delivery half of App/app/mail.py (brief 1231): configuration, address helpers
// and the shared error values. Unexported names start with ob so they cannot
// clash with the message builders in this package.

import (
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Backend names, as UBYHOST_MAIL_BACKEND spells them.
const (
	BackendDisabled = "disabled"
	BackendConsole  = "console"
	BackendSES      = "ses"
)

// Config is everything one drain needs. Now, HTTPClient and SESEndpoint are
// injectable so tests need no clock, network or AWS account.
type Config struct {
	Backend         string
	Deployment      string
	From            string
	SESRegion       string
	AccessKeyID     string
	SecretAccessKey string
	Keys            *secure.MultiFernet
	Now             func() time.Time
	HTTPClient      *http.Client
	// SESEndpoint overrides https://email.<region>.amazonaws.com (tests only).
	SESEndpoint string
	// Details fills {{guest_details}} and {{receipt_details}} at send time.
	// Nil means the package default (obDefaultDetails, set by brief 1231b).
	Details DetailsRenderer
}

// Errors the delivery returns. None of them carries an address or a secret.
var (
	// ErrMailConfig is mail.MailConfigError.
	ErrMailConfig = errors.New("mail configuration error")
	// ErrDecryption is db.DecryptionError.
	ErrDecryption = errors.New("stored value could not be decrypted")
)

func obConfigErr(format string, args ...any) error {
	return fmt.Errorf("%w: %s", ErrMailConfig, fmt.Sprintf(format, args...))
}

// ConfigFromEnv reads the mail environment and applies validate_mail_env:
// an invalid backend, ses outside production or an incomplete ses setup is an
// error. The data keys are loaded only when a backend is on.
func ConfigFromEnv(getenv func(string) string) (Config, error) {
	cfg := Config{
		Backend:         strings.ToLower(strings.TrimSpace(obDefault(getenv("UBYHOST_MAIL_BACKEND"), BackendDisabled))),
		Deployment:      strings.ToLower(strings.TrimSpace(obDefault(getenv("UBYHOST_DEPLOYMENT"), "local"))),
		From:            strings.TrimSpace(getenv("UBYHOST_MAIL_FROM")),
		SESRegion:       strings.TrimSpace(obDefault(getenv("UBYHOST_SES_REGION"), "eu-central-1")),
		AccessKeyID:     strings.TrimSpace(getenv("UBYHOST_AWS_ACCESS_KEY_ID")),
		SecretAccessKey: strings.TrimSpace(getenv("UBYHOST_AWS_SECRET_ACCESS_KEY")),
	}
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	if cfg.Enabled() {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return Config{}, fmt.Errorf("mail data keys: %w", err)
		}
		cfg.Keys = keys
	}
	return cfg, nil
}

func obDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}

// Validate is validate_mail_env without the warnings.
func (c Config) Validate() error {
	switch c.Backend {
	case BackendDisabled, BackendConsole, BackendSES:
	default:
		return obConfigErr("UBYHOST_MAIL_BACKEND is invalid (use disabled, console, or ses)")
	}
	if c.Backend == BackendSES && c.Deployment != "production" {
		return obConfigErr("UBYHOST_MAIL_BACKEND=ses is only allowed on production; use console on staging")
	}
	if c.Backend == BackendSES {
		var missing []string
		for _, f := range []struct{ key, value string }{
			{"UBYHOST_SES_REGION", c.SESRegion},
			{"UBYHOST_MAIL_FROM", c.From},
			{"UBYHOST_AWS_ACCESS_KEY_ID", c.AccessKeyID},
			{"UBYHOST_AWS_SECRET_ACCESS_KEY", c.SecretAccessKey},
		} {
			if f.value == "" {
				missing = append(missing, f.key)
			}
		}
		if len(missing) > 0 {
			return obConfigErr("production SES is selected but incomplete: %s", strings.Join(missing, ", "))
		}
	}
	return nil
}

// Enabled is mail_enabled: console or ses.
func (c Config) Enabled() bool { return c.Backend == BackendConsole || c.Backend == BackendSES }

func (c Config) now() time.Time {
	if c.Now != nil {
		return c.Now().UTC()
	}
	return time.Now().UTC()
}

// DisplayFrom is display_from: a readable name in front of a bare address.
func (c Config) DisplayFrom() string { return DisplayFrom(c.From) }

// DisplayFrom is mail.display_from(address).
func DisplayFrom(address string) string {
	value := strings.TrimSpace(address)
	if value == "" || strings.Contains(value, "<") || !strings.Contains(value, "@") {
		return value
	}
	return "UbyHost <" + value + ">"
}

var obEmailRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

// obNormaliseEmail is mail.normalise_email for the two forms the app stores,
// a plain address or "Name <addr>" (the same rule as ubyport.NormaliseEmail,
// which this package cannot import).
func obNormaliseEmail(raw string) string {
	s := strings.TrimSpace(raw)
	if strings.ContainsAny(s, ",\"") || strings.Count(s, "<") > 1 || strings.Count(s, ">") > 1 {
		return ""
	}
	addr := s
	if i := strings.Index(s, "<"); i >= 0 {
		j := strings.Index(s, ">")
		if j < i || strings.TrimSpace(s[j+1:]) != "" {
			return ""
		}
		addr = s[i+1 : j]
	}
	addr = strings.ToLower(strings.TrimSpace(addr))
	if addr == "" || len(addr) > 254 || !obEmailRE.MatchString(addr) {
		return ""
	}
	return addr
}

// MaskEmail is mail.mask_email. A host part that is empty gives "" (Python
// raises IndexError there).
func MaskEmail(addr string) string {
	addr = strings.ToLower(strings.TrimSpace(addr))
	local, domain, ok := strings.Cut(addr, "@")
	if !ok || local == "" || domain == "" {
		return ""
	}
	lr := []rune(local)
	stars := len(lr) - 1
	if stars > 8 {
		stars = 8
	}
	if stars < 3 {
		stars = 3
	}
	parts := strings.Split(domain, ".")
	host := []rune(parts[0])
	if len(host) == 0 {
		return ""
	}
	rest := strings.Join(parts[1:], ".")
	hostStars := len(host) - 1
	if hostStars < 3 {
		hostStars = 3
	}
	out := string(lr[0]) + strings.Repeat("*", stars) + "@" + string(host[0]) + strings.Repeat("*", hostStars)
	if rest != "" {
		out += "." + rest
	}
	return out
}

var obAddrInText = regexp.MustCompile(`[^\s@<>"',;()]+@[^\s@<>"',;()]+`)

// obSafeError turns an error into the text kept in last_error and alerts: no
// address, cut to 400 characters.
func obSafeError(err error) string {
	text := obAddrInText.ReplaceAllString(err.Error(), "[address]")
	r := []rune(text)
	if len(r) > 400 {
		r = r[:400]
	}
	return string(r)
}

// obStamp is db.utcnow(): second precision, +00:00.
func obStamp(t time.Time) string { return t.UTC().Format("2006-01-02T15:04:05") + "+00:00" }

// obIsoNaive is datetime.isoformat() of a naive datetime: microseconds only
// when they are not zero.
func obIsoNaive(t time.Time) string {
	if t.Nanosecond()/1000 != 0 {
		return t.Format("2006-01-02T15:04:05.000000")
	}
	return t.Format("2006-01-02T15:04:05")
}

// obRow is the part of an email_outbox row delivery needs.
type obRow struct {
	ID            int64
	Kind          string
	ApartmentID   *int64
	ReservationID *int64
	To, CC        string
	CCRaw         *string
	Subject       string
	Payload       string
	Attempts      int64
}

// obRowColumns is the column list obRow.dest scans.
const obRowColumns = `id, kind, apartment_id, reservation_id, COALESCE(to_email, ''), COALESCE(cc_email, ''),
	COALESCE(subject, ''), COALESCE(payload, ''), attempts, cc_email`

func (r *obRow) dest() []any {
	return []any{&r.ID, &r.Kind, &r.ApartmentID, &r.ReservationID, &r.To, &r.CC, &r.Subject, &r.Payload, &r.Attempts, &r.CCRaw}
}
