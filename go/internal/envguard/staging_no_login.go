// Package envguard mirrors App/app/env_guard.py checks Go must enforce at startup.
package envguard

import (
	"fmt"
	"strings"
)

func deployment(getenv func(string) string) string {
	v := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_DEPLOYMENT")))
	if v == "" {
		return "local"
	}
	return v
}

func ubyportEnv(getenv func(string) string) string {
	v := strings.TrimSpace(getenv("UBYHOST_UBYPORT_ENV"))
	if v == "" {
		v = strings.TrimSpace(getenv("UBYPORT_ENV"))
	}
	return strings.ToLower(v)
}

func stagingNoLoginFlag(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAGING_NO_LOGIN"))) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}

// ValidateStagingNoLogin refuses to start when the bypass flag is set on production
// or with a live UbyPort (UBYHOST_UBYPORT_ENV=prod), matching env_guard.py.
func ValidateStagingNoLogin(getenv func(string) string) error {
	if !stagingNoLoginFlag(getenv) {
		return nil
	}
	deploy := deployment(getenv)
	uby := ubyportEnv(getenv)
	if deploy == "production" || uby == "prod" {
		return fmt.Errorf(
			"UBYHOST_STAGING_NO_LOGIN switches the login off and is only for staging; "+
				"remove it when UBYHOST_DEPLOYMENT=%s or UBYHOST_UBYPORT_ENV=%s",
			deploy, uby,
		)
	}
	return nil
}

// StagingNoLoginActive is auth.staging_no_login after env checks (staging deployment only).
func StagingNoLoginActive(getenv func(string) string) bool {
	if err := ValidateStagingNoLogin(getenv); err != nil {
		return false
	}
	return stagingNoLoginFlag(getenv) && deployment(getenv) == "staging"
}
