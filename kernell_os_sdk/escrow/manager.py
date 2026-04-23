from enum import Enum
from dataclasses import dataclass, field
import uuid
from typing import Optional
import time

class EscrowState(Enum):
    CREATED = "CREATED"
    LOCKED = "LOCKED"
    RELEASED = "RELEASED"
    DISPUTED = "DISPUTED"
    REFUNDED = "REFUNDED"

@dataclass
class EscrowContract:
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    buyer_id: str = ""
    seller_id: str = ""
    amount_kern: float = 0.0
    state: EscrowState = EscrowState.CREATED
    timeout_timestamp: float = 0.0
    arbitrator_id: Optional[str] = None
    multisig_signatures: list = field(default_factory=list)

class EscrowManager:
    """Gestión segura de pagos, disputas y timeouts"""
    
    def __init__(self):
        self._contracts: dict[str, EscrowContract] = {}

    def create_escrow(self, buyer_id: str, seller_id: str, amount: float, timeout_hours: int = 24) -> str:
        timeout_ts = time.time() + (timeout_hours * 3600)
        contract = EscrowContract(
            buyer_id=buyer_id, 
            seller_id=seller_id, 
            amount_kern=amount,
            state=EscrowState.LOCKED,
            timeout_timestamp=timeout_ts
        )
        self._contracts[contract.contract_id] = contract
        return contract.contract_id

    def release_funds(self, contract_id: str, caller_id: str) -> bool:
        contract = self._contracts.get(contract_id)
        if not contract:
            return False
        
        # Solo el buyer o el árbitro pueden liberar fondos
        if caller_id == contract.buyer_id or caller_id == contract.arbitrator_id:
            contract.state = EscrowState.RELEASED
            return True
        return False

    def open_dispute(self, contract_id: str, caller_id: str) -> bool:
        contract = self._contracts.get(contract_id)
        if not contract:
            return False
            
        if caller_id in (contract.buyer_id, contract.seller_id):
            contract.state = EscrowState.DISPUTED
            return True
        return False
