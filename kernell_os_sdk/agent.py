import inspect
import json
import logging
import uuid
from typing import Callable, Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel

from .config import default_config, KernellConfig
from .memory import Memory
from .wallet import Wallet
from .identity import AgentPassport, create_passport, load_passport
from .sandbox import Sandbox, ResourceLimits, AgentPermissions

logger = logging.getLogger("kernell.agent")

class AgentState(BaseModel):
    status: str = "idle"
    tasks_completed: int = 0
    kern_earned: float = 0.0

class Agent:
    """
    The Core Kernell PC Agent.
    Autonomous entity capable of executing tasks, using memory,
    participating in the $KERN M2M economy, and controlling the PC.
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
        config: Optional[KernellConfig] = None
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.rate = rate_kern_per_task
        self.config = config or default_config
        
        # Identity & Passport
        self.storage_path = Path(storage_dir).expanduser() / name.lower().replace(" ", "_")
        self.passport = load_passport(self.storage_path)
        if not self.passport:
            logger.info(f"Creating new cryptographic passport for {name}...")
            self.passport, self._private_key = create_passport(name, storage_dir=self.storage_path)
        
        self.id = self.passport.agent_id
        
        # Core Modules
        self.memory = Memory(agent_id=self.id, config=self.config)
        self.wallet = Wallet(config=self.config)
        
        # PC Container & Permissions
        self.limits = limits or ResourceLimits()
        self.permissions = permissions or AgentPermissions()
        self.sandbox = Sandbox(self.id, self.limits, self.permissions)
        
        self._skills: Dict[str, Callable] = {}
        self._skill_schemas: List[Dict[str, Any]] = []
        self.state = AgentState()
        
        # Register default Computer Use skills if enabled
        if self.permissions.gui_automation or self.permissions.execute_commands:
            self._register_computer_use_skills()
        
        logger.info(f"Initialized Agent '{self.name}'")
        logger.info(f"Passport ID: {self.id} | KAP: {self.passport.kap_address}")
        logger.info(f"Dual Wallet | Volatile: {self.passport.kern_volatile_address} | SOL: {self.passport.kern_solana_address or 'Pending Bridge'}")

    def _register_computer_use_skills(self):
        """Registers native PC control skills (Computer Use)."""
        @self.skill("execute_bash", "Execute a bash command on the host (if permitted).")
        def execute_bash(command: str) -> str:
            if not self.permissions.execute_commands:
                return "Error: Command execution permission is disabled."
            import subprocess
            res = subprocess.run(command, shell=True, capture_output=True, text=True)
            return res.stdout if res.returncode == 0 else res.stderr

        @self.skill("mouse_click", "Click a specific coordinate on the screen.")
        def mouse_click(x: int, y: int) -> str:
            if not self.permissions.gui_automation:
                return "Error: GUI automation permission is disabled."
            return f"Clicked at ({x}, {y})"

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
            
            self._skills[skill_name] = func
            self._skill_schemas.append(schema)
            return func
        return decorator

    def toggle_permission(self, permission: str, state: bool):
        """Runtime switch to turn permissions ON/OFF dynamically via GUI."""
        if hasattr(self.permissions, permission):
            setattr(self.permissions, permission, state)
            logger.info(f"Permission '{permission}' set to {state}")
            # In a full implementation, this triggers a dynamic Docker update or proxy rule
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

    def run(self):
        """Starts the agent daemon."""
        logger.info(f"Agent {self.name} is live.")
