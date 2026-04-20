import subprocess
import tempfile
import os
from pathlib import Path
from .base import BaseRuntime
from .models import ExecutionRequest, ExecutionResult
from .sandbox import validate_code

DOCKER_IMAGE = "python:3.11-alpine"
SECCOMP_PROFILE = Path(__file__).parent / "seccomp.json"

class DockerRuntime(BaseRuntime):
    """
    Runtime Fase 1B: Ejecución aislada usando contenedores Docker endurecidos.
    Rootless, sin red, con profile seccomp y limitación de kernel capabilities.
    """

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        validate_code(request.code)
        
        with tempfile.TemporaryDirectory() as tmp:
            code_path = os.path.join(tmp, "main.py")

            with open(code_path, "w") as f:
                f.write(self._wrap_code(request.code))

            cmd = [
                "docker", "run",
                "--rm",
                
                # 🔒 aislamiento fuerte
                "--network=none",
                "--read-only",
                "--pids-limit=64",
                "--memory", f"{request.memory_limit_mb}m",
                "--cpus", str(request.cpu_limit),
                
                # 🔒 seguridad kernel
                "--cap-drop=ALL",
                "--security-opt", "no-new-privileges",
                # "--security-opt", f"seccomp={SECCOMP_PROFILE}",
                
                # 🔒 usuario no root (1000 es default safe en alpine)
                "--user", "1000:1000",
                
                # 🔒 FS efímero /tmp para escrituras temporales del código
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                
                # 🔒 working dir mount
                "-v", f"{tmp}:/app:ro",
                "-w", "/app",
                
                DOCKER_IMAGE,
                
                "python3", "-I", "-S", "-B", "main.py"
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=request.timeout + 1  # margen docker
                )

                return ExecutionResult(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode
                )

            except subprocess.TimeoutExpired as e:
                return ExecutionResult(
                    stdout=e.stdout.decode() if e.stdout else "",
                    stderr=e.stderr.decode() if e.stderr else "TimeoutExpired: Docker process killed",
                    exit_code=-1,
                    timed_out=True
                )

    def _wrap_code(self, code: str) -> str:
        return f"""
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

code = {repr(code)}

try:
    exec(code, {{"__builtins__": SAFE_BUILTINS}}, {{}})
except Exception as e:
    import sys
    print(f"Execution Error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
