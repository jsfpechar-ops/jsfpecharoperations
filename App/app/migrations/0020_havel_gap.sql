-- Brief 0320: questions Havel (AI) could not answer, for the owner to grow the guide.
-- No user id and no property id; the question is redacted (havel.redact) and
-- deleted after 90 days by retention.py (_havel_gap_step). kind is escalate,
-- fail or not_helped; page is a havel.PAGES id or NULL.
CREATE TABLE IF NOT EXISTS havel_gap (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    lang        TEXT NOT NULL,
    page        TEXT,
    kind        TEXT NOT NULL,
    question    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS havel_gap_created ON havel_gap (created_at);
