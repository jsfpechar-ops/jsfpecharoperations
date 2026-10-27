"""Public legal pages (software operator — no login required)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import billing, config, cookie_inventory, host_i18n, operator, signup
from ..public_guides import GUIDE_TRANSLATIONS
from ..templating import render

router = APIRouter()

# WP24: § 10a (UbyPort access credentials) sits between § 10 and § 11, so the
# later clauses keep their numbers.
TERMS_SECTION_IDS = (
    tuple(f"{n:02d}" for n in range(1, 11)) + ("10a",) + tuple(f"{n:02d}" for n in range(11, 28))
)
PRIVACY_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 23))
DPA_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 25))
# WP09: the five rows of 04_legal_positions.md section 5 first, then the two
# conditional providers the repo still documents (Render demo, Drive backups).
SUBPROCESSOR_IDS = (
    "aws_lightsail",
    "aws_ses",
    "aws_s3",
    "cloudflare",
    "posthog",
    "render",
    "google",
)
# Recipients that are not subprocessors (section 5). "google_ads" belongs to
# self sign-up with Google Ads (WP20), so it is listed only while
# UBYHOST_SIGNUP_ENABLED is on (recipient_ids()).
# "meta_ads" (WP21) is listed only while sign-up is on and the Meta
# Conversions API is configured.
# "push" (0229) is listed only while urgent alerts are on (UBYHOST_WEB_PUSH).
RECIPIENT_IDS = ("google_ads", "meta_ads", "police", "municipality", "ttlock", "push")


def recipient_ids() -> tuple:
    hidden = set()
    if not config.WEB_PUSH:
        hidden.add("push")
    if not signup.enabled():
        hidden.update(("google_ads", "meta_ads"))
    elif not config.meta_capi_enabled():
        hidden.add("meta_ads")
    return tuple(rid for rid in RECIPIENT_IDS if rid not in hidden)


@router.get("/jak-to-funguje")
def product_details(request: Request):
    """Public product detail and UbyPort FAQ page."""
    return render(
        request,
        "product.html",
        {"show_nav": False, "open_alerts": []},
    )


# The public price list in whole Kč, read from app/billing.py (brief 0416) so
# the page and the invoices can never disagree.
PUBLIC_RATES = {
    "base": {interval: list(rates) for interval, rates in billing.BASE.items()},
    "max": {interval: list(rates) for interval, rates in billing.MAX_EXTRA.items()},
    "ttlock": dict(billing.TTLOCK),
}


def _graduated(count: int, rates) -> int:
    """Each band prices only the apartments in it: 1-4, 5-9, 10 and up."""
    return sum(rates[0 if i <= 4 else 1 if i <= 9 else 2] for i in range(1, count + 1))


def _per_month(year_total: int) -> int:
    """A yearly total shown per month, rounded half up like Math.round in pricing.js."""
    return (year_total * 2 + 12) // 24


def _kc(amount: int, lang: str) -> str:
    """1 190 (no-break space) in Czech, 1,190 in English, as pricing.js prints it."""
    text = f"{amount:,}"
    return text.replace(",", " ") if lang == "cs" else text


@router.get("/cenik")
def pricing(request: Request):
    """Public price list with the calculator (brief 0412). Without JS: 1 apartment, yearly."""
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)
    std_year = _graduated(1, PUBLIC_RATES["base"]["year"])
    max_year = std_year + _graduated(1, PUBLIC_RATES["max"]["year"])
    start = {
        "std_month": _kc(_per_month(std_year), lang),
        "max_month": _kc(_per_month(max_year), lang),
        "std_year": _kc(std_year, lang),
        "max_year": _kc(max_year, lang),
        "ttlock_month": _kc(_per_month(PUBLIC_RATES["ttlock"]["year"]), lang),
        "ttlock_year": _kc(PUBLIC_RATES["ttlock"]["year"], lang),
        "bands": [_kc(_per_month(rate), lang) for rate in PUBLIC_RATES["base"]["year"]],
    }
    return render(
        request,
        "pricing.html",
        {
            "show_nav": False,
            "open_alerts": [],
            **signup.public_context(request),
            "rates": PUBLIC_RATES,
            "start": start,
            # 0416: places left at the founder price, only while billing is on.
            "founder_left": billing.founder_slots_left() if billing.enabled() else None,
        },
    )


@router.get("/pruvodce/{slug}")
def public_guide(request: Request, slug: str):
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)
    guides = GUIDE_TRANSLATIONS[lang]
    guide = guides.get(slug)
    if not guide:
        raise HTTPException(status_code=404)
    path = f"/pruvodce/{slug}"
    requested = host_i18n.supported_language(request.query_params.get("lang"))
    canonical = f"{config.PUBLIC_BASE_URL}{path}"
    if requested:
        canonical += f"?lang={requested}"
    return render(
        request,
        "public_guide.html",
        {
            "guide": guide,
            "guides": guides,
            "current_slug": slug,
            "canonical_url": canonical,
            "alternate_urls": [
                ("cs", f"{config.PUBLIC_BASE_URL}{path}?lang=cs"),
                ("en", f"{config.PUBLIC_BASE_URL}{path}?lang=en"),
                ("x-default", f"{config.PUBLIC_BASE_URL}{path}"),
            ],
            "show_nav": False,
            "open_alerts": [],
        },
    )


@router.get("/legal")
def legal_operator(request: Request):
    return render(
        request,
        "legal.html",
        {"operator": operator.details(), "wrap_class": "narrow"},
        status_code=200,
    )


@router.get("/terms")
def terms_of_service(request: Request):
    op = operator.details()
    return render(
        request,
        "terms.html",
        {
            "operator": op,
            "wrap_class": "narrow",
            "terms_sections": TERMS_SECTION_IDS,
        },
        status_code=200,
    )


@router.get("/privacy")
def privacy_policy(request: Request):
    op = operator.details()
    return render(
        request,
        "privacy.html",
        {
            "operator": op,
            "wrap_class": "narrow",
            "privacy_sections": PRIVACY_SECTION_IDS,
            "cookie_inventory": cookie_inventory.COOKIE_INVENTORY,
            "cookieless_services": cookie_inventory.COOKIELESS_SERVICES,
            "legal_placeholders": config.DEPLOYMENT != "production",
            # WP20 draft for counsel: shown only while self sign-up is on.
            "signup_ads_notice": signup.enabled(),
            # WP21: the Meta paragraph only once the Conversions API is configured.
            "signup_meta_notice": signup.enabled() and config.meta_capi_enabled(),
        },
        status_code=200,
    )


@router.get("/dpa")
def data_processing_agreement(request: Request):
    op = operator.details()
    return render(
        request,
        "dpa.html",
        {
            "operator": op,
            "wrap_class": "narrow",
            "dpa_sections": DPA_SECTION_IDS,
        },
        status_code=200,
    )


@router.get("/subprocessors")
def subprocessor_register(request: Request):
    return render(
        request,
        "subprocessors.html",
        {
            "operator": operator.details(),
            "wrap_class": "narrow",
            "subprocessor_ids": SUBPROCESSOR_IDS,
            "recipient_ids": recipient_ids(),
            "signup_meta_notice": signup.enabled() and config.meta_capi_enabled(),
        },
        status_code=200,
    )
