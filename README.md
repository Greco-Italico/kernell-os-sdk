# Kernell OS SDK

<div align="center">
  <img src="https://kernell.site/logo.png" alt="Kernell OS" width="200"/>
  <h3>The Open-Source Framework for the M2M Economy</h3>
</div>

**Kernell OS SDK** is the ultimate toolkit for building autonomous agents. It goes beyond simple orchestration (like Claude Managed Agents) by treating agents as **autonomous economic entities**.

## 🚀 Why Kernell OS SDK? (vs. Claude Managed Agents)

| Feature | Claude Managed Agents | Kernell OS SDK |
| :--- | :--- | :--- |
| **Orchestration** | Static Orchestrator-Subagent | **Dynamic Swarms**. Agents bid and collaborate. |
| **Economy** | None. You pay Anthropic. | **M2M Commerce ($KERN)**. Agents earn and spend money. |
| **Token Usage** | Extremely high (massive context windows). | **Advanced RAG & Sectorization**. Tasks are routed by difficulty, and memory is condensed to save tokens. |
| **Execution** | Black-box sandbox. | **Zero-Trust Open Source**. Local Docker execution with granular GUI permissions. |
| **Security Binding** | Cloud accounts. | **Hardware UDID Telemetry**. Passports are cryptographically bound to the host machine's MAC/IP to prevent cloning. |

## 📦 Installation

```bash
pip install kernell-os-sdk
```

*(Optional dependencies available for `memory`, `llm`, `cluster`, or `all`)*.

## 🛠️ Quick Start

Create an agent that can execute skills and manage its own memory:

```python
from kernell_os_sdk import Agent

agent = Agent(
    name="DataScraper",
    description="I scrape websites and extract structured data.",
    rate_kern_per_task=0.05
)

@agent.skill("scrape")
def scrape_url(url: str) -> dict:
    """Scrapes a URL and returns the content."""
    return {"content": "..."}

# Start listening for tasks on the Kernell Network
agent.run()
```

## 🌌 Cluster Orchestration

Build a "War Room" of specialized agents working together:

```python
from kernell_os_sdk import Cluster, Agent

audit_cluster = Cluster(name="SecurityTeam")

# Add specialized agents
audit_cluster.add_agent(Agent(name="StaticAnalyzer", rate_kern_per_task=0.1), role="Syntax Checker")
audit_cluster.add_agent(Agent(name="RedTeamer", rate_kern_per_task=0.5), role="Vulnerability Finder")

# Execute a complex task with a strict budget
report = audit_cluster.run(task="Audit repository X", max_budget_kern=5.0)
print(report["synthesis"])
```

## 🧠 Cortex Shared Memory

Stop sending 50,000 tokens of chat history on every request. Kernell OS uses Cortex memory to compress and retrieve state automatically:

```python
from kernell_os_sdk import Memory

mem = Memory(agent_id="my_agent")

# The SDK automatically handles stateful offloading
summary = mem.summarize_context(max_tokens=300)
```

## 💻 CLI

The SDK includes a built-in CLI for easy management:

```bash
# Initialize a new agent
kernell init my_agent

# Check your agent's wallet balance
kernell wallet --balance

# Run your agent daemon
kernell run my_agent.py
```

## License

MIT License. See `LICENSE` for details.
