# Kernell OS SDK — Security Architecture
### SOC2 / ISO 27001 / OWASP Audit-Ready

> **Version:** 1.2.0 — Enterprise Hardened  
> **Last Audit:** 2026-04-19  
> **Classification:** Financial-Grade Agent Runtime

---

## 1. Threat Model (Zero Trust)

Kernell OS SDK assumes **all LLM outputs are hostile**. The security boundary is a deterministic, capability-based Python execution engine — never the model's alignment.

### 1.1 Identified Threat Actors

| Actor | Vector | Mitigation Layer |
|-------|--------|-----------------|
| **Compromised LLM** | Prompt Injection → Goal Hijacking | PolicyEngine (DPI) |
| **Malicious Agent** | A2A payload injection | Ed25519 Passport + Taint Propagation |
| **Colluding Agents** | Taint Laundering (multi-agent exfil) | Distributed Taint Protocol |
| **Resource Abuser** | Fork bombs, CPU exhaustion | gVisor + pids-limit + memory-swap |
| **Economic Attacker** | Double-spend, TOCTOU races | Self-contained Lua + Idempotency |
| **Insider / Oracle** | Multisig abuse | Trust Diversity Enforcement |

### 1.2 Attack Surface Assumptions
- The LLM **will** attempt to execute arbitrary code via `-c` flags.
- Agents **will** attempt to exfiltrate data through permitted network channels.
- Concurrent requests **will** attempt to exploit race conditions in financial operations.
- Colluding agents **will** attempt to launder tainted data across trust boundaries.

---

## 2. Defense-in-Depth Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LLM (UNTRUSTED)                      │
├─────────────────────────────────────────────────────────┤
│  Layer 1: PolicyEngine (Capability-Based DPI)           │
│    ├── Binary Authorization (command whitelist)         │
│    ├── Argument Validation (flag-level)                 │
│    ├── Python Semantic Inspection (-c BLOCKED)          │
│    ├── Network DPI (URL parsing + exfil detection)      │
│    └── Filesystem Containment (realpath + deny list)    │
├─────────────────────────────────────────────────────────┤
│  Layer 2: RiskEngine (Dynamic Behavioral Analysis)      │
│    ├── Data Taint Tracking (ExecutionContext)            │
│    ├── Behavior Drift Detection (rate + volume)         │
│    ├── Chained Action Correlation                       │
│    └── Dynamic Risk Score Mutation                      │
├─────────────────────────────────────────────────────────┤
│  Layer 3: ExecutionGate (Consensus & Time-Locks)        │
│    ├── Multi-Sig (N-of-M Ed25519 signatures)            │
│    ├── Trust Diversity (agent + oracle roles required)   │
│    ├── Time-Lock (30s freeze before CRITICAL ops)        │
│    └── Agent State Freeze (anti-evasion)                │
├─────────────────────────────────────────────────────────┤
│  Layer 4: gVisor Sandbox (Kernel Isolation)             │
│    ├── --runtime=runsc (syscall interception)            │
│    ├── --read-only --cap-drop=ALL                       │
│    ├── --pids-limit=64 --memory-swap=RAMmb              │
│    └── --network=none (when disabled)                   │
├─────────────────────────────────────────────────────────┤
│  Layer 5: Economic Safety Layer (Escrow Hardening)      │
│    ├── Self-Contained Lua (TOCTOU eliminated)           │
│    ├── Idempotency Keys (1h TTL, anti double-spend)     │
│    ├── Circuit Breaker (50 ops/min max)                 │
│    └── WAL-first + HMAC-signed audit trail              │
├─────────────────────────────────────────────────────────┤
│  Layer 6: Distributed Trust Protocol                    │
│    ├── A2AMessage with mandatory sensitivity tags       │
│    ├── Obligatory Taint Propagation on receipt          │
│    └── Cryptographic signing of context + sensitivity    │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Key Security Controls

### 3.1 PolicyEngine (`policy_engine.py`)
- **Default Deny**: Only explicitly listed commands execute.
- **`python -c` permanently blocked**: Eliminates arbitrary code execution.
- **Network DPI**: Detects `$()`, backticks, and pipes in URLs (anti-exfiltration).
- **Path containment**: `os.path.realpath()` resolves symlinks before validation.

### 3.2 RiskEngine (`risk_engine.py`)
- **Taint Tracking**: Reading sensitive files marks the agent's `ExecutionContext`.
- **Data Flow Control**: Tainted agents attempting network egress get escalated to CRITICAL.
- **Behavior Monitor**: Detects rate anomalies (>10 req/min) and volume drift (>500KB reads).

### 3.3 ExecutionGate (`execution_gate.py`)
- **Trust Diversity**: Multisig requires signatures from distinct roles (e.g., `agent` + `oracle`). Two agents cannot approve each other's critical operations.
- **Replay Prevention**: Signatures expire after 5 minutes.
- **State Freeze**: During time-lock, the agent ignores all external stimuli.

### 3.4 Escrow Engine (`kap_escrow/engine.py`)
- **TOCTOU Eliminated**: Lua scripts read metadata, compute amounts, and execute transfers in a single atomic block. No Python pre-computation of financial values.
- **Idempotency**: Each operation gets a unique key (`idem:{op}:{contract_id}`) with 1-hour TTL. Retries return `already_processed`.
- **Circuit Breaker**: More than 50 escrow operations in 60 seconds trips the breaker and halts all operations.

### 3.5 Supply Chain
- **Hash-locked dependencies** via `pip-compile --generate-hashes`.
- **Ed25519 Passports** for all inter-agent identity verification.

---

## 4. Known Limitations & Residual Risk

| Risk | Severity | Status | Mitigation Path |
|------|----------|--------|-----------------|
| Side-channel (Spectre/Meltdown) on shared hardware | Low | Accepted | vCPU pinning in dedicated deployments |
| Egress filtering at IP level (vs app layer) | Medium | Planned | `iptables` rules on Docker bridge |
| Oracle incentive alignment | Medium | Partial | Staking + slashing (roadmap) |
| Formal verification of Lua invariants | Low | Planned | Property-based testing suite |

---

## 5. Vulnerability Disclosure

For responsible disclosure of security vulnerabilities, contact the Kernell OS Security Team via the repository's security advisory feature.

---

*This document is maintained as part of the SDK's compliance artifacts and is updated with each security-relevant release.*
