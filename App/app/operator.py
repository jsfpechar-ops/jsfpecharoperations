"""Public operator identity for UbyHost (software provider, not the accommodation data controller)."""
from __future__ import annotations

from typing import Any, Dict

from . import config


def details() -> Dict[str, Any]:
    """Operator of the UbyHost software — distinct from each host's legal entity (GDPR controller)."""
    return {
        "name": config.OPERATOR_NAME,
        "ico": config.OPERATOR_ICO,
        "dic": config.OPERATOR_DIC,
        "address": config.OPERATOR_ADDRESS,
        "email": config.OPERATOR_EMAIL,
        "registry_url": config.OPERATOR_REGISTRY_URL,
    }
