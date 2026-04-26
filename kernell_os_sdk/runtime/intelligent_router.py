import random
import asyncio
import logging

logger = logging.getLogger("kernell.router")

class IntelligentRouter:
    def __init__(
        self,
        nsjail_executor,
        firecracker_client,
        metrics,
        config
    ):
        self.nsjail = nsjail_executor
        self.fc = firecracker_client
        self.metrics = metrics
        self.config = config

    async def route(self, code: str):
        mode = self.config.get("FIRECRACKER_MODE", "off")
        enabled = self.config.get("FIRECRACKER_ENABLED", False)
        
        if not enabled or mode == "off":
            return await self._nsjail(code)
            
        if mode == "shadow":
            return await self._shadow_mode(code)
            
        if mode == "canary":
            return await self._canary_mode(code)
            
        return await self._nsjail(code)

    # ------------------------
    # SHADOW MODE
    # ------------------------
    async def _shadow_mode(self, code: str):
        result = await self._nsjail(code)
        # fire and forget
        asyncio.create_task(self._firecracker_shadow(code, result))
        return result

    async def _firecracker_shadow(self, code, expected):
        try:
            fc_result = await self.fc.execute(code)
            self.metrics.inc("firecracker_shadow_calls")
            
            fc_stdout = fc_result.get("stdout", "")
            exp_stdout = expected.stdout if hasattr(expected, "stdout") else expected.get("stdout", "")
            
            if fc_stdout != exp_stdout:
                self.metrics.inc("firecracker_divergence")
                logger.warning("firecracker_divergence_detected", code=code[:50])
        except Exception as e:
            self.metrics.inc("firecracker_shadow_failures")
            logger.debug(f"shadow_execution_failed: {e}")

    # ------------------------
    # CANARY MODE
    # ------------------------
    async def _canary_mode(self, code: str):
        percent = self.config.get("FIRECRACKER_CANARY_PERCENT", 0.01)
        if random.random() < percent:
            try:
                result = await self.fc.execute(code)
                self.metrics.inc("firecracker_success")
                return result
            except Exception as e:
                self.metrics.inc("firecracker_failures")
                logger.warning(f"canary_fallback_triggered: {e}")
                return await self._nsjail(code)
        else:
            return await self._nsjail(code)

    # ------------------------
    # NSJAIL (fallback)
    # ------------------------
    async def _nsjail(self, code: str):
        # Determine if execution is async
        if asyncio.iscoroutinefunction(self.nsjail.execute):
            return await self.nsjail.execute(code)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.nsjail.execute, code)
