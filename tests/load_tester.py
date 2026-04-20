"""
Kernell OS — Load Tester for Firecracker Runtime (Crucible Node Validation)

Simulates 4 core scenarios:
1. STEADY: Consistent traffic to test auto-scaler & baseline latency
2. BURST: Spikes from 0 to 300 req/s to test backpressure & token buckets
3. NOISY_NEIGHBOR: One tenant spams 80% of traffic, testing fairness/isolation
4. SLOW_EXECUTION: Payloads that sleep, testing concurrency & FD limits
"""

import asyncio
import httpx
import random
import time
import argparse
from typing import List

# SaaS Plans mapped from our architecture
TENANT_PROFILES = [
    ("free", 0.70),        # 70% of traffic is free tier
    ("pro", 0.20),         # 20% of traffic is pro tier
    ("enterprise", 0.10),  # 10% of traffic is enterprise tier
]

PAYLOADS = [
    # Fast / normal
    ('print("hello world")', 0.9),
    # Slow execution (tests concurrency limits)
    ('import time; time.sleep(0.5); print("done")', 0.1),
]

class LoadTester:
    def __init__(self, target_url: str):
        self.url = target_url
        self.stats = {"ok": 0, "429": 0, "402": 0, "503": 0, "error": 0}
        self.latencies = []
        self.running = True

    def pick_tenant(self, noisy: bool = False) -> str:
        if noisy and random.random() < 0.8:
            return "free_noisy_neighbor"  # 80% traffic from one bad actor
            
        r = random.random()
        cumulative = 0
        for t, p in TENANT_PROFILES:
            cumulative += p
            if r <= cumulative:
                return t
        return "free"

    def pick_payload(self) -> str:
        r = random.random()
        cumulative = 0
        for code, p in PAYLOADS:
            cumulative += p
            if r <= cumulative:
                return code
        return PAYLOADS[0][0]

    async def worker(self, client: httpx.AsyncClient, rate_per_sec: float, noisy: bool):
        interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0
        
        while self.running:
            tenant = self.pick_tenant(noisy)
            code = self.pick_payload()

            payload = {
                "code": code,
                "timeout": 2,
                "tenant_id": tenant
            }

            try:
                start = time.time()
                r = await client.post(self.url, json=payload)
                latency = time.time() - start

                # Record stats
                if r.status_code == 200:
                    self.stats["ok"] += 1
                    self.latencies.append(latency)
                elif r.status_code == 429:
                    self.stats["429"] += 1
                elif r.status_code == 402:
                    self.stats["402"] += 1
                elif r.status_code == 503:
                    self.stats["503"] += 1
                else:
                    self.stats["error"] += 1

            except Exception:
                self.stats["error"] += 1

            if interval > 0:
                await asyncio.sleep(interval)

    async def reporter(self):
        """Prints live stats to the console."""
        start_time = time.time()
        while self.running:
            await asyncio.sleep(2)
            elapsed = time.time() - start_time
            reqs = sum(self.stats.values())
            rps = reqs / elapsed if elapsed > 0 else 0
            
            p95 = 0
            if self.latencies:
                lats = sorted(self.latencies)
                p95 = lats[int(len(lats) * 0.95)]
                
            print(f"[LIVE] RPS: {rps:.1f} | p95: {p95:.3f}s | OK: {self.stats['ok']} | "
                  f"429: {self.stats['429']} | 503: {self.stats['503']} | Err: {self.stats['error']}")

    async def run_scenario(self, concurrency: int, rps_per_worker: float, duration: int, noisy: bool = False):
        print(f"Starting Scenario: {concurrency} workers, {rps_per_worker} rps/worker, duration {duration}s")
        self.stats = {k: 0 for k in self.stats}
        self.latencies = []
        self.running = True
        
        limits = httpx.Limits(max_keepalive_connections=None, max_connections=None)
        async with httpx.AsyncClient(timeout=10.0, limits=limits) as client:
            tasks = [self.worker(client, rps_per_worker, noisy) for _ in range(concurrency)]
            rep_task = asyncio.create_task(self.reporter())
            
            await asyncio.sleep(duration)
            self.running = False
            
            await asyncio.gather(*tasks, return_exceptions=True)
            rep_task.cancel()
            print("--- Scenario Complete ---")


async def main():
    parser = argparse.ArgumentParser(description="Kernell OS Load Tester")
    parser.add_argument("--url", default="http://127.0.0.1:8080/execute", help="Target API URL")
    parser.add_argument("--scenario", choices=["steady", "burst", "noisy"], default="steady")
    args = parser.parse_args()

    tester = LoadTester(args.url)

    if args.scenario == "steady":
        # 50 workers x 2 rps = 100 RPS steady state
        await tester.run_scenario(concurrency=50, rps_per_worker=2.0, duration=60)
        
    elif args.scenario == "burst":
        # 0 to 300 req/s instantly
        await tester.run_scenario(concurrency=300, rps_per_worker=1.0, duration=30)
        
    elif args.scenario == "noisy":
        # Simulate noisy neighbor abusing fairness queue
        await tester.run_scenario(concurrency=100, rps_per_worker=2.0, duration=45, noisy=True)

if __name__ == "__main__":
    asyncio.run(main())
