"""
KAP Escrow V2 (FinCEN-Grade Taint-Aware Escrow)
=================================================
Implements strict UTXO-based escrow to prevent Escrow Taint Sinks
and Conditional Clean Extraction.

Security Properties:
1. Internal UTXO tracking (no pooling of clean + tainted inside escrow).
2. Execution Contexts for multi-tx atomic settlement.
3. Strict Partial Participation Leak prevention.
"""
from __future__ import annotations

import json
import time
import uuid
from decimal import Decimal
from typing import Dict, List, Set, Optional

from kap_escrow.taint import TaintedAsset, TaintLedger, merge_assets, split_asset


class EscrowUTXO:
    """Internal UTXO tracking for Escrows. Prevents mixing inside the contract."""
    __slots__ = ("id", "owner", "clean", "tainted", "parent_tx")

    def __init__(self, owner: str, clean: Decimal, tainted: Decimal, parent_tx: str):
        self.id = str(uuid.uuid4())
        self.owner = owner
        self.clean = clean
        self.tainted = tainted
        self.parent_tx = parent_tx

    def to_asset(self) -> TaintedAsset:
        return TaintedAsset(self.clean, self.tainted, self.parent_tx)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner": self.owner,
            "clean": str(self.clean),
            "tainted": str(self.tainted),
            "parent_tx": self.parent_tx,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EscrowUTXO":
        inst = cls(d["owner"], Decimal(d["clean"]), Decimal(d["tainted"]), d["parent_tx"])
        inst.id = d["id"]
        return inst


class ExecutionContext:
    """
    Atomic Economic Context for Multi-Hop/Multi-Tx Settlement.
    Tracks global state changes across the entire logical transaction lifecycle.
    """
    def __init__(self, ledger: TaintLedger):
        self.ledger = ledger
        self.participants: Set[str] = set()
        self.initial_state: Dict[str, TaintedAsset] = {}
        self.final_state: Dict[str, TaintedAsset] = {}
        self.tx_chain: List[dict] = []

    def load_participant(self, agent_id: str):
        if agent_id not in self.participants:
            self.participants.add(agent_id)
            self.initial_state[agent_id] = self.ledger.get_taint(agent_id)

    def execute_transfer(self, sender: str, receiver: str, amount: Decimal, tx_id: str):
        self.load_participant(sender)
        self.load_participant(receiver)
        
        # Local logic execution (in memory)
        sender_asset = self.initial_state[sender] if sender not in self.final_state else self.final_state[sender]
        receiver_asset = self.initial_state[receiver] if receiver not in self.final_state else self.final_state[receiver]

        if amount > sender_asset.total_amount:
            raise ValueError(f"Insufficient balance for {sender}")

        transferred = split_asset(sender_asset, amount)
        new_sender = TaintedAsset(
            sender_asset.clean_amount - transferred.clean_amount,
            sender_asset.tainted_amount - transferred.tainted_amount
        )
        new_receiver = merge_assets([receiver_asset, transferred])

        self.final_state[sender] = new_sender
        self.final_state[receiver] = new_receiver
        self.tx_chain.append({"sender": sender, "receiver": receiver, "amount": amount, "tx": tx_id})

    def validate_global_invariants(self) -> bool:
        """
        FinCEN-Grade Rule: "No Deferred Clean Extraction" & "No Partial Participation Leak".
        Si un agente alguna vez tocó tainted en la red, o entró con tainted al contexto,
        NO puede salir con MÁS clean del que entró.
        """
        for agent in self.participants:
            before = self.initial_state[agent]
            after = self.final_state[agent]

            # Vector 4 Fix: Partial Participation Leak
            # Si el agente entró con algo de taint, su masa limpia neta no puede aumentar.
            if before.tainted_amount > 0 and after.clean_amount > before.clean_amount:
                # Excepción: si el origin_tx prueba que fue un fee legítimo limpio.
                # (Para un sistema real, requiere whitelist estricto).
                raise Exception(
                    f"Compliance Violation: Deferred Clean Extraction by {agent}. "
                    f"Clean Before: {before.clean_amount}, After: {after.clean_amount}. "
                    f"Tainted Before: {before.tainted_amount}."
                )
        return True

    def commit(self):
        """Atomic commit of the execution context to the ledger."""
        self.validate_global_invariants()
        for agent in self.participants:
            if agent in self.final_state:
                self.ledger.set_taint(agent, self.final_state[agent])


class FinCenEscrow:
    """Taint-Aware UTXO Escrow."""
    
    def __init__(self, contract_id: str):
        self.contract_id = contract_id
        self.utxos: List[EscrowUTXO] = []
        self.is_resolved = False

    def deposit(self, sender: str, asset: TaintedAsset, parent_tx: str):
        if self.is_resolved:
            raise ValueError("Escrow already resolved")
        # UTXO mapping explicitly links the owner to the exact mass ratio
        utxo = EscrowUTXO(sender, asset.clean_amount, asset.tainted_amount, parent_tx)
        self.utxos.append(utxo)

    def distribute(self, payouts: Dict[str, Decimal], context: ExecutionContext):
        """
        Distributes funds UTXO by UTXO.
        Outputs preserve the exact lineage and taint of the inputs.
        """
        if self.is_resolved:
            raise ValueError("Escrow already resolved")
            
        total_payout = sum(payouts.values())
        total_available = sum(u.clean + u.tainted for u in self.utxos)
        
        if total_payout > total_available:
            raise ValueError("Payout exceeds available UTXOs")

        # In a real system, you'd match specific UTXOs to specific payouts based on
        # contract logic (e.g. refund goes from exact UTXO to original owner).
        # Here we simulate sequential UTXO draining.
        
        for receiver, amount in payouts.items():
            context.load_participant(receiver)
            receiver_final = context.final_state.get(receiver, context.initial_state[receiver])
            
            remaining = amount
            for utxo in self.utxos:
                if remaining <= 0:
                    break
                utxo_total = utxo.clean + utxo.tainted
                if utxo_total == 0:
                    continue
                    
                take = min(remaining, utxo_total)
                ratio = utxo.tainted / utxo_total
                
                take_tainted = take * ratio
                take_clean = take - take_tainted
                
                transferred = TaintedAsset(take_clean, take_tainted, utxo.parent_tx)
                receiver_final = merge_assets([receiver_final, transferred])
                
                utxo.clean -= take_clean
                utxo.tainted -= take_tainted
                remaining -= take
                
            context.final_state[receiver] = receiver_final
            
        self.is_resolved = True
        context.validate_global_invariants()
