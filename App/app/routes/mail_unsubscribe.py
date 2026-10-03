"""The unsubscribe link in a lifecycle tip (WP12, legal position 2).

Public and without the host CSRF dependency on purpose. The signed token in
the path is the only credential, and a mailbox provider acting on the
``List-Unsubscribe-Post: List-Unsubscribe=One-Click`` header (RFC 8058) posts
to the same URL from its own servers, with no cookie and no form token.

GET only shows the page with one button: link scanners follow every link in a
message and must not unsubscribe the host. POST unsubscribes.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import db, lifecycle_mail, rate_limit
from ..templating import render

router = APIRouter()

_SCOPE = "mail_unsubscribe"
_LIMIT = 30
_WINDOW_SECONDS = 3600


def _page(request: Request, token: str, *, done: bool = False, status_code: int = 200):
    # The message is a catalogue key, like every other auth-route error.
    message = {404: "unsubscribe.invalid", 429: "unsubscribe.too_many"}.get(status_code, "")
    return render(
        request,
        "mail_unsubscribe.html",
        {"token": token, "done": done, "message": message, "open_alerts": []},
        status_code=status_code,
    )


def _blocked(request: Request) -> bool:
    return rate_limit.blocked(_SCOPE, rate_limit.client_key(request, _SCOPE), _LIMIT, _WINDOW_SECONDS)


def _count(request: Request) -> None:
    rate_limit.record(_SCOPE, rate_limit.client_key(request, _SCOPE))


@router.get("/mail/unsubscribe/{token}")
def mail_unsubscribe_form(token: str, request: Request):
    if _blocked(request):
        return _page(request, token, status_code=429)
    _count(request)
    data = lifecycle_mail.read_unsubscribe_token(token)
    if not data or not db.query_one("SELECT 1 AS x FROM user_account WHERE id = ?", (data["u"],)):
        return _page(request, token, status_code=404)
    return _page(request, token, done=lifecycle_mail.is_opted_out(int(data["u"])))


@router.post("/mail/unsubscribe/{token}")
def mail_unsubscribe_submit(token: str, request: Request):
    # A valid token always works: one-click posts come from a few provider
    # addresses, and a limit there would drop real refusals. Only failed
    # attempts count towards the limit.
    data = lifecycle_mail.read_unsubscribe_token(token)
    if data and lifecycle_mail.unsubscribe(int(data["u"]), str(data["h"])):
        return _page(request, token, done=True)
    if _blocked(request):
        return _page(request, token, status_code=429)
    _count(request)
    return _page(request, token, status_code=404)
