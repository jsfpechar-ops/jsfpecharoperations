#!/usr/bin/env python3
"""Write the Python oracle for the Go mail delivery (brief 1231).

Dev tool, never run in production. Invented data only: a fixed test Fernet key,
no .env, no database, no network (boto3 clients and the database are replaced
by recorders). Output: go/internal/mail/testdata/drain/cases.json, byte-stable.
Usage: mail_drain_golden.py [--out FILE]
"""

from __future__ import annotations

import argparse
import base64
import email
import email.policy
import hashlib
import io
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "mail" / "testdata" / "drain" / "cases.json"

FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="  # invented test key
FIXED_TS = 1700000000
FIXED_IV = bytes(range(16))

os.environ["UBYHOST_DATA_KEYS"] = FERNET_KEY
os.environ["UBYHOST_DATA_KEY_LEGACY"] = "0"
os.environ["UBYHOST_MAIL_BACKEND"] = "ses"
os.environ["UBYHOST_DEPLOYMENT"] = "production"
os.environ["UBYHOST_MAIL_FROM"] = "noreply@mail.example.test"
os.environ["UBYHOST_SES_REGION"] = "eu-central-1"
os.environ["UBYHOST_AWS_ACCESS_KEY_ID"] = "AKIDEXAMPLE"
os.environ["UBYHOST_AWS_SECRET_ACCESS_KEY"] = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
os.environ.setdefault("UBYHOST_SECRET_KEY", "test-secret-key-not-for-real-use")
os.environ.setdefault("UBYHOST_DATA_DIR", "/tmp/ubyhost-mail-drain-golden")
os.environ.setdefault("UBYHOST_DB", "/tmp/ubyhost-mail-drain-golden/unused.db")
sys.path.insert(0, str(APP_DIR))

from cryptography.fernet import Fernet  # noqa: E402

from app import billing_invoices, db, mail  # noqa: E402

FERNET = Fernet(FERNET_KEY.encode("ascii"))
FILING_PDF = b"%PDF-1.4 invented stay fee filing\n%%EOF\n"
INVOICE_PDF = b"%PDF-1.4 invented platform invoice\n%%EOF\n"
SPAYD = "SPD*1.0*ACC:CZ6508000000192000145399*AM:150.00*CC:CZK*X-VS:1234567890*MSG:POPLATEK"


def enc(text: bytes) -> str:
    return FERNET._encrypt_from_parts(text, FIXED_TS, FIXED_IV).decode("ascii")


FILINGS = {7: {"id": 7, "period_key": "2026-10", "pdf_enc": enc(FILING_PDF).encode("ascii")}}
INVOICES = {
    9: {"pdf_blob": INVOICE_PDF, "pdf_sha256": hashlib.sha256(INVOICE_PDF).hexdigest()},
    10: {"pdf_blob": INVOICE_PDF, "pdf_sha256": "0" * 64},
}


def _query_one(sql, params=()):
    if "FROM stay_fee_filing" in sql:
        return FILINGS.get(int(params[0]))
    if "FROM platform_invoice" in sql:
        return INVOICES.get(int(params[0]))
    raise AssertionError(f"unexpected query: {sql}")


db.query_one = _query_one


class FakeClient:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "0100invented-message-id"}


V1, V2 = FakeClient("ses"), FakeClient("sesv2")
mail._ses_client = lambda: V1
mail._sesv2_client = lambda: V2

