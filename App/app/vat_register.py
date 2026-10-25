"""MFČR VAT register (registr plátců DPH) lookup for invoice details.

Uses the official "rozhraní CRPDPH" SOAP service, on the host's click only,
and sends only the DIČ digits. Returns the published bank accounts and the
VAT status; ARES does not publish accounts.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import payments

_API_URL = "https://adisrws.mfcr.cz/dpr/axis2/services/rozhraniCRPDPH.rozhraniCRPDPHSOAP"
_ACTION = "http://adis.mfcr.cz/rozhraniCRPDPH/getStatusNespolehlivySubjektRozsirenyV2"
_NS = "{http://adis.mfcr.cz/rozhraniCRPDPH/}"
_TIMEOUT_SECONDS = 6
_MAX_BYTES = 200_000
_USER_AGENT = "UbyHost"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_DIC_RE = re.compile(r"^(?:CZ)?(\d{8,10})$")
_VAT_STATUS = {
    "PLATCE_DPH": "payer",
    "SKUPINA_DPH": "payer",
    "IDENTIFIKOVANA_OSOBA": "identified",
}
_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soapenv:Body>"
    '<StatusNespolehlivySubjektRozsirenyV2Request xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/">'
    "<dic>{dic}</dic>"
    "</StatusNespolehlivySubjektRozsirenyV2Request>"
    "</soapenv:Body></soapenv:Envelope>"
)

_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}


def dic_digits(raw: str) -> str:
    """The digits of a Czech DIČ ("CZ12345678" -> "12345678"), or "" if it is not one."""
    text = re.sub(r"\s+", "", raw or "").upper()
    match = _DIC_RE.match(text)
    return match.group(1) if match else ""


def _accounts(subject: ET.Element) -> List[str]:
    accounts: List[str] = []
    for ucet in subject.iter(f"{_NS}ucet"):
        if ucet.get("datumZverejneniUkonceni"):
            continue
        standard = ucet.find(f"{_NS}standardniUcet")
        if standard is None:
            continue
        account = payments.compose_czech_account(
            standard.get("predcisli") or "", standard.get("cislo") or "", standard.get("kodBanky") or ""
        )
        if account and account not in accounts:
            accounts.append(account)
    return accounts


def _parse(body: bytes, digits: str) -> Optional[Dict[str, Any]]:
    """Mapped data, None when the register does not know the DIČ; raises on a bad answer."""
    root = ET.fromstring(body)
    status = root.find(f".//{_NS}status")
    if status is None or status.get("statusCode") != "0":
        raise ValueError("register error")
    for subject in root.iter(f"{_NS}statusSubjektu"):
        if subject.get("dic") != digits:
            continue
        vat_status = _VAT_STATUS.get(subject.get("typSubjektu") or "")
        if not vat_status:
            return None
        return {
            "vat_status": vat_status,
            "unreliable": subject.get("nespolehlivyPlatce") == "ANO",
            "accounts": _accounts(subject),
        }
    return None


def lookup(dic: str) -> Optional[Dict[str, Any]]:
    """Return the register data for ``dic`` or None (unknown DIČ or any failure)."""
    digits = dic_digits(dic)
    if not digits:
        return None
    now = time.time()
    cached = _CACHE.get(digits)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        response = requests.post(
            _API_URL,
            data=_ENVELOPE.format(dic=digits).encode("utf-8"),
            timeout=_TIMEOUT_SECONDS,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{_ACTION}"',
                "User-Agent": _USER_AGENT,
            },
        )
        if not response.ok or len(response.content) > _MAX_BYTES:
            return None
        data = _parse(response.content, digits)
    except Exception:
        return None
    if len(_CACHE) > 1000:
        _CACHE.clear()
    _CACHE[digits] = (now, data)
    return data
