from typing import Dict, Any
from .base import BaseAdapter
import structlog

logger = structlog.get_logger("kernell.adapters.m2m")

class M2MAdapter(BaseAdapter):
    """
    Adapter that handles M2M economic delegation.
    If the agent lacks a capability or prefers to outsource, it uses this adapter
    to pay another agent to execute the task.
    """
    capability_name = "peer_delegation"

    def __init__(self, agent):
        self.agent = agent

    def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("m2m_delegating", task=task[:50])
        
        # 1. Estimate cost
        estimated_cost = 2.0
        
        # 2. Check balance
        if self.agent.wallet.balance < estimated_cost:
            return {"status": "error", "reason": "insufficient_kern"}
            
        # 3. Pay Peer (Mock Escrow execution)
        success = self.agent.pay_peer(target="MarketplaceNode", amount=estimated_cost, task=task)
        
        if success:
            return {
                "status": "success", 
                "output": "Delegated successfully to peer.",
                "cost": estimated_cost
            }
        else:
            return {"status": "error", "reason": "escrow_failed"}
