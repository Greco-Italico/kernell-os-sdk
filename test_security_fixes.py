import os
import sys
from pathlib import Path
import tempfile
import time

sys.path.insert(0, str(Path(__file__).parent))

def test_aes_gcm():
    from kernell_os_sdk.identity import _encrypt_private_key, _decrypt_private_key, SecurityError
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir)
        private_hex = "a" * 64
        
        # Test 1: Each encryption generates a distinct nonce
        c1 = _encrypt_private_key(private_hex, storage)
        c2 = _encrypt_private_key(private_hex, storage)
        assert c1[:12] != c2[:12], "Nonce must be unique"
        assert c1 != c2, "Ciphertexts must be distinct"
        
        # Test 2: Decrypts successfully
        d1 = _decrypt_private_key(c1, storage)
        assert d1 == private_hex, "Decryption failed"
        
        # Test 3: Modifying 1 byte causes exception
        modified = bytearray(c1)
        modified[-1] ^= 0x01
        try:
            _decrypt_private_key(bytes(modified), storage)
            assert False, "Modified ciphertext should raise SecurityError"
        except SecurityError:
            pass
            
        # Test 4: Format is nonce (12) + ciphertext + tag (16)
        # AES-GCM ciphertext length = plaintext length + 16 (tag)
        # Total length = 12 (nonce) + len(plaintext) + 16
        expected_len = 12 + len(private_hex.encode()) + 16
        assert len(c1) == expected_len, f"Expected length {expected_len}, got {len(c1)}"
            
        print("✅ AES-GCM Cryptography tests passed")

def test_sandbox():
    from kernell_os_sdk.runtime.sandbox_validator import validate_code
    
    # Test 1: Bypasses fail
    res1 = validate_code("().__class__")
    assert not res1.valid, "().__class__ should be blocked"
    
    res2 = validate_code("[].__class__.__mro__")
    assert not res2.valid, "[].__class__.__mro__ should be blocked"
    
    res3 = validate_code("getattr(x, '__class__')")
    assert not res3.valid, "getattr should be blocked"
    
    res4 = validate_code("x.__init__()")
    assert res4.valid, "__init__ should be allowed"
    
    print("✅ AST Sandbox tests passed")

def test_execution_gate():
    from kernell_os_sdk.execution_gate import ExecutionGate, ApprovalSignature
    from kernell_os_sdk.risk_engine import RiskLevel
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    
    gate = ExecutionGate(required_signatures=1, timelock_seconds=0)
    
    pk = Ed25519PrivateKey.generate()
    pub_hex = pk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    
    timestamp = time.time()
    command = "rm -rf /"
    payload = f"{command}:{timestamp}"
    valid_sig = pk.sign(payload.encode())
    
    # Mock threading.Event.wait to avoid waiting during test
    import threading
    original_wait = threading.Event.wait
    threading.Event.wait = lambda self, timeout: None
    
    sig1 = ApprovalSignature(signer_id="agent1", signer_role="agent", public_key_hex=pub_hex, signature=valid_sig, timestamp=timestamp)
    sig_oracle = ApprovalSignature(signer_id="oracle1", signer_role="oracle", public_key_hex=pub_hex, signature=valid_sig, timestamp=timestamp)
    assert gate.approve(command, RiskLevel.CRITICAL, [sig1, sig_oracle]), "Valid signatures should be accepted"
    
    # Invalid length
    sig2 = ApprovalSignature(signer_id="agent1", signer_role="agent", public_key_hex=pub_hex, signature=b"x"*63, timestamp=timestamp)
    sig2_oracle = ApprovalSignature(signer_id="oracle1", signer_role="oracle", public_key_hex=pub_hex, signature=b"x"*63, timestamp=timestamp)
    assert not gate.approve(command, RiskLevel.CRITICAL, [sig2, sig2_oracle]), "63 byte signature should be rejected"
    
    sig3 = ApprovalSignature(signer_id="agent1", signer_role="agent", public_key_hex=pub_hex, signature=b"x"*65, timestamp=timestamp)
    sig3_oracle = ApprovalSignature(signer_id="oracle1", signer_role="oracle", public_key_hex=pub_hex, signature=b"x"*65, timestamp=timestamp)
    assert not gate.approve(command, RiskLevel.CRITICAL, [sig3, sig3_oracle]), "65 byte signature should be rejected"
    
    # Invalid signature
    invalid_sig = b"x" * 64
    sig4 = ApprovalSignature(signer_id="agent1", signer_role="agent", public_key_hex=pub_hex, signature=invalid_sig, timestamp=timestamp)
    sig4_oracle = ApprovalSignature(signer_id="oracle1", signer_role="oracle", public_key_hex=pub_hex, signature=invalid_sig, timestamp=timestamp)
    assert not gate.approve(command, RiskLevel.CRITICAL, [sig4, sig4_oracle]), "Invalid 64 byte signature should be rejected"
    
    threading.Event.wait = original_wait
    print("✅ Ed25519 Signature tests passed")

if __name__ == "__main__":
    test_aes_gcm()
    test_sandbox()
    test_execution_gate()
    print("ALL TESTS PASSED")
