package doorcleaning

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

const (
	nextOneMinute   = "2026-11-15T10:01:00+00:00"
	nextFiveMinutes = "2026-11-15T10:05:00+00:00"
	nextFourHours   = "2026-11-15T14:00:00+00:00"
	staleClaim      = "2026-11-15T09:55:00+00:00" // 5 minutes before the test clock: stale
)

// matchEntry is one TTLock list entry for the world's PIN "4821" with the given type and id.
func matchEntry(kind float64, pin string, id float64) map[string]any {
	return map[string]any{"keyboardPwdType": kind, "keyboardPwd": pin, "keyboardPwdId": id}
}

func TestQueueIssuesPendingCode(t *testing.T) {
	w := newWorld(t)
	id := w.pending("pending", "4821", "UH Cleaning 01", 0)
	w.lock.add = func(string, string) (string, error) { return "5001", nil }

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1", n)
	}
	row := w.read(id)
	if row.State != "active" || derefStr(row.ProviderCodeID) != "5001" || row.Attempts != 1 || row.ClaimedAt != nil {
		t.Fatalf("row = %+v", row)
	}
	if code, pending := w.property(); code == nil || *code != id || pending != nil {
		t.Fatalf("property code=%v pending=%v, want code %d and no pending", code, pending, id)
	}
	if len(w.lock.adds) != 1 || w.lock.adds[0] != "4821/UH Cleaning 01" {
		t.Fatalf("adds = %v", w.lock.adds)
	}
}

// A PIN the gateway refuses (ErrInvalidPermanentPIN) fails that row alone: the pass goes on.
func TestQueueInvalidPINFailsOnlyThatRow(t *testing.T) {
	w := newWorld(t)
	bad := w.pending("pending", "4821", "UH bad", 0)
	good := w.pending("pending", "4822", "UH good", 0)
	w.lock.add = func(_ string, name string) (string, error) {
		if name == "UH bad" {
			return "", ttlock.ErrInvalidPermanentPIN
		}
		return "5002", nil
	}
	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1 (the good row only)", n)
	}
	if row := w.read(bad); row.State != "failed" || row.LastError == nil {
		t.Fatalf("bad row = %+v, want failed with a last error", row)
	}
	if row := w.read(good); row.State != "active" {
		t.Fatalf("good row = %+v, want active", row)
	}
}

func TestQueueFindsExistingCodeOnRetry(t *testing.T) {
	w := newWorld(t)
	id := w.pending("retrying", "4821", "UH Cleaning 02", 1)
	w.lock.named = func(string) ([]map[string]any, bool, error) {
		return []map[string]any{matchEntry(2, "4821", 6002)}, true, nil
	}

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1", n)
	}
	row := w.read(id)
	if row.State != "active" || derefStr(row.ProviderCodeID) != "6002" || len(w.lock.adds) != 0 {
		t.Fatalf("row = %+v adds = %v; want the existing code adopted without a second add", row, w.lock.adds)
	}
}

func TestQueueLookupProblemsAreRecorded(t *testing.T) {
	cases := []struct {
		name      string
		entries   []map[string]any
		complete  bool
		wantState string
		wantLast  string
	}{
		{"incomplete list retries", nil, false, "retrying", "transient"},
		{"two matches fail", []map[string]any{matchEntry(2, "4821", 1), matchEntry(2, "4821", 2)}, true, "failed", "permission"},
		{"pin mismatch fails", []map[string]any{matchEntry(2, "0000", 1)}, true, "failed", "permission"},
		{"wrong code type fails", []map[string]any{matchEntry(1, "4821", 1)}, true, "failed", "permission"},
	}
	for i, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			w := newWorld(t)
			id := w.pending("retrying", "4821", "UH Cleaning L"+string(rune('a'+i)), 1)
			w.lock.named = func(string) ([]map[string]any, bool, error) { return c.entries, c.complete, nil }

			w.runQueue()
			row := w.read(id)
			if row.State != c.wantState || derefStr(row.LastError) != c.wantLast {
				t.Fatalf("state=%s last=%v, want %s/%s", row.State, row.LastError, c.wantState, c.wantLast)
			}
			if len(w.lock.adds) != 0 {
				t.Fatalf("adds = %v, want none: an unknown lookup must not add a second code", w.lock.adds)
			}
		})
	}
}

func TestQueueTransientIssueFailureBacksOff(t *testing.T) {
	w := newWorld(t)
	id := w.pending("pending", "4821", "UH Cleaning 03", 0)
	w.lock.add = func(string, string) (string, error) { return "", ttlockErr(ttlock.KindOffline) }

	if n := w.runQueue(); n != 0 {
		t.Fatalf("processed %d, want 0 (a failure is not processed)", n)
	}
	row := w.read(id)
	if row.State != "retrying" || row.Attempts != 1 || derefStr(row.LastError) != "offline" ||
		derefStr(row.NextAttemptAt) != nextOneMinute || row.ClaimedAt != nil {
		t.Fatalf("row = %+v", row)
	}
	if code, pending := w.property(); code != nil || pending == nil || *pending != id {
		t.Fatalf("property must keep the pending pointer, got code=%v pending=%v", code, pending)
	}
}

