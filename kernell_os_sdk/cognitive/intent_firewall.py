"""
Kernell OS SDK — Intent Firewall (Agentic Immune System)
════════════════════════════════════════════════════════
Every action an agent wants to perform passes through here.
Actions are classified by type and risk, then auto-approved,
queued for human review, or denied outright.

This is what makes Kernell OS fundamentally safer than
Claude Code, OpenCode, or any uncontrolled agent framework.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger("kernell.cognitive.firewall")


class ActionType(str, Enum):
    """Category of agent action."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    LIST_DIR = "list_dir"
    EXECUTE_COMMAND = "execute_command"
    NETWORK_REQUEST = "network_request"
    RUN_TESTS = "run_tests"
    GIT_OPERATION = "git_operation"
    INSTALL_PACKAGE = "install_package"
    SYSTEM_CALL = "system_call"


class RiskLevel(str, Enum):
    """Assessed risk of an action."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FirewallVerdict(str, Enum):
    """Decision on an action."""
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"       # Waiting for human approval


# ── Default risk classification ──
_DEFAULT_RISK: Dict[ActionType, RiskLevel] = {
    ActionType.READ_FILE:        RiskLevel.NONE,
    ActionType.LIST_DIR:         RiskLevel.NONE,
    ActionType.RUN_TESTS:        RiskLevel.LOW,
    ActionType.GIT_OPERATION:    RiskLevel.LOW,
    ActionType.WRITE_FILE:       RiskLevel.MEDIUM,
    ActionType.INSTALL_PACKAGE:  RiskLevel.MEDIUM,
    ActionType.EXECUTE_COMMAND:  RiskLevel.HIGH,
    ActionType.NETWORK_REQUEST:  RiskLevel.HIGH,
    ActionType.DELETE_FILE:      RiskLevel.HIGH,
    ActionType.SYSTEM_CALL:      RiskLevel.CRITICAL,
}

# ── Patterns that ALWAYS get denied ──
_DENY_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/"),
    re.compile(r"sudo\s+"),
    re.compile(r"curl\s+.*\|\s*(ba)?sh"),
    re.compile(r"wget\s+.*\|\s*(ba)?sh"),
    re.compile(r"chmod\s+777"),
    re.compile(r"dd\s+if="),
    re.compile(r"mkfs"),
    re.compile(r":\(\)\{.*\}"),  # fork bomb
    re.compile(r">(\/dev\/sd|\/dev\/nvme)"),  # raw device write
]


@dataclass
class AgentIntent:
    """An action an agent wants to perform."""
    intent_id: str = field(default_factory=lambda: f"intent-{uuid.uuid4().hex[:10]}")
    agent_id: str = ""
    action_type: ActionType = ActionType.READ_FILE
    target: str = ""              # file path, URL, command string
    payload: str = ""             # file content, request body, etc.
    context: str = ""             # why the agent wants to do this
    timestamp: float = field(default_factory=time.time)


@dataclass
class FirewallDecision:
    """The firewall's ruling on an intent."""
    intent_id: str
    agent_id: str
    action_type: str
    target: str
    risk: RiskLevel
    verdict: FirewallVerdict
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_event(self) -> dict:
        """Serialize for /ws/firewall broadcast."""
        return {
            "intent_id": self.intent_id,
            "agent": self.agent_id,
            "action": self.action_type,
            "target": self.target[:200],
            "risk": self.risk.value,
            "verdict": self.verdict.value,
            "reason": self.reason,
        }


