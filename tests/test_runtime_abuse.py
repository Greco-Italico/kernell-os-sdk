import pytest
from kernell_os_sdk.runtime import SubprocessRuntime, DockerRuntime, ExecutionRequest, SandboxViolation

@pytest.fixture(params=["subprocess", "docker"])
def runtime(request):
    if request.param == "subprocess":
        return SubprocessRuntime()
    else:
        # Nota: DockerRuntime asume Docker demon activo.
        return DockerRuntime()

def test_bypass_import(runtime):
    # Intentar usar reflexión de builtins
    code = "__builtins__.__dict__['__import__']('os').system('id')"
    # El AST analyzer lo va a dejar pasar porque no es una import statement directa
    req = ExecutionRequest(code=code, timeout=2)
    result = runtime.execute(req)
    
    # Debería fallar con KeyError o AttributeError porque __builtins__ fue reemplazado
    assert result.exit_code != 0
    assert "Execution Error" in result.stderr
    assert "KeyError" in result.stderr or "AttributeError" in result.stderr

def test_indirect_sys_access(runtime):
    code = "().__class__.__base__.__subclasses__()"
    req = ExecutionRequest(code=code, timeout=2)
    result = runtime.execute(req)
    
    # Este comando genera output gigante si accede a las subclases,
    # pero al no tener acceso a clases peligrosas no debería poder escalar fácilmente.
    # A nivel de ejecución pura el string se evalúa. 
    # Solo aseguramos que no crashea ni da timeout y no devuelve paths de escape obvios.
    assert result.exit_code == 0
    assert "subprocess" not in result.stdout

def test_file_system_escape(runtime):
    code = "open('/etc/passwd').read()"
    req = ExecutionRequest(code=code, timeout=2)
    result = runtime.execute(req)
    
    # 'open' ya no existe en SAFE_BUILTINS
    assert result.exit_code != 0
    assert "Execution Error: NameError: name 'open' is not defined" in result.stderr

def test_memory_bomb(runtime):
    # Limite de memoria 128MB
    code = "a = 'A' * (10**9)" # ~1GB
    req = ExecutionRequest(code=code, timeout=2, memory_limit_mb=128)
    result = runtime.execute(req)
    
    # Debería crashear o dar error por límite de memoria (MemoryError si python lo atrapa, o exit_code < 0 si lo mata el OS)
    assert "MemoryError" in result.stderr or result.exit_code != 0

def test_cpu_burn(runtime):
    code = "while True:\n    pass"
    req = ExecutionRequest(code=code, timeout=1) # 1 sec
    result = runtime.execute(req)
    
    assert result.timed_out is True

def test_fork_bomb(runtime):
    code = "import os\nwhile True:\n    os.fork()"
    req = ExecutionRequest(code=code, timeout=2)
    try:
        result = runtime.execute(req)
    except SandboxViolation:
        # El AST lo bloquea
        pass
    else:
        # Si de alguna forma lograra saltar el AST
        assert result.timed_out is True or result.exit_code != 0

def test_ast_import_block(runtime):
    code = "import subprocess"
    req = ExecutionRequest(code=code, timeout=2)
    with pytest.raises(SandboxViolation):
        runtime.execute(req)
