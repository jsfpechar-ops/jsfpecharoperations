"""Writes golden sign-up values for go/internal/signup (brief 1281).

Run from App/: .venv/bin/python scripts/signup_golden.py
Everything comes from app.signup and app.mail_notify with a frozen clock
and fixed inputs, so the Go tests can compare byte for byte.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
SECRET = "signup-golden-secret-0123456789-abcdefghij"
NOW = 1798761600
NOW_MS = NOW * 1000
OUT = REPO / "go" / "internal" / "signup" / "testdata" / "signup.json"
ENV = {
    "UBYHOST_SECRET_KEY": SECRET,
    "UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example/",
    "UBYHOST_APP_BASE_URL": "https://app.ubyhost.example",
    "UBYHOST_OPERATOR_EMAIL": "ops@ubyhost.example",
    "UBYHOST_ADS_CONVERSION_NAME": ' Sign-up, "paid" ',
}
os.environ.update(ENV)
sys.path.insert(0, str(APP_DIR))

from starlette.datastructures import QueryParams  # noqa: E402

from app import billing_trial, mail_notify, signup, signup_selection  # noqa: E402

out = {"secret": SECRET, "now": NOW, "env": ENV}
signup._now_ms = lambda: NOW_MS

WS = ['Chata <Pod> & "Les" 100%', "Penzion Ú Lípy", "x"]
out["clean"] = [
    {"param": p, "value": v, "out": signup.clean_click_id(p, v)}
    for p, v in [
        ("gclid", " Cj0KCQ_abc-1 "), ("gclid", "bad value"), ("gclid", "a" * 200),
        ("gclid", "a" * 201), ("fbclid", "F" * 500), ("fbclid", "F" * 501),
        ("wbraid", "\x1cabc\x1f"), ("gbraid", " abc　"), ("utm", "abc"),
        ("gclid", ""), ("gclid", "ábc"),
    ]
]
out["utm"] = [
    {"value": v, "out": signup.clean_utm(v)}
    for v in [" google ", "spring sale 2027", "a+b.c_d-e", "<x>", "a" * 100, "a" * 101, "\x1d fb "]
]
out["user_agent"] = [
    {"value": v, "out": signup.clean_user_agent(v)}
    for v in ["Mozilla/5.0 (X11)", "  tab\there é  ", "", "A" * 600, "  x  "]
]
SEL = [
    [("plan", "max"), ("interval", "year"), ("ttlock", "1"), ("apartments", "07")],
    [("plan", "gold"), ("apts", "3")],
    [("apartments", ""), ("apts", "4")],
    [("apartments", "51")],
    [("apartments", "50"), ("plan", "max"), ("plan", "standard")],
    [("interval", "month"), ("interval", "week")],
]
out["selection"] = [
    {"query": q, "json": json.dumps(signup_selection.clean(QueryParams(q)), sort_keys=True)}
    for q in SEL
]
CLICKS = [
    ({"gclid": "Cj0KCQ_abc-1"}, NOW_MS - 1000),
    ({"gclid": "G1", "gbraid": "B2", "wbraid": "W3", "fbclid": "IwAR0_x"}, NOW_MS),
    ({"fbclid": "IwAR" + "z" * 400}, NOW_MS - 3600 * 1000),
]
out["clicks"] = []
for ids, seen in CLICKS:
    token = signup.issue_click(ids, seen)
    reads = {}
    for name, at in [("now", NOW_MS), ("future_ok", seen - 5 * 60 * 1000),
                     ("future_bad", seen - 5 * 60 * 1000 - 1),
                     ("old_ok", seen + 90 * 86400 * 1000),
                     ("old_bad", seen + 90 * 86400 * 1000 + 1)]:
        got = signup.read_click(token, at)
        reads[name] = {"at": at, "ok": got is not None}
    out["clicks"].append({"ids": ids, "seen_ms": seen, "token": token, "reads": reads})
# Signed but refused: an unknown key, an invalid id, a non-int time.
ser = signup._click_serializer()
out["bad_clicks"] = [
    ser.dumps({"i": {"gclid": "ok", "x": "y"}, "t": NOW_MS}),
    ser.dumps({"i": {"gclid": "bad id"}, "t": NOW_MS}),
    ser.dumps({"i": {}, "t": NOW_MS}),
    ser.dumps({"i": {"gclid": "ok"}}),
    ser.dumps([1, 2]),
]
gtok = out["clicks"][0]["token"]
ATTR = [
    ([("utm_source", " google "), ("utm_medium", "<cpc>"), ("gclid", "Cj0KCQ_abc-1")], True),
    ([("utm_campaign", "spring"), ("gclid", "Cj0KCQ_abc-1"), ("click", gtok)], True),
    ([("gclid", "NEW1"), ("click", gtok)], True),
    ([("gclid", "NEW1"), ("click", gtok)], False),
    ([("click", "forged.token"), ("fbclid", "bad id")], True),
    ([("utm_source", "a"), ("utm_source", "b")], False),
]
out["attribution"] = [
    {"query": q, "mint": m, "out": signup.attribution(QueryParams(q), mint=m)} for q, m in ATTR
]
with mock.patch("time.time", return_value=float(NOW)):
    out["tokens"] = [
        {"uid": uid, "nonce": n, "token": signup.issue_token(uid, n)}
        for uid, n in [(7, "AbC_-123xyzAbC_-123xy"), (123456789, "n")]
    ]
out["consent"] = []
for platform in signup.PLATFORMS:
    for lang in ["en", "cs", "vi", "de", "CS"]:
        text = signup.consent_text(platform, lang)
        out["consent"].append({"platform": platform, "lang": lang, "text": text})
out["source"] = [
    {"stored": s, "attr": a, "out": signup.signup_source(s, a)}
    for s, a in [([], {}), (["meta"], {"utm_source": "google"}), (["google", "meta"], {}),
                 ([], {"utm_source": " Instagram "}), ([], {"utm_source": "GoogleAds"}),
                 ([], {"utm_source": "bing"})]
]
out["conversion_time"] = [
    {"stored": s, "out": signup.conversion_time(s)}
    for s in ["2027-01-01T00:00:00+00:00", "2026-07-01T12:30:00+00:00",
              "2026-03-29T00:59:59+00:00", "2026-03-29T01:00:00+00:00", "2026-10-25T00:30:00",
              "2026-10-25T01:30:00Z"]
]
CSV_ROWS = [{"id": 1, "gclid": "G1", "email_verified_at": "2027-01-01T00:00:00+00:00"},
            {"id": 2, "gclid": "G2", "email_verified_at": "2026-07-01T12:30:00+00:00"}]
out["csv"] = {"rows": CSV_ROWS, "body": signup.conversions_csv(CSV_ROWS)}
out["iso_from_ms"] = [{"ms": ms, "out": signup._iso_from_ms(ms)} for ms in [NOW_MS, NOW_MS + 999, 1]]
out["trial"] = [
    {"stamp": s, "first": f.isoformat(), "last": l.isoformat()}
    for s in ["2027-01-01T00:00:00+00:00", "2026-10-25T22:30:00+00:00", "2026-03-01T23:30:00+00:00"]
    for f, l in [billing_trial.activation_dates(s)]
]
LINK = mail_notify._public("/signup/verify?t={{claim_secret}}")
out["verify_link"] = LINK
mails = []
for lang in ["en", "cs", "vi", "de", "CS-cz"]:
    for ws in WS:
        c = mail_notify.build_signup_verify(lang=lang, workspace=ws, username="host-ab12", link=LINK)
        mails.append({"kind": "verify", "lang": lang, "workspace": ws, **c})
    c = mail_notify.build_signup_exists(lang=lang)
    mails.append({"kind": "exists", "lang": lang, **c})
for ws, campaign, ads, meta in [(WS[0], "google / cpc / spring", True, False), ("", "", False, True)]:
    c = mail_notify.build_signup_admin(workspace=ws, email="a@b.cz", username="host-ab12",
                                       campaign=campaign, ads_click=ads, meta_click=meta)
    mails.append({"kind": "admin", "workspace": ws, "campaign": campaign, "ads": ads, "meta": meta, **c})
out["mails"] = mails
first = mails[1]
out["payload"] = {
    "lang": "CS-cz",
    "json": json.dumps({"text": first["text"], "html": first["html"], "lang": "CS-cz"}),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {OUT.relative_to(REPO)}")
