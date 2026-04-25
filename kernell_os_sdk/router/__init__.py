"""
Kernell OS SDK — Intelligent Router Package
═════════════════════════════════════════════
3-Layer Token Economy Engine for maximum cost reduction
in agentic AI workloads.

Architecture:
  Layer 0: Hardware Profiler (install-time)
  Layer 1: Fine-tuned Classifier-Decomposer (indispensable)
  Layer 2: Local inference (Nano → Small → Medium → Large)
  Layer 2.5: Cheap API inference (DeepSeek, Groq, Flash)
  Layer 3: Premium API (Claude, GPT-5, Gemini Pro — last resort)

Anti-waste components:
  - SemanticCache: Skip repeated work entirely
  - RollingSummarizer: Compress context between steps (kills O(n²))
  - SelfVerifier: Validate before escalating (prevents premature spend)
  - DecomposerTrainingCollector: Auto-calibrate with implicit feedback

Observability:
  - RouterMetricsCollector: Full Prometheus-compatible metrics
  - CostEstimator: Pre-execution cost simulation
"""
from .types import (
    SubTask,
    ExecutionResult,
    RouterStats,
    DifficultyLevel,
    ModelTier,
    TaskDomain,
)
from .model_registry import (
    ModelRegistry,
    LocalModelSpec,
    HardwareTierConfig,
    DEFAULT_CATALOG,
)
from .decomposer import (
    TaskDecomposer,
    DecomposerTrainingCollector,
    DECOMPOSER_SYSTEM_PROMPT,
)
from .summarizer import RollingSummarizer
from .verifier import SelfVerifier, VerificationResult
from .intelligent_router import IntelligentRouter
from .metrics import RouterMetricsCollector, API_COST_TABLE
from .estimator import CostEstimator

__all__ = [
    # Core types
    "SubTask",
    "ExecutionResult",
    "RouterStats",
    "DifficultyLevel",
    "ModelTier",
    "TaskDomain",
    # Model registry
    "ModelRegistry",
    "LocalModelSpec",
    "HardwareTierConfig",
    "DEFAULT_CATALOG",
    # Decomposer
    "TaskDecomposer",
    "DecomposerTrainingCollector",
    "DECOMPOSER_SYSTEM_PROMPT",
    # Anti-waste
    "RollingSummarizer",
    "SelfVerifier",
    "VerificationResult",
    # Main engine
    "IntelligentRouter",
    # Observability
    "RouterMetricsCollector",
    "API_COST_TABLE",
    "CostEstimator",
]
