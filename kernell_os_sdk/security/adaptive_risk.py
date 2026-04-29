"""
Kernell OS SDK — Adaptive Risk Engine v1
═════════════════════════════════════════
Self-evolving security layer that learns from real attack patterns,
adjusts thresholds dynamically, and maintains federated trust scores
between agents.

Components:
  - PatternLearner: extracts attack signatures from blocked events
  - DynamicThresholds: adjusts sensitivity based on observed pressure
  - ReputationNetwork: federated trust scoring between agents
  - AdaptiveRiskEngine: orchestrator that integrates with ActorRiskRegistry

Philosophy: the system gets HARDER to attack over time, not easier.
"""

import time
import math
import json
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger("kernell.security.adaptive")


# ── Campaign Detector ────────────────────────────────────────────────────────

class CampaignDetector:
    """
    Identifies if multiple actors are coordinating attacks by sharing
    the same attack patterns (Sybil / Campaign detection).
    """
    def __init__(self, campaign_threshold: int = 3):
        self.actor_patterns = defaultdict(set)
        self.pattern_actors = defaultdict(set)
        self.campaign_threshold = campaign_threshold
        self.active_campaigns = []

    def record_event(self, actor_id: str, pattern_key: str):
        self.actor_patterns[actor_id].add(pattern_key)
        self.pattern_actors[pattern_key].add(actor_id)

    def detect(self):
        campaigns = []
        for pattern, actors in self.pattern_actors.items():
            if len(actors) >= self.campaign_threshold:
                campaigns.append({
                    "id": f"camp_{hash(pattern) % 10000:04x}",
                    "pattern": pattern,
                    "actors": list(actors),
                    "confidence": min(1.0, len(actors) * 0.3),
                    "status": "active"
                })
        self.active_campaigns = campaigns
        return campaigns


# ── Pattern Learner ──────────────────────────────────────────────────────────

@dataclass
class LearnedPattern:
    """An attack pattern extracted from observed blocked events."""
    regex: str
    source: str         # "tool_governor", "output_guard", "input_guard"
    confidence: float   # 0.0–1.0, increases with more observations
    first_seen: float
    last_seen: float
    hit_count: int = 1
    status: str = "VALIDATING"  # CANDIDATE -> VALIDATING -> PROMOTED -> REJECTED

    def decay(self, rate: float = 0.01):
        """Patterns that stop appearing lose confidence over time."""
        if self.status == "PROMOTED":
            return # Promoted patterns don't decay automatically
        age_hours = (time.time() - self.last_seen) / 3600
        self.confidence *= max(0.1, 1.0 - (rate * age_hours))


class PatternLearner:
    """
    Extracts recurring attack patterns from blocked event payloads.
    When a pattern appears N+ times across different actors, it becomes
    a 'learned pattern' that can be added to the detection engine.
    """

    def __init__(self, promotion_threshold: int = 3):
        self._candidates: Dict[str, dict] = {}  # normalized_snippet → metadata
        self._learned: List[LearnedPattern] = []
        self._promotion_threshold = promotion_threshold

    def observe(self, payload: str, event_type: str, actor_id: str):
        """Feed a blocked payload to the learner."""
        # Extract potential attack fragments
        fragments = self._extract_fragments(payload)

        for frag in fragments:
            key = frag.lower().strip()
            if len(key) < 5:
                continue

            if key not in self._candidates:
                self._candidates[key] = {
                    "fragment": frag,
                    "actors": set(),
                    "event_type": event_type,
                    "count": 0,
                    "first_seen": time.time(),
                }

            self._candidates[key]["actors"].add(actor_id)
            self._candidates[key]["count"] += 1

            # Record in CampaignDetector (will be handled by orchestrator, but we emit the event conceptually)
            # We just flag it as a candidate here
            
            # Promote to learned pattern if seen from multiple actors
            if (self._candidates[key]["count"] >= self._promotion_threshold
                    and len(self._candidates[key]["actors"]) >= 2):
                self._promote(key)
        return [frag.lower().strip() for frag in fragments if len(frag.lower().strip()) >= 5]

    def _extract_fragments(self, payload: str) -> List[str]:
        """Extract potentially meaningful attack fragments from payload."""
        fragments = []

        # Command-like patterns
        cmd_patterns = re.findall(r'(?:ejecuta|run|cat|ls|grep|find|env)\s+\S+', payload.lower())
        fragments.extend(cmd_patterns)

        # Path-like patterns
        path_patterns = re.findall(r'/[a-zA-Z0-9_./-]{3,}', payload)
        fragments.extend(path_patterns)

        # Key=value patterns (potential credential probing)
        kv_patterns = re.findall(r'[A-Z_]{2,}=[^\s]+', payload)
        fragments.extend(kv_patterns)

        # Quoted strings (potential injection)
        quoted = re.findall(r'"([^"]{5,})"', payload)
        fragments.extend(quoted)

        return fragments

    def _validate_pattern(self, key: str, safe_dataset: List[str] = None) -> bool:
        if not safe_dataset:
            return True # Fallback if no validation data
        false_hits = 0
        for task in safe_dataset:
            if re.search(re.escape(key), task.lower()):
                false_hits += 1
        fp_rate = false_hits / len(safe_dataset)
        return fp_rate < 0.05

    def _promote(self, key: str, safe_dataset: List[str] = None):
        """Promote a candidate to a learned pattern."""
        candidate = self._candidates[key]

        # Don't re-promote
        if any(lp.regex == re.escape(key) for lp in self._learned):
            return

        status = "PROMOTED" if self._validate_pattern(key, safe_dataset) else "REJECTED"

        pattern = LearnedPattern(
            regex=re.escape(key),
            source=candidate["event_type"],
            confidence=min(1.0, candidate["count"] / 10.0),
            first_seen=candidate["first_seen"],
            last_seen=time.time(),
            hit_count=candidate["count"],
            status=status
        )
        self._learned.append(pattern)
        logger.info(f"pattern_{status.lower()}",
                     pattern=key[:50],
                     confidence=f"{pattern.confidence:.2f}",
                     actors=len(candidate["actors"]))

    def check(self, text: str) -> Optional[LearnedPattern]:
        """Check if text matches any learned pattern."""
        text_lower = text.lower()
        for pattern in self._learned:
            if pattern.status == "PROMOTED" or (pattern.status == "VALIDATING" and pattern.confidence > 0.6):
                if re.search(pattern.regex, text_lower):
                    pattern.hit_count += 1
                    pattern.last_seen = time.time()
                    pattern.confidence = min(1.0, pattern.confidence + 0.05)
                    return pattern
        return None

    @property
    def learned_patterns(self) -> List[LearnedPattern]:
        return list(self._learned)

    def decay_all(self):
        """Age out stale patterns."""
        for p in self._learned:
            p.decay()
        self._learned = [p for p in self._learned if p.confidence > 0.1]


