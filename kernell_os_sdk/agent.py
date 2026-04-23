import inspect
import json
import shlex
import uuid
import time
from typing import Callable, Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel, validate_call
import structlog

from .config import default_config, KernellConfig
from .memory import Memory
from .wallet import Wallet
from .adapters import OpenInterpreterAdapter, AnthropicGUIAdapter, M2MAdapter, CapabilityRouter
from .identity import (
    AgentPassport, create_passport, load_passport,
    load_private_key, SecurityError
)
from .sandbox import Sandbox, ResourceLimits, AgentPermissions
from .budget import TokenBudget
from .health import SLOMonitor
from .constants import VALID_PERMISSIONS
from .llm import BaseLLMProvider, LLMMessage
from .policy_engine import PolicyEngine, AgentCapabilities
from .risk_engine import RiskEngine, ExecutionContext, ActionTag, DataSensitivity
from .execution_gate import ExecutionGate, ApprovalSignature
from .security.rate_limiter import RateLimitGovernor, RateLimitExceeded

logger = structlog.get_logger("kernell.agent")

class A2AMessage(BaseModel):
    """Cryptographically signed Inter-Agent message with Taint Propagation."""
    sender_id: str
    target_id: str
    payload: str
    sensitivity: DataSensitivity
    signature: bytes
    timestamp: float


class AgentState(BaseModel):
    status: str = "idle"
    tasks_completed: int = 0
    kern_earned: float = 0.0


