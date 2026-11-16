-- +goose Up
-- Brief 1816. The job table is small (about 12,000 rows) but every row is updated 2-3 times,
-- so dead tuples pile up fast; the default 20% scale factor waits for thousands. Vacuum
-- early and often, and analyze early so the partial indexes keep good plans.
SET LOCAL lock_timeout = '5s';
ALTER TABLE job SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 100,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_analyze_threshold = 100
);

-- +goose Down
ALTER TABLE job RESET (
    autovacuum_vacuum_scale_factor,
    autovacuum_vacuum_threshold,
    autovacuum_analyze_scale_factor,
    autovacuum_analyze_threshold
);
