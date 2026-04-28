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

app.mount("/", StaticFiles(directory="kernell_os_sdk/web_dashboard/static", html=True), name="static")
