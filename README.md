<div align="center">
  <img src="https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/logo3d.png" alt="Kernell OS Logo" width="180" height="180">

  # Kernell OS SDK
  ### Policy-driven execution infrastructure for agent systems
</div>

Kernell OS SDK is not a simple LLM wrapper.  
It is an execution control plane that optimizes inference cost, quality, and latency while collecting feedback to improve routing decisions over time.

## What This SDK Is

- Policy-driven inference engine
- Multi-tier execution router (local, cheap API, premium API)
- Quality-aware runtime with verification and safe fallback
- Telemetry + labeling + training pipeline for continuous improvement
- Agent runtime foundation (security, sandboxing, economics, marketplace, governance)

## What This SDK Is Not

- Prompt utility library
- Single-model client wrapper
- Static rule router without learning loop

---

## Core Value Proposition

Traditional flow:

`input -> one LLM`

Kernell OS flow:

`input -> policy decision -> multi-layer execution -> verification -> telemetry -> retraining`

### Why this matters

- Optimize costs without blindly degrading quality
- Route dynamically per task/hardware/risk
- Learn from production behavior (data flywheel)
- Keep fallback safety under uncertainty

---

## Architecture Overview

```text
Task Input
  -> Policy Model (Lite/Pro)
  -> (Optional) Task Decomposition
  -> Execution Layers:
       [Semantic Cache] -> [Local] -> [Cheap API] -> [Premium]
  -> Self Verification
  -> Re-route / Fallback (if needed)
  -> Telemetry
  -> Offline Labeling
  -> Dataset / Fine-tuning Pipeline
```

## Routing Strategy

The router is policy-driven, not difficulty-only:

- `route`: `local | cheap | premium | hybrid`
- `confidence`
- `risk`
- `expected_cost_usd`
- `expected_latency_s`
- `needs_decomposition`

When confidence/risk/economic uncertainty is unsafe, it forces `hybrid` fallback path.

---

## Main Components (Real Modules)

### Router and Policy

- `kernell_os_sdk/router/intelligent_router.py`  
  Orchestrates execution across cache/local/cheap/premium, verification, telemetry.
- `kernell_os_sdk/router/policy_lite.py`  
  Local policy model client with safety overrides.
- `kernell_os_sdk/router/classifier_pro.py`  
  Cloud escalation client for higher-precision routing.
- `kernell_os_sdk/router/types.py`  
  Canonical contracts (`PolicyDecision`, tiers, results).
- `kernell_os_sdk/router/entrypoint.py`  
  Shadow/canary/full rollout entrypoint with safe fallback.

### Quality, Cost, and Context

- `kernell_os_sdk/router/verifier.py` (`SelfVerifier`)
- `kernell_os_sdk/router/estimator.py` (`CostEstimator`)
- `kernell_os_sdk/router/summarizer.py` (`RollingSummarizer`)
- `kernell_os_sdk/router/decomposer.py` (`TaskDecomposer`)
- `kernell_os_sdk/router/model_registry.py` (`ModelRegistry`)

### Telemetry and Learning Loop

- `kernell_os_sdk/router/telemetry_collector.py`  
  Collects anonymized route/outcome/quality signals.
- `kernell_os_sdk/router/offline_labeler.py`  
  Produces optimal-route labels from real outcomes (cost + quality aware).

### Data Pipeline Scripts

- `scripts/policy_build_dataset.py` -> telemetry to labeled dataset
- `scripts/policy_make_sft_jsonl.py` -> labeled dataset to SFT JSONL
- `scripts/policy_train_lora.py` -> LoRA training scaffold
- `scripts/policy_audit_dataset.py` -> distribution and sampling audit

### Runtime, Security, and Infra Domains

- `kernell_os_sdk/runtime/`  
  Firecracker/Docker/Subprocess/hybrid runtime primitives
- `kernell_os_sdk/security/`  
  policy, verifier, SSRF and capability controls
- `kernell_os_sdk/cognitive/`  
  memory graph, execution graph, semantic modules
- `kernell_os_sdk/marketplace/`, `governance/`, `cluster/`, `delegation/`, `escrow/`  
  economic coordination and distributed agent primitives

---

## Data Flywheel

Kernell OS improves routing through a closed learning loop:

1. Runtime emits telemetry from real executions
2. Offline labeler computes optimal route targets
3. Dataset is generated and audited
4. Model fine-tuning is prepared/executed
5. Updated policy models are deployed

This converts routing mistakes into training signal (`underestimation`, `overestimation`, `misroute`) and enables continuous optimization.

---

## Safety and Production Hardening

- Verification-aware routing to reduce low-quality escalations
- Risk-aware and budget-aware fallback to `hybrid`
- Optional Prometheus dependency (non-blocking no-op fallback in runtime metrics)
- Shadow/canary rollout strategy before full traffic cutover
- Rate limiting, sandbox controls, and capability policy modules available in SDK

---

## Installation

```bash
pip install kernell-os
```

Optional observability dependency:

```bash
pip install prometheus_client
```

---

## Minimal Example

```python
from kernell_os_sdk.router import PolicyLiteClient, PolicyLiteConfig

# Integrate PolicyLiteClient into your IntelligentRouter wiring
# based on your local model backend and runtime configuration.
```

See `kernell_os_sdk/router/` modules and tests for concrete integration patterns.

---

## Testing

Router and flywheel suites:

```bash
python -m pytest tests/test_router.py tests/test_data_flywheel.py tests/test_policy_lite.py -q
```

---

## Current Status

### Implemented now

- Policy-driven router integration
- Telemetry v2 with policy signals
- Offline labeling pipeline with quality-aware guards
- Dataset audit tooling and sampling workflow
- Regression-tested router/flywheel suites

### Planned / in progress

- Persistent semantic cache backend integration (distributed)
- Full training automation and model promotion gates
- Expanded online feedback correction and deploy gating benchmarks

---

## Open-Core Positioning

- SDK core: open source runtime and routing foundations
- Advanced policy intelligence and cloud services: source-available/commercial layers

---

<div align="center">
  <i>From static LLM calls to adaptive inference infrastructure.</i>
</div>
