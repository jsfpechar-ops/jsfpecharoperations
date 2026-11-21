package envguard

import "testing"

func TestValidateStagingNoLogin_productionRefusesFlag(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_DEPLOYMENT":
			return "production"
		case "UBYHOST_STAGING_NO_LOGIN":
			return "1"
		default:
			return ""
		}
	}
	err := ValidateStagingNoLogin(getenv)
	if err == nil {
		t.Fatal("expected error on production with STAGING_NO_LOGIN")
	}
}

func TestValidateStagingNoLogin_prodUbyportRefusesFlag(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_DEPLOYMENT":
			return "staging"
		case "UBYHOST_UBYPORT_ENV":
			return "prod"
		case "UBYHOST_STAGING_NO_LOGIN":
			return "true"
		default:
			return ""
		}
	}
	err := ValidateStagingNoLogin(getenv)
	if err == nil {
		t.Fatal("expected error when UBYPORT_ENV=prod with STAGING_NO_LOGIN")
	}
}

func TestStagingNoLoginActive_stagingMock(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_DEPLOYMENT":
			return "staging"
		case "UBYHOST_UBYPORT_ENV":
			return "mock"
		case "UBYHOST_STAGING_NO_LOGIN":
			return "1"
		default:
			return ""
		}
	}
	if !StagingNoLoginActive(getenv) {
		t.Fatal("expected active on staging mock")
	}
}

func TestStagingNoLoginActive_ignoresOnProduction(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_DEPLOYMENT":
			return "production"
		case "UBYHOST_STAGING_NO_LOGIN":
			return "1"
		default:
			return ""
		}
	}
	if StagingNoLoginActive(getenv) {
		t.Fatal("must ignore flag on production")
	}
}
