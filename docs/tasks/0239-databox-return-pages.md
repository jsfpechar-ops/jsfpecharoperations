# 0239: Data box return and error pages

Status: review
Depends on: none | Base commit: c1ebb74 | Branch: claude/project-thread-jf2b3v
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add two public landing pages, `/stay-fees/databox/done` and `/stay-fees/databox/error`, that the ISDS "Odesílací brána" sends the host back to after they leave their data box. Josef has registered these URLs with ISDS; the rest of the data-box flow stays on hold (memory `isds-send-gateway`), so these pages only show one line and a link back.

## 2. Context

Rules that apply:
- The pages must work without a UbyHost session (the host may come back after their session expired). They read nothing from the request: no query string, no form body, no logging of either. They never ask for or store data-box credentials.
- ISDS may return with GET or POST; answer both. POST must not go through the host CSRF dependency, so the router is NOT the `stay_fees` router (which has `Depends(security.protect_host_post)`).
- No new CSS: reuse `auth_base.html` and the `auth-card` classes, so no `?v=` key changes.
- Copy: one line, no slop (AGENTS.md rule 9).

Pattern to copy, `App/app/templates/mail_unsubscribe.html` (public page on `auth_base.html`):

```html
{% extends "auth_base.html" %}
{% block title %}{{ t('unsubscribe.title') }}{% endblock %}
{% block auth_body %}
<section class="auth-card">
  <h1 class="auth-title">{{ t('unsubscribe.title') }}</h1>
```

`App/app/main.py` lines 343-347:

```python
app.include_router(stay_fees.router)
app.include_router(cleaning_routes.router)
app.include_router(legal.router)
# Public, outside the host CSRF dependency: RFC 8058 one-click posts (WP12).
app.include_router(mail_unsubscribe.router)
```

i18n anchors (insert the new keys right after each):
- `App/app/host_i18n.py:5488` EN `"unsubscribe.too_many": "Too many attempts from this connection. Try again in an hour.",`
- `App/app/host_i18n.py:5531` CS `"unsubscribe.too_many": "Z tohoto připojení bylo příliš mnoho pokusů. Zkuste to znovu za hodinu.",`
- `App/app/host_vi_i18n.py:2635` VI `"unsubscribe.too_many": "Quá nhiều lần thử từ kết nối này. Hãy thử lại sau một giờ.",` (4-space indent, EN/CS use 8)

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/databox_return.py | create | public router, 4 handlers |
| App/app/templates/databox_return.html | create | one card |
| App/app/main.py | edit | import and include router before `stay_fees.router` |
| App/app/host_i18n.py | edit | 5 EN + 5 CS keys |
| App/app/host_vi_i18n.py | edit | 5 VI keys |
| App/tests/test_databox_return.py | create | tests |
| docs/context/decisions.md | edit | append one line |

No other file may change.

## 4. Steps

1. Create `App/app/routes/databox_return.py`:

```python
"""Where the ISDS Odesílací brána sends the host back (brief 0239).

Public and outside the host CSRF dependency: ISDS may come back with a POST,
and the host's UbyHost session may have expired while they were in their data
box. The pages read nothing from the request and store nothing; UbyHost never
sees or keeps data-box login details.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..templating import render

router = APIRouter()


def _page(request: Request, ok: bool):
    return render(request, "databox_return.html", {"ok": ok, "open_alerts": []})


@router.get("/stay-fees/databox/done")
@router.post("/stay-fees/databox/done")
def databox_done(request: Request):
    return _page(request, True)


@router.get("/stay-fees/databox/error")
@router.post("/stay-fees/databox/error")
def databox_error(request: Request):
    return _page(request, False)
```

2. Create `App/app/templates/databox_return.html`:

```html
{% extends "auth_base.html" %}
{% set key = 'databox_return.done' if ok else 'databox_return.error' %}
{% block title %}{{ t(key ~ '.title') }}{% endblock %}
{% block auth_body %}
<section class="auth-card">
  <h1 class="auth-title">{{ t(key ~ '.title') }}</h1>
  <p class="auth-lede" role="{{ 'status' if ok else 'alert' }}">{{ t(key ~ '.lede') }}</p>
  <p><a class="auth-submit" href="/stay-fees">{{ t('databox_return.back') }}</a></p>
</section>
{% endblock %}
```

If `{% set %}` outside a block is not visible inside the blocks, move the `set` inside each block (STOP only if that also fails).

