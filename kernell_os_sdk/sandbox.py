"""
Kernell OS SDK — Containerized Execution & Resource Management
══════════════════════════════════════════════════════════════
Handles the secure, isolated execution of the agent on Windows/Linux
using Docker. Allows assigning specific resources (RAM, CPU, Disk)
and managing permission boundaries.

SECURITY:
  - Never mounts root filesystem (/) — only user-approved directories
  - Enforces disk quotas
  - Drops all capabilities by default
  - Prevents privilege escalation
"""
import subprocess
import logging
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger("kernell.sandbox")

# Docker image digest for supply chain verification
AGENT_BASE_IMAGE_TAG = "kernell/agent-base:latest"  # Para referencia humana
# ↓ Usar este en producción (inmutable, no puede ser reemplazado silenciosamente)
AGENT_BASE_IMAGE = "kernell/agent-base@sha256:REEMPLAZAR_CON_DIGEST_REAL_DE_SHA256"

def _verify_image_integrity() -> bool:
    """
    Verifica que la imagen Docker local coincide con el digest esperado.
    Llama esto antes de start() para detectar imágenes comprometidas.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{index .RepoDigests 0}}", AGENT_BASE_IMAGE_TAG],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            logger.error("No se pudo inspeccionar la imagen Docker")
            return False

        actual_ref = result.stdout.strip()
        expected_sha = AGENT_BASE_IMAGE.split("@sha256:")[-1]
        if expected_sha not in actual_ref:
            logger.critical(
                f"⚠️  ALERTA DE SEGURIDAD: Digest de imagen no coincide!\n"
                f"   Esperado: ...{expected_sha[:16]}\n"
                f"   Actual: {actual_ref[:80]}"
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout verificando imagen Docker")
        return False


class ResourceLimits(BaseModel):
    ram_mb: int = Field(default=2048, ge=256, le=65536)
    cpu_cores: float = Field(default=1.0, ge=0.25, le=32.0)
    disk_gb: int = Field(default=10, ge=1, le=500)
    runtime: str = Field(default="runsc", description="Container runtime (e.g., 'runsc' for gVisor or 'runc')")


class AgentPermissions(BaseModel):
    network_access: bool = True
    file_system_read: bool = True
    file_system_write: bool = False
    execute_commands: bool = False
    browser_control: bool = False
    gui_automation: bool = False  # Full computer use

    # Allowed filesystem paths (never mount / wholesale)
    allowed_paths: List[str] = Field(default_factory=lambda: [
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
    ])


class Sandbox:
    """Manages the Docker container for the agent."""
    def __init__(self, agent_id: str, limits: ResourceLimits, permissions: AgentPermissions):
        self.agent_id = agent_id
        self.limits = limits
        self.permissions = permissions
        self.container_name = f"kernell_agent_{self.agent_id}"

    def _build_docker_args(self) -> List[str]:
        args = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "--runtime", self.limits.runtime,
            "--memory", f"{self.limits.ram_mb}m",
            "--memory-swap", f"{self.limits.ram_mb}m",  # No swap — prevent OOM abuse
            "--cpus", str(self.limits.cpu_cores),
            "--pids-limit", "64",  # Prevent fork bombs
            # Disk quota enforcement
            "--storage-opt", f"size={self.limits.disk_gb}g",
            # Security hardening
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",
            "--read-only",
            # tmpfs for writable areas inside the container
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
            "--tmpfs", "/var/tmp:rw,noexec,nosuid,size=128m",
        ]

        # Network isolation
        if not self.permissions.network_access:
            args.extend(["--network", "none"])

        # Mount ONLY allowed paths (NEVER mount /)
        if self.permissions.file_system_read or self.permissions.file_system_write:
            mode = "rw" if self.permissions.file_system_write else "ro"
            for host_path in self.permissions.allowed_paths:
                resolved_path = Path(host_path).resolve()
                host_path_str = str(resolved_path)
                
                # Strict safety check against path traversal and sensitive mounts
                forbidden_prefixes = ["/etc", "/root", "/var", "/sys", "/dev", "/boot", "/usr/lib"]
                if host_path_str == "/" or host_path_str == "" or any(host_path_str.startswith(p) for p in forbidden_prefixes) or "docker.sock" in host_path_str:
                    logger.error(f"SECURITY: Refused to mount sensitive host path: {host_path_str}")
                    continue
                
                container_path = f"/workspace/{resolved_path.name}"
                args.extend(["-v", f"{host_path_str}:{container_path}:{mode}"])

        # For full computer use, we need X11/Wayland socket access
        if self.permissions.gui_automation:
            import os
            display = os.environ.get("DISPLAY", ":0")
            args.extend([
                "-e", f"DISPLAY={display}",
                "-v", "/tmp/.X11-unix:/tmp/.X11-unix:ro"
            ])

        args.append(AGENT_BASE_IMAGE)
        return args

    def start(self) -> bool:
        """Deploys the agent in the container."""
        logger.info(f"Deploying agent {self.agent_id} in isolated sandbox...")
        try:
            # Remove existing container if present
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                capture_output=True, timeout=10
            )

            if not _verify_image_integrity():
                logger.error("Sandbox deployment aborted due to image integrity verification failure.")
                return False

            cmd = self._build_docker_args()
            logger.info(f"Docker command: {' '.join(cmd[:6])}...")  # Log truncated for security
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info(f"Sandbox started successfully: {result.stdout.strip()[:12]}...")
                return True
            else:
                logger.error(f"Failed to start sandbox: {result.stderr}")
                return False
        except FileNotFoundError:
            logger.error("Docker is not installed or not running.")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Docker command timed out.")
            return False

    def stop(self):
        """Terminates the sandbox gracefully."""
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True, timeout=30
            )
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True, timeout=10
            )
            logger.info(f"Sandbox {self.container_name} stopped and removed.")
        except subprocess.TimeoutExpired:
            # Force kill
            subprocess.run(
                ["docker", "kill", self.container_name],
                capture_output=True
            )
            logger.warning(f"Sandbox {self.container_name} force-killed.")
