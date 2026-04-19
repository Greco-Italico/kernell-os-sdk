"""
KAP Taint Engine — Mass Conservation Taint Tracking (Anti-Sybil/Laundering)
=============================================================================
Prevents "Iterative Dilution" and Sybil laundering attacks.

Model: Conservation of Tainted Mass
Every asset tracks EXACTLY how much of it is clean and how much is tainted:
  - clean_amount: Decimal
  - tainted_amount: Decimal

When assets merge, mass is simply added:
  total_clean = a.clean + b.clean
  total_tainted = a.tainted + b.tainted

When splitting, amounts are divided proportionally to the ratio.
CRITICAL: Tainted mass is NEVER destroyed or diluted out of existence.
"""
from __future__ import annotations

import json
import time
import logging
from decimal import Decimal, getcontext
from typing import Dict, Optional, List

getcontext().prec = 28

logger = logging.getLogger("KAP_TAINT")

# Policy thresholds
TAINT_RATIO_BLOCK_THRESHOLD = Decimal("0.20")   # Block if ratio > 20%
MAX_PATH_FEE = Decimal("0.15")                  # Anti-Sybil Fee chaining limit
MIN_TRANSFER_SIZE = Decimal("0.0001")           # Anti-Dust attack precision exploit


class TaintedAsset:
    """Represents an asset with conserved taint mass."""
    __slots__ = ("clean_amount", "tainted_amount", "origin_tx", "ts")

    def __init__(self, clean_amount: Decimal, tainted_amount: Decimal = Decimal("0"),
                 origin_tx: str = "", ts: float = None):
        self.clean_amount = clean_amount
        self.tainted_amount = tainted_amount
        self.origin_tx = origin_tx
        self.ts = ts or time.time()

    @property
    def total_amount(self) -> Decimal:
        return self.clean_amount + self.tainted_amount

    @property
    def taint_ratio(self) -> Decimal:
        if self.total_amount == 0:
            return Decimal("0")
        return self.tainted_amount / self.total_amount

    def to_dict(self) -> dict:
        return {
            "clean_amount": str(self.clean_amount),
            "tainted_amount": str(self.tainted_amount),
            "origin_tx": self.origin_tx,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaintedAsset":
        return cls(
            clean_amount=Decimal(d["clean_amount"]),
            tainted_amount=Decimal(d["tainted_amount"]),
            origin_tx=d.get("origin_tx", ""),
            ts=d.get("ts", time.time()),
        )


def merge_assets(assets: List[TaintedAsset]) -> TaintedAsset:
    """
    Merge multiple assets into one. Mass is conserved.
    Attacker cannot 'dilute' 100 tainted by adding 900 clean — 
    the 100 tainted mass remains perfectly intact.
    """
    clean = sum(a.clean_amount for a in assets)
    tainted = sum(a.tainted_amount for a in assets)
    return TaintedAsset(clean_amount=clean, tainted_amount=tainted)


def split_asset(source: TaintedAsset, amount_to_extract: Decimal) -> TaintedAsset:
    """
    Extract a sub-amount from an asset. The extracted amount draws proportionally
    from the clean and tainted mass.
    """
    if amount_to_extract > source.total_amount:
        raise ValueError("Cannot extract more than total amount")
    
    if source.total_amount == 0:
        return TaintedAsset(Decimal("0"), Decimal("0"))

    ratio = source.taint_ratio
    extracted_tainted = amount_to_extract * ratio
    extracted_clean = amount_to_extract - extracted_tainted

    return TaintedAsset(clean_amount=extracted_clean, tainted_amount=extracted_tainted)


class TaintLedger:
    """
    Per-agent taint ledger backed by Redis.
    Tracks conserved taint mass.
    """

    def __init__(self, redis_client, prefix: str = "kap:taint"):
        self.r = redis_client
        self.prefix = prefix

    def _key(self, agent_id: str) -> str:
        return f"{self.prefix}:{agent_id}"

    def get_taint(self, agent_id: str) -> TaintedAsset:
        raw = self.r.get(self._key(agent_id))
        if not raw:
            return TaintedAsset(Decimal("0"), Decimal("0"))
        return TaintedAsset.from_dict(json.loads(raw))

    def set_taint(self, agent_id: str, asset: TaintedAsset) -> None:
        self.r.set(self._key(agent_id), json.dumps(asset.to_dict()))

    def transfer_with_taint(
        self, sender: str, receiver: str, amount: Decimal, tx_id: str = ""
    ) -> Dict[str, str]:
        """
        Transfer funds with Mass Conservation.
        """
        # Anti-Dust Attack (Precision exploit rounding mitigation)
        if amount < MIN_TRANSFER_SIZE:
            return {"status": "rejected", "reason": f"amount below min transfer size {MIN_TRANSFER_SIZE}"}

        sender_asset = self.get_taint(sender)
        receiver_asset = self.get_taint(receiver)

        if amount > sender_asset.total_amount:
            return {"status": "rejected", "reason": "insufficient_balance"}

        # Extract proportional mass
        transferred = split_asset(sender_asset, amount)

        # Anti-Sybil Path Enforcement (block if transferred chunk itself exceeds threshold)
        if transferred.taint_ratio >= TAINT_RATIO_BLOCK_THRESHOLD:
            logger.critical(
                f"taint_transfer_blocked sender={sender} receiver={receiver} "
                f"taint_ratio={transferred.taint_ratio} tainted_mass={transferred.tainted_amount}"
            )
            return {
                "status": "blocked",
                "reason": "taint threshold exceeded",
            }

        # Update sender: subtract exact mass extracted
        new_sender = TaintedAsset(
            clean_amount=sender_asset.clean_amount - transferred.clean_amount,
            tainted_amount=sender_asset.tainted_amount - transferred.tainted_amount
        )

        # Update receiver: merge incoming with existing (conserves all mass)
        new_receiver = merge_assets([receiver_asset, transferred])

        self.set_taint(sender, new_sender)
        self.set_taint(receiver, new_receiver)

        return {
            "status": "ok",
            "receiver_taint_ratio": str(new_receiver.taint_ratio),
        }

    def check_path_fee(self, accumulated_fee: Decimal) -> bool:
        """
        Anti-Sybil Fee Extraction: reject paths where accumulated fee > MAX_PATH_FEE.
        """
        if accumulated_fee > MAX_PATH_FEE:
            logger.critical("sybil_fee_chain_blocked", accumulated=str(accumulated_fee))
            return False
        return True

    def verify_no_clean_gain(self, agent_id: str, before: TaintedAsset, after: TaintedAsset) -> bool:
        """
        Anti-Taint-Swap Invariant (Attack: Taint Immobilization -> Clean Proxy Extraction).
        Nadie puede aumentar su clean_amount neto si aporta tainted.
        Si la masa tainted de un agente DISMINUYE (es decir, la movió a un escrow o la usó),
        su masa limpia NO PUEDE AUMENTAR en la misma transacción lógica.
        
        Returns False si la regla es violada.
        """
        tainted_delta = after.tainted_amount - before.tainted_amount
        clean_delta = after.clean_amount - before.clean_amount
        
        # Si el agente se deshizo de tainted (delta < 0), y de alguna forma
        # terminó con MAS dinero limpio (delta > 0), es un Taint Swap exploit.
        if tainted_delta < 0 and clean_delta > 0:
            logger.critical(
                f"taint_swap_exploit_blocked agent={agent_id} "
                f"clean_gain={clean_delta} tainted_loss={tainted_delta}"
            )
            return False
        return True
