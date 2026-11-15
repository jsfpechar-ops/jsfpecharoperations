package doorcleaning

import (
	"context"
	"crypto/subtle"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// codeColumns is the column list every cleaning_code read uses, in scanCode's order.
const codeColumns = "id, apartment_id, source, pin_enc, lock_account_id, lock_id, provider_code_id, " +
	"operation_ref, state, attempts, next_attempt_at, claimed_at, last_error, created_at, updated_at"

// codeRow is one cleaning_code row.
type codeRow struct {
	ID             int64
	ApartmentID    int64
	Source         string
	PinEnc         *string
	LockAccountID  *int64
	LockID         *string
	ProviderCodeID *string
	OperationRef   string
	State          string
	Attempts       int64
	NextAttemptAt  *string
	ClaimedAt      *string
	LastError      *string
	CreatedAt      string
	UpdatedAt      string
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanCode(r rowScanner) (codeRow, error) {
	var c codeRow
	err := r.Scan(&c.ID, &c.ApartmentID, &c.Source, &c.PinEnc, &c.LockAccountID, &c.LockID,
		&c.ProviderCodeID, &c.OperationRef, &c.State, &c.Attempts, &c.NextAttemptAt, &c.ClaimedAt,
		&c.LastError, &c.CreatedAt, &c.UpdatedAt)
	return c, err
}

// queue carries the collaborators of one ProcessQueue pass.
type queue struct {
	pool   *pgxpool.Pool
	lock   LockAPI
	cipher Cipher
	clock  Clock
}

// ProcessQueue is cleaning_codes.process_queue: the sequential worker pass that is the only
// caller of the lock provider for cleaner codes. It first moves rows whose binding is gone
// to revoke_pending, releases stale claims, then handles up to queueBatch due rows one at a
// time. It returns the number of rows it changed. A TTLockError on one row is recorded
// against that row; any other error stops the pass and is returned.
func ProcessQueue(ctx context.Context, pool *pgxpool.Pool, d QueueDeps) (int, error) {
	if d.StagingNoLogin || d.TTLock == nil || !d.TTLock.Enabled() {
		return 0, nil
	}
	now := d.Clock.Now()
	nowISO := iso(now)
	if _, err := pool.Exec(ctx,
		"UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = $1 "+
			"WHERE source = 'ttlock' AND state = 'active' AND NOT EXISTS ("+
			"SELECT 1 FROM apartment a JOIN lock_account la ON la.id = cleaning_code.lock_account_id "+
			"WHERE a.id = cleaning_code.apartment_id AND a.active = 1 AND a.archived_at IS NULL "+
			"AND a.lock_provider = 'ttlock' AND a.lock_id = cleaning_code.lock_id "+
			"AND la.owner_user_id = a.owner_user_id)",
		nowISO); err != nil {
		return 0, err
	}
	stale := pyISO(now.Add(-staleClaimMinutes * time.Minute))
	if _, err := pool.Exec(ctx,
		"UPDATE cleaning_code SET state = 'retrying', claimed_at = NULL "+
			"WHERE state = 'issuing' AND claimed_at < $1", stale); err != nil {
		return 0, err
	}
	if _, err := pool.Exec(ctx,
		"UPDATE cleaning_code SET state = 'revoke_pending', claimed_at = NULL "+
			"WHERE state = 'revoking' AND claimed_at < $1", stale); err != nil {
		return 0, err
	}
	rows, err := pool.Query(ctx,
		"SELECT c.id, c.apartment_id, c.source, c.pin_enc, c.lock_account_id, c.lock_id, "+
			"c.provider_code_id, c.operation_ref, c.state, c.attempts, c.next_attempt_at, c.claimed_at, "+
			"c.last_error, c.created_at, c.updated_at FROM cleaning_code c "+
			"JOIN cleaning_property p ON p.apartment_id = c.apartment_id "+
			"WHERE c.state IN ('pending', 'retrying', 'revoke_pending') "+
			"AND (c.next_attempt_at IS NULL OR c.next_attempt_at <= $1) ORDER BY c.id LIMIT $2",
		nowISO, queueBatch)
	if err != nil {
		return 0, err
	}
	var due []codeRow
	for rows.Next() {
		c, err := scanCode(rows)
		if err != nil {
			rows.Close()
			return 0, err
		}
		due = append(due, c)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return 0, err
	}
	rows.Close()

	q := &queue{pool: pool, lock: d.TTLock, cipher: d.Cipher, clock: d.Clock}
	processed := 0
	for _, row := range due {
		n, err := q.process(ctx, row)
		processed += n
		if err != nil {
			return processed, err
		}
	}
	return processed, nil
}

// process handles one due row and returns 1 when it changed the row's binding or state
// for the better (Python: processed += 1), 0 otherwise.
func (q *queue) process(ctx context.Context, row codeRow) (int, error) {
	now := q.clock.Now()
	nowISO := iso(now)
	revoking := row.State == "revoke_pending"
	expected := row.State

	if !revoking {
		var found int64
		err := q.pool.QueryRow(ctx,
			"SELECT a.id FROM apartment a JOIN lock_account la ON la.id = $1 "+
				"WHERE a.id = $2 AND a.active = 1 AND a.archived_at IS NULL "+
				"AND a.lock_provider = 'ttlock' AND a.lock_id = $3 AND la.owner_user_id = a.owner_user_id",
			row.LockAccountID, row.ApartmentID, row.LockID).Scan(&found)
		if err != nil && !errNoRow(err) {
			return 0, err
		}
		if errNoRow(err) {
			// Never program a previously mapped lock. An uncertain earlier attempt still
			// needs exact-operation reconciliation and revocation.
			attempted := row.Attempts > 0
			next := "revoked"
			var pin *string
			if attempted {
				next = "revoke_pending"
				pin = row.PinEnc
			}
			tag, err := q.pool.Exec(ctx,
				"UPDATE cleaning_code SET state = $1, pin_enc = $2, attempts = 0, next_attempt_at = $3, "+
					"claimed_at = NULL, updated_at = $3 WHERE id = $4 "+
					"AND state IS NOT DISTINCT FROM $5 AND attempts IS NOT DISTINCT FROM $6",
				next, pin, nowISO, row.ID, expected, row.Attempts)
			if err != nil {
				return 0, err
			}
			if tag.RowsAffected() != 1 {
				return 0, nil
			}
			if _, err := q.pool.Exec(ctx,
				"UPDATE cleaning_property SET pending_code_id = NULL WHERE pending_code_id = $1", row.ID); err != nil {
				return 0, err
			}
			return 1, nil
		}
	}

	attempts := row.Attempts + 1
	claimState := "issuing"
	if revoking {
		claimState = "revoking"
	}
	tag, err := q.pool.Exec(ctx,
		"UPDATE cleaning_code SET state = $1, claimed_at = $2, attempts = $3, updated_at = $2 "+
			"WHERE id = $4 AND state IS NOT DISTINCT FROM $5 AND attempts IS NOT DISTINCT FROM $6",
		claimState, nowISO, attempts, row.ID, expected, row.Attempts)
	if err != nil {
		return 0, err
	}
	if tag.RowsAffected() != 1 {
		return 0, nil
	}
	row.Attempts = attempts

	err = q.attempt(ctx, row, revoking)
	if err == nil {
		return 1, nil
	}
	te, ok := ttlock.AsError(err)
	if !ok {
		return 0, err
	}
	return 0, q.failure(ctx, row, te, revoking)
}

// attempt is the TTLock side of one claimed row. A returned error that is a TTLockError
// is recorded by failure; any other error stops the pass.
func (q *queue) attempt(ctx context.Context, row codeRow, revoking bool) error {
	if row.LockAccountID == nil {
		return &ttlock.TTLockError{Kind: ttlock.KindPermission, Message: "connection removed"}
	}
	account := *row.LockAccountID
	lockID := derefStr(row.LockID)

	if revoking {
		var codeID string
		var err error
		if row.Attempts > 1 || derefStr(row.ProviderCodeID) == "" {
			codeID, err = q.find(ctx, row)
			if err != nil {
				return err
			}
		} else {
			codeID = derefStr(row.ProviderCodeID)
		}
		if codeID != "" {
			if derr := q.lock.DeleteCode(ctx, account, lockID, codeID, ttlock.PriorityCritical); derr != nil {
				if !q.alreadyGone(ctx, row, codeID, derr) {
					return derr
				}
			}
		}
		_, err = q.pool.Exec(ctx,
			"UPDATE cleaning_code SET state = 'revoked', pin_enc = NULL, claimed_at = NULL, updated_at = $1 WHERE id = $2",
			iso(q.clock.Now()), row.ID)
		return err
	}

	var codeID string
	if row.Attempts > 1 {
		var err error
		codeID, err = q.find(ctx, row)
		if err != nil {
			return err
		}
	}
	if codeID == "" {
		pin, err := q.decrypt(row.PinEnc)
		if err != nil {
			return err
		}
		codeID, err = q.lock.AddPermanentCode(ctx, account, lockID, pin, row.OperationRef)
		if errors.Is(err, ttlock.ErrInvalidPermanentPIN) {
			// A stored PIN the gateway refuses fails this row only. Python's ValueError would abort the
			// whole pass here (a documented divergence), so the row gets a non-transient error instead.
			return &ttlock.TTLockError{Kind: ttlock.KindConfig, Message: "invalid permanent PIN"}
		}
		if err != nil {
			return err
		}
	}
	tx, err := q.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, "UPDATE cleaning_code SET provider_code_id = $1 WHERE id = $2", codeID, row.ID); err != nil {
		return err
	}
	if err := q.activate(ctx, tx, row, iso(q.clock.Now())); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// find is cleaning_codes._find: the exact-name idempotency lookup for the operation. It returns
// "" when the whole list was read and the operation is not on the lock. An incomplete list is a
// transient error; two matches or a mismatched PIN is a permission error.
func (q *queue) find(ctx context.Context, row codeRow) (string, error) {
	matches, complete, err := q.lock.CodesNamed(ctx, *row.LockAccountID, derefStr(row.LockID), row.OperationRef)
	if err != nil {
		return "", err
	}
	if !complete {
		return "", &ttlock.TTLockError{Kind: ttlock.KindTransient, Message: "incomplete code list"}
	}
	if len(matches) > 1 {
		return "", &ttlock.TTLockError{Kind: ttlock.KindPermission, Message: "ambiguous operation"}
	}
	if len(matches) == 0 {
		return "", nil
	}
	entry := matches[0]
	kind, err := intValue(entry["keyboardPwdType"])
	if err != nil {
		return "", err
	}
	mismatch := &ttlock.TTLockError{Kind: ttlock.KindPermission, Message: "operation mismatch"}
	if kind != 2 {
		return "", mismatch
	}
	pin, err := q.decrypt(row.PinEnc)
	if err != nil {
		return "", err
	}
	if subtle.ConstantTimeCompare([]byte(strValue(entry["keyboardPwd"])), []byte(pin)) != 1 {
		return "", mismatch
	}
	return strValue(entry["keyboardPwdId"]), nil
}

// alreadyGone is cleaning_codes._already_gone. A -1007 answer is never trusted alone: the code
// must be read as absent from the complete list. A failed or incomplete lookup means not gone.
func (q *queue) alreadyGone(ctx context.Context, row codeRow, codeID string, derr error) bool {
	te, ok := ttlock.AsError(derr)
	if !ok || te.Kind != ttlock.KindCodeMissing {
		return false
	}
	state, err := q.lock.CodeIsListed(ctx, *row.LockAccountID, derefStr(row.LockID), row.OperationRef, codeID)
	if err != nil {
		return false
	}
	return state == ttlock.TriNo
}

// failure is cleaning_codes._failure: a transient error below the attempt limit goes back to
// the queue after the backoff; anything else is final (failed, or revoke_failed for a revoke).
func (q *queue) failure(ctx context.Context, row codeRow, te *ttlock.TTLockError, revoking bool) error {
	transient := false
	switch te.Kind {
	case ttlock.KindOffline, ttlock.KindTransient, ttlock.KindNetwork, ttlock.KindRate,
		ttlock.KindBudget, ttlock.KindCodeMissing, ttlock.KindLockSetup:
		transient = true
	}
	retry := transient && row.Attempts < queueMaxAttempts
	var state string
	switch {
	case revoking && retry:
		state = "revoke_pending"
	case revoking:
		state = "revoke_failed"
	case retry:
		state = "retrying"
	default:
		state = "failed"
	}
	idx := int(row.Attempts) - 1
	if idx < 0 {
		idx = 0
	}
	if idx > len(backoffMinutes)-1 {
		idx = len(backoffMinutes) - 1
	}
	next := pyISO(q.clock.Now().Add(time.Duration(backoffMinutes[idx]) * time.Minute))
	_, err := q.pool.Exec(ctx,
		"UPDATE cleaning_code SET state = $1, claimed_at = NULL, last_error = $2, next_attempt_at = $3, "+
			"updated_at = $4 WHERE id = $5",
		state, te.Kind, next, iso(q.clock.Now()), row.ID)
	return err
}

// decrypt is db.decrypt_field: "" and NULL stay "", an undecryptable value is an error.
func (q *queue) decrypt(token *string) (string, error) {
	if token == nil || *token == "" {
		return "", nil
	}
	plain, err := q.cipher.Decrypt(*token, 0, q.clock.Now())
	if err != nil {
		return "", err
	}
	return string(plain), nil
}
