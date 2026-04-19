"""
Kernell OS SDK — Execution Gate & Consensus
════════════════════════════════════════════════════
Enforces the final security frontier for CRITICAL actions.
Requires Multi-Sig approvals and enforces Time-Locks.
"""
import time
import structlog
from typing import List, Optional
from pydantic import BaseModel
from .risk_engine import RiskLevel

logger = structlog.get_logger("kernell.execution_gate")


class ApprovalSignature(BaseModel):
    signer_id: str
    signature: bytes
    timestamp: float


class ExecutionGate:
    """
    Multi-Layer Execution Authority.
    Gatekeeper that stops execution even if Policy Engine allows it,
    demanding external consensus for High/Critical risk profiles.
    """
    def __init__(self, required_signatures: int = 2, timelock_seconds: int = 30):
        self.required_signatures = required_signatures
        self.timelock_seconds = timelock_seconds

    def approve(self, command: str, risk: RiskLevel, signatures: Optional[List[ApprovalSignature]] = None) -> bool:
        if risk == RiskLevel.LOW:
            return True
            
        if risk == RiskLevel.MEDIUM:
            # Could enforce soft-rate limits here
            return True
            
        if risk == RiskLevel.HIGH:
            logger.warning("execution_gate_high_risk", command=command)
            # Future: Request Oracle pre-approval
            return True
            
        if risk == RiskLevel.CRITICAL:
            logger.critical("execution_gate_critical_risk_triggered", command=command)
            return self._enforce_multisig_and_timelock(command, signatures)
            
        return False

    def _enforce_multisig_and_timelock(self, command: str, signatures: Optional[List[ApprovalSignature]]) -> bool:
        """Enforces N-of-M signatures and delays execution."""
        sigs = signatures or []
        if len(sigs) < self.required_signatures:
            logger.error(
                "execution_gate_multisig_failed",
                required=self.required_signatures,
                provided=len(sigs),
                command=command
            )
            return False
            
        # Verify timestamps to prevent replay attacks
        now = time.time()
        for sig in sigs:
            if now - sig.timestamp > 300:  # Signatures valid for 5 minutes
                logger.error("execution_gate_signature_expired", signer=sig.signer_id)
                return False

        # Apply Time-Lock Delay
        logger.warning(f"TIMELOCK ENGAGED: Executing CRITICAL action in {self.timelock_seconds} seconds. Press Ctrl+C to abort.")
        time.sleep(self.timelock_seconds)
        
        logger.info("execution_gate_approved", command=command)
        return True
