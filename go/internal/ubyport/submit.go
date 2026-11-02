// SubmitBatch is the whole send of one batch of guests: it matches Python's
// reporting.submit_batch (App/app/reporting.py 1541-1842) line by line.
// Order of side effects: insert the running row, send, then the in-doubt,
// transport or answer branch, then the audit row. Mail and push are
// best-effort: their errors are logged and do not change the result.
package ubyport

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Sender is the part of *Client that SubmitBatch uses.
type Sender interface {
	Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error)
}

// BatchPair is one guest of the batch with its stay. Source is the reservation
// source; "demo" stays are dropped before anything is written (demo.is_demo_stay).
type BatchPair struct {
	Guest       Guest
	Reservation Reservation
	Outcome     OutcomeGuest
	Source      string
}

// BatchDeps holds the environment SubmitBatch needs. Endpoint is config.endpoint_for(env)
// as the caller resolves it. Now is used for mail and push; UTCNow for the DB rows.
type BatchDeps struct {
	Pool          *pgxpool.Pool
	Enc           FieldEncrypter
	Getenv        func(string) string
	AppBaseURL    string
	PublicBaseURL string
	Endpoint      string
	Codebook      map[string]string
	Severities    map[string]int
	Now           func() time.Time
}

// BatchResult is the summary Python's submit_batch returns.
type BatchResult struct {
	Submitted    int
	Failed       int
	Blocked      int
	SubmissionID int64
	State        string
	Error        string
	Stamp        string
}

const batchDemoSource = "demo"

