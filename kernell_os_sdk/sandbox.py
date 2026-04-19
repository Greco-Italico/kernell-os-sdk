"""
Kernell OS SDK — Containerized Execution & Resource Management
══════════════════════════════════════════════════════════════
Handles the secure, isolated execution of the agent on Windows/Linux
using Docker. Allows assigning specific resources (RAM, CPU, Disk)
and managing permission boundaries.
"""
import subprocess
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("kernell.sandbox")

class ResourceLimits(BaseModel):
    ram_mb: int = 2048
    cpu_cores: float = 1.0
    disk_gb: int = 10

class AgentPermissions(BaseModel):
    network_access: bool = True
    file_system_read: bool = True
    file_system_write: bool = False
    execute_commands: bool = False
    browser_control: bool = False
    gui_automation: bool = False  # Full computer use

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
            "--memory", f"{self.limits.ram_mb}m",
            "--cpus", str(self.limits.cpu_cores),
        ]
        
        # Apply permissions via Docker flags
        if not self.permissions.network_access:
            args.extend(["--network", "none"])
            
        if self.permissions.file_system_read and not self.permissions.file_system_write:
            args.extend(["-v", "/:/host_fs:ro"])
        elif self.permissions.file_system_write:
            args.extend(["-v", "/:/host_fs:rw"])
            
        # For full computer use, we need X11/Wayland socket access
        if self.permissions.gui_automation:
            args.extend([
                "-e", "DISPLAY=$DISPLAY",
                "-v", "/tmp/.X11-unix:/tmp/.X11-unix:rw"
            ])
            
        args.append("kernell/agent-base:latest")
        return args

    def start(self) -> bool:
        """Deploys the agent in the container."""
        logger.info(f"Deploying agent {self.agent_id} in isolated sandbox...")
        try:
            # Check if exists
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True)
            
            cmd = self._build_docker_args()
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Sandbox started successfully: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"Failed to start sandbox: {result.stderr}")
                return False
        except FileNotFoundError:
            logger.error("Docker is not installed or not running.")
            return False

    def stop(self):
        """Terminates the sandbox."""
        subprocess.run(["docker", "stop", self.container_name], capture_output=True)
        subprocess.run(["docker", "rm", self.container_name], capture_output=True)
