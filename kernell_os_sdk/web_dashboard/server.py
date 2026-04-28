from __future__ import annotations
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import json
import httpx
import subprocess
import sys

app = FastAPI()

TELEMETRY_FILE = Path("/tmp/kernell_telemetry/telemetry_buffer_latest.jsonl")
_static_dir = Path(__file__).parent / "static"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/events")
def get_events(limit: int = 50):
    if not TELEMETRY_FILE.exists():
        return []
    lines = TELEMETRY_FILE.read_text().splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]

@app.get("/benchmark/latest")
def latest_benchmark():
    runs = sorted(Path("benchmarks/runs").glob("*.jsonl"))
    if not runs:
        return {"status": "no_data"}
    rows = [json.loads(l) for l in open(runs[-1])]
    return {
        "tasks": len(rows),
        "avg_savings": sum(r.get("savings_pct", r.get("savings", 0)) for r in rows)/len(rows),
        "avg_quality_drop": sum(r["quality_drop"] for r in rows)/len(rows),
    }

from kernell_os_sdk.runtime.version_manager import VersionManager

@app.get("/version/status")
def version_status():
    manager = VersionManager()
    curr = manager.current_version()
    latest = manager.latest_version()
    return {
        "current": curr,
        "latest": latest,
        "has_update": manager.has_update(),
        "changelog": manager.get_changelog()
    }

@app.post("/version/upgrade")
def version_upgrade():
    subprocess.Popen([
        sys.executable, "-m", "pip", "install", "--upgrade", "kernell-os-sdk"
    ])
    return {"status": "updating"}

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api(request: Request, path: str):
    url = f"http://127.0.0.1:8502/api/{path}"
    async with httpx.AsyncClient() as client:
        body = await request.body()
        proxy_req = client.build_request(
            request.method,
            url,
            headers=request.headers.raw,
            content=body,
            params=request.query_params
        )
        try:
            proxy_res = await client.send(proxy_req)
            return Response(
                content=proxy_res.content,
                status_code=proxy_res.status_code,
                headers=dict(proxy_res.headers)
            )
        except Exception as e:
            return Response(content=json.dumps({"error": str(e), "message": "Kernell OS API Server not running on 8502"}), status_code=502)

app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

@app.get("/{path:path}")
async def serve_spa(path: str):
    file_path = _static_dir / path
    if file_path.is_file() and file_path.exists():
        return FileResponse(file_path)
    return FileResponse(_static_dir / "index.html")
