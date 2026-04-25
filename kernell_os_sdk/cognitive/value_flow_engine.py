"""
Kernell OS SDK — Value Flow Engine V2 (High-Concurrency Edition)
═════════════════════════════════════════════════════════════════════
Transitions security from "Global Serial Lock" to "Fine-Grained Optimistic Sharding".
Protects against:
- Lock Amplification & Queue Buildup
- Global Serialization Bottlenecks
"""
from __future__ import annotations

import hashlib
import time
import uuid
import threading
from decimal import Decimal, getcontext
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

getcontext().prec = 28

class ValueFlowViolation(Exception):
    pass

@dataclass(frozen=True)
class StrictAddress:
    public_key_hash: str
    entity_type: str

@dataclass
class SingleUseCapability:
    granted_to: StrictAddress = field(init=True)
    target_address: StrictAddress = field(init=True)
    action: str = field(init=True)
    max_amount: Decimal = field(init=True)
    capability_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)
    expires_at: float = field(default_factory=lambda: time.time() + 60.0)
    
    is_consumed: bool = field(default=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    def verify_and_consume(self, amount: Decimal):
        with self._lock:
            if self.is_consumed:
                raise ValueFlowViolation("Capability Replay Attack: Token already consumed.")
            if time.time() > self.expires_at:
                raise ValueFlowViolation("Capability Expired.")
            if amount > self.max_amount:
                raise ValueFlowViolation(f"Capability Overbreadth: {amount} > {self.max_amount}")
            self.is_consumed = True

@dataclass
class ValueNode:
    node_id: str
    address: StrictAddress
    balance: Decimal
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

@dataclass
class ValueEdge:
    transaction_id: str
    source_node: str
    target_node: str
    amount: Decimal
    previous_hash: str
    timestamp: float = field(default_factory=time.time)
    tx_hash: str = field(init=False)
    
    def __post_init__(self):
        payload = f"{self.transaction_id}|{self.source_node}|{self.target_node}|{self.amount}|{self.previous_hash}"
        self.tx_hash = hashlib.sha256(payload.encode()).hexdigest()

class ValueFlowGraph:
    def __init__(self):
        self.nodes: Dict[str, ValueNode] = {}
        self.edges: List[ValueEdge] = []
        self._graph_structure_lock = threading.Lock() # Solo para añadir nodos o auditar
        self.last_tx_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"
        
        self.provenance: Dict[str, Dict[str, Decimal]] = {}
        self._total_system_value: Decimal = Decimal('0')
        self._emergency_freeze: bool = False

    def activate_kill_switch(self):
        with self._graph_structure_lock:
            self._emergency_freeze = True
            
    def deactivate_kill_switch(self):
        with self._graph_structure_lock:
            self._emergency_freeze = False

    def register_node(self, node: ValueNode):
        with self._graph_structure_lock:
            self.nodes[node.node_id] = node
            self.provenance[node.node_id] = {node.node_id: node.balance}
            self._total_system_value += node.balance

    def validate_trajectory(self, source_id: str, target_id: str, amount: Decimal) -> None:
        source_node = self.nodes.get(source_id)
        target_node = self.nodes.get(target_id)
        
        if not source_node or not target_node:
            raise ValueFlowViolation("Unregistered nodes in value flow.")
        if source_node.balance < amount:
            raise ValueFlowViolation("Insufficient balance for flow.")

        source_history = self.provenance.get(source_id, {})
        
        for origin_id, tainted_amount in source_history.items():
            origin_node = self.nodes.get(origin_id)
            if origin_node and origin_node.address.entity_type == 'escrow_pool':
                proportion = tainted_amount / source_node.balance if source_node.balance > Decimal('0') else Decimal('0')
                tainted_transfer = amount * proportion
                
                if target_node.address.entity_type == 'external_vendor' and tainted_transfer > Decimal('0'):
                    raise ValueFlowViolation(
                        f"MULTI-HOP INVARIANT BROKEN: {tainted_transfer} of Escrow taint reaching External."
                    )

    def commit_transfer(self, capability: SingleUseCapability, amount: Decimal) -> str:
        if self._emergency_freeze:
            raise ValueFlowViolation("SYSTEM FROZEN: Emergency Kill Switch is active. No transactions allowed.")
            
        source_id = capability.granted_to.public_key_hash
        target_id = capability.target_address.public_key_hash
        
        if source_id == target_id:
            raise ValueFlowViolation("Self-transfers are not allowed.")
            
        with self._graph_structure_lock:
            if source_id not in self.nodes or target_id not in self.nodes:
                raise ValueFlowViolation("Nodes not registered.")
            node_ids = sorted([source_id, target_id])
            lock1 = self.nodes[node_ids[0]]._lock
            lock2 = self.nodes[node_ids[1]]._lock
            
        with lock1:
            with lock2:
                # Revalidación del Kill Switch (Corte en caliente)
                if self._emergency_freeze:
                    raise ValueFlowViolation("SYSTEM FROZEN: Emergency Kill Switch is active.")
                    
                # 2-Phase Commit inside the dual node lock
                capability.verify_and_consume(amount)
                self.validate_trajectory(source_id, target_id, amount)
                
                source_node = self.nodes[source_id]
                target_node = self.nodes[target_id]
                
                proportion = amount / source_node.balance if source_node.balance > Decimal('0') else Decimal('0')
                
                transfer_provenance = {}
                for origin_id, origin_amount in list(self.provenance.get(source_id, {}).items()):
                    moved = origin_amount * proportion
                    transfer_provenance[origin_id] = moved
                    self.provenance[source_id][origin_id] = max(Decimal('0'), self.provenance[source_id][origin_id] - moved)
                
                for origin_id, moved_amount in transfer_provenance.items():
                    if origin_id not in self.provenance.get(target_id, {}):
                        self.provenance.setdefault(target_id, {})[origin_id] = Decimal('0')
                    self.provenance[target_id][origin_id] += moved_amount
                
                source_node.balance -= amount
                target_node.balance += amount
                
                tx_id = uuid.uuid4().hex
                edge = ValueEdge(tx_id, source_id, target_id, amount, self.last_tx_hash)
                
                # Para la cadena de hashes usamos lock estructural (rápido, no compite con IO)
                with self._graph_structure_lock:
                    self.last_tx_hash = edge.tx_hash
                    self.edges.append(edge)
                
                return tx_id

    def audit_system_value(self):
        # Para auditoría se bloquea todo (usar solo off-peak)
        with self._graph_structure_lock:
            current_total = sum(n.balance for n in self.nodes.values())
            if current_total != self._total_system_value:
                raise ValueFlowViolation("SYSTEMIC ERROR: Value conservation broken.")
