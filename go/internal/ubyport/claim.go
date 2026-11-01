package ubyport

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// SubmissionClaimTTL matches SUBMISSION_CLAIM_TTL_SECONDS in App/app/reporting.py.
const SubmissionClaimTTL = 5 * time.Minute

// ClaimPair is one guest offered for filing. SubmitState is the state the
// caller read when it built the list; Payload is opaque and returned as given.
type ClaimPair struct {
	GuestID     int64
	SubmitState string
	Payload     any
}

// ClaimSendable leases the guests so concurrent workers cannot file the same
// record twice. It mirrors reporting.claim_sendable: one transaction, stale
// claims removed, guests locked in ascending id order with the same advisory
// key as db.lock_key, and each row re-read before it is claimed. A pair is
// dropped when its row is gone, archived, filed by hand or has a different
// submit_state. The result keeps input order.
func ClaimSendable(ctx context.Context, pool *pgxpool.Pool, pairs []ClaimPair) (string, []ClaimPair, error) {
	raw := make([]byte, 18)
	if _, err := rand.Read(raw); err != nil {
		return "", nil, err
	}
	token := base64.RawURLEncoding.EncodeToString(raw)

	tx, err := pool.Begin(ctx)
	if err != nil {
		return "", nil, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	now := nowSeconds()
	if _, err := tx.Exec(ctx, `DELETE FROM submission_claim WHERE claimed_at < $1`,
		now-SubmissionClaimTTL.Seconds()); err != nil {
		return "", nil, err
	}

	seen := map[int64]bool{}
	ids := make([]int64, 0, len(pairs))
	for _, p := range pairs {
		if !seen[p.GuestID] {
			seen[p.GuestID] = true
			ids = append(ids, p.GuestID)
		}
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for _, id := range ids {
		// Python's db.lock_key takes the id as a 32-bit integer.
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(id)); err != nil {
			return "", nil, err
		}
	}

	claimed := map[int64]bool{}
	for _, p := range pairs {
		var state string
		var archived, manual *string
		err := tx.QueryRow(ctx,
			`SELECT submit_state, archived_at, manual_filed_at FROM guest WHERE id = $1`, p.GuestID,
		).Scan(&state, &archived, &manual)
		if errors.Is(err, pgx.ErrNoRows) {
			continue
		}
		if err != nil {
			return "", nil, err
		}
		// Python tests these for truth, so an empty string counts as not set.
		if truthy(archived) || truthy(manual) || state != p.SubmitState {
			continue
		}
		tag, err := tx.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, $2, $3)
			 ON CONFLICT (guest_id) DO NOTHING`,
			p.GuestID, token, now)
		if err != nil {
			return "", nil, err
		}
		if tag.RowsAffected() == 1 {
			claimed[p.GuestID] = true
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return "", nil, err
	}

	out := make([]ClaimPair, 0, len(claimed))
	for _, p := range pairs {
		if claimed[p.GuestID] {
			out = append(out, p)
		}
	}
	return token, out, nil
}

// ReleaseSendableClaim deletes the claims that carry token.
func ReleaseSendableClaim(ctx context.Context, pool *pgxpool.Pool, token string) error {
	_, err := pool.Exec(ctx, `DELETE FROM submission_claim WHERE claim_token = $1`, token)
	return err
}

func truthy(s *string) bool {
	return s != nil && *s != ""
}

// nowSeconds is Python's time.time(): a float of Unix seconds.
func nowSeconds() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}
