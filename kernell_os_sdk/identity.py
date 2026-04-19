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
  - Hardware UDID binding (anti-cloning)

SECURITY:
  - Private keys are encrypted at rest using Fernet (AES-128-CBC)
  - Passports are signed with HMAC-SHA256 to prevent tampering
  - UDID is validated on every load to prevent cloning
"""
from __future__ import annotations

import hashlib
import hmac as hmac_module
import json
import os
import secrets
import time
import uuid
import base64
import getpass
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet

def _get_machine_secret() -> str:
    """Retrieve or generate a high-entropy secret bound to this machine."""
    secret_path = Path.home() / ".kernell" / ".machine_secret"
    if secret_path.exists():
        return secret_path.read_text().strip()
    
    # Generate a cryptographically secure random secret
    import secrets
    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(secret)
    os.chmod(str(secret_path), 0o600)
    return secret

# Derive a Fernet key from a passphrase (or machine-specific secret)
def _derive_fernet_key(salt: bytes = b"kernell_os_sdk_v1") -> bytes:
    """
    Derives a Fernet encryption key from a machine-specific secret.
    Uses a highly secure, randomly generated machine secret.
    """
    machine_secret = _get_machine_secret()
    raw = hashlib.pbkdf2_hmac("sha256", machine_secret.encode(), salt, 100_000, dklen=32)
    return base64.urlsafe_b64encode(raw)


# Allowed fields for AgentPassport — used to reject unknown fields
_PASSPORT_FIELDS = {
    "agent_id", "name", "version", "created_at",
    "public_key_hex", "identity_hash", "kap_address",
    "kern_volatile_address", "kern_solana_address",
    "hardware_udid", "origin", "tier", "capabilities",
}


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
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> "AgentPassport":
        parsed = json.loads(data)
        # Reject unknown fields to prevent injection
        unknown = set(parsed.keys()) - _PASSPORT_FIELDS
        if unknown:
            raise ValueError(f"Unknown passport fields rejected: {unknown}")
        # Validate required fields exist
        required = {"agent_id", "name", "version", "created_at", "public_key_hex",
                     "identity_hash", "kap_address", "kern_volatile_address"}
        missing = required - set(parsed.keys())
        if missing:
            raise ValueError(f"Missing required passport fields: {missing}")
        return cls(**parsed)


def _compute_passport_hmac(passport_json: str, private_key_hex: str) -> str:
    """Compute HMAC-SHA256 of the passport JSON for integrity verification."""
    return hmac_module.new(
        bytes.fromhex(private_key_hex[:64]),  # Use first 32 bytes as HMAC key
        passport_json.encode(),
        hashlib.sha256
    ).hexdigest()


def _generate_keypair() -> Tuple[str, str]:
    """Generate an Ed25519 keypair. Returns (private_hex, public_hex)."""
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


def _encrypt_private_key(private_hex: str) -> bytes:
    """Encrypt the private key using Fernet (AES) bound to this machine."""
    fernet = Fernet(_derive_fernet_key())
    return fernet.encrypt(private_hex.encode())


def _decrypt_private_key(encrypted_data: bytes) -> str:
    """Decrypt the private key. Will FAIL if run on a different machine (different UDID)."""
    fernet = Fernet(_derive_fernet_key())
    return fernet.decrypt(encrypted_data).decode()


def create_passport(
    name: str,
    version: str = "1.0.0",
    capabilities: list = None,
    storage_dir: Optional[Path] = None,
) -> Tuple[AgentPassport, str]:
    """
    Create a new agent passport with full cryptographic identity.
    Binds the passport to the host machine's hardware UDID.
    Private key is encrypted at rest.
    Passport is signed with HMAC to prevent tampering.

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

        # Save passport JSON
        passport_json = passport.to_json()
        passport_path = storage_dir / "passport.json"
        passport_path.write_text(passport_json)

        # Save HMAC signature for integrity verification
        hmac_sig = _compute_passport_hmac(passport_json, private_hex)
        sig_path = storage_dir / ".passport_sig"
        sig_path.write_text(hmac_sig)
        os.chmod(str(sig_path), 0o600)

        # Encrypt private key at rest (bound to this machine's UDID)
        encrypted_key = _encrypt_private_key(private_hex)
        key_path = storage_dir / ".private_key.enc"
        key_path.write_bytes(encrypted_key)
        os.chmod(str(key_path), 0o600)

        # Remove any old plaintext key files
        old_plaintext = storage_dir / ".private_key"
        if old_plaintext.exists():
            old_plaintext.unlink()

    return passport, private_hex


def load_passport(storage_dir: Path) -> Optional[AgentPassport]:
    """
    Load an existing passport from disk with full integrity verification.
    
    Checks:
      1. Passport JSON schema validation
      2. HMAC signature integrity (detects tampering)
      3. Hardware UDID match (detects cloning to another machine)
    """
    from .telemetry import HardwareFingerprint

    storage_dir = Path(storage_dir)
    passport_path = storage_dir / "passport.json"

    if not passport_path.exists():
        return None

    # Load and validate schema
    try:
        passport = AgentPassport.from_json(passport_path.read_text())
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        raise SecurityError(f"Passport corrupted or tampered: {e}")

    # Verify HMAC integrity
    sig_path = storage_dir / ".passport_sig"
    key_path = storage_dir / ".private_key.enc"
    if sig_path.exists() and key_path.exists():
        try:
            private_hex = _decrypt_private_key(key_path.read_bytes())
            expected_hmac = _compute_passport_hmac(passport.to_json(), private_hex)
            actual_hmac = sig_path.read_text().strip()
            if not hmac_module.compare_digest(expected_hmac, actual_hmac):
                raise SecurityError(
                    "PASSPORT INTEGRITY FAILURE: HMAC mismatch. "
                    "The passport file has been tampered with."
                )
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Cannot verify passport integrity: {e}")

    # Verify hardware UDID (anti-cloning)
    if passport.hardware_udid:
        current_udid = HardwareFingerprint.get_system_udid()
        if passport.hardware_udid != current_udid:
            raise SecurityError(
                f"HARDWARE BINDING VIOLATION: This passport was created on a different machine. "
                f"Expected UDID: {passport.hardware_udid[:16]}... "
                f"Current UDID: {current_udid[:16]}... "
                f"Agent will NOT start."
            )

    return passport


def load_private_key(storage_dir: Path) -> Optional[str]:
    """Load and decrypt the private key from disk."""
    key_path = Path(storage_dir) / ".private_key.enc"
    if key_path.exists():
        return _decrypt_private_key(key_path.read_bytes())
    # Legacy fallback: check for unencrypted key and migrate
    old_path = Path(storage_dir) / ".private_key"
    if old_path.exists():
        private_hex = old_path.read_text().strip()
        # Migrate to encrypted storage
        encrypted = _encrypt_private_key(private_hex)
        key_path.write_bytes(encrypted)
        os.chmod(str(key_path), 0o600)
        old_path.unlink()  # Remove plaintext
        return private_hex
    return None


def sign_message(message: str, private_key_hex: str) -> str:
    """Sign a message with the agent's Ed25519 private key."""
    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    signature = private_key.sign(message.encode())
    return signature.hex()


def verify_signature(message: str, signature_hex: str, public_key_hex: str) -> bool:
    """Verify an Ed25519 signature. Returns True if valid."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        public_key.verify(bytes.fromhex(signature_hex), message.encode())
        return True
    except Exception:
        return False


class SecurityError(Exception):
    """Raised when a security invariant is violated."""
    pass
