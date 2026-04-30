"""
Kernell OS SDK — Agent Runtime (Phase 5)
═════════════════════════════════════════
Autonomous agent loop with planning, memory, tools, and execution.

This is the bridge between "infrastructure that runs code" and
"system that pursues goals autonomously" — the key gap vs Computer Use.

Architecture:
    Agent
      ├── Planner          (decides what to do next)
      ├── MemoryStore       (persistent state across steps)
      ├── ToolRegistry      (callable capabilities)
      ├── AgentLoop         (think → act → observe → refine)
      └── Executor          (CodePipeline → FormalVerifier → ExecutionGate)

Usage:
    from kernell_os_sdk.agent_runtime import (
        Agent, MemoryStore, ToolRegistry, Tool, AgentConfig
    )

    memory = MemoryStore()
    tools = ToolRegistry()
    tools.register(Tool("calculator", lambda expr: str(eval(expr)), "Evaluate math"))

    agent = Agent(
        llm_registry=my_registry,
        memory=memory,
        tools=tools,
    )

    result = agent.run("Calculate the compound interest on $1000 at 5% for 10 years")
    print(result.final_answer)
    print(result.steps_taken)
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
import uuid

from kernell_os_sdk.agent_persistence import (
    CheckpointManager, AgentStateSnapshot, TaskStatus
)
from kernell_os_sdk.agent_validation import ToolValidator

logger = logging.getLogger("kernell.agent")


# ══════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════

@dataclass
class MemoryItem:
    """A single memory entry with metadata."""
    key: str
    value: Any
    timestamp: float
    step: int = 0
    source: str = ""  # "tool", "code", "observation", "user"


class MemoryStore:
    """
    Persistent agent memory. Survives across steps and tasks.
    MVP: in-memory dict. Pluggable to Redis/SQLite/vector DB.
    """

    def __init__(self):
        self._store: Dict[str, MemoryItem] = {}
        self._history: List[MemoryItem] = []  # Append-only timeline

    def remember(self, key: str, value: Any, source: str = "", step: int = 0):
        """Store a key-value pair in memory."""
        item = MemoryItem(
            key=key, value=value, timestamp=time.time(),
            step=step, source=source,
        )
        self._store[key] = item
        self._history.append(item)

    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from memory."""
        item = self._store.get(key)
        return item.value if item else default

    def search(self, prefix: str) -> Dict[str, Any]:
        """Find all memories matching a key prefix."""
        return {k: v.value for k, v in self._store.items() if k.startswith(prefix)}

    def dump(self) -> Dict[str, Any]:
        """Get all current memory as a flat dict."""
        return {k: v.value for k, v in self._store.items()}

    def timeline(self, last_n: int = 10) -> List[Dict]:
        """Get the last N memory operations."""
        return [
            {"key": m.key, "value": str(m.value)[:200], "source": m.source, "step": m.step}
            for m in self._history[-last_n:]
        ]

    def clear(self):
        """Reset all memory."""
        self._store.clear()
        self._history.clear()

    def __len__(self):
        return len(self._store)

    def __contains__(self, key: str):
        return key in self._store


# ══════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    """A callable tool available to the agent."""
    name: str
    func: Callable
    description: str
    parameters: Optional[Dict[str, str]] = None  # param_name → description

    def __call__(self, **kwargs):
        return self.func(**kwargs)


