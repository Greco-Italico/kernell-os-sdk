"""
KAP Signing — Asymmetric Ed25519 Transaction Authentication
============================================================
Non-repudiation layer. Uses deterministic JSON serialization
signed with Ed25519 (cryptography) to allow global verification of records
without sharing the private key.
"""
import base64
import json
import logging
from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger("KAP_SIGNING")


def sign_tx(record: Dict[str, Any], private_key: bytes = b"") -> Dict[str, Any]:
    """
    Sign a transaction record using Ed25519.
    Injects "sig" and "sig_pk" (public key in base64).
    """
    if not private_key:
        raise ValueError(
            "private_key is required. Set KERNELL_TX_PRIVATE_KEY in your environment."
        )

    # Clean output-only fields
    clean = {k: v for k, v in record.items() if k not in ("sig", "sig_pk", "wal_status")}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")

    signer = Ed25519PrivateKey.from_private_bytes(private_key[:32])
    sig = signer.sign(canonical)

    record["sig_pk"] = base64.b64encode(
        signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("utf-8")
    record["sig"] = base64.b64encode(sig).decode("utf-8")
    return record


def verify_tx(record: Dict[str, Any], public_keyring: set[bytes] = None) -> bool:
    """
    Verify Ed25519 signature. If public_keyring is provided,
    the transaction's public key (sig_pk) must be authorized in the ring.
    """
    sig = record.get("sig", "")
    sig_pk = record.get("sig_pk", "")

    if not sig or not sig_pk:
        return False

    try:
        pk_bytes = base64.b64decode(sig_pk)
        if public_keyring and pk_bytes not in public_keyring:
            logger.warning("Signature uses an unauthorized key: %s", sig_pk)
            return False

        clean = {k: v for k, v in record.items() if k not in ("sig", "sig_pk", "wal_status")}
        canonical = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")

        Ed25519PublicKey.from_public_bytes(pk_bytes).verify(
            base64.b64decode(sig),
            canonical,
        )
        return True
    except (InvalidSignature, ValueError, TypeError) as e:
        logger.debug("Signature validation failed: %s", e)
        return False
