"""
Kernell OS SDK — Security Telemetry & Observability
════════════════════════════════════════════════════
Structured event logging + real-time metrics aggregation for the
CognitiveSecurityLayer in production.

Provides:
  - SecurityEventLog: append-only structured log of every CSL decision
  - SecurityMetrics: aggregated stats (block rate, top patterns, actor drift)
  - SecurityObserver: singleton that wires into ToolGovernor + OutputGuard
"""

import time
import json
import os
from typing import Dict, Any, List, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict

import structlog

logger = structlog.get_logger("kernell.security.telemetry")


@dataclass
class SecurityEvent:
    """Single immutable security decision record."""
    timestamp: float
    event_type: str       # "tool_governor", "output_guard", "input_guard", "hallucination"
    origin: str           # "user", "m2m", "gui", "system"
    actor_id: str
    tool_requested: Optional[str]
    action: str           # "ALLOWED", "BLOCKED"
    reason: str
    risk_delta: int
    session_risk: int
    actor_risk: float
    effective_risk: float
    payload_snippet: str  # first 100 chars, sanitized
    is_shadow: bool = False
    would_block: bool = False
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    suspicious_success: bool = False


class SecurityEventLog:
    """Append-only structured event log. Thread-safe for single-process."""

    def __init__(self, max_events: int = 10000):
        self._events: List[SecurityEvent] = []
        self._max = max_events

    def record(self, event: SecurityEvent):
        if len(self._events) >= self._max:
            self._events = self._events[-(self._max // 2):]  # keep recent half
        self._events.append(event)
        logger.info(
            "security_event",
            event_type=event.event_type,
            action=event.action,
            origin=event.origin,
            actor=event.actor_id,
            tool=event.tool_requested,
            reason=event.reason[:80],
            risk_delta=event.risk_delta,
            effective_risk=f"{event.effective_risk:.0f}",
            is_shadow=event.is_shadow,
            would_block=event.would_block,
            severity=event.severity,
            suspicious_success=event.suspicious_success,
        )

    @property
    def events(self) -> List[SecurityEvent]:
        return list(self._events)

    def export_json(self, path: str):
        with open(path, "w") as f:
            json.dump([asdict(e) for e in self._events], f, indent=2)


class SecurityMetrics:
    """Aggregated security metrics for dashboarding and alerting."""

    def __init__(self, event_log: SecurityEventLog):
        self.log = event_log

    def compute(self) -> Dict[str, Any]:
        events = self.log.events
        if not events:
            return {"total_events": 0}

        total = len(events)
        blocked = sum(1 for e in events if e.action == "BLOCKED" and not e.is_shadow)
        shadow_blocked = sum(1 for e in events if e.would_block and e.is_shadow)
        suspicious_successes = sum(1 for e in events if e.suspicious_success and e.action == "ALLOWED")
        allowed = total - blocked - shadow_blocked

        # Block rate
        block_rate = (blocked / total) * 100 if total else 0
        shadow_block_rate = (shadow_blocked / total) * 100 if total else 0

        # Weighted severity rate
        severity_weights = {"LOW": 1, "MEDIUM": 3, "HIGH": 7, "CRITICAL": 10}
        total_weight = sum(severity_weights.get(e.severity, 1) for e in events)
        shadow_weight = sum(severity_weights.get(e.severity, 1) for e in events if e.would_block and e.is_shadow)
        weighted_shadow_rate = (shadow_weight / total_weight) * 100 if total_weight else 0
        suspicious_success_rate = (suspicious_successes / total) * 100 if total else 0

        # Top block reasons
        block_reasons = Counter(e.reason for e in events if e.action == "BLOCKED")
        top_reasons = block_reasons.most_common(5)

        # Top blocked tools
        blocked_tools = Counter(e.tool_requested for e in events if e.action == "BLOCKED" and e.tool_requested)
        top_blocked_tools = blocked_tools.most_common(5)

        # Actor risk distribution
        actor_risks = defaultdict(float)
        for e in events:
            actor_risks[e.actor_id] = max(actor_risks[e.actor_id], e.actor_risk)
        flagged_actors = {a: r for a, r in actor_risks.items() if r >= 100}

        # Origin distribution
        origin_counts = Counter(e.origin for e in events)

        # Events per hour (last hour)
        now = time.time()
        recent = sum(1 for e in events if now - e.timestamp < 3600)

        return {
            "total_events": total,
            "blocked": blocked,
            "shadow_blocked": shadow_blocked,
            "suspicious_successes": suspicious_successes,
            "allowed": allowed,
            "block_rate_pct": round(block_rate, 2),
            "shadow_block_rate_pct": round(shadow_block_rate, 2),
            "weighted_shadow_rate_pct": round(weighted_shadow_rate, 2),
            "suspicious_success_rate_pct": round(suspicious_success_rate, 2),
            "events_last_hour": recent,
            "top_block_reasons": top_reasons,
            "top_blocked_tools": top_blocked_tools,
            "flagged_actors": flagged_actors,
            "origin_distribution": dict(origin_counts),
        }

    def print_dashboard(self):
        m = self.compute()
        print("\n📊 Security Telemetry Dashboard")
        print("=" * 50)
        print(f"  Total events:     {m['total_events']}")
        print(f"  Blocked:          {m['blocked']} ({m['block_rate_pct']}%)")
        print(f"  Shadow Blocked:   {m['shadow_blocked']} ({m['shadow_block_rate_pct']}%)")
        print(f"  Allowed:          {m['allowed']}")
        print(f"  Events (1h):      {m['events_last_hour']}")
        print()
        print("  🔴 Top Block Reasons:")
        for reason, count in m.get('top_block_reasons', []):
            print(f"     {count}x — {reason[:60]}")
        print()
        print("  🛠️  Top Blocked Tools:")
        for tool, count in m.get('top_blocked_tools', []):
            print(f"     {count}x — {tool}")
        print()
        if m.get('flagged_actors'):
            print("  ⚠️  Flagged Actors:")
            for actor, risk in m['flagged_actors'].items():
                print(f"     {actor}: risk={risk:.0f}")
        else:
            print("  ✅ No flagged actors")
        print()
        print(f"  📡 Origins: {m.get('origin_distribution', {})}")
        print("=" * 50)


class SecurityObserver:
    """
    Singleton observer that hooks into CognitiveSecurityLayer decisions.
    Usage: create once, pass to CSL, all events get logged automatically.
    """

    def __init__(self):
        self.event_log = SecurityEventLog()
        self.metrics = SecurityMetrics(self.event_log)

    def on_tool_decision(self, tool_name: str, allowed: bool, reason: str,
                         context: Dict, state, origin: str = "unknown",
                         actor_id: str = "anonymous", is_shadow: bool = False,
                         would_block: bool = False, severity: str = "LOW",
                         suspicious_success: bool = False):
        self.event_log.record(SecurityEvent(
            timestamp=time.time(),
            event_type="tool_governor",
            origin=origin,
            actor_id=actor_id,
            tool_requested=tool_name,
            action="ALLOWED" if allowed else "BLOCKED",
            reason=reason,
            risk_delta=0 if allowed and not would_block else 30,
            session_risk=state.risk_score if state else 0,
            actor_risk=state.registry.get_risk(actor_id) if state else 0,
            effective_risk=state.effective_risk() if state else 0,
            payload_snippet="",
            is_shadow=is_shadow,
            would_block=would_block,
            severity=severity,
            suspicious_success=suspicious_success,
        ))

    def on_output_decision(self, allowed: bool, reason: str,
                           context: Dict, state, response_snippet: str = "",
                           origin: str = "unknown", actor_id: str = "anonymous",
                           is_shadow: bool = False, would_block: bool = False,
                           severity: str = "LOW", suspicious_success: bool = False):
        self.event_log.record(SecurityEvent(
            timestamp=time.time(),
            event_type="output_guard",
            origin=origin,
            actor_id=actor_id,
            tool_requested=None,
            action="ALLOWED" if allowed else "BLOCKED",
            reason=reason,
            risk_delta=0 if allowed and not would_block else 40,
            session_risk=state.risk_score if state else 0,
            actor_risk=state.registry.get_risk(actor_id) if state else 0,
            effective_risk=state.effective_risk() if state else 0,
            payload_snippet=response_snippet[:100],
            is_shadow=is_shadow,
            would_block=would_block,
            severity=severity,
            suspicious_success=suspicious_success,
        ))

    def on_hallucination(self, tool_name: str, actor_id: str = "anonymous",
                         is_shadow: bool = False, would_block: bool = True):
        self.event_log.record(SecurityEvent(
            timestamp=time.time(),
            event_type="hallucination",
            origin="llm",
            actor_id=actor_id,
            tool_requested=tool_name,
            action="ALLOWED" if is_shadow else "BLOCKED",
            reason=f"Tool '{tool_name}' does not exist",
            risk_delta=40,
            session_risk=0,
            actor_risk=0,
            effective_risk=0,
            payload_snippet="",
            is_shadow=is_shadow,
            would_block=would_block,
            severity="MEDIUM",
            suspicious_success=False,
        ))
