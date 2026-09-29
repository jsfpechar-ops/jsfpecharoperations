"""HTTP/NTLM transport for the UbyPort web service."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
import urllib3

from . import soap

try:
    from requests_ntlm import HttpNtlmAuth
except ImportError:  # pragma: no cover - dependency is declared
    HttpNtlmAuth = None


def include_wsa_header() -> bool:
    """Whether to send the WS-Addressing header, read per call.

    A runtime read rather than a module constant: the flag is an
    interoperability switch for the police service, and an operator turning it
    on in the environment should not have to wait for a rebuild.
    """
    return os.environ.get("UBYHOST_SOAP_WSA_HEADER", "0") not in ("0", "false", "no")


class UbyportError(Exception):
    """Data was reachable but the service refused it."""


class UbyportTransportError(UbyportError):
    """The service could not be reached or returned a fault.

    Appendix 5 section 10.2(c) requires the host application to escalate this
    rather than swallow it, and 10.2(e) requires that no data is lost.
    """


class UbyportOutcomeUnknownError(UbyportTransportError):
    """The request may have reached UbyPort, so whether it was filed is unknown.

    A timeout after sending, a 5xx, an unreadable answer or a record-count
    mismatch. Resending automatically risks a duplicate the police count
    against the host, so callers must not retry this on their own.
    ``request_xml`` carries the envelope that was sent, when known.
    """

    request_xml: str = ""


class UbyportAuthError(UbyportTransportError):
    """UbyPort refused the web-service login (HTTP 401). Retrying cannot help."""


def _definitely_not_sent(exc: requests.RequestException) -> bool:
    """True only when the request cannot have reached the server."""
    if isinstance(exc, (requests.ConnectTimeout, requests.exceptions.SSLError)):
        return True
    if isinstance(exc, requests.ConnectionError) and exc.args:
        reason = getattr(exc.args[0], "reason", None)
        return isinstance(reason, urllib3.exceptions.NewConnectionError)
    return False


@dataclass
class SubmissionResult:
    endpoint: str
    request_xml: str
    response_xml: str
    header_errors: str = ""
    record_errors: List[str] = field(default_factory=list)
    receipt_pdf: str = ""
    error_pdf: str = ""
    pseudo_stamp: str = ""


class UbyportClient:
    def __init__(
        self,
        endpoint: str,
        username: str = "",
        password: str = "",
        domain: str = "EXRESORTMV",
        timeout: int = 60,
        use_ntlm: bool = True,
        auth_code: str = "X",
        verify_tls: bool = True,
    ):
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.domain = domain
        self.timeout = timeout
        self.use_ntlm = use_ntlm
        self.auth_code = auth_code
        self.verify_tls = verify_tls

    # --- transport -------------------------------------------------------

    def _auth(self):
        if not self.use_ntlm or not self.username:
            return None
        if HttpNtlmAuth is None:
            raise UbyportTransportError(
                "requests_ntlm is not installed, so NTLM authentication is unavailable."
            )
        # The police authenticate web-service accounts against the EXRESORTMV
        # domain, so the login must be sent in DOMAIN\user form.
        user = self.username if "\\" in self.username else f"{self.domain}\\{self.username}"
        return HttpNtlmAuth(user, self.password)

    def _post(self, method: str, envelope: str) -> str:
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{soap.ACTION_PREFIX}{method}",
            "Accept": "text/xml",
        }
        try:
            response = requests.post(
                self.endpoint,
                data=envelope.encode("utf-8"),
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
                verify=self.verify_tls,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            if _definitely_not_sent(exc):
                raise UbyportTransportError(
                    f"Could not reach UbyPort at {self.endpoint}: {exc}"
                ) from exc
            raise UbyportOutcomeUnknownError(
                f"UbyPort did not answer after the request was sent (outcome unknown): {exc}"
            ) from exc

        text = response.text or ""
        if response.status_code == 401:
            raise UbyportAuthError(
                "UbyPort rejected the credentials (HTTP 401). Check that this is a web-service "
                "login (UBY-WS...) and that it is registered for this IDUB."
            )
        if 300 <= response.status_code < 400:
            raise UbyportTransportError(
                f"UbyPort returned an unexpected redirect (HTTP {response.status_code})."
            )
        fault = soap.parse_fault(text)
        if fault:
            raise UbyportTransportError(f"UbyPort returned a SOAP fault: {fault}")
        if response.status_code >= 500:
            raise UbyportOutcomeUnknownError(
                f"UbyPort returned HTTP {response.status_code} (outcome unknown): {text[:400]}"
            )
        if response.status_code >= 400:
            raise UbyportTransportError(
                f"UbyPort returned HTTP {response.status_code}: {text[:400]}"
            )
        return text

    # --- operations ------------------------------------------------------

    def test_availability(self) -> bool:
        envelope = soap.build_simple_call("TestDostupnosti", self.auth_code, "", include_wsa_header())
        text = self._post("TestDostupnosti", envelope)
        return (soap.parse_scalar_response(text, "TestDostupnosti") or "").lower() == "true"

    def max_batch_size(self) -> Optional[int]:
        envelope = soap.build_simple_call(
            "MaximalniDelkaSeznamu", self.auth_code, "", include_wsa_header()
        )
        text = self._post("MaximalniDelkaSeznamu", envelope)
        value = soap.parse_scalar_response(text, "MaximalniDelkaSeznamu")
        try:
            return int(value) if value else None
        except ValueError:
            return None

    def code_list(self, kind: str) -> List[Dict[str, str]]:
        """kind is one of Staty, UcelyPobytu, Chyby."""
        envelope = soap.build_dej_mi_ciselnik(kind, self.auth_code, include_wsa_header())
        text = self._post("DejMiCiselnik", envelope)
        return soap.parse_ciselnik_response(text)

    def submit(
        self,
        header: Dict[str, Optional[str]],
        guests: List[Dict[str, Any]],
    ) -> SubmissionResult:
        if not guests:
            raise UbyportError("Nothing to submit: the guest list is empty.")
        envelope = soap.build_zapis_ubytovane(
            header, guests, self.auth_code, include_wsa_header()
        )
        try:
            text = self._post("ZapisUbytovane", envelope)
        except UbyportOutcomeUnknownError as exc:
            exc.request_xml = envelope
            raise
        try:
            parsed = soap.parse_zapis_response(text)
        except ET.ParseError as exc:
            err = UbyportOutcomeUnknownError(
                "UbyPort returned an unreadable XML response."
            )
            err.request_xml = envelope
            raise err from exc
        if len(parsed["record_errors"]) != len(guests):
            err = UbyportOutcomeUnknownError(
                "UbyPort returned an incomplete result: "
                f"{len(parsed['record_errors'])} outcomes for {len(guests)} guest records."
            )
            err.request_xml = envelope
            raise err
        return SubmissionResult(
            endpoint=self.endpoint,
            request_xml=envelope,
            response_xml=text,
            header_errors=parsed["header_errors"],
            record_errors=parsed["record_errors"],
            receipt_pdf=parsed["receipt_pdf"],
            error_pdf=parsed["error_pdf"],
            pseudo_stamp=parsed["pseudo_stamp"],
        )
