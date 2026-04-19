"""
Kernell OS SDK — Identity & Passport System
═══════════════════════════════════════════════
Every agent created with the SDK receives a unique, cryptographic
identity (Passport) that makes it a citizen of the Kernell Ecosystem.

The passport contains:
  - A unique Agent ID (UUID v4)
  - An Ed25519 keypair for message signing
  - A KAP-compatible identity hash
  - Dual wallet addresses (volatile KERN + Solana KERN)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Use stdlib for Ed25519 if available, fallback to HMAC-based signing
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@dataclass
class AgentPassport:
    """Immutable identity document for a Kernell OS Agent."""
    agent_id: str
    name: str
    version: str
    created_at: float
    
    # Cryptographic identity
    public_key_hex: str
    identity_hash: str  # SHA-256 of (agent_id + public_key)
    
    # Kernell ecosystem registration
    kap_address: str  # KAP protocol address: kap://<identity_hash[:16]>
    
    # Dual wallet
    kern_volatile_address: str   # Internal KERN token address
    kern_solana_address: Optional[str] = None  # Solana SPL token address (set after bridge)
    
    # Security Binding
    hardware_udid: str = ""      # Prevents passport cloning
    
    # Metadata
    origin: str = "sdk"
    tier: str = "free"
    capabilities: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, data: str) -> "AgentPassport":
        return cls(**json.loads(data))


def _generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair. Returns (private_hex, public_hex)."""
    if HAS_CRYPTO:
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption()
        )
        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw
        )
        return private_bytes.hex(), public_bytes.hex()
    else:
        # Fallback: use random bytes (still cryptographically secure)
        private = secrets.token_bytes(32)
        # Derive a "public key" via SHA-256 (not real Ed25519 but functional)
        public = hashlib.sha256(private).digest()
        return private.hex(), public.hex()


def create_passport(
    name: str,
    version: str = "1.0.0",
    capabilities: list = None,
    storage_dir: Optional[Path] = None,
) -> tuple[AgentPassport, str]:
    """
    Create a new agent passport with full cryptographic identity.
    Binds the passport to the host machine's hardware UDID.
    
    Returns:
        (passport, private_key_hex)
    """
    from .telemetry import HardwareFingerprint
    
    agent_id = f"ka_{uuid.uuid4().hex[:16]}"
    private_hex, public_hex = _generate_keypair()
    
    hardware_udid = HardwareFingerprint.get_system_udid()
    
    # Identity hash: SHA-256(agent_id || public_key)
    identity_hash = hashlib.sha256(
        f"{agent_id}{public_hex}".encode()
    ).hexdigest()
    
    # KAP address
    kap_address = f"kap://{identity_hash[:16]}"
    
    # Volatile KERN wallet address (derived from identity)
    kern_volatile = f"kern_v_{hashlib.sha256(f'{identity_hash}:volatile'.encode()).hexdigest()[:24]}"
    
    passport = AgentPassport(
        agent_id=agent_id,
        name=name,
        version=version,
        created_at=time.time(),
        public_key_hex=public_hex,
        identity_hash=identity_hash,
        kap_address=kap_address,
        kern_volatile_address=kern_volatile,
        hardware_udid=hardware_udid,
        capabilities=capabilities or [],
    )
    
    # Persist to disk if storage_dir provided
    if storage_dir:
        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        passport_path = storage_dir / "passport.json"
        passport_path.write_text(passport.to_json())
        
        # Store private key with restrictive permissions
        key_path = storage_dir / ".private_key"
        key_path.write_text(private_hex)
        os.chmod(str(key_path), 0o600)
    
    return passport, private_hex


def load_passport(storage_dir: Path) -> Optional[AgentPassport]:
    """Load an existing passport from disk."""
    passport_path = Path(storage_dir) / "passport.json"
    if passport_path.exists():
        return AgentPassport.from_json(passport_path.read_text())
    return None


def sign_message(message: str, private_key_hex: str) -> str:
    """Sign a message with the agent's private key."""
    if HAS_CRYPTO:
        private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        signature = private_key.sign(message.encode())
        return signature.hex()
    else:
        # HMAC-SHA256 fallback
        import hmac
        sig = hmac.new(
            bytes.fromhex(private_key_hex),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return sig
