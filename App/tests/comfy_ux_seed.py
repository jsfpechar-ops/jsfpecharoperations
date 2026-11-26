"""Seed fixture for Chromium geometry & layout-lint tests (Briefs 2087-2090)."""
from __future__ import annotations

import datetime as dt
import time

import itsdangerous
import psycopg


def session_cookie(secret: str, uid: int) -> str:
    serializer = itsdangerous.URLSafeTimedSerializer(secret, salt="ubyhost-session")
    return serializer.dumps({"uid": uid, "sv": 1, "iat": int(time.time())})


def seed_comfy_world(db_url: str, host_id: int, first_apt_id: int) -> dict[str, int]:
    today = dt.date.today()
    iso = lambda delta: (today + dt.timedelta(days=delta)).isoformat()
    now_ts = dt.datetime.now(dt.timezone.utc).isoformat()

    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE apartment
               SET internal_name = 'Vinohrady Loft',
                   permalink_token = 'tok-vinohrady',
                   lock_provider = 'ttlock',
                   lock_id = 'LK-9001',
                   uby_idub = 'IDUB1234',
                   uby_ws_user = 'wsuser',
                   uby_ws_password_enc = 'enc-dummy'
               WHERE id = %s""",
            (first_apt_id,),
        )
        apt1 = first_apt_id

        cur.execute(
            """INSERT INTO apartment (owner_user_id, internal_name, permalink_token, active, created_at)
               VALUES (%s, 'Smichov Studio', 'tok-smichov', 1, %s) RETURNING id""",
            (host_id, now_ts),
        )
        apt2 = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO apartment_entry_code (apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
               VALUES (%s, 1, 'building_entrance', 'Main door', 'SECRET-CODE-7744', %s, %s, %s)""",
            (apt2, iso(60), now_ts, now_ts),
        )

        cur.execute(
            """INSERT INTO apartment (owner_user_id, internal_name, permalink_token, active, created_at)
               VALUES (%s, 'Karlin Suite', 'tok-karlin', 1, %s) RETURNING id""",
            (host_id, now_ts),
        )
        apt3 = cur.fetchone()[0]

        cur.execute(
            """INSERT INTO ical_feed (apartment_id, label, url, active, created_at)
               VALUES (%s, 'Airbnb', 'https://example.test/cal.ics', 1, %s)""",
            (apt1, now_ts),
        )

        # Stay A (apt1): arriving today, claimed, 2/2 guests, code issued & sent, reported (4 green)
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'manual', 'uid-green', 'Anna Novakova', %s, %s, 2, 'active', %s, %s) RETURNING id""",
            (apt1, iso(0), iso(3), now_ts, now_ts),
        )
        stay_green = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO reservation_claim (reservation_id, state, email, completion_notified_at, created_at, updated_at)
               VALUES (%s, 'claimed', 'secret-anna@example.test', %s, %s, %s)""",
            (stay_green, now_ts, now_ts, now_ts),
        )
        cur.execute(
            """INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, pin_enc, notified_at, created_at, updated_at)
               VALUES (%s, %s, 'LK-9001', 'stay', 'issued', 'SECRET-PIN-9988', %s, %s, %s)""",
            (stay_green, apt1, now_ts, now_ts, now_ts),
        )
        for idx in range(2):
            cur.execute(
                """INSERT INTO guest (reservation_id, first_name, surname, birth_date, nationality, doc_number, stay_from, stay_to, submit_state, created_at, updated_at)
                   VALUES (%s, %s, 'Novakova', '1990-05-10', 'DEU', %s, %s, %s, 'reported', %s, %s)""",
                (stay_green, f"Anna{idx+1}", f"DOC900{idx}", iso(0), iso(3), now_ts, now_ts),
            )

        # Stay B (apt1): checked out yesterday, 1/2 guests, failed TTLock, failed UbyPort (non-overlapping with Stay A)
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'manual', 'uid-urgent', 'Lukas Weber', %s, %s, 2, 'active', %s, %s) RETURNING id""",
            (apt1, iso(-5), iso(-1), now_ts, now_ts),
        )
        stay_urgent = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO reservation_claim (reservation_id, state, created_at, updated_at)
               VALUES (%s, 'provisional', %s, %s)""",
            (stay_urgent, now_ts, now_ts),
        )
        cur.execute(
            """INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, created_at, updated_at)
               VALUES (%s, %s, 'LK-9001', 'stay', 'failed', %s, %s)""",
            (stay_urgent, apt1, now_ts, now_ts),
        )
        cur.execute(
            """INSERT INTO guest (reservation_id, first_name, surname, birth_date, nationality, doc_number, stay_from, stay_to, submit_state, created_at, updated_at)
               VALUES (%s, 'Lukas', 'Weber', '1988-03-15', 'AUT', 'AT123456', %s, %s, 'failed', %s, %s)""",
            (stay_urgent, iso(-5), iso(-1), now_ts, now_ts),
        )

        # Stay C (apt1): arriving in 3 days, unclaimed, 0/2 guests
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'airbnb', 'uid-upcoming', 'Marco Rossi', %s, %s, 2, 'active', %s, %s) RETURNING id""",
            (apt1, iso(3), iso(6), now_ts, now_ts),
        )
        stay_upcoming = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'manual', 'uid-upcoming-2', 'Elena Novak', %s, %s, 2, 'active', %s, %s)""",
            (apt1, iso(7), iso(10), now_ts, now_ts),
        )

        # Old unfilled stay (apt1): ended 14 days ago -> filtered from Needs You + bulk archive strip
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'airbnb', 'uid-old-backfill', 'Old Backfill Guest', %s, %s, 2, 'active', %s, %s)""",
            (apt1, iso(-18), iso(-14), now_ts, now_ts),
        )

        # Smichov Studio (apt2): 3 non-overlapping stays (2 within nag window), 0 claims ever -> 1 nudge card + scrollable rail
        for idx, (d1, d2, name) in enumerate(
            [(0, 1, "Claire Martin"), (1, 4, "Kenji Sato"), (5, 8, "Sofia Lind")]
        ):
            cur.execute(
                """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
                   VALUES (%s, 'manual', %s, %s, %s, %s, 2, 'active', %s, %s)""",
                (apt2, f"uid-smichov-{idx}", name, iso(d1), iso(d2), now_ts, now_ts),
            )

        # Solo 1-property host -> verifies single-property calendar auto-skip
        cur.execute(
            """INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email, two_factor_prompted_at)
               VALUES ('solo_host_2089', 'x', 'host', 1, 1, %s, 'solo@example.test', %s) RETURNING id""",
            (now_ts, now_ts),
        )
        solo_uid = cur.fetchone()[0]
        for doc, ver in (("terms", "t1"), ("privacy", "p1"), ("dpa", "d1")):
            cur.execute(
                """INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method)
                   VALUES (%s, %s, %s, %s, 'backfill')""",
                (solo_uid, doc, ver, now_ts),
            )
        cur.execute(
            """INSERT INTO apartment (owner_user_id, internal_name, permalink_token, active, created_at)
               VALUES (%s, 'Solo Studio', 'tok-solo', 1, %s) RETURNING id""",
            (solo_uid, now_ts),
        )
        solo_apt = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO reservation (apartment_id, source, uid, summary, date_from, date_to, declared_guests, status, created_at, updated_at)
               VALUES (%s, 'manual', 'uid-solo-1', 'Solo Guest', %s, %s, 1, 'active', %s, %s)""",
            (solo_apt, iso(1), iso(4), now_ts, now_ts),
        )

    return {
        "apt1": apt1,
        "apt2": apt2,
        "apt3": apt3,
        "stay_green": stay_green,
        "stay_urgent": stay_urgent,
        "stay_upcoming": stay_upcoming,
        "solo_uid": solo_uid,
        "solo_apt": solo_apt,
    }