// SubmitBatch sends pairs to UbyPort as one ZapisUbytovane and records the outcome.
// Transport and in-doubt problems are recorded and returned in the result, not as
// an error; an error is returned only for database or alert failures.
func SubmitBatch(ctx context.Context, d BatchDeps, s Sender, apt Apartment, ref ApartmentRef, pairs []BatchPair, mode string) (BatchResult, error) {
	real := make([]BatchPair, 0, len(pairs))
	for _, p := range pairs {
		if p.Source != batchDemoSource {
			real = append(real, p)
		}
	}
	if len(real) != len(pairs) {
		log.Printf("submit_batch_refused_demo_stay apartment_id=%d", ref.ID)
	}
	pairs = real
	if len(pairs) == 0 {
		return BatchResult{State: "noop"}, nil
	}

	header := Header(apt)
	guests := make([]map[string]any, 0, len(pairs))
	guestIDs := make([]int64, 0, len(pairs))
	outcomes := make([]OutcomeGuest, 0, len(pairs))
	byID := make(map[int64]BatchPair, len(pairs))
	for _, p := range pairs {
		guests = append(guests, GuestFields(p.Guest, p.Reservation))
		guestIDs = append(guestIDs, p.Outcome.ID)
		outcomes = append(outcomes, p.Outcome)
		byID[p.Outcome.ID] = p
	}

	subID, err := InsertSubmission(ctx, d.Pool, ref.ID, mode, guestIDs, d.Endpoint, UTCNow())
	if err != nil {
		return BatchResult{}, err
	}

	res, err := s.Submit(ctx, header, guests)
	if err != nil {
		var ue *Error
		if !errors.As(err, &ue) {
			return BatchResult{SubmissionID: subID}, err
		}
		if errors.Is(err, ErrOutcomeUnknown) {
			return batchOutcomeUnknown(ctx, d, ref, subID, guestIDs, ue)
		}
		return batchTransport(ctx, d, ref, subID, ue)
	}

	if err := ResolveAlert(ctx, d.Pool, fmt.Sprintf("submission_transport:%d", ref.ID)); err != nil {
		return BatchResult{}, err
	}

	lookup, err := ReceiptLookup(ctx, d.Pool, outcomes)
	if err != nil {
		return BatchResult{}, err
	}
	now := UTCNow()
	plan := PlanOutcome(outcomes, res, subID, now, d.Codebook, d.Severities, lookup)
	if err := RecordOutcome(ctx, d.Pool, d.Enc, subID, plan, res, now); err != nil {
		return BatchResult{}, err
	}

	name := ref.InternalName
	if err := batchStuck(ctx, d, ref, byID, plan.Exhausted); err != nil {
		return BatchResult{}, err
	}

	seen := map[int64]bool{}
	for _, p := range pairs {
		if p.Outcome.ReservationID == nil || seen[*p.Outcome.ReservationID] {
			continue
		}
		seen[*p.Outcome.ReservationID] = true
		if err := ClearStuckIfRecovered(ctx, d.Pool, *p.Outcome.ReservationID); err != nil {
			return BatchResult{}, err
		}
	}

	if plan.State == "ok" || plan.State == "ok_duplicate" {
		if err := ResolveAlert(ctx, d.Pool, fmt.Sprintf("submission_rejected:%d", ref.ID)); err != nil {
			return BatchResult{}, err
		}
		// The in-doubt card is apartment-wide: keep it while another guest is in doubt.
		inDoubt, err := ApartmentInDoubt(ctx, d.Pool, ref.ID)
		if err != nil {
			return BatchResult{}, err
		}
		if !inDoubt {
			if err := ResolveAlert(ctx, d.Pool, fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); err != nil {
				return BatchResult{}, err
			}
		}
	} else {
		log.Printf("ubyport_submission_rejected apartment_id=%d submission_id=%d state=%s accepted=%d failed=%d blocked=%d",
			ref.ID, subID, plan.State, plan.Accepted, plan.Failed, plan.Blocked)
		detailBits := []string{}
		headerText := ""
		if res.HeaderErrors != "" {
			parts := []string{}
			for _, c := range SplitCodes(&res.HeaderErrors) {
				parts = append(parts, Describe(c, d.Codebook, "en"))
			}
			headerText = strings.Join(parts, ", ")
			detailBits = append(detailBits, "Report header rejected: "+headerText)
		}
		detailBits = append(detailBits, fmt.Sprintf("%d record(s) to fix, %d that resending will not fix.", plan.Failed, plan.Blocked))
		detail := strings.Join(detailBits, " ")
		refused := plan.Failed + plan.Blocked
		if err := RaiseAlert(ctx, d.Pool, "critical", "submission_rejected",
			fmt.Sprintf("%s: UbyPort did not accept %d guest record(s).", name, refused), detail,
			fmt.Sprintf("submission_rejected:%d", ref.ID), &ref.ID, nil, nil,
			AlertParams{"property": name, "count": refused, "failed": plan.Failed, "blocked": plan.Blocked, "header": headerText},
		); err != nil {
			return BatchResult{}, err
		}
		batchMail(ctx, d, ref, subID, plan.State, detail, false)
		if _, err := QueueFilingProblemPush(ctx, d.Pool, d.Getenv, ref, subID, batchNow(d)); err != nil {
			log.Printf("filing_problem_push_failed submission_id=%d", subID)
		}
	}

	// The Dorucenka is kept: a first accept with neither stamp nor confirmation is flagged.
	if res.PseudoStamp != "" || res.ReceiptPDF != "" {
		if err := ResolveAlert(ctx, d.Pool, fmt.Sprintf("receipt_missing:%d", ref.ID)); err != nil {
			return BatchResult{}, err
		}
	} else if plan.State == "ok" && plan.FirstAccepts > 0 {
		if err := RaiseAlert(ctx, d.Pool, "warning", "receipt_missing",
			fmt.Sprintf("%s: UbyPort accepted the report but returned no confirmation.", name),
			fmt.Sprintf("Submission %d recorded %d accepted guest record(s) with no Dorucenka and no stamp behind them. "+
				"The register has them; ask the police for a copy if you need written proof.", subID, plan.FirstAccepts),
			fmt.Sprintf("receipt_missing:%d", ref.ID), &ref.ID, nil, nil,
			AlertParams{"property": name, "submission": subID, "count": plan.FirstAccepts},
		); err != nil {
			return BatchResult{}, err
		}
	}

	if err := Audit(ctx, d.Pool, "ubyport_submit",
		fmt.Sprintf("apartment=%d submission=%d state=%s accepted=%d failed=%d blocked=%d",
			ref.ID, subID, plan.State, plan.Accepted, plan.Failed, plan.Blocked),
		ref.OwnerUserID); err != nil {
		return BatchResult{}, err
	}

	return BatchResult{
		Submitted:    plan.Accepted,
		Failed:       plan.Failed,
		Blocked:      plan.Blocked,
		SubmissionID: subID,
		State:        plan.State,
		Stamp:        res.PseudoStamp,
	}, nil
}

