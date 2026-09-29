"""AR-02 (Task 3.2): an ambiguous UbyPort outcome is not "not sent".

A timeout after the request was sent, a 5xx, an unreadable answer or a
record-count mismatch may all mean the record was filed. Those raise
``UbyportOutcomeUnknownError`` so a caller can stop instead of refiling a
duplicate the police count against the host. A failure that cannot have reached
the server stays a plain ``UbyportTransportError``.
"""
from __future__ import annotations

import pytest
import requests
import urllib3

from app.ubyport.client import (
    UbyportAuthError,
    UbyportClient,
    UbyportOutcomeUnknownError,
    UbyportTransportError,
)


def _client() -> UbyportClient:
    return UbyportClient("https://ubyport.invalid", "user", "password")


def _raising_post(exc: Exception):
    def fake_post(*_args, **_kwargs):
        raise exc

    return fake_post


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_read_timeout_is_outcome_unknown_with_the_sent_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.ubyport.client.requests.post", _raising_post(requests.ReadTimeout("t"))
    )

    with pytest.raises(UbyportOutcomeUnknownError) as caught:
        _client().submit({}, [{}])

    assert caught.value.request_xml


def test_connect_timeout_is_definitely_not_sent(monkeypatch):
    monkeypatch.setattr(
        "app.ubyport.client.requests.post", _raising_post(requests.ConnectTimeout("t"))
    )

    with pytest.raises(UbyportTransportError) as caught:
        _client().submit({}, [{}])

    assert not isinstance(caught.value, UbyportOutcomeUnknownError)


def test_a_refused_connection_is_definitely_not_sent(monkeypatch):
    exc = requests.ConnectionError(
        urllib3.exceptions.MaxRetryError(
            None, "https://x", urllib3.exceptions.NewConnectionError(None, "refused")
        )
    )
    monkeypatch.setattr("app.ubyport.client.requests.post", _raising_post(exc))

    with pytest.raises(UbyportTransportError) as caught:
        _client().submit({}, [{}])

    assert not isinstance(caught.value, UbyportOutcomeUnknownError)


def test_a_5xx_is_outcome_unknown(monkeypatch):
    monkeypatch.setattr(
        "app.ubyport.client.requests.post",
        lambda *_args, **_kwargs: _FakeResponse(503),
    )

    with pytest.raises(UbyportOutcomeUnknownError) as caught:
        _client().submit({}, [{}])

    assert caught.value.request_xml


def test_a_401_is_an_auth_error_and_still_a_transport_error(monkeypatch):
    """AR-18: a refused login gets its own class so the caller can pause, not retry."""
    monkeypatch.setattr(
        "app.ubyport.client.requests.post",
        lambda *_args, **_kwargs: _FakeResponse(401),
    )

    with pytest.raises(UbyportAuthError) as caught:
        _client().submit({}, [{}])

    assert isinstance(caught.value, UbyportTransportError)
    assert not isinstance(caught.value, UbyportOutcomeUnknownError)
