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

try:
    from kap_escrow.kap_core import RustTransactionWAL
except ImportError as e:
    raise RuntimeError("HFT Error: kap_core Rust module not found. You must compile the bindings with Maturin.") from e

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

_verify_binary()

class TransactionWAL:
    """Zero-Copy Write-Ahead Log delegated to Rust via PyO3.
    Wrapped with a threading lock to prevent Rust RefCell 'Already borrowed' panics 
    under heavy multi-threading.
    Added Cryptographic Hash Chain for Tamper-Evident Ledger.
    """

    def __init__(self, path: str = "./kap_escrow_wal.bin"):
        self.path = path
        self._rust_wal = RustTransactionWAL(path)
        self._lock = threading.Lock()
        self._last_hash = "0" * 64

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        import json
        with self._lock:
            # Hash Chaining
            payload = json.dumps(record, sort_keys=True)
            new_hash = hashlib.sha256((payload + self._last_hash).encode()).hexdigest()
            record["prev_hash"] = self._last_hash
            record["hash"] = new_hash
            self._last_hash = new_hash
            return self._rust_wal.append(record)

    def verify_integrity(self) -> Tuple[bool, int]:
        return self._rust_wal.verify_integrity()

    def replay(self, since_seq: int = 0) -> List[Dict[str, Any]]:
        return self._rust_wal.replay(since_seq)
