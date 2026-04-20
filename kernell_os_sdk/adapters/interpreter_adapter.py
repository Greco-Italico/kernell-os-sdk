import subprocess
import shlex
from typing import Dict, Any
from .base import BaseAdapter
import structlog

logger = structlog.get_logger("kernell.adapters.interpreter")

class OpenInterpreterAdapter(BaseAdapter):
    """
    Adapter that absorbs Open Interpreter style functionality.
    Executes code in the secure Docker/Seccomp sandbox.
    """
    capability_name = "terminal_execution"

    def __init__(self, sandbox):
        self.sandbox = sandbox

    def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("interpreter_executing", task=task[:50])
        
        # PolicyEngine is MANDATORY — never execute without validation
        policy_engine = context.get("policy_engine")
        if not policy_engine:
            logger.error("interpreter_no_policy_engine")
            return {"status": "error", "reason": "PolicyEngine requerida en contexto — ejecución denegada"}

        val = policy_engine.validate(task)
        if not val.allowed:
            return {"status": "error", "reason": f"PolicyEngine Denied: {val.reason}"}

        # Ejecutar en Sandbox
        try:
            container = self.sandbox.container_name

            # Never pass task as a raw string to bash -c — use shlex.split
            # to tokenize the command into safe arguments
            try:
                cmd_parts = shlex.split(task)
            except ValueError as e:
                return {"status": "error", "reason": f"Comando malformado: {e}"}

            # Execute without bash -c — each argument is passed individually
            args = ["docker", "exec", "--", container] + cmd_parts
            res = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if res.returncode == 0:
                return {"status": "success", "output": res.stdout}
            else:
                return {"status": "error", "output": res.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "error", "reason": "TimeoutExpired"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}
