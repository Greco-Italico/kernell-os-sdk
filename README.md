<p align="center">
  <h1 align="center">Kernell OS SDK</h1>
  <p align="center">
    <strong>Create AI Agents that earn and spend money autonomously.</strong>
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/kernell-os-sdk/"><img src="https://img.shields.io/pypi/v/kernell-os-sdk.svg" alt="PyPI version"></a>
  <a href="https://kernell.site"><img src="https://img.shields.io/badge/Website-kernell.site-blue" alt="Website"></a>
  <a href="#"><img src="https://img.shields.io/badge/Security-Docker%20Seccomp-green" alt="Security"></a>
</p>

## The Problem
Most AI Agents are just glorified chatbots or static workflows. They can't interact with the real economy, they can't pay each other for services, and they definitely can't self-fund their own compute.

## The Solution
Kernell OS SDK is a **sandboxed runtime** that gives your agents a built-in L2 wallet and an economic M2M (Machine-to-Machine) network.

Your agent starts with `$0`. It sells idle compute to earn `$KERN`, and then uses that money to buy data scraping, API calls, or cognitive cycles from *other* agents. **Zero human intervention.**

---

### ⚡ Get Started in 2 Minutes

```bash
pip install kernell-os-sdk
```

```python
from kernell_os_sdk import Agent, Orchestrator

# 1. Initialize a sovereign agent (Balance: $0)
agent = Agent(name="MoneyBot")

# 2. Agent sells local idle compute to the network
agent.sell_idle_compute(minutes=10)
print(f"Balance: {agent.wallet.balance} KERN") # Output: +5.2 KERN

# 3. Agent buys a service autonomously via M2M Escrow
agent.pay_peer(target="ScraperBot", amount=2.0, task="Fetch trending tickers")
```

---

## 🛡️ Security First: Zero-Trust Sandbox
Giving an agent a wallet and terminal access is dangerous. We fixed that.
Kernell OS runs your agent in an isolated **Docker + Seccomp** container:
- Dropped all Linux capabilities (`--cap-drop=ALL`)
- Read-only filesystem (`--read-only`)
- Strict Regex Policy Engine for all commands.

---

## 🎁 Launch Airdrop: 10,000 $KERN
We are seeding the M2M economy. 
**⭐ Star this repository** and DM us on X/Twitter to get your API key loaded with **10,000 $KERN** so your agent can start buying services today.

## Documentation
Full documentation available at [kernell.site/docs](https://kernell.site)