LIFE = "lifecycle_no_property"
CASES = [
    {"name": "plain_claim_secret", "kind": "claim", "to": "guest@example.test",
     "subject": "Your check-in link",
     "payload": {"text": "Open: https://app.example.test/c/{{claim_secret}}\n", "html": "<p>https://app.example.test/c/{{claim_secret}}</p>",
                 "claim_secret_enc": enc(b"s3cr3t-token_AB")}},
    {"name": "plain_text_only_czech_subject", "kind": "completion", "to": "Guest@Example.test",
     "subject": "Potvrzení pobytu č. 1", "payload": {"text": "Dobrý den,\nděkujeme.\n"}},
    {"name": "door_code", "kind": "door_code", "to": "guest@example.test", "subject": "Door code",
     "payload": {"text": "PIN {{door_code}}", "html": "<b>{{door_code}}</b>", "door_code_enc": enc(b"123456")}},
    {"name": "door_code_with_confirm", "kind": "door_code", "to": "guest@example.test", "subject": "Door code",
     "payload": {"text": "PIN {{door_code}}", "door_code_enc": enc(b"4321#")}},
    {"name": "cc_and_reply_to", "kind": "completion", "to": "guest@example.test", "cc": "Host <HOST@Example.test>",
     "subject": "Receipt", "payload": {"text": "ok", "html": "<p>ok</p>", "reply_to": "Reply Me <Reply@Example.test>"}},
    {"name": "bad_cc_and_reply_to_dropped", "kind": "completion", "to": "guest@example.test", "cc": "not-an-address",
     "subject": "Receipt", "payload": {"text": "ok", "reply_to": "nonsense"}},
    {"name": "lifecycle_unsubscribe", "kind": LIFE, "to": "host@example.test", "subject": "Tip 1",
     "payload": {"text": "tip", "html": "<p>tip</p>", "list_unsubscribe": "https://app.example.test/u/abc123", "reply_to": "support@example.test"}},
    {"name": "lifecycle_http_dropped", "kind": LIFE, "to": "host@example.test", "subject": "Tip 2",
     "payload": {"text": "tip", "list_unsubscribe": "http://app.example.test/u/abc"}},
    {"name": "lifecycle_non_ascii_dropped", "kind": LIFE, "to": "host@example.test", "subject": "Tip 3",
     "payload": {"text": "tip", "list_unsubscribe": "https://app.example.test/u/é"}},
    {"name": "service_kind_ignores_unsubscribe", "kind": "completion", "to": "host@example.test", "subject": "S",
     "payload": {"text": "tip", "list_unsubscribe": "https://app.example.test/u/abc"}},
    {"name": "attach_filing_default_name", "kind": "stay_fee_filing", "to": "host@example.test", "subject": "Poplatek",
     "payload": {"text": "See attachment", "stay_fee_filing_id": 7}},
    {"name": "attach_filing_custom_name_html", "kind": "stay_fee_filing", "to": "host@example.test", "cc": "cc@example.test",
     "subject": "Poplatek 2", "payload": {"text": "See attachment", "html": "<p>See attachment</p>",
                                            "stay_fee_filing_id": 7, "attachment_name": "my-filing.pdf",
                                            "reply_to": "r@example.test"}},
    {"name": "attach_invoice_and_qr_html", "kind": "billing_invoice", "to": "host@example.test", "subject": "Faktura",
     "payload": {"text": "Invoice", "html": "<p>Invoice</p><img src=\"cid:stayfeeqr\">", "platform_invoice_id": 9,
                 "qr_spayd": SPAYD}},
    {"name": "attach_qr_text_only", "kind": "payment_request", "to": "guest@example.test", "subject": "Pay",
     "payload": {"text": "Scan", "qr_spayd": SPAYD}},
    {"name": "lifecycle_unsubscribe_with_attachment", "kind": LIFE, "to": "host@example.test", "subject": "Tip 4",
     "payload": {"text": "tip", "html": "<p>tip</p>", "list_unsubscribe": "https://app.example.test/u/abc123",
                 "stay_fee_filing_id": 7}},
    {"name": "attach_invoice_sha_mismatch", "kind": "billing_invoice", "to": "host@example.test", "subject": "Faktura",
     "payload": {"text": "Invoice", "platform_invoice_id": 10}},
    {"name": "attach_filing_missing", "kind": "stay_fee_filing", "to": "host@example.test", "subject": "Poplatek",
     "payload": {"text": "x", "stay_fee_filing_id": 99}},
    {"name": "claim_marker_without_secret", "kind": "claim", "to": "guest@example.test", "subject": "Link",
     "payload": {"text": "{{claim_secret}}"}},
    {"name": "door_marker_without_secret", "kind": "door_code", "to": "guest@example.test", "subject": "Code",
     "payload": {"text": "{{door_code}}"}},
    {"name": "claim_marker_bad_token", "kind": "claim", "to": "guest@example.test", "subject": "Link",
     "payload": {"text": "{{claim_secret}}", "claim_secret_enc": "not-a-token"}},
]

STAGING_LINKS = [
    {"kind": "login_link", "to": "guest@example.test", "text": "Sign in: https://app.example.test/login?t=AbC-123_x.y now",
     "want": "https://app.example.test/login?t=AbC-123_x.y"},
    {"kind": "login_link", "to": "guest@example.test", "text": "no link here", "want": ""},
    {"kind": "claim", "to": "guest@example.test", "text": "https://app.example.test/x?t=abc", "want": ""},
]

NORMALISE = ["a@b.cz", " A@B.CZ ", "Name <Addr@Host.example>", "Name<a@b.cz>", "nope", "", "a@b", "a b@c.de",
             "<a@b.cz>", "a@b.cz, c@d.cz", "x" * 250 + "@b.cz", "a@b.cz.", "Jan Novák <jan@example.cz>"]
MASK = ["jan@example.cz", "a@b.cz", "ab@cd.example.org", "verylonglocalpart@longdomainname.co.uk", "nope", "@x.cz", "x@"]
DISPLAY_FROM = ["noreply@mail.example.test", " noreply@mail.example.test ", "Custom Name <n@x.test>", "", "no-at-sign", "a@b <c>"]


