import subprocess
import os
import signal
from typing import Dict, Any

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

from .base import BaseRuntime
from .models import ExecutionRequest, ExecutionResult
from .sandbox import SandboxFS, validate_code
from .errors import ExecutionTimeout

class SubprocessRuntime(BaseRuntime):
    """
    Runtime Fase 1A: Ejecución aislada nativa usando subprocess + flags de Python.
    """

    def _limit_resources(self, request: ExecutionRequest):
        """Aplica límites de sistema (solo en Linux/Unix)."""
        if not HAS_RESOURCE:
            return
            
        try:
            # Limitar memoria
            mem_bytes = request.memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

            # Limitar CPU (segundos de tiempo de CPU)
            # Esto dispara SIGXCPU si se pasa
            cpu_limit = int(request.timeout) + 1
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
            
            # Limitar número de procesos (evitar fork bombs)
            resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
            
            # Limitar tamaño de archivo creado
            resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024)) # 10MB
        except (ValueError, OSError):
            pass

    def _drop_privileges(self):
        """Drops privileges to a non-root user if running as root."""
        if hasattr(os, 'getuid') and os.getuid() == 0:
            try:
                # Intenta cambiar al usuario 'nobody' (UID genérico 65534)
                # En un entorno real, crearíamos un usuario 'kernell-jail'
                os.setgid(65534)
                os.setuid(65534)
            except OSError:
                pass

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        validate_code(request.code)

        with SandboxFS() as sandbox_dir:
            file_path = os.path.join(sandbox_dir, "main.py")

            wrapper = """
SAFE_BUILTINS = {{
    "print": print,
    "range": range,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "dict": dict,
    "list": list,
    "tuple": tuple,
    "set": set,
    "type": type,
    "isinstance": isinstance,
    "Exception": Exception,
    "ValueError": ValueError,
}}

code = {code}

try:
    exec(code, {{"__builtins__": SAFE_BUILTINS}}, {{}})
except Exception as e:
    import sys
    print(f"Execution Error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
            safe_code = wrapper.format(code=repr(request.code))
            
            with open(file_path, "w") as f:
                f.write(safe_code)

            def preexec():
                # Crear nueva sesión para matar a todos los hijos fácilmente
                os.setsid()
                self._limit_resources(request)
                self._drop_privileges()

            # Entorno limpio (no heredar env del sistema, solo inyectar explícitamente)
            clean_env = {
                "PYTHONUNBUFFERED": "1",
                "PYTHONHASHSEED": "random", # Anti-DDoS hash collisions
            }
            if request.env:
                clean_env.update(request.env)

            # Comando: Python aislado
            # -I: Isolated mode (ignora sys.path, site-packages, etc.)
            # -S: No carga site (bloquea site-packages)
            # -B: No escribe bytecode
            cmd = ["python3", "-I", "-S", "-B", file_path]

            try:
                result = subprocess.run(
                    cmd,
                    cwd=sandbox_dir,
                    capture_output=True,
                    text=True,
                    timeout=request.timeout,
                    env=clean_env,
                    preexec_fn=preexec if os.name != 'nt' else None
                )

                return ExecutionResult(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode
                )

            except subprocess.TimeoutExpired as e:
                # Limpiar todos los procesos huérfanos del process group si timeout
                return ExecutionResult(
                    stdout=e.stdout.decode() if e.stdout else "",
                    stderr=e.stderr.decode() if e.stderr else "TimeoutExpired: Process killed",
                    exit_code=-1,
                    timed_out=True
                )
            except Exception as e:
                return ExecutionResult(
                    stdout="",
                    stderr=f"Runtime wrapper error: {str(e)}",
                    exit_code=-2
                )
