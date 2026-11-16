"""A1: a transport error says what happened (cause), and the copy follows it.

UbyPort answering with a fault, an HTTP 4xx or a redirect is not "could not be
reached". The cause travels on the exception as a structured field, never read
back from the message text. A 4xx body is never kept.
"""
from __future__ import annotations

import pytest
import requests

from app.routes import admin
from app.mail_notify import build_submission_problem
from app.ubyport import soap
from app.ubyport.client import (
    UbyportAuthError,
    UbyportClient,
    UbyportOutcomeUnknownError,
    UbyportTransportError,
)

FAULT_XML = (
    '<?xml version="1.0"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
    "<soap:Fault><faultcode>Chyba běhu programu</faultcode>"
    "<faultstring>Odpověď neobsahuje záznamy o chybách</faultstring></soap:Fault>"
    "</soap:Body></soap:Envelope>"
)
FAULT_DETAIL = "Chyba běhu programu / Odpověď neobsahuje záznamy o chybách"


def _client() -> UbyportClient:
    return UbyportClient("https://ubyport.invalid", "user", "password")


def _raising_post(exc: Exception):
    def fake_post(*_args, **_kwargs):
        raise exc

    return fake_post


def _answering_post(status: int, text: str = ""):
    class _Resp:
        def __init__(self) -> None:
            self.status_code = status
            self.text = text

    def fake_post(*_args, **_kwargs):
        return _Resp()

    return fake_post


def _submit_and_catch(monkeypatch, post) -> Exception:
    monkeypatch.setattr("app.ubyport.client.requests.post", post)
    with pytest.raises(UbyportTransportError) as caught:
        _client().submit({}, [{}])
    return caught.value


def test_refused_connection_has_cause_dial(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _raising_post(requests.ConnectTimeout("refused")))
    assert exc.cause == "dial"
    assert exc.detail == ""


def test_401_has_cause_auth(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _answering_post(401))
    assert isinstance(exc, UbyportAuthError)
    assert exc.cause == "auth"


def test_redirect_has_cause_redirect_and_status_detail(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _answering_post(302))
    assert exc.cause == "redirect"
    assert exc.detail == "HTTP 302"


def test_fault_has_cause_fault_and_clean_detail(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _answering_post(200, FAULT_XML))
    assert exc.cause == "fault"
    assert exc.detail == FAULT_DETAIL


def test_fault_on_500_is_a_fault_not_outcome_unknown(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _answering_post(500, FAULT_XML))
    assert not isinstance(exc, UbyportOutcomeUnknownError)
    assert exc.cause == "fault"


def test_4xx_has_cause_http4xx_and_never_the_body(monkeypatch):
    exc = _submit_and_catch(monkeypatch, _answering_post(404, "<html>Novak P1100220</html>"))
    assert exc.cause == "http4xx"
    assert exc.detail == "HTTP 404"
    assert "Novak" not in str(exc)
    assert "P1100220" not in str(exc)


def test_5xx_stays_outcome_unknown_without_cause(monkeypatch):
    monkeypatch.setattr(
        "app.ubyport.client.requests.post", _answering_post(503, "busy")
    )
    with pytest.raises(UbyportOutcomeUnknownError) as caught:
        _client().submit({}, [{}])
    assert caught.value.cause == ""


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ("Chyba / Odpověď", "Chyba / Odpověď"),
        ("a<b>bold</b>  c\n d", "a bold c d"),
        ("x" * 250, "x" * 200 + "…"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_fault_text_cases(raw, cleaned):
    assert soap.clean_fault_text(raw) == cleaned


@pytest.mark.parametrize(
    "cause, key",
    [
        ("dial", "flash.error.ubyport_unreachable"),
        ("auth", "flash.error.ubyport_login_refused"),
        ("fault", "flash.error.ubyport_fault"),
        ("http4xx", "flash.error.ubyport_http_error"),
        ("redirect", "flash.error.ubyport_http_error"),
        ("setup", "flash.error.ubyport_send_failed"),
        ("", "flash.error.ubyport_send_failed"),
    ],
)
def test_transport_flash_picks_the_key_by_cause(monkeypatch, cause, key):
    monkeypatch.setattr(admin, "_flash", lambda request, key, **p: (key, p))
    got_key, _ = admin._transport_flash(None, {"cause": cause, "detail": "HTTP 404"})
    assert got_key == key


def test_transport_flash_ignores_the_error_text(monkeypatch):
    monkeypatch.setattr(admin, "_flash", lambda request, key, **p: (key, p))
    got_key, _ = admin._transport_flash(
        None, {"cause": "dial", "error": "UbyPort returned a SOAP fault: x"}
    )
    assert got_key == "flash.error.ubyport_unreachable"


def test_answered_mail_never_says_the_connection_failed():
    dial_text = build_submission_problem(
        property_name="Byt", state="transport_error", reason="could not reach",
        transport=True, cause="dial", stays=[], submission_id=None, lang="en",
    )["text"]
    fault_text = build_submission_problem(
        property_name="Byt", state="transport_error",
        reason="UbyPort returned a SOAP fault: Chyba", transport=True, cause="fault",
        stays=[], submission_id=None, lang="en",
    )["text"]
    assert "The connection to UbyPort failed before the report was delivered." in dial_text
    assert "The connection to UbyPort failed before the report was delivered." not in fault_text
    assert "Chyba" in fault_text
