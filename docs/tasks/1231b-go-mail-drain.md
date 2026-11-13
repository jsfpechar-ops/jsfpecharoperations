# 1231b: Go mail delivery, part 2: Drain, SendNow, Purge and the Python golden

Status: todo
Depends on: 1231 (this branch) | Base commit: 902bc51 | Branch: task/1230-track-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (code is copied by a script; do not read the code blocks)

## 1. Objective

Add `Drain`, `SendNow`, `Purge` and the console backend (port of mail.drain, _deliver, send_now, purge_old, _send_console) in a new `go/internal/mail/outbox_drain.go`, and the golden script that records Python's delivered mail for the Go tests in 1231c.

## 2. Context

Part 2 of 3 (1231, 1231b, 1231c; one branch, one PR). Python source, behaviour decisions and the reason for each difference: [1231 §2](1231-go-mail-delivery.md); do not repeat them, do not open the Python.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/mail_drain_golden.py` | create | Python oracle; writes `go/internal/mail/testdata/drain/cases.json` |
| `go/internal/mail/outbox_drain.go` | create | Drain, SendNow, deliver, console backend, staging link, Purge, mail_failed alert |
| `go/internal/mail/testdata/drain/cases.json` | create (generated in step 2) | Python fixtures |
| `docs/tasks/1231b-go-mail-drain.md` | edit | `Status:` line only |
| `docs/tasks/1231b-report.md` | create | report |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `task/1230-track-a`; `grep -c '^func (c Config) obSendSES' go/internal/mail/outbox_ses.go` prints 1 (1231 is applied); `ls App/scripts/mail_drain_golden.py go/internal/mail/outbox_drain.go 2>&1 | grep -c 'No such file'` prints 2; `git status --short | tail -5` is empty. Any check failing: STOP (§8). Then write the helper that copies code block k of this brief byte for byte:

```bash
cat > /tmp/extract_block.py <<'EOF'
import re, sys
src, k, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = open(src, encoding='utf-8').read()
blocks = re.findall(r'^```(?:python|go)\n(.*?)^```$', text, re.S | re.M)
open(dest, 'w', encoding='utf-8').write(blocks[k - 1])
EOF
```

1. Create the 2 files in one call (from the repo root):

```bash
B=docs/tasks/1231b-go-mail-drain.md; X="python3 /tmp/extract_block.py $B"
mkdir -p go/internal/mail App/scripts
$X 1 App/scripts/mail_drain_golden.py
$X 2 go/internal/mail/outbox_drain.go
sha256sum App/scripts/mail_drain_golden.py go/internal/mail/outbox_drain.go | tail -10
```

   Expected:

   - `c6ffccf8c61ccf362031f56c3c082d6a42bff08a7eefc731cd6184d9b3019775`  `App/scripts/mail_drain_golden.py`
   - `d42b39c5b9eacdf722e63149a2fd392d4d61f28aa00882ccddd222fa4ccc87be`  `go/internal/mail/outbox_drain.go`

   A different hash: re-run that one extract once; still different: STOP (§8).

2. From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30` prints nothing. Then from `App/`: `.venv/bin/python scripts/mail_drain_golden.py 2>&1 | tail -3` ends `wrote .../go/internal/mail/testdata/drain/cases.json`; run it a second time; from the repo root `sha256sum go/internal/mail/testdata/drain/cases.json` prints `84faacbe05b15a3bf285b75e752cd59650ee55ea4ed9af5e833d6654396999b0`. Commit "1231b step 1-2" (the three files).

3. Write the report (§9), set `Status: review`, commit "1231b step 3".

## 5. Do not touch

