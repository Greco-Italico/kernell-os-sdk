import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Optional
import secrets as secrets_module

# Load Prometheus metrics early so they register before the server starts
from . import metrics as prom
from .orchestrator import RuntimeOrchestrator
from ..firecracker_runtime import FirecrackerRuntime
from ..models import ExecutionRequest

app = FastAPI(title="Kernell OS Firecracker Control Plane")

# Global instances
runtime = None
orchestrator = None


class ExecutePayload(BaseModel):
    code: str
    timeout: int = 2
    memory_limit_mb: int = 128
    tenant_id: str = "default_tenant"
    request_id: Optional[str] = None

def _require_control_token(request) -> None:
    token = os.getenv("FC_CONTROL_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="ControlPlaneUnavailable: FC_CONTROL_TOKEN not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    presented = auth[7:].strip()
    if not secrets_module.compare_digest(presented, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.on_event("startup")
async def startup_event():
    global runtime, orchestrator
    
    # Extract paths from env or use defaults
    kernel_path = os.getenv("FC_KERNEL", "/var/lib/kernell/vmlinux")
    rootfs_path = os.getenv("FC_ROOTFS", "/var/lib/kernell/rootfs.ext4")
    
    if not os.path.exists(kernel_path):
        print(f"WARN: Kernel not found at {kernel_path} (Safe to ignore if running dummy/mock tests)")
        
    runtime = FirecrackerRuntime(kernel_path, rootfs_path)
    
    # 50 worker threads matching our Enterprise Max Concurrency tier
    orchestrator = RuntimeOrchestrator(runtime, num_workers=50)
    orchestrator.start()
    
    # Start Prometheus metrics server on a separate port
    prom.start_metrics_server(port=9090)
    print("Prometheus metrics exposed on port 9090")


@app.on_event("shutdown")
async def shutdown_event():
    global runtime, orchestrator
    if orchestrator:
        orchestrator.stop()
    if runtime and hasattr(runtime.pool, "running"):
        runtime.pool.running = False


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/execute")
async def execute(payload: ExecutePayload, request: Request):
    _require_control_token(request)
    req = ExecutionRequest(
        code=payload.code,
        timeout=payload.timeout,
        memory_limit_mb=payload.memory_limit_mb,
        tenant_id=payload.tenant_id,
        request_id=payload.request_id
    )
    
    # Use the orchestrator (Fair Queuing + Async Worker Pool) instead of direct execution
    future = orchestrator.submit(req, request_id=payload.request_id)
    result = future.result()  # Blocks until execution completes or fails
    
    if result.exit_code == 402:
        raise HTTPException(status_code=402, detail=result.stderr)
    if result.exit_code == 429:
        raise HTTPException(status_code=429, detail=result.stderr)
    if result.exit_code == 503:
        raise HTTPException(status_code=503, detail=result.stderr)
        
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out
    }


def main():
    host = os.getenv("FC_CONTROL_PLANE_HOST", "127.0.0.1")
    port = int(os.getenv("FC_CONTROL_PLANE_PORT", "8080"))
    if host == "0.0.0.0" and not os.getenv("FC_ALLOW_PUBLIC_BIND", "").strip():
        raise RuntimeError("Refusing to bind 0.0.0.0 without FC_ALLOW_PUBLIC_BIND=1")
    uvicorn.run("kernell_os_sdk.runtime.firecracker.server:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
