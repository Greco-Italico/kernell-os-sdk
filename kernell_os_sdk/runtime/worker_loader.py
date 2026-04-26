import json
import os
import asyncio
from kernell_os_sdk.runtime.scheduler import WorkerState

def load_workers(path: str):
    if not os.path.exists(path):
        return []
        
    with open(path, "r") as f:
        data = json.load(f)
        
    workers = []
    for w in data.get("workers", []):
        if not w.get("enabled", True):
            continue
        workers.append(
            WorkerState(
                id=w["id"],
                url=w["url"],
                max_concurrency=w.get("max_concurrency", 8)
            )
        )
    return workers

async def reload_loop(scheduler, path):
    last_mtime = 0
    while True:
        try:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                if mtime != last_mtime:
                    new_workers = load_workers(path)
                    
                    # Merge to preserve health states of existing workers
                    async with scheduler._lock:
                        state_map = {w.url: w for w in scheduler.workers}
                        merged = []
                        for nw in new_workers:
                            if nw.url in state_map:
                                existing = state_map[nw.url]
                                existing.id = nw.id
                                existing.max_concurrency = nw.max_concurrency
                                merged.append(existing)
                            else:
                                merged.append(nw)
                                
                        scheduler.workers = merged
                    last_mtime = mtime
        except Exception:
            pass
        await asyncio.sleep(5)