func TestQueueRetryLimitEndsInFailed(t *testing.T) {
	w := newWorld(t)
	id := w.pending("retrying", "4821", "UH Cleaning 04", 4)
	w.lock.add = func(string, string) (string, error) { return "", ttlockErr(ttlock.KindOffline) }

	w.runQueue()
	row := w.read(id)
	if row.State != "failed" || row.Attempts != 5 || derefStr(row.NextAttemptAt) != nextFourHours {
		t.Fatalf("row = %+v, want failed after 5 attempts with the 240 minute delay", row)
	}
}

func TestQueuePermanentIssueFailureFails(t *testing.T) {
	w := newWorld(t)
	id := w.pending("pending", "4821", "UH Cleaning 05", 0)
	w.lock.add = func(string, string) (string, error) { return "", ttlockErr(ttlock.KindPermission) }

	w.runQueue()
	if row := w.read(id); row.State != "failed" || derefStr(row.LastError) != "permission" {
		t.Fatalf("row = %+v, want failed/permission", row)
	}
}

func TestQueueNonTTLockErrorStopsThePass(t *testing.T) {
	w := newWorld(t)
	id := w.pending("pending", "4821", "UH Cleaning 06", 0)
	w.lock.add = func(string, string) (string, error) { return "", errors.New("invented boom") }

	_, err := ProcessQueue(context.Background(), w.pool, w.deps())
	if err == nil || !strings.Contains(err.Error(), "boom") {
		t.Fatalf("err = %v, want the non-TTLock error returned", err)
	}
	row := w.read(id)
	if row.State != "issuing" || row.Attempts != 1 || row.ClaimedAt == nil {
		t.Fatalf("row = %+v, want the claim left in place (no failure recorded)", row)
	}
}

func TestQueueLostBindingRevokesBeforeProgramming(t *testing.T) {
	w := newWorld(t)
	id := w.pending("pending", "4821", "UH Cleaning 07", 0)
	w.exec("UPDATE apartment SET lock_id = '202' WHERE id = $1", w.apt)

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1", n)
	}
	row := w.read(id)
	if row.State != "revoked" || row.PinEnc != nil || len(w.lock.adds) != 0 {
		t.Fatalf("row = %+v adds = %v; never program a lock that is no longer bound", row, w.lock.adds)
	}
	if _, pending := w.property(); pending != nil {
		t.Fatalf("pending pointer = %d, want cleared", *pending)
	}
}

func TestQueueLostBindingAfterAttemptKeepsPinForRevoke(t *testing.T) {
	w := newWorld(t)
	id := w.pending("retrying", "4821", "UH Cleaning 08", 1)
	w.exec("UPDATE apartment SET lock_id = '202' WHERE id = $1", w.apt)

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1", n)
	}
	row := w.read(id)
	if row.State != "revoke_pending" || row.PinEnc == nil || row.Attempts != 0 || len(w.lock.adds) != 0 {
		t.Fatalf("row = %+v; an uncertain earlier attempt keeps its PIN for exact revocation", row)
	}
}

func TestQueueActiveBindingLostIsRevokedInSamePass(t *testing.T) {
	w := newWorld(t)
	id := w.code(codeSeed{source: "ttlock", state: "active", pin: "4821", provider: "7001",
		ref: "UH Cleaning 09", acct: w.acct, lockID: "101", attempts: 1})
	w.setProperty(&id, nil)
	w.exec("UPDATE apartment SET lock_id = '202' WHERE id = $1", w.apt)
	w.lock.remove = func(string, string) error { return nil }

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1 (the revoke)", n)
	}
	row := w.read(id)
	if row.State != "revoked" || row.PinEnc != nil {
		t.Fatalf("row = %+v, want revoked", row)
	}
	if len(w.lock.deletes) != 1 || w.lock.deletes[0] != "7001/"+ttlock.PriorityCritical {
		t.Fatalf("deletes = %v", w.lock.deletes)
	}
}

func TestQueueRevokeDeletesProviderCode(t *testing.T) {
	w := newWorld(t)
	id := w.code(codeSeed{source: "ttlock", state: "revoke_pending", pin: "4821", provider: "7002",
		ref: "UH Cleaning 10", acct: w.acct, lockID: "101"})
	w.lock.remove = func(string, string) error { return nil }

	if n := w.runQueue(); n != 1 {
		t.Fatalf("processed %d, want 1", n)
	}
	row := w.read(id)
	if row.State != "revoked" || row.PinEnc != nil || row.ClaimedAt != nil {
		t.Fatalf("row = %+v", row)
	}
	if len(w.lock.deletes) != 1 || w.lock.deletes[0] != "7002/"+ttlock.PriorityCritical {
		t.Fatalf("deletes = %v", w.lock.deletes)
	}
}

