package staydetail

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func TestMissingDetailsSummary(t *testing.T) {
	sixIssues := []validation.Issue{
		{Field: "birth_date", Severity: "error", Message: "bad birth date"},
		{Field: "res_street", Severity: "error", Message: "missing street"},
		{Field: "res_city", Severity: "error", Message: "missing city"},
		{Field: "res_country", Severity: "error", Message: "missing country"},
		{Field: "purpose", Severity: "error", Message: "missing purpose"},
		{Field: "signature", Severity: "error", Message: "missing signature"},
	}

	if got := missingDetailsSummary("en", sixIssues); got != "Missing: Birth date, Street, City +3 more" {
		t.Errorf("en 6 issues = %q", got)
	}
	if got := missingDetailsSummary("cs", sixIssues); got != "Chybí: Datum narození, Ulice, Město +3 další" {
		t.Errorf("cs 6 issues = %q", got)
	}
	if got := missingDetailsSummary("vi", sixIssues); got != "Thiếu: Ngày sinh, Đường, Thành phố +3 mục nữa" {
		t.Errorf("vi 6 issues = %q", got)
	}

	twoDup := []validation.Issue{
		{Field: "stay_from", Severity: "error"},
		{Field: "stay_to", Severity: "error"},
		{Field: "signature", Severity: "error"},
	}
	if got := missingDetailsSummary("en", twoDup); got != "Missing: Stay dates, Signature" {
		t.Errorf("deduped 2 labels = %q", got)
	}

	unknown := []validation.Issue{{Field: "custom_unknown", Severity: "error"}}
	if got := missingDetailsSummary("en", unknown); got != "1 detail missing" {
		t.Errorf("unknown fallback = %q", got)
	}
}
