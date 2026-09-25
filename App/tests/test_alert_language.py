"""A host reads every alert card in their own language [F5, F6, F12].

The alert table stores English prose because the log line and the e-mail copy
are English, but the card on screen is rebuilt from ``notification.*`` copy at
render time. That only works if the alert carried the values the copy
interpolates, so these tests pin both halves: the storage and the render.
"""
from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pytest

from app import alerts, host_i18n

APP = Path(__file__).resolve().parents[1] / "app"

# A stored kind and a representative set of the values its copy interpolates.
STORED_KINDS = {
    "cancelled_after_report": {"date": "2026-09-11", "variant": "cancelled"},
    "feed_error": {"feed": "Karlín Loft", "error": "boom"},
    "submission_immediate": {"property": "Loft", "error": "boom"},
    "submission_transport": {"property": "Loft", "error": "boom"},
    "submission_rejected": {"property": "Loft", "count": 3, "failed": 2, "blocked": 1},
    "receipt_missing": {"property": "Loft", "submission": 4711, "count": 2},
    "apartment_setup": {"property": "Loft"},
    "mail_failed": {"kind": "claim", "to": "g@example.test", "error": "boom"},
    "turnstile_unavailable": {},
    "guest_pin_rotated": {},
    "guest_pin_abuse": {},
}

ENGLISH_MARKER = "english log copy"


def _card(kind, message, detail, params, lang):
    row = {
        "kind": kind,
        "message": message,
        "detail": detail,
        "params": json.dumps(params, ensure_ascii=False) if params else None,
    }
    return alerts.present(row, lang)


def test_no_converted_kind_shows_the_stored_english_prose_in_czech():
    for kind, params in STORED_KINDS.items():
        shown = _card(kind, ENGLISH_MARKER, ENGLISH_MARKER, params, "cs")
        assert shown["display_title"] != ENGLISH_MARKER, kind
        # apartment_setup is the one kind whose detail is a code list UbyPort
        # returns itself, so it is deliberately not translated.
        if kind != "apartment_setup":
            assert ENGLISH_MARKER not in shown["display_detail"], kind
        assert "%(" not in shown["display_title"] + shown["display_detail"], kind
        # Both languages must produce text - a missing key would render the key.
        for lang in ("en", "cs"):
            card = _card(kind, "stored", "stored", params, lang)
            assert card["display_title"] and card["display_title"] != "stored", (kind, lang)


def test_a_stay_cancelled_after_reporting_is_described_in_the_hosts_language():
    message = (
        "A stay from 2026-09-11 was cancelled in the calendar after it had "
        "already been reported to the police."
    )
    params = {"date": "2026-09-11", "variant": "cancelled"}

    en = _card("cancelled_after_report", message, "english detail", params, "en")
    assert en["display_title"] == (
        "A stay from 2026-09-11 was cancelled in the calendar after it had "
        "already been reported to the police."
    )
    assert en["display_detail"] == "Check whether the booking was cancelled or merely moved."

    cs = _card("cancelled_after_report", message, "english detail", params, "cs")
    assert cs["display_title"] == (
        "Pobyt od 2026-09-11 byl v kalendáři zrušen poté, co již byl nahlášen na policii."
    )
    assert cs["display_detail"] == (
        "Zkontrolujte, zda byla rezervace zrušena, nebo se jen přesunula."
    )


def test_a_stay_that_vanished_uses_the_other_variant_wording():
    """One kind, two events - the variant picks the sentence, not the kind."""
    params = {"date": "2026-09-11", "variant": "disappeared"}
    en = _card("cancelled_after_report", "stored english", "stored detail", params, "en")
    cs = _card("cancelled_after_report", "stored english", "stored detail", params, "cs")
    assert en["display_title"] == (
        "A stay from 2026-09-11 disappeared from the calendar after it had "
        "already been reported to the police."
    )
    assert cs["display_title"] == (
        "Pobyt od 2026-09-11 zmizel z kalendáře poté, co již byl nahlášen na policii."
    )
    assert "zrušen" not in cs["display_title"]


def test_a_calendar_failure_card_names_the_feed_and_the_error():
    params = {"feed": "Karlín Loft", "error": "HTTP 500 from the calendar server"}
    en = _card("feed_error", "stored", "stored", params, "en")
    cs = _card("feed_error", "stored", "stored", params, "cs")
    assert en["display_title"] == "Calendar 'Karlín Loft' could not be synchronised."
    assert en["display_detail"] == (
        "The calendar server answered: HTTP 500 from the calendar server"
    )
    assert cs["display_title"] == "Kalendář 'Karlín Loft' se nepodařilo synchronizovat."
    assert "HTTP 500" in cs["display_detail"]