func TestQueueRevokeFailures(t *testing.T) {
	cases := []struct {
		name      string
		remove    error
		listed    func(string) (ttlock.TriState, error)
		wantState string
		wantLast  string
		wantN     int
	}{
		{"offline is retried", ttlockErr(ttlock.KindOffline), nil, "revoke_pending", "offline", 0},
		{"permission is final", ttlockErr(ttlock.KindPermission), nil, "revoke_failed", "permission", 0},
		{"code missing and gone revokes", ttlockErr(ttlock.KindCodeMissing),
			func(string) (ttlock.TriState, error) { return ttlock.TriNo, nil }, "revoked", "", 1},
		{"code missing but still listed retries", ttlockErr(ttlock.KindCodeMissing),
			func(string) (ttlock.TriState, error) { return ttlock.TriYes, nil }, "revoke_pending", "code_missing", 0},
		{"code missing with unknown list retries", ttlockErr(ttlock.KindCodeMissing),
			func(string) (ttlock.TriState, error) { return ttlock.TriUnknown, nil }, "revoke_pending", "code_missing", 0},
		{"code missing with failed lookup retries", ttlockErr(ttlock.KindCodeMissing),
			func(string) (ttlock.TriState, error) { return ttlock.TriUnknown, errors.New("invented") }, "revoke_pending", "code_missing", 0},
	}
	for i, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			w := newWorld(t)
			id := w.code(codeSeed{source: "ttlock", state: "revoke_pending", pin: "4821", provider: "7003",
				ref: "UH Cleaning R" + string(rune('a'+i)), acct: w.acct, lockID: "101"})
			w.lock.remove = func(string, string) error { return c.remove }
			if c.listed != nil {
				w.lock.listed = c.listed
			}

			if n := w.runQueue(); n != c.wantN {
				t.Fatalf("processed %d, want %d", n, c.wantN)
			}
			row := w.read(id)
			if row.State != c.wantState {
				t.Fatalf("state = %s, want %s", row.State, c.wantState)
			}
			if c.wantLast != "" && derefStr(row.LastError) != c.wantLast {
				t.Fatalf("last_error = %v, want %s", row.LastError, c.wantLast)
			}
			if c.wantState == "revoke_pending" && c.wantLast == "offline" && derefStr(row.NextAttemptAt) != nextOneMinute {
				t.Fatalf("next_attempt_at = %v, want %s", row.NextAttemptAt, nextOneMinute)
			}
		})
	}
}

func TestQueueRevokeLooksUpWhenRetried(t *testing.T) {
	t.Run("found then deleted", func(t *testing.T) {
		w := newWorld(t)
		id := w.code(codeSeed{source: "ttlock", state: "revoke_pending", pin: "4821", provider: "7004",
			ref: "UH Cleaning RL1", acct: w.acct, lockID: "101", attempts: 1})
		w.lock.named = func(string) ([]map[string]any, bool, error) {
			return []map[string]any{matchEntry(2, "4821", 7005)}, true, nil
		}
		w.lock.remove = func(string, string) error { return nil }
		w.runQueue()
		if row := w.read(id); row.State != "revoked" {
			t.Fatalf("state = %s, want revoked", row.State)
		}
		if len(w.lock.deletes) != 1 || w.lock.deletes[0] != "7005/"+ttlock.PriorityCritical {
			t.Fatalf("deletes = %v, want the id found by the lookup, not the stored one", w.lock.deletes)
		}
	})
	t.Run("absent is revoked without a delete", func(t *testing.T) {
		w := newWorld(t)
		id := w.code(codeSeed{source: "ttlock", state: "revoke_pending", pin: "4821", provider: "7006",
			ref: "UH Cleaning RL2", acct: w.acct, lockID: "101", attempts: 1})
		w.runQueue()
		if row := w.read(id); row.State != "revoked" || len(w.lock.deletes) != 0 {
			t.Fatalf("row = %+v deletes = %v", row, w.lock.deletes)
		}
	})
}

