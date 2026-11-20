package doorcodes

import (
	"context"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// lcLock is a fake TTLock that also answers the LockCodes calls. Every hook succeeds by default.
// priorities holds the priority of every lock call, in order; deletes the code ids deleted.
type lcLock struct {
	create     func(priority string) (string, string, error)
	add        func(priority string) (string, string, error)
	del        func(codeID string) error
	listed     func(codeID string) (ttlock.TriState, error)
	priorities []string
	deletes    []string
	creates    int
}

func newLcLock() *lcLock {
	return &lcLock{
		create: func(string) (string, string, error) { return "123456", "code-1", nil },
		add:    func(string) (string, string, error) { return "654321", "custom-1", nil },
		del:    func(string) error { return nil },
		listed: func(string) (ttlock.TriState, error) { return ttlock.TriYes, nil },
	}
}

func (l *lcLock) Enabled() bool { return true }

func (l *lcLock) CreatePeriodCode(_ context.Context, _ int64, _ string, _, _ int64, _, priority string) (string, string, error) {
	l.creates++
	l.priorities = append(l.priorities, priority)
	return l.create(priority)
}

func (l *lcLock) AddCustomCode(_ context.Context, _ int64, _ string, _, _ int64, _, priority string) (string, string, error) {
	l.priorities = append(l.priorities, priority)
	return l.add(priority)
}

func (l *lcLock) FindCodeByName(_ context.Context, _ int64, _, _ string, _, _ int64) (string, string, bool, error) {
	return "", "", false, nil
}

func (l *lcLock) DeleteCode(_ context.Context, _ int64, _, codeID, priority string) error {
	l.deletes = append(l.deletes, codeID)
	l.priorities = append(l.priorities, priority)
	return l.del(codeID)
}

func (l *lcLock) CodeIsListed(_ context.Context, _ int64, _, _, codeID string) (ttlock.TriState, error) {
	return l.listed(codeID)
}

// lcNotice is one host notice the lifecycle asked for.
type lcNotice struct {
	ID     int64
	Stage  string
	Suffix string
}

type lcNotices struct{ calls []lcNotice }

func (n *lcNotices) DoorCodeNotice(_ context.Context, id int64, stage, keySuffix string) error {
	n.calls = append(n.calls, lcNotice{ID: id, Stage: stage, Suffix: keySuffix})
	return nil
}

func (n *lcNotices) count(stage string) int {
	c := 0
	for _, x := range n.calls {
		if x.Stage == stage {
			c++
		}
	}
	return c
}

// lcEnv is the phase-1 fixture (one issued-or-pending row for an active stay) with the lifecycle
// wrapped around its Service. The lock fake is the TTLock too.
type lcEnv struct {
	*fixture
	lc    *Lifecycle
	lk    *lcLock
	notes *lcNotices
}

func newLcEnv(t *testing.T) *lcEnv {
	t.Helper()
	f := newFixture(t)
	lk := newLcLock()
	f.svc.TTLock = lk
	notes := &lcNotices{}
	return &lcEnv{fixture: f, lc: &Lifecycle{Service: f.svc, Notices: notes, Locks: lk}, lk: lk, notes: notes}
}

// issued makes the row ISSUED with code-1 on the lock.
func (e *lcEnv) issued() {
	e.t.Helper()
	if !e.issue(false) {
		e.t.Fatal("issue did not succeed")
	}
}

func (e *lcEnv) setStay(status string) {
	e.exec("UPDATE reservation SET status = $1 WHERE id = $2", status, e.res)
}

func (e *lcEnv) cancelStay() { e.setStay("cancelled") }

func (e *lcEnv) advance(d time.Duration) { e.clk.t = e.clk.t.Add(d) }

func (e *lcEnv) cancelTick() {
	e.t.Helper()
	if err := e.lc.handleCancellations(e.ctx, iso(e.clk.t)); err != nil {
		e.t.Fatalf("handleCancellations: %v", err)
	}
}

func (e *lcEnv) moveTick() {
	e.t.Helper()
	if err := e.lc.handleMoves(e.ctx, iso(e.clk.t)); err != nil {
		e.t.Fatalf("handleMoves: %v", err)
	}
}

func (e *lcEnv) audited(action, detail string) bool {
	e.t.Helper()
	ok, err := e.svc.exists(e.ctx, "SELECT 1 FROM audit WHERE action = $1 AND detail = $2", action, detail)
	if err != nil {
		e.t.Fatal(err)
	}
	return ok
}

func (e *lcEnv) rowExists(id int64) bool {
	e.t.Helper()
	ok, err := e.svc.exists(e.ctx, "SELECT 1 FROM door_code WHERE id = $1", id)
	if err != nil {
		e.t.Fatal(err)
	}
	return ok
}

func (e *lcEnv) alertKinds() []string {
	var out []string
	for _, a := range e.alerts.raised {
		out = append(out, a.Kind)
	}
	return out
}

// wantMove fails when TRANSITIONS does not declare the move.
func wantMove(t *testing.T, from, to string) {
	t.Helper()
	if !allowedMove(from, to) {
		t.Fatalf("TRANSITIONS has no %s -> %s", from, to)
	}
}

func lcRefused(kind string, code int) *ttlock.TTLockError {
	return &ttlock.TTLockError{Code: code, Kind: kind, Message: "refused"}
}

// TestLcTransitionsDeclared checks every move the lifecycle makes against TRANSITIONS.
func TestLcTransitionsDeclared(t *testing.T) {
	for _, m := range [][2]string{
		{StatePending, StateRevoked},
		{StateRetrying, StateRevoked},
		{StateIssued, StateRevokePending},
		{StateRevokePending, StateRevoked},
		{StateRevokePending, StateRevokeFailed},
		{StateRevokePending, StateIssued},
		{StateRevokeFailed, StateIssued},
		{StateIssued, StatePending},
		{StatePending, StateIssuing},
		{StateIssuing, StateIssued},
	} {
		wantMove(t, m[0], m[1])
	}
}

func TestLcRevokeDeletesIssuedCodeWhenStayCancelled(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.cancelStay()
	e.cancelTick()
	// ISSUED -> REVOKE_PENDING, then the due query runs the revoke in the same tick.
	d := e.row(e.dc)
	wantState(t, d, StateRevoked, 1)
	wantMove(t, StateIssued, StateRevokePending)
	if d.PinEnc != nil {
		t.Fatal("pin_enc should be cleared on revoke")
	}
	if got := strings.Join(e.lk.deletes, ","); got != "code-1" {
		t.Fatalf("deletes=%q, want code-1", got)
	}
	if last := e.lk.priorities[len(e.lk.priorities)-1]; last != ttlock.PriorityCritical {
		t.Fatalf("delete priority=%q, want critical", last)
	}
	if !e.audited("door_code_revoked", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_revoked not audited")
	}
	if e.notes.count("cancelled_deleted") != 1 {
		t.Fatalf("cancelled_deleted notices=%d, want 1", e.notes.count("cancelled_deleted"))
	}
}

func TestLcRevokeRetriesGatewayErrorsAndNoticesOnThirdTry(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.del = func(string) error { return lcRefused(ttlock.KindTransient, 90000) }
	e.cancelStay()
	start := e.clk.t
	e.cancelTick()
	d := e.row(e.dc)
	wantState(t, d, StateRevokePending, 1)
	wantLastError(t, d, "transient")
	wantNext(t, d, start.Add(time.Minute))
	if e.notes.count("cancelled_not_deleted") != 0 {
		t.Fatal("no notice before the third try")
	}

	e.advance(time.Minute)
	e.cancelTick()
	d = e.row(e.dc)
	wantState(t, d, StateRevokePending, 2)
	wantNext(t, d, e.clk.t.Add(15*time.Minute))

	e.advance(15 * time.Minute)
	e.cancelTick()
	d = e.row(e.dc)
	wantState(t, d, StateRevokePending, 3)
	wantNext(t, d, e.clk.t.Add(60*time.Minute))
	if e.notes.count("cancelled_not_deleted") != 1 {
		t.Fatalf("cancelled_not_deleted=%d, want 1 on the third try", e.notes.count("cancelled_not_deleted"))
	}
}

func TestLcRevokeRefusedFailsThenStayReturnsRevivesPIN(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.del = func(string) error { return lcRefused(ttlock.KindPermission, 10005) }
	e.cancelStay()
	e.cancelTick()
	d := e.row(e.dc)
	wantState(t, d, StateRevokeFailed, 1)
	wantLastError(t, d, "permission")
	wantMove(t, StateRevokePending, StateRevokeFailed)
	if !e.audited("door_code_revoke_failed", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_revoke_failed not audited")
	}
	if e.notes.count("cancelled_not_deleted") != 1 {
		t.Fatalf("cancelled_not_deleted=%d, want 1", e.notes.count("cancelled_not_deleted"))
	}

	e.setStay("active")
	e.cancelTick()
	d = e.row(e.dc)
	wantState(t, d, StateIssued, 0)
	wantLastError(t, d, "")
	wantMove(t, StateRevokeFailed, StateIssued)
	if !e.audited("door_code_revoke_aborted", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_revoke_aborted not audited")
	}
	if len(e.lk.deletes) != 1 {
		t.Fatalf("deletes=%d, want only the first refused delete", len(e.lk.deletes))
	}
}

func TestLcRevokeReviveKeepsPINForPendingAndFailedRows(t *testing.T) {
	for _, state := range []string{StateRevokePending, StateRevokeFailed} {
		t.Run(state, func(t *testing.T) {
			e := newLcEnv(t)
			e.issued()
			e.exec("UPDATE door_code SET state = $1, attempts = 0 WHERE id = $2", state, e.dc)
			e.cancelTick()
			d := e.row(e.dc)
			wantState(t, d, StateIssued, 0)
			wantMove(t, state, StateIssued)
			if len(e.lk.deletes) != 0 {
				t.Fatal("a revived stay must not delete the code")
			}
		})
	}
}

func TestLcRevokeNoAccountFailsWithoutDeleting(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	if err := e.svc.Accounts.SetStatus(e.ctx, e.acc, "disabled", e.now); err != nil {
		t.Fatal(err)
	}
	e.cancelStay()
	e.cancelTick()
	d := e.row(e.dc)
	wantState(t, d, StateRevokeFailed, 1)
	wantLastError(t, d, "no_account")
	if len(e.lk.deletes) != 0 {
		t.Fatal("no account means no delete call")
	}
	if e.notes.count("cancelled_not_deleted") != 1 {
		t.Fatal("cancelled_not_deleted notice missing")
	}
}

func TestLcAlreadyGoneNeedsListingConfirmation(t *testing.T) {
	cases := []struct {
		name      string
		err       *ttlock.TTLockError
		listed    ttlock.TriState
		wantState string
		wantVia   string
	}{
		{"code_missing confirmed gone", lcRefused(ttlock.KindCodeMissing, -1007), ttlock.TriNo, StateRevoked, " via=gone:-1007"},
		{"code_missing still listed", lcRefused(ttlock.KindCodeMissing, -1007), ttlock.TriYes, StateRevokePending, ""},
		{"code_missing listing incomplete", lcRefused(ttlock.KindCodeMissing, -1007), ttlock.TriUnknown, StateRevokePending, ""},
		{"unmapped errcode confirmed gone", lcRefused(ttlock.KindTransient, 424242), ttlock.TriNo, StateRevoked, " via=gone:424242"},
		{"mapped permission not checked", lcRefused(ttlock.KindPermission, 10005), ttlock.TriNo, StateRevokeFailed, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			e := newLcEnv(t)
			e.issued()
			e.lk.del = func(string) error { return c.err }
			e.lk.listed = func(string) (ttlock.TriState, error) { return c.listed, nil }
			e.cancelStay()
			e.cancelTick()
			d := e.row(e.dc)
			if d.State != c.wantState {
				t.Fatalf("state=%s, want %s (last_error=%q)", d.State, c.wantState, derefOr(d.LastError, ""))
			}
			if c.wantVia != "" && !e.audited("door_code_revoked", fmt.Sprintf("door_code=%d%s", e.dc, c.wantVia)) {
				t.Fatalf("door_code_revoked with %q not audited", c.wantVia)
			}
		})
	}
}

