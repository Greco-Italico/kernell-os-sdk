# Kernell OS SDK

The complete suite for building and transacting within the Kernell OS ecosystem.

This is a **meta-package** that automatically installs the two core pillars of the Kernell Developer Ecosystem:

1. **`kernell-agent-sdk`**: For building secure, identity-verified autonomous agents with local memory and sandboxed skills.
2. **`kernell-pay-sdk`**: For processing M2M (Machine-to-Machine) payments, programmable escrows, and bounties.

## Installation

To install the complete suite:

```bash
pip install kernell-os-sdk
```

*(This will automatically install both `kernell-agent-sdk` and `kernell-pay-sdk`)*.

## Usage

You can import directly from the sub-packages:

```python
# From the Agent SDK
from kernell_agent_sdk import KernellAgent, LocalMemory
from kernell_agent_sdk.skills import BrowserAutomation

# From the Pay SDK
from kernell_pay_sdk import LedgerClient, EscrowTransaction
```

For detailed documentation, please visit the respective repositories:
- [Kernell Agent SDK](https://github.com/Greco-Italico/kernell-agent-sdk)
- [Kernell Pay SDK](https://github.com/Greco-Italico/kernell-pay-sdk)
