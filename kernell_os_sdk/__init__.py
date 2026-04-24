"""Kernell OS SDK — Open-Source Agent Framework"""

from importlib.metadata import version as _pkg_version, PackageNotFoundError
try:
    __version__ = _pkg_version("kernell-os-sdk")
except PackageNotFoundError:
    __version__ = "dev"

__author__ = "Kernell OS"

from kernell_os_sdk.agent import Agent
from kernell_os_sdk.memory import Memory
from kernell_os_sdk.cluster import ClusterNode, ClusterDiscovery, BountyBoard, Bounty, MemorySync
from kernell_os_sdk.wallet import Wallet
from kernell_os_sdk.config import KernellConfig
from kernell_os_sdk.sandbox import ResourceLimits, AgentPermissions
from kernell_os_sdk.identity import AgentPassport, SecurityError
from kernell_os_sdk.gui import AgentGUI
from kernell_os_sdk.dashboard import CommandCenter
from kernell_os_sdk.telemetry import HardwareFingerprint
from kernell_os_sdk.budget import TokenBudget
from kernell_os_sdk.resilience import CircuitBreaker, CircuitOpenError
from kernell_os_sdk.tracing import TraceContext, get_current_trace_id
from kernell_os_sdk.health import SLOMonitor, HealthStatus
from kernell_os_sdk.skill_loader import SkillLoader, SkillConfig
from kernell_os_sdk.token_estimator import estimate_tokens
from kernell_os_sdk.persister import ToolResultPersister
from kernell_os_sdk.llm import (
    BaseLLMProvider, OllamaProvider, AnthropicProvider,
    OpenAIProvider, LLMRouter, ComplexityLevel, LLMMessage
)
from kernell_os_sdk.delegation import SubAgentManager, TaskQueue

__all__ = [
    "Agent", "Memory", "ClusterNode", "ClusterDiscovery", "BountyBoard", "Bounty", "MemorySync",
    "Wallet", "KernellConfig",
    "ResourceLimits", "AgentPermissions", "AgentPassport",
    "AgentGUI", "CommandCenter",
    "HardwareFingerprint", "SecurityError",
    "TokenBudget", "CircuitBreaker", "CircuitOpenError",
    "TraceContext", "get_current_trace_id",
    "SLOMonitor", "HealthStatus",
    "SkillLoader", "SkillConfig",
    "estimate_tokens", "ToolResultPersister",
    "BaseLLMProvider", "OllamaProvider", "AnthropicProvider",
    "OpenAIProvider", "LLMRouter", "ComplexityLevel", "LLMMessage",
    "SubAgentManager", "TaskQueue",
    "__version__",
]