class ToolRegistry:
    """Registry of tools the agent can use."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] Registered: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """Get tool names and descriptions for the planner."""
        return {name: t.description for name, t in self._tools.items()}

    def list_tools_detailed(self) -> str:
        """Formatted tool descriptions for LLM prompts."""
        parts = []
        for name, tool in self._tools.items():
            params = ""
            if tool.parameters:
                params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
                params = f" (params: {params})"
            parts.append(f"  - {name}: {tool.description}{params}")
        return "\n".join(parts) if parts else "  (no tools registered)"

    def __len__(self):
        return len(self._tools)

    def __contains__(self, name: str):
        return name in self._tools


# ══════════════════════════════════════════════════════════════════════
# STEP / ACTION TYPES
# ══════════════════════════════════════════════════════════════════════

class ActionType(str, Enum):
    THINK = "think"       # Pure reasoning, no side effects
    CODE = "code"         # Generate and execute code
    TOOL = "tool"         # Call a registered tool
    ANSWER = "answer"     # Final answer to the user
    MEMORY = "memory"     # Store/recall from memory


@dataclass
class StepPlan:
    """A single planned action."""
    action: ActionType
    description: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    code_task: str = ""
    answer: str = ""
    memory_key: str = ""
    memory_value: Any = None
    expected_outcome: str = ""


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_idx: int
    action: ActionType
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


# ══════════════════════════════════════════════════════════════════════
# AGENT CONFIG
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    max_steps: int = 10
    max_think_tokens: int = 2048
    max_code_tokens: int = 4096
    planning_temperature: float = 0.3
    planning_role: str = "reasoning"
    enable_code_execution: bool = True
    enable_tools: bool = True


# ══════════════════════════════════════════════════════════════════════
# AGENT RESULT
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AgentResult:
    """Complete result of an agent run."""
    goal: str
    final_answer: str = ""
    success: bool = False
    steps_taken: int = 0
    step_results: List[StepResult] = field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════
# PLANNER PROMPT
# ══════════════════════════════════════════════════════════════════════

PLANNER_SYSTEM = """You are an autonomous agent planner. Given a goal, current memory, available tools, and previous step results, decide the NEXT SINGLE action to take.

You MUST respond with valid JSON only. No markdown, no explanation outside JSON.

Action types:
- "think": Reason about the problem (no side effects). Use this to analyze before acting.
- "code": Generate Python code to execute. Specify the task description.
- "tool": Call a registered tool by name with arguments.
- "answer": Provide the final answer. Use this when the goal is achieved.
- "memory": Store a value for later use.

Response format:
{
  "action": "think|code|tool|answer|memory",
  "reasoning": "why this action",
  "description": "what this step does",
  "tool_name": "name (if action=tool)",
  "tool_args": {"key": "value"} (if action=tool),
  "code_task": "task description (if action=code)",
  "answer": "final answer text (if action=answer)",
  "memory_key": "key (if action=memory)",
  "memory_value": "value (if action=memory)",
  "expected_outcome": "what should visually/technically happen as a result (for tool/code)"
}

