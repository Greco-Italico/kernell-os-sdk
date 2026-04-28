from __future__ import annotations
import subprocess

def main() -> int:
    print("\n📊 Starting Kernell Dashboard...\n")
    subprocess.run([
        "uvicorn",
        "kernell_os_sdk.web_dashboard.server:app",
        "--host", "0.0.0.0",
        "--port", "8765"
    ])
    return 0