# ── Dynamic Thresholds ───────────────────────────────────────────────────────

class BayesianThresholdTuner:
    """
    Adjusts risk thresholds based on Bayesian probability of an actual attack,
    rather than just raw event volume. Prevents over-reaction and blindness.
    """

    def __init__(self):
        self.observed_attacks = 0
        self.total_events = 0

    def update(self, severity: str):
        self.total_events += 1
        if severity in ["CRITICAL", "HIGH"]:
            self.observed_attacks += 1

    @property
    def attack_probability(self) -> float:
        # Simple Laplace smoothing
        return (self.observed_attacks + 1) / (self.total_events + 2)

    @property
    def session_max_risk(self) -> int:
        p = self.attack_probability
        if p > 0.2:
            return 80  # Tighten
        elif p < 0.05:
            return 120 # Relax
        return 100

    @property
    def actor_flag_threshold(self) -> float:
        p = self.attack_probability
        if p > 0.2:
            return 120.0
        elif p < 0.05:
            return 180.0
        return 150.0

    def status(self) -> Dict:
        return {
            "attack_prob": round(self.attack_probability, 3),
            "session_max": self.session_max_risk,
            "actor_flag": self.actor_flag_threshold,
            "total_events": self.total_events,
            "observed_attacks": self.observed_attacks
        }


# ── Reputation Network ──────────────────────────────────────────────────────

@dataclass
class AgentReputation:
    agent_id: str
    trust_score: float = 50.0   # 0–100, starts neutral
    interactions: int = 0
    blocks: int = 0
    last_interaction: float = 0.0

    @property
    def block_rate(self) -> float:
        return self.blocks / max(1, self.interactions)

    def update(self, was_blocked: bool):
        self.interactions += 1
        self.last_interaction = time.time()
        if was_blocked:
            self.blocks += 1
            # Trust decays faster for blocks
            self.trust_score = max(0, self.trust_score - 5.0)
        else:
            # Trust grows slowly for clean interactions
            self.trust_score = min(100, self.trust_score + 0.5)


class ReputationNetwork:
    """
    Federated trust scoring between agents.
    Agents that repeatedly trigger security events lose trust.
    Low-trust agents face stricter scrutiny.
    """

    def __init__(self):
        self._agents: Dict[str, AgentReputation] = {}

    def get_or_create(self, agent_id: str) -> AgentReputation:
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentReputation(agent_id=agent_id)
        return self._agents[agent_id]

    def record_interaction(self, agent_id: str, was_blocked: bool):
        rep = self.get_or_create(agent_id)
        rep.update(was_blocked)

    def trust_modifier(self, agent_id: str) -> float:
        """
        Returns a risk multiplier based on agent trust.
        Low trust → higher risk multiplier (1.0–2.0)
        High trust → lower multiplier (0.8–1.0)
        """
        rep = self.get_or_create(agent_id)
        if rep.trust_score >= 80:
            return 0.8  # Trusted agent, slightly relaxed
        elif rep.trust_score >= 50:
            return 1.0  # Neutral
        elif rep.trust_score >= 20:
            return 1.5  # Suspicious
        else:
            return 2.0  # Hostile

    def flagged_agents(self, threshold: float = 20.0) -> List[AgentReputation]:
        return [r for r in self._agents.values() if r.trust_score < threshold]

    def leaderboard(self) -> List[AgentReputation]:
        return sorted(self._agents.values(), key=lambda r: r.trust_score)


