"""Brief 0204: Web Push encryption and VAPID, checked against the RFCs."""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app import webpush

# RFC 8291, section 5 and appendix A.
RFC_PLAINTEXT = b"When I grow up, I want to be a watermelon"
RFC_UA_PUBLIC = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
RFC_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RFC_AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
RFC_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
RFC_BODY = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
    "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
    "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def test_encryption_reproduces_the_rfc_8291_example_byte_for_byte():
    body = webpush.encrypt(
        RFC_PLAINTEXT,
        webpush.unb64url(RFC_UA_PUBLIC),
        webpush.unb64url(RFC_AUTH),
        as_private=webpush.private_from_raw(webpush.unb64url(RFC_AS_PRIVATE)),
        salt=webpush.unb64url(RFC_SALT),
    )
    assert webpush.b64url(body) == RFC_BODY


def test_every_message_gets_a_fresh_key_and_salt():
    ua = webpush.public_raw(webpush.new_private_key())
    first = webpush.encrypt(b"x", ua, b"0" * 16)
    second = webpush.encrypt(b"x", ua, b"0" * 16)
    assert first[:16] != second[:16]
    assert first[21:86] != second[21:86]


def test_the_vapid_token_is_signed_by_the_servers_key():
    key = webpush.new_private_key()
    header = webpush.vapid_header(
        key, "https://fcm.googleapis.com", "mailto:support@ubyhost.com", now=1000
    )
    token, public = header.removeprefix("vapid t=").split(", k=")
    assert webpush.unb64url(public) == webpush.public_raw(key)
    head, claims, signature = token.split(".")
    assert json.loads(webpush.unb64url(head)) == {"typ": "JWT", "alg": "ES256"}
    assert json.loads(webpush.unb64url(claims)) == {
        "aud": "https://fcm.googleapis.com",
        "exp": 1000 + 12 * 3600,
        "sub": "mailto:support@ubyhost.com",
    }
    raw = webpush.unb64url(signature)
    key.public_key().verify(
        encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
        f"{head}.{claims}".encode("ascii"),
        ec.ECDSA(hashes.SHA256()),
    )


def test_a_key_round_trips_through_its_raw_form():
    key = webpush.new_private_key()
    again = webpush.private_from_raw(webpush.private_raw(key))
    assert webpush.public_raw(again) == webpush.public_raw(key)


@pytest.mark.parametrize(
    "raw", [b"", b"\x04" + b"\x00" * 64, b"\x02" + b"\x01" * 64, b"\x04" * 10]
)
def test_a_browser_key_that_is_not_a_p256_point_is_refused(raw):
    with pytest.raises(ValueError):
        webpush.check_public_key(raw)


def test_send_posts_an_encrypted_body_with_the_standard_headers(monkeypatch):
    seen = {}

    class _Answer:
        status_code = 201

    def fake_post(url, data, headers, timeout, allow_redirects):
        seen.update(url=url, data=data, headers=headers, timeout=timeout, redirects=allow_redirects)
        return _Answer()

    monkeypatch.setattr(webpush.requests, "post", fake_post)
    ua = webpush.new_private_key()
    status = webpush.send(
        "https://fcm.googleapis.com/fcm/send/abc",
        webpush.public_raw(ua),
        b"1" * 16,
        b'{"title":"x"}',
        private_key=webpush.new_private_key(),
        subject="mailto:support@ubyhost.com",
        ttl=86400,
    )
    assert status == 201
    assert seen["url"] == "https://fcm.googleapis.com/fcm/send/abc"
    assert seen["headers"]["Content-Encoding"] == "aes128gcm"
    assert seen["headers"]["TTL"] == "86400"
    assert seen["headers"]["Urgency"] == "high"
    assert seen["headers"]["Authorization"].startswith("vapid t=")
    assert seen["redirects"] is False and seen["timeout"] == 10.0
    assert b"title" not in seen["data"]


def test_an_unreachable_push_service_is_a_transport_error(monkeypatch):
    def down(*args, **kwargs):
        raise webpush.requests.ConnectionError("down")

    monkeypatch.setattr(webpush.requests, "post", down)
    ua = webpush.new_private_key()
    with pytest.raises(webpush.TransportError):
        webpush.send(
            "https://fcm.googleapis.com/x", webpush.public_raw(ua), b"1" * 16, b"{}",
            private_key=ua, subject="mailto:a@example.test", ttl=60,
        )
