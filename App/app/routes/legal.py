"""Public legal pages (software operator — no login required)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import config, operator
from ..public_guides import GUIDES
from ..templating import render

router = APIRouter()

TERMS_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 28))
PRIVACY_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 23))
DPA_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 25))


@router.get("/pruvodce/{slug}")
def public_guide(request: Request, slug: str):
    guide = GUIDES.get(slug)
    if not guide:
        raise HTTPException(status_code=404)
    return render(
        request,
        "public_guide.html",
        {
            "guide": guide,
            "guides": GUIDES,
            "current_slug": slug,
            "canonical_url": f"{config.PUBLIC_BASE_URL}/pruvodce/{slug}",
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
