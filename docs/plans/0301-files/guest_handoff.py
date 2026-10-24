"""Brief 0301: the host side of Leon (AI).

When Leon cannot answer from the guide he writes a ``guest_question`` row
(brief 0300). This module alerts the host, lets the host answer in the app,
hands the answer back to the guest's conversation (a ``guest_chat_message``
with role ``host``, which the guide page renders) and turns an answer into a
guide card on one tap.

Alert channel (owner, 2026-10-24): the existing "needs you" stack. One open
alert per property (``alerts.raise_alert`` with a dedupe key) carries the
count of waiting questions and resolves itself when the last one is answered
or dismissed. One e-mail per batch: the mail goes out only when a new question
is the only open one for the property, so a host who has not yet opened the
app gets one mail, not one per guest message. Neither the alert nor the mail
carries any message text.

Privacy: the guest's message is already redacted (0300). Logs carry ids and
counts only. Rows are deleted with the chat (``leon.purge``, 30 days).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import alerts, config, db, guest_guide, host_i18n, mail, mail_notify

log = logging.getLogger(__name__)

ALERT_KIND = "guest_question"
MAIL_KIND = "guest_question"
MAX_ANSWER_CHARS = 1000
LIST_LIMIT = 50
_DOOR_VISIBILITY = {"qr": "everyone", "stay": "booked"}


class HandoffError(Exception):
    """A host-side mistake, named by a ``flash.error.*`` key."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def dedupe_key(apartment_id: int) -> str:
    return f"{ALERT_KIND}:{apartment_id}"


def questions_url(apartment_id: int) -> str:
    return f"/apartments/{apartment_id}/guide/questions"


# --- reading -----------------------------------------------------------------------

def open_count(apartment_id: int) -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM guest_question WHERE apartment_id = ? AND status = 'open'",
        (apartment_id,),
    )
    return int(row["n"]) if row else 0


_SELECT = (
    "SELECT q.id, q.chat_id, q.apartment_id, q.message_id, q.summary, q.status, q.answer, q.created_at, "
    "q.answered_at, c.door, c.lang, m.text AS question "
    "FROM guest_question q JOIN guest_chat c ON c.id = q.chat_id "
    "JOIN guest_chat_message m ON m.id = q.message_id "
)


def questions(apartment_id: int, limit: int = LIST_LIMIT) -> List[Dict[str, Any]]:
    """Open questions first (oldest first, so nobody waits longest), then the rest, newest first."""
    rows = db.query(
        _SELECT + "WHERE q.apartment_id = ? "
        "ORDER BY CASE q.status WHEN 'open' THEN 0 ELSE 1 END, "
        "CASE q.status WHEN 'open' THEN q.id ELSE -q.id END LIMIT ?",
        (apartment_id, int(limit)),
    )
    return [dict(r) for r in rows]


def get(apartment_id: int, question_id: int) -> Optional[Dict[str, Any]]:
    """One question, only when it belongs to ``apartment_id`` (the caller has checked ownership)."""
    row = db.query_one(_SELECT + "WHERE q.id = ? AND q.apartment_id = ?", (question_id, apartment_id))
    return dict(row) if row else None


def card_title(question: Dict[str, Any]) -> str:
    """The guide card title an answer would get: Leon's summary, else the question, cut to the title limit."""
    text = " ".join(str(question.get("summary") or question.get("question") or "").split())
    return (text or "Guest question")[: guest_guide.LIMITS["title"]].strip()


def card_for(question: Dict[str, Any]) -> Optional[int]:
    """The custom card this question already became, if the host tapped "Add to guide" before."""
    row = db.query_one(
        "SELECT id FROM guide_item WHERE apartment_id = ? AND kind = 'custom' AND title = ? ORDER BY id DESC LIMIT 1",
        (question["apartment_id"], card_title(question)),
    )
    return int(row["id"]) if row else None


# --- the alert and the one mail ----------------------------------------------------

def _property(apartment_id: int):
    return db.query_one(
        "SELECT id, internal_name, legal_entity_id, owner_user_id FROM apartment WHERE id = ?", (apartment_id,)
    )


def refresh_alert(apartment_id: int) -> int:
    """Keep the one "needs you" line in step with the open count. Returns the count."""
    count = open_count(apartment_id)
    key = dedupe_key(apartment_id)
    if count == 0:
        alerts.resolve(key)
        return 0
    home = _property(apartment_id)
    name = (home["internal_name"] if home else "") or ""
    alerts.raise_alert(
        "warning", ALERT_KIND,
        f"{count} guest question(s) wait for an answer at {name}",
        "Leon (AI) could not answer from the guide. Answer in the app; the guest sees it on the guide page.",
        dedupe_key=key, apartment_id=apartment_id,
        params={"property": name, "count": count},
    )
    return count


