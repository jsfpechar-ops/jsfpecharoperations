package ubyport

import "strings"

// FaultRow mirrors one row of App/app/ubyport/faults.py FAULT_ROWS (A1b P2).
type FaultRow struct {
	Key     string // error_code
	Match   string // compared case-insensitively with the cleaned fault text
	TextKey string // host copy key
}

// FaultRows is the fault table, in the same order as the Python table.
var FaultRows = []FaultRow{
	{"uby_runtime_no_errors", "Odpověď neobsahuje záznamy o chybách", "ubyport.fault.uby_runtime_no_errors"},
	{"uby_runtime", "Chyba běhu programu", "ubyport.fault.uby_runtime"},
}

const (
	FaultUnknownKey = "ubyport.fault.unknown"
	faultDetailCap  = 200
)

// faultRowFor returns the first row whose Match occurs in detail, case-insensitively.
func faultRowFor(detail string) (FaultRow, bool) {
	folded := strings.ToLower(detail)
	for _, row := range FaultRows {
		if strings.Contains(folded, strings.ToLower(row.Match)) {
			return row, true
		}
	}
	return FaultRow{}, false
}

// FaultCodeFor mirrors App/app/ubyport/faults.py code_for (A1b P1/P2): http_<status>
// for an HTTP answer that was not a success; the fault row key for a SOAP fault
// whose text matches a row; else "" (the shared fixture of PR 1058). It only picks the operator's key;
// behaviour is never chosen from message text.
func FaultCodeFor(cause, detail string) string {
	if (cause == "http4xx" || cause == "redirect") && strings.HasPrefix(detail, "HTTP ") {
		return "http_" + detail[5:]
	}
	if cause == "fault" {
		if row, ok := faultRowFor(detail); ok {
			return row.Key
		}
	}
	return ""
}

// FaultHostKey mirrors faults.host_copy_key: the host copy key for a SOAP fault, else "".
func FaultHostKey(cause, detail string) string {
	if cause != "fault" {
		return ""
	}
	if row, ok := faultRowFor(detail); ok {
		return row.TextKey
	}
	return FaultUnknownKey
}

// FaultHostDetail mirrors faults.host_detail: the cleaned text capped at 200 characters.
func FaultHostDetail(detail string) string {
	runes := []rune(detail)
	if len(runes) > faultDetailCap {
		return string(runes[:faultDetailCap])
	}
	return detail
}

// FaultAlertParams mirrors faults.fault_alert_params: the host copy key for a
// SOAP fault, and the capped text when no row matches. Empty for other causes.
func FaultAlertParams(cause, detail string) AlertParams {
	key := FaultHostKey(cause, detail)
	if key == "" {
		return AlertParams{}
	}
	params := AlertParams{"fault_text_key": key}
	if key == FaultUnknownKey {
		params["detail"] = FaultHostDetail(detail)
	}
	return params
}
