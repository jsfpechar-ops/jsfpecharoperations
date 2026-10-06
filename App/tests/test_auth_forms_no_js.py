"""UX-126 (audit B-22): the auth forms must not depend on JavaScript, and the
2FA templates must not carry inline styles.

``csrf.js`` injects the token, so a host whose JS failed got a silent
"form expired" bounce. Every auth form ships an explicit hidden ``_csrf``,
the e-mail login pages of task 0003 included, and the setup QR code was the
last inline style on these screens.
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
APP_CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.css"
AUTH_TEMPLATES = (
    "two_factor_setup.html",
    "two_factor_recovery.html",
    "account_accept.html",
    # Task 0003: the e-mail login pages.
    "login.html",
    "login_sent.html",
    "login_link.html",
    "account_email_confirm.html",
)

def _forms(source: str):
    """(method, body) for every <form> in a template."""
    for match in re.finditer(r"<form\b[^>]*>(.*?)</form>", source, re.S):
        opening = match.group(0)[: match.group(0).index(">")]
        yield opening, match.group(1)


def test_every_posting_auth_form_carries_its_own_csrf_field():
    for name in AUTH_TEMPLATES:
        source = (TEMPLATES / name).read_text(encoding="utf-8")
        forms = list(_forms(source))
        if name == "two_factor_recovery.html":
            assert not forms, "the recovery page stopped being a no-form page"
            continue
        assert forms, f"{name} lost its form"
        for opening, body in forms:
            if "post" not in opening.lower():
                continue
            assert 'name="_csrf"' in body, f"{name} posts without an explicit _csrf input"


def test_the_2fa_templates_have_no_inline_styles():
    for name in AUTH_TEMPLATES:
        source = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'style="' not in source, f"{name} still styles inline"


def test_the_qr_class_carries_the_style_that_was_inline():
    rules = APP_CSS.read_text(encoding="utf-8")
    block = re.search(r"\.auth-setup-qr\s*\{([^}]*)\}", rules)
    assert block, ".auth-setup-qr is missing from app.css"
    body = " ".join(block.group(1).split())
    for declaration in ("width: 220px", "max-width: 100%", "margin: 18px auto", "border-radius: 12px"):
        assert declaration in body, declaration
    assert 'class="auth-setup-qr"' in (TEMPLATES / "two_factor_setup.html").read_text(encoding="utf-8")