class Agent:
    """
    The Core Kernell PC Agent.
    Autonomous entity capable of executing tasks, using memory,
    participating in the $KERN M2M economy, and controlling the PC.

    Security features:
      - Shell injection prevention (no shell=True)
      - Command blacklisting
      - Permission name whitelisting
      - UDID-bound passport with encrypted private key
    """
    def __init__(
        self,
        name: str,
        description: str = "",
        system_prompt: str = "You are a highly capable Kernell OS autonomous agent.",
        rate_kern_per_task: float = 0.0,
        storage_dir: str = "~/.kernell/agents",
        limits: Optional[ResourceLimits] = None,
        permissions: Optional[AgentPermissions] = None,
        capabilities: Optional[AgentCapabilities] = None,
        config: Optional[KernellConfig] = None,
        engine: Optional['BaseLLMProvider'] = None,  # Support for custom LLM engines
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.rate = rate_kern_per_task
        self.config = config or default_config
        self.engine = engine

        # Identity & Passport
        self.storage_path = Path(storage_dir).expanduser() / name.lower().replace(" ", "_")

        try:
            self.passport = load_passport(self.storage_path)
        except SecurityError as e:
            logger.critical("security_violation", error=str(e), agent_name=name)
            raise

        if not self.passport:
            logger.info("creating_new_passport", agent_name=name)
            self.passport, self._private_key = create_passport(name, storage_dir=self.storage_path)
        else:
            # Load the encrypted private key
            self._private_key = load_private_key(self.storage_path)
            if not self._private_key:
                logger.warning("private_key_not_found", agent_name=name)

        self.id = self.passport.agent_id

        # Core Modules
        self.memory = Memory(agent_id=self.id, config=self.config)
        self.wallet = Wallet(config=self.config)
        
        # Capability Layer (Adapters)
        self.adapters = {
            "terminal": OpenInterpreterAdapter(self.sandbox) if hasattr(self, "sandbox") else None,
            "gui": AnthropicGUIAdapter(),
            "m2m": M2MAdapter(self)
        }
        self.router = CapabilityRouter(self.adapters, self.wallet)

        # PC Container & Permissions
        self.limits = limits or ResourceLimits()
        self.permissions = permissions or AgentPermissions()
        self.sandbox = Sandbox(self.id, self.limits, self.permissions)
        self.adapters["terminal"] = OpenInterpreterAdapter(self.sandbox)

        self._skills: Dict[str, Callable] = {}
        self._skill_schemas: List[Dict[str, Any]] = []
        self.state = AgentState()

        # Policy Engine (capability-based security boundary)
        self.capabilities = capabilities or AgentCapabilities()
        self.policy = PolicyEngine(self.capabilities)

        # Multi-Layer Execution Authority (Paranoid Mode)
        self.execution_context = ExecutionContext()
        self.risk_engine = RiskEngine()
        self.execution_gate = ExecutionGate(required_signatures=2, timelock_seconds=30)

        # Observability
        self.budget = TokenBudget(agent_name=self.name)
        self.slo = SLOMonitor(agent_name=self.name)

        # Rate Limiting & Circuit Breakers (singleton)
        self.governor = RateLimitGovernor()

        # Register default Computer Use skills if enabled
        if self.permissions.gui_automation or self.permissions.execute_commands:
            self._register_computer_use_skills()

        logger.info("agent_initialized", agent_name=self.name, agent_id=self.id, kap_address=self.passport.kap_address)
        logger.info("wallet_status", volatile_address=self.passport.kern_volatile_address, solana_address=self.passport.kern_solana_address or "pending")

    def _is_command_safe(self, command: str) -> bool:
        """
        Capability-based command validation via the formal PolicyEngine.

        This is the security boundary between the LLM planner and system execution.
        All commands, arguments, network egress, filesystem access, and code
        semantics are validated against the agent's AgentCapabilities manifest.
        """
        result = self.policy.validate(command)
        if not result.allowed:
            logger.warning(
                "policy_engine_denied",
                command=command[:80],
                reason=result.reason,
            )
        return result.allowed

    def _register_computer_use_skills(self):
        """Registers native PC control skills (Computer Use)."""
        @self.skill("execute_bash", "Ejecuta un comando bash seguro dentro del sandbox.")
        def execute_bash(command: str) -> str:
            if not self.permissions.execute_commands:
                return "Error: permiso 'execute_commands' está deshabilitado."

            # Rate limit check
            try:
                self.governor.check_skill_call(self.id, "execute_bash")
            except RateLimitExceeded as e:
                return f"Error: [RATE_LIMIT] {e}"

            # PolicyEngine validates command, args, network, filesystem, and semantics
            # Crucially, we pass the current taint status to block exfiltration
            is_tainted = self.execution_context.holds_sensitive_data
            result = self.policy.validate(command, is_tainted=is_tainted)
            if not result.allowed:
                logger.warning(
                    "execute_bash_denied",
                    command=command[:80],
                    reason=result.reason,
                )
                return f"Error: [POLICY] {result.reason}"

            # Multi-Layer Execution Authority
            risk = self.risk_engine.evaluate(command, self.execution_context)

            # Cross-Layer Consistency Check (catches desync edge cases)
            if not self.risk_engine.cross_layer_verify(result.allowed, risk, command):
                return f"Error: [CROSS_LAYER] Risk override blocked '{command[:40]}' despite policy approval."

            if not self.execution_gate.approve(command, risk):
                return f"Error: [EXECUTION_GATE] CRITICAL action denied. Missing Multi-Sig or Oracle approval."

            import subprocess
            try:
                container = self.sandbox.container_name
                args = ["docker", "exec", "--", container] + shlex.split(command)
                res = subprocess.run(
                    args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=self.capabilities.max_cpu_seconds,
                )
                # Enforce output size cap (anti-exfiltration)
                stdout = res.stdout[:self.capabilities.max_output_bytes]
                
                # Context Tagging (Taint Tracking)
                sensitivity = DataSensitivity.PUBLIC
                # If command reads files or was already tainted, mark context as holding sensitive data
                if "cat " in command or "grep " in command or "ls " in command or "tree " in command:
                    sensitivity = DataSensitivity.INTERNAL
                    self.execution_context.holds_sensitive_data = True
                
                self.execution_context.record_action(ActionTag(
                    command=command,
                    timestamp=time.time(),
                    bytes_processed=len(stdout),
                    sensitivity=sensitivity
                ))
                
                if res.returncode == 0:
                    return stdout
                return f"Error (exit {res.returncode}): {res.stderr[:2000]}"
            except subprocess.TimeoutExpired:
                return f"Error: Comando expiró después de {self.capabilities.max_cpu_seconds} segundos."
            except Exception as e:
                return f"Error inesperado: {str(e)[:500]}"

        @self.skill("mouse_click", "Click a specific coordinate on the screen.")
        def mouse_click(x: int, y: int) -> str:
            if not self.permissions.gui_automation:
                return "Error: GUI automation permission is disabled."
            return f"Clicked at ({x}, {y})"

        @self.skill("send_a2a_message", "Sends a cryptographically signed message to another agent.")
        def send_a2a_message(target_id: str, payload: str) -> str:
            if not self.permissions.network_access:
                return "Error: Network access disabled."
                
            # Distribute Taint: Message inherits agent's current highest sensitivity
            msg_sensitivity = DataSensitivity.PUBLIC
            if self.execution_context.holds_sensitive_data:
                msg_sensitivity = DataSensitivity.INTERNAL

            import time
            from nacl.signing import SigningKey
            from nacl.encoding import Base64Encoder

            # Sign payload + sensitivity
            if not self._private_key:
                return "Error: clave privada no disponible. No se puede firmar."

            import binascii
            raw_msg = f"{target_id}:{payload}:{msg_sensitivity.value}:{time.time()}".encode()
            sk = SigningKey(binascii.unhexlify(self._private_key))
            signature = sk.sign(raw_msg).signature

            # Build A2A Message
            msg = A2AMessage(
                sender_id=self.name,
                target_id=target_id,
                payload=payload,
                sensitivity=msg_sensitivity,
                signature=signature,
                timestamp=time.time()
            )
            
            # Simulated network dispatch...
            logger.info("a2a_message_dispatched", target=target_id, sensitivity=msg_sensitivity.name)
            return f"Message sent securely to {target_id}."

        # Sub-Agent Delegation
        self._delegation_manager = None

    def sell_idle_compute(self, minutes: int):
        """Mock method for GTM Demo: Agent sells compute and earns KERN."""
        import time
        from kernell_os_sdk.security.ssrf import create_safe_client
        earned = minutes * 0.52
        self.wallet.credit(earned)
        logger.info(f"Earned {earned} KERN selling idle compute.")

        try:
            self.governor.check_webhook(self.id)
        except RateLimitExceeded:
            return earned  # Silently skip webhook if rate limited
        
        try:
            with create_safe_client(agent_id=self.id, timeout=2.0) as client:
                client.post("http://localhost:8000/event", json={
                    "type": "EARN",
                    "agent_id": self.id,
                    "payload": {
                        "amount": earned,
                        "source": "idle_compute",
                        "minutes": minutes
                    }
                })
        except Exception as e:
            pass
        return earned

    def pay_peer(self, target: str, amount: float, task: str):
        """Mock method for GTM Demo: Agent pays another agent for a task via Escrow."""
        import time
        from kernell_os_sdk.security.ssrf import create_safe_client
        if not self.wallet.debit(amount):
            logger.error("Insufficient KERN to pay peer.")
            return False
            
        logger.info(f"Paid {amount} KERN to {target} for: {task}")
        
        try:
            with create_safe_client(agent_id=self.id, timeout=2.0) as client:
                client.post("http://localhost:8000/event", json={
                    "type": "SPEND",
                    "agent_id": self.id,
                    "payload": {
                        "amount": amount,
                        "target": target,
                        "task": task
                    }
                })
        except Exception as e:
            pass
        return True

    def receive_a2a_message(self, message: A2AMessage) -> bool:
        """Processes incoming A2A messages and forces Taint Propagation."""
        # Signature validation would go here
        
        # OBLIGATORY TAINT PROPAGATION:
        # If the incoming message is tainted, this agent becomes tainted.
        if message.sensitivity > DataSensitivity.PUBLIC:
            logger.warning(
                "agent_tainted_by_a2a",
                sender=message.sender_id,
                sensitivity=message.sensitivity.name
            )
            self.execution_context.holds_sensitive_data = True
            
        return True

    def enable_delegation(self, max_workers: int, worker_engine: 'BaseLLMProvider', timeout: float = 60.0):
        """Enable local sub-agent delegation."""
        from .delegation import SubAgentManager
        self._delegation_manager = SubAgentManager(self)
        self._delegation_manager.enable(max_workers=max_workers, worker_engine=worker_engine, timeout=timeout)

    def disable_delegation(self):
        """Disable local sub-agent delegation."""
        if self._delegation_manager:
            self._delegation_manager.disable()

    def delegate_batch(self, tasks: list[str], max_concurrent: int = None) -> list[str]:
        """Delegate a batch of tasks to the local sub-agent swarm."""
        if not self._delegation_manager or not self._delegation_manager.is_enabled():
            raise RuntimeError("Delegation is not enabled. Call enable_delegation() first.")
        return self._delegation_manager.execute_batch(tasks, max_concurrent)

    def skill(self, name: str = None, description: str = None):
        """Decorator to register a custom skill (tool) for the agent."""
        def decorator(func: Callable):
            skill_name = name or func.__name__
            skill_desc = description or func.__doc__ or f"Execute {skill_name}"

            sig = inspect.signature(func)
            props = {}
            required = []

            for param_name, param in sig.parameters.items():
                param_type = "string"
                if param.annotation == int: param_type = "integer"
                elif param.annotation == float: param_type = "number"
                elif param.annotation == bool: param_type = "boolean"

                props[param_name] = {"type": param_type}
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schema = {
                "name": skill_name,
                "description": skill_desc,
                "input_schema": {
                    "type": "object",
                    "properties": props,
                    "required": required
                }
            }

            validated_func = validate_call(func)
            self._skills[skill_name] = validated_func
            self._skill_schemas.append(schema)
            return validated_func
        return decorator

    def toggle_permission(self, permission: str, state: bool):
        """Runtime switch to turn permissions ON/OFF dynamically via GUI."""
        # SECURITY: Whitelist-only permission names
        if permission not in VALID_PERMISSIONS:
            logger.error(f"[SECURITY] Rejected invalid permission name: {permission}")
            return

        if hasattr(self.permissions, permission):
            setattr(self.permissions, permission, state)
            logger.info(f"[AUDIT] Permission '{permission}' set to {state}")
        else:
            logger.error(f"Unknown permission: {permission}")

    def _estimate_difficulty(self, task: str) -> str:
        """Heuristic to determine task difficulty to save tokens (Sectorization)."""
        length = len(task.split())
        if length < 10 and "analyze" not in task.lower():
            return "easy" # Route to Llama-3-8B or Haiku
        elif length < 50:
            return "medium" # Route to Claude 3.5 Haiku / Sonnet
        else:
            return "hard" # Route to Opus or deep thinking models

    def prompt(self, task: str) -> str:
        """Executes a task with Advanced RAG and Task Sectorization."""
        self.state.status = "working"

        if not self.permissions.network_access:
            logger.warning("Network access disabled. Agent is running in offline local LLM mode.")

        # Task Sectorization: Route by difficulty to save tokens
        difficulty = self._estimate_difficulty(task)
        logger.info(f"Task Sectorization: '{task[:20]}...' classified as {difficulty.upper()} difficulty.")

        # Advanced RAG: Condense context instead of appending everything
        context = self.memory.summarize_context(max_tokens=300)
        self.memory.add_episodic("task_started", {"task": task, "difficulty": difficulty})

        # TODO: Route to appropriate model based on 'difficulty'
        response = f"[Execution output for '{task}'. Model: {difficulty}_tier. Skills: {list(self._skills.keys())}]"

        self.state.tasks_completed += 1
        self.state.status = "idle"
        self.memory.add_episodic("task_completed", {"task": task, "status": "success"})

        return response

    def install(self):
        """Builds the container and sets up the environment."""
        self.sandbox.start()

    def run(self, task: str = None):
        """
        Universal entry point. 
        If task is given, it analyzes and routes via the Capability Layer (Adapters).
        If none, it starts the idle daemon.
        """
        if not task:
            logger.info(f"Agent {self.name} is live in daemon mode.")
            return

        logger.info(f"Agent {self.name} routing task via CapabilityRouter: {task[:50]}")
        
        context = {
            "execution_context": self.execution_context,
            "policy_engine": self.policy
        }
        
        result = self.router.route_and_execute(task, context)
        
        # Dispatch event for Moltbook Feed if an adapter was used
        if result.get("used_adapter") and result.get("used_adapter") != "none":
            try:
                from kernell_os_sdk.security.ssrf import create_safe_client
                with create_safe_client(agent_id=self.id, timeout=2.0) as client:
                    client.post("http://localhost:8000/event", json={
                    "type": "ADAPTER_USE",
                    "agent_id": self.id,
                    "payload": {
                        "adapter": result["used_adapter"],
                        "task": task[:100],
                        "status": result.get("status")
                    }
                }, timeout=2)
            except Exception:
                pass
                
        return result

    def shutdown(self):
        """Graceful shutdown: stop sandbox, close wallet, flush memory."""
        logger.info(f"Shutting down agent {self.name}...")
        self.sandbox.stop()
        self.wallet.close()
        logger.info(f"Agent {self.name} stopped.")
