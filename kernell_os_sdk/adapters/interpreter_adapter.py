import subprocess
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
        
        # En una integración completa, aquí usaríamos un LLM para compilar la tarea
        # en un script de bash/python. Por ahora, asumimos que 'task' es un comando.
        
        # Validar en PolicyEngine si está disponible en context
        policy_engine = context.get("policy_engine")
        if policy_engine:
            val = policy_engine.validate(task)
            if not val.allowed:
                return {"status": "error", "reason": f"PolicyEngine Denied: {val.reason}"}

        # Ejecutar en Sandbox
        try:
            container = self.sandbox.container_name
            # Para mayor seguridad, nunca se usa shell=True
            args = ["docker", "exec", "--", container, "bash", "-c", task]
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
