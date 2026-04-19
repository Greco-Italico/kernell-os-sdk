"""
Kernell OS SDK — Risk Engine & Behavioral Monitor
════════════════════════════════════════════════════
Defends against Goal Hijacking, Chained Low-Risk Actions,
and Data Exfiltration via Taint Tracking and Anomaly Detection.
"""
from enum import IntEnum
from typing import Any, Dict, List, Optional
import time
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger("kernell.risk_engine")


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class DataSensitivity(IntEnum):
    PUBLIC = 1
    INTERNAL = 2
    SECRET = 3


class ActionTag(BaseModel):
    command: str
    timestamp: float
    bytes_processed: int = 0
    sensitivity: DataSensitivity = DataSensitivity.PUBLIC


class ExecutionContext(BaseModel):
    """Short-term memory of the agent's execution flow for Taint Tracking."""
    history: List[ActionTag] = Field(default_factory=list)
    total_bytes_read: int = 0
    holds_sensitive_data: bool = False
    
    def record_action(self, tag: ActionTag):
        self.history.append(tag)
        self.total_bytes_read += tag.bytes_processed
        if tag.sensitivity >= DataSensitivity.INTERNAL:
            self.holds_sensitive_data = True
            
        # Keep last 50 actions to avoid memory bloat
        if len(self.history) > 50:
            self.history.pop(0)


class BehaviorMonitor:
    """Detects behavioral drift and chained anomalies."""
    
    def __init__(self, max_requests_per_min: int = 10, max_read_volume_kb: int = 500):
        self.max_requests_per_min = max_requests_per_min
        self.max_read_volume = max_read_volume_kb * 1024

    def detect_anomalies(self, context: ExecutionContext, current_cmd: str) -> List[str]:
        anomalies = []
        now = time.time()
        
        # 1. Rate Limiting Anomaly
        recent_actions = [a for a in context.history if now - a.timestamp < 60]
        if len(recent_actions) >= self.max_requests_per_min:
            anomalies.append(f"Behavior Drift: {len(recent_actions)} requests/min exceeds baseline.")
            
        # 2. Chained Data Volume Anomaly (Slow Exfiltration)
        if context.total_bytes_read > self.max_read_volume:
            anomalies.append(f"Volume Drift: Read {context.total_bytes_read} bytes, exceeding threshold.")
            
        return anomalies


class RiskEngine:
    """
    Evaluates semantic risk dynamically based on action and context (Taint Tracking).
    """
    def __init__(self):
        self.monitor = BehaviorMonitor()

    def evaluate(self, command: str, context: ExecutionContext) -> RiskLevel:
        base_risk = self._get_base_risk(command)
        risk_score = base_risk.value
        
        # Data Flow Control (Taint Tracking)
        # If agent read sensitive data previously, sending it to network is CRITICAL.
        if context.holds_sensitive_data and self._is_egress_command(command):
            logger.warning("risk_data_flow_violation", command=command)
            risk_score += 2  # Escalate immediately
            
        # Behavior Drift Detection
        anomalies = self.monitor.detect_anomalies(context, command)
        if anomalies:
            for anomaly in anomalies:
                logger.warning("risk_anomaly_detected", reason=anomaly)
            risk_score += 1
            
        # Cap at CRITICAL
        final_risk = min(risk_score, RiskLevel.CRITICAL.value)
        return RiskLevel(final_risk)

    def _get_base_risk(self, command: str) -> RiskLevel:
        """Static base risk assessment."""
        if "wallet.transfer" in command or "escrow" in command:
            return RiskLevel.CRITICAL
        if command.startswith("curl ") or command.startswith("wget ") or "git push" in command:
            return RiskLevel.HIGH
        if "cat /" in command or "python" in command:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _is_egress_command(self, command: str) -> bool:
        """Returns True if the command sends data out of the system."""
        egress_cmds = ["curl", "wget", "git push", "scp", "rsync"]
        return any(command.startswith(cmd) for cmd in egress_cmds)
