"""Public legal pages (software operator — no login required)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import operator
from ..templating import render

router = APIRouter()


@router.get("/legal")
def legal_operator(request: Request):
    return render(
        request,
        "legal.html",
        {"operator": operator.details(), "wrap_class": "narrow"},
        status_code=200,
    )
