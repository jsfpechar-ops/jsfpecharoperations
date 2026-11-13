// Package lifecyclemail is the Go port of App/app/lifecycle_mail.py (the three
// setup tips to stalled hosts) with mail_notify.build_lifecycle and
// mail_notify.workspace_contact_emails. Same SQL, same queue rows, same bytes.
package lifecyclemail

import (
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Timezone is config.TIMEZONE: the day boundary of the daily check.
const Timezone = "Europe/Prague"

// Config is the part of App/app/config.py this job reads. Python reads it once
// at import time; ConfigFromEnv does the same once at start.
type Config struct {
	// LifecycleMail is UBYHOST_LIFECYCLE_MAIL in (1, true, yes): lower-cased, not trimmed.
	LifecycleMail bool
	// MailBackend is UBYHOST_MAIL_BACKEND (default disabled).
	MailBackend string
	// PublicBaseURL and AppBaseURL carry no trailing slash; AppBaseURL "" means PublicBaseURL.
	PublicBaseURL   string
	AppBaseURL      string
	OperatorName    string
	OperatorICO     string
	OperatorAddress string
	// OperatorEmail is the reply-to (default support@ubyhost.com).
	OperatorEmail string
	// SecretKey is read like config._load_secret but never minted: empty when absent,
	// and RunDaily then returns an error.
	SecretKey string
}

// ConfigFromEnv reads the environment through getenv (os.Getenv in production).
func ConfigFromEnv(getenv func(string) string) Config {
	public := strings.TrimRight(getenv("UBYHOST_PUBLIC_BASE_URL"), "/")
	if getenv("UBYHOST_PUBLIC_BASE_URL") == "" {
		public = "http://127.0.0.1:8080"
	}
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	if backend == "" {
		backend = "disabled"
	}
	email := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if email == "" {
		email = "support@ubyhost.com"
	}
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		secret = ""
	}
	return Config{
		LifecycleMail:   lifecycleSwitch(getenv("UBYHOST_LIFECYCLE_MAIL")),
		MailBackend:     backend,
		PublicBaseURL:   public,
		AppBaseURL:      strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"),
		OperatorName:    strings.TrimSpace(getenv("UBYHOST_OPERATOR_NAME")),
		OperatorICO:     strings.TrimSpace(getenv("UBYHOST_OPERATOR_ICO")),
		OperatorAddress: strings.TrimSpace(getenv("UBYHOST_OPERATOR_ADDRESS")),
		OperatorEmail:   email,
		SecretKey:       secret,
	}
}

func lifecycleSwitch(raw string) bool {
	switch strings.ToLower(raw) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// mailEnabled is mail.mail_enabled().
func (c Config) mailEnabled() bool {
	return c.MailBackend == "console" || c.MailBackend == "ses"
}

// appBaseURL is config.app_base_url().
func (c Config) appBaseURL() string {
	if c.AppBaseURL != "" {
		return c.AppBaseURL
	}
	return c.PublicBaseURL
}

// senderIdentified is lifecycle_mail.sender_identified: company, IČO and
// address are all set. No tip goes out without them.
func (c Config) senderIdentified() bool {
	return c.OperatorName != "" && c.OperatorICO != "" && c.OperatorAddress != ""
}
