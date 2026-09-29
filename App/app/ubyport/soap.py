"""SOAP envelope construction and response parsing for WS_UBY.

Element order matters. The service is WCF-hosted and its DataContractSerializer
emits members in alphabetical order, which is what the wire example in
appendix 5 section 5.1.1 shows. Appendix 5 section 7 explicitly warns against
renaming or reordering nodes when the body is built by hand, so the field
order below is fixed and deliberate.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_METHOD = "http://UBY.pcr.cz/WS_UBY"
NS_DATA = "http://schemas.datacontract.org/2004/07/WS_UBY"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_WSA_NONE = "http://schemas.microsoft.com/ws/2005/05/addressing/none"

ACTION_PREFIX = "http://UBY.pcr.cz/WS_UBY/IWS_UBY/"

# XML 1.0 cannot carry these at all; one of them in any field makes the
# whole UbyPort batch unparseable for every guest in it.
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Alphabetical, exactly as the service serialises SeznamUbytovanych.
HEADER_FIELDS = (
    "uCont",
    "uHomN",
    "uIdub",
    "uMark",
    "uName",
    "uOb",
    "uObCa",
    "uOkr",
    "uOriN",
    "uPsc",
    "uStr",
)

# Alphabetical, exactly as the service serialises Ubytovany.
GUEST_FIELDS = (
    "cDate",
    "cDocN",
    "cFirstN",
    "cFrom",
    "cNati",
    "cNote",
    "cPlac",
    "cPurp",
    "cResi",
    "cSpz",
    "cSurN",
    "cUntil",
    "cVisN",
)


def _node(prefix: str, name: str, value: Any) -> str:
    """One element, or a nil element when the value is None."""
    if value is None:
        return f'<{prefix}:{name} i:nil="true" />'
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = escape(_XML_ILLEGAL.sub(" ", str(value)))
    return f"<{prefix}:{name}>{text}</{prefix}:{name}>"


def build_envelope(method: str, body_inner: str, include_wsa_header: bool = False) -> str:
    header = ""
    if include_wsa_header:
        header = (
            f'<Action s:mustUnderstand="1" xmlns="{NS_WSA_NONE}">'
            f"{ACTION_PREFIX}{method}</Action>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<s:Envelope xmlns:s="{NS_SOAP}">'
        f"<s:Header>{header}</s:Header>"
        f"<s:Body>{body_inner}</s:Body>"
        "</s:Envelope>"
    )


def build_zapis_ubytovane(
    header: Dict[str, Optional[str]],
    guests: List[Dict[str, Any]],
    auth_code: str = "X",
    include_wsa_header: bool = False,
) -> str:
    """Serialise a ZapisUbytovane call: one facility header plus 1..N guests."""
    guest_xml = []
    for guest in guests:
        fields = "".join(_node("d", name, guest.get(name)) for name in GUEST_FIELDS)
        guest_xml.append(f"<d:Ubytovany>{fields}</d:Ubytovany>")

    seznam = (
        f'<Seznam xmlns:d="{NS_DATA}" xmlns:i="{NS_XSI}">'
        f"<d:Ubytovani>{''.join(guest_xml)}</d:Ubytovani>"
        + "".join(_node("d", name, header.get(name)) for name in HEADER_FIELDS)
        + _node("d", "VracetPDF", True)
        + "</Seznam>"
    )
    body = (
        f'<ZapisUbytovane xmlns="{NS_METHOD}">'
        f"<AutentificationCode>{escape(auth_code)}</AutentificationCode>"
        f"{seznam}"
        "</ZapisUbytovane>"
    )
    return build_envelope("ZapisUbytovane", body, include_wsa_header)


def build_simple_call(
    method: str, auth_code: str = "X", extra: str = "", include_wsa_header: bool = False
) -> str:
    body = (
        f'<{method} xmlns="{NS_METHOD}">'
        f"<AutentificationCode>{escape(auth_code)}</AutentificationCode>"
        f"{extra}"
        f"</{method}>"
    )
    return build_envelope(method, body, include_wsa_header)


def build_dej_mi_ciselnik(kind: str, auth_code: str = "X", include_wsa_header: bool = False) -> str:
    return build_simple_call(
        "DejMiCiselnik", auth_code, f"<CoChci>{escape(kind)}</CoChci>", include_wsa_header
    )


# --- response parsing ----------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find(root: ET.Element, name: str) -> Optional[ET.Element]:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _find_all(root: ET.Element, name: str) -> List[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == name]


def _is_nil(el: ET.Element) -> bool:
    return el.get(f"{{{NS_XSI}}}nil") == "true"


def parse_fault(xml_text: str) -> Optional[str]:
    """Return the fault string if the response is a SOAP fault."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    fault = _find(root, "Fault")
    if fault is None:
        return None
    parts = []
    for name in ("faultcode", "faultstring", "Reason", "Text"):
        el = _find(fault, name)
        if el is not None and (el.text or "").strip():
            parts.append(el.text.strip())
    return " / ".join(parts) or "Unspecified SOAP fault"


def parse_zapis_response(xml_text: str) -> Dict[str, Any]:
    """Extract the Chyby class returned by ZapisUbytovane."""
    root = ET.fromstring(xml_text)
    result: Dict[str, Any] = {
        "header_errors": "",
        "record_errors": [],
        "receipt_pdf": "",
        "error_pdf": "",
        "pseudo_stamp": "",
    }

    el = _find(root, "ChybyHlavicky")
    if el is not None and not _is_nil(el):
        result["header_errors"] = (el.text or "").strip()

    container = _find(root, "ChybyZaznamu")
    if container is not None:
        for item in container:
            result["record_errors"].append((item.text or "").strip())

    for key, tag in (
        ("receipt_pdf", "DokumentPotvrzeni"),
        ("error_pdf", "DokumentChybyPotvrzeni"),
    ):
        el = _find(root, tag)
        if el is not None and not _is_nil(el):
            result[key] = (el.text or "").strip()

    # The specification text spells this both "PseudoRazitko" and
    # "PseudoRazirko"; accept either.
    for tag in ("PseudoRazitko", "PseudoRazirko"):
        el = _find(root, tag)
        if el is not None and not _is_nil(el) and (el.text or "").strip():
            result["pseudo_stamp"] = el.text.strip()
            break

    return result


def parse_scalar_response(xml_text: str, method: str) -> Optional[str]:
    root = ET.fromstring(xml_text)
    el = _find(root, f"{method}Result")
    if el is None:
        return None
    return (el.text or "").strip()


def parse_ciselnik_response(xml_text: str) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_text)
    out: List[Dict[str, str]] = []
    for entry in _find_all(root, "CiselnikType"):
        item: Dict[str, str] = {}
        for child in entry:
            item[_local(child.tag)] = (child.text or "").strip()
        out.append(item)
    return out
