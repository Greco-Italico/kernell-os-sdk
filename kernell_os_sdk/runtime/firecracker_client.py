import httpx
import asyncio
import time
from typing import Optional

class CircuitBreaker:
    def __init__(self, failure_threshold=5, base_recovery_time=10):
        self.failure_threshold = failure_threshold
        self.base_recovery_time = base_recovery_time
        self.recovery_time = base_recovery_time
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    def record_success(self):
        self.failures = 0
        self.recovery_time = self.base_recovery_time
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            # Backoff exponencial: 10s, 20s, 40s, max 60s
            exponent = self.failures - self.failure_threshold
            self.recovery_time = min(self.base_recovery_time * (2 ** exponent), 60)

    def can_execute(self):
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_time:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True

class FirecrackerClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 1.2,
    ):
        self.base_url = base_url
        self.token = token
        self.timeout = timeout
        self.cb = CircuitBreaker()

    async def execute(self, code: str) -> dict:
        if not self.cb.can_execute():
            raise RuntimeError("CircuitBreakerOpen")

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/execute",
                    json={"code": code},
                    headers=headers,
                )

            if resp.status_code != 200:
                raise RuntimeError(f"BadStatus {resp.status_code}")

            self.cb.record_success()
            return resp.json()

        except Exception as e:
            self.cb.record_failure()
            raise e
