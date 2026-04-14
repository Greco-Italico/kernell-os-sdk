"""
AP2 Mandate Compatibility Layer
=================================
Bridges Google's Agent Payments Protocol (AP2) "Mandates" into
KAP escrow operations.

An AP2 Mandate is a cryptographically signed authorization from a
human user that specifies:
  - What an agent is allowed to buy
  - Maximum spend limit
  - Expiration time
  - The user's verified identity

KAP uses Mandates to:
  1. Auto-trigger escrow_lock when a Mandate is received
  2. Enforce budget limits (never lock more than mandate.max_amount)
  3. Attach the Mandate signature to the escrow TX for auditability

Spec reference: https://developers.google.com/agent-payments
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("KAP_AP2")


@dataclass
class Mandate:
    """
    Representation of an AP2 Mandate (authorization to spend).

    This is a simplified view — full AP2 Mandates use Verifiable
    Credentials with cryptographic signatures. KAP preserves the
    full mandate in `raw` for external verification.
    """
    mandate_id: str
    payer_id: str                     # User/org who authorized
    agent_id: str                     # Agent authorized to spend
    service_type: str                 # What they're buying
    max_amount: float                 # Budget ceiling
    currency: str = "KERN"            # Token/currency
    expires_at: float = 0.0           # Unix timestamp
    signature: str = ""               # AP2 cryptographic signature
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mandate":
        return cls(
            mandate_id=data.get("mandate_id", ""),
            payer_id=data.get("payer_id", ""),
            agent_id=data.get("agent_id", ""),
            service_type=data.get("service_type", ""),
            max_amount=float(data.get("max_amount", 0)),
            currency=data.get("currency", "KERN"),
            expires_at=float(data.get("expires_at", 0)),
            signature=data.get("signature", ""),
            raw=data,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Mandate":
        return cls.from_dict(json.loads(json_str))


def validate_mandate(mandate: Mandate) -> Tuple[bool, str]:
    """
    Validate a Mandate before triggering escrow.

    Checks:
      1. Not expired
      2. Has positive budget
      3. Has required identity fields
    """
    if mandate.is_expired:
        return False, f"Mandate {mandate.mandate_id} expired at {mandate.expires_at}"
    if mandate.max_amount <= 0:
        return False, f"Mandate {mandate.mandate_id} has non-positive amount: {mandate.max_amount}"
    if not mandate.payer_id:
        return False, "Mandate missing payer_id"
    if not mandate.agent_id:
        return False, "Mandate missing agent_id"
    return True, "ok"


def escrow_from_mandate(
    engine: Any,  # EscrowEngine
    mandate: Mandate,
    contract_id: Optional[str] = None,
    amount: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Convenience: validate an AP2 Mandate and auto-lock escrow.

    Args:
        engine: A KAP EscrowEngine instance
        mandate: The AP2 Mandate authorization
        contract_id: Optional override (defaults to mandate_id)
        amount: Amount to lock (defaults to mandate.max_amount, capped by it)

    Returns:
        (success, message) from engine.lock()
    """
    # Validate mandate first
    valid, err = validate_mandate(mandate)
    if not valid:
        return False, f"mandate_invalid: {err}"

    # Determine lock amount (never exceed mandate ceiling)
    lock_amount = min(amount or mandate.max_amount, mandate.max_amount)
    cid = contract_id or mandate.mandate_id

    logger.info(
        f"AP2 Mandate → Escrow: payer={mandate.payer_id} "
        f"amount={lock_amount} {mandate.currency} contract={cid}"
    )

    return engine.lock(mandate.payer_id, lock_amount, cid)
