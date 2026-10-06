"""Single Doručenka PDFs stay available to admins during workspace preview."""
from __future__ import annotations

from unittest.mock import MagicMock

from app import access, auth


def _request() -> MagicMock:
    return MagicMock()


def test_dorucenka_downloads_need_no_impersonation_gate(monkeypatch):
    monkeypatch.setattr(auth, "impersonating", lambda _r: False)
    assert access.dorucenka_download_visible(_request()) is True


def test_an_admin_may_fetch_dorucenka_while_previewing(monkeypatch):
    monkeypatch.setattr(auth, "impersonating", lambda _r: True)
    monkeypatch.setattr(auth, "current_user", lambda _r: {"role": "admin"})
    assert access.dorucenka_download_visible(_request()) is True


def test_a_non_admin_session_cannot_download_dorucenka_during_preview(monkeypatch):
    monkeypatch.setattr(auth, "impersonating", lambda _r: True)
    monkeypatch.setattr(auth, "current_user", lambda _r: {"role": "host"})
    assert access.dorucenka_download_visible(_request()) is False
