package mail

import "strings"

// Host copy of a SOAP fault for the submission problem mail (A1b P2). Python
// (App/app/mail_notify.py) renders the same ubyport.fault.* copy; the match rows
// and the English texts are checked against the golden JSON written by
// App/scripts/ubyport_fault_golden.py (fault_copy_test.go).
type faultCopyRow struct {
	match   string
	textKey string
}

var faultCopyRows = []faultCopyRow{
	{"Odpověď neobsahuje záznamy o chybách", "ubyport.fault.uby_runtime_no_errors"},
	{"Chyba běhu programu", "ubyport.fault.uby_runtime"},
}

var faultCopyEN = map[string]string{
	"ubyport.fault.uby_runtime_no_errors": "UbyPort hit an internal error and returned no result. Nothing was filed. If it keeps failing, contact UbyPort support with the property's IDUB and the time.",
	"ubyport.fault.uby_runtime":           "UbyPort hit an internal error. Nothing was filed. If it keeps failing, contact UbyPort support.",
	"ubyport.fault.unknown":               "UbyPort answered with an error: %(detail)s. Nothing was filed.",
}

const faultDetailCap = 200

// faultReason returns the host copy for a SOAP fault, so the raw fault text never
// reaches the mail. The first matching row wins; other causes return reason unchanged.
func faultReason(cause, reason string) string {
	if cause != "fault" {
		return reason
	}
	folded := strings.ToLower(reason)
	key := "ubyport.fault.unknown"
	for _, row := range faultCopyRows {
		if strings.Contains(folded, strings.ToLower(row.match)) {
			key = row.textKey
			break
		}
	}
	runes := []rune(reason)
	if len(runes) > faultDetailCap {
		runes = runes[:faultDetailCap]
	}
	return strings.ReplaceAll(faultCopyEN[key], "%(detail)s", string(runes))
}
