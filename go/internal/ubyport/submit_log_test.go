package ubyport

import (
	"strings"
	"testing"
)

func TestTransportLogLineHasParityFields(t *testing.T) {
	owner := int64(9)
	ref := ApartmentRef{ID: 5, OwnerUserID: &owner}
	ue := &Error{Kind: ErrTransport, Msg: "UbyPort returned a SOAP fault: Chyba", Cause: "fault"}
	line := transportLogLine(ref, 7, "test", "https://ubyport.invalid/ws", []int64{3, 4}, ue)
	for _, want := range []string{"apartment_id=", "owner_user_id=9", "submission_id=", "env=test",
		"endpoint=https://ubyport.invalid/ws", "guest_ids=[3 4]", "error_type=UbyportTransportError", "cause=fault"} {
		if !strings.Contains(line, want) {
			t.Errorf("log line missing %q: %s", want, line)
		}
	}
	if strings.Contains(line, "Chyba") {
		t.Errorf("log line carries message text: %s", line)
	}

	authLine := transportLogLine(ApartmentRef{ID: 5}, 7, "test", "https://ubyport.invalid/ws", []int64{3, 4},
		&Error{Kind: ErrAuth, Msg: "refused", Cause: "auth"})
	for _, want := range []string{"owner_user_id=None", "error_type=UbyportAuthError"} {
		if !strings.Contains(authLine, want) {
			t.Errorf("auth log line missing %q: %s", want, authLine)
		}
	}
}

func TestTransportAlertParamsNameTheThreeFieldsOnlyOnAFault(t *testing.T) {
	fault := transportAlertParams("Flat", "fault text", "fault")
	if fault["variant"] != "answered" || fault["header"] != "fault" {
		t.Errorf("fault params = %v", fault)
	}
	for _, cause := range []string{"auth", "http4xx", "redirect", "dial", "setup"} {
		if _, ok := transportAlertParams("Flat", "x", cause)["header"]; ok {
			t.Errorf("%s must not set header", cause)
		}
	}
	if transportAlertParams("Flat", "x", "auth")["variant"] != "auth" {
		t.Error("auth variant lost")
	}
	if _, ok := transportAlertParams("Flat", "x", "dial")["variant"]; ok {
		t.Error("dial must have no variant")
	}
}
