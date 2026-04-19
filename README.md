<p align="center">
  <img src="https://raw.githubusercontent.com/Greco-Italico/kernell-os-sdk/main/logo3d.png" alt="Kernell OS Logo" width="300" />
</p>

# Kernell OS SDK

![PyPI version](https://badge.fury.io/py/kernell-os-sdk.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Kernell OS SDK** is a production-grade, security-first framework for building autonomous AI agents that can interact with the machine, participate in M2M (Machine-to-Machine) commerce, and operate securely within isolated environments.

## Features

- **🛡️ Secure By Default**: Hardened sandbox execution, cryptographic identities bound to hardware UDID, and strict permission boundaries (anti-RCE).
- **💸 Built-in M2M Commerce**: Native integration with the Kernell Agent Protocol (KAP) and `$KERN` token for task payments and escrow.
- **🧠 Cortex Shared Memory**: Offloads context to Redis for massive token savings using episodic memory streams.
- **📈 Command Center**: A beautiful, real-time local dashboard to monitor metrics, toggle permissions, and manage API keys safely.
- **🔋 Production Resilience**: Includes Token Budgeting, Circuit Breakers, SLO Monitoring, and Tool Output Persistence out of the box.

## Installation & Quick Start

Kernell OS features a **Zero-Touch Web Installer**. You don't need to write manual Python scripts to get your swarm running.

```bash
# 1. Install the SDK
pip install kernell-os-sdk

# 2. Launch the Unified Web Installer
kernell init
```

🟢 **`kernell init` will automatically open your browser at `http://localhost:3000`.**

The Web Wizard will guide you through:
1. **Hardware Auto-Discovery**: Automatically selecting the best local open-source models for your RAM/VRAM.
2. **Dual Wallet Generation**: Automatically spinning up an L1/L2 cryptographic wallet for 0-fee M2M microtransactions.
3. **Swarm Booting**: Generating your secure Sandbox `.env` and launching the agent swarm.

Once initialized, the wizard will seamlessly redirect you to the **Command Center Dashboard**.

### Advanced: Programmatic Usage

If you prefer to scaffold your agents manually via Python instead of using the Web Installer:

```python
from kernell_os_sdk import Agent, AgentPermissions
from kernell_os_sdk.llm import LLMRouter, OllamaProvider, AnthropicProvider

# 1. Hybrid Engine
local = OllamaProvider(model="gemma4:9b")
cloud = AnthropicProvider(model="claude-3-5-sonnet-20241022")
router = LLMRouter(local_provider=local, cloud_provider=cloud, cloud_threshold="hard")

# 2. Architect Agent
director = Agent(
    name="System Architect",
    engine=router,
    permissions=AgentPermissions(network_access=True)
)

# 3. Enable Fractal Delegation
director.enable_delegation(max_workers=5, worker_engine=local)

# Start the agent daemon
director.run()
```

### 3. Add Custom Skills (Tools)

Easily extend your agent with type-hinted skills. API keys are safely retrieved from the Command Center at runtime.

```python
import httpx

@agent.skill(description="Fetch the weather for a city.")
def get_weather(city: str) -> str:
    # Safely get API key added via the Dashboard
    api_key = dashboard.get_api_key("weather_api")
    if not api_key:
        return "Error: Weather API key not configured."
        
    response = httpx.get(f"https://api.weather.com/v1/{city}?key={api_key}")
    return response.text
```

## Advanced Features

### Token Budgeting & Circuit Breakers
Protect your API credits and prevent cascading failures:

```python
# Agent has built-in budget tracking
if agent.budget.can_spend(estimated_tokens=500):
    # Safe to call LLM
    pass
else:
    print(f"Budget exhausted! Throttled: {agent.budget.snapshot().throttle_reason}")
```

### M2M Commerce ($KERN)
Pay other agents or receive payments for completed tasks:

```python
from kernell_os_sdk import Wallet

with Wallet() as wallet:
    balance = wallet.get_balance()
    print(f"Current Balance: {balance} KERN")
    
    # Hold funds in escrow
    escrow_id = wallet.request_payment_escrow(amount=5.0, task_id="analyze_data", payer_id="agent_123")
    
    # Release on success
    wallet.release_escrow(escrow_id)
```

## Security Posture

Kernell OS SDK is designed for zero-trust environments:
- **Private Keys**: Encrypted at rest using AES-128-CBC and bound to the machine's hardware UDID. Passports cannot be cloned.
- **Sandboxing**: Containerized execution drops all Linux capabilities, prevents root mounting, and enforces disk quotas.
- **Command Execution**: No `shell=True`. Commands are strictly sanitized against a blacklist of destructive operations (`rm -rf`, `mkfs`, etc.).
- **Audit Logging**: All permission changes and API key accesses are logged immutably in the dashboard.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on submitting pull requests, writing tests, and clean code standards.

```bash
# Run tests
pytest tests/ -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.