`App/app/` (all of it), `App/migrations_pg/`, every existing file in `go/internal/` (incl. the `go/internal/mail/*.go` files that exist on the base commit, `go/internal/ubyport/`, `go/internal/payments/`, `go/internal/secure/`, `go/internal/jobs/`), `go/cmd/`, `go/go.mod`, `go/go.sum`, `docs/context/`, `.github/`. No job kind, env var, route, migration or dependency. Hard rules 2 (no addresses or bodies in logs or errors), 3, 4, 5.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -30`. Golden freshness: from `App/`, `.venv/bin/python scripts/mail_drain_golden.py >/dev/null 2>&1; git status --short ../go | tail -30` prints nothing after the step 2 commit. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The two file hashes and the `cases.json` hash match.
- [ ] gofmt empty, `go vet ./...` clean; golden freshness clean.
- [ ] Context lint passes.
- [ ] `git diff --stat 902bc51..HEAD | tail -20` lists only paths of the 1230/1231 briefs' §3.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- a step 0 check fails, or a hash still differs after one re-extract (never edit code by hand);
- `cases.json` differs while the script hash matches (Python behaviour moved: never edit JSON, Python or Go to match);
- a parity test fails (`TestGoldenDelivery`, `TestGoldenAddressHelpers`, `TestSigV4MatchesBotocore`), or any test fails twice;
- you reach 25 tool calls or about 50k tokens (see executor.md);
- a file outside §3 needs a change, or a new dependency seems needed;
- you need push, merge, a PR, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1231b-report.md` (600 tokens at most) and set `Status: review`. It has: 1. `git diff --stat HEAD~2..HEAD | tail -10`; 2. each command with its last 5 lines; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `outbox_drain.go` against mail.py 737-845 and alerts.py 440-520: stale reset (`updated_at < now-10 min`, text compare), claim `WHERE id AND state='queued'`, `ORDER BY id LIMIT`, the success UPDATE (attempts+1, last_error NULL), the failure UPDATE and the terminal alert (owner lookup apartment then reservation, update an open alert with the same dedupe key, else insert); `SendNow` returns nil on a failed delivery; the `ErrNoDetailsRenderer` put-back; Purge states and cutoff.
- `mail_drain_golden.py`: invented data, fixed Fernet key and IV, no DB (query_one patched), no network (boto3 clients replaced). Behaviour decisions: [1231 §2](1231-go-mail-delivery.md).

## Owner steps

None (nothing is wired). Brief 1236 carries the switch; it must not be switched on before the guest/receipt detail renderer brief is merged, or guest-list and receipt mails stay queued.

## Code blocks

### Block 1: `App/scripts/mail_drain_golden.py`

```python
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
```

### Block 2: `go/internal/mail/outbox_drain.go`

```go
package mail

// mail.drain, _deliver, _send_console, _log_staging_link and purge_old.

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// Summary counts what one Drain did.
type Summary struct{ Sent, Failed, Skipped int }

const (
	obMaxAttempts = 8
	obStaleAfter  = 10 * time.Minute
)

// ObBackoff is the delay after a failed attempt: min(6 h, 60 s * 2^min(n, 8)).
func ObBackoff(attempts int) time.Duration {
	n := attempts
	if n > 8 {
		n = 8
	}
	d := 60 * (1 << n)
	if d > 6*60*60 {
		d = 6 * 60 * 60
	}
	return time.Duration(d) * time.Second
}

// Drain sends up to limit queued rows: stale "sending" rows go back to queued,
// each due row is claimed with a compare-and-set and delivered.
func Drain(ctx context.Context, pool *pgxpool.Pool, cfg Config, limit int) (Summary, error) {
	var sum Summary
	if !cfg.Enabled() {
		return sum, nil
	}
	now := cfg.now()
	stale := obStamp(now.Add(-obStaleAfter))
	if _, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = 'queued' WHERE state = 'sending' AND updated_at < $1`, stale); err != nil {
		return sum, errors.New("mail drain: stale rows not reset")
	}
	rows, err := pool.Query(ctx,
		`SELECT `+obRowColumns+` FROM email_outbox WHERE state = 'queued' AND next_attempt_at <= $1 ORDER BY id LIMIT $2`,
		obStamp(now), limit)
	if err != nil {
		return sum, errors.New("mail drain: queue not read")
	}
	var due []obRow
	for rows.Next() {
		var r obRow
		if err := rows.Scan(r.dest()...); err != nil {
			rows.Close()
			return sum, errors.New("mail drain: queue row not read")
		}
		due = append(due, r)
	}
	rows.Close()
	if rows.Err() != nil {
		return sum, errors.New("mail drain: queue not read")
	}
	for _, r := range due {
		claimed, err := cfg.claim(ctx, pool, r.ID)
		if err != nil {
			return sum, err
		}
		if !claimed {
			continue // another drain took it
		}
		outcome, err := cfg.deliver(ctx, pool, r)
		if err != nil {
			return sum, err
		}
		switch outcome {
		case "sent":
			sum.Sent++
		case "failed":
			sum.Failed++
		default:
			sum.Skipped++
		}
	}
	return sum, nil
}

