from kernell_os_sdk.runtime import DockerRuntime, ExecutionRequest
runtime = DockerRuntime()
code = "__builtins__.__dict__['__import__']('os').system('id')"
req = ExecutionRequest(code=code, timeout=2)
result = runtime.execute(req)
print(f"EXIT CODE: {result.exit_code}")
print(f"STDOUT: {result.stdout}")
print(f"STDERR: {result.stderr}")
