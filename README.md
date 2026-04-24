<div align="center">
  <img src="https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/logo3d.png" alt="Kernell OS Logo" width="200" height="200">
  
  # Kernell OS
  ### Machines coordinate, verify, and settle value autonomously.

  <br>
  
  ![Kernell OS Demo](https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/docs/assets/demo_60s.gif)

  <br>
</div>

Kernell OS is an agentic runtime where multiple AI systems collaborate, reuse accumulated knowledge, and transact value securely.

This is not another framework for LLM wrappers. This is **infrastructure for autonomous machine-to-machine economies**.

---

## The Landscape

| System | Generates Code | Remembers Architecture | Coordinates Agents | Settles M2M Value |
| :--- | :---: | :---: | :---: | :---: |
| **Copilots** | ✅ | ❌ | ❌ | ❌ |
| **Agent Frameworks** | ✅ | ⚠️ | ⚠️ | ❌ |
| **Kernell OS** | ✅ | ✅ | ✅ | ✅ |

---

## How It Works

Kernell OS fundamentally shifts how LLMs interact with code, infrastructure, and economics:

1. 🔀 **Cognitive Router v2**: Evaluates tasks contextually. If an architecture is unknown, it routes to premium reasoning models (e.g., DeepSeek-V3). If the architecture is known, it routes to hyper-cheap local models ($0) to just write the glue code.
2. 🧠 **Semantic Memory Graph**: Doesn't cache strings. It learns and traverses architectural paths, reusing proven dependencies and pruning toxic routes via the **Dual Confidence Model**.
3. 🛡️ **Intent Firewall**: Untrusted AI execution is halted. Every action (syscalls, file writes, outbound requests) is sandbox-verified before touching the host system.
4. 💰 **Escrow Engine**: Agents are financially bound. Kernell holds execution value in cryptographic escrow, releasing funds ($KERN) only upon verified, monotonic success.

---

## Quickstart

Stop building prototypes. Boot your first agentic economy in seconds.

```bash
# 1. Install the runtime
pip install kernell-os

# 2. Scaffold a new environment
kernell init

# 3. Boot the execution engine, Memory Graph, and Gateway
kernell start

# 4. Run the 60-second interactive investor demo
kernell demo
```

---

## Expected Output

Upon running `kernell demo`, your browser will launch the **Control Plane Dashboard**. 

You will visually trace:
* 🟣 **Path Intelligence Hit**: The system bypassing generation and retrieving an entire architectural sub-graph.
* 🔴 **Firewall Freeze**: The system halting a malicious external dependency request for human-in-the-loop approval.
* 🟢 **Escrow Settlement**: The smart contract releasing $KERN funds upon successful test execution.

*(See the placeholder GIF at the top for reference)*

---

<div align="center">
  <br>
  <i>This is not a copilot.</i><br>
  <b>This is infrastructure for autonomous systems.</b>
</div>
