"""Public legal pages (software operator — no login required)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import operator
from ..templating import render

router = APIRouter()

TERMS_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 28))
PRIVACY_SECTION_IDS = tuple(f"{n:02d}" for n in range(1, 23))


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
