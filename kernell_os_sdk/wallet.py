"""
Kernell OS SDK — Wallet & M2M Commerce
═══════════════════════════════════════
Handles $KERN payments between agents via the Kernell Agent Protocol (KAP).
Agents can receive payments for completed tasks and pay other agents for services.

Usage:
    wallet = Wallet(config=my_config)

    balance = wallet.get_balance()
    escrow_id = wallet.request_payment_escrow(amount=50.0, task_id="t1", payer_id="agent_2")
    wallet.release_escrow(escrow_id)
"""
import logging
from typing import Optional

import httpx

from .config import default_config, KernellConfig

logger = logging.getLogger("kernell.wallet")

# Default timeout for all HTTP operations (seconds)
REQUEST_TIMEOUT = 10.0


class Wallet:
    """
    Handles M2M commerce via the Kernell Agent Protocol (KAP).

    Each agent has a volatile $KERN wallet for internal transactions
    and optionally a Solana SPL wallet for on-chain settlement.
    """

    def __init__(self, config: Optional[KernellConfig] = None):
        self.config = config or default_config
        self._client = httpx.Client(
            base_url=self.config.gateway_url,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            timeout=REQUEST_TIMEOUT,
        )

    def get_balance(self) -> float:
        """Fetch the current $KERN balance from the gateway.

        Returns 0.0 if no wallet is configured or the gateway is unreachable.
        """
        if not self.config.wallet_address:
            logger.debug("No wallet address configured — balance is 0.0")
            return 0.0

        try:
            endpoint = f"/api/v1/wallet/{self.config.wallet_address}/balance"
            response = self._client.get(endpoint)
            response.raise_for_status()
            return response.json().get("balance", 0.0)
        except httpx.HTTPStatusError as error:
            logger.warning(f"Balance check failed (HTTP {error.response.status_code})")
            return 0.0
        except httpx.RequestError as error:
            logger.warning(f"Balance check failed (network): {error}")
            return 0.0

    def request_payment_escrow(
        self,
        amount: float,
        task_id: str,
        payer_id: str,
    ) -> str:
        """Request funds to be held in escrow for a specific task.

        Args:
            amount: Number of $KERN tokens to escrow.
            task_id: Unique identifier for the task being paid for.
            payer_id: Agent ID of the entity funding the escrow.

        Returns:
            The escrow ID string.

        Raises:
            httpx.HTTPStatusError: If the gateway rejects the request.
        """
        payload = {
            "amount": amount,
            "task_id": task_id,
            "payer": payer_id,
            "payee": self.config.wallet_address,
        }
        response = self._client.post("/api/v1/escrow/create", json=payload)
        response.raise_for_status()

        escrow_id = response.json().get("escrow_id", "")
        logger.info(f"Escrow created: {escrow_id} ({amount} KERN for task {task_id})")
        return escrow_id

    def release_escrow(self, escrow_id: str) -> bool:
        """Release escrowed funds upon task completion.

        Args:
            escrow_id: The escrow ID returned by request_payment_escrow().

        Returns:
            True if the release was successful, False otherwise.
        """
        try:
            response = self._client.post(f"/api/v1/escrow/{escrow_id}/release")
            is_success = response.status_code == 200
            if is_success:
                logger.info(f"Escrow {escrow_id} released successfully")
            else:
                logger.warning(f"Escrow {escrow_id} release failed (HTTP {response.status_code})")
            return is_success
        except httpx.RequestError as error:
            logger.error(f"Escrow release failed (network): {error}")
            return False

    def close(self):
        """Close the HTTP client and release connections."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
