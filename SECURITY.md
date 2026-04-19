# Kernell OS SDK — Security & Audit Overview (SOC2/ISO 27001 Ready)

## 1. Threat Model & Zero Trust Architecture

Kernell OS SDK is built upon a **Strict Zero Trust** architecture. We assume that the LLM (Large Language Model) is inherently vulnerable to Prompt Injection, Goal Hijacking, and malicious instructions. Therefore, the security boundary is **not** the LLM's alignment, but a deterministic, capability-based Python Execution Engine.

### Identified Threat Actors
1.  **Malicious Agents (External):** Agents communicating via the AEON M2M network attempting to inject malicious payloads into delegation requests.
2.  **Compromised LLM (Goal Hijacking):** The underlying LLM is manipulated via prompt injection to perform valid but destructive actions (e.g., exfiltrating data via `curl` or sending `$KERN` to an attacker).
3.  **Resource Abusers (DoS):** Agents attempting to exhaust node resources via Fork Bombs or Memory Leaks.

---

## 2. Security Boundaries & Defenses

### 2.1 Formal Capability-Based Policy Engine (DPI)
All commands suggested by the LLM must pass through the `PolicyEngine`. It operates on a strict **Default Deny** basis.
*   **Binary Authorization:** Commands must exist in the agent's explicit `AgentCapabilities` manifest.
*   **Argument Inspection:** Flags and arguments are strictly validated. (e.g., `python -c` is permanently blocked to prevent RCE).
*   **Semantic Deep Packet Inspection (DPI):** Network commands (`curl`, `wget`) are parsed to block command substitution (`$()`, \`\`, `|`) and egress is restricted to whitelisted domains (e.g., `api.kernell.site`). File commands are sandboxed to specific allowed paths, defeating symlink traversal.

### 2.2 gVisor Sandbox Hardening
Agent execution does not happen on the host. It runs inside a hardened Docker container intercepted by **gVisor (`runsc`)**, providing lightweight micro-VM isolation for system calls.
*   **Immutable Root:** `--read-only` filesystem.
*   **Privilege Drop:** `--cap-drop=ALL` and `--security-opt=no-new-privileges`.
*   **Anti-DoS:** Strict quotas using `--pids-limit=64` and bounded `--memory-swap`.

### 2.3 Cryptographic Identity & Supply Chain
*   **Ed25519 Passports:** All inter-agent communication (A2A) and Escrow transactions require Ed25519 cryptographic signatures to verify authenticity and prevent spoofing.
*   **Hash-Locked Dependencies:** The SDK is distributed with `pip-compile` generated cryptographic hashes (`requirements.txt`), mitigating PyPI supply chain attacks.

---

## 3. The "Paranoid Mode" (Multi-Layer Execution Authority)
*(Under Active Deployment)*

For critical financial and enterprise operations, Kernell OS employs a **RiskEngine** to classify tasks and enforce consensus.

### Risk Level Tiers:
*   🟢 **LOW** (e.g., `ls`, `pwd`): Auto-approved by Policy Engine.
*   🟡 **MEDIUM** (e.g., standard API queries): Subject to Behavior Monitor rate-limiting.
*   🔴 **HIGH** (e.g., `curl` to unknown domain): Requires Explicit Sandbox Egress Rule.
*   🚨 **CRITICAL** (e.g., `$KERN` Escrow Transfers, delegation of sensitive skills): Triggers the **Execution Gate**.

### Execution Gate Defenses (Critical Tasks):
1.  **Multi-Sig Consensus:** Requires $N$ of $M$ valid Ed25519 signatures (e.g., Agent + Human Oracle).
2.  **Time-Locks:** Mandatory execution delays (e.g., 30 seconds) for anomaly detection and cancellation.
3.  **Behavioral Monitoring:** Blocks valid actions if they deviate from the agent's historical baseline (Anti-Goal Hijacking).
4.  **Immutable Audit Log:** All critical actions are cryptographically signed and appended to an immutable WAL (Write-Ahead Log) before execution.

---

## 4. Known Limitations
*   While gVisor isolates syscalls, side-channel attacks (Spectre/Meltdown) are theoretically possible if running on shared multi-tenant hardware without strict vCPU pinning.
*   Egress network filtering relies on application-layer DPI. Future versions will implement strict `iptables` at the Docker bridge level for kernel-level dropping of non-whitelisted packets.

---
*For vulnerability disclosures, please contact the Kernell OS Security Team.*
