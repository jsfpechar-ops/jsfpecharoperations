"""0404: the Leon setup wizard: switch on, import the listing, check the cards, try, done."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import ai, auth, guest_guide, guest_guide_import, guest_guide_merge, leon, security
from .admin_helpers import back
from .guest_guide import _home, _render

router = APIRouter(dependencies=[Depends(security.protect_host_post)])
TOTAL = 4


def _offered(request: Request, apartment_id: int):
    apartment = _home(request, apartment_id)
    if not ai.enabled_for_property(leon.FEATURE, apartment_id):
        raise HTTPException(404)
    return apartment


def _facts(apartment_id: int) -> Dict[str, Any]:
    progress = guest_guide.progress(apartment_id)
    imports = guest_guide_import.imports(apartment_id)
    open_cards = [
        r for r in guest_guide.items(apartment_id)
        if r["state"] == "check" or (r["state"] == "missing" and r["kind"] in guest_guide.MUST_HAVE)
    ]
    return {
        "progress": progress,
        "live": bool(progress["live"]),
        "checking": int(progress["check"]),
        "import_on": guest_guide_import.enabled(),
        "imports": imports,
        "import_started": any(r.get("status") != "failed" for r in imports),
        "import_busy": guest_guide_import.in_progress(apartment_id),
        "sources": guest_guide_import.sources_left(apartment_id),
        "drafts": guest_guide_merge.drafted_count(apartment_id),
        "open_cards": open_cards,
    }


@router.get("/apartments/{apartment_id}/leon/setup")
def setup_entry(request: Request, apartment_id: int):
    """0404: the first step the host still has to do."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _offered(request, apartment_id)
    facts = _facts(apartment_id)
    step = leon.setup_step(
        apartment, live=facts["live"], checking=facts["checking"],
        import_started=facts["import_started"], import_on=facts["import_on"],
    )
    return back(f"/apartments/{apartment_id}/leon/setup/{step}")


@router.get("/apartments/{apartment_id}/leon/setup/{step}")
def setup_step_page(request: Request, apartment_id: int, step: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = _offered(request, apartment_id)
    if step not in leon.SETUP_STEPS + ("done",):
        raise HTTPException(404)
    facts = _facts(apartment_id)
    state = leon.host_state(apartment, facts["live"])
    if state in ("off", "terms") and step != "switch_on":
        return back(f"/apartments/{apartment_id}/leon/setup/switch_on")
    steps = leon.SETUP_STEPS
    index = steps.index(step) if step in steps else None
    done_steps = set()
    if state in ("on", "waiting"):
        done_steps.add("switch_on")
    if facts["import_started"] or not facts["import_on"]:
        done_steps.add("import")
    if facts["live"] and not facts["checking"]:
        done_steps.add("cards")
    if step == "done":
        prev_step = "try"
    else:
        prev_step = steps[index - 1] if index else None
    open_cards = facts["open_cards"]
    return _render(
        request, f"leon_setup/{step}.html", apartment=apartment, step=step, steps=steps,
        number=index + 1 if index is not None else None, total=TOTAL, prev_step=prev_step,
        done_steps=done_steps, state=state,
        next_id=open_cards[0]["id"] if open_cards else None, **facts,
    )


@router.post("/apartments/{apartment_id}/leon/setup")
async def setup_save(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    _offered(request, apartment_id)
    form = await request.form()
    action = form.get("action")
    if action == "skip_import":
        return back(f"/apartments/{apartment_id}/leon/setup/cards")
    if action == "finish":
        return back(f"/apartments/{apartment_id}/leon/setup/done")
    return back(f"/apartments/{apartment_id}/leon/setup")
