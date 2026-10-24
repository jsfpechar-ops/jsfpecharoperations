-- Brief 0310: the shared model-API ledger (docs/plans/havel-support-assistant.md, section 12).
--
-- ai_usage: tokens per day, feature and key. No user, no text. feature is the
-- caller ("havel", "leon", "guide_import"); key is the caller's own grouping
-- for a per-key daily cap (the guest bot passes the property id, Havel passes
-- nothing and the row has key ''). ai.py prices these rows to enforce the
-- per-feature monthly budget, today's share of it and the per-key cap.
-- havel_stats: Havel replies per day and kind (answer, clarify, action,
-- escalate, refuse, guardrail_fail, limit_hit), no user, no text.
-- havel_gap (redacted questions) comes with brief 0320 and its retention line:
-- this migration holds no personal data.
CREATE TABLE IF NOT EXISTS ai_usage (
    day                TEXT NOT NULL,
    feature            TEXT NOT NULL,
    key                TEXT NOT NULL DEFAULT '',
    requests           INTEGER NOT NULL DEFAULT 0,
    input_tokens       INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, feature, key)
);

CREATE TABLE IF NOT EXISTS havel_stats (
    day   TEXT NOT NULL,
    kind  TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind)
);
