-- Synthetic retention fixture (no real person). Loaded after App/migrations_pg
-- by App/scripts/retention_golden.py and by golden_test.go. The run instant is
-- 2026-01-20T03:00:00.250000Z, today 2026-01-20: guests before 2019-01-01 are
-- due, stays ending in 2019 get the retention_due notice. Each step has rows
-- that are due and rows that are not, for owner 1 and owner 2.
INSERT INTO user_account (id, username, password_hash, created_at, active, last_login_at, deletion_due_at) VALUES
 (1, 'host-one', 'x', '2017-01-01T00:00:00+00:00', 1, '2026-01-19T08:00:00+00:00', NULL),
 (2, 'host-two', 'x', '2017-01-01T00:00:00+00:00', 1, '2026-01-18T08:00:00+00:00', NULL),
 (3, 'gone-inactive', 'x', '2017-01-01T00:00:00+00:00', 0, '2022-01-01T00:00:00+00:00', NULL),
 (4, 'due-now', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-01-19T00:00:00+00:00'),
 (5, 'due-in-3-days', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-01-23T00:00:00+00:00'),
 (6, 'due-in-march', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-03-01T00:00:00+00:00'),
 (7, 'recent-inactive', 'x', '2017-01-01T00:00:00+00:00', 0, '2025-06-01T00:00:00+00:00', NULL);

INSERT INTO apartment (id, internal_name, created_at, owner_user_id) VALUES
 (10, 'Flat A', '2017-01-01T00:00:00+00:00', 1),
 (20, 'Flat B', '2017-01-01T00:00:00+00:00', 2);

INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, guest_email, phone_last4, created_at, updated_at) VALUES
 (100, 10, 'r100', '2018-05-01', '2018-05-05', 'g100@example.test', '1001', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (101, 10, 'r101', '2019-06-01', '2019-06-03', NULL, NULL, '2019-01-01T00:00:00+00:00', '2019-01-01T00:00:00+00:00'),
 (102, 10, 'r102', '2025-12-01', '2025-12-10', 'g102@example.test', NULL, '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (103, 10, 'r103', '2026-01-10', '2026-01-15', 'g103@example.test', '1003', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (104, 10, 'r104', '2017-01-01', '2017-01-02', NULL, NULL, '2017-01-01T00:00:00+00:00', '2017-01-01T00:00:00+00:00'),
 (105, 10, 'r105', '2025-01-01', '2025-01-02', NULL, '1005', '2024-12-01T00:00:00+00:00', '2024-12-01T00:00:00+00:00'),
 (106, 10, 'r106', '2025-08-01', '2025-08-05', NULL, NULL, '2025-07-01T00:00:00+00:00', '2025-07-01T00:00:00+00:00'),
 (107, 10, 'r107', '2018-07-01', '2018-07-07T12:00:00', NULL, NULL, '2018-06-01T00:00:00+00:00', '2018-06-01T00:00:00+00:00'),
 (200, 20, 'r200', '2018-03-01', '2018-03-02', NULL, '2001', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (201, 20, 'r201', '2019-02-01', '2019-02-02', NULL, NULL, '2019-01-01T00:00:00+00:00', '2019-01-01T00:00:00+00:00'),
 (202, 20, 'r202', '2016-01-01', '2016-01-02', NULL, NULL, '2016-01-01T00:00:00+00:00', '2016-01-01T00:00:00+00:00');

INSERT INTO submission (id, apartment_id, created_at) VALUES
 (500, 10, '2018-05-06T00:00:00+00:00'),
 (501, 10, '2018-01-01T00:00:00+00:00'),
 (502, 10, '2025-01-01T00:00:00+00:00'),
 (503, 20, '2018-03-03T00:00:00+00:00');

INSERT INTO guest (id, reservation_id, stay_to, filled_ip, submission_id, receipt_submission_id, created_at, updated_at) VALUES
 (1000, 100, '2018-05-05', '192.0.2.1', 500, NULL, '2018-05-01T00:00:00+00:00', '2018-05-01T00:00:00+00:00'),
 (1001, 100, 'not-a-date', NULL, NULL, NULL, '2018-05-01T00:00:00+00:00', '2018-05-01T00:00:00+00:00'),
 (1002, 101, NULL, NULL, NULL, NULL, '2019-06-01T00:00:00+00:00', '2019-06-01T00:00:00+00:00'),
 (1003, 102, NULL, '192.0.2.3', NULL, NULL, '2025-12-01T00:00:00+00:00', '2025-12-01T00:00:00+00:00'),
 (1004, 106, '2025-08-05', '192.0.2.4', NULL, NULL, '2025-08-01T00:00:00+00:00', '2025-08-01T00:00:00+00:00'),
 (1005, 106, '2025-11-30', '192.0.2.5', NULL, NULL, '2025-08-01T00:00:00+00:00', '2025-08-01T00:00:00+00:00'),
 (1006, 107, NULL, NULL, NULL, NULL, '2018-07-01T00:00:00+00:00', '2018-07-01T00:00:00+00:00'),
 (2000, 200, NULL, '192.0.2.20', NULL, 503, '2018-03-01T00:00:00+00:00', '2018-03-01T00:00:00+00:00'),
 (2001, 201, NULL, NULL, NULL, NULL, '2019-02-01T00:00:00+00:00', '2019-02-01T00:00:00+00:00'),
 (2002, 103, NULL, NULL, NULL, NULL, '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00');

INSERT INTO reservation_claim (reservation_id, email, created_at, updated_at) VALUES
 (100, NULL, '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (102, 'c102@example.test', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (103, 'c103@example.test', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (200, 'c200@example.test', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00');

INSERT INTO stay_fee_filing (id, apartment_id, period_key, cadence, rate_czk, liable_days, exempt_days, total_due_czk, total_collected_czk, created_at) VALUES
 (300, 10, '2018-03', 'monthly', 50, 1, 0, 50, 50, '2018-04-01T00:00:00+00:00'),
 (301, 10, '2019-Q1', 'quarterly', 50, 1, 0, 50, 50, '2019-04-01T00:00:00+00:00'),
 (302, 20, '2017-Q4', 'quarterly', 50, 1, 0, 50, 50, '2018-01-01T00:00:00+00:00');

INSERT INTO stay_fee_adjustment (id, apartment_id, period_key, direction, mode, bed_days, reason_enc, created_at) VALUES
 (310, 10, '2018-03', 'add', 'bed_days', 1, 'x', '2018-04-01T00:00:00+00:00'),
 (311, 10, '2020-01', 'add', 'bed_days', 1, 'x', '2020-02-01T00:00:00+00:00');

INSERT INTO legal_entity (id, name, created_at, owner_user_id) VALUES
 (30, 'Entity A', '2017-01-01T00:00:00+00:00', 1),
 (40, 'Entity B', '2017-01-01T00:00:00+00:00', 2);

INSERT INTO invoice (id, legal_entity_id, owner_user_id, kind, corrects_invoice_id, seq_year, seq_no, number, vs, lang, vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler, created_at) VALUES
 (600, 30, 1, 'invoice', NULL, 2015, 1, 'A2015-1', '20151', 'cs', 'non_payer', '2015-03-01', 'S', 'S', 'B', 100, '2015-03-01T00:00:00+00:00'),
 (601, 30, 1, 'invoice', NULL, 2015, 2, 'A2015-2', '20152', 'cs', 'non_payer', '2015-06-01', 'S', 'S', 'B', 100, '2015-06-01T00:00:00+00:00'),
 (602, 30, 1, 'storno', 601, 2016, 1, 'A2016-1', '20161', 'cs', 'non_payer', '2016-02-01', 'S', 'S', 'B', -100, '2016-02-01T00:00:00+00:00'),
 (603, 30, 1, 'invoice', NULL, 2015, 3, 'A2015-3', '20153', 'cs', 'non_payer', '2015-01-10', 'S', 'S', 'B', 100, '2015-01-10T00:00:00+00:00'),
 (604, 30, 1, 'storno', 603, 2015, 4, 'A2015-4', '20154', 'cs', 'non_payer', '2015-12-01', 'S', 'S', 'B', -100, '2015-12-01T00:00:00+00:00'),
 (605, 40, 2, 'invoice', NULL, 2014, 1, 'B2014-1', '20141', 'cs', 'non_payer', '2014-01-01', 'S', 'S', 'B', 100, '2014-01-01T00:00:00+00:00'),
 (606, 30, 1, 'invoice', NULL, 2020, 1, 'A2020-1', '20201', 'cs', 'non_payer', '2020-01-01', 'S', 'S', 'B', 100, '2020-01-01T00:00:00+00:00');

INSERT INTO invoice_item (id, invoice_id, position, kind, description, gross_haler) VALUES
 (650, 600, 1, 'accommodation', 'Stay', 100),
 (651, 603, 1, 'accommodation', 'Stay', 100),
 (652, 606, 1, 'accommodation', 'Stay', 100);

UPDATE invoice SET issued_at = issue_date || 'T12:00:00+00:00';

INSERT INTO platform_invoice (id, owner_user_id, kind, corrects_id, seq_year, seq_no, number, vs, issue_date, due_date, period_from, period_to, total_haler, snapshot_json, created_at) VALUES
 (700, 1, 'invoice', NULL, 2015, 1, 'U2015-1', '9001', '2015-02-01', '2015-02-15', '2015-02-01', '2015-02-28', 100, '{}', '2015-02-01T00:00:00+00:00'),
 (701, 1, 'invoice', NULL, 2015, 2, 'U2015-2', '9002', '2015-05-01', '2015-05-15', '2015-05-01', '2015-05-31', 100, '{}', '2015-05-01T00:00:00+00:00'),
 (702, 1, 'storno', 701, 2016, 1, 'U2016-1', '9003', '2016-01-05', '2016-01-19', '2015-05-01', '2015-05-31', -100, '{}', '2016-01-05T00:00:00+00:00'),
 (703, 1, 'invoice', NULL, 2020, 1, 'U2020-1', '9004', '2020-03-01', '2020-03-15', '2020-03-01', '2020-03-31', 100, '{}', '2020-03-01T00:00:00+00:00');

INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, status, matched_invoice_id) VALUES
 ('tx-700', '2015-02-10', 100, 'matched', 700),
 ('tx-old-unmatched', '2015-01-01', 100, 'unmatched', NULL),
 ('tx-new-unmatched', '2020-01-01', 100, 'unmatched', NULL),
 ('tx-703', '2020-03-10', 100, 'matched', 703);

INSERT INTO audit (id, at, actor, action, detail, owner_user_id) VALUES
 (1, '2022-01-01T00:00:00+00:00', 'host-one', 'login', '', 1),
 (2, '2022-01-01T00:00:00+00:00', 'host-one', 'legal_accepted', '', 1),
 (3, '2025-01-01T00:00:00+00:00', 'host-one', 'login', '', 1),
 (4, '2021-01-01T00:00:00+00:00', 'host-two', 'login', '', 2),
 (5, '2021-01-01T00:00:00+00:00', 'system', 'backup', '', NULL),
 (6, '2021-01-01T00:00:00+00:00', 'host-two', 'door_code_terms_accepted', '', 2),
 (7, '2023-01-21T02:59:59+00:00', 'host-one', 'login', '', 1),
 (8, '2023-01-21T03:00:00+00:00', 'host-one', 'login', '', 1);
SELECT setval('audit_id_seq', 100);

INSERT INTO alert (id, level, kind, message, created_at, resolved_at, owner_user_id, dedupe_key, params) VALUES
 (1, 'warning', 'x', 'm', '2024-05-01T00:00:00+00:00', '2024-06-01T00:00:00+00:00', 1, 'x:1', NULL),
 (2, 'warning', 'x', 'm', '2025-05-01T00:00:00+00:00', '2025-06-01T00:00:00+00:00', 1, 'x:2', NULL),
 (3, 'warning', 'x', 'm', '2020-05-01T00:00:00+00:00', NULL, 1, 'x:3', NULL),
 (4, 'warning', 'x', 'm', '2023-05-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00', NULL, 'x:4', NULL),
 (5, 'warning', 'retention_due', 'old copy', '2026-01-01T00:00:00+00:00', NULL, 2, 'retention_due:2:2026-01', '{"count": 9, "days": 30}');
SELECT setval('alert_id_seq', 100);

-- Run instant E = 1768878000.25 (epoch seconds).
INSERT INTO rate_limit_event (id, scope, key, at) VALUES
 (1, 'login', 'k', 1768788000.25),
 (2, 'login', 'k', 1768874400.25),
 (3, 'havel_week', 'k', 1768788000.25),
 (4, 'havel_month', 'k', 1765422000.25),
 (5, 'login', 'k', 1768791600.25);

INSERT INTO havel_gap (id, created_at, lang, kind, question) VALUES
 (1, '2025-09-01T00:00:00+00:00', 'en', 'gap', 'q'),
 (2, '2025-12-01T00:00:00+00:00', 'en', 'gap', 'q');

INSERT INTO login_token (id, token_hash, user_account_id, purpose, email, created_at, expires_at) VALUES
 (1, 'h1', 1, 'login', 'host-one@example.test', '2026-01-17T00:00:00+00:00', '2026-01-18T00:00:00+00:00'),
 (2, 'h2', 1, 'login', 'host-one@example.test', '2026-01-18T03:00:00+00:00', '2026-01-19T03:00:00+00:00');

INSERT INTO webauthn_challenge (id, challenge_hash, purpose, user_account_id, created_at, expires_at) VALUES
 (1, 'c1', 'login', 1, '2026-01-19T02:55:00+00:00', '2026-01-19T03:00:00+00:00'),
 (2, 'c2', 'login', 1, '2026-01-19T02:55:01+00:00', '2026-01-19T03:00:01+00:00');

INSERT INTO door_code (id, reservation_id, apartment_id, lock_id, pin_enc, valid_to, created_at, updated_at) VALUES
 (1, 102, 10, 'L', 'pin-a', '2026-01-18T10:00:00+00:00', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 103, 10, 'L', 'pin-b', '2026-01-19T12:00:00+00:00', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (3, 105, 10, 'L', NULL, '2025-01-02T10:00:00+00:00', '2024-12-01T00:00:00+00:00', '2024-12-01T00:00:00+00:00');

INSERT INTO cleaning_event (id, apartment_id, scheduled_date, notes_enc, created_at, updated_at) VALUES
 (1, 10, '2025-12-01', 'n1', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 10, '2026-01-10', 'n2', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (3, 20, '2025-11-01', 'n3', '2025-10-01T00:00:00+00:00', '2025-10-01T00:00:00+00:00'),
 (4, 10, '2025-11-01', NULL, '2025-10-01T00:00:00+00:00', '2025-10-01T00:00:00+00:00');

INSERT INTO cleaning_share (id, owner_user_id, token_hash, expires_at, created_at) VALUES
 (1, 1, 's1', '2025-12-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 1, 's2', '2026-02-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
 (3, 2, 's3', '2025-12-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00');

INSERT INTO push_subscription (id, user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc, created_at, last_seen_at) VALUES
 (1, 1, 'e1', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2025-06-01T00:00:00+00:00'),
 (2, 1, 'e2', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
 (3, 2, 'e3', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00');

INSERT INTO push_outbox (id, idempotency_key, subscription_id, user_account_id, kind, next_attempt_at, created_at) VALUES
 (1, 'p1', 2, 1, 'k', '2025-12-01T00:00:00+00:00', '2025-12-01T00:00:00+00:00'),
 (2, 'p2', 2, 1, 'k', '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00'),
 (3, 'p3', 1, 1, 'k', '2026-01-15T00:00:00+00:00', '2026-01-15T00:00:00+00:00'),
 (4, 'p4', 3, 2, 'k', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00');

INSERT INTO guide_import (id, apartment_id, source, url, status, raw_json, created_at) VALUES
 (1, 10, 'booking', 'https://example.test/1', 'done', '{}', '2026-01-01T00:00:00+00:00'),
 (2, 10, 'booking', 'https://example.test/2', 'failed', NULL, '2025-10-01T00:00:00+00:00'),
 (3, 10, 'booking', 'https://example.test/3', 'failed', NULL, '2025-12-01T00:00:00+00:00'),
 (4, 10, 'airbnb', 'https://example.test/4', 'queued', '{}', '2026-01-15T00:00:00+00:00'),
 (5, 20, 'airbnb', 'https://example.test/5', 'failed', '{}', '2025-09-01T00:00:00+00:00');

INSERT INTO guest_chat (id, apartment_id, door, reservation_id, cookie_id, created_at, last_message_at) VALUES
 (1, 10, 'stay', 102, NULL, '2025-12-01T00:00:00+00:00', '2025-12-05T00:00:00+00:00'),
 (2, 10, 'stay', 103, NULL, '2026-01-10T00:00:00+00:00', '2026-01-12T00:00:00+00:00'),
 (3, 10, 'qr', NULL, 'k1', '2025-11-01T00:00:00+00:00', '2025-12-01T10:00:00+00:00'),
 (4, 10, 'qr', NULL, 'k2', '2025-11-01T00:00:00+00:00', '2026-01-10T10:00:00+00:00'),
 (5, 20, 'stay', NULL, NULL, '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00');

INSERT INTO guest_chat_message (id, chat_id, role, text, created_at) VALUES
 (1, 1, 'guest', 't', '2025-12-01T00:00:00+00:00'),
 (2, 2, 'guest', 't', '2026-01-10T00:00:00+00:00'),
 (3, 3, 'guest', 't', '2025-12-01T00:00:00+00:00');

INSERT INTO guest_question (id, chat_id, apartment_id, message_id, summary, created_at) VALUES
 (1, 1, 10, 1, 's', '2025-12-01T00:00:00+00:00'),
 (2, 2, 10, 2, 's', '2026-01-10T00:00:00+00:00');

INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES
 (1, 3, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap'),
 (2, 1, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap'),
 (3, 7, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap');

INSERT INTO settings (key, value) VALUES ('retention_last_run', 'old');
