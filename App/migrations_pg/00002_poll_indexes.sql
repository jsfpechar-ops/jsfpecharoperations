-- +goose Up
-- Poll-job indexes (0466 part a), measured on 2,000 apartments / 40,000 reservations.
CREATE INDEX IF NOT EXISTS idx_reservation_active_date_to ON reservation (date_to) WHERE status = 'active' AND archived_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_reservation_claim_provisional ON reservation_claim (provisional_until) WHERE state = 'provisional';

-- +goose Down
DROP INDEX IF EXISTS idx_reservation_claim_provisional;
DROP INDEX IF EXISTS idx_reservation_active_date_to;
