"""Filing watchdog: stays that may miss their police deadline (WP23).

The deadline job (every 30 minutes) asks one question on top of the in-app
``deadline`` alert: which stays have a foreign guest UbyPort has not accepted,
with less than 24 hours left or the deadline already gone? It then

- mails the host once per stay, the first time the stay is at risk
  (``deadline_at_risk``, a kind of its own: ``reminder_host`` is the check-in
  day nudge about missing guest forms and knows nothing about the deadline);
- mails the operator (``config.OPERATOR_EMAIL``) at most one digest per six
  hours, listing every stay at risk across all workspaces, without guest names;
- reports the overall answer to ``scheduler``, which pings the
  ``UBYHOST_HEARTBEAT_FILING_URL`` dead-man switch with it.

"Reportable" is the existing rule, ``validation.guest_is_reportable``: every
nationality except Czech, EU citizens included. "Accepted" means
``submit_state == 'sent'``; a refused (``error`` or ``blocked``) or pending
guest still has to be filed. A stay that is cancelled, ignored or archived, or
whose property is switched off, is not watched, the same set the deadline alert
watches. A guest the host filed by hand in UbyPort is ``sent`` too, so it is
not at risk.

A guest whose send got no clear answer sits on an ``outcome_unknown`` batch.
PR 230's sweep resends such a batch once on its own (``retried_at`` marks it).
While that one resend is still to come, the guest is not filed but nothing is
wrong yet either: the stay is "awaiting the automatic resend". If the deadline
has not passed, it is left out of the host mail, the digest and the heartbeat
for at most ``RETRY_GRACE`` after the unclear answer, which gives the sweep two
runs to resend. After that, or once the deadline has passed, it counts as at
risk like any other unfiled guest. The grace is measured from the batch's own
finish time. WP31: the resend (``submission.mode = 'auto_resend'``) is never
resent itself, so when it comes back unclear too the stay is at risk once that
one grace is over, and stays at risk until the host files it.

A property set to send only when the host presses send gets one extra note in
the last eight hours before the police deadline (``manual_deadline``). The
usual ``deadline_at_risk`` mail still goes out earlier, in the last twenty-four
hours, so the two do not leave on the same run. Automatic properties do not get
the eight-hour note.

A stay with no guest entered at all is a second, weaker case ("unknown risk"):
the guests have arrived (arrival today or earlier), the deadline is less than
24 hours away or passed, and nobody is on file. UbyHost cannot tell whether a
report is due, because Czech guests owe none. Such a stay gets the host mail
once ("no guest details yet") and a section of the operator digest, but it
never sets the heartbeat to ``/fail``: that is kept for guests known to be
reportable, so a stay of Czech guests nobody typed in does not page anyone.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import config, db, deadlines, mail, mail_notify, reporting, validation

log = logging.getLogger("ubyhost.filing_watchdog")

# A stay is at risk from this long before its deadline, and stays at risk
# after the deadline until it is filed or no longer active.
AT_RISK_WINDOW = timedelta(hours=24)
# Manual-send properties: one reminder in the last eight hours before the
# police deadline (end of the third working day after arrival).
MANUAL_NOTICE_LEAD = timedelta(hours=8)
DIGEST_INTERVAL = timedelta(hours=6)
DIGEST_SETTING = "filing_watchdog_digest_sent_at"
# A stay with no guest on file drops off the lists this long after its
# deadline. A known reportable guest never does; an empty stay that old is a
# calendar entry nobody is going to fill in, not news.
UNKNOWN_RISK_MAX_OVERDUE = timedelta(days=7)
# How long a guest on an unclear (outcome_unknown) batch that the sweep has not
# resent yet is treated as "awaiting the automatic resend" rather than at risk:
# two sweep intervals, so one missed sweep run does not raise the alarm.
RETRY_GRACE = timedelta(minutes=2 * max(1, config.SUBMIT_SWEEP_MINUTES))


def _awaiting_retry(row, current_utc: datetime) -> bool:
    """Is this unfiled guest on an unclear batch whose one resend is still due?"""
    if row["sub_state"] != "outcome_unknown" or row["sub_retried_at"]:
        return False
    try:
        finished = datetime.fromisoformat(str(row["sub_finished_at"]))
    except (TypeError, ValueError):
        return False
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    return timedelta(0) <= current_utc - finished <= RETRY_GRACE


def _utc(now: Optional[datetime]) -> datetime:
    """``now`` as an aware UTC time. A naive value is Prague civil time."""
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(config.TIMEZONE))
    return now.astimezone(timezone.utc)


def at_risk_stays(
    now: Optional[datetime] = None,
    *,
    include_awaiting_retry: bool = False,
    window: timedelta = AT_RISK_WINDOW,
) -> List[Dict[str, Any]]:
    """Every stay at risk of missing its police deadline, soonest deadline first.

    A stay whose every unfiled guest is awaiting the automatic resend and whose
    deadline has not passed is left out, unless ``include_awaiting_retry``;
    it then carries ``awaiting_retry=True``.
    """
    local = deadlines.local_now(now)
    current_utc = _utc(now)
    # Only the columns the answer needs: nationality and submit_state are
    # plain columns, so no guest field is decrypted here.
    rows = db.query(
        "SELECT r.id AS reservation_id, r.date_from, r.at_risk_mailed_at, "
        "r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id, "
        "a.automation_mode, u.username AS workspace, g.nationality, "
        "s.state AS sub_state, s.retried_at AS sub_retried_at, "
        "s.finished_at AS sub_finished_at "
        "FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "JOIN guest g ON g.reservation_id = r.id "
        "LEFT JOIN submission s ON s.id = g.submission_id "
        "LEFT JOIN user_account u ON u.id = a.owner_user_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND g.archived_at IS NULL AND g.submit_state != ? "
        "AND g.nationality IS NOT NULL AND g.nationality != '' "
        "ORDER BY r.id",
        (reporting.SENT,),
    )
    grouped: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        if not validation.guest_is_reportable(row["nationality"]):
            continue
        stay = grouped.get(row["reservation_id"])
        if stay is None:
            stay = grouped[row["reservation_id"]] = {
                "reservation_id": row["reservation_id"],
                "date_from": row["date_from"],
                "apartment_id": row["apartment_id"],
                "property": row["internal_name"] or "",
                "legal_entity_id": row["legal_entity_id"],
                "owner_user_id": row["owner_user_id"],
                "automation_mode": row["automation_mode"] or "",
                "workspace": row["workspace"] or "",
                "mailed_at": row["at_risk_mailed_at"],
                "unfiled": 0,
                "awaiting_retry_guests": 0,
            }
        stay["unfiled"] += 1
        if _awaiting_retry(row, current_utc):
            stay["awaiting_retry_guests"] += 1
    found: List[Dict[str, Any]] = []
    for stay in grouped.values():
        # The deadline runs from the earliest guest arrival, as everywhere else.
        anchor = reporting.reservation_deadline_anchor(
            {"id": stay["reservation_id"], "date_from": stay["date_from"]}
        )
        if not anchor:
            continue
        due = deadlines.reporting_deadline(anchor)
        if due - local > window:
            continue
        stay["arrival"] = anchor
        stay["deadline"] = due
        stay["overdue"] = due < local
        stay["awaiting_retry"] = (
            not stay["overdue"] and stay["awaiting_retry_guests"] == stay["unfiled"]
        )
        if stay["awaiting_retry"] and not include_awaiting_retry:
            continue
        found.append(stay)
    found.sort(key=lambda stay: (stay["deadline"], stay["reservation_id"]))
    return found


def unknown_risk_stays(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Stays with no guest on file whose guests have arrived and whose deadline is near.

    Same stay set as ``at_risk_stays`` (active, not archived, property
    active). The deadline runs from the stay's arrival, as for any stay
    without guests.
    """
    local = deadlines.local_now(now)
    today = local.date()
    # The deadline is at most a few working days after arrival, so stays that
    # arrived long ago cannot qualify; this bounds the scan.
    earliest = today - UNKNOWN_RISK_MAX_OVERDUE - timedelta(days=21)
    rows = db.query(
        "SELECT r.id AS reservation_id, r.date_from, r.at_risk_mailed_at, "
        "r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id, "
        "u.username AS workspace "
        "FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "LEFT JOIN user_account u ON u.id = a.owner_user_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND r.date_from <= ? AND r.date_from >= ? "
        "AND NOT EXISTS (SELECT 1 FROM guest g "
        "WHERE g.reservation_id = r.id AND g.archived_at IS NULL) "
        "ORDER BY r.id",
        (today.isoformat(), earliest.isoformat()),
    )
    found: List[Dict[str, Any]] = []
    for row in rows:
        try:
            arrival = date.fromisoformat(str(row["date_from"])[:10])
        except ValueError:
            continue
        due = deadlines.reporting_deadline(arrival)
        if due - local > AT_RISK_WINDOW or local - due > UNKNOWN_RISK_MAX_OVERDUE:
            continue
        found.append(
            {
                "reservation_id": row["reservation_id"],
                "date_from": row["date_from"],
                "apartment_id": row["apartment_id"],
                "property": row["internal_name"] or "",
                "legal_entity_id": row["legal_entity_id"],
                "owner_user_id": row["owner_user_id"],
                "workspace": row["workspace"] or "",
                "mailed_at": row["at_risk_mailed_at"],
                "unfiled": 0,
                "no_guests": True,
                "arrival": arrival,
                "deadline": due,
                "overdue": due < local,
            }
        )
    found.sort(key=lambda stay: (stay["deadline"], stay["reservation_id"]))
    return found