@pytest.mark.parametrize(
    "kind,params,expected_en,expected_cs",
    [
        (
            "submission_immediate",
            {"property": "Loft", "error": "timeout"},
            "Loft: automatic send failed after registration completed.",
            "Loft: automatické odeslání po dokončení registrace selhalo.",
        ),
        (
            "submission_transport",
            {"property": "Loft", "error": "timeout"},
            "Loft: could not deliver data to UbyPort.",
            "Loft: data se nepodařilo doručit do UbyPortu.",
        ),
    ],
)
def test_a_failed_send_is_rebuilt_from_its_parameters(kind, params, expected_en, expected_cs):
    en = _card(kind, "stored", "stored", params, "en")
    cs = _card(kind, "stored", "stored", params, "cs")
    assert en["display_title"] == expected_en
    assert cs["display_title"] == expected_cs
    assert "timeout" in en["display_detail"] and "timeout" in cs["display_detail"]


def test_a_rejected_report_counts_the_records_in_the_hosts_language():
    params = {"property": "Loft", "count": 3, "failed": 2, "blocked": 1}
    en = _card("submission_rejected", "stored", "stored", params, "en")
    cs = _card("submission_rejected", "stored", "stored", params, "cs")
    assert en["display_title"] == "Loft: UbyPort did not accept 3 guest record(s)."
    assert cs["display_title"] == "Loft: UbyPort nepřijal 3 záznamů hostů."
    assert "2" in en["display_detail"] and "1" in en["display_detail"]
    assert "2" in cs["display_detail"] and "1" in cs["display_detail"]
    assert "Report header rejected" not in en["display_detail"]


def test_a_rejected_header_is_an_optional_leading_clause():
    """The extra sentence appears only when the report header was refused."""
    params = {"property": "Loft", "count": 3, "failed": 2, "blocked": 1, "header": "IČO invalid"}
    en = _card("submission_rejected", "stored", "stored", params, "en")
    cs = _card("submission_rejected", "stored", "stored", params, "cs")
    assert en["display_detail"].startswith("Report header rejected: IČO invalid")
    assert cs["display_detail"].startswith("Hlavička hlášení byla odmítnuta: IČO invalid")


def test_a_missing_receipt_card_names_the_submission():
    params = {"property": "Loft", "submission": 4711, "count": 2}
    en = _card("receipt_missing", "stored", "stored", params, "en")
    cs = _card("receipt_missing", "stored", "stored", params, "cs")
    assert en["display_title"] == (
        "Loft: UbyPort accepted the report but returned no confirmation."
    )
    assert cs["display_title"] == "Loft: UbyPort hlášení přijal, ale nevrátil potvrzení."
    assert "4711" in en["display_detail"] and "4711" in cs["display_detail"]


def test_the_ubyport_code_list_stays_english_on_purpose():
    """There is nothing to translate: UbyPort returns those codes itself."""
    params = {"property": "Loft"}
    cs = _card("apartment_setup", "stored english", "IČO is missing", params, "cs")
    assert cs["display_title"] == (
        "Loft: nastavení UbyPortu není úplné, nelze nic nahlásit."
    )
    assert cs["display_detail"] == "IČO is missing"


def test_a_card_whose_parameters_were_never_stored_keeps_its_english_copy():
    """An alert raised before this release must not show ``%(property)s``."""
    row = {"kind": "submission_rejected", "message": "old english", "detail": "old detail"}
    for lang in ("en", "cs"):
        shown = alerts.present(row, lang)
        assert shown["display_title"] == "old english"
        assert shown["display_detail"] == "old detail"
        assert "%(" not in shown["display_title"] + shown["display_detail"]


def test_an_unparseable_parameter_blob_falls_back_instead_of_raising():
    row = {
        "kind": "submission_rejected",
        "message": "old english",
        "detail": "old detail",
        "params": "{not json",
    }
    shown = alerts.present(row, "cs")
    assert shown["display_title"] == "old english"


def test_raise_alert_stores_the_values_the_card_needs(monkeypatch):
    """The storage half: what the call site passes is what the card renders."""
    captured = {}

    def fake_insert(table, values):
        captured.update(values)
        return 1

    monkeypatch.setattr(alerts.db, "query_one", lambda sql, params=(): None)
    monkeypatch.setattr(alerts.db, "insert", fake_insert)
    monkeypatch.setattr(alerts.db, "update", lambda *a, **k: None)

    alerts.raise_alert(
        "warning",
        "submission_transport",
        "Loft: could not deliver data to UbyPort.",
        "timeout",
        dedupe_key="submission_transport:1",
        apartment_id=1,
        params={"property": "Loft", "error": "timeout"},
    )

    assert json.loads(captured["params"]) == {"property": "Loft", "error": "timeout"}
    shown = alerts.present(captured, "cs")
    assert shown["display_title"] == "Loft: data se nepodařilo doručit do UbyPortu."
    assert "timeout" in shown["display_detail"]


