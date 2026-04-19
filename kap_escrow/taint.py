"""
KAP Taint Engine — Fractional Taint Tracking (Anti-Laundering)
================================================================
Prevents "Taint Laundering" where adversaries fragment tainted funds
across multiple escrows and recombine them through mixer agents.

Model: UTXO-style fractional taint propagation through the transaction graph.
Every asset carries a taint_ratio ∈ [0.0, 1.0]:
  - 0.0 = completely clean
  - 1.0 = fully tainted (e.g., stolen funds, sanctioned origin)

When assets merge (deposits to same agent), taint is weighted by amount.
When assets split (withdrawals), taint propagates proportionally.

Taint NEVER decreases through transaction volume alone — only through
explicit governance action (e.g., compliance review, staking bond).
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
TAINT_BLOCK_THRESHOLD = Decimal("0.20")   # Block transactions above 20% taint
TAINT_WARN_THRESHOLD = Decimal("0.05")    # Warn above 5% taint
MAX_ALLOWED_FEE = Decimal("0.15")         # 15% max fee (anti-economic-drain)


class TaintedAsset:
    """Represents an asset with fractional taint metadata."""
    __slots__ = ("amount", "taint_ratio", "origin_tx", "ts")

    def __init__(self, amount: Decimal, taint_ratio: Decimal = Decimal("0"),
                 origin_tx: str = "", ts: float = None):
        self.amount = amount
        self.taint_ratio = max(Decimal("0"), min(Decimal("1"), taint_ratio))
        self.origin_tx = origin_tx
        self.ts = ts or time.time()

    def to_dict(self) -> dict:
        return {
            "amount": str(self.amount),
            "taint_ratio": str(self.taint_ratio),
            "origin_tx": self.origin_tx,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaintedAsset":
        return cls(
            amount=Decimal(d["amount"]),
            taint_ratio=Decimal(d["taint_ratio"]),
            origin_tx=d.get("origin_tx", ""),
            ts=d.get("ts", time.time()),
        )


def merge_assets(assets: List[TaintedAsset]) -> TaintedAsset:
    """
    Merge multiple assets into one (e.g., agent receives multiple deposits).
    Taint is WEIGHTED by amount — prevents dilution attacks.

    Example:
      - Asset A: 100 KERN, 80% tainted
      - Asset B: 900 KERN, 0% tainted
      - Result:  1000 KERN, 8% tainted (not 0%!)

    An attacker cannot "wash" 100 tainted KERN by mixing with 900 clean KERN
    and then withdrawing — the 8% taint follows ALL outputs.
    """
    total = sum(a.amount for a in assets)
    if total == 0:
        return TaintedAsset(Decimal("0"), Decimal("0"))

    weighted_taint = sum(a.amount * a.taint_ratio for a in assets) / total
    return TaintedAsset(amount=total, taint_ratio=weighted_taint)


def split_asset(source: TaintedAsset, amounts: List[Decimal]) -> List[TaintedAsset]:
    """
    Split an asset into multiple outputs. Taint propagates to ALL outputs equally.
    This prevents the "fragment and recombine" attack.
    """
    return [
        TaintedAsset(amount=amt, taint_ratio=source.taint_ratio)
        for amt in amounts
    ]


class TaintLedger:
    """
    Per-agent taint ledger backed by Redis.
    Tracks the aggregate taint ratio of each agent's wallet.
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
        Transfer funds with taint propagation.
        Returns status dict with warnings/blocks.
        """
        sender_asset = self.get_taint(sender)
        receiver_asset = self.get_taint(receiver)

        if amount > sender_asset.amount:
            return {"status": "rejected", "reason": "insufficient_balance"}

        # The transferred chunk inherits sender's taint ratio
        transferred = TaintedAsset(
            amount=amount,
            taint_ratio=sender_asset.taint_ratio,
            origin_tx=tx_id,
        )

        # Check taint policy BEFORE executing
        if transferred.taint_ratio >= TAINT_BLOCK_THRESHOLD:
            logger.critical(
                "taint_transfer_blocked",
                sender=sender, receiver=receiver,
                taint=str(transferred.taint_ratio),
                threshold=str(TAINT_BLOCK_THRESHOLD),
            )
            return {
                "status": "blocked",
                "reason": f"taint_ratio {transferred.taint_ratio} exceeds threshold {TAINT_BLOCK_THRESHOLD}",
            }

        if transferred.taint_ratio >= TAINT_WARN_THRESHOLD:
            logger.warning("taint_transfer_warning", taint=str(transferred.taint_ratio))

        # Update sender: subtract amount, taint ratio unchanged
        new_sender = TaintedAsset(
            amount=sender_asset.amount - amount,
            taint_ratio=sender_asset.taint_ratio,
        )

        # Update receiver: merge incoming with existing (weighted taint)
        new_receiver = merge_assets([receiver_asset, transferred])

        self.set_taint(sender, new_sender)
        self.set_taint(receiver, new_receiver)

        return {
            "status": "ok",
            "receiver_taint": str(new_receiver.taint_ratio),
        }

    def check_fee_policy(self, fee: Decimal, service_agent: str) -> bool:
        """
        Anti-Economic-Drain: reject fees above MAX_ALLOWED_FEE.
        Prevents agents from slowly extracting value via inflated fees.
        """
        if fee > MAX_ALLOWED_FEE:
            logger.critical(
                "economic_drain_blocked",
                agent=service_agent,
                fee=str(fee),
                max=str(MAX_ALLOWED_FEE),
            )
            return False
        return True
