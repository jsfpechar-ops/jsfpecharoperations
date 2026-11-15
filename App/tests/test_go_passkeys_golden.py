"""Freshness check for the passkey golden fixtures shared with Go.

``go/internal/web/auth/testdata/passkeys_python.json`` is written by
``scripts/go_passkeys_golden.py``. Both of its ceremonies are re-verified here
with py_webauthn the same way ``app/passkeys.py`` calls it.

If ``go/internal/web/auth/testdata/passkeys_go.json`` exists, the Go-written
login is verified the same way. When it is absent that check passes without
doing anything.
"""
import json
from pathlib import Path

from webauthn import verify_authentication_response, verify_registration_response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

REPO = Path(__file__).resolve().parents[2]
TESTDATA = REPO / "go/internal/web/auth/testdata"
PY_FIXTURE = TESTDATA / "passkeys_python.json"
GO_FIXTURE = TESTDATA / "passkeys_go.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_python_registration_reverifies():
    fx = _load(PY_FIXTURE)
    reg = fx["registration"]
    verified = verify_registration_response(
        credential=reg["credential"],
        expected_challenge=base64url_to_bytes(reg["challenge"]),
        expected_rp_id=fx["rp_id"],
        expected_origin=[fx["origin"]],
        require_user_verification=True,
    )
    assert bytes_to_base64url(verified.credential_id) == fx["credential_id"]
    assert bytes_to_base64url(verified.credential_public_key) == fx["public_key"]
    assert int(verified.sign_count or 0) == fx["sign_count"]


def test_python_stored_fields_consistent():
    fx = _load(PY_FIXTURE)
    assert fx["registration"]["credential"]["id"] == fx["credential_id"]
    assert fx["registration"]["credential"]["rawId"] == fx["credential_id"]
    assert fx["login"]["credential"]["rawId"] == fx["credential_id"]
    assert len(base64url_to_bytes(fx["user_handle"])) == 64
    assert fx["login"]["credential"]["response"]["userHandle"] == fx["user_handle"]


def test_python_login_reverifies():
    fx = _load(PY_FIXTURE)
    login = fx["login"]
    verified = verify_authentication_response(
        credential=login["credential"],
        expected_challenge=base64url_to_bytes(login["challenge"]),
        expected_rp_id=fx["rp_id"],
        expected_origin=[fx["origin"]],
        credential_public_key=base64url_to_bytes(fx["public_key"]),
        credential_current_sign_count=int(fx["sign_count"] or 0),
        require_user_verification=True,
    )
    assert int(verified.new_sign_count) == 7


def test_go_login_reverifies_if_present():
    if not GO_FIXTURE.exists():
        return
    fx = _load(GO_FIXTURE)
    assert fx["credential"]["rawId"] == fx["credential_id"]
    verified = verify_authentication_response(
        credential=fx["credential"],
        expected_challenge=base64url_to_bytes(fx["challenge"]),
        expected_rp_id=fx["rp_id"],
        expected_origin=[fx["origin"]],
        credential_public_key=base64url_to_bytes(fx["public_key"]),
        credential_current_sign_count=int(fx["sign_count_before"] or 0),
        require_user_verification=True,
    )
    assert bytes_to_base64url(verified.credential_id) == fx["credential_id"]
