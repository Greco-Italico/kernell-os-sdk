"""
KAP Merkle Tree — SHA-256 Batch Anchoring
==========================================
Prefix-protected (\\x00 leaves, \\x01 nodes) to prevent
second-preimage attacks (Bitcoin CVE-2012-2459 class).

Security patches applied:
  • KAP-02a: Node hash preserves positional ordering (L‖R, never sorted)
  • KAP-02b: Odd-layer padding uses a dedicated NULL sentinel
             instead of duplicating the last leaf (prevents
             [A,B,C] == [A,B,C,C] collision)
"""
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


# Sentinel used for odd-leaf padding — a deterministic, non-colliding value
_NULL_SENTINEL = hashlib.sha256(b"\x02NULL_PADDING_KAP").hexdigest()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _leaf_hash(item: str) -> str:
    return _hash(b"\x00" + item.encode("utf-8"))

def _node_hash(left: str, right: str) -> str:
    """
    KAP-02a FIX: Always concatenate left‖right in positional order.
    Never sort lexicographically — sorting destroys the structural
    integrity of inclusion proofs and allows subtree reordering.
    """
    combined = left + right
    return _hash(b"\x01" + combined.encode("utf-8"))


class MerkleTree:
    """Binary Merkle tree with O(log N) inclusion proofs."""

    def __init__(self):
        self.leaves: List[str] = []
        self.layers: List[List[str]] = []
        self.root: Optional[str] = None
        self._leaf_index: Dict[str, int] = {}

    def build(self, items: List[str]) -> str:
        if not items:
            self.root = _hash(b"")
            self.leaves = []
            self.layers = [[self.root]]
            return self.root
        self.leaves = [_leaf_hash(item) for item in items]
        self._leaf_index = {_leaf_hash(item): i for i, item in enumerate(items)}
        self.layers = [self.leaves[:]]
        current = self.leaves[:]
        while len(current) > 1:
            next_layer = []
            for i in range(0, len(current), 2):
                left = current[i]
                # KAP-02b FIX: Use NULL sentinel instead of duplicating
                # the last node. This prevents [A,B,C] from producing
                # the same root as [A,B,C,C].
                right = current[i + 1] if i + 1 < len(current) else _NULL_SENTINEL
                next_layer.append(_node_hash(left, right))
            self.layers.append(next_layer)
            current = next_layer
        self.root = current[0]
        return self.root

    def get_proof(self, item: str) -> List[Tuple[str, str]]:
        leaf = _leaf_hash(item)
        if leaf not in self._leaf_index:
            raise ValueError(f"Item not in tree: {item[:64]}...")
        idx = self._leaf_index[leaf]
        proof: List[Tuple[str, str]] = []
        for layer in self.layers[:-1]:
            if idx % 2 == 0:
                sibling_idx = idx + 1
                if sibling_idx < len(layer):
                    proof.append((layer[sibling_idx], "R"))
                else:
                    # Odd leaf: sibling is the NULL sentinel
                    proof.append((_NULL_SENTINEL, "R"))
            else:
                proof.append((layer[idx - 1], "L"))
            idx //= 2
        return proof

    @staticmethod
    def verify_proof(item: str, proof: List[Tuple[str, str]], root: str) -> bool:
        current = _leaf_hash(item)
        for sibling_hash, direction in proof:
            if direction == "L":
                current = _node_hash(sibling_hash, current)
            else:
                current = _node_hash(current, sibling_hash)
        return current == root

    def get_summary(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "leaf_count": len(self.leaves),
            "depth": len(self.layers),
            "algorithm": "SHA-256",
            "prefix_protection": True,
            "null_sentinel": True,
            "positional_ordering": True,
        }


def build_tx_merkle(transactions: List[Dict[str, Any]]) -> Tuple[str, MerkleTree]:
    items = [json.dumps(tx, sort_keys=True, separators=(",", ":")) for tx in transactions]
    tree = MerkleTree()
    root = tree.build(items)
    return root, tree
