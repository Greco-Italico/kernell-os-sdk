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
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet

def write_secret_bytes(path: Path, data: bytes) -> None:
    import stat
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    mode = stat.S_IRUSR | stat.S_IWUSR
    fd = os.open(str(path), flags, mode)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)

def _get_machine_secret() -> str:
    """Retrieve or generate a high-entropy secret bound to this machine."""
    secret_path = Path.home() / ".kernell" / ".machine_secret"
    if secret_path.exists():
        return secret_path.read_text().strip()
    
    # Generate a cryptographically secure random secret
    import secrets
    secret = secrets.token_hex(32)
    write_secret_bytes(secret_path, secret.encode())
    return secret

def _get_or_create_salt(storage_dir: Path) -> bytes:
    """
    Obtiene o genera un salt criptográfico único para esta instalación.
    El salt se almacena junto a la clave cifrada y tiene permisos 600.
    """
    salt_path = storage_dir / ".key_salt"
    if salt_path.exists():
        return salt_path.read_bytes()

    # Generar 32 bytes de entropía criptográfica
    salt = os.urandom(32)
    write_secret_bytes(salt_path, salt)
    return salt

# Derive a key from a passphrase (or machine-specific secret)
def _derive_encryption_key(storage_dir: Path) -> bytes:
    """
    Derives an AES-256-GCM encryption key from a machine-specific secret.
    Uses a highly secure, randomly generated machine secret.
    """
    machine_secret = _get_machine_secret()
    salt = _get_or_create_salt(storage_dir)
    return hashlib.pbkdf2_hmac("sha256", machine_secret.encode("utf-8"), salt, 200_000, dklen=32)


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
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"passport_hmac")
    hmac_key = hkdf.derive(bytes.fromhex(private_key_hex))
    return hmac_module.new(
        hmac_key,
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


def _encrypt_private_key(private_hex: str, storage_dir: Path) -> bytes:
    """Encrypt the private key using AES-256-GCM bound to this machine."""
    key = _derive_encryption_key(storage_dir)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, private_hex.encode(), None)
    return nonce + ct


class LegacyEncryptionDetected(Exception):
    pass

def _decrypt_private_key(encrypted_data: bytes, storage_dir: Path) -> str:
    """Decrypt the private key, supporting fallback to Fernet for migration."""
    # Heuristics: Fernet tokens are base64, so they start with "gAAAAA".
    # AES-GCM starts with a binary nonce (12 bytes).
    if encrypted_data.startswith(b"gAAAAA"):
        raise LegacyEncryptionDetected()
        
    key = _derive_encryption_key(storage_dir)
    from cryptography.exceptions import InvalidTag
    try:
        aesgcm = AESGCM(key)
        nonce = encrypted_data[:12]
        ct = encrypted_data[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except InvalidTag:
        raise SecurityError("Failed to decrypt private key: Invalid tag or modified ciphertext")


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
        write_secret_bytes(sig_path, hmac_sig.encode())

        # Encrypt private key at rest (bound to this machine's UDID)
        encrypted_key = _encrypt_private_key(private_hex, storage_dir)
        key_path = storage_dir / ".private_key.enc"
        write_secret_bytes(key_path, encrypted_key)

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
            private_hex = _decrypt_private_key(key_path.read_bytes(), storage_dir)
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
        data = key_path.read_bytes()
        try:
            return _decrypt_private_key(data, Path(storage_dir))
        except LegacyEncryptionDetected:
            # Migrate Fernet to AES-GCM
            machine_secret = _get_machine_secret()
            salt = _get_or_create_salt(Path(storage_dir))
            raw = hashlib.pbkdf2_hmac("sha256", machine_secret.encode("utf-8"), salt, 200_000, dklen=32)
            fernet_key = base64.urlsafe_b64encode(raw)
            fernet = Fernet(fernet_key)
            private_hex = fernet.decrypt(data).decode()
            
            # Re-encrypt and save with AES-GCM
            encrypted = _encrypt_private_key(private_hex, Path(storage_dir))
            write_secret_bytes(key_path, encrypted)
            return private_hex
    # Legacy fallback: check for unencrypted key and migrate
    old_path = Path(storage_dir) / ".private_key"
    if old_path.exists():
        private_hex = old_path.read_text().strip()
        # Migrate to encrypted storage
        encrypted = _encrypt_private_key(private_hex, Path(storage_dir))
        write_secret_bytes(key_path, encrypted)
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


# ── Attack #5 Mitigation: Immutable Agent Identity Registry ─────────

_LUA_REGISTER_IDENTITY = """
local reg_key = KEYS[1]
if redis.call('EXISTS', reg_key) == 1 then return 0 end
redis.call('SET', reg_key, ARGV[1])
return 1
"""


class IdentityRegistry:
    """
    Immutable Agent Identity Registry backed by Redis.
    Prevents Identity Forgery: UUID → PublicKey is WRITE-ONCE (atomic Lua).
    
    Attack scenario mitigated:
      - Attacker generates keypair K2
      - Claims to be agent_id "alice" (registered with K1)
      - Signs with K2
      - verify_agent("alice", msg, sig_K2) → FALSE (K2 ≠ K1)
    """

    def __init__(self, redis_client, prefix: str = "kernell:identity"):
        self.r = redis_client
        self.prefix = prefix
        self._sha_register = self.r.script_load(_LUA_REGISTER_IDENTITY)

    def _reg_key(self, agent_id: str) -> str:
        return f"{self.prefix}:{agent_id}"

    def register(self, agent_id: str, public_key_hex: str, metadata: dict = None) -> bool:
        """Register agent identity. WRITE-ONCE: binding can NEVER be changed."""
        if len(public_key_hex) != 64:
            raise ValueError("Public key hex must be exactly 64 chars (32 bytes Ed25519)")

        payload = json.dumps({
            "public_key_hex": public_key_hex,
            "registered_at": time.time(),
            "metadata": metadata or {},
        })
        result = self.r.evalsha(self._sha_register, 1, self._reg_key(agent_id), payload)
        return result == 1

    def lookup(self, agent_id: str) -> Optional[dict]:
        raw = self.r.get(self._reg_key(agent_id))
        if not raw:
            return None
        return json.loads(raw)

    def verify_agent(self, agent_id: str, message: str, signature_hex: str) -> bool:
        """Verify message was signed by the REGISTERED owner of agent_id."""
        entry = self.lookup(agent_id)
        if not entry:
            return False
        return verify_signature(message, signature_hex, entry["public_key_hex"])

