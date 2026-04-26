<div align="center">
  <img src="https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/logo3d.png" alt="Kernell OS Logo" width="200" height="200">
  
  # Kernell OS
  ### Machines coordinate, verify, and settle value autonomously.

  <br>
  
  ![Kernell OS Demo](https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/docs/assets/demo_60s.gif)

  <br>

  ![Tests](https://img.shields.io/badge/tests-135%20passing-brightgreen)
  ![Coverage](https://img.shields.io/badge/router%20coverage-37%20tests-blue)
  ![Python](https://img.shields.io/badge/python-3.11%2B-blue)
  ![License](https://img.shields.io/badge/license-Apache%202.0-green)
</div>

Kernell OS is an agentic runtime where multiple AI systems collaborate, reuse accumulated knowledge, and transact value securely.

This is not another framework for LLM wrappers. This is **infrastructure for autonomous machine-to-machine economies**.

---

## The Landscape

| System | Generates Code | Remembers Architecture | Coordinates Agents | Settles M2M Value | Optimizes Costs |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Copilots** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Agent Frameworks** | ✅ | ⚠️ | ⚠️ | ❌ | ❌ |
| **Kernell OS** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## How It Works

Kernell OS fundamentally shifts how LLMs interact with code, infrastructure, and economics:

1. ⚡ **3-Layer Token Economy Engine**: Routes every task through the cheapest capable layer — Local (free) → Cheap API ($0.14/M) → Premium API (last resort). Achieves **85-95% cost reduction** compared to sending everything to premium models.
2. 🧠 **Semantic Memory Graph**: Doesn't cache strings. It learns and traverses architectural paths, reusing proven dependencies and pruning toxic routes via the **Dual Confidence Model**.
3. 🛡️ **Intent Firewall**: Untrusted AI execution is halted. Every action (syscalls, file writes, outbound requests) is sandbox-verified before touching the host system.
4. 💰 **Escrow Engine**: Agents are financially bound. Kernell holds execution value in cryptographic escrow, releasing funds ($KERN) only upon verified, monotonic success.
5. 📊 **Production Observability**: Prometheus-ready metrics, cost-per-task tracking, misclassification detection, and pre-execution cost simulation — all exposed via dashboard and API.

---

## Token Economy Engine (NEW)

The **Intelligent Router** is the economic brain of Kernell OS. It eliminates unnecessary API spend by routing tasks through a 3-layer pipeline:

```
INPUT → Decompose → Cache Check → Local Exec → Verify → [Cheap API] → [Premium API]
                                                  ↑                         ↑
                                           AutoMix Gate              Last resort only
```

### Architecture

| Layer | Models | Cost/1M tokens | When Used |
|---|---|---|---|
| **Local** (Ollama) | Qwen3-1.7B, Gemma3-4B, Mistral-7B, DeepSeek-R1-14B | **$0.00** | Default for 70%+ of tasks |
| **Cheap API** | DeepSeek V3, Groq, Gemini Flash | **$0.14 - $0.55** | Medium-complexity tasks |
| **Premium API** | Claude Opus, GPT-5, Gemini Pro | **$15 - $75** | Expert-level only |

### Anti-Waste Components

- **SemanticCache**: Skip repeated work entirely (40-70% fewer API calls)
- **RollingSummarizer**: Compress context between steps (kills O(n²) token leak)
- **SelfVerifier**: Validate output before escalating (prevents premature spend)
- **CostEstimator**: Show cost *before* execution — full transparency

### Deployment Strategy

The router integrates via **safe dual-mode** — no breaking changes:

```python
# Phase 0: Shadow Mode (default) — zero risk
#   Runs both routers, returns legacy, logs differences
config = RouterConfig(enable_intelligent_router=True, shadow_mode=True)

# Phase 1: Canary — 10% traffic to new router
config = RouterConfig(canary_percent=0.10)

# Phase 2: Full rollout with automatic fallback
config = RouterConfig(enable_intelligent_router=True)
```

### Dashboard

The **Command Center** now includes a Token Economy panel:
- 💰 Real-time cost vs. savings metrics
- 🤖 Local model inventory (auto-detected from hardware)
- ⚡ Inference provider key management
- 📊 Prometheus `/metrics` endpoint for Grafana
- 🎯 Classifier health + fine-tuning readiness score

---

## Security

Production-grade security hardened with **98 automated tests**:

- 🔒 **Sandbox Isolation**: Docker/gVisor with AST-validated code execution
- 🛡️ **SSRF Protection**: Centralized safe HTTP client, CIDR block enforcement
- ⚡ **Rate Limiting**: Sliding window with circuit breakers (Netflix Hystrix pattern)
- 🔐 **Cryptographic Passports**: Ed25519 + AES-256-GCM agent identity
- 📜 **Audit Trail**: Immutable operation log with redacted PII

---

## Quickstart

```bash
# 1. Install the runtime
pip install kernell-os

# 2. Scaffold a new environment
kernell init

# 3. Boot the execution engine, Memory Graph, and Gateway
kernell start

# 4. Run the 60-second interactive demo
kernell demo
```

---

## SDK Architecture (19,000+ LOC)

```
kernell_os_sdk/
├── router/          ⚡ 3-Layer Token Economy Engine (2,436 LOC)
├── cognitive/       🧠 Memory, Execution Graph, Intent Firewall
├── security/        🔒 Sandbox, SSRF, Rate Limiter, Policy Engine
├── escrow/          💰 Cryptographic Escrow Manager
├── llm/             🤖 Multi-provider LLM abstraction
├── cluster/         🌐 P2P Discovery + Compute Pool
├── governance/      🏛️ Agent DAOs + Federation
├── marketplace/     🏪 Matching Engine
├── delegation/      👥 Sub-agent Spawning
├── runtime/         📦 Docker/Firecracker/Subprocess isolation
└── dashboard.py     📊 FastAPI Command Center
```

---

## Business Model (Open-Core)

| Layer | License | Description |
|---|---|---|
| **SDK Core** | ✅ Open Source | Router, interfaces, integrations, base classifier |
| **Classifier Pro** | 🔒 API | Fine-tuned model with real-world optimization data |
| **Cloud Platform** | 🔒 SaaS | Managed router, dashboard, auto-learning pipeline |

---

<div align="center">
  <br>
  <i>This is not a copilot.</i><br>
  <b>This is infrastructure for autonomous systems.</b>
</div>
