-- Brief 0300: Leon (AI), the guest bot (plan: docs/plans/guest-guide.md).
--
-- guest_chat: one conversation per door. Stay door: one row per reservation
-- (every device of that stay shares it). QR door: one row per property and
-- random browser cookie id (no login). lang is the guest's page language.
-- refusals and paused_until: a conversation Leon refused three times rests
-- for a day. Deleted 30 days after checkout (stay) or after the last message
-- (QR): retention.py guest_chats step, leon.purge.
-- guest_chat_message: the turns. role 'guest' (text already redacted of
-- e-mails, phones and long numbers), 'leon' (kind answer, ask_host, refuse,
-- smalltalk, resting) or 'host' (brief 0301 writes it when the host answers).
-- sources: the guide card ids an answer cited, as "c<id>,c<id>".
-- guest_question: a question Leon could not answer from the guide. Brief 0301
-- shows open rows to the host and writes answer + answered_at; the guest page
-- renders the answer. summary is Leon's short English summary for the host;
-- urgent marks an emergency, triaged = 0 a message Leon never read (cap, budget).
CREATE TABLE IF NOT EXISTS guest_chat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id    INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    door            TEXT NOT NULL CHECK (door IN ('stay', 'qr')),
    reservation_id  INTEGER REFERENCES reservation(id) ON DELETE CASCADE,
    cookie_id       TEXT,
    lang            TEXT NOT NULL DEFAULT 'en',
    refusals        INTEGER NOT NULL DEFAULT 0,
    paused_until    TEXT,
    model_messages  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_message_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_guest_chat_stay ON guest_chat (reservation_id) WHERE door = 'stay';
CREATE UNIQUE INDEX IF NOT EXISTS uq_guest_chat_qr ON guest_chat (apartment_id, cookie_id) WHERE door = 'qr';
CREATE INDEX IF NOT EXISTS idx_guest_chat_last ON guest_chat (door, last_message_at);

CREATE TABLE IF NOT EXISTS guest_chat_message (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL REFERENCES guest_chat(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('guest', 'leon', 'host')),
    kind       TEXT NOT NULL DEFAULT '',
    text       TEXT NOT NULL,
    sources    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guest_chat_message_chat ON guest_chat_message (chat_id, id);

CREATE TABLE IF NOT EXISTS guest_question (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id      INTEGER NOT NULL REFERENCES guest_chat(id) ON DELETE CASCADE,
    apartment_id INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    message_id   INTEGER NOT NULL REFERENCES guest_chat_message(id) ON DELETE CASCADE,
    summary      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'answered', 'dismissed')),
    answer       TEXT NOT NULL DEFAULT '',
    urgent       INTEGER NOT NULL DEFAULT 0,
    triaged      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    answered_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_guest_question_open ON guest_question (apartment_id, status, created_at);