Rules:
- Take ONE action at a time
- Use "think" first if the problem needs analysis
- Use "answer" when you have enough information to respond
- If you're stuck after multiple attempts, use "answer" with what you have
- NEVER loop indefinitely — converge to an answer"""


# ══════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════

class Agent:
    """
    Autonomous agent with plan-act-observe loop.
    Integrates all SDK components: LLM Registry, CodePipeline,
    FormalVerifier, ExecutionGate, EconomicEngine.
    """

    def __init__(
        self,
        llm_registry,
        memory: Optional[MemoryStore] = None,
        tools: Optional[ToolRegistry] = None,
        config: Optional[AgentConfig] = None,
        code_pipeline=None,
        verifier=None,
        execution_gate=None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self._registry = llm_registry
        self.memory = memory or MemoryStore()
        self.tools = tools or ToolRegistry()
        self.config = config or AgentConfig()
        self._pipeline = code_pipeline
        self._verifier = verifier
        self._gate = execution_gate
        self._checkpoint_manager = checkpoint_manager
        self._validator = ToolValidator(llm_registry)

    def run(self, goal: str, session_id: Optional[str] = None) -> AgentResult:
        """
        Execute the agent loop for a given goal.
        If session_id is provided and a checkpoint exists, the agent will resume from it.
        Loop: plan → execute → observe → refine → repeat until answer or max_steps.
        """
        t0 = time.time()
        
        # ── Phase 5.5: Task Recovery ──────────────────────────────
        session_id = session_id or str(uuid.uuid4())
        start_step = 0
        step_history: List[Dict] = []
        
        if self._checkpoint_manager:
            checkpoint = self._checkpoint_manager.load_checkpoint(session_id)
            if checkpoint:
                logger.info(f"[Agent] Resuming session {session_id} from step {checkpoint.current_step}")
                goal = checkpoint.goal  # Ensure goal matches
                start_step = checkpoint.current_step
                step_history = checkpoint.history
                
                # Restore memory
                self.memory.clear()
                for k, v in checkpoint.memory_dump.items():
                    self.memory.remember(k, v, source="checkpoint")
                    
                if checkpoint.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    logger.warning(f"[Agent] Session {session_id} is already {checkpoint.status.value}")
                    return AgentResult(
                        goal=goal, success=(checkpoint.status == TaskStatus.COMPLETED),
                        steps_taken=start_step, memory_snapshot=self.memory.dump()
                    )

        result = AgentResult(goal=goal)
        logger.info(f"[Agent] Starting/Resuming: {goal[:100]} (session: {session_id})")

        for step_idx in range(start_step, self.config.max_steps):
            # ── Plan next action ─────────────────────────────────
            plan = self._plan_next(goal, step_history)

            if plan is None:
                result.final_answer = "Planning failed — could not determine next action"
                self._save_checkpoint(session_id, goal, step_idx, step_history, TaskStatus.FAILED)
                break

            # ── Execute the action ───────────────────────────────
            step_result = self._execute_step(step_idx, plan)
            result.step_results.append(step_result)
            result.steps_taken = step_idx + 1

            # Record in history for next planning iteration
            step_history.append({
                "step": step_idx,
                "action": plan.action.value,
                "description": plan.description,
                "output": step_result.output[:500],
                "success": step_result.success,
                "error": step_result.error,
            })

            # ── Check for completion ─────────────────────────────
            if plan.action == ActionType.ANSWER:
                result.final_answer = plan.answer or step_result.output
                result.success = True
                self._save_checkpoint(session_id, goal, step_idx + 1, step_history, TaskStatus.COMPLETED)
                break

            # ── Safety: detect spinning ──────────────────────────
            if len(step_history) >= 3:
                last_actions = [h["action"] for h in step_history[-3:]]
                if len(set(last_actions)) == 1 and last_actions[0] == "think":
                    logger.warning("[Agent] Detected thinking loop — forcing answer")
                    result.final_answer = self._force_answer(goal, step_history)
                    result.success = True
                    self._save_checkpoint(session_id, goal, step_idx + 1, step_history, TaskStatus.COMPLETED)
                    break
                    
            # ── Phase 5.5: Save state after step ─────────────────
            self._save_checkpoint(session_id, goal, step_idx + 1, step_history, TaskStatus.RUNNING)

        if not result.final_answer and step_history:
            result.final_answer = self._force_answer(goal, step_history)
            result.success = True
            self._save_checkpoint(session_id, goal, self.config.max_steps, step_history, TaskStatus.COMPLETED)

        result.total_duration_ms = round((time.time() - t0) * 1000, 1)
        result.memory_snapshot = self.memory.dump()

        logger.info(
            f"[Agent] Complete: {result.steps_taken} steps, "
            f"{result.total_duration_ms}ms, success={result.success}"
        )
        return result

    # ── Planning ─────────────────────────────────────────────────────

    def _plan_next(self, goal: str, history: List[Dict]) -> Optional[StepPlan]:
        """Ask the LLM to plan the next action."""
        context_parts = [f"GOAL: {goal}"]

        # Memory context
        mem = self.memory.dump()
        if mem:
            context_parts.append(f"CURRENT MEMORY:\n{json.dumps(mem, default=str)[:1000]}")

        # Tools context
        if self.tools and len(self.tools) > 0:
            context_parts.append(f"AVAILABLE TOOLS:\n{self.tools.list_tools_detailed()}")
        else:
            context_parts.append("AVAILABLE TOOLS: none")

        # Code execution capability
        if self.config.enable_code_execution:
            context_parts.append("CODE EXECUTION: enabled (Python sandbox)")

        # Previous steps
        if history:
            hist_str = json.dumps(history[-5:], default=str)[:2000]  # Last 5 steps
            context_parts.append(f"PREVIOUS STEPS:\n{hist_str}")

        prompt = "\n\n".join(context_parts)

        resp = self._registry.complete(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=PLANNER_SYSTEM,
            role=self.config.planning_role,
            max_tokens=self.config.max_think_tokens,
            temperature=self.config.planning_temperature,
        )

        if not resp:
            return None

        return self._parse_plan(resp.content)

    def _parse_plan(self, content: str) -> Optional[StepPlan]:
        """Parse the LLM's JSON response into a StepPlan."""
        # Try to extract JSON from the response
        text = content.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: treat entire response as a think step
            return StepPlan(action=ActionType.THINK, description=content[:500])

        action_str = data.get("action", "think")
        try:
            action = ActionType(action_str)
        except ValueError:
            action = ActionType.THINK

        return StepPlan(
            action=action,
            description=data.get("description", data.get("reasoning", "")),
            tool_name=data.get("tool_name", ""),
            tool_args=data.get("tool_args", {}),
            code_task=data.get("code_task", ""),
            answer=data.get("answer", ""),
            memory_key=data.get("memory_key", ""),
            memory_value=data.get("memory_value"),
            expected_outcome=data.get("expected_outcome", ""),
        )

    # ── Step Execution ───────────────────────────────────────────────

    def _execute_step(self, step_idx: int, plan: StepPlan) -> StepResult:
        """Execute a single planned step."""
        t0 = time.time()

        if plan.action == ActionType.THINK:
            return StepResult(
                step_idx=step_idx, action=plan.action, success=True,
                output=plan.description,
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

        elif plan.action == ActionType.TOOL:
            return self._execute_tool(step_idx, plan)

        elif plan.action == ActionType.CODE:
            return self._execute_code(step_idx, plan)

        elif plan.action == ActionType.MEMORY:
            self.memory.remember(
                plan.memory_key, plan.memory_value,
                source="agent", step=step_idx,
            )
            return StepResult(
                step_idx=step_idx, action=plan.action, success=True,
                output=f"Stored '{plan.memory_key}'",
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

        elif plan.action == ActionType.ANSWER:
            return StepResult(
                step_idx=step_idx, action=plan.action, success=True,
                output=plan.answer,
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

        return StepResult(
            step_idx=step_idx, action=plan.action, success=False,
            error=f"Unknown action: {plan.action}",
        )

    def _execute_tool(self, step_idx: int, plan: StepPlan) -> StepResult:
        """Execute a tool call."""
        t0 = time.time()
        tool = self.tools.get(plan.tool_name)

        if not tool:
            return StepResult(
                step_idx=step_idx, action=ActionType.TOOL, success=False,
                error=f"Tool not found: {plan.tool_name}",
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

        try:
            output = tool(**plan.tool_args)
            output_str = str(output)[:5000]
            
            # Phase 5.6: Validate expectation
            if plan.expected_outcome:
                val_result = self._validator.validate(plan.expected_outcome, output_str)
                if not val_result.is_valid:
                    output_str += f"\n\n[VALIDATION FAILED] The expectation was NOT met: {val_result.reason}"
            
            self.memory.remember(
                f"tool:{plan.tool_name}:result",
                output_str, source="tool", step=step_idx,
            )
            return StepResult(
                step_idx=step_idx, action=ActionType.TOOL, success=True,
                output=output_str,
                duration_ms=round((time.time() - t0) * 1000, 1),
            )
        except Exception as e:
            return StepResult(
                step_idx=step_idx, action=ActionType.TOOL, success=False,
                error=f"{type(e).__name__}: {e}",
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    def _execute_code(self, step_idx: int, plan: StepPlan) -> StepResult:
        """Execute code via the full pipeline: CodePipeline → Verifier → Gate."""
        t0 = time.time()

        if not self.config.enable_code_execution:
            return StepResult(
                step_idx=step_idx, action=ActionType.CODE, success=False,
                error="Code execution disabled by config",
            )

        # If we have the full pipeline, use it
        if self._pipeline:
            pipe_result = self._pipeline.run(task=plan.code_task)
            if not pipe_result.success:
                return StepResult(
                    step_idx=step_idx, action=ActionType.CODE, success=False,
                    error="CodePipeline failed",
                    duration_ms=round((time.time() - t0) * 1000, 1),
                )
            code = pipe_result.final_code
        else:
            # Fallback: ask LLM directly for code
            resp = self._registry.complete(
                messages=[{"role": "user", "content": f"Write Python code for: {plan.code_task}\nOutput ONLY the code, no explanations."}],
                system_prompt="You are a Python programmer. Output only executable Python code.",
                role="implementer",
                max_tokens=self.config.max_code_tokens,
                temperature=0.2,
            )
            if not resp:
                return StepResult(
                    step_idx=step_idx, action=ActionType.CODE, success=False,
                    error="LLM failed to generate code",
                )
            code = resp.content
            # Strip markdown code blocks
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

        # Verify if verifier available
        if self._verifier:
            vr = self._verifier.verify(code)
            if not vr.passed:
                return StepResult(
                    step_idx=step_idx, action=ActionType.CODE, success=False,
                    error=f"Verification blocked: {len(vr.violations)} violations",
                    duration_ms=round((time.time() - t0) * 1000, 1),
                )

        # Execute via gate or direct
        if self._gate:
            exec_result = self._gate.execute(code)
            output = exec_result.stdout if exec_result.success else (exec_result.error or "")
            self.memory.remember(
                f"code:step{step_idx}:result",
                output, source="code", step=step_idx,
            )
            return StepResult(
                step_idx=step_idx, action=ActionType.CODE,
                success=exec_result.success,
                output=output[:5000],
                error=exec_result.error or "",
                duration_ms=round((time.time() - t0) * 1000, 1),
            )
        else:
            # No gate — return code as output (dry run)
            self.memory.remember(
                f"code:step{step_idx}:generated",
                code[:2000], source="code", step=step_idx,
            )
            return StepResult(
                step_idx=step_idx, action=ActionType.CODE, success=True,
                output=f"[Code generated, no execution gate]\n{code[:2000]}",
                duration_ms=round((time.time() - t0) * 1000, 1),
            )

    # ── Forced Answer ────────────────────────────────────────────────

    def _force_answer(self, goal: str, history: List[Dict]) -> str:
        """Force a final answer when the agent is stuck or at max steps."""
        context = (
            f"GOAL: {goal}\n\n"
            f"MEMORY: {json.dumps(self.memory.dump(), default=str)[:1500]}\n\n"
            f"STEPS TAKEN: {json.dumps(history[-5:], default=str)[:1500]}\n\n"
            "Based on everything above, provide your BEST final answer now."
        )
        resp = self._registry.complete(
            messages=[{"role": "user", "content": context}],
            system_prompt="Synthesize all available information into a clear, complete answer.",
            role="default",
            max_tokens=2048,
        )
        return resp.content if resp else "Unable to produce answer"

    # ── Persistence ──────────────────────────────────────────────────

    def _save_checkpoint(self, session_id: str, goal: str, step: int, history: List[Dict], status: TaskStatus):
        """Save the agent's current state if checkpoint manager is enabled."""
        if not self._checkpoint_manager:
            return
            
        state = AgentStateSnapshot(
            session_id=session_id,
            goal=goal,
            status=status,
            current_step=step,
            memory_dump=self.memory.dump(),
            history=history,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._checkpoint_manager.save_checkpoint(state)