3. `App/app/main.py`: add `databox_return` to the `from .routes import ...` line (alphabetical), and insert before `app.include_router(stay_fees.router)`:

```python
# Public, outside the host CSRF dependency: ISDS may return with a POST (0239).
app.include_router(databox_return.router)
```

4. i18n keys after each anchor in §2.

EN:
```python
        "databox_return.done.title": "Back from your data box",
        "databox_return.done.lede": "If you sent the message in your data box, the city office has your stay fee report.",
        "databox_return.error.title": "Your data box did not take the message",
        "databox_return.error.lede": "Nothing was sent. Try again from Stay fee, or send the PDF from your data box yourself.",
        "databox_return.back": "Back to Stay fee",
```
CS:
```python
        "databox_return.done.title": "Zpět z datové schránky",
        "databox_return.done.lede": "Pokud jste zprávu v datové schránce odeslali, úřad má vaše hlášení k poplatku z pobytu.",
        "databox_return.error.title": "Datová schránka zprávu nepřijala",
        "databox_return.error.lede": "Nic se neodeslalo. Zkuste to znovu z Poplatku z pobytu, nebo pošlete PDF ze své datové schránky sami.",
        "databox_return.back": "Zpět na poplatek z pobytu",
```
VI (4-space indent):
```python
    "databox_return.done.title": "Đã quay lại từ hộp dữ liệu",
    "databox_return.done.lede": "Nếu bạn đã gửi tin nhắn trong hộp dữ liệu, cơ quan thành phố đã nhận báo cáo phí lưu trú của bạn.",
    "databox_return.error.title": "Hộp dữ liệu không nhận tin nhắn",
    "databox_return.error.lede": "Chưa có gì được gửi. Hãy thử lại từ Phí lưu trú, hoặc tự gửi tệp PDF từ hộp dữ liệu của bạn.",
    "databox_return.back": "Quay lại Phí lưu trú",
```

5. Create `App/tests/test_databox_return.py`:

```python
"""0239: the ISDS return pages work signed out, by GET and POST, and keep nothing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.mark.parametrize("path,text", [
    ("/stay-fees/databox/done", "Back from your data box"),
    ("/stay-fees/databox/error", "did not take the message"),
])
@pytest.mark.parametrize("method", ["get", "post"])
def test_return_pages_signed_out(client, path, text, method):
    response = getattr(client, method)(path, follow_redirects=False)
    assert response.status_code == 200
    assert text in response.text
    assert 'href="/stay-fees"' in response.text


def test_return_page_ignores_and_hides_input(client):
    response = client.post(
        "/stay-fees/databox/done?dmID=123&secret=x",
        data={"password": "hunter2", "username": "abc"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "hunter2" not in response.text
    assert "123" not in response.text
    assert "<input" not in response.text.split("auth-card", 1)[1]


def test_return_page_czech(client):
    client.cookies.set("lang", "cs")
    response = client.get("/stay-fees/databox/error")
    assert response.status_code == 200
```

For the Czech test, check how the app picks the language (`grep -n "def resolve_language" -A15 App/app/host_i18n.py`); if a cookie or `?lang=` sets it, assert `"Datová schránka zprávu nepřijala" in response.text`. If not quick to find, keep the status assertion only and say so in the report.

6. Append to `docs/context/decisions.md`:

```
- 2026-10-22 ISDS Odesílací brána return URLs: https://ubyhost.com/stay-fees/databox/done and /error, public, read nothing; draft validity 60 min, citizen-identity login allowed (owner, 0239).
```

## 5. Do not touch

`App/app/routes/stay_fees.py`, any CSS/JS, `auth_base.html`, migrations, retention. Hard rules 2 (no new outbound request, no new personal data), 3, 4, 8.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_databox_return.py tests/test_host_i18n.py tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30` → all pass.
- From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10` → clean.

## 7. Acceptance

- [ ] Both URLs answer 200 signed out, by GET and POST.
- [ ] Posted fields and query values never appear in the page.
- [ ] EN, CS, VI keys present; i18n tests pass.
- [ ] decisions line added; lint clean.
- Screenshots: the orchestrator takes them (390/820/1280/2000 in EN/CS/VI) at review; the executor need not.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

Write `docs/tasks/0239-report.md` (600 tokens at most), set `Status: review`. Do not commit; the orchestrator commits.
