"""
kap_escrow binary integrity verifier.

Run at import time (in __init__.py) or as a standalone script:
    python -m kap_escrow.verify_binary
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

EXPECTED_SHA256 = "101b2890ba6b8038c89811504e83db84f5fe65a6c669c9b5f157c2d24e323486"
BINARY_PATH = Path(__file__).parent / "kap_core.abi3.so"


def verify() -> bool:
    """Returns True if the binary matches the expected checksum."""
    if not BINARY_PATH.exists():
        raise FileNotFoundError(f"Binary not found: {BINARY_PATH}")
    digest = hashlib.sha256(BINARY_PATH.read_bytes()).hexdigest()
    return digest == EXPECTED_SHA256


def verify_or_raise() -> None:
    """Raises RuntimeError if the binary has been tampered with."""
    if not verify():
        raise RuntimeError(
            f"SECURITY: kap_core.abi3.so checksum mismatch. "
            f"Expected {EXPECTED_SHA256}. "
            "The binary may have been tampered with. "
            "Rebuild from source: see kap_escrow/BINARY_INTEGRITY.md"
        )


if __name__ == "__main__":
    try:
        verify_or_raise()
        print(f"✅ Binary integrity OK: {BINARY_PATH.name}")
        sys.exit(0)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