// claim is db.update_if(email_outbox, id, {state: sending}, {state: queued}).
func (c Config) claim(ctx context.Context, pool *pgxpool.Pool, id int64) (bool, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = 'sending', updated_at = $1 WHERE id = $2 AND state = 'queued'`,
		obStamp(c.now()), id)
	if err != nil {
		return false, errors.New("mail: outbox row not claimed")
	}
	return tag.RowsAffected() == 1, nil
}

// SendNow is mail.send_now: send one queued row straight away (a login link
// the reader waits for). An id <= 0, mail switched off, a missing row or a row
// that is not queued is not an error. A failed delivery is not an error either:
// the row stays queued with the usual back-off and Drain retries it. The error
// is only for an invalid mail environment or database trouble.
func SendNow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, outboxID int64) error {
	if outboxID <= 0 {
		return nil
	}
	cfg, err := ConfigFromEnv(getenv)
	if err != nil {
		return err
	}
	return cfg.sendNow(ctx, pool, outboxID)
}

func (c Config) sendNow(ctx context.Context, pool *pgxpool.Pool, outboxID int64) error {
	if outboxID <= 0 || !c.Enabled() {
		return nil
	}
	var r obRow
	var state string
	err := pool.QueryRow(ctx, `SELECT `+obRowColumns+`, COALESCE(state, '') FROM email_outbox WHERE id = $1`, outboxID).
		Scan(append(r.dest(), &state)...)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return errors.New("mail send_now: row not read")
	}
	if state != "queued" {
		return nil
	}
	claimed, err := c.claim(ctx, pool, r.ID)
	if err != nil || !claimed {
		return err
	}
	_, err = c.deliver(ctx, pool, r)
	return err
}

// deliver sends one row already marked sending. It returns sent, failed or
// skipped; the error is only for database trouble or a cancelled context.
func (c Config) deliver(ctx context.Context, pool *pgxpool.Pool, r obRow) (string, error) {
	providerID, sendErr := c.send(ctx, pool, r)
	if sendErr == nil {
		stamp := obStamp(c.now())
		_, err := pool.Exec(ctx,
			`UPDATE email_outbox SET state = 'sent', provider_id = $1, sent_at = $2, updated_at = $2,
			        last_error = NULL, attempts = $3 WHERE id = $4`,
			providerID, stamp, r.Attempts+1, r.ID)
		if err != nil {
			return "", errors.New("mail drain: sent row not saved")
		}
		return "sent", nil
	}
	if ctx.Err() != nil {
		return "", ctx.Err() // the row stays sending and goes back to queued after 10 minutes
	}
	if errors.Is(sendErr, ErrNoDetailsRenderer) {
		// A setup problem, not a failed send: put the row back as it was.
		if _, err := pool.Exec(ctx,
			`UPDATE email_outbox SET state = 'queued', updated_at = $1 WHERE id = $2 AND state = 'sending'`,
			obStamp(c.now()), r.ID); err != nil {
			return "", errors.New("mail drain: row not put back")
		}
		return "", sendErr
	}
	attempts := r.Attempts + 1
	terminal := attempts >= obMaxAttempts
	state := "queued"
	if terminal {
		state = "failed"
	}
	now := c.now()
	next := now.Add(ObBackoff(int(attempts))).Format("2006-01-02T15:04:05") + "Z"
	safe := obSafeError(sendErr)
	if _, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = $1, attempts = $2, last_error = $3, next_attempt_at = $4, updated_at = $5
		 WHERE id = $6`, state, attempts, safe, next, obStamp(now), r.ID); err != nil {
		return "", errors.New("mail drain: failed row not saved")
	}
	if !terminal {
		return "skipped", nil
	}
	masked := MaskEmail(r.To)
	err := obRaiseAlert(ctx, pool, now, "warning", "mail_failed",
		fmt.Sprintf("E-mail could not be sent (%s).", r.Kind),
		fmt.Sprintf("To %s: %s", masked, safe),
		fmt.Sprintf("mail_failed:%d", r.ID), r.ApartmentID, r.ReservationID,
		[][2]string{{"error", safe}, {"kind", r.Kind}, {"to", masked}})
	if err != nil {
		return "", errors.New("mail drain: mail_failed alert not saved")
	}
	return "failed", nil
}

// send builds and delivers one row and returns the provider id.
func (c Config) send(ctx context.Context, pool *pgxpool.Pool, r obRow) (string, error) {
	p, err := obParsePayload(r.Payload)
	if err != nil {
		return "", err
	}
	if c.Backend == BackendConsole {
		return c.sendConsole(ctx, pool, r, p)
	}
	body, err := c.deliveryBody(ctx, pool, p)
	if err != nil {
		return "", err
	}
	html, err := c.deliveryHTML(ctx, pool, p)
	if err != nil {
		return "", err
	}
	parts, err := c.obAttachments(ctx, pool, p)
	if err != nil {
		return "", err
	}
	id, err := c.obSendSES(ctx, r, p, body, html, parts)
	if err != nil {
		return "", err
	}
	slog.Info("ses mail", "id", r.ID, "kind", r.Kind, "to", MaskEmail(r.To), "message_id", id)
	return id, nil
}

