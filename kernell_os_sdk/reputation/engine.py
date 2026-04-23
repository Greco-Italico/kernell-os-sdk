import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class AgentReputationMetrics:
    quality_score: float = 0.0      # Q (0-100): Calidad de reviews
    uptime_score: float = 0.0       # U (0-100): Uptime histórico
    sla_compliance: float = 0.0     # S (0-100): Cumplimiento de SLA
    benchmark_score: float = 0.0    # B (0-100): Puntuación de hardware/IA
    task_volume: float = 0.0        # T (0-100): Volumen normalizado de trabajos
    disputes_penalties: float = 0.0 # D (0-100): Disputas y penalizaciones

    category_scores: Dict[str, float] = field(default_factory=dict)
    
    @property
    def global_reputation(self) -> float:
        """
        Fórmula híbrida de reputación:
        R = 0.30Q + 0.20U + 0.20S + 0.15B + 0.10T - 0.05D
        """
        r = (
            0.30 * self.quality_score +
            0.20 * self.uptime_score +
            0.20 * self.sla_compliance +
            0.15 * self.benchmark_score +
            0.10 * self.task_volume -
            0.05 * self.disputes_penalties
        )
        return max(0.0, min(100.0, r))

class ReputationEngine:
    """Motor central para calcular y actualizar la reputación de agentes"""
    
    def __init__(self):
        # En producción, esto interactuaría con un Ledger o base de datos inmutable
        self._metrics_store: Dict[str, AgentReputationMetrics] = {}

    def get_reputation(self, agent_uuid: str) -> float:
        metrics = self._metrics_store.get(agent_uuid)
        if not metrics:
            return 0.0
        return metrics.global_reputation

    def update_metrics(self, agent_uuid: str, updates: dict):
        if agent_uuid not in self._metrics_store:
            self._metrics_store[agent_uuid] = AgentReputationMetrics()
        
        metrics = self._metrics_store[agent_uuid]
        
        for k, v in updates.items():
            if hasattr(metrics, k):
                setattr(metrics, k, v)
