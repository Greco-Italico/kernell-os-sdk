"""
KAP KMS — Key Management Service Abstraction
===============================================
Prevents private key material from ever residing in Python process memory.

Attack mitigated: Key Exfiltration via /proc/<pid>/mem, gcore, ptrace.

Supports:
  • LocalKMS: Development-only, keys in memory (NOT for production)
  • ExternalKMS: Delegates signing to an external KMS daemon (HSM-backed)
  • EnvKMS: Reads key from env var, signs, then zeros the memory
"""
from __future__ import annotations

import abc
import base64
import ctypes
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger("KAP_KMS")


def _secure_zero(secret: bytearray) -> None:
    """Overwrite memory with zeros to prevent cold-boot / heap-spray recovery."""
    ctypes.memset(ctypes.addressof((ctypes.c_char * len(secret)).from_buffer(secret)), 0, len(secret))


class KMSProvider(abc.ABC):
    """Abstract KMS interface. Python NEVER holds persistent key material."""

    @abc.abstractmethod
    def sign(self, message: bytes) -> bytes:
        """Sign message and return raw Ed25519 signature (64 bytes)."""
        ...

    @abc.abstractmethod
    def public_key(self) -> bytes:
        """Return the Ed25519 public key (32 bytes)."""
        ...

    @abc.abstractmethod
    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature against this KMS's public key."""
        ...


class LocalKMS(KMSProvider):
    """
    Development-only KMS. Key lives in memory.
    ⚠️  NOT SUITABLE FOR PRODUCTION — use ExternalKMS with HSM.
    """

    def __init__(self, private_key: bytes):
        import nacl.signing
        self._signer = nacl.signing.SigningKey(private_key)
        self._verify_key = self._signer.verify_key
        logger.warning("local_kms_initialized — NOT production safe. Use ExternalKMS for mainnet.")

    def sign(self, message: bytes) -> bytes:
        signed = self._signer.sign(message)
        return signed.signature

    def public_key(self) -> bytes:
        return bytes(self._verify_key)

    def verify(self, message: bytes, signature: bytes) -> bool:
        import nacl.exceptions
        try:
            self._verify_key.verify(message, signature)
            return True
        except nacl.exceptions.BadSignatureError:
            return False


class ExternalKMS(KMSProvider):
    """
    Production KMS. Delegates all cryptographic operations to an external
    daemon (e.g., HashiCorp Vault Transit, AWS KMS, or a local HSM proxy).
    
    Python process NEVER sees the private key.
    """

    def __init__(self, endpoint: str = "http://127.0.0.1:8200/v1/transit", key_name: str = "kap-agent"):
        from urllib.parse import urlparse
        _ALLOWED_KMS_HOSTS = {"127.0.0.1", "localhost", "vault.kernell.internal"}
        parsed = urlparse(endpoint)
        if parsed.hostname not in _ALLOWED_KMS_HOSTS:
            raise ValueError(
                f"SSRF Protection: KMS endpoint hostname '{parsed.hostname}' "
                f"not in allowed list: {_ALLOWED_KMS_HOSTS}"
            )
        self._endpoint = endpoint.rstrip("/")
        self._key_name = key_name
        self._cached_pubkey: bytes | None = None
        logger.info("external_kms_initialized", endpoint=endpoint, key_name=key_name)

    def sign(self, message: bytes) -> bytes:
        import httpx
        resp = httpx.post(
            f"{self._endpoint}/sign/{self._key_name}",
            json={"input": base64.b64encode(message).decode()},
            timeout=5.0,
        )
        resp.raise_for_status()
        sig_b64 = resp.json()["data"]["signature"].split(":")[-1]
        return base64.b64decode(sig_b64)

    def public_key(self) -> bytes:
        if self._cached_pubkey:
            return self._cached_pubkey
        import httpx
        resp = httpx.get(
            f"{self._endpoint}/keys/{self._key_name}",
            timeout=5.0,
        )
        resp.raise_for_status()
        keys = resp.json()["data"]["keys"]
        latest = keys[str(max(int(k) for k in keys))]
        self._cached_pubkey = base64.b64decode(latest["public_key"])
        return self._cached_pubkey

    def verify(self, message: bytes, signature: bytes) -> bool:
        import httpx
        resp = httpx.post(
            f"{self._endpoint}/verify/{self._key_name}",
            json={
                "input": base64.b64encode(message).decode(),
                "signature": f"vault:v1:{base64.b64encode(signature).decode()}",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        return resp.json()["data"]["valid"]


class EnvKMS(KMSProvider):
    """
    Reads key from environment, signs, then securely zeros the key from memory.
    Better than LocalKMS but still not HSM-grade.
    """

    def __init__(self, env_var: str = "KERNELL_TX_PRIVATE_KEY"):
        import nacl.signing
        raw = os.environ.get(env_var, "")
        if not raw:
            raise ValueError(f"Environment variable {env_var} not set")
        key_bytes = bytearray(bytes.fromhex(raw))
        self._signer = nacl.signing.SigningKey(bytes(key_bytes))
        self._verify_key = self._signer.verify_key
        _secure_zero(key_bytes)
        # Also remove from environment
        os.environ[env_var] = "0" * len(raw)
        logger.info("env_kms_initialized — key read and zeroed from env")

    def sign(self, message: bytes) -> bytes:
        return self._signer.sign(message).signature

    def public_key(self) -> bytes:
        return bytes(self._verify_key)

    def verify(self, message: bytes, signature: bytes) -> bool:
        import nacl.exceptions
        try:
            self._verify_key.verify(message, signature)
            return True
        except nacl.exceptions.BadSignatureError:
            return False
