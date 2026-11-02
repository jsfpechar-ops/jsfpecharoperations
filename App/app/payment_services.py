"""Saved extras a host charges often (0762): name + price, per owner.

Stored as JSON in the settings table (key payment_services:<owner>), so no
schema change. Not personal data: a service name and a price.
"""
from __future__ import annotations

import json
import secrets
from typing import Any, Dict, List, Optional

from . import db

MAX_SERVICES = 20
MAX_NAME = 60
MAX_AMOUNT = 1_000_000


def _key(owner_user_id: int) -> str:
    return f"payment_services:{int(owner_user_id)}"


def list_for(owner_user_id: int) -> List[Dict[str, Any]]:
    raw = db.get_setting(_key(owner_user_id)) or "[]"
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    return [i for i in items if isinstance(i, dict) and i.get("id") and i.get("name")]


def get(owner_user_id: int, service_id: str) -> Optional[Dict[str, Any]]:
    return next((s for s in list_for(owner_user_id) if s["id"] == service_id), None)


def add(owner_user_id: int, name: str, amount_czk: int) -> Dict[str, Any]:
    name = " ".join((name or "").split())[:MAX_NAME]
    if not name:
        raise ValueError("name required")
    if not isinstance(amount_czk, int) or not 1 <= amount_czk <= MAX_AMOUNT:
        raise ValueError("amount out of range")
    items = list_for(owner_user_id)
    if len(items) >= MAX_SERVICES:
        raise ValueError("too many services")
    item = {"id": secrets.token_hex(4), "name": name, "amount_czk": amount_czk}
    items.append(item)
    db.set_setting(_key(owner_user_id), json.dumps(items, ensure_ascii=False))
    return item


def remove(owner_user_id: int, service_id: str) -> bool:
    items = list_for(owner_user_id)
    kept = [s for s in items if s["id"] != service_id]
    if len(kept) == len(items):
        return False
    db.set_setting(_key(owner_user_id), json.dumps(kept, ensure_ascii=False))
    return True