def build_mail(property_name: str, url: str, lang: Optional[str] = None) -> Dict[str, str]:
    """Subject, text and HTML of the one host mail: no message text, just where to answer."""
    lang = host_i18n.normalise_language(lang or mail_notify.HOST_MAIL_LANGUAGE)
    text = lambda key, **kw: host_i18n.translate(lang, key, **kw)  # noqa: E731
    subject = text("mail.guest_question.subject", property=property_name)
    heading = text("mail.guest_question.heading")
    intro = text("mail.guest_question.intro", property=property_name)
    action = text("mail.guest_question.action")
    footer = text("mail.guest_question.footer")
    blocks = mail_notify._guest_blocks(heading=heading, intro=intro, action_url=url, action_label=action)
    return {
        "subject": subject,
        "text": "\n".join([intro, "", f"{action}: {url}", "", "--", "UbyHost", footer]),
        "html": mail_notify._shell(lang=lang, title=property_name, preheader=intro, blocks=blocks,
                                   footer_lines=["UbyHost", footer]),
    }


def on_new_question(question_id: int) -> None:
    """Called by ``leon.reply`` right after it writes the row. Never raises: the guest reply comes first."""
    try:
        row = db.query_one("SELECT apartment_id FROM guest_question WHERE id = ?", (question_id,))
        if not row:
            return
        apartment_id = int(row["apartment_id"])
        count = refresh_alert(apartment_id)
        if count != 1:
            log.info("guest question %s apartment=%s open=%s (batch mail already sent)", question_id, apartment_id, count)
            return
        home = _property(apartment_id)
        to_email = mail_notify._entity_contact_email(home["legal_entity_id"]) if home else ""
        if not to_email:
            log.info("guest question %s apartment=%s: no host address, alert only", question_id, apartment_id)
            return
        content = build_mail(home["internal_name"] or "", f"{config.app_base_url()}{questions_url(apartment_id)}")
        mail.enqueue(
            kind=MAIL_KIND, idempotency_key=f"{MAIL_KIND}:{apartment_id}:{question_id}", to_email=to_email,
            subject=content["subject"],
            payload={"text": content["text"], "html": content["html"], "lang": mail_notify.HOST_MAIL_LANGUAGE},
            apartment_id=apartment_id, owner_user_id=home["owner_user_id"],
        )
        log.info("guest question %s apartment=%s: host mailed", question_id, apartment_id)
    except Exception:
        log.exception("guest question %s: host alert failed", question_id)


# --- the host acts ---------------------------------------------------------------

def clean_answer(text: Any) -> str:
    value = str(text or "").replace("\r\n", "\n").strip()
    if not value:
        raise HandoffError("flash.error.guest_question_empty")
    if len(value) > MAX_ANSWER_CHARS:
        raise HandoffError("flash.error.guest_question_too_long")
    return value


def answer(apartment_id: int, question_id: int, text: Any) -> Dict[str, Any]:
    """Store the host's answer as written and show it in the guest's conversation."""
    question = get(apartment_id, question_id)
    if not question:
        raise HandoffError("flash.error.guest_question_gone")
    value = clean_answer(text)
    now = db.utcnow()
    db.insert("guest_chat_message", {
        "chat_id": question["chat_id"], "role": "host", "kind": "answer", "text": value, "sources": "",
        "created_at": now,
    })
    db.execute("UPDATE guest_chat SET last_message_at = ? WHERE id = ?", (now, question["chat_id"]))
    db.update("guest_question", question_id, {"answer": value, "answered_at": now, "status": "answered"})
    refresh_alert(apartment_id)
    log.info("guest question %s apartment=%s settled", question_id, apartment_id)
    return get(apartment_id, question_id) or question


def dismiss(apartment_id: int, question_id: int) -> None:
    question = get(apartment_id, question_id)
    if not question:
        raise HandoffError("flash.error.guest_question_gone")
    if question["status"] == "open":
        db.update("guest_question", question_id, {"status": "dismissed", "answered_at": db.utcnow()})
    refresh_alert(apartment_id)
    log.info("guest question %s apartment=%s dismissed", question_id, apartment_id)


def add_to_guide(apartment_id: int, question_id: int, topic: str) -> int:
    """One tap: the answer becomes a host-saved custom card the host can still edit. Returns the card id."""
    question = get(apartment_id, question_id)
    if not question:
        raise HandoffError("flash.error.guest_question_gone")
    if question["status"] != "answered" or not question["answer"]:
        raise HandoffError("flash.error.guest_question_not_answered")
    existing = card_for(question)
    if existing:
        return existing
    item_id = guest_guide.add_custom(apartment_id, topic, card_title(question))
    guest_guide.save(apartment_id, item_id, {
        "steps": question["answer"],
        "visibility": _DOOR_VISIBILITY.get(question["door"] or "", "booked"),
    })
    log.info("guest question %s apartment=%s became card %s", question_id, apartment_id, item_id)
    return int(item_id)
