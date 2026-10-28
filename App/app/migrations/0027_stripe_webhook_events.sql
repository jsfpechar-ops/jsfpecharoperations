-- Brief 0428: Stripe webhook event dedupe (direct payments, P1.2).
--
-- Stripe delivers webhooks at-least-once: it retries until the endpoint
-- answers 2xx, so a replayed event must never run its handler twice. One row
-- per processed event id is the idempotency gate; the UNIQUE constraint turns
-- a replay into a no-op. Event ids and type names are Stripe's identifiers,
-- not personal data, so retention.py needs no line for this table; rows are
-- tiny and pruned together with old audit rows in a later sweep brief.
CREATE TABLE IF NOT EXISTS stripe_webhook_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    event_type  TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('test', 'live')),
    created_at  TEXT NOT NULL
);
