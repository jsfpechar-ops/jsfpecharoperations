package ubyport

import (
	"encoding/json"
	"strings"
)

// Go port of App/app/reporting.py plan_outcome: the pure decision of what each
// guest's row becomes after a UbyPort answer. No database, no network.
// App/tests/golden/ubyport/outcome/expected.json is the contract: every case
// in cases.json must come out of PlanOutcome as the same JSON.

// SubmissionMaxAutoAttempts mirrors SUBMISSION_MAX_AUTO_ATTEMPTS in Python.
const SubmissionMaxAutoAttempts = 1

// Guest states, as the Python SENT, ERROR and BLOCKED constants spell them.
const (
	outcomeSent    = "sent"
	outcomeError   = "error"
	outcomeBlocked = "blocked"
)

// OutcomeGuest is one entry of the guests list: the guest row fields the
// decision reads. Nullable columns are pointers; nil is SQL NULL.
type OutcomeGuest struct {
	ID                  int64   `json:"id"`
	ReservationID       *int64  `json:"reservation_id"`
	SubmitState         *string `json:"submit_state"`
	SubmittedAt         *string `json:"submitted_at"`
	SubmissionID        *int64  `json:"submission_id"`
	ReceiptSubmissionID *int64  `json:"receipt_submission_id"`
	SubmitAttempts      *int64  `json:"submit_attempts"`
}

// GuestWrite is one row update. A key missing from Values means "leave the
// column alone"; a nil value means SQL NULL.
type GuestWrite struct {
	ID     int64
	Values map[string]any
}

// MarshalJSON writes the golden form: [id, values].
func (w GuestWrite) MarshalJSON() ([]byte, error) {
	return json.Marshal([]any{w.ID, w.Values})
}

// OutcomePlan is the result of PlanOutcome, in the same shape as the Python dict.
type OutcomePlan struct {
	State            string       `json:"state"`
	Accepted         int          `json:"accepted"`
	Failed           int          `json:"failed"`
	Blocked          int          `json:"blocked"`
	FirstAccepts     int          `json:"first_accepts"`
	DuplicateAccepts int          `json:"duplicate_accepts"`
	GuestWrites      []GuestWrite `json:"guest_writes"`
	Exhausted        []int64      `json:"exhausted"`
}

// PlanOutcome decides each guest's new values and the batch state from a
// UbyPort answer. receiptLookup stands in for receipt_submission_id in Python.
func PlanOutcome(guests []OutcomeGuest, res SubmitResult, submissionID int64, now string, codebook map[string]string, severities map[string]int, receiptLookup func(id *int64) *int64) OutcomePlan {
	plan := OutcomePlan{GuestWrites: []GuestWrite{}, Exhausted: []int64{}}
	acceptedCount, failedCount, blockedCount := 0, 0, 0
	duplicateAccepts, firstAccepts := 0, 0
	headerErrors := res.HeaderErrors

	for index, guest := range guests {
		recordError := ""
		if index < len(res.RecordErrors) {
			recordError = res.RecordErrors[index]
		}
		state, messages := Classify(&headerErrors, &recordError, codebook, "en", severities)
		if state == "accepted" {
			var receipt any = int64PtrValue(guest.ReceiptSubmissionID)
			if res.ReceiptPDF != "" {
				receipt = submissionID
			}
			plan.GuestWrites = append(plan.GuestWrites, GuestWrite{
				ID: guest.ID,
				Values: map[string]any{
					"submit_state":          outcomeSent,
					"submitted_at":          now,
					"submission_id":         submissionID,
					"receipt_submission_id": receipt,
					"last_errors":           nil,
					"submit_attempts":       int64(0),
					"updated_at":            now,
				},
			})
			acceptedCount++
			firstAccepts++
			continue
		}

		newState := outcomeError
		if state == "not_correctable" {
			newState = outcomeBlocked
		}
		if RecordIsDuplicate(&recordError, codebook) {
			newState = outcomeSent
			duplicateAccepts++
		}
		attempts := int64(0)
		if newState != outcomeSent {
			attempts = autoAttempts(guest.SubmitAttempts) + 1
		}
		if newState == outcomeError && attempts >= SubmissionMaxAutoAttempts {
			plan.Exhausted = append(plan.Exhausted, guest.ID)
		}
		values := map[string]any{
			"submit_state":    newState,
			"submission_id":   submissionID,
			"last_errors":     strings.Join(messages, " | "),
			"submit_attempts": attempts,
			"updated_at":      now,
		}
		if newState == outcomeSent {
			values["submitted_at"] = now
			if guest.SubmittedAt != nil && *guest.SubmittedAt != "" {
				values["submitted_at"] = *guest.SubmittedAt
			}
			// A pointer already on file wins; otherwise look it up on the
			// submission that carried the guest before this one.
			if truthyID(guest.ReceiptSubmissionID) {
				values["receipt_submission_id"] = *guest.ReceiptSubmissionID
			} else {
				values["receipt_submission_id"] = int64PtrValue(receiptLookup(guest.SubmissionID))
			}
		}
		plan.GuestWrites = append(plan.GuestWrites, GuestWrite{ID: guest.ID, Values: values})
		switch newState {
		case outcomeSent:
			if guest.SubmitState == nil || *guest.SubmitState != outcomeSent {
				acceptedCount++
			}
		case outcomeError:
			failedCount++
		default:
			blockedCount++
		}
	}

	switch {
	case failedCount > 0 || blockedCount > 0:
		if acceptedCount > 0 {
			plan.State = "partial"
		} else {
			plan.State = "error"
		}
	case firstAccepts > 0:
		plan.State = "ok"
	case duplicateAccepts > 0:
		plan.State = "ok_duplicate"
	default:
		plan.State = "ok"
	}
	plan.Accepted = acceptedCount
	plan.Failed = failedCount
	plan.Blocked = blockedCount
	plan.FirstAccepts = firstAccepts
	plan.DuplicateAccepts = duplicateAccepts
	return plan
}

// autoAttempts mirrors Python auto_attempts: max(0, x or 0).
func autoAttempts(v *int64) int64 {
	if v == nil || *v < 0 {
		return 0
	}
	return *v
}

// truthyID is Python truthiness for an id: nil and 0 are both falsy.
func truthyID(p *int64) bool {
	return p != nil && *p != 0
}

// int64PtrValue turns a nullable id into a row value: nil becomes SQL NULL.
func int64PtrValue(p *int64) any {
	if p == nil {
		return nil
	}
	return *p
}