def _stay_url(reservation_id: int) -> str:
    return f"{config.PUBLIC_BASE_URL.rstrip('/')}/reservations/{reservation_id}"


def notify_hosts(stays: List[Dict[str, Any]], now: Optional[datetime] = None) -> int:
    """Queue the host warning for each stay not warned yet. Returns how many.

    One warning per stay, whichever variant comes first: a stay mailed as "no
    guest details yet" is not mailed again when its guests are entered.
    """
    queued = 0
    for stay in stays:
        if stay.get("mailed_at"):
            continue
        try:
            to_email = mail_notify._entity_contact_email(stay["legal_entity_id"])
            if not to_email:
                continue
            lang = mail_notify.HOST_MAIL_LANGUAGE
            content = mail_notify.build_deadline_at_risk(
                property_name=stay["property"],
                arrival=stay["arrival"].strftime("%d.%m.%Y"),
                deadline=stay["deadline"],
                unfiled=stay["unfiled"],
                stay_url=_stay_url(stay["reservation_id"]),
                lang=lang,
                no_guests=bool(stay.get("no_guests")),
            )
            outbox_id = mail.enqueue(
                kind="deadline_at_risk",
                idempotency_key=f"deadline_at_risk:{stay['reservation_id']}",
                to_email=to_email,
                subject=content["subject"],
                payload={"text": content["text"], "html": content["html"], "lang": lang},
                reservation_id=stay["reservation_id"],
                apartment_id=stay["apartment_id"],
                owner_user_id=stay["owner_user_id"],
            )
            if not outbox_id:
                # Mail is switched off or the address is unusable: try again on
                # the next run rather than marking a warning nobody got.
                continue
            stamp = _utc(now).replace(microsecond=0).isoformat()
            db.execute(
                "UPDATE reservation SET at_risk_mailed_at = ? "
                "WHERE id = ? AND at_risk_mailed_at IS NULL",
                (stamp, stay["reservation_id"]),
            )
            stay["mailed_at"] = stamp
            queued += 1
        except Exception:
            log.exception(
                "deadline_at_risk mail failed reservation_id=%s", stay["reservation_id"]
            )
    return queued


