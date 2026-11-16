package ubyport

import "strings"

// FaultCodeFor mirrors App/app/ubyport/faults.py code_for (A1b P1): http_<status>
// for an HTTP answer that was not a success, else "". It only picks the operator's
// key; behaviour is never chosen from message text.
func FaultCodeFor(cause, detail string) string {
	if (cause == "http4xx" || cause == "redirect") && strings.HasPrefix(detail, "HTTP ") {
		return "http_" + detail[5:]
	}
	return ""
}
