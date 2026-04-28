from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json

app = FastAPI()

TELEMETRY_FILE = Path("/tmp/kernell_telemetry/telemetry_buffer_latest.jsonl")

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
        "avg_savings": sum(r["savings_pct"] for r in rows)/len(rows),
        "avg_quality_drop": sum(r["quality_drop"] for r in rows)/len(rows),
    }

app.mount("/", StaticFiles(directory="kernell_os_sdk/web_dashboard/static", html=True), name="static")

from kernell_os_sdk.runtime.version_manager import VersionManager
import subprocess
import sys

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