def send_operator_digest(
    stays: List[Dict[str, Any]],
    now: Optional[datetime] = None,
    unknown: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Queue the operator digest unless one went out in the last six hours.

    ``unknown`` (stays with no guest on file) is listed in its own section.
    """
    unknown = unknown or []
    if not stays and not unknown:
        return False
    to_email = mail.normalise_email(config.OPERATOR_EMAIL or "")
    if not to_email:
        return False
    current = _utc(now).replace(microsecond=0)
    last_raw = db.get_setting(DIGEST_SETTING)
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
        except ValueError:
            last = None
        # A stamp from the future (a clock set back) does not block the digest.
        if last is not None and timedelta(0) <= current - last < DIGEST_INTERVAL:
            return False
    lang = mail_notify.HOST_MAIL_LANGUAGE
    content = mail_notify.build_deadline_digest(stays, lang=lang, unknown=unknown)
    stamp = current.isoformat()
    outbox_id = mail.enqueue(
        kind="deadline_digest",
        idempotency_key=f"deadline_digest:{stamp}",
        to_email=to_email,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": lang},
    )
    if not outbox_id:
        return False
    db.set_setting(DIGEST_SETTING, stamp)
    return True


def manual_deadline_stays(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Manual-send stays in the last eight hours before the police deadline.

    ``deadline_at_risk`` already warned the host in the last twenty-four hours.
    This second note is closer to the deadline so the two mails do not leave
    together.
    """
    local = deadlines.local_now(now)
    found = []
    for stay in at_risk_stays(now, window=MANUAL_NOTICE_LEAD):
        if stay.get("automation_mode") != "manual" or stay.get("awaiting_retry"):
            continue
        if stay["deadline"] <= local:
            continue
        found.append(stay)
    return found


def notify_manual_hosts(stays: List[Dict[str, Any]], now: Optional[datetime] = None) -> int:
    """Queue the eight-hour manual-send note. One per stay. Returns how many."""
    queued = 0
    for stay in stays:
        key = f"manual_deadline:{stay['reservation_id']}"
        if db.query_one("SELECT id FROM email_outbox WHERE idempotency_key = ?", (key,)):
            continue
        try:
            to_email = mail_notify._entity_contact_email(stay["legal_entity_id"])
            if not to_email:
                continue
            lang = mail_notify.HOST_MAIL_LANGUAGE
            content = mail_notify.build_manual_deadline(
                property_name=stay["property"],
                arrival=stay["arrival"].strftime("%d.%m.%Y"),
                deadline=stay["deadline"],
                unfiled=stay["unfiled"],
                stay_url=_stay_url(stay["reservation_id"]),
                lang=lang,
            )
            outbox_id = mail.enqueue(
                kind="manual_deadline",
                idempotency_key=key,
                to_email=to_email,
                subject=content["subject"],
                payload={"text": content["text"], "html": content["html"], "lang": lang},
                reservation_id=stay["reservation_id"],
                apartment_id=stay["apartment_id"],
                owner_user_id=stay["owner_user_id"],
            )
            if outbox_id:
                queued += 1
        except Exception:
            log.exception(
                "manual deadline notice failed reservation=%s", stay.get("reservation_id")
            )
    return queued


def run(now: Optional[datetime] = None) -> Dict[str, int]:
    """One watchdog pass. Raises only if the at-risk query itself fails.

    ``at_risk`` counts only stays with known reportable guests; it alone
    decides the heartbeat. ``unknown_risk`` (no guest on file) does not.
    ``awaiting_retry`` counts the stays left out because their one automatic
    resend is still due (see the module docstring); they do not decide the
    heartbeat and get no mail yet.
    """
    every = at_risk_stays(now, include_awaiting_retry=True)
    stays = [stay for stay in every if not stay["awaiting_retry"]]
    awaiting = len(every) - len(stays)
    try:
        unknown = unknown_risk_stays(now)
    except Exception:
        # The weaker check must not silence the real one or its heartbeat.
        log.exception("unknown-risk query failed")
        unknown = []
    host_mails = notify_hosts(stays + unknown, now)
    try:
        manual_mails = notify_manual_hosts(manual_deadline_stays(now), now)
    except Exception:
        log.exception("manual deadline notice failed")
        manual_mails = 0
    try:
        digest = send_operator_digest(stays, now, unknown=unknown)
    except Exception:
        log.exception("deadline digest failed")
        digest = False
    return {
        "at_risk": len(stays),
        "unknown_risk": len(unknown),
        "awaiting_retry": awaiting,
        "host_mails": host_mails,
        "manual_mails": manual_mails,
        "digest": int(digest),
    }


def heartbeat_url(at_risk: bool) -> str:
    """The URL to ping for this run, or "" when the switch is not configured.

    healthchecks.io semantics: the base URL reports success, ``<url>/fail``
    reports a failure and alerts at once.
    """
    url = (config.HEARTBEAT_FILING_URL or "").strip().rstrip("/")
    if not url:
        return ""
    return f"{url}/fail" if at_risk else url
