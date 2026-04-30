"""
Kernell OS SDK — Model Market Registry (Pricing Oracle)
═══════════════════════════════════════════════════════
Real-time market data aggregator for all available LLM endpoints.
Provides Sully with live pricing, latency, rate-limit status, and quality scores.

This is the Oracle — Sully NEVER memorizes prices. It always asks here.
"""

import logging
import time
from typing import Dict, List, Optional

from kernell_os_sdk.sully.types import ModelMarketInfo, Tier

logger = logging.getLogger("kernell.sully.market")


class ModelMarketProvider:
    """Base class for market data providers."""
    
    def fetch_models(self) -> List[ModelMarketInfo]:
        raise NotImplementedError


class GroqMarketProvider(ModelMarketProvider):
    """Fetches live model data from Groq."""
    
    def fetch_models(self) -> List[ModelMarketInfo]:
        # In production: hit https://api.groq.com/openai/v1/models
        # and cross-reference with published pricing
        return [
            ModelMarketInfo(
                model_id="groq/llama3-70b",
                provider="groq",
                input_cost_per_1k=0.00059,
                output_cost_per_1k=0.00079,
                context_limit=8192,
                max_output_tokens=8192,
                avg_latency_ms=300,
                p95_latency_ms=800,
                supports_reasoning=True,
                quality_score=0.75,
            ),
            ModelMarketInfo(
                model_id="groq/llama3-8b",
                provider="groq",
                input_cost_per_1k=0.00005,
                output_cost_per_1k=0.00008,
                context_limit=8192,
                max_output_tokens=8192,
                avg_latency_ms=150,
                p95_latency_ms=400,
                quality_score=0.60,
            ),
            ModelMarketInfo(
                model_id="groq/qwen3-32b",
                provider="groq",
                input_cost_per_1k=0.00,
                output_cost_per_1k=0.00,
                context_limit=131072,
                max_output_tokens=8192,
                avg_latency_ms=400,
                p95_latency_ms=1200,
                supports_reasoning=True,
                quality_score=0.80,
            ),
        ]


class OpenRouterMarketProvider(ModelMarketProvider):
    """Fetches live model data from OpenRouter."""
    
    def fetch_models(self) -> List[ModelMarketInfo]:
        # In production: hit https://openrouter.ai/api/v1/models
        return [
            ModelMarketInfo(
                model_id="openrouter/deepseek-r1",
                provider="openrouter",
                input_cost_per_1k=0.00055,
                output_cost_per_1k=0.0022,
                context_limit=65536,
                max_output_tokens=8192,
                avg_latency_ms=1500,
                p95_latency_ms=4000,
                supports_reasoning=True,
                quality_score=0.82,
            ),
            ModelMarketInfo(
                model_id="openrouter/claude-3-5-sonnet",
                provider="openrouter",
                input_cost_per_1k=0.003,
                output_cost_per_1k=0.015,
                context_limit=200000,
                max_output_tokens=8192,
                avg_latency_ms=2000,
                p95_latency_ms=5000,
                supports_reasoning=True,
                supports_vision=True,
                quality_score=0.95,
            ),
            ModelMarketInfo(
                model_id="openrouter/gemini-2.5-flash",
                provider="openrouter",
                input_cost_per_1k=0.0001,
                output_cost_per_1k=0.0004,
                context_limit=1000000,
                max_output_tokens=65536,
                avg_latency_ms=800,
                p95_latency_ms=2500,
                supports_reasoning=True,
                supports_vision=True,
                quality_score=0.85,
            ),
        ]


class LocalMarketProvider(ModelMarketProvider):
    """Reports locally available models (Ollama, vLLM, etc)."""
    
    def fetch_models(self) -> List[ModelMarketInfo]:
        return [
            ModelMarketInfo(
                model_id="local/sully-8b",
                provider="local",
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                context_limit=8192,
                max_output_tokens=4096,
                avg_latency_ms=200,
                p95_latency_ms=600,
                quality_score=0.55,
            ),
            ModelMarketInfo(
                model_id="local/llama3-8b",
                provider="local",
                input_cost_per_1k=0.0,
                output_cost_per_1k=0.0,
                context_limit=8192,
                max_output_tokens=4096,
                avg_latency_ms=250,
                p95_latency_ms=700,
                quality_score=0.60,
            ),
        ]


class ModelMarketRegistry:
    """
    Aggregated, cached market view across all providers.
    TTL-based cache to avoid hammering APIs on every Sully decision.
    """
    
    def __init__(self, providers: List[ModelMarketProvider] = None, ttl: float = 5.0):
        self.providers = providers or [
            LocalMarketProvider(),
            GroqMarketProvider(),
            OpenRouterMarketProvider(),
        ]
        self.ttl = ttl
        self._cache: Dict[str, ModelMarketInfo] = {}
        self._last_fetch: float = 0.0
    
    def get_market(self) -> Dict[str, ModelMarketInfo]:
        """Return current market snapshot (cached with TTL)."""
        now = time.time()
        if self._cache and (now - self._last_fetch < self.ttl):
            return self._cache
        
        market = {}
        for provider in self.providers:
            try:
                models = provider.fetch_models()
                for m in models:
                    market[m.model_id] = m
            except Exception as e:
                logger.warning(f"[Market] Provider {provider.__class__.__name__} failed: {e}")
        
        self._cache = market
        self._last_fetch = now
        logger.debug(f"[Market] Refreshed: {len(market)} models available")
        return market
    
    def get_models_by_tier(self, market: Dict[str, ModelMarketInfo] = None) -> Dict[Tier, List[ModelMarketInfo]]:
        """Categorize models into tiers based on cost."""
        market = market or self.get_market()
        tiers = {Tier.LOCAL: [], Tier.ECONOMIC: [], Tier.PREMIUM: []}
        
        for m in market.values():
            if m.provider == "local":
                tiers[Tier.LOCAL].append(m)
            elif m.input_cost_per_1k < 0.001:
                tiers[Tier.ECONOMIC].append(m)
            else:
                tiers[Tier.PREMIUM].append(m)
        
        return tiers
    
    def mark_rate_limited(self, model_id: str):
        """Mark a model as rate-limited (called by execution layer on 429s)."""
        if model_id in self._cache:
            self._cache[model_id].rate_limited = True
            logger.info(f"[Market] {model_id} marked as rate-limited")
    
    def update_quality_score(self, model_id: str, success: bool):
        """Update quality score with exponential moving average from telemetry."""
        if model_id in self._cache:
            m = self._cache[model_id]
            alpha = 0.1  # learning rate
            m.quality_score = m.quality_score * (1 - alpha) + (1.0 if success else 0.0) * alpha