func TestQueueSkipsNotDueAndDisabled(t *testing.T) {
	w := newWorld(t)
	id := w.code(codeSeed{source: "ttlock", state: "pending", pin: "4821", ref: "UH Cleaning 11",
		acct: w.acct, lockID: "101", next: "2026-11-15T11:00:00+00:00"})
	w.setProperty(nil, &id)
	w.lock.add = func(string, string) (string, error) { return "5011", nil }

	if n := w.runQueue(); n != 0 || w.read(id).State != "pending" {
		t.Fatalf("not-due row: processed %d, state %s", n, w.read(id).State)
	}

	w.exec("UPDATE cleaning_code SET next_attempt_at = NULL WHERE id = $1", id)
	w.lock.enabled = false
	if n := w.runQueue(); n != 0 || w.read(id).State != "pending" || len(w.lock.adds) != 0 {
		t.Fatalf("disabled TTLock: processed %d, adds %v", n, w.lock.adds)
	}
	w.lock.enabled = true

	deps := w.deps()
	deps.StagingNoLogin = true
	if n, err := ProcessQueue(context.Background(), w.pool, deps); err != nil || n != 0 || len(w.lock.adds) != 0 {
		t.Fatalf("staging: processed %d err %v adds %v", n, err, w.lock.adds)
	}
}

func TestQueueReleasesStaleClaims(t *testing.T) {
	w := newWorld(t)
	issuing := w.code(codeSeed{source: "ttlock", state: "issuing", pin: "4821", ref: "UH Cleaning S1",
		acct: w.acct, lockID: "101", attempts: 1, claimed: staleClaim})
	w.setProperty(nil, &issuing)
	revoking := w.code(codeSeed{source: "ttlock", state: "revoking", pin: "4821", provider: "7100",
		ref: "UH Cleaning S2", acct: w.acct, lockID: "101", attempts: 1, claimed: staleClaim})
	w.lock.add = func(string, string) (string, error) { return "8001", nil }

	if n := w.runQueue(); n != 2 {
		t.Fatalf("processed %d, want 2", n)
	}
	if row := w.read(issuing); row.State != "active" || derefStr(row.ProviderCodeID) != "8001" {
		t.Fatalf("stale issuing row = %+v", row)
	}
	if row := w.read(revoking); row.State != "revoked" || len(w.lock.deletes) != 0 {
		t.Fatalf("stale revoking row = %+v deletes = %v", row, w.lock.deletes)
	}
}

// runActivate calls activate inside a transaction, as the claim path does.
func runActivate(t *testing.T, w *world, id int64) {
	t.Helper()
	ctx := context.Background()
	tx, err := w.pool.Begin(ctx)
	if err != nil {
		t.Fatal(err)
	}
	q := &queue{pool: w.pool, lock: w.lock, cipher: w.keys, clock: w.clock}
	if err := q.activate(ctx, tx, w.read(id), iso(testStart)); err != nil {
		_ = tx.Rollback(ctx)
		t.Fatalf("activate: %v", err)
	}
	if err := tx.Commit(ctx); err != nil {
		t.Fatal(err)
	}
}

func TestActivateDetachesSamePhysicalPin(t *testing.T) {
	w := newWorld(t)
	old := w.code(codeSeed{source: "ttlock", state: "active", pin: "4321", provider: "6100",
		ref: "UH Cleaning A1", acct: w.acct, lockID: "101"})
	w.setProperty(&old, nil)
	manual := w.code(codeSeed{source: "manual", state: "active", pin: "4321#", ref: "manual-A1"})

	runActivate(t, w, manual)
	code, _ := w.property()
	if code == nil || *code != manual {
		t.Fatalf("property code = %v, want %d", code, manual)
	}
	if row := w.read(old); row.State != "detached" || row.PinEnc != nil {
		t.Fatalf("old = %+v, want detached with the PIN dropped (the manual code keeps the keypad PIN)", row)
	}
}

func TestActivateRevokesOtherPins(t *testing.T) {
	t.Run("ttlock previous with other pin is revoke_pending", func(t *testing.T) {
		w := newWorld(t)
		old := w.code(codeSeed{source: "ttlock", state: "active", pin: "4321", provider: "6101",
			ref: "UH Cleaning A2", acct: w.acct, lockID: "101"})
		w.setProperty(&old, nil)
		manual := w.code(codeSeed{source: "manual", state: "active", pin: "9999", ref: "manual-A2"})
		runActivate(t, w, manual)
		if row := w.read(old); row.State != "revoke_pending" || row.PinEnc == nil || row.Attempts != 0 {
			t.Fatalf("old = %+v, want revoke_pending keeping the PIN for the worker", row)
		}
	})
	t.Run("manual previous is revoked and its PIN dropped", func(t *testing.T) {
		w := newWorld(t)
		old := w.code(codeSeed{source: "manual", state: "active", pin: "1111", ref: "manual-A3"})
		w.setProperty(&old, nil)
		manual := w.code(codeSeed{source: "manual", state: "active", pin: "2222", ref: "manual-A4"})
		runActivate(t, w, manual)
		if row := w.read(old); row.State != "revoked" || row.PinEnc != nil {
			t.Fatalf("old = %+v, want revoked with no PIN", row)
		}
	})
}
