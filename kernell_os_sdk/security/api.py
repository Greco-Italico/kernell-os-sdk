"""
Kernell OS SDK — Security Observer API
══════════════════════════════════════
FastAPI backend that exposes telemetry data from the SecurityEventLog and
AdaptiveRiskEngine to the Command Center v4 Dashboard.

Run with: uvicorn kernell_os_sdk.security.api:app --reload --port 8050
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
from typing import List, Dict, Any

# We assume a global singleton observer and adaptive engine are available.
# In a real deployment, these would be wired into the application state.
from .telemetry import SecurityObserver
from .adaptive_risk import AdaptiveRiskEngine
from .cognitive_firewall import CognitiveSecurityLayer

app = FastAPI(title="Kernell OS Security Command Center API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared instances for the API
# In production, these should be the same instances used by the active Agent.
observer = SecurityObserver()
adaptive_engine = AdaptiveRiskEngine()

@app.get("/api/v1/security/metrics")
def get_metrics():
    """Returns top-level security metrics (Shadow Block Rate, etc)."""
    m = observer.metrics.compute()
    return m

@app.get("/api/v1/security/events")
def get_recent_events(limit: int = 100):
    """Returns the most recent security events."""
    events = observer.event_log.events[-limit:]
    # Reverse so newest is first
    return [e.__dict__ for e in reversed(events)]

@app.get("/api/v1/security/actors")
def get_actor_reputation():
    """Returns reputation scores for agents/actors."""
    return [
        {
            "actor_id": rep.agent_id,
            "trust_score": rep.trust_score,
            "block_rate": rep.block_rate,
            "interactions": rep.interactions,
        }
        for rep in adaptive_engine.reputation.leaderboard()
    ]

@app.get("/api/v1/security/patterns")
def get_emerging_patterns():
    """Returns newly learned attack patterns."""
    return [
        {
            "regex": p.regex,
            "confidence": p.confidence,
            "hits": p.hit_count,
            "source": p.source,
            "status": p.status,
            "last_seen": p.last_seen
        }
        for p in adaptive_engine.learner.learned_patterns
    ]

@app.get("/api/v1/security/campaigns")
def get_campaigns():
    """Returns detected coordinated campaigns."""
    return adaptive_engine.campaigns.active_campaigns

@app.get("/api/v1/security/cross-channel")
def get_cross_channel():
    """Returns detected cross-channel attacks."""
    return adaptive_engine.cross_channel.active_threats

@app.get("/api/v1/security/adaptive-status")
def get_adaptive_status():
    """Returns the status of the dynamic thresholds."""
    return adaptive_engine.status()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