# ── Adaptive Risk Engine (Orchestrator) ──────────────────────────────────────

class AdaptiveRiskEngine:
    """
    Orchestrates all adaptive security components.
    Integrates with the existing CognitiveSecurityLayer via hooks.

    Usage:
        engine = AdaptiveRiskEngine()
        # After each CSL decision:
        engine.on_decision(event_type, actor_id, payload, was_blocked, origin)
        # Before each CSL check:
        risk_mod = engine.pre_check(actor_id, origin)
    """

    def __init__(self, safe_dataset: List[str] = None):
        self.learner = PatternLearner(promotion_threshold=3)
        self.campaigns = CampaignDetector()
        self.tuner = BayesianThresholdTuner()
        self.reputation = ReputationNetwork()
        self.safe_dataset = safe_dataset or []
        self._decision_count = 0
        self._started = time.time()

    def pre_check(self, actor_id: str, payload: str, origin: str = "unknown") -> Dict:
        """
        Called BEFORE CSL makes a decision. Returns context modifiers.
        """
        result = {
            "risk_multiplier": 1.0,
            "learned_pattern_match": None,
            "dynamic_session_max": self.tuner.session_max_risk,
            "dynamic_actor_flag": self.tuner.actor_flag_threshold,
        }

        # 1. Check trust modifier from reputation
        if origin == "m2m":
            result["risk_multiplier"] = self.reputation.trust_modifier(actor_id)

        # 2. Check against learned patterns
        match = self.learner.check(payload)
        if match:
            result["learned_pattern_match"] = match.regex[:50]
            result["risk_multiplier"] *= 1.5  # Extra suspicion for learned patterns

        return result

    def on_decision(self, event_type: str, actor_id: str, payload: str,
                    was_blocked: bool, origin: str = "unknown", severity: str = "LOW"):
        """
        Called AFTER each CSL decision. Feeds all adaptive systems.
        """
        self._decision_count += 1

        # Feed reputation network
        if origin == "m2m":
            self.reputation.record_interaction(actor_id, was_blocked)

        self.tuner.update(severity)

        # Feed pattern learner and campaign detector (only blocked events)
        if was_blocked:
            patterns = self.learner.observe(payload, event_type, actor_id)
            for p in patterns:
                self.campaigns.record_event(actor_id, p)
            self.campaigns.detect()

        # Periodic maintenance
        if self._decision_count % 100 == 0:
            self.learner.decay_all()

    def status(self) -> Dict:
        """Full adaptive engine status for dashboarding."""
        return {
            "uptime_hours": round((time.time() - self._started) / 3600, 2),
            "total_decisions": self._decision_count,
            "learned_patterns": len(self.learner.learned_patterns),
            "active_campaigns": len(self.campaigns.active_campaigns),
            "tuner": self.tuner.status(),
            "flagged_agents": [
                {"id": a.agent_id, "trust": a.trust_score, "block_rate": round(a.block_rate, 2)}
                for a in self.reputation.flagged_agents()
            ],
        }

    def print_status(self):
        s = self.status()
        print("\n🧠 Adaptive Risk Engine — Status")
        print("=" * 50)
        print(f"  Uptime:           {s['uptime_hours']}h")
        print(f"  Decisions:        {s['total_decisions']}")
        print(f"  Learned patterns: {s['learned_patterns']}")
        print(f"  Active Campaigns: {s['active_campaigns']}")
        print(f"  Attack Prob:      {s['tuner']['attack_prob']:.2f}")
        print(f"  Session max:      {s['tuner']['session_max']}/100")
        print(f"  Actor flag:       {s['tuner']['actor_flag']}/150")
        if s['flagged_agents']:
            print(f"  ⚠️  Flagged agents:")
            for a in s['flagged_agents']:
                print(f"     {a['id']}: trust={a['trust']:.0f}, block_rate={a['block_rate']:.0%}")
        else:
            print(f"  ✅ No flagged agents")

        if self.learner.learned_patterns:
            print(f"\n  📚 Learned Patterns:")
            for p in self.learner.learned_patterns[:5]:
                print(f"     [{p.confidence:.0%}] {p.regex[:40]}  (hits: {p.hit_count})")
        print("=" * 50)
