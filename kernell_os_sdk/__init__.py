"""
Kernell OS SDK — Open-Source Agent Framework
═══════════════════════════════════════════════
Build autonomous PC agents with:
  • Zero-trust Sandbox — containerized execution (Windows/Linux)
  • Cryptographic Identity — passports and dual wallets (KERN/SOL)
  • PC Control — permissions, filesystem, and GUI automation
  • Local GUI — built-in control panel with bearer token auth
  • M2M Commerce ($KERN) — agents earn money
  • Shared memory (Cortex) — spend less tokens
  • Hardware binding — passports tied to physical machines

Quick Start:
    from kernell_os_sdk import Agent, ResourceLimits, AgentPermissions

    agent = Agent(
        name="DesktopAssistant",
        limits=ResourceLimits(ram_mb=4096),
        permissions=AgentPermissions(gui_automation=True)
    )

    agent.run()
"""

__version__ = "0.3.0"
__author__ = "Kernell OS"

from kernell_os_sdk.agent import Agent
from kernell_os_sdk.memory import Memory
from kernell_os_sdk.cluster import Cluster
from kernell_os_sdk.wallet import Wallet
from kernell_os_sdk.config import KernellConfig
from kernell_os_sdk.sandbox import ResourceLimits, AgentPermissions
from kernell_os_sdk.identity import AgentPassport, SecurityError
from kernell_os_sdk.gui import AgentGUI
from kernell_os_sdk.telemetry import HardwareFingerprint

__all__ = [
    "Agent",
    "Memory",
    "Cluster",
    "Wallet",
    "KernellConfig",
    "ResourceLimits",
    "AgentPermissions",
    "AgentPassport",
    "AgentGUI",
    "HardwareFingerprint",
    "SecurityError",
    "__version__",
]