// batchOutcomeUnknown is the in-doubt branch (reporting.py 1585-1612). The batch may
// be in the register, so it waits for a person; the envelope is kept encrypted.
func batchOutcomeUnknown(ctx context.Context, d BatchDeps, ref ApartmentRef, subID int64, guestIDs []int64, ue *Error) (BatchResult, error) {
	msg := ue.Error()
	log.Printf("ubyport_submission_outcome_unknown apartment_id=%d submission_id=%d guest_ids=%v", ref.ID, subID, guestIDs)
	if err := RecordOutcomeUnknown(ctx, d.Pool, d.Enc, subID, guestIDs, msg, ue.RequestXML, UTCNow()); err != nil {
		return BatchResult{}, err
	}
	name := ref.InternalName
	if err := RaiseAlert(ctx, d.Pool, "critical", "submission_outcome_unknown",
		fmt.Sprintf("%s: UbyPort may or may not have received the report.", name), msg,
		fmt.Sprintf("submission_outcome_unknown:%d", ref.ID), &ref.ID, nil, nil,
		AlertParams{"property": name, "error": msg},
	); err != nil {
		return BatchResult{}, err
	}
	batchMail(ctx, d, ref, subID, "transport_error", msg, true)
	return BatchResult{SubmissionID: subID, State: "outcome_unknown", Error: msg}, nil
}

// batchTransport is the transport branch (reporting.py 1613-1660). Guests stay pending.
func batchTransport(ctx context.Context, d BatchDeps, ref ApartmentRef, subID int64, ue *Error) (BatchResult, error) {
	msg := ue.Error()
	log.Printf("ubyport_submission_failed apartment_id=%d submission_id=%d", ref.ID, subID)
	if err := RecordTransportError(ctx, d.Pool, subID, msg, UTCNow()); err != nil {
		return BatchResult{}, err
	}
	name := ref.InternalName
	if err := RaiseAlert(ctx, d.Pool, "critical", "submission_transport",
		fmt.Sprintf("%s: could not deliver data to UbyPort.", name), msg,
		fmt.Sprintf("submission_transport:%d", ref.ID), &ref.ID, nil, nil,
		AlertParams{"property": name, "error": msg},
	); err != nil {
		return BatchResult{}, err
	}
	if errors.Is(ue, ErrAuth) {
		if err := RaiseAlert(ctx, d.Pool, "critical", "ubyport_auth_failed",
			fmt.Sprintf("%s: UbyPort refused the web-service login.", name), msg,
			fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil,
			AlertParams{"property": name},
		); err != nil {
			return BatchResult{}, err
		}
	}
	batchMail(ctx, d, ref, subID, "transport_error", msg, true)
	return BatchResult{SubmissionID: subID, State: "transport_error", Error: msg}, nil
}

// batchStuck raises one submission_stuck card per stay, in first-seen order
// (reporting.py 1718-1744). exhausted holds guest ids.
func batchStuck(ctx context.Context, d BatchDeps, ref ApartmentRef, byID map[int64]BatchPair, exhausted []int64) error {
	order := []int64{}
	names := map[int64][]string{}
	for _, gid := range exhausted {
		p := byID[gid]
		var rid int64
		if p.Outcome.ReservationID != nil {
			rid = *p.Outcome.ReservationID
		}
		if _, ok := names[rid]; !ok {
			order = append(order, rid)
		}
		names[rid] = append(names[rid], batchGuestName(p.Guest, gid))
	}
	for _, rid := range order {
		reservationID := rid
		if err := RaiseAlert(ctx, d.Pool, "warning", "submission_stuck",
			fmt.Sprintf("%d guest record(s) are no longer being sent automatically.", len(names[rid])),
			"UbyPort refused these records, and sending the same data again would only add "+
				"another refusal, so the automatic send has stopped offering them. Fix the guest "+
				"data, then send the stay again by hand: "+strings.Join(names[rid], ", "),
			fmt.Sprintf("submission_stuck:%d", rid), &ref.ID, &reservationID, nil, nil,
		); err != nil {
			return err
		}
	}
	return nil
}

// batchGuestName is the stuck-alert name: "<surname> <first_name>" stripped, else "#<id>".
func batchGuestName(g Guest, id int64) string {
	name := strings.TrimSpace(g.Surname + " " + g.FirstName)
	if name == "" {
		return fmt.Sprintf("#%d", id)
	}
	return name
}

// batchMail is mail_notify.submission_problem. Best-effort: the error is logged
// without the address or the reason text.
func batchMail(ctx context.Context, d BatchDeps, ref ApartmentRef, subID int64, state, reason string, transport bool) {
	if _, err := QueueSubmissionProblemMail(ctx, d.Pool, d.Getenv, d.AppBaseURL, d.PublicBaseURL,
		ref, subID, state, reason, transport, batchNow(d)); err != nil {
		log.Printf("submission_problem_mail_failed submission_id=%d", subID)
	}
}

func batchNow(d BatchDeps) time.Time {
	if d.Now == nil {
		return time.Now().UTC()
	}
	return d.Now()
}
