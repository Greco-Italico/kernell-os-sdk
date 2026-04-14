"""
A2A Agent Card Compatibility Layer
====================================
Parses and validates A2A Agent Cards (JSON metadata) so that
escrow contracts reference standard agent identities instead of
arbitrary string IDs.

Spec reference: https://a2a-protocol.org/spec/agent-cards

An Agent Card contains:
  - name: Human-readable agent name
  - url: Agent's service endpoint
  - capabilities: List of supported actions
  - authentication: Required auth methods
  - version: A2A protocol version

KAP uses Agent Cards to:
  1. Identify buyer/seller in escrow contracts
  2. Verify the agent is reachable before locking funds
  3. Publish reputation scores back to the agent's profile
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("KAP_A2A")


@dataclass
class AgentCard:
    """
    Lightweight representation of an A2A Agent Card.
    
    Only the fields relevant to escrow are required.
    Additional A2A fields are preserved in `extra`.
    """
    name: str
    url: str
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0"
    authentication: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        """
        Deterministic agent ID derived from (name + url).
        Used as the wallet key in escrow operations.
        """
        raw = f"{self.name}::{self.url}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["agent_id"] = self.agent_id
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCard":
        known = {"name", "url", "capabilities", "version", "authentication"}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            name=data.get("name", "unknown"),
            url=data.get("url", ""),
            capabilities=data.get("capabilities", []),
            version=data.get("version", "1.0"),
            authentication=data.get("authentication", {}),
            extra=extra,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AgentCard":
        return cls.from_dict(json.loads(json_str))


def validate_agent_card(card: AgentCard) -> tuple[bool, str]:
    """
    Validate that an Agent Card has the minimum fields required
    for escrow participation.
    
    Returns (is_valid, error_message).
    """
    if not card.name or not card.name.strip():
        return False, "Agent Card missing 'name'"
    if not card.url or not card.url.strip():
        return False, "Agent Card missing 'url'"
    if not card.url.startswith(("http://", "https://")):
        return False, f"Agent Card 'url' must be HTTP(S), got: {card.url}"
    if not card.capabilities:
        logger.warning(f"Agent Card '{card.name}' has no capabilities listed")
    return True, "ok"


def agent_id_from_card(card: AgentCard) -> str:
    """Convenience: extract the deterministic agent_id."""
    return card.agent_id
