import os
import tempfile
import ast
from .errors import SandboxViolation

FORBIDDEN_PATHS = [
    "/etc",
    "/root",
    "/proc",
    "/sys",
    "/var/run/docker.sock"
]

class SandboxFS:
    def __init__(self):
        self._tmp = None

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        return self._tmp.name

    def __exit__(self, exc_type, exc, tb):
        if self._tmp:
            self._tmp.cleanup()

def validate_code(code: str):
    if "\x00" in code:
        raise SandboxViolation("Null byte detected")

    # Anti-payloads obvios
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        # Invalid python code, allow the runtime to fail naturally or reject here
        raise SandboxViolation(f"Syntax error in submitted code: {e}")
        
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Dependiendo del nivel de restricción, bloquear imports. 
            # Por ahora lo mantenemos flexible o definimos policy.
            # En v1 bloqueamos os, subprocess, sys
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("os", "subprocess", "sys", "socket"):
                        raise SandboxViolation(f"Importing {alias.name} is not allowed")
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("os", "subprocess", "sys", "socket"):
                    raise SandboxViolation(f"Importing from {node.module} is not allowed")