func TestLcAmbiguousDeleteLookupsThenUnverifiedKeepsPIN(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.listed = func(string) (ttlock.TriState, error) { return ttlock.TriUnknown, nil }
	e.exec("UPDATE door_code SET state = $1, attempts = 2, last_error = 'network', next_attempt_at = NULL WHERE id = $2",
		StateRevokePending, e.dc)

	e.cancelTick()
	d := e.row(e.dc)
	wantState(t, d, StateRevokePending, 2)
	wantLastError(t, d, "lookup_failed:1")

	e.advance(3 * time.Minute) // the lease from the last lookup expires after LEASE_MINUTES
	e.cancelTick()
	d = e.row(e.dc)
	wantLastError(t, d, "lookup_failed:2")

	e.advance(3 * time.Minute)
	e.cancelTick()
	d = e.row(e.dc)
	wantState(t, d, StateIssued, 0)
	wantMove(t, StateRevokePending, StateIssued)
	wantLastError(t, d, "")
	if !e.audited("door_code_pin_unverified", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_pin_unverified not audited")
	}
	if len(e.alerts.raised) == 0 || e.alerts.raised[len(e.alerts.raised)-1].DedupeKey != fmt.Sprintf("door_code_pin_unverified:%d", e.res) {
		t.Fatalf("host warning not raised: %v", e.alertKinds())
	}
	if e.notes.count("pin_unverified") != 1 {
		t.Fatalf("pin_unverified notices=%d, want 1", e.notes.count("pin_unverified"))
	}
}

