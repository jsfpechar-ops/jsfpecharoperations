// Package statemachine holds the state-transition tables of the Python app
// (round 1 of docs/plans/explicit-state-machines.md) as Go data, so that no
// table has to be re-derived when a domain is ported to Go.
//
// Nothing calls this package yet. App/tests/test_sm_go_parity.py parses this
// file as text and fails when a table here differs from its Python table.
// Change a table in both places in the same PR.
//
// Layout the parity test depends on (keep it, gofmt aligns the values):
//
//	"table.column": {                    one machine, opened on its own line
//		"from": {"to1", "to2"},          one row per line, sorted, double quotes
//		"end": {},                       a state with no way out is an empty row
//	},                                   the machine is closed with a tab then "},"
package statemachine

import "sort"

// NoRow is the "from" state of a move that creates the row (the INSERT), and
// the Python None key. It is never a "to" state. The tables spell it as the
// literal "<none>"; TestNoRowMatchesTables keeps the two in step. No machine
// has a NULL state: a NULL column is reported as NoRow by the caller.
const NoRow = "<none>"

// Tables maps "table.column" to from-state to the sorted list of states the
// code may move to. Every state a machine can hold is a key of its machine,
// so a state with no way out is a key with an empty list.
var Tables = map[string]map[string][]string{
	"ad_click.send_state": {
		"<none>":    {"pending"},
		"expired":   {},
		"failed":    {},
		"pending":   {"expired", "sending", "withdrawn"},
		"sending":   {"failed", "pending", "sent", "withdrawn"},
		"sent":      {},
		"withdrawn": {},
	},
	"billing_account.status": {
		"active":        {"canceling", "overdue"},
		"canceling":     {"active", "paused"},
		"overdue":       {"active", "paused"},
		"paused":        {"active"},
		"trial_pending": {"trialing"},
		"trialing":      {"active", "paused"},
	},
	"cleaning_code.state": {
		"active":         {"active", "detached", "revoke_pending", "revoked"},
		"detached":       {},
		"failed":         {"retrying", "revoke_pending"},
		"issuing":        {"active", "failed", "retrying", "revoke_pending"},
		"pending":        {"issuing", "revoke_pending", "revoked"},
		"retrying":       {"issuing", "revoke_pending"},
		"revoke_failed":  {"revoke_pending"},
		"revoke_pending": {"revoke_pending", "revoking"},
		"revoked":        {"revoke_pending"},
		"revoking":       {"revoke_failed", "revoke_pending", "revoked"},
	},
	"door_code.state": {
		"expired":        {},
		"failed":         {},
		"issued":         {"expired", "pending", "revoke_pending"},
		"issuing":        {"expired", "failed", "issued", "pending", "retrying"},
		"pending":        {"expired", "issuing", "revoked"},
		"retrying":       {"expired", "issuing", "revoked"},
		"revoke_failed":  {"issued"},
		"revoke_pending": {"issued", "revoke_failed", "revoked"},
		"revoked":        {},
	},
	"email_outbox.state": {
		"bounced":    {},
		"complained": {},
		"failed":     {},
		"queued":     {"failed", "sending"},
		"sending":    {"failed", "queued", "sent"},
		"sent":       {},
	},
	"guest.submit_state": {
		"blocked":      {"error", "not_required", "pending", "sent"},
		"error":        {"blocked", "not_required", "pending", "sent"},
		"not_required": {"blocked", "error", "pending", "sent"},
		"pending":      {"blocked", "error", "not_required", "sent"},
		"sent":         {"blocked", "error", "pending"},
	},
	"guide_import.status": {
		"done":    {"expired", "failed", "used"},
		"expired": {},
		"failed":  {},
		"queued":  {"failed", "running"},
		"running": {"done", "failed"},
		"used":    {},
	},
	"payment_request.status": {
		"awaiting_payment": {"cancelled", "expired", "paid"},
		"cancelled":        {"paid"},
		"draft":            {"cancelled", "sent"},
		"expired":          {"paid"},
		"paid":             {},
		"sent":             {"awaiting_payment", "cancelled", "expired", "paid"},
	},
	"push_outbox.state": {
		"failed": {},
		"queued": {"failed", "sent"},
		"sent":   {},
	},
	"reservation_claim.state": {
		"<none>":      {"unclaimed"},
		"claimed":     {"claimed", "unclaimed"},
		"provisional": {"claimed", "provisional", "unclaimed"},
		"unclaimed":   {"provisional", "unclaimed"},
	},
	"site_booking.status": {
		"cancelled":      {"refunded"},
		"clash_refunded": {},
		"expired":        {"cancelled", "clash_refunded", "paid"},
		"paid":           {"cancelled", "clash_refunded", "refunded"},
		"pending":        {"clash_refunded", "expired", "paid"},
		"refunded":       {},
		"requested":      {"cancelled", "expired", "paid"},
	},
	"submission.state": {
		"<none>":  {"running"},
		"running": {"error", "ok", "ok_duplicate", "outcome_unknown", "partial", "transport_error"},
	},
}

// Machines returns the machine names ("table.column"), sorted.
func Machines() []string {
	names := make([]string, 0, len(Tables))
	for name := range Tables {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Allowed reports whether machine lists the move from to to. Pass NoRow as
// from for the INSERT that creates the row. An unknown machine or from state
// is not allowed. A move to the same state is allowed only where the table
// lists it.
func Allowed(machine, from, to string) bool {
	for _, next := range Tables[machine][from] {
		if next == to {
			return true
		}
	}
	return false
}