class IntentFirewall:
    """
    The immune system of Kernell OS.

    Classifies every agent action by risk and applies policy:
      - auto_approve: Actions allowed without human input
      - manual_approve: Actions queued for Dashboard approval
      - always_deny: Actions that are NEVER allowed
    """

    def __init__(
        self,
        auto_approve: Optional[Set[ActionType]] = None,
        manual_approve: Optional[Set[ActionType]] = None,
        always_deny_patterns: Optional[List[re.Pattern]] = None,
        on_decision: Optional[Callable] = None,
    ):
        self._auto_approve = auto_approve or {
            ActionType.READ_FILE,
            ActionType.LIST_DIR,
            ActionType.RUN_TESTS,
        }
        self._manual = manual_approve or {
            ActionType.WRITE_FILE,
            ActionType.EXECUTE_COMMAND,
            ActionType.NETWORK_REQUEST,
            ActionType.INSTALL_PACKAGE,
            ActionType.GIT_OPERATION,
        }
        self._deny_patterns = always_deny_patterns or _DENY_PATTERNS
        self._on_decision = on_decision
        self._pending: Dict[str, AgentIntent] = {}
        self._decision_log: List[FirewallDecision] = []

    def evaluate(self, intent: AgentIntent) -> FirewallDecision:
        """
        Evaluate an agent's intent and return a decision.

        Flow:
          1. Check deny patterns → DENIED
          2. Check auto_approve set → APPROVED
          3. Everything else → PENDING (human review)
        """
        # Step 1: Always-deny patterns
        target_lower = (intent.target + " " + intent.payload).lower()
        for pattern in self._deny_patterns:
            if pattern.search(target_lower):
                decision = FirewallDecision(
                    intent_id=intent.intent_id,
                    agent_id=intent.agent_id,
                    action_type=intent.action_type.value,
                    target=intent.target,
                    risk=RiskLevel.CRITICAL,
                    verdict=FirewallVerdict.DENIED,
                    reason=f"Matched deny pattern: {pattern.pattern}",
                )
                self._record(decision)
                return decision

        # Step 2: Auto-approve
        if intent.action_type in self._auto_approve:
            risk = _DEFAULT_RISK.get(intent.action_type, RiskLevel.LOW)
            decision = FirewallDecision(
                intent_id=intent.intent_id,
                agent_id=intent.agent_id,
                action_type=intent.action_type.value,
                target=intent.target,
                risk=risk,
                verdict=FirewallVerdict.APPROVED,
                reason="auto_approved (policy)",
            )
            self._record(decision)
            return decision

        # Step 3: Manual approval required
        risk = _DEFAULT_RISK.get(intent.action_type, RiskLevel.MEDIUM)
        self._pending[intent.intent_id] = intent
        decision = FirewallDecision(
            intent_id=intent.intent_id,
            agent_id=intent.agent_id,
            action_type=intent.action_type.value,
            target=intent.target,
            risk=risk,
            verdict=FirewallVerdict.PENDING,
            reason="requires_human_approval",
        )
        self._record(decision)
        return decision

    def approve(self, intent_id: str) -> Optional[FirewallDecision]:
        """Human approves a pending intent from the Dashboard."""
        intent = self._pending.pop(intent_id, None)
        if not intent:
            return None
        decision = FirewallDecision(
            intent_id=intent_id,
            agent_id=intent.agent_id,
            action_type=intent.action_type.value,
            target=intent.target,
            risk=_DEFAULT_RISK.get(intent.action_type, RiskLevel.MEDIUM),
            verdict=FirewallVerdict.APPROVED,
            reason="human_approved",
        )
        self._record(decision)
        return decision

    def deny(self, intent_id: str) -> Optional[FirewallDecision]:
        """Human denies a pending intent from the Dashboard."""
        intent = self._pending.pop(intent_id, None)
        if not intent:
            return None
        decision = FirewallDecision(
            intent_id=intent_id,
            agent_id=intent.agent_id,
            action_type=intent.action_type.value,
            target=intent.target,
            risk=_DEFAULT_RISK.get(intent.action_type, RiskLevel.MEDIUM),
            verdict=FirewallVerdict.DENIED,
            reason="human_denied",
        )
        self._record(decision)
        return decision

    def get_pending(self) -> List[dict]:
        """Return all pending intents for Dashboard rendering."""
        return [
            {
                "intent_id": i.intent_id,
                "agent": i.agent_id,
                "action": i.action_type.value,
                "target": i.target[:200],
                "context": i.context[:200],
                "risk": _DEFAULT_RISK.get(i.action_type, RiskLevel.MEDIUM).value,
            }
            for i in self._pending.values()
        ]

    def _record(self, decision: FirewallDecision) -> None:
        self._decision_log.append(decision)
        if self._on_decision:
            self._on_decision(decision.to_event())
        logger.info(
            f"Firewall: {decision.verdict.value} | "
            f"{decision.agent_id} → {decision.action_type} "
            f"({decision.target[:60]}) [{decision.risk.value}]"
        )