def test_raise_alert_without_parameters_stores_no_parameter_blob(monkeypatch):
    captured = {}
    monkeypatch.setattr(alerts.db, "query_one", lambda sql, params=(): None)
    monkeypatch.setattr(alerts.db, "insert", lambda table, values: captured.update(values))
    alerts.raise_alert(
        "warning",
        "guest_pin_abuse",
        "Guest link temporarily blocked after repeated wrong PINs.",
        "Review the message PIN.",
        dedupe_key="guest_pin_abuse:1",
        apartment_id=1,
    )
    assert captured["params"] is None
    shown = alerts.present(captured, "cs")
    assert shown["display_title"] == (
        "Hostovský odkaz byl po opakovaných chybných PINech dočasně zablokován."
    )


def test_a_dead_background_job_card_names_the_job_in_czech():
    alert = {
        "kind": "job_failed",
        "dedupe_key": "job_failed:ical",
        "message": "english log copy",
        "detail": "english log copy",
    }
    en = alerts.present(alert, "en")
    cs = alerts.present(alert, "cs")
    assert en["display_title"] == "Background job 'calendar sync' failed."
    assert cs["display_title"] == "Úloha na pozadí 'synchronizace kalendáře' selhala."
    assert cs["display_detail"] == (
        "Automatické hlášení se může zpozdit, dokud úloha neproběhne znovu."
    )


def _raise_alert_calls():
    """Every ``alerts.raise_alert`` call in the application, as (file, kind, kwargs)."""
    found = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "raise_alert":
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "alerts":
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                continue
            keywords = {kw.arg for kw in node.keywords}
            found.append((path.name, node.args[1].value, keywords))
    return found


def _copy_keys(kind, lang):
    """The ``notification.*`` keys that can title a card of this kind."""
    table = host_i18n.STRINGS[lang]
    keys = [
        key
        for key in table
        if key == f"notification.{kind}.title"
        or key.startswith(f"notification.{kind}.title.")
    ]
    if kind in alerts._COMPUTED_ALERT_KINDS:
        # A computed card takes its title from the stay or the property, so it
        # needs a reason line instead of a kind-specific title.
        keys += [
            key
            for key in table
            if key == f"notification.reason.{kind}"
            or key.startswith(f"notification.reason.{kind}.")
        ]
    return keys


def test_every_alert_kind_that_interpolates_gets_its_values_passed():
    """A kind whose copy interpolates must carry ``params``, or hosts read English.

    This is the regression guard for the whole conversion: adding a
    ``%(property)s`` to a ``notification.*`` key and forgetting ``params=`` at
    the call site is otherwise invisible until a Czech host sees the card.
    Computed kinds are exempt - they interpolate live data, not stored values.
    """
    calls = _raise_alert_calls()
    assert calls, "no raise_alert call sites found - the AST walk is broken"
    missing = []
    for filename, kind, keywords in calls:
        if kind in alerts._COMPUTED_ALERT_KINDS:
            continue
        table = host_i18n.STRINGS["en"]
        keys = _copy_keys(kind, "en") + [
            key
            for key in table
            if key == f"notification.{kind}.detail"
            or key.startswith(f"notification.{kind}.detail.")
            or key == f"notification.{kind}.header"
        ]
        if not any("%(" in table[key] for key in keys):
            continue
        if "params" not in keywords:
            missing.append(f"{filename}: {kind}")
    assert missing == [], f"these call sites raise an interpolating alert with no params: {missing}"


# What each computed kind needs to render: nothing, a feed row, or a stay.
COMPUTED_FIXTURES = {
    "deadline": "stay",
    "guest_incomplete_checkin": "stay",
    "headcount_mismatch": "stay",
    "dates_changed_resign": "stay",
    "moved_after_report": "stay",
    "submission_stuck": "stay",
    "job_failed": "none",
    "feed_incomplete": "feed",
    "feed_duplicate_uid": "feed",
    "feed_recurring_event": "feed",
}


def test_the_computed_kind_list_and_its_fixtures_agree():
    assert alerts._COMPUTED_ALERT_KINDS == set(COMPUTED_FIXTURES)


