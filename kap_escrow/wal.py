"""
KAP WAL — Crash-Recoverable Transaction Journal
=================================================
Append-only JSONL with chained SHA-256 hashes and fsync durability.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("KAP_WAL")

import hashlib

EXPECTED_KAP_CORE_HASH = "101b2890ba6b8038c89811504e83db84f5fe65a6c669c9b5f157c2d24e323486"

def _verify_binary():
    import os
    # kap_core is in the same directory as this file
    path = os.path.join(os.path.dirname(__file__), "kap_core.abi3.so")
    with open(path, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    if h != EXPECTED_KAP_CORE_HASH:
        raise RuntimeError("Binary tampered: kap_core.abi3.so hash mismatch")

# KOS-022: Verify BEFORE import — tampered binary never gets to execute
_verify_binary()

try:
    from kap_escrow.kap_core import RustTransactionWAL
except ImportError as e:
    raise RuntimeError("HFT Error: kap_core Rust module not found. You must compile the bindings with Maturin.") from e

class TransactionWAL:
    """Zero-Copy Write-Ahead Log delegated to Rust via PyO3.
    
    Security Properties:
      • Cryptographic Hash Chain (tamper-evident)
      • Signed Checkpoints (prevents Shadow Fork — Attack #1)
      • WAL-based Nonce Recovery (prevents replay after Redis loss — Attack #6)
    """

    def __init__(self, path: str = "./kap_escrow_wal.bin", signing_key: bytes = None):
        self.path = path
        self._rust_wal = RustTransactionWAL(path)
        self._lock = threading.Lock()
        self._last_hash = "0" * 64
        self._signing_key = signing_key  # Ed25519 key for checkpoint signing
        self._used_nonces: set = set()   # In-memory nonce cache rebuilt from WAL
        self._seq = 0

        # Attack #6: Rebuild nonce set from existing WAL on startup
        self._rebuild_nonces()

    def _rebuild_nonces(self) -> None:
        """Recover all used nonces from the WAL to survive Redis loss."""
        try:
            records = self._rust_wal.replay(0)
            for r in records:
                tx_id = r.get("tx_id")
                if tx_id:
                    self._used_nonces.add(tx_id)
                # Restore hash chain continuity
                if "hash" in r:
                    self._last_hash = r["hash"]
                self._seq += 1
            if records:
                logger.info(f"WAL recovery: {len(self._used_nonces)} nonces, seq={self._seq}")
        except Exception as e:
            logger.warning(f"WAL replay failed (fresh start): {e}")

    def is_nonce_used(self, nonce: str) -> bool:
        """Check if nonce was already used (WAL-authoritative, survives Redis loss)."""
        return nonce in self._used_nonces

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        import json
        with self._lock:
            # Track nonce
            tx_id = record.get("tx_id")
            if tx_id:
                self._used_nonces.add(tx_id)

            # Hash Chaining
            payload = json.dumps(record, sort_keys=True)
            new_hash = hashlib.sha256((payload + self._last_hash).encode()).hexdigest()
            record["prev_hash"] = self._last_hash
            record["hash"] = new_hash
            self._last_hash = new_hash
            self._seq += 1
            return self._rust_wal.append(record)

    def create_checkpoint(self) -> Dict[str, Any]:
        """
        Attack #1 Mitigation: Create a signed checkpoint of the current WAL state.
        This checkpoint can be anchored externally (blockchain, append-only store)
        to prevent complete WAL rewrite (Shadow Fork).
        """
        import json
        checkpoint = {
            "type": "checkpoint",
            "seq": self._seq,
            "state_hash": self._last_hash,
            "nonce_count": len(self._used_nonces),
            "ts": __import__("time").time(),
        }

        if self._signing_key:
            import nacl.signing
            import base64
            signer = nacl.signing.SigningKey(self._signing_key)
            canonical = json.dumps(checkpoint, sort_keys=True).encode()
            sig = signer.sign(canonical).signature
            checkpoint["sig"] = base64.b64encode(sig).decode()
            checkpoint["sig_pk"] = base64.b64encode(bytes(signer.verify_key)).decode()

        return checkpoint

    @staticmethod
    def verify_checkpoint(checkpoint: Dict[str, Any]) -> bool:
        """Verify a checkpoint signature (used by external auditors)."""
        import json
        import base64
        import nacl.signing
        import nacl.exceptions

        sig = checkpoint.get("sig")
        sig_pk = checkpoint.get("sig_pk")
        if not sig or not sig_pk:
            return False

        clean = {k: v for k, v in checkpoint.items() if k not in ("sig", "sig_pk")}
        canonical = json.dumps(clean, sort_keys=True).encode()
        try:
            vk = nacl.signing.VerifyKey(base64.b64decode(sig_pk))
            vk.verify(canonical, base64.b64decode(sig))
            return True
        except nacl.exceptions.BadSignatureError:
            return False

    def verify_integrity(self) -> Tuple[bool, int]:
        return self._rust_wal.verify_integrity()

    def replay(self, since_seq: int = 0) -> List[Dict[str, Any]]:
        return self._rust_wal.replay(since_seq)