def _png_size(data: bytes) -> str:
    """The QR PNG is compared by size only: Python's qrcode and Go's go-qrcode
    draw the same payload with a different mask, so the bytes differ."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as im:
        return f"{im.size[0]}x{im.size[1]}"


def _raw_tree(raw: bytes) -> dict:
    """Decoded structure of a MIME message: headers, content types, part hashes."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    headers = {}
    for name in ("From", "To", "Cc", "Subject", "Reply-To", "List-Unsubscribe", "List-Unsubscribe-Post"):
        if msg[name] is not None:
            headers[name] = str(msg[name])

    def walk(part):
        node = {"type": part.get_content_type()}
        if part.get_filename():
            node["filename"] = part.get_filename()
        if part["Content-ID"]:
            node["cid"] = str(part["Content-ID"])
        if part["Content-Disposition"]:
            node["disposition"] = part.get_content_disposition()
        if part.is_multipart():
            node["parts"] = [walk(p) for p in part.iter_parts()]
        else:
            data = part.get_payload(decode=True) or b""
            if part.get_content_maintype() == "image":
                node["png_size"] = _png_size(data)
                return node
            if part.get_content_maintype() == "text":
                data = data.replace(b"\r\n", b"\n")
            node["sha256"] = hashlib.sha256(data).hexdigest()
        return node

    return {"headers": headers, "tree": walk(msg)}


def _case(c: dict) -> dict:
    row = {"id": 1, "kind": c["kind"], "to_email": c["to"], "cc_email": c.get("cc"), "subject": c["subject"],
           "payload": json.dumps(c["payload"], ensure_ascii=False)}
    out = {"name": c["name"], "kind": c["kind"], "to": c["to"], "cc": c.get("cc"), "subject": c["subject"],
           "payload": c["payload"]}
    try:
        payload = c["payload"]
        out["body"] = mail.delivery_body(payload)
        out["html"] = mail.delivery_html(payload)
        out["headers"] = mail.list_unsubscribe_headers(row, payload)
        out["reply_to"] = mail.normalise_email(str(payload.get("reply_to") or ""))
        out["cc_normalised"] = mail.normalise_email(row["cc_email"] or "")
        parts = mail.attachments(payload)
        out["attachments"] = [
            {"filename": p["filename"], "maintype": p["maintype"], "subtype": p["subtype"], "cid": p["cid"],
             **({"png_size": _png_size(p["data"])} if p["maintype"] == "image"
                else {"sha256": hashlib.sha256(p["data"]).hexdigest()})} for p in parts]
        V1.calls.clear()
        V2.calls.clear()
        mail._send_ses(row)
        if V2.calls:
            call = V2.calls[0]
            if "Raw" in call["Content"]:
                out["raw"] = _raw_tree(call["Content"]["Raw"]["Data"])
                out["sent_as"] = "raw"
            else:
                out["sent_as"] = "simple"
                out["v2_simple"] = call
        else:
            out["sent_as"] = "simple"
        out["error"] = ""
    except Exception as exc:  # noqa: BLE001 - the oracle records which cases fail
        out["error"] = type(exc).__name__
        for key in ("body", "html", "headers", "attachments"):
            out.pop(key, None)
    return out


def _sigv4() -> dict:
    import datetime

    import botocore.auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials

    class Fixed(datetime.datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 11, 13, 10, 0, 0)

        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 13, 10, 0, 0, tzinfo=tz)

    body = json.dumps({"FromEmailAddress": "a@b.test", "Content": {"Raw": {"Data": "eA=="}}},
                      separators=(",", ":"))
    url = "https://email.eu-central-1.amazonaws.com/v2/email/outbound-emails"
    req = AWSRequest(method="POST", url=url, data=body, headers={"Content-Type": "application/json"})
    creds = Credentials("AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY")
    real = botocore.auth.datetime.datetime
    botocore.auth.datetime.datetime = Fixed
    try:
        botocore.auth.SigV4Auth(creds, "ses", "eu-central-1").add_auth(req)
    finally:
        botocore.auth.datetime.datetime = real
    return {"url": url, "body": body, "date": req.headers["X-Amz-Date"],
            "authorization": req.headers["Authorization"], "region": "eu-central-1",
            "access_key": "AKIDEXAMPLE", "secret_key": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"}


def render() -> str:
    staging = []
    mail.config.DEPLOYMENT = "staging"
    for s in STAGING_LINKS:
        import logging

        records = []

        class H(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        h = H()
        mail.log.addHandler(h)
        mail.log.setLevel(logging.WARNING)
        mail._log_staging_link({"kind": s["kind"], "to_email": s["to"]}, {"text": s["text"]})
        mail.log.removeHandler(h)
        staging.append({**s, "logged": bool(records)})
    mail.config.DEPLOYMENT = "production"
    data = {
        "fernet_key": FERNET_KEY,
        "filing_pdf_b64": base64.b64encode(FILING_PDF).decode(),
        "filing_pdf_enc": FILINGS[7]["pdf_enc"].decode("ascii"),
        "filing_period": "2026-10",
        "invoice_pdf_b64": base64.b64encode(INVOICE_PDF).decode(),
        "spayd": SPAYD,
        "cases": [_case(c) for c in CASES],
        "staging_links": staging,
        "normalise": [{"in": v, "out": mail.normalise_email(v)} for v in NORMALISE],
        "mask": [{"in": v, "out": mail.mask_email(v)} for v in MASK],
        "display_from": [{"in": v, "out": mail.display_from(v)} for v in DISPLAY_FROM],
        "backoff": [{"attempts": n, "delay": min(6 * 60 * 60, 60 * (2 ** min(n, 8))), "terminal": n >= 8}
                    for n in range(1, 12)],
        "sigv4": _sigv4(),
    }
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