@pytest.mark.parametrize("kind", sorted(COMPUTED_FIXTURES))
def test_a_computed_card_is_rendered_from_live_data_in_both_languages(kind, monkeypatch):
    reservation = {
        "id": 7,
        "date_from": "2026-09-19",
        "date_to": "2026-09-21",
        "internal_name": "Vinohrady Studio (demo)",
        "apartment_id": 1,
        "expected_guests": 2,
    }
    wants = COMPUTED_FIXTURES[kind]

    def fake_query_one(sql, params=()):
        if wants == "feed" or "internal_name FROM apartment" in sql:
            return {"internal_name": "Vinohrady Studio (demo)"}
        return reservation if wants == "stay" else None

    monkeypatch.setattr(alerts.db, "query_one", fake_query_one)
    monkeypatch.setattr(
        "app.reporting.reservation_progress",
        lambda _r: {"filled": 0, "expected": 2, "status": "awaiting_guest", "incomplete": True},
    )
    monkeypatch.setattr(
        "app.reporting.reservation_deadline_anchor", lambda _r: date(2026, 9, 19)
    )

    alert = {
        "kind": kind,
        "reservation_id": 7 if wants == "stay" else None,
        "apartment_id": 1,
        "dedupe_key": "job_failed:ical" if kind == "job_failed" else "",
        "message": ENGLISH_MARKER,
        "detail": ENGLISH_MARKER,
    }
    for lang in ("en", "cs"):
        shown = alerts.present(alert, lang)
        assert shown["display_title"], (kind, lang)
        assert shown["display_detail"], (kind, lang)
        # A missing key would come back as the key itself.
        assert "notification." not in shown["display_title"], (kind, lang)
        assert "notification." not in shown["display_detail"], (kind, lang)
    assert alerts.present(alert, "cs")["display_detail"] != alerts.present(alert, "en")[
        "display_detail"
    ], kind


def test_every_alert_kind_has_a_translated_card():
    """No call site may raise a kind the presentation layer cannot name."""
    for filename, kind, _keywords in _raise_alert_calls():
        if kind in alerts._COMPUTED_ALERT_KINDS:
            continue
        for lang in ("en", "cs"):
            assert _copy_keys(kind, lang), (
                f"{filename} raises {kind} with no title copy for {lang}"
            )


# --- W5.4: the flash messages a host reads after a form post ----------------

ROUTE_MODULES = ["routes/admin.py", "routes/admin_accounts.py"]


def test_every_flash_key_exists_in_both_languages():
    keys = [key for key in host_i18n.STRINGS["en"] if key.startswith("flash.")]
    assert len(keys) >= 43, "the flash catalogue lost keys"
    for key in keys:
        for lang in ("en", "cs"):
            text = host_i18n.STRINGS[lang].get(key)
            assert text, (key, lang)
            # An interpolating message must interpolate the same names in both.
            names = {
                part.split(")")[0]
                for part in text.split("%(")[1:]
                if ")" in part
            }
            assert names == _placeholder_names(host_i18n.STRINGS["en"][key]), (key, lang)


def _placeholder_names(text):
    return {part.split(")")[0] for part in text.split("%(")[1:] if ")" in part}


def test_no_route_still_flashes_a_hardcoded_english_message():
    """``back()`` carries a plain string, so it must be translated at the raise."""
    for relative in ROUTE_MODULES:
        source = (APP / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name) or func.id != "_back":
                continue
            for keyword in node.keywords:
                if keyword.arg != "msg":
                    continue
                # _flash(...) and a variable holding one are fine; a bare
                # literal or an f-string is not.
                value = keyword.value
                if isinstance(value, ast.Constant) and value.value:
                    offenders.append((node.lineno, value.value))
        assert offenders == [], f"{relative} flashes English: {offenders}"


def test_a_flash_message_follows_the_hosts_language(monkeypatch):
    from app.routes import admin_helpers

    class FakeRequest:
        pass

    monkeypatch.setattr(
        admin_helpers.host_i18n, "lang_from_request", lambda _request: "cs"
    )
    text = admin_helpers.flash(FakeRequest(), "flash.entities.saved")
    assert text == "Uloženo."
    monkeypatch.setattr(
        admin_helpers.host_i18n, "lang_from_request", lambda _request: "en"
    )
    assert admin_helpers.flash(FakeRequest(), "flash.entities.saved") == "Saved."
    assert admin_helpers.flash(FakeRequest(), "flash.apartments.pin_rotated") == (
        "New PIN generated. Copy it from the guest link card and update your "
        "portal messages."
    )