// sendConsole is _send_console: the delivered form is built first (so a missing
// secret fails the row), the log keeps the stored form with an attachment note.
func (c Config) sendConsole(ctx context.Context, pool *pgxpool.Pool, r obRow, p obPayload) (string, error) {
	body, err := c.deliveryBody(ctx, pool, p)
	if err != nil {
		return "", err
	}
	if _, err := c.deliveryHTML(ctx, pool, p); err != nil {
		return "", err
	}
	parts, err := c.obAttachments(ctx, pool, p)
	if err != nil {
		return "", err
	}
	note := ""
	if len(parts) > 0 {
		names := make([]string, len(parts))
		for i, a := range parts {
			names[i] = a.Filename
		}
		note = "\n\n[Attachments: " + strings.Join(names, ", ") + "]"
	}
	var html any
	if h := p.str("html"); h != "" {
		html = h
	}
	var cc any
	if r.CCRaw != nil {
		cc = *r.CCRaw
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO console_mail_log (outbox_id, to_email, cc_email, subject, body_text, body_html, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		r.ID, r.To, cc, r.Subject, p.str("text")+note, html, obStamp(c.now())); err != nil {
		return "", errors.New("console mail log not written")
	}
	slog.Info("console mail", "id", r.ID, "kind", r.Kind, "to", MaskEmail(r.To), "attachments", len(parts))
	if link := obStagingLink(c.Deployment, r.Kind, body); link != "" {
		slog.Warn("staging login link", "kind", r.Kind, "to", MaskEmail(r.To), "link", link)
	}
	return "console:" + strconv.FormatInt(r.ID, 10), nil
}

var obLinkKinds = map[string]bool{"login_link": true, "account_invite": true, "email_confirm": true, "signup_verify": true}

var obLinkInBody = regexp.MustCompile(`https?://\S+[?&]t=[A-Za-z0-9_.\-]+`)

// obStagingLink is the match _log_staging_link would log; empty when it logs
// nothing. Only staging, only the kinds whose link logs someone in.
func obStagingLink(deployment, kind, body string) string {
	if deployment != "staging" || !obLinkKinds[kind] {
		return ""
	}
	return obLinkInBody.FindString(body)
}

// Purge is mail.purge_old: finished outbox rows and console log entries older
// than days. The cutoff is the Prague wall clock as Python's isoformat writes it.
// It returns the number of outbox rows deleted.
func Purge(ctx context.Context, pool *pgxpool.Pool, now time.Time, days int) (int, error) {
	cutoff := obIsoNaive(deadlines.LocalNow(now).Add(-time.Duration(days) * 24 * time.Hour))
	tag, err := pool.Exec(ctx,
		`DELETE FROM email_outbox WHERE state IN ('sent', 'failed', 'bounced', 'complained') AND updated_at < $1`, cutoff)
	if err != nil {
		return 0, errors.New("mail purge: outbox not purged")
	}
	if _, err := pool.Exec(ctx, `DELETE FROM console_mail_log WHERE created_at < $1`, cutoff); err != nil {
		return int(tag.RowsAffected()), errors.New("mail purge: console log not purged")
	}
	return int(tag.RowsAffected()), nil
}

// obRaiseAlert is alerts.raise_alert for the mail_failed case (ubyport.RaiseAlert
// does the same, but this package cannot import ubyport). params are written as
// json.dumps(sort_keys=True, ensure_ascii=False) does, so they must be sorted.
func obRaiseAlert(ctx context.Context, pool *pgxpool.Pool, now time.Time, level, kind, message, detail, dedupeKey string,
	apartmentID, reservationID *int64, params [][2]string) error {
	var b strings.Builder
	b.WriteByte('{')
	for i, kv := range params {
		if i > 0 {
			b.WriteString(", ")
		}
		obJSONString(&b, kv[0])
		b.WriteString(": ")
		obJSONString(&b, kv[1])
	}
	b.WriteByte('}')
	stored := b.String()

	var owner *int64
	if apartmentID != nil && *apartmentID != 0 {
		err := pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, *apartmentID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	if owner == nil && reservationID != nil && *reservationID != 0 {
		err := pool.QueryRow(ctx,
			`SELECT a.owner_user_id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1`,
			*reservationID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	stamp := obStamp(now)
	tag, err := pool.Exec(ctx,
		`UPDATE alert SET level = $1, message = $2, detail = $3, params = $4, created_at = $5
		 WHERE dedupe_key = $6 AND resolved_at IS NULL`, level, message, detail, stored, stamp, dedupeKey)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}
	_, err = pool.Exec(ctx,
		`INSERT INTO alert (level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, message, detail, params, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		level, kind, apartmentID, reservationID, owner, dedupeKey, message, detail, stored, stamp)
	return err
}

// obJSONString writes s as json.dumps(ensure_ascii=False) does.
func obJSONString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}
```