func TestLcHeldRevokeLookupKeepsDeleteAttemptCount(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.listed = func(string) (ttlock.TriState, error) { return ttlock.TriUnknown, nil }
	e.exec("UPDATE door_code SET state = $1, attempts = 1, last_error = 'network' WHERE id = $2", StateRevokePending, e.dc)
	if err := e.lc.revokeOne(e.ctx, e.dc); err != nil {
		t.Fatal(err)
	}
	d := e.row(e.dc)
	// revokeOne claimed the row (attempts 2); the failed lookup takes that claim back.
	wantState(t, d, StateRevokePending, 1)
	wantLastError(t, d, "lookup_failed:1")
	if len(e.lk.deletes) != 0 {
		t.Fatal("a lookup must not delete")
	}
}

func TestLcLookupFindsCodeGoneReissuesPIN(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.listed = func(string) (ttlock.TriState, error) { return ttlock.TriNo, nil }
	e.exec("UPDATE door_code SET state = $1, attempts = 2, last_error = 'network' WHERE id = $2", StateRevokePending, e.dc)
	e.cancelTick()

	d := e.row(e.dc)
	wantState(t, d, StateIssued, d.Attempts)
	if derefOr(d.ProviderCodeID, "") != "code-1" {
		t.Fatalf("provider_code_id=%q, want the re-issued code-1", derefOr(d.ProviderCodeID, ""))
	}
	wantMove(t, StateIssued, StatePending)
	if !e.audited("door_code_pin_reissued", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_pin_reissued not audited")
	}
	if e.notes.count("reissued") != 1 {
		t.Fatalf("reissued notices=%d, want 1", e.notes.count("reissued"))
	}
	found := false
	for _, a := range e.alerts.raised {
		if a.Kind == "door_code_reissued" && a.DedupeKey == fmt.Sprintf("door_code_reissued:%d", e.res) {
			found = true
		}
	}
	if !found {
		t.Fatalf("door_code_reissued host card missing: %v", e.alertKinds())
	}
}

