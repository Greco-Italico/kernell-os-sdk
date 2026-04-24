import os
from typing import Dict, Any
from .base import BaseAdapter
from ..runtime import SubprocessRuntime, ExecutionRequest, ExecutionTimeout, SandboxViolation
import structlog

logger = structlog.get_logger("kernell.adapters.python_runtime")

class PythonRuntimeAdapter(BaseAdapter):
    """
    Ejecuta código Python arbitrario en un entorno nativo seguro (Fase 1A).
    Aisla la memoria, sistema de archivos y prohíbe red/imports sensibles.
    """
    capability_name = "python_execution"

    def __init__(self):
        # Same dual gate as SubprocessRuntime.execute (env + constructor flag).
        allow = os.environ.get("KERNELL_ALLOW_UNSAFE_SUBPROCESS_RUNTIME") == "1"
        self.runtime = SubprocessRuntime(allow_insecure_exec=allow)

    def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("python_runtime_executing", task_snippet=task[:50])
        
        token = context.get("capability_token")
        verifier = context.get("capability_verifier")
        policy_engine = context.get("capability_policy")
        
        if not (token and verifier and policy_engine):
            logger.error("python_runtime_missing_capability_auth")
            return {"status": "error", "reason": "Missing CapabilityAuth: token, verifier, or policy is missing from context"}

        # 1. Verificar firma, expiración y replay
        if not verifier.verify(token):
            logger.warning("invalid_capability_token", subject=token.subject)
            return {"status": "error", "reason": "Invalid or expired capability token"}

        req = ExecutionRequest(
            code=task,
            timeout=10, # Limite base global (el token puede restringirlo aún más, pero no agrandarlo)
            memory_limit_mb=token.capability.max_memory_mb,
            cpu_limit=token.capability.max_cpu,
            allow_network=token.capability.allow_network
        )

        # 2. Enforce de políticas del token y vinculación al código (code_hash)
        try:
            policy_engine.enforce(token, req)
        except Exception as e:
            logger.warning("capability_policy_violation", reason=str(e))
            return {"status": "error", "reason": f"CapabilityPolicy Violation: {str(e)}"}

        try:
            result = self.runtime.execute(req)
            
            if result.timed_out:
                return {"status": "error", "reason": "ExecutionTimeout: Procesamiento tardó demasiado."}
            elif result.exit_code == 0:
                return {"status": "success", "output": result.stdout}
            else:
                return {"status": "error", "output": result.stderr}
                
        except SandboxViolation as e:
            logger.critical("sandbox_violation", reason=str(e))
            return {"status": "error", "reason": f"SandboxViolation: {str(e)}"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}