func TestLcLostRaceDuringDeleteReissues(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.cancelStay()
	e.lk.del = func(string) error {
		// The stay comes back and the row is issued again while the delete runs.
		e.exec("UPDATE door_code SET state = 'issued' WHERE id = $1", e.dc)
		e.setStay("active")
		return nil
	}
	e.cancelTick()
	if !e.audited("door_code_revoke_lost_race", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_revoke_lost_race not audited")
	}
	if e.audited("door_code_revoked", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("a lost race must not audit revoked")
	}
	d := e.row(e.dc)
	wantState(t, d, StateIssued, d.Attempts)
	if !e.audited("door_code_pin_reissued", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("the lost race must re-issue the PIN")
	}
}

func TestLcCancelledPendingAndRetryingBecomeRevoked(t *testing.T) {
	for _, state := range []string{StatePending, StateRetrying} {
		t.Run(state, func(t *testing.T) {
			e := newLcEnv(t)
			e.exec("UPDATE door_code SET state = $1 WHERE id = $2", state, e.dc)
			e.cancelStay()
			e.cancelTick()
			d := e.row(e.dc)
			wantState(t, d, StateRevoked, 0)
			wantMove(t, state, StateRevoked)
			if len(e.lk.deletes) != 0 {
				t.Fatal("a row that never had a code deletes nothing")
			}
		})
	}
}

func TestLcReactivatedRevokedRowIsReset(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.cancelStay()
	e.cancelTick()
	wantState(t, e.row(e.dc), StateRevoked, 1)
	e.setStay("active")
	e.cancelTick()
	if e.rowExists(e.dc) {
		t.Fatal("a reactivated revoked row must be reset (deleted)")
	}
	if !e.audited("door_code_reset", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_reset not audited")
	}
}

func TestLcPastEndRevokeFailsWithoutNotice(t *testing.T) {
	e := newLcEnv(t)
	e.issued()
	e.lk.del = func(string) error { return lcRefused(ttlock.KindTransient, 90000) }
	e.cancelStay()
	e.cancelTick()
	validTo, err := parseISO(*e.row(e.dc).ValidTo)
	if err != nil {
		t.Fatal(err)
	}
	e.clk.t = validTo.Add(time.Hour)
	e.cancelTick()
	d := e.row(e.dc)
	wantState(t, d, StateRevokeFailed, 2)
	wantLastError(t, d, "transient")
	if e.notes.count("cancelled_not_deleted") != 0 {
		t.Fatal("a past-end give-up sends no notice")
	}
	if !e.audited("door_code_revoke_failed", fmt.Sprintf("door_code=%d", e.dc)) {
		t.Fatal("door_code_revoke_failed not audited")
	}
}
